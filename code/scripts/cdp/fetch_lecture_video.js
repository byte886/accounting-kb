#!/usr/bin/env node
/**
 * fetch_lecture_video.js — 单讲视频「取回放URL → CDP抓HLS key → 下m3u8取IV → 下载解密合并」主控。
 * 不做压缩（压缩慢、CPU bound，交由队列脚本在下载后串行执行 compress.sh）。
 *
 * 幂等：目标讲目录已存在 video.mp4 则跳过。
 * 时效：每讲实时从 syllabus 取最新回放 token，抓流→下载在同一轮连续完成（m3u8/authorize token 会过期）。
 *
 * 用法：node scripts/cdp/fetch_lecture_video.js <idx> [--profile <key>]
 *   idx = course_catalog / syllabus children 下标（idx1=开班前缀00，idxN→前缀 N-1）
 *   课程目录 / courseId / syllabusId 全部读 config/courses/<key>.json（缺省税法，或 GAODUN_COURSE_PROFILE）
 * 产物：<课程库>/<前缀_讲名>/.vfetch/manifest.json + merged.ts（压缩步骤读取 manifest）
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync, execFileSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..', '..');
const { findJwt, makeHeaders } = require(path.join(ROOT, 'scripts/cdp/gaodun_paper_core.js'));
const { loadProfile, primaryIds } = require(path.join(ROOT, 'scripts/cdp/load_profile.js'));
// 命名参数：--profile <key> / --profile=<key>
function namedArg(name) {
  const i = process.argv.indexOf(`--${name}`);
  if (i >= 0 && process.argv[i + 1]) return process.argv[i + 1];
  const eq = process.argv.find((a) => a.startsWith(`--${name}=`));
  return eq ? eq.slice(name.length + 3) : undefined;
}
// 课程目录/ID 全部来自 profile（data/高顿 为项目内实体目录，ADR-021 去软链；统一相对路径访问）
const profile = loadProfile(namedArg('profile'));
const _ids = primaryIds(profile);
const COURSE = path.join(ROOT, profile.paths.localRoot);
// 下载/压缩工作区基准：默认课程根（向后兼容，旧调用方不传即旧行为）；
// 动态流水线显式 --work-base 指向 data/_workspace/<profile>/dl-tmp，
// 让 .vfetch 分片/merged 等过程件落在工作区、不污染课程库（课程库只保留成品）。
const LEC_BASE = namedArg('work-base') || process.env.GAODUN_VFETCH_BASE || COURSE;
fs.mkdirSync(LEC_BASE, { recursive: true });
const COURSE_ID = _ids.courseId, SYLLABUS_ID = _ids.syllabusId;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function log(...a) { console.log(`[fetch ${new Date().toLocaleTimeString()}]`, ...a); }
function must(bin, args, opts = {}) {
  const r = spawnSync(bin, args, { encoding: 'utf8', maxBuffer: 1024 * 1024 * 64, ...opts });
  if (r.status !== 0) throw new Error(`${bin} ${args.slice(0, 3).join(' ')} 失败: ${(r.stderr || r.stdout || '').slice(0, 300)}`);
  return r.stdout;
}

async function getLive(idx) {
  const H = makeHeaders(findJwt());
  const j = await (await fetch(
    `https://apigateway.gaodun.com/g-study/api/v1/front/course/${COURSE_ID}/syllabus/glive/${SYLLABUS_ID}`, { headers: H })).json();
  const children = j && j.result && j.result.children;
  if (!Array.isArray(children)) {
    const e = new Error(`idx${idx} 大纲未返回 children（该讲平台未上线/未开放，属"待学习"），跳过`); e.code = 'NOT_ONLINE'; throw e;
  }
  const node = children[idx];
  if (!node) { const e = new Error(`children[${idx}] 不存在（该讲平台未上线），跳过`); e.code = 'NOT_ONLINE'; throw e; }
  let live = null;
  for (const key of ['preClassResource', 'inClassMainResource', 'inClassAssistResource', 'afterClassResource']) {
    for (const r of node[key] || []) if (r.discriminator === 'live_new') live = r;
  }
  if (!live || !live.liveUrlPlayBackPc) { const e = new Error(`idx${idx} 无 live_new 回放（该讲平台未上线），跳过`); e.code = 'NOT_ONLINE'; throw e; }
  return { name: node.name || live.title, url: live.liveUrlPlayBackPc, durationMinutes: live.durationMinutes };
}

(async () => {
  const idx = Number(process.argv.slice(2).find((a) => /^\d+$/.test(a)));
  if (!idx) { console.error('用法: node fetch_lecture_video.js <idx> [--profile <key>] [--work-base <工作区目录>]'); process.exit(2); }
  const prefix = String(idx - 1).padStart(2, '0');
  log(`[profile] ${profile.key}｜${profile.subject.name}｜course=${COURSE_ID} syllabus=${SYLLABUS_ID}`);
  const { name, url, durationMinutes } = await getLive(idx);
  // 定位/创建讲目录（前缀匹配，避免讲名特殊字符差异）
  let dir = fs.readdirSync(LEC_BASE).find((d) => d.startsWith(prefix + '_'));
  if (!dir) { dir = `${prefix}_${name.trim()}`; fs.mkdirSync(path.join(LEC_BASE, dir), { recursive: true }); }
  const lecDir = path.join(LEC_BASE, dir);
  if (fs.existsSync(path.join(lecDir, 'video.mp4'))) { log('已存在 video.mp4，跳过', dir); process.exit(0); }
  const work = path.join(lecDir, '.vfetch');
  fs.mkdirSync(work, { recursive: true });
  // 断点续跑：已下载解密出 merged 且 manifest 在，则跳过抓取/下载（压缩阶段另跑）
  const mfPath = path.join(work, 'manifest.json');
  if (fs.existsSync(mfPath)) {
    try {
      const mf = JSON.parse(fs.readFileSync(mfPath, 'utf8'));
      if (mf.merged && fs.existsSync(mf.merged)) { log('已下载 merged，跳过抓取下载', dir); process.exit(0); }
    } catch { /* manifest 损坏则重抓 */ }
  }
  log(`讲目录 ${dir}（约${durationMinutes}分钟）工作目录 ${work}`);

  // 1) CDP 抓 key（复用 capture_video_key.js，自动连日常 Chrome、抓完关临时标签）
  const streamsPath = path.join(work, 'streams.json');
  log('CDP 抓 HLS key ...');
  must('node', [path.join(ROOT, 'scripts/cdp/capture_video_key.js'), url, streamsPath], { stdio: 'inherit' });
  const streams = JSON.parse(fs.readFileSync(streamsPath, 'utf8'));
  const fhd = streams.find((s) => s.quality.includes('FHD')) || streams[0];
  if (!fhd || !fhd.keyAscii) throw new Error('未抓到 FHD key');
  log('选用', fhd.quality, 'key=', fhd.keyAscii);

  // 2) 下 m3u8 并解析 IV
  const m3u8Path = path.join(work, 'playlist.m3u8');
  must('curl', ['-s', '-o', m3u8Path, '-H', 'Referer: https://v-glive.gaodun.com/', fhd.m3u8]);
  const m3u8 = fs.readFileSync(m3u8Path, 'utf8');
  const keyLine = m3u8.split('\n').find((l) => l.includes('EXT-X-KEY'));
  const ivm = keyLine && keyLine.match(/IV=0x([0-9a-fA-F]+)/);
  if (!ivm) throw new Error('m3u8 未找到 IV');
  const iv = ivm[1];
  const segCount = m3u8.split('\n').filter((l) => l.startsWith('http') && l.includes('.ts')).length;
  log('IV=', iv, '分片数=', segCount);

  // 3) 下载 + 解密 + 合并（断点续传，20 并发）
  const merged = path.join(work, 'merged.ts');
  log('下载解密合并...');
  must('node', [path.join(ROOT, 'scripts/download_decrypt.js'), m3u8Path, merged,
    path.join(work, 'segments'), fhd.keyAscii, iv, '20'], { stdio: 'inherit' });
  if (!fs.existsSync(merged)) throw new Error('merged.ts 未生成');
  const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1', merged], { encoding: 'utf8' }).trim();
  fs.writeFileSync(path.join(work, 'manifest.json'), JSON.stringify({
    idx, prefix, lecture: dir, capturedAt: new Date().toISOString(),
    quality: fhd.quality, iv, segCount, merged, durationSec: Number(dur),
    targetVideo: path.join(lecDir, 'video.mp4'),
  }, null, 2));
  log(`✓ 下载解密完成 merged=${(fs.statSync(merged).size / 1024 / 1024).toFixed(1)}MB 时长=${Number(dur).toFixed(0)}s，待压缩 -> video.mp4`);
  process.exit(0);
})().catch((e) => {
  // 未上线/未开放讲（"待学习"放最后）：退出码 3，语义化跳过，不打误导性堆栈；真实下载失败才是 exit 1
  if (e && e.code === 'NOT_ONLINE') { console.error('[SKIP-NOT-ONLINE]', e.message); process.exit(3); }
  console.error('[FETCH-FAIL]', e.stack || e.message); process.exit(1);
});
