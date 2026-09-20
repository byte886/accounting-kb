/**
 * refresh_inventory.js — 刷新作业基线（只读，不交卷）
 *
 * 做三件事：
 *   1) 纯 HTTP 拉课程大纲 syllabus（g-study，整树无分页），递归枚举全部 paper 及章节祖先(csItemId)；
 *   2) 对每张【基础卷】（硬排除标题含“冲刺模考”/num===48）只读调 student/paper/record，按最新实例分类：
 *        满分     = paperSubmitStatus===1 且 score>=questionTotal
 *        平台最优 = paperSubmitStatus===1 但分低，进一步用 paper/analysis 复核：配了AI的主观题全满分、
 *                   客观题全对，失分全部来自“题库未配AI判分(cpaBotType!==3)”的子题（平台不判分，非我方问题）→ 视同完成
 *        非满分   = 已交卷但存在“本可判分却没拿满”的题（真·待补）
 *        未提交   = paperSubmitStatus===0（做过没交，progress=2）
 *        未做     = record.result===null（progress=null，首次需 create-paper）
 *   3) 章节自然顺序（全面精讲→强化冲刺，段内按序号）写出：
 *        data/_workspace/<profile>/manifest/papers_inventory.json  全量基础卷（含入口ID/进度/最新分）
 *        data/_workspace/<profile>/manifest/papers_audit.json       待做卷（cls 非“满分/平台最优”），供 batch_redo_papers.js 消费
 *
 * 用法：node scripts/cdp/refresh_inventory.js [--profile <key>]
 *   课程 ID/syllabus 从 config/courses/<key>.json 读取（缺省 cpa-tax-2026，或环境变量 GAODUN_COURSE_PROFILE）。
 * 只读、低频（每张 record 间隔 250ms）；JWT 从 data/_workspace/_account/auth 最新抓包提取。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { findJwt, makeHeaders, MINERVA_BASE, canonAnswer, htmlToTextKeepLayout, isPlaceholderAnswerText } = require('./gaodun_paper_core');
const { loadProfile, primaryIds, workspaceDirFor, argvProfileKey } = require('./load_profile');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const ROOT = path.resolve(__dirname, '..', '..');
// sourceFromType：glivepro 作业来源类型枚举（平台常量、非课程 ID，跨正课通用；换 epiphany 名师课需另查）
const SFT = 100533962;
const isSprint = (p) => /冲刺模考/.test(p.title) || p.num === 48;

function chapterKey(ch) {
  const s = String(ch || '');
  const seg = /全面精讲/.test(s) ? 1 : /强化冲刺/.test(s) ? 2 : 3;
  const m = s.match(/(\d+)/);
  return seg * 1000 + (m ? Number(m[1]) : 999);
}
// 递归 syllabus，维护最近章节祖先，收集 paper 节点
function collectPapers(syl) {
  const papers = [];
  const walk = (x, ch) => {
    if (typeof x !== 'object' || x === null) return;
    let c = ch;
    if (x.itemId && x.name && x.discriminator !== 'paper') c = { csItemId: x.itemId, chapter: x.name };
    if (x.discriminator === 'paper' && x.paperId) {
      papers.push({
        paperId: x.paperId, resourceId: x.resourceId, csItemId: c && c.csItemId, chapter: c && c.chapter,
        title: x.title, num: x.num, progress: x.progress, homework: x.homework,
      });
    }
    Object.values(x).forEach((v) => { if (Array.isArray(v) || (typeof v === 'object' && v)) walk(v, c); });
  };
  walk(syl, null);
  return papers;
}

/**
 * 对“已交卷但分数<总分”的卷只读复核是否为【平台最优】：
 * 配了 AI 的主观题(cpaBotType===3)必须全部 correctStatus===2；系统自动判分的客观题必须拿满；
 * 题库未配 AI(cpaBotType!==3) 的主观题平台不判分，不纳入失分。返回 {best,configured,configuredFull,unsupported,bad}。
 */
