#!/usr/bin/env node
/**
 * download_lecture_notes.js — 批量下载一门课全部讲义（lecture_note）。
 *
 * 讲义资源在 glive 大纲每个 child 的四个资源数组里，discriminator==='lecture_note'，
 * 其 `path` 是免认证 CDN 直链（无需 Playwright 监听、无需 HLS key），直接 curl 即可。
 *
 * 落盘范式（对齐税法/会计01章）：
 *   <localRoot>/原始资源/notes/<NN_讲名>/<title>.<extension>
 *   NN = idx-1（idx 从 1 起；idx0 是冲刺模考、无讲义）。一个讲目录可放多份（如开班3份）。
 *
 * 幂等：目标 PDF 已存在且非空则跳过（可反复跑、断点续下）。
 * 用法：
 *   node scripts/cdp/download_lecture_notes.js --profile cpa-accounting-2026            # 真下
 *   node scripts/cdp/download_lecture_notes.js --profile cpa-accounting-2026 --dry-list # 只列清单/目标路径，不下载
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..', '..');
const { findJwt, makeHeaders } = require(path.join(ROOT, 'scripts/cdp/gaodun_paper_core.js'));
const { loadProfile, primaryIds } = require(path.join(ROOT, 'scripts/cdp/load_profile.js'));

function namedArg(name) {
  const i = process.argv.indexOf(`--${name}`);
  if (i >= 0 && process.argv[i + 1]) return process.argv[i + 1];
  const eq = process.argv.find((a) => a.startsWith(`--${name}=`));
  return eq ? eq.slice(name.length + 3) : undefined;
}
// 文件名/目录名只替换文件系统非法字符；中文、&、（）等保留（与视频讲目录命名一致）
function safeName(s) { return String(s).replace(/[\\/:*?"<>|]/g, '_').trim(); }
function log(...a) { console.log(`[notes ${new Date().toLocaleTimeString()}]`, ...a); }

const profile = loadProfile(namedArg('profile'));
const ids = primaryIds(profile);
const COURSE = path.join(ROOT, profile.paths.localRoot);
const NOTES = path.join(COURSE, '原始资源', 'notes');
const DRY = process.argv.includes('--dry-list');
const RES_KEYS = ['preClassResource', 'inClassMainResource', 'inClassAssistResource', 'afterClassResource'];

(async () => {
  const H = makeHeaders(findJwt());
  const j = await (await fetch(
    `https://apigateway.gaodun.com/g-study/api/v1/front/course/${ids.courseId}/syllabus/glive/${ids.syllabusId}`,
    { headers: H })).json();
  const children = j && j.result && j.result.children;
  if (!Array.isArray(children)) throw new Error('glive 未返回 children');
  fs.mkdirSync(NOTES, { recursive: true });

  const stat = { total: 0, exists: 0, downloaded: 0, fail: 0 };
  const fails = [];
  for (let idx = 1; idx < children.length; idx++) {
    const node = children[idx];
    const prefix = String(idx - 1).padStart(2, '0');
    const notes = [];
    for (const key of RES_KEYS) for (const r of node[key] || []) {
      if (r.discriminator === 'lecture_note' && r.path) notes.push(r);
    }
    if (!notes.length) continue;
    // 复用 notes 下已有 prefix_* 目录，否则按 node.name 建（与视频讲前缀一致，便于对应）
    let dirName = fs.readdirSync(NOTES).find((d) => d.startsWith(prefix + '_'));
    if (!dirName) dirName = `${prefix}_${safeName(node.name || '未命名')}`;
    const dir = path.join(NOTES, dirName);
    fs.mkdirSync(dir, { recursive: true });

    for (const r of notes) {
      stat.total++;
      const fname = `${safeName(r.title || `讲义${r.id}`)}.${r.extension || 'pdf'}`;
      const out = path.join(dir, fname);
      if (fs.existsSync(out) && fs.statSync(out).size > 0) { stat.exists++; if (DRY) log('已存在', dirName, fname); continue; }
      if (DRY) { log('[dry]', dirName, '/', fname, r.fileSize || ''); continue; }
      const res = spawnSync('curl', ['-sL', '--fail', '--retry', '2',
        '-H', 'Referer: https://glivepro.gaodun.com/', '-o', out, r.path], { encoding: 'utf8' });
      if (res.status === 0 && fs.existsSync(out) && fs.statSync(out).size > 0) {
        stat.downloaded++; log('✓', dirName, fname, `${(fs.statSync(out).size / 1024 / 1024).toFixed(1)}MB`);
      } else {
        stat.fail++; fails.push(`${prefix}/${fname}`);
        try { fs.unlinkSync(out); } catch { /* ignore */ }
        console.error('  ✗ 下载失败', fname, (res.stderr || '').slice(0, 150));
      }
    }
  }
  log('汇总', JSON.stringify(stat), fails.length ? `失败: ${fails.join('; ')}` : '全部成功');
  process.exit(stat.fail ? 1 : 0);
})().catch((e) => { console.error('[NOTES-FAIL]', e.stack || e.message); process.exit(1); });
