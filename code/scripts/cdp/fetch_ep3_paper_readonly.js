#!/usr/bin/env node
/**
 * fetch_ep3_paper_readonly.js — ep3 名师课试卷「只读」采集题面/标准答案/解析（绝不提交）
 *
 * 与做题的区别：gaodun_paper_core.doPaperViaApi 走 record→redo→等待→submit；
 * 本脚本只走 record→(必要时 create 开实例)→redo-paper，拿到题面与 questionAnswer(answer/analysis) 即落盘，
 * **不等待最小作答时长、不调 submit-paper、不产生作答行为**，因此不触发"做题行为异常"10462221。
 *
 * 用途：审计/财管等课程在风控期无法继续做题时，把"已做过"的卷子的题面/标准答案/解析回补落盘，
 *      作为知识详解的题目来源（用户决策 2026-09-10：排除风控拿不到的来源，现有来源一直推到知识库）。
 *
 * 已做卷集合 = papers_inventory.json 全集 − papers_audit.json 待做集（做题只从 audit 删、不回写 inventory.cls）。
 *
 * 用法：
 *   node scripts/cdp/fetch_ep3_paper_readonly.js --profile ep3-audit-2026 --probe
 *       探测模式：只取 1 张已做卷，打印 status/题量/是否含答案解析，用于判断只读接口是否被连带风控（不写盘也行）
 *   node scripts/cdp/fetch_ep3_paper_readonly.js --profile ep3-audit-2026 --paperId 82807
 *   node scripts/cdp/fetch_ep3_paper_readonly.js --profile ep3-audit-2026 --done-only [--limit N] [--gap 6,15]
 *       回补全部已做卷（拟人间隔，默认白天节奏），断点续跑：已落盘的 paperId 自动跳过
 *
 * 落盘：data/_workspace/<profile>/papers/<paperId>.json（redo.result 原样，含 moduleList 题面与 questionAnswer）
 * 退出码：全部 status=0 → 0；出现 10462221/10462222 等风控码 → 2（调用方据此挂起、等用户通知，不反复试探）
 */
'use strict';
const fs = require('fs');
const path = require('path');
const core = require('./gaodun_paper_core');
const { loadProfile, workspaceDirFor, argvProfileKey } = require('./load_profile');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const randInt = (a, b) => Math.floor(a + Math.random() * (b - a + 1));
function arg(name, def) {
  const i = process.argv.indexOf(`--${name}`);
  if (i < 0) return def;
  const v = process.argv[i + 1];
  return (!v || v.startsWith('--')) ? true : v;
}

const RISK_CODES = new Set([10462221, 10462222, 10462203]);

async function fetchOne(target, jwt, outDir, { logSave = true } = {}) {
  const H = core.makeHeaders(jwt); // 与 batch_ep3_papers 同源（默认 glivepro origin，ep3 做题同样走通）
  const call = async (method, urlPath, body) => {
    const res = await fetch(core.MINERVA_BASE + urlPath, {
      method, headers: H, body: body ? JSON.stringify(body) : undefined,
    });
    return res.json();
  };
  const business = {
    courseId: core.COURSE_ID, csItemId: target.csItemId, resourceId: target.resourceId,
    paperId: target.paperId, sourceFromType: core.SOURCE_FROM_TYPE,
  };
  const rec = await call('GET',
    `/student/paper/record?paperId=${target.paperId}&sourceFromType=${core.SOURCE_FROM_TYPE}&needAuth=1`);
  if (rec.status !== 0) return { ok: false, stage: 'record', status: rec.status, message: rec.message };
  let logId = rec.result && rec.result.paperDataLogId;
  if (!logId) {
    const cp = await call('POST', '/create-paper', {
      paperId: target.paperId, sourceFromType: core.SOURCE_FROM_TYPE, businessParam: business,
    }); // 仅开实例，非提交
    if (cp.status !== 0) return { ok: false, stage: 'create-paper', status: cp.status, message: cp.message };
    logId = cp.result.paperDataLogId;
  }
  const redo = await call('POST', '/redo-paper', {
    paperDataLogId: logId, sourceFromType: core.SOURCE_FROM_TYPE, needReviewInfo: 1,
    businessParam: business, openEnergyToEquity: 1,
  });
  if (redo.status !== 0) return { ok: false, stage: 'redo-paper', status: redo.status, message: redo.message };
  const r = redo.result;
  // 统计答案/解析覆盖度（不依赖具体嵌套，粗扫 questionAnswer）
  let q = 0, withAnswer = 0, withAnalysis = 0;
  const walk = (n) => {
    if (!n || typeof n !== 'object') return;
    if (n.questionAnswer) {
      q += 1;
      const qa = n.questionAnswer;
      if (qa.answer && String(qa.answer).replace(/<[^>]+>/g, '').trim()) withAnswer += 1;
      if (qa.analysis && String(qa.analysis).replace(/<[^>]+>/g, '').trim()) withAnalysis += 1;
    }
    for (const k of Object.keys(n)) if (Array.isArray(n[k])) n[k].forEach(walk);
      else if (n[k] && typeof n[k] === 'object') walk(n[k]);
  };
  walk(r);
  if (logSave) {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, `${target.paperId}.json`), JSON.stringify(
      { paperId: target.paperId, title: target.title, fetchedAt: new Date().toISOString(), result: r }, null, 2));
  }
  return { ok: true, logId, questionTotal: r.questionTotal, q, withAnswer, withAnalysis };
}