async function inspectSubmitted(H, logId) {
  const z = await (await fetch(`${MINERVA_BASE}/paper/analysis`, {
    method: 'POST', headers: H,
    body: JSON.stringify({ paperDataLogId: logId, openEnergyToEquity: 1 }),
  })).json();
  if (z.status !== 0) return { best: false, err: `${z.status} ${z.message}` };
  let configured = 0; let configuredFull = 0; let unsupported = 0; let ceiling = 0; const bad = [];
  // 强归一化：去空白/标点/符号，仅留中英文数字，用于判断“我方提交是否就是标准答案原文”
  const norm = (s) => String(s || '').replace(/[\s\p{P}\p{S}]/gu, '').toLowerCase();
  const answerMatchesCanon = (leaf) => {
    const qa = leaf.questionAnswer || {};
    // 标准答案与作答侧同口径（BUG-03）：独立 answer 为实质内容则优先（保留排版），否则才从 analysis 提炼
    const std = !isPlaceholderAnswerText(qa.answer) ? htmlToTextKeepLayout(qa.answer) : canonAnswer(qa.analysis);
    const canon = norm(std);
    const mine = norm((leaf.userAnswer || {}).userAnswer);
    if (!canon || mine.length < Math.min(20, canon.length * 0.5)) return false;
    return canon.includes(mine) || mine.includes(canon);
  };
  const judgeLeaf = (leaf) => {
    const t = leaf.questionType;
    const ai = leaf.aiCorrect;
    const ua = leaf.userAnswer || {};
    if (t === 6) {
      if (ai && ai.cpaBotType === 3) {
        configured += 1;
        if (ai.correctStatus === 2) configuredFull += 1;
        else if (ai.correctStatus === 6 && answerMatchesCanon(leaf)) ceiling += 1; // AI 判分上限：提交=标准答案原文但模型反复判部分分
        else if (ai.correctStatus === 3) ceiling += 1; // AI 批改返回空结果(pointList/corrects空、已耗权益)，平台侧批改失败，非答案错误(实锤82337 Q1757524)
        else if (ai.correctStatus === 1) ceiling += 1; // 批改中/未出结果，多次重做仍为1则稳定为平台不出分，暂归平台最优
        else bad.push({ q: leaf.questionId, cs: ai.correctStatus, matchCanon: ai.correctStatus === 6 ? answerMatchesCanon(leaf) : undefined });
      } else {
        unsupported += 1; // 题库未配 AI 判分，平台不给分，忽略
      }
    } else if (t !== 5) { // 客观/判断/填空等系统自动判分题：必须拿满
      if ((ua.userScore || 0) < (leaf.score || 0)) bad.push({ q: leaf.questionId, score: ua.userScore, full: leaf.score });
    }
  };
  for (const m of z.result.moduleList || []) {
    for (const q of m.questionList || []) {
      if (q.questionType === 5 && Array.isArray(q.subQuestionList)) q.subQuestionList.forEach(judgeLeaf);
      else judgeLeaf(q);
    }
  }
  return { best: bad.length === 0 && configured === configuredFull + ceiling, configured, configuredFull, unsupported, ceiling, bad };
}

