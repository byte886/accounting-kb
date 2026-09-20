#!/usr/bin/env node
/**
 * fetch_question_video_keys.js
 * ------------------------------------------------------------------
 * 一次性抓取「题目级讲解视频」的 AES-128 解密 key。
 *
 * 背景（已实证，详见 docs/development/guides/exam-workflow.md）：
 *  - 题目级视频按综合大题聚合，vid 挂在子题 questionAnswer.questionVideo.vid；
 *  - m3u8 为标准 HLS AES-128，分片在 glive2-video-resource.gaodun.com；
 *  - 但 key 不直接下发：replay/authorize 直连/带 cookie 均被拒（40301 / 登录超时），
 *    播放器用 wasm 把 authorize 的 108B 加密包解成 16B key，明文只存在于 Worker 内存；
 *  - 解法：CDP 打开逐题解析页 -> 点封面图加载 sub-study-player -> hook Worker，
 *    从 postMessage 的 response 取 32B（前 16B 即 AES key，ASCII hex 字符串形态）；
 *  - key 为「视频级固定值」，跨会话不变（同 vid 两次抓取一致），故只需抓一次，
 *    之后下载/解密/转写全部离线可重跑，不再依赖浏览器。
 *
 * 产物：data/_workspace/<profile>/papers/qvideo_keys.json  { [vid]: {key, paperId, entry, m3u8} }
 * ------------------------------------------------------------------
 */
const path = require('path');
const fs = require('fs');
const { connectDailyChrome, safeDisconnect, newBackgroundPage, captureFrontmost, restoreFrontmost } = require('./connect_browser.js');
const { workspaceDir } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
// 题目视频 key 台账（税法专属，缺省 profile），落课程工作区 papers
const OUT = workspaceDir('papers', 'qvideo_keys.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 注入主世界：hook Worker 双向 postMessage（Uint8Array 转普通数组）
const HOOK = `(()=>{
  window.__wd=[];
  const push=o=>{try{window.__wd.push(o);}catch(e){}};
  const clone=v=>JSON.parse(JSON.stringify(v,(k,x)=>{
    if(x instanceof Uint8Array)return Array.from(x);
    if(x instanceof ArrayBuffer)return Array.from(new Uint8Array(x));
    return x;}));
  const OW=window.Worker;
  window.Worker=function(...a){
    const w=new OW(...a);
    const op=w.postMessage.bind(w);
    w.postMessage=function(m,t){try{push({dir:'to_worker',msg:clone(m)});}catch(e){}return op(m,t);};
    const oa=w.addEventListener.bind(w);
    w.addEventListener=function(type,l,opt){
      if(type==='message'){const wl=function(e){try{push({dir:'from_worker',msg:clone(e.data)});}catch(x){}return l.apply(this,arguments);};return oa(type,wl,opt);}
      return oa(type,l,opt);};
    return w;};
  window.Worker.prototype=OW.prototype;
})();`;

// 卷 -> 解析页定位 + 带视频大题（答题卡入口 N-1 -> vid）。cs/res 来自 syllabus_full.json
const PAPERS = [
  {
    paperId: 86722, cs: 2225061, res: 2550958,
    targets: [
      ['43-1', '0bf9c069-21cf-4189-8f72-bff490782f60'],
      ['47-1', '3588a5bd-697c-44c5-aa3e-739ea44cd189'],
      ['48-1', 'd9bf2b13-5ad8-41ab-a692-042b52f25222'],
    ],
  },
  {
    paperId: 86723, cs: 2225062, res: 2550959,
    targets: [
      ['44-1', '004ff841-4969-45ba-938a-dbc0ed4ae7df'],
      ['46-1', '5ff8269e-3ca5-4f77-83d3-cf53428425f4'],
      ['47-1', 'd28aaba2-852d-4ebb-bdd2-d048a27fbe3a'],
      ['48-1', '88f83c1e-72c8-41e3-b153-f839dc51c288'],
    ],
  },
];

const urlOf = (p) =>
  `https://glivepro.gaodun.com/course/42660/tiku-resource/cs_item_id/${p.cs}/resource_id/${p.res}/paper_id/${p.paperId}/type/2/resState/1?title=x&homework=0&stageId=74658`;

const clickText = (txt) => `(()=>{
  const el=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&e.textContent.trim()===${JSON.stringify(txt)});
  if(el){el.click();return true;}return false;})()`;

async function grabOne(page, entry) {
  // 开答题卡 -> 点入口子题
  await page.evaluate(clickText('答题卡'));
  await sleep(1100);
  const jumped = await page.evaluate(clickText(entry));
  if (!jumped) throw new Error(`答题卡找不到入口 ${entry}`);
  await sleep(3800);
  await page.mouse.click(400, 400); // 收起弹层
  await sleep(600);
  // 基线：记录当前 __wd 长度，只看本次点击新增
  const base = await page.evaluate(() => (window.__wd || []).length);
  const clicked = await page.evaluate(() => {
    const img = document.querySelector('.sub-tiku__video-box img');
    if (!img) return false;
    img.scrollIntoView(); img.click(); return true;
  });
  if (!clicked) throw new Error(`${entry} 无视频封面`);
  // 轮询等待新增 initHls + 带 response 的 key（最多 22s）
  const deadline = Date.now() + 22000;
  while (Date.now() < deadline) {
    await sleep(1000);
    const got = await page.evaluate((b) => {
      const W = (window.__wd || []).slice(b);
      const hls = W.find((e) => e.msg && e.msg.type === 'initHls' && e.msg.data && e.msg.data.hlsConfig && e.msg.data.hlsConfig.url);
      const kr = W.find((e) => e.dir === 'to_worker' && e.msg && e.msg.response && e.msg.response.length >= 16);
      if (hls && kr) {
        const ascii = String.fromCharCode.apply(null, kr.msg.response.slice(0, 16));
        return { m3u8: hls.msg.data.hlsConfig.url, key: ascii };
      }
      return null;
    }, base);
    if (got) return got;
  }
  throw new Error(`${entry} 等待 m3u8/key 超时`);
}

const __front = captureFrontmost();
(async () => {
  const result = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT)) : {};
  const browser = await connectDailyChrome({ ensureRunning: false });
  try {
    for (const p of PAPERS) {
      const page = await newBackgroundPage(browser);
      await page.evaluateOnNewDocument(HOOK);
      await page.goto(urlOf(p), { waitUntil: 'domcontentloaded', timeout: 45000 });
      await sleep(5000);
      await page.evaluate(clickText('全部解析'));
      await sleep(5000);
      for (const [entry, vid] of p.targets) {
        if (result[vid] && result[vid].key) { console.log(`跳过(已有key) ${entry} ${vid.slice(0, 8)}`); continue; }
        try {
          const g = await grabOne(page, entry);
          result[vid] = { key: g.key, m3u8: g.m3u8, paperId: p.paperId, entry, grabbedAt: new Date().toISOString() };
          fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
          console.log(`✅ ${entry} ${vid.slice(0, 8)} key=${g.key}`);
        } catch (e) {
          console.log(`✘ ${entry} ${vid.slice(0, 8)} ${e.message}`);
        }
      }
      await page.close();
    }
  } finally {
    await safeDisconnect(browser);
    restoreFrontmost(__front); // 授权弹窗若把 Chrome 置前，归还采集前的前台 App
  }
  const ok = Object.keys(result).length;
  console.log(`\n完成，已抓 ${ok}/7，产物 ${OUT}`);
  process.exit(0);
})().catch((e) => { restoreFrontmost(__front); console.error('FAIL', e.stack.slice(0, 300)); process.exit(1); });
