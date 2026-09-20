#!/usr/bin/env node
/**
 * collect_paper_sources.js — 线B原料只读补采：把已交卷的 116 张基础卷
 * 题面 / 选项 / 标准答案 / 官方解析 / 知识点标签 / 全站正确率，经只读接口
 * record -> paper/analysis 逐张拉出并精简落盘，供末期知识库生成使用。
 *
 * 纯只读：不 redo、不建实例、不交卷、不耗 AI 权益、无副作用。
 * 输出（按 profile 子目录隔离）：
 *   data/_workspace/<profile>/papers/<paperId>.json   每卷精简题/答/解析（paperId 全局唯一）
 *   data/_workspace/<profile>/manifest/paper_index.json  paperId -> 章/标题/题数/文件
 * 用法：node scripts/cdp/collect_paper_sources.js [--profile <key>] [--all] [paperId...]
 *   默认只补本地缺失的卷；--all 强制重拉；可跟指定 paperId；课程由 --profile/GAODUN_COURSE_PROFILE 决定。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { findJwt, makeHeaders, MINERVA_BASE, stripHtml } = require('./gaodun_paper_core');
const { loadProfile, workspaceDirFor, argvProfileKey } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
const SFT = 100533962;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 只保留知识库需要的字段，剥掉运行时/判分冗余
function pickQuestion(q) {
  const qa = q.questionAnswer || {};
  const base = {
    questionId: q.questionId,
    questionType: q.questionType,
    title: q.title,
    selectList: Array.isArray(q.selectList) ? q.selectList.map((s) => ({
      optionLabel: s.optionLabel || s.label, optionContent: s.optionContent || s.content, isAnswer: s.isAnswer,
    })) : undefined,
    score: q.score,
    correctRate: q.correctRate,
    knowledgePointList: q.knowledgePointList,
    answer: qa.answer,
    analysis: qa.analysis,
    analysisText: qa.analysis ? stripHtml(qa.analysis) : undefined,
    improve: qa.improve,
    translate: qa.translate,
  };
  if (Array.isArray(q.subQuestionList) && q.subQuestionList.length) {
    base.subQuestionList = q.subQuestionList.map(pickQuestion);
  }
  return base;
}

(async () => {
  const profile = loadProfile(argvProfileKey());
  const manifestDir = workspaceDirFor(profile.key, 'manifest');
  const papersDir = workspaceDirFor(profile.key, 'papers');
  fs.mkdirSync(papersDir, { recursive: true });
  const H = makeHeaders(findJwt());
  const invPath = path.join(manifestDir, 'papers_inventory.json');
  const inv = JSON.parse(fs.readFileSync(invPath, 'utf8'));
  console.log(`[profile] ${profile.key}｜inventory=${path.basename(invPath)}｜卷数=${inv.length}`);
  const forceAll = process.argv.includes('--all');
  const only = process.argv.slice(2).filter((a) => /^\d+$/.test(a)).map(Number);
  let list = inv;
  if (only.length) list = inv.filter((p) => only.includes(p.paperId));

  const index = [];
  const failed = [];
  let ok = 0, skip = 0;
  for (let i = 0; i < list.length; i += 1) {
    const p = list[i];
    const dest = path.join(papersDir, `${p.paperId}.json`);
    if (!forceAll && fs.existsSync(dest)) { skip += 1; continue; }
    let logId = null;
    try {
      const rj = await (await fetch(
        `${MINERVA_BASE}/student/paper/record?paperId=${p.paperId}&sourceFromType=${SFT}&needAuth=1`, { headers: H })).json();
      logId = rj.result && rj.result.paperDataLogId;
      if (!logId) throw new Error('record 无 logId（可能未交卷）');
      let z = await (await fetch(`${MINERVA_BASE}/paper/analysis`, {
        method: 'POST', headers: H, body: JSON.stringify({ paperDataLogId: logId, openEnergyToEquity: 1 }),
      })).json();
      if (z.status !== 0) { await sleep(1500); z = await (await fetch(`${MINERVA_BASE}/paper/analysis`, {
        method: 'POST', headers: H, body: JSON.stringify({ paperDataLogId: logId, openEnergyToEquity: 1 }),
      })).json(); }
      if (z.status !== 0) throw new Error(`analysis ${z.status} ${z.message}`);
      const r = z.result;
      const modules = (r.moduleList || []).map((m) => ({
        moduleName: m.moduleName || m.name,
        questionList: (m.questionList || []).map(pickQuestion),
      }));
      const qCount = modules.reduce((a, m) => a + m.questionList.length, 0);
      const doc = {
        paperId: p.paperId, title: r.title || p.title, chapter: p.chapter, cls: p.cls,
        paperDataLogId: logId, capturedAt: new Date().toISOString(),
        moduleList: modules,
      };
      fs.writeFileSync(dest, JSON.stringify(doc, null, 1));
      index.push({ paperId: p.paperId, title: doc.title, chapter: p.chapter, cls: p.cls, qCount, file: `papers/${p.paperId}.json` });
      ok += 1;
      if ((i + 1) % 10 === 0) console.log(`  ...${i + 1}/${list.length}（成功${ok}）`);
    } catch (e) {
      failed.push({ paperId: p.paperId, title: p.title, err: e.message });
      console.log(`  ✗ ${p.paperId} ${e.message}`);
    }
    await sleep(300);
  }

  // 合并已有 index（增量补采时保留旧条目）
  const idxPath = path.join(manifestDir, 'paper_index.json');
  let old = [];
  if (!only.length && fs.existsSync(idxPath)) old = JSON.parse(fs.readFileSync(idxPath, 'utf8'));
  const merged = only.length || forceAll ? (only.length ? [...old.filter((x) => !only.includes(x.paperId)), ...index] : index)
    : [...old.filter((x) => !index.some((n) => n.paperId === x.paperId)), ...index];
  merged.sort((a, b) => String(a.chapter || '').localeCompare(String(b.chapter || ''), 'zh') || a.paperId - b.paperId);
  fs.writeFileSync(idxPath, JSON.stringify(merged, null, 1));
  console.log(`\n===== 线B原料补采完成 =====`);
  console.log(`新采 ${ok}，已存在跳过 ${skip}，失败 ${failed.length}，索引累计 ${merged.length} 卷 -> data/_workspace/${profile.key}/papers/`);
  if (failed.length) console.log('失败清单:', JSON.stringify(failed));
  process.exit(failed.length && ok === 0 ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
