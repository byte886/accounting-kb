/**
 * api_do_paper.js — 通用“纯接口做卷”闭环（单卷）
 *   从 syllabus 抓包解析 paperId/入口ID → 交给 gaodun_paper_core 完成
 *   record → redo 取题与标准答案 → 满足最小作答时长 → submit 一次性交【全部】答案
 *   → 交卷后逐题 AI 批改主观子题冲满分 → exam-report 回查。
 * 不做任何 UI 点选。仅用于可重做的知识点/课后/分章真题卷；冲刺模考不在本脚本范围。
 *
 * 用法：
 *   node scripts/cdp/api_do_paper.js <paperId 或 标题关键字> [最小停留秒]
 *   加 --no-ai：只交卷、不做交卷后 AI 批改（主观子题停在“待批改”，作业仍算已交）
 * 例：node scripts/cdp/api_do_paper.js 82749
 *     node scripts/cdp/api_do_paper.js 消费税纳税人
 *
 * 退出码：0=满分或平台最优（客观全对+可AI题全满，仅题库未配AI题不可判分）；4=已交卷但未达平台最优（可补批）；1/2=未交卷成功或异常
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { findJwt, doPaperViaApi } = require('./gaodun_paper_core');
const { accountAuthDir, workspaceDir } = require('./load_profile');
const AUTH_DIR = accountAuthDir();
const arg = process.argv[2] || '82656';
const dwellArg = process.argv[3] && /^\d+$/.test(process.argv[3]) ? Number(process.argv[3]) : undefined;
const DO_AI = !process.argv.includes('--no-ai');

function latestFile(prefix) {
  return path.join(AUTH_DIR, fs.readdirSync(AUTH_DIR)
    .filter((f) => f.startsWith(prefix) && f.endsWith('.jsonl')).sort().pop());
}
// 优先从 papers_inventory.json 解析 paperId -> { csItemId, resourceId, title, num }
// （会计课等新课程的 syllabus 抓包可能不存在，但 papers_inventory 已由 refresh_inventory.js 生成）
// 找不到时回退到 schedule_*.jsonl 抓包方式（税法课兼容）
function resolvePaper() {
  // 方式1：papers_inventory.json
  try {
    const invPath = path.join(workspaceDir('manifest'), 'papers_inventory.json');
    if (fs.existsSync(invPath)) {
      const inv = JSON.parse(fs.readFileSync(invPath, 'utf8'));
      const hit = inv.find((p) => {
        if (/^\d+$/.test(arg)) return String(p.paperId) === arg;
        return (p.title || '').includes(arg);
      });
      if (hit) {
        return {
          csItemId: hit.csItemId,
          chapter: hit.chapter,
          paperId: hit.paperId,
          resourceId: hit.resourceId,
          title: hit.title,
          num: hit.num,
        };
      }
    }
  } catch (e) {
    console.warn('[resolvePaper] papers_inventory 读取失败，回退 schedule 抓包:', e.message);
  }
  // 方式2：schedule_*.jsonl 抓包（税法课兼容）
  const f = latestFile('schedule_');
  const syllabus = JSON.parse(fs.readFileSync(f, 'utf8').split('\n').filter(Boolean)
    .map((l) => JSON.parse(l)).filter((o) => o.url && o.url.includes('syllabus')).pop().body).result;
  const found = [];
  const walk = (x, chapter) => {
    if (typeof x !== 'object' || x === null) return;
    let ch = chapter;
    if (x.itemId && x.name && x.discriminator !== 'paper') ch = { csItemId: x.itemId, chapter: x.name };
    if (x.discriminator === 'paper' && x.paperId) {
      const hit = /^\d+$/.test(arg) ? String(x.paperId) === arg : (x.title || '').includes(arg);
      if (hit) found.push({ ...ch, paperId: x.paperId, resourceId: x.resourceId, title: x.title, num: x.num });
    }
    Object.values(x).forEach((v) => { if (Array.isArray(v) || (typeof v === 'object' && v)) walk(v, ch); });
  };
  walk(syllabus, null);
  if (!found.length) throw new Error(`syllabus/papers_inventory 中找不到：${arg}`);
  return found[0];
}

(async () => {
  const target = resolvePaper();
  console.log('[目标卷]', JSON.stringify(target), DO_AI ? '' : '(--no-ai 不做AI批改)');
  const jwt = findJwt();
  const out = await doPaperViaApi({
    target, jwt, doAi: DO_AI, dwellSecOverride: dwellArg,
    log: (...a) => console.log(...a),
  });
  console.log('\n===== 完成 =====');
  console.log(JSON.stringify({
    paperId: out.paperId, logId: out.logId, submitted: out.submitted,
    score: `${out.userScore}/${out.totalScore}`, objectiveAllRight: out.objectiveAllRight,
    ai: `${out.aiFull}/${out.aiTotal}`, aiPartial: out.aiPartial, aiFailed: out.aiFailed,
    aiUnsupported: out.aiUnsupported, aiCeiling: out.aiCeiling,
    fullScore: out.fullScore, platformDone: out.platformDone, wrong: out.wrong, error: out.error,
  }, null, 1));
  if (out.fullScore || out.platformDone) process.exit(0); // 严格满分 或 平台最优（仅题库未配AI题不可判分）都视为达成
  if (out.submitted) process.exit(4);
  process.exit(out.error ? 1 : 2);
})().catch((e) => { console.error('[do-paper FAIL]', e.stack || e.message); process.exit(1); });