async function main() {
  const profile = loadProfile(argvProfileKey());
  const manifestDir = workspaceDirFor(profile.key, 'manifest');
  const outDir = path.join(workspaceDirFor(profile.key).replace(/\/$/, ''), 'papers');
  const inv = JSON.parse(fs.readFileSync(path.join(manifestDir, 'papers_inventory.json'), 'utf8'));
  const auditPath = path.join(manifestDir, 'papers_audit.json');
  const audit = fs.existsSync(auditPath) ? JSON.parse(fs.readFileSync(auditPath, 'utf8')) : [];
  const pendingIds = new Set(audit.map((p) => p.paperId));
  const jwt = core.findJwt();

  // 目标列表
  let targets;
  if (arg('paperId')) {
    const id = Number(arg('paperId'));
    targets = inv.filter((p) => p.paperId === id);
  } else {
    // 已做卷 = 全集 − 待做
    targets = inv.filter((p) => !pendingIds.has(p.paperId));
    if (arg('probe')) targets = targets.slice(0, 1);
  }
  if (arg('limit')) targets = targets.slice(0, Number(arg('limit')));
  const gap = String(arg('gap', '6,15')).split(',').map(Number);

  console.log(`=== 只读采集（不提交） profile=${profile.key} 目标=${targets.length} 张 ===`);
  let ok = 0, risk = 0, fail = 0, skip = 0;
  for (let i = 0; i < targets.length; i += 1) {
    const t = targets[i];
    const outFile = path.join(outDir, `${t.paperId}.json`);
    if (fs.existsSync(outFile) && !arg('probe')) { skip += 1; continue; }
    process.stdout.write(`[${i + 1}/${targets.length}] ${t.paperId} ${t.title} ... `);
    let res;
    try { res = await fetchOne(t, jwt, outDir, { logSave: !arg('probe') }); }
    catch (e) { res = { ok: false, stage: 'exception', message: e.message }; }
    if (res.ok) {
      ok += 1;
      console.log(`✓ 题量=${res.questionTotal} 答案块=${res.q}(答${res.withAnswer}/析${res.withAnalysis})${arg('probe') ? ' [probe不写盘]' : ''}`);
    } else if (RISK_CODES.has(Number(res.status))) {
      risk += 1;
      console.log(`⛔ 风控码 ${res.status} @${res.stage} ${res.message}`);
      console.log('只读接口也被风控连带 → 挂起，等用户通知风控解除，不反复试探。');
      process.exit(2);
    } else {
      fail += 1;
      console.log(`✗ ${res.stage} ${res.status || ''} ${res.message || ''}`);
    }
    if (i < targets.length - 1 && !arg('probe')) await sleep(randInt(gap[0], gap[1]) * 1000);
  }
  console.log(`\n=== 完成：成功${ok} 跳过(已采)${skip} 风控${risk} 失败${fail} ===`);
  process.exit(risk ? 2 : fail ? 1 : 0);
}
main().catch((e) => { console.error(e); process.exit(1); });
