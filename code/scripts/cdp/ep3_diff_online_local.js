#!/usr/bin/env node
/**
 * ep3_diff_online_local.js — 名师课「在线真视频 vs 本地实物」只读核对器
 *
 * 通道：node 直连 apigateway 被 Tengine 按客户端指纹拦 405，统一走项目标准浏览器桥
 *   connect_browser（ADR-010，puppeteer-core 连日常 Chrome），在已登录高顿页面 page.evaluate
 *   内 fetch（真实浏览器指纹 + credentials:'include'）。纯只读：只 GET syllabus、不下载、
 *   不取 key、不写课程库、不碰做题风控。
 *
 * 关键口径（2026-09-13 定版，与真实课程页一致）：
 *   - syllabus 大纲树的每个叶子节点**已内嵌 resource 对象**（含 discriminator/video_id/teacher_id），
 *     无需再逐个调 front/resource（逐个调上千次会触发业务码 10161000；页面本身也只拉 syllabus）。
 *     真视频 = node.resource.discriminator==='video' && node.resource.video_id。
 *   - 双老师必须逐 teacher_id 各拉一套树（不传只得主老师折叠树、漏第二老师整套），再按
 *     chapterPath 归并成统一讲目录，目录内 `<老师名>_video.mp4` 前缀区分。
 *   - 平台树会调整致 seq 漂移，本地以「讲名 safeName」为主键对齐，seq 仅参考。
 *   - 完整判据：归并讲所需每位老师都有非空(>100KB)对应前缀 video（单老师无前缀时回退任意 video.mp4）。
 *
 * 用法：node scripts/cdp/ep3_diff_online_local.js <profileKey>... [--out <json>]
 */
const fs = require('fs');
const path = require('path');
const core = require('./gaodun_paper_core');
const { loadProfile } = require('./load_profile');
const { connectDailyChrome, findPage, newBackgroundPage, safeDisconnect } = require('./connect_browser');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function log(...x) { console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...x); }
function safeName(s) { return String(s).replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, '').slice(0, 60); }

const TEACHER_NAME = {
  22455: '姚远', 14178: '陈蓓蓓', 11138: '罗翔', 15038: '郁刚', 57023: '王潇粒',
  24825: '杨志国', 50070: '高蒙', 15317: '吴奕', 24042: '沈甜甜', 15466: '齐萌',
  15251: '王依然', 15463: '陈岩', 11134: '李晶',
};
const NAME_BY_TEACHER = Object.fromEntries(Object.entries(TEACHER_NAME).map(([id, n]) => [n, Number(id)]));

// 浏览器页面内：逐 teacher_id 拉 syllabus，直接用「内嵌 resource」判别真视频（不调 front/resource）
async function pageEnumStage(arg) {
  const H = { authentication: arg.auth, accept: 'application/json', 'content-type': 'application/json' };
  const jget = async (p) => {
    const r = await fetch('https://apigateway.gaodun.com' + p, { headers: H, credentials: 'include' });
    if (!r.ok) throw new Error('HTTP' + r.status);
    return r.json();
  };
  const collect = (node, ctx, acc) => {
    const my = { ...ctx };
    const isCh = Array.isArray(node.cs_item_ids) || (node.video_total !== undefined && !ctx.ch);
    if (isCh && !ctx.ch) my.ch = node.id;
    my.path = ctx.path ? ctx.path + '/' + node.name : node.name;
    if (node.resource_id != null && (!Array.isArray(node.children) || node.children.length === 0)) {
      const res = node.resource || null;
      acc.push({
        csItemId: node.id, resourceId: node.resource_id, name: node.name, chapterPath: my.path,
        hasEmbedded: !!res,
        disc: res && res.discriminator, videoId: res && res.video_id,
        teacherId: (res && res.teacher_id) || null, paperId: res && res.paper_id,
      });
    }
    if (Array.isArray(node.children)) node.children.forEach((c) => collect(c, my, acc));
    if (Array.isArray(node.syllabus)) node.syllabus.forEach((c) => collect(c, my, acc));
  };
  const enumOne = async (tid) => {
    const tq = tid ? `&teacher_id=${tid}` : '';
    const sr = await jget(`/ep-study/front/course/${arg.cid}/syllabus?gradation_id=${arg.grad}&syllabus_id=${arg.syl}${tq}`);
    if (sr.status !== 0) throw new Error('syllabus status=' + sr.status);
    let gn = null;
    for (const s of (sr.result.syllabus || [])) {
      if (String(s.id) === String(arg.grad)) { gn = s; break; }
      if (Array.isArray(s.children)) for (const c of s.children) if (String(c.id) === String(arg.grad)) { gn = c; break; }
      if (gn) break;
    }
    if (!gn) return { teacherId: tid, totalLeaves: 0, videos: [], embeddedMissing: 0 };
    const acc = [];
    const roots = Array.isArray(gn.syllabus) ? gn.syllabus : Array.isArray(gn.children) ? gn.children : [];
    roots.forEach((n) => collect(n, { ch: null, path: '' }, acc));
    acc.forEach((l, i) => { l.seq = i + 1; });
    const videos = acc.filter((l) => l.disc === 'video' && l.videoId)
      .map((l) => ({ seq: l.seq, name: l.name, chapterPath: l.chapterPath, videoId: l.videoId, teacherId: l.teacherId || tid }));
    return { teacherId: tid, totalLeaves: acc.length, videos, embeddedMissing: acc.filter((l) => !l.hasEmbedded).length };
  };
  const ids = arg.teacherIds && arg.teacherIds.length ? arg.teacherIds : [null];
  const perTeacher = [];
  for (const tid of ids) { perTeacher.push(await enumOne(tid)); await new Promise((r) => setTimeout(r, 300)); }
  return { perTeacher };
}