(async () => {
  const profile = loadProfile(argvProfileKey());
  const ids = primaryIds(profile);
  const manifestDir = workspaceDirFor(profile.key, 'manifest');
  fs.mkdirSync(manifestDir, { recursive: true });
  const COURSE_ID = ids.courseId;
  const COURSE_SYLLABUS_ID = ids.syllabusId;
  if (!COURSE_ID || !COURSE_SYLLABUS_ID) {
    throw new Error(`profile ${profile.key} 缺 primaryCourse.saasCourseId/syllabusId，无法刷新作业基线`);
  }
  console.log(`[profile] ${profile.key}｜${profile.subject.name}｜courseId=${COURSE_ID} syllabus=${COURSE_SYLLABUS_ID} platform=${ids.platform}`);
  const H = makeHeaders(findJwt());
  // 1) syllabus
  const sj = await (await fetch(
    `https://apigateway.gaodun.com/g-study/api/v1/front/course/${COURSE_ID}/syllabus/glive/${COURSE_SYLLABUS_ID}`,
    { headers: H },
  )).json();
  if (sj.status !== 0) throw new Error(`syllabus 失败 ${sj.status} ${sj.message}`);
  const all = collectPapers(sj.result);
  const sprint = all.filter(isSprint);
  const base = all.filter((p) => !isSprint(p))
    .sort((a, b) => chapterKey(a.chapter) - chapterKey(b.chapter) || a.paperId - b.paperId);
  console.log(`syllabus：paper 共 ${all.length}（基础 ${base.length} / 冲刺 ${sprint.length} 排除）；顶层 resourceTotal=${sj.result.resourceTotal} done=${sj.result.doneResourceTotal}`);

  // 2) 逐张只读 record 审计
  const inv = []; const audit = [];
  const stat = { 满分: 0, 平台最优: 0, 非满分: 0, 未提交: 0, 未做: 0 };
  for (let i = 0; i < base.length; i += 1) {
    const p = base[i];
    const z = await (await fetch(
      `${MINERVA_BASE}/student/paper/record?paperId=${p.paperId}&sourceFromType=${SFT}&needAuth=1`, { headers: H },
    )).json();
    const r = z.result;
    let cls; let score = null; let total = p.num; let times = 0; let pss = null; let detail = null;
    if (!r) { cls = '未做'; stat.未做 += 1; }
    else {
      times = r.times; score = r.score; total = r.questionTotal; pss = r.paperSubmitStatus;
      if (r.paperSubmitStatus === 1) {
        // BUG-01 修复：score 是得分、questionTotal 是题数，量纲不同且 record 无卷面满分字段，
        // 旧 `score>=questionTotal` 对百分制卷恒真（如 80>=5）会把错题卷误判满分并冻结。已交卷一律走 paper/analysis 逐题判：
        // 客观逐题拿满 + 配 AI 主观 cs=2/判分上限 + 未配 AI 忽略；best 即"到顶"，再按有无未配AI/判分上限区分真满分与平台最优。
        detail = await inspectSubmitted(H, r.paperDataLogId);
        await sleep(250);
        if (detail.best && detail.unsupported === 0 && detail.ceiling === 0) {
          cls = '满分'; stat.满分 += 1;
        } else if (detail.best) {
          // 到顶但含"题库未配 AI"或"AI 判分上限"：平台给不了更多，归平台最优
          cls = '平台最优'; stat.平台最优 += 1;
          console.log(`  ${p.paperId} 平台最优（可AI判满 ${detail.configuredFull}/${detail.configured}${detail.ceiling ? `，AI判分上限 ${detail.ceiling}` : ''}，未配AI ${detail.unsupported}）`);
        } else {
          cls = '非满分'; stat.非满分 += 1;
          console.log(`  ${p.paperId} 真·非满分 score=${r.score}/${r.questionTotal}题`, JSON.stringify(detail.bad || detail.err).slice(0, 200));
        }
      }
      else { cls = '未提交'; stat.未提交 += 1; }
    }
    inv.push({ paperId: p.paperId, resourceId: p.resourceId, csItemId: p.csItemId, chapter: p.chapter,
      title: p.title, num: p.num, progress: p.progress, times, score, questionTotal: total, paperSubmitStatus: pss, cls, detail });
    if (cls !== '满分' && cls !== '平台最优') audit.push({ paperId: p.paperId, title: p.title, num: p.num, score, total, cls, progress: p.progress, chapter: p.chapter });
    if ((i + 1) % 20 === 0) console.log(`  ...${i + 1}/${base.length}`);
    await sleep(250);
  }

  const invPath = path.join(manifestDir, 'papers_inventory.json');
  const auditPath = path.join(manifestDir, 'papers_audit.json');
  fs.writeFileSync(invPath, JSON.stringify(inv, null, 1));
  fs.writeFileSync(auditPath, JSON.stringify(audit, null, 1));
  console.log(`写出 ${path.relative(ROOT, invPath)} / ${path.relative(ROOT, auditPath)}（按 profile 子目录隔离）`);
  console.log('\n===== 基线刷新完成 =====');
  console.log('分类:', JSON.stringify(stat));
  console.log('已完成（满分+平台最优）:', stat.满分 + stat.平台最优, '张；待做（audit）:', audit.length,
    '张 = 未提交', stat.未提交, '+ 非满分', stat.非满分, '+ 未做', stat.未做);
  console.log('冲刺（最后处理，不进 audit）:', sprint.map((s) => `${s.paperId}(prog=${s.progress})`).join(', '));
  process.exit(0);
})().catch((e) => { console.error('[refresh FAIL]', e.stack || e.message); process.exit(1); });
