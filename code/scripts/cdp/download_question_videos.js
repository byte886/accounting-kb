#!/usr/bin/env node
/**
 * download_question_videos.js — 题目级讲解视频「纯接口」下载解密器
 *
 * 与 fetch_sprint_video.js（整卷视频解析，encrypt=0 不加密）的区别：
 *  题目级视频 encrypt=1，HLS AES-128 加密。key 不直接下发（authorize 被鉴权拦），
 *  已由 fetch_question_video_keys.js 通过 CDP hook Worker 一次性抓到、为视频级固定值，
 *  存于 data/_workspace/<profile>/papers/qvideo_keys.json。本脚本读取固定 key，纯 Node 完成：
 *    JWT 取 SD m3u8 -> 解析全局 IV 与分片 -> 并发下载 -> 逐片 AES-128-CBC 解密 -> 顺序合并。
 *  不再依赖浏览器，可并行、可断点重跑（分片落盘缓存）。
 *
 * 用法：
 *   node scripts/cdp/download_question_videos.js all      # 下载全部 7 个
 *   node scripts/cdp/download_question_videos.js <vid8>   # 下载指定一个
 * 产物：data/_workspace/<profile>/tmp/download/sprint-videos/题目级讲解/qvideo_<paperId>_<entry>_<vid8>/.vfetch/{seg,merged.ts,manifest.json}
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const { findJwt, makeHeaders } = require('./gaodun_paper_core');
const { workspaceDir } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
// 题目讲解为税法专属（缺省 profile）：key 台账在 papers，下载缓存在 tmp/download
const KEYS_PATH = workspaceDir('papers', 'qvideo_keys.json');
const OUT_ROOT = workspaceDir('tmp', 'download', 'sprint-videos', '题目级讲解');
const GW = 'https://apigateway.gaodun.com';
const CONCURRENCY = 10;

function log(...a) { console.log(`[qv ${new Date().toLocaleTimeString()}]`, ...a); }

function getBuf(url, headers, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('too many redirects'));
    https.get(url, { headers: headers || { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume(); return resolve(getBuf(new URL(res.headers.location, url).href, headers, redirects + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode} ${url.slice(0, 90)}`)); }
      const ch = []; res.on('data', (c) => ch.push(c)); res.on('end', () => resolve(Buffer.concat(ch)));
    }).on('error', reject);
  });
}

async function fetchSdM3u8(vid, jwt) {
  const H = makeHeaders(jwt);
  const r = await (await fetch(`${GW}/glive2-vod/api/v1/live/resource?code=${vid}&res=SD&lang=zh`, { headers: H })).json();
  if (r.status !== 200 || !r.result?.list?.SD) throw new Error(`取流失败 ${r.status} ${r.message || ''}`);
  return { m3u8: r.result.list.SD.path, duration: r.result.duration, encrypt: r.result.encrypt };
}

// 解析 m3u8：全局 IV（EXT-X-KEY）+ 分片有序列表
function parseM3u8(text, m3u8Url) {
  const lines = text.split('\n').map((l) => l.trim());
  const keyLine = lines.find((l) => l.includes('EXT-X-KEY')) || '';
  const ivMatch = keyLine.match(/IV=0x([0-9a-fA-F]+)/);
  const iv = ivMatch ? Buffer.from(ivMatch[1], 'hex') : null;
  const base = m3u8Url.slice(0, m3u8Url.lastIndexOf('/') + 1);
  const segs = lines.filter((l) => l && !l.startsWith('#')).map((s) => (s.startsWith('http') ? s : base + s));
  return { iv, segs };
}

function decryptSeg(enc, keyBuf, iv, seq) {
  // IV 缺省时按 HLS 规范 = 分片 media sequence（16B 大端）
  const useIv = iv || (() => { const b = Buffer.alloc(16); b.writeBigUInt64BE(BigInt(seq), 8); return b; })();
  const d = crypto.createDecipheriv('aes-128-cbc', keyBuf, useIv);
  d.setAutoPadding(false);
  return Buffer.concat([d.update(enc), d.final()]);
}

async function downloadDecryptMerge(vid, keyAscii, m3u8Url, segDir, mergedPath) {
  const text = (await getBuf(m3u8Url, { 'User-Agent': 'Mozilla/5.0', Referer: 'https://glivepro.gaodun.com/' })).toString('utf8');
  const { iv, segs } = parseM3u8(text, m3u8Url);
  const keyBuf = Buffer.from(keyAscii.slice(0, 16), 'ascii'); // 16B ASCII hex 形态
  log(`分片 ${segs.length} 个 IV=${iv ? iv.toString('hex').slice(0, 12) + '…' : '序号派生'} 并发=${CONCURRENCY}`);
  const dec = new Array(segs.length);
  let done = 0, cursor = 0;
  async function worker() {
    while (cursor < segs.length) {
      const idx = cursor++;
      const cache = path.join(segDir, `${idx}.dec.ts`);
      if (fs.existsSync(cache) && fs.statSync(cache).size > 0) { dec[idx] = fs.readFileSync(cache); }
      else {
        let lastErr;
        for (let t = 0; t < 3; t++) {
          try {
            const enc = await getBuf(segs[idx], { 'User-Agent': 'Mozilla/5.0', Referer: 'https://glivepro.gaodun.com/' });
            dec[idx] = decryptSeg(enc, keyBuf, iv, idx);
            if (dec[idx][0] !== 0x47) throw new Error(`分片${idx}解密后非TS(0x${dec[idx][0].toString(16)})`);
            fs.writeFileSync(cache, dec[idx]); break;
          } catch (e) { lastErr = e; await new Promise((r) => setTimeout(r, 700 * (t + 1))); }
        }
        if (!dec[idx]) throw lastErr || new Error(`分片${idx}失败`);
      }
      done++;
      if (done % 60 === 0 || done === segs.length) log(`  解密进度 ${done}/${segs.length}`);
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));
  const out = fs.createWriteStream(mergedPath);
  for (let i = 0; i < dec.length; i++) out.write(dec[i]);
  await new Promise((r) => out.end(r));
  return segs.length;
}

async function runOne(vid, meta, jwt) {
  const name = `qvideo_${meta.paperId}_${meta.entry.replace('-', '_')}_${vid.slice(0, 8)}`;
  const dir = path.join(OUT_ROOT, name, '.vfetch');
  fs.mkdirSync(path.join(dir, 'seg'), { recursive: true });
  const merged = path.join(dir, 'merged.ts');
  if (fs.existsSync(merged) && fs.statSync(merged).size > 100000) { log(name, '已存在，跳过'); return; }
  const { m3u8, duration, encrypt } = await fetchSdM3u8(vid, jwt);
  if (encrypt !== 1) log(`注意 encrypt=${encrypt}`);
  log(`${name}（${duration}s）开始下载解密`);
  const t0 = Date.now();
  const segCount = await downloadDecryptMerge(vid, meta.key, m3u8, path.join(dir, 'seg'), merged);
  const bytes = fs.statSync(merged).size;
  fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify(
    { vid, name, paperId: meta.paperId, entry: meta.entry, key: meta.key, m3u8, duration, segCount, bytes, fetchedAt: new Date().toISOString() }, null, 2));
  log(`✅ ${name}：${segCount}片 ${(bytes / 1024 / 1024).toFixed(1)}MB 用时${((Date.now() - t0) / 1000).toFixed(0)}s`);
}

(async () => {
  const keys = JSON.parse(fs.readFileSync(KEYS_PATH));
  const vids = Object.keys(keys);
  const arg = process.argv[2] || 'all';
  const targets = arg === 'all' ? vids : vids.filter((v) => v.startsWith(arg));
  if (!targets.length) throw new Error(`无匹配 vid：${arg}`);
  const jwt = findJwt();
  for (const vid of targets) { try { await runOne(vid, keys[vid], jwt); } catch (e) { console.error(`✘ ${vid.slice(0, 8)} ${e.message}`); } }
  log('全部结束'); process.exit(0);
})().catch((e) => { console.error('[qv FAIL]', e.stack || e.message); process.exit(1); });