async function diffStage(page, auth, profile, stg) {
  const cid = profile.primaryCourse.saasCourseId;
  const teacherIds = (profile.teachers || []).map((nm) => NAME_BY_TEACHER[nm]).filter(Boolean);
  const r = await page.evaluate(pageEnumStage, { cid, grad: stg.gradationId, syl: stg.syllabusId, auth, teacherIds });

  const pathOrder = new Map(), grouped = new Map();
  let leafMax = 0, embeddedMissing = 0, teacherVideoHits = 0;
  for (const pt of r.perTeacher) {
    leafMax = Math.max(leafMax, pt.totalLeaves); embeddedMissing += pt.embeddedMissing || 0; teacherVideoHits += pt.videos.length;
    for (const v of pt.videos) {
      const p = v.chapterPath;
      if (!pathOrder.has(p)) pathOrder.set(p, v.seq);
      if (!grouped.has(p)) grouped.set(p, { name: v.name, teachers: new Set() });
      grouped.get(p).teachers.add(Number(v.teacherId));
    }
  }
  const paths = [...pathOrder.keys()].sort((a, b) => pathOrder.get(a) - pathOrder.get(b));

  const stageDir = path.join(REPO_ROOT, profile.paths.localRoot, '原始资源', 'videos', stg.label);
  const localDirs = fs.existsSync(stageDir)
    ? fs.readdirSync(stageDir).filter((n) => !n.startsWith('.') && fs.statSync(path.join(stageDir, n)).isDirectory()) : [];
  const byExact = new Set(localDirs);
  const byName = new Map();
  for (const d of localDirs) { const k = d.replace(/^\d+_/, ''); if (!byName.has(k)) byName.set(k, d); }

  const teacherVideoPresent = (dir, id, dual) => {
    const dp = path.join(stageDir, dir);
    if (!fs.existsSync(dp)) return false;
    const files = fs.readdirSync(dp);
    const nm = TEACHER_NAME[id];
    if (dual) {
      const f = files.find((x) => x === `${nm}_video.mp4`);
      return !!f && fs.statSync(path.join(dp, f)).size > 102400;
    }
    const own = nm && files.find((x) => x === `${nm}_video.mp4`);
    if (own) return fs.statSync(path.join(dp, own)).size > 102400;
    const any = files.find((x) => /(^|_)video\.mp4$/.test(x));
    return !!any && fs.statSync(path.join(dp, any)).size > 102400;
  };

  const okExact = [], okDrift = [], incomplete = [], missing = [];
  paths.forEach((p, idx) => {
    const g = grouped.get(p);
    const dirSeq = idx + 1;
    const nameKey = safeName(g.name);
    const exact = `${String(dirSeq).padStart(2, '0')}_${nameKey}`;
    const needIds = [...g.teachers];
    const dual = needIds.length > 1;
    const hitDir = byExact.has(exact) ? exact : byName.get(nameKey);
    const rec = { dirSeq, name: g.name, expectDir: exact, needTeachers: needIds.map((i) => TEACHER_NAME[i] || i), chapterPath: p };
    if (!hitDir) { missing.push({ ...rec, reason: '本地无此讲(全新缺)' }); return; }
    const missT = needIds.filter((id) => !teacherVideoPresent(hitDir, id, dual)).map((id) => TEACHER_NAME[id] || id);
    if (missT.length) incomplete.push({ ...rec, localDir: hitDir, missingTeachers: missT, reason: '缺老师视频(残缺补片)' });
    else if (hitDir === exact) okExact.push(rec); else okDrift.push({ ...rec, localDir: hitDir });
  });

  const onlineNames = new Set(paths.map((p) => safeName(grouped.get(p).name)));
  const extraLocal = localDirs.filter((d) => !onlineNames.has(d.replace(/^\d+_/, '')));
  return {
    profile: profile.key, course: cid, stage: stg.label,
    totalLeaves: leafMax, teacherVideoHits, videoOnline: paths.length, teacherIds,
    okExact: okExact.length, okDrift: okDrift.length, incomplete: incomplete.length, missing: missing.length,
    localOk: okExact.length + okDrift.length, need: incomplete.length + missing.length,
    extraLocalDirs: extraLocal.length, embeddedMissing,
    missingList: missing, incompleteList: incomplete, extraLocalList: extraLocal,
  };
}

