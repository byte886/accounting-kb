#!/usr/bin/env node
/**
 * capture_video_key.js — 经 CDP(puppeteer-core) 打开高顿回放页，注入 Worker hook，
 * 捕获 HLS 的 m3u8(SD/FHD) 与 AES key。走本项目主链路（连接日常 Chrome，复用登录态），
 * 由 fetch_lecture_video.js 内部调用，一般不单独运行。
 *
 * 用法：node scripts/cdp/capture_video_key.js "<回放player?token=URL>" [输出json路径]
 * 输出 JSON：{quality,m3u8,keyAscii}[]（通常含 SD-540P / FHD-1080P 两项）
 * 纯采集：只新开一个临时播放标签、静音播放以触发 worker 流量，抓完即关该标签，不动用户其它页。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { connectDailyChrome, safeDisconnect, newBackgroundPage, captureFrontmost, restoreFrontmost } = require('./connect_browser');
const { workspaceDir } = require('./load_profile');

const playUrl = process.argv[2];
// 手动侦查产物落课程工作区 sniff（缺省 profile），可用第3参数覆盖
const outPath = process.argv[3] || workspaceDir('sniff', 'video_streams.json');
if (!playUrl || !playUrl.startsWith('http')) {
  console.error('用法: node capture_video_key.js "<player?token=URL>" [out.json]');
  process.exit(2);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const isEp3 = /epiphany\.gaodun\.com\/ep3\//.test(playUrl);

// 注入到页面主世界：hook Worker 的双向 postMessage，记录到 window.__workerData
const INIT_HOOK = () => {
  window.__workerData = [];
  const OrigWorker = window.Worker;
  window.Worker = function (...args) {
    const worker = new OrigWorker(...args);
    window.__workerData.push({ type: 'worker_created', url: String(args[0]).substring(0, 200) });
    const origPost = worker.postMessage.bind(worker);
    worker.postMessage = function (msg, transfer) {
      try {
        if (msg && typeof msg === 'object') {
          const clone = JSON.parse(JSON.stringify(msg, (k, v) => {
            if (v instanceof Uint8Array) return Array.from(v);
            if (v instanceof ArrayBuffer) return Array.from(new Uint8Array(v));
            if (v instanceof Date) return v.toISOString();
            return v;
          }));
          window.__workerData.push({ direction: 'to_worker', msg: clone });
        }
      } catch (e) { window.__workerData.push({ direction: 'to_worker', error: String(e) }); }
      return origPost(msg, transfer);
    };
    const origAdd = worker.addEventListener.bind(worker);
    worker.addEventListener = function (type, listener, options) {
      if (type === 'message') {
        const wrapped = function (event) {
          try {
            const data = event.data;
            if (data && typeof data === 'object') {
              let clone;
              try {
                clone = JSON.parse(JSON.stringify(data, (k, v) => {
                  if (v instanceof Uint8Array) return Array.from(v);
                  if (v instanceof ArrayBuffer) return Array.from(new Uint8Array(v));
                  return v;
                }));
              } catch (e) { clone = { error: String(e), keys: Object.keys(data) }; }
              window.__workerData.push({ direction: 'from_worker', msg: clone });
            }
          } catch (e) {}
          return listener.apply(this, arguments);
        };
        return origAdd(type, wrapped, options);
      }
      return origAdd(type, listener, options);
    };
    return worker;
  };
  window.Worker.prototype = OrigWorker.prototype;
};

const __front = captureFrontmost();
(async () => {
  // 连接前已记住前台 App（__front）：连接触发的授权弹窗会把 Chrome 置前，结束/异常时归还
  const frontmost = __front;
  const browser = await connectDailyChrome({ ensureRunning: false });
  // 后台建标签（background:true），不抢占用户正在输入的前台标签焦点；静音后台播放仍触发 worker
  const page = await newBackgroundPage(browser);
  try {
    await page.evaluateOnNewDocument(INIT_HOOK);
    console.log('[1] 打开回放页...');
    await page.goto(playUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(6000);

    console.log('[2] 静音 + 从头播放以触发 hls worker...');
    const play = await page.evaluate(async () => {
      // ep3：gp.video 在 closed shadow DOM，外部 querySelector 找不到，用 gp.play()
      if (window.gp && typeof window.gp.play === 'function') {
        try { await window.gp.play(); return 'ep3-gp-play'; } catch (e) { /* fall through */ }
      }
      if (window.gp && window.gp.video) {
        try { window.gp.video.muted = true; window.gp.video.currentTime = 0; await window.gp.video.play(); return 'ep3-gp-video'; } catch (e) { /* fall through */ }
      }
      const wrap = document.querySelector('.gp-video-wrap');
      if (!wrap) return 'no wrap';
      const customEl = Array.from(wrap.children).find((c) => c.tagName.startsWith('G-'));
      if (!customEl || !customEl.video) return 'no video';
      const v = customEl.video;
      v.muted = true;
      v.currentTime = 0;
      v.play();
      return 'playing';
    });
    console.log('    play =>', play);
    await sleep(9000);

    console.log('[3] 切 1080P...');
    // ep3 与 glive 的清晰度项 DOM 一致（.gp-setting-quality-item：1080P超清/720P高清/540P标清），统一点击
    const fhd = await page.evaluate(() => {
      const find1080 = () => {
        const items = document.querySelectorAll('.gp-setting-quality-item');
        for (const it of items) if (it.textContent.includes('1080')) return it;
        return null;
      };
      let target = find1080();
      if (!target) {
        // 菜单未展开时先 hover 清晰度入口再找
        const q = document.querySelector('.gp-icon-quality,.gp-quality-text,.gp-setting-quality');
        if (q) ['mouseover', 'mouseenter'].forEach((ev) => q.dispatchEvent(new MouseEvent(ev, { bubbles: true })));
        target = find1080();
      }
      if (target) { target.click(); return 'clicked 1080P'; }
      return 'no1080; items=' + Array.from(document.querySelectorAll('.gp-setting-quality-item')).map((i) => i.textContent.trim()).join('|');
    });
    console.log('    ', fhd);
    await sleep(10000);

    console.log('[4] 提取 streams...');
    const streams = await page.evaluate(() => {
      // 两路 CDN 命名不一：.../tc/FHD_xxx.m3u8（含 FHD/HD/SD）vs .../outputm3u8/<uuid>_1080_xxx.m3u8（分辨率后缀）
      // 顺序：先 1080/FHD，再 720/HD（FHD 含 HD 子串须先返回），最后归 SD。
      const classifyQuality = (u = '') => {
        const s = String(u).toUpperCase();
        if (/FHD|1080/.test(s)) return 'FHD-1080P';
        if (/HD|720/.test(s)) return 'HD-720P';
        return 'SD-540P';
      };
      const msgs = window.__workerData || [];
      const inits = msgs.filter((m) => m.msg && m.msg.type === 'initHls');
      const resps = msgs.filter((m) => m.direction === 'to_worker' && m.msg && m.msg.response !== undefined);
      const out = [];
      for (let i = 0; i < inits.length; i += 1) {
        const url = inits[i].msg.data?.hlsConfig?.url || '';
        const resp = resps[i];
        const kb = resp ? resp.msg.response : null;
        out.push({
          quality: classifyQuality(url),
          m3u8: url,
          keyAscii: kb ? String.fromCharCode.apply(null, kb.slice(0, 16)) : null,
          keyBytes: kb ? Array.from(kb) : null,
        });
      }
      // worker 创建/消息计数，便于判断 hook 是否生效
      const meta = {
        workers: msgs.filter((m) => m.type === 'worker_created').length,
        initHls: inits.length,
        keyResp: resps.length,
        total: msgs.length,
      };
      return { out, meta };
    });
    console.log('    meta=', JSON.stringify(streams.meta));
    if (!streams.out.length) {
      console.log('[FAIL] 未捕获 initHls，可能播放器结构变化或未真正播放。meta=', JSON.stringify(streams.meta));
      await page.screenshot({ path: workspaceDir('sniff', 'capture_fail.png') });
      process.exitCode = 3;
    } else {
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      fs.writeFileSync(outPath, JSON.stringify(streams.out, null, 2));
      streams.out.forEach((s) => console.log(`  ${s.quality} key=${s.keyAscii} m3u8=${s.m3u8.slice(0, 90)}...`));
      console.log('[OK] streams ->', outPath);
    }
  } finally {
    try { await page.close(); } catch {}
    await safeDisconnect(browser);
    restoreFrontmost(frontmost); // 授权弹窗若把 Chrome 置前，归还采集前的前台 App
    process.exit(process.exitCode || 0);
  }
})().catch((e) => { restoreFrontmost(__front); console.error('[FAIL]', e.stack || e.message); process.exit(1); });
