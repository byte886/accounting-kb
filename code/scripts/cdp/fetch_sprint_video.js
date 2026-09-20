#!/usr/bin/env node
/**
 * fetch_sprint_video.js — 冲刺模考「课后视频解析」纯接口下载器（点播，非直播回放）
 *
 * 与正课直播回放的区别（2026-09-05 CDP 侦查实证，见任务报告第五/六段）：
 *   - 正课 live_new：syllabus 自带 v-glive player?token= 回放页，HLS 加密，需 CDP 抓 AES key；
 *   - 冲刺 afterClassResource：只有 UUID videoId（hermesVideoType=2 点播），取流链路为
 *       GET /glive2-vod/api/v1/live/resource?code=<videoId>&res=FHD&lang=zh （JWT）
 *     → result.list.FHD.path = 直链 m3u8，encrypt=0【不加密】，分片为相对路径 N.ts、CDN 公开可下。
 *   故本脚本纯 Node 即可：取 m3u8 → 并发下 ts → 顺序合并 merged.ts（无需 CDP、无需解密）。
 *   后续压缩/转写复用正课管线 compress.sh / transcribe_pipeline.py。
 *
 * 用法：
 *   node scripts/cdp/fetch_sprint_video.js 1|2|3   # 下载某一卷的视频解析
 *   node scripts/cdp/fetch_sprint_video.js all     # 依次下载三卷
 * 产物：data/_workspace/<profile>/tmp/download/sprint-videos/<标题>/.vfetch/{manifest.json, merged.ts}（merged.ts 供压缩步骤）
 */
'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');
const { findJwt, makeHeaders } = require('./gaodun_paper_core');
const { workspaceDir } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
// 冲刺视频下载工作目录（税法专属，缺省 profile），merged.ts 供压缩步骤，完成后清
const OUT_ROOT = workspaceDir('tmp', 'download', 'sprint-videos');
const GW = 'https://apigateway.gaodun.com';
const CONCURRENCY = 12;

const VIDEOS = {
  1: { videoId: '8c48a21d-a57b-4caa-b294-4c220e13cb34', title: '26考季-冲刺模考-税法01-视频解析', minutes: 126 },
  2: { videoId: '7a82267f-e9ef-4bb2-8f71-11fd5eef66a8', title: '26考季-冲刺模考-税法02-视频解析', minutes: 128 },
  3: { videoId: 'd4b346be-4746-42ce-b242-52e7a17597d9', title: '26考季-冲刺模考-税法03-视频解析', minutes: 125 },
};

function log(...a) { console.log(`[svideo ${new Date().toLocaleTimeString()}]`, ...a); }

function getBuf(url, headers, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('too many redirects'));
    https.get(url, { headers: headers || { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume(); return resolve(getBuf(new URL(res.headers.location, url).href, headers, redirects + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode} ${url.slice(0, 100)}`)); }
      const chunks = []; res.on('data', (c) => chunks.push(c)); res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject);
  });
}

async function fetchM3u8Url(videoId, jwt) {
  const H = makeHeaders(jwt);
  const r = await (await fetch(`${GW}/glive2-vod/api/v1/live/resource?code=${videoId}&res=FHD&lang=zh`, { headers: H })).json();
  if (r.status !== 200 || !r.result || !r.result.list || !r.result.list.FHD) throw new Error(`取流失败 ${r.status} ${r.message}`);
  if (r.result.encrypt !== 0) throw new Error(`意外：encrypt=${r.result.encrypt}，本脚本仅处理不加密点播`);
  return { m3u8: r.result.list.FHD.path, duration: r.result.duration };
}

// 并发下载、顺序合并（不加密，直接拼接）
async function downloadAndMerge(m3u8Url, segDir, mergedPath) {
  const m3u8 = (await getBuf(m3u8Url, { 'User-Agent': 'Mozilla/5.0', Referer: 'https://glivepro.gaodun.com/' })).toString('utf8');
  const segs = m3u8.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));
  const base = m3u8Url.slice(0, m3u8Url.lastIndexOf('/') + 1);
  const urls = segs.map((s) => (s.startsWith('http') ? s : base + s));
  log(`分片 ${urls.length} 个，并发=${CONCURRENCY}`);
  const results = new Array(urls.length);
  let done = 0;
  let cursor = 0;
  async function worker() {
    while (cursor < urls.length) {
      const idx = cursor++;
      const f = path.join(segDir, `${idx}.ts`);
      if (fs.existsSync(f) && fs.statSync(f).size > 0) { results[idx] = fs.readFileSync(f); }
      else {
        let lastErr;
        for (let t = 0; t < 3; t++) { try { results[idx] = await getBuf(urls[idx], { 'User-Agent': 'Mozilla/5.0', Referer: 'https://glivepro.gaodun.com/' }); fs.writeFileSync(f, results[idx]); break; } catch (e) { lastErr = e; await new Promise((r) => setTimeout(r, 800 * (t + 1))); } }
        if (!results[idx]) throw lastErr || new Error(`分片${idx}下载失败`);
      }
      done += 1;
      if (done % 50 === 0 || done === urls.length) log(`  分片进度 ${done}/${urls.length}`);
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  const out = fs.createWriteStream(mergedPath);
  for (let i = 0; i < results.length; i++) out.write(results[i]);
  await new Promise((r) => out.end(r));
  return urls.length;
}

async function runOne(seq) {
  const meta = VIDEOS[seq];
  if (!meta) throw new Error(`卷序号应为 1/2/3，收到 ${seq}`);
  const dir = path.join(OUT_ROOT, meta.title, '.vfetch');
  fs.mkdirSync(dir, { recursive: true });
  const segDir = path.join(dir, 'seg'); fs.mkdirSync(segDir, { recursive: true });
  const merged = path.join(dir, 'merged.ts');
  const mfPath = path.join(dir, 'manifest.json');
  if (fs.existsSync(merged) && fs.statSync(merged).size > 1000000) { log(meta.title, '已存在 merged.ts，跳过'); return; }
  const jwt = findJwt();
  const { m3u8, duration } = await fetchM3u8Url(meta.videoId, jwt);
  log(`${meta.title}（约${meta.minutes}分钟/${duration}s）m3u8=${m3u8.slice(0, 90)}...`);
  const t0 = Date.now();
  const segCount = await downloadAndMerge(m3u8, segDir, merged);
  const bytes = fs.statSync(merged).size;
  fs.writeFileSync(mfPath, JSON.stringify({ ...meta, seq, m3u8, duration, segCount, merged, bytes, fetchedAt: new Date().toISOString() }, null, 2));
  log(`完成 ${meta.title}：${segCount}片 ${(bytes / 1024 / 1024).toFixed(1)}MB 用时${((Date.now() - t0) / 1000).toFixed(0)}s`);
}

(async () => {
  const arg = process.argv[2] || '1';
  const seqs = arg === 'all' ? [1, 2, 3] : [Number(arg)];
  for (const s of seqs) { await runOne(s); }
  log('全部结束');
  process.exit(0);
})().catch((e) => { console.error('[svideo FAIL]', e.stack || e.message); process.exit(1); });
