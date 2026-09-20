#!/usr/bin/env node
/**
 * ep3_download_handouts.js — 按 ep3_course_outline 的 manifest 下载名师课讲义/课件。
 *
 * 下载源（已实测，2026-09-08 名师会计 17244）：
 *   主：https://simg01.gaodunwangxiao.com + handout.symlink（免认证 CDN，字节数==fileSize）
 *   备：g-study batch-download/handout 返回 enclosure-cdn-aliyun 签名 link（CDN 失败时兜底，需 JWT）
 *
 * 用法：
 *   node scripts/cdp/ep3_download_handouts.js <courseId> [--format pdf|all] [--limit N] [--dry]
 *   默认只下 pdf（OCR 来源）；--format all 连 zip 课件一起。
 * 落盘（试点阶段先落工作区，正式课程库落位待 L1 方案确认）：
 *   data/_workspace/_account/ep3/downloads/<cid>/<梯度>/<分类>/<文件名>，幂等（大小一致即跳过）。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');
const { findJwt, platformHeaders } = require('./gaodun_paper_core');
const { argvProfileKey, loadProfile } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
const GW = 'https://apigateway.gaodun.com';
const CDN = 'https://simg01.gaodunwangxiao.com';
const safe = (s) => String(s || '未命名').replace(/[\/\\:]/g, '-').trim();

// B 方案落位规则（用户 2026-09-09）：目录不按老师分层（沿用内容结构，两位老师同目录），
// 老师只进文件名前缀；最终知识详解两源 Fan-In 成一套。
const TEACHERS = ['陈蓓蓓', '姚远', '罗翔', '郁刚', '王潇粒', '王依然', '李晶'];
const teacherOf = (h) => {
  const s = `${h.category || ''} ${h.name || ''}`;
  return TEACHERS.find((t) => s.includes(t)) || '其他';
};
// 剥离目录名/文件名里的老师字样，并清理残留的空括号与悬挂分隔
const noTeacher = (s0) => {
  let x = String(s0 || '');
  for (const t of TEACHERS) x = x.split(t).join('');
  return x
    .replace(/老师/g, '')
    .replace(/[-_、,，]\s*(?=[】（）)])/g, '')
    .replace(/（\s*）/g, '').replace(/\(\s*\)/g, '')
    .replace(/\s+/g, ' ').trim();
};
// 统一落盘相对路径：<梯度>/<内容分类(去老师)>/<老师>_<文件名(去老师)>
const relDest = (h) => {
  const teacher = teacherOf(h);
  return path.join(safe(h.gradationName), safe(noTeacher(h.category)), safe(`${teacher}_${noTeacher(h.name)}`));
};

function download(url, dest, headers) {
  return new Promise((resolve, reject) => {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const tmp = dest + '.part';
    const req = https.get(url, { headers: headers || {}, timeout: 60000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume(); return download(res.headers.location, dest, headers).then(resolve, reject);
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error('HTTP ' + res.statusCode)); }
      const ws = fs.createWriteStream(tmp);
      let bytes = 0;
      res.on('data', (c) => { bytes += c.length; });
      res.pipe(ws);
      ws.on('finish', () => ws.close(() => { fs.renameSync(tmp, dest); resolve(bytes); }));
      ws.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (e) => { try { fs.unlinkSync(tmp); } catch { /* ignore */ } reject(e); });
  });
}

(async () => {
  // cid 来源：位置参数（探路，落工作区）优先；否则 --profile 从档案卡读（落正式课程库 原始资源/notes）
  const profileKey = argvProfileKey(process.argv);
  const profile = profileKey ? loadProfile(profileKey) : null;
  // 先剔除 --profile <key> / --profile=<key>，避免把 profile 名误当成 courseId 位置参数
  const rest = [];
  const pv = process.argv.slice(2);
  for (let i = 0; i < pv.length; i += 1) {
    if (pv[i] === '--profile') { i += 1; continue; }
    if (pv[i].startsWith('--profile=')) continue;
    rest.push(pv[i]);
  }
  const positional = rest.find((a) => !a.startsWith('--'));
  const cid = positional || (profile ? profile.primaryCourse.saasCourseId : null);
  if (!cid) { console.error('用法: ep3_download_handouts.js <courseId|--profile key> [--format pdf|all] [--limit N] [--dry]'); process.exit(1); }
  const fmt = (process.argv.find((a) => a.startsWith('--format=')) || '').split('=')[1]
    || (process.argv.includes('--all') ? 'all' : 'pdf');
  const limitArg = process.argv.find((a) => a.startsWith('--limit='));
  const limit = limitArg ? Number(limitArg.split('=')[1]) : Infinity;
  const dry = process.argv.includes('--dry');

  const manifestPath = path.join(ROOT, 'data/_workspace/_account/ep3/manifest', `${cid}.outline.json`);
  const m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  let items = m.handouts.filter((h) => fmt === 'all' || h.format === 'pdf');
  const base = profile
    ? path.join(ROOT, profile.paths.localRoot, '原始资源', 'notes')
    : path.join(ROOT, 'data/_workspace/_account/ep3/downloads', String(cid));
  console.log(`${m.courseName}：待处理 ${items.length} 个（format=${fmt}${Number.isFinite(limit) ? ' limit=' + limit : ''}）`);
  console.log('落位:', path.relative(ROOT, base));

  const H = platformHeaders(findJwt(), 'ep3');
  let ok = 0, skip = 0, fail = 0, n = 0;
  for (const h of items) {
    n += 1; if (n > limit) break;
    const dest = path.join(base, relDest(h));
    if (fs.existsSync(dest) && fs.statSync(dest).size === h.fileSize) { skip += 1; continue; }
    if (dry) { console.log(`[dry] ${h.format} ${(h.fileSize / 1e6).toFixed(1)}MB -> ${path.relative(ROOT, dest)}`); continue; }
    try {
      let bytes;
      try { bytes = await download(CDN + h.symlink, dest); }
      catch (e1) { // 兜底：g-study 换签名链接
        const j = await (await fetch(`${GW}/g-study/api/v1/front/batch-download/handout?handoutIds=${h.id}&resourceIds=&courseId=${cid}`, { headers: H })).json();
        const link = j.result && j.result.path && j.result.path[0] && j.result.path[0].link;
        if (!link) throw e1;
        bytes = await download(link, dest);
      }
      const good = !h.fileSize || bytes === h.fileSize;
      console.log(`${good ? '✅' : '⚠️字节不符'} ${h.name} ${bytes}${h.fileSize ? '/' + h.fileSize : ''}`);
      ok += 1;
    } catch (e) { console.error(`❌ ${h.name}: ${e.message}`); fail += 1; }
  }
  console.log(`完成：新下${ok} 跳过${skip} 失败${fail}，落于 ${path.relative(ROOT, base)}`);
  process.exit(fail ? 2 : 0);
})().catch((e) => { console.error('[HANDOUT-FAIL]', e.stack || e.message); process.exit(1); });