(async () => {
  const argv = process.argv.slice(2);
  const keys = [];
  let outPath = '';
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--out') outPath = argv[++i];
    else if (!argv[i].startsWith('--')) keys.push(argv[i]);
  }
  if (!keys.length) { console.error('用法: node ep3_diff_online_local.js <profileKey>... [--out json]'); process.exit(2); }

  const auth = core.platformHeaders(core.findJwt(), 'ep3').authentication;
  log('连接日常 Chrome（浏览器桥，仅读 syllabus 树）…');
  const browser = await connectDailyChrome({ timeoutMs: 120000 });
  let page = await findPage(browser, 'epiphany.gaodun.com');
  if (!page) page = await findPage(browser, 'gaodun.com');
  if (!page) {
    page = await newBackgroundPage(browser);
    await page.goto('https://epiphany.gaodun.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(4000);
  }
  log('使用高顿页:', await page.url());

  const report = { generatedAt: new Date().toISOString(), via: 'browser-bridge+syllabus-embedded-resource', courses: {} };
  try {
    for (const key of keys) {
      const profile = loadProfile(key); profile.key = key;
      report.courses[key] = [];
      log(`=== ${key} 老师=${(profile.teachers || []).join('/')}（${(profile.stages || []).length} 阶段）===`);
      for (const stg of profile.stages || []) {
        try {
          const s = await diffStage(page, auth, profile, stg);
          report.courses[key].push(s);
          log(`■ ${stg.label}: 叶${s.totalLeaves} 归并讲${s.videoOnline}(老师视频条${s.teacherVideoHits}) | 齐(同序)${s.okExact} 齐(漂移)${s.okDrift} 残缺${s.incomplete} 全新缺${s.missing} | 待补${s.need} 多余${s.extraLocalDirs} 缺内嵌${s.embeddedMissing}`);
        } catch (e) {
          report.courses[key].push({ stage: stg.label, error: e.message });
          log(`■ ${stg.label}: 核对失败 ${e.message}`);
        }
        await sleep(500);
      }
    }
  } finally {
    await safeDisconnect(browser);
  }
  const sum = { videoOnline: 0, teacherVideoHits: 0, okExact: 0, okDrift: 0, localOk: 0, incomplete: 0, missing: 0, need: 0, extraLocalDirs: 0, embeddedMissing: 0 };
  for (const k of Object.keys(report.courses)) for (const s of report.courses[k]) {
    if (s.error) continue;
    sum.videoOnline += s.videoOnline; sum.teacherVideoHits += s.teacherVideoHits;
    sum.okExact += s.okExact; sum.okDrift += s.okDrift; sum.localOk += s.localOk;
    sum.incomplete += s.incomplete; sum.missing += s.missing; sum.need += s.need;
    sum.extraLocalDirs += s.extraLocalDirs; sum.embeddedMissing += s.embeddedMissing;
  }
  report.summary = sum;
  if (outPath) {
    const abs = path.isAbsolute(outPath) ? outPath : path.join(REPO_ROOT, outPath);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, JSON.stringify(report, null, 2));
    log('明细 ->', path.relative(REPO_ROOT, abs));
  }
  log(`===== 合计：归并讲 ${sum.videoOnline}（老师视频条 ${sum.teacherVideoHits}），本地齐 ${sum.localOk}(同序${sum.okExact}/漂移${sum.okDrift})，待补 ${sum.need}(残缺${sum.incomplete}+全新${sum.missing})，多余 ${sum.extraLocalDirs}，缺内嵌 ${sum.embeddedMissing} =====`);
  process.exit(sum.embeddedMissing > 0 ? 1 : 0);
})().catch((e) => { console.error('[FATAL]', e.stack || e.message); process.exit(1); });
