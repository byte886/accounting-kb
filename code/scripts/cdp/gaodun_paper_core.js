/**
 * gaodun_paper_core.js — 高顿「纯接口做完一张卷」的共享核心
 *
 * 覆盖：客观题（type1 单选 / type2 多选）+ 主观计算大题（type5 父题容器套 type6 自由文本小问，AI 批改）。
 * 完整链路均已在 2026-09-02 卷 82749「带答案交卷 + 交卷后逐题 AI 批改」干净实例上实测到 11/11：
 *
 *   record → redo-paper（返回题面与标准答案/解析）
 *     → 平铺构造 userAnswerList：type5 父题本身不提交，平铺其 subQuestionList 为 type6 子题项
 *     → 满足最小作答时长 → submit-paper 一次性交【全部】答案（主观子题绝不能留空）
 *     → 交卷后对每个 type6 子题逐题 POST correct-ai/cpa（必带 openEnergyToEquity:1），AI 判分会回写正式成绩：
 *         cs=2 批改完成(满分) / cs=6 部分得分→用整段解析(含【点拨】)重发一次覆盖 /
 *         cs=1 批改中→每 5s 长轮询(单题上限 75s) / 11193404 已批过→直接读状态
 *     → exam-report 核对：userScore===totalScore、noCorrectAiQuestionScore===0、wrongQuestionIds 空、子题全 ai=2
 *
 * 交卷与批改解耦（重要设计原则）：
 *   - submit 成功即「作业已交」，课程大纲 progress=1，这是硬完成，不消耗 AI 批改权益；
 *   - AI 批改负责把主观题冲到满分；若批改超时 / 权益用完 / 异常，交卷结果保留，只在返回里标记
 *     aiPartial/aiFailed，不抛崩、不影响后续卷，之后可补批。
 *
 * 纯 Node 全局 fetch（Node>=18），不依赖浏览器；鉴权头 authentication 由调用方传入或用 findJwt 从抓包目录读取。
 * 接口契约详见 docs/development/api/gaodun-exam-api.md。
 */
'use strict';
const fs = require('fs');
const path = require('path');

const MINERVA_BASE = 'https://apigateway.gaodun.com/minerva/api/v1/front';
const AITUTOR_BASE = 'https://apigateway.gaodun.com/aitutor/api/v1/front';
// 课程 ID：env GAODUN_COURSE_ID 最高优先；否则取课程 profile 主源 saasCourseId（缺省税法 42660）
// 换课设 GAODUN_COURSE_PROFILE=<key> 即可，无需再手抄 ID
const { loadProfile, primaryIds, accountAuthDir } = require('./load_profile');
const COURSE_ID = parseInt(process.env.GAODUN_COURSE_ID || String(primaryIds(loadProfile()).courseId), 10);
const SOURCE_FROM_TYPE = parseInt(process.env.GAODUN_SOURCE_FROM_TYPE || '100533962', 10); // 作业卷固定 sourceFromType，可环境变量覆盖
const CPA = { aiTutorConfigId: 55, sourceType: 100536073, cpaAiBotType: 3, botId: '171109285178801048' }; // 兜底默认值；实际以每题 redo 的 aiCorrect 为准
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 主观题 AI 批改默认并发数：不同 itemId 相互独立，可小并发；保守取 3 兼顾速度与风控，可用 opts.aiConcurrency 覆盖
const AI_CONCURRENCY = 3;
// cs=6（AI 语义判分部分得分）三级文本补全后仍不满时的 best-of-N 原样重取上限：
// 高顿 AI 判分存在“同一份标准答案、重复提交结果不同”的模型波动（外部 LLM-judge 固有非确定性），
// 我们提交的本就是标准答案原文，故原样重交、碰到一次 cs=2 即停；用尽仍 cs=6 归 aiCeiling（AI 判分上限，不阻断平台最优）。
const AI_CS6_RERUN = 4;
/** 限并发 map：最多 limit 个 worker 同时在跑，保持结果顺序 */
async function mapLimit(items, limit, worker) {
  const ret = new Array(items.length);
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const idx = cursor;
      cursor += 1;
      ret[idx] = await worker(items[idx], idx);
    }
  });
  await Promise.all(runners);
  return ret;
}

/** 从账号鉴权抓包目录（默认 data/_workspace/_account/auth）最新 jsonl 倒序提取 authentication 头
 *  按文件 mtime 升序排列（旧到新），倒序遍历时优先读最新文件；不按文件名排序，
 *  否则 refresh 开头的文件永远排在 schedule、sprint 开头文件前面、反而最后被读到（曾导致用过期token）。 */
function findJwt(dir) {
  const authDir = dir || accountAuthDir();
  const files = fs.readdirSync(authDir)
    .filter((f) => f.endsWith('.jsonl'))
    .map((f) => ({ f, mtime: fs.statSync(path.join(authDir, f)).mtimeMs }))
    .sort((a, b) => a.mtime - b.mtime)  // 旧→新，下面倒序即最新优先
    .map((x) => x.f);
  for (let i = files.length - 1; i >= 0; i -= 1) {
    const lines = fs.readFileSync(path.join(authDir, files[i]), 'utf8').split('\n').filter(Boolean);
    for (let j = lines.length - 1; j >= 0; j -= 1) {
      try {
        const o = JSON.parse(lines[j]);
        if (o.headers && o.headers.authentication) return o.headers.authentication;
      } catch { /* skip */ }
    }
  }
  throw new Error('未找到 authentication，需先用 CDP 抓一次带鉴权的请求。');
}

function makeHeaders(jwt, opts = {}) {
  const origin = opts.origin || 'https://glivepro.gaodun.com';
  return {
    authentication: jwt,
    'content-type': 'application/json;charset=UTF-8',
    accept: 'application/json, text/plain, */*',
    'accept-language': 'zh',
    origin,
    referer: opts.referer || `${origin}/`,
    'user-agent': UA,
  };
}

// 平台 header 预设：glive=正课(glivepro, saasCourseType=16)；ep3=名师专业课(epiphany, saasCourseType=13)。
// 两平台鉴权头一致、只差 origin/referer。统一从这里取，避免各脚本事后赋值、甚至写出 Referer/referer 大小写重复键。
const PLATFORM_PROFILES = {
  glive: { origin: 'https://glivepro.gaodun.com' },
  ep3: { origin: 'https://epiphany.gaodun.com', referer: 'https://epiphany.gaodun.com/' },
};
/** 按平台取鉴权头：platformHeaders(jwt,'ep3')；extra 可再覆盖个别字段 */
function platformHeaders(jwt, platform = 'glive', extra = {}) {
  const p = PLATFORM_PROFILES[platform] || {};
  return makeHeaders(jwt, { origin: p.origin, referer: p.referer, ...extra });
}

/** 最小作答停留秒：max(20, 答案项*1.5 向上取整到 5s)；含主观大题再保底 25s */
function dwellSec(answerCount, hasSubjective) {
  return Math.max(20, Math.ceil((answerCount * 1.5) / 5) * 5, hasSubjective ? 25 : 0);
}

const stripHtml = (s) => (s || '')
  .replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();

// 保留会计分录排版的 HTML→纯文本：块级标签/<br> 转换行，&nbsp; 转空格，保留制表符与行首缩进（借/贷、金额对齐）。
// 与 stripHtml 的区别：不折叠换行与行内多空格——分录/综合大题平台 AI 按"借/贷"逐笔识别，挤成一行会逐笔判 0（实测 85418 2-2）。
const htmlToTextKeepLayout = (s) => (s || '')
  .replace(/<\s*br\b[^>]*>/gi, '\n')
  .replace(/<\/(p|div|li|tr|h\d)>/gi, '\n')
  .replace(/<[^>]+>/g, '')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
  .split('\n').map((l) => l.replace(/[ \t]+$/, '')) // 只去行尾空白，保留行首缩进与内部对齐空格/制表
  .join('\n')
  .replace(/\n{3,}/g, '\n\n')
  .split('\n').map((l) => (l.trim() === '' ? '' : l)).join('\n').trim();

// 判断一段答案文本是否为"无实质内容的占位"（无 / 略 / 见答案 / 解析见答案 等）。
// 仅当整段去掉小问序号、标点空白后只剩占位词才判 true；"（1）略（2）有实质内容…"这类不误判。
const isPlaceholderAnswerText = (s) => {
  const t = stripHtml(s);
  if (!t) return true;
  const core = t.replace(/[（(]\s*\d+\s*[)）]/g, '').replace(/[\s\p{P}\p{S}]/gu, '');
  if (!core) return true;
  return /^(无|暂无|略|省略|见答案|详见答案|答案见解析|解析见答案|参考答案见解析|见解析|同解析|见上述解析?)+$/.test(core);
};

/** 首版主观答案：取【点拨】之前的计算/结论句，去掉开头 (1) 序号与结尾句读符号 */
function canonAnswer(analysis) {
  let a = stripHtml(analysis).split(/【点拨】/)[0].trim();
  a = a.replace(/^[（(]\d+[)）]/, '').trim().replace(/[。.;；]$/, '').trim();
  return a;
}

/** cs=6 兜底答案：整段解析（含【点拨】里的法理 / 因果定性句），覆盖 AI 动态生成的定性采分点 */
function fullAnswer(analysis) {
  return stripHtml(analysis);
}

// AI 判分友好答案（首次提交用）：标准解之外，把【点拨】里影响结论的判定语境一并给出（去掉教辅标记）。
// 实测 86722：业务(1)第二个采分点"购入免税货物取得普票不得抵扣"藏在【点拨】，canon 砍掉后被判漏点 0 分。
// 冗余的政策说明不会导致扣分（判分按采分点命中），只可能帮助命中，故首次直接给最完整版本，避免 cs=2 终态锁死无补救机会。
function judgeAnswer(analysis) {
  return stripHtml(analysis)
    .replace(/【点拨】/g, '；')
    .replace(/\s+/g, ' ')
    .replace(/；\s*；+/g, '；')
    .replace(/^；|；$/g, '')
    .trim();
}

// 从 correct-ai/status 结果提取采分点与真实得分。showStatus：1=命中，2=未命中。
// 注意 cs=2 只代表"批改完成"，全命中(userScore=questionScore)才是满分；cs=2 且采分点 show=2 是"判完但 0 分"。
function aiPoints(rr) {
  const points = [];
  let got = 0; let full = 0;
  ((rr && rr.corrects) || []).forEach((c) => {
    const ct = c.correctText || {};
    if (typeof ct.userScore === 'number') got += ct.userScore;
    if (typeof ct.questionScore === 'number') full += ct.questionScore;
    (ct.correctPointList || []).forEach((p) => points.push(p));
  });
  if (!full && rr && typeof rr.userScore === 'number') { got = rr.userScore; full = rr.userScore; }
  // 满分以"记分为准"：userScore 累计达到 questionScore 即满分（实测存在不记分的参考采分点 show=2 但仍给满分，如 1686288 1/1）；
  // 只有在拿不到记分（full=0）时才退化为"所有采分点命中"。
  const isFull = full > 0 ? got + 1e-9 >= full : (points.length > 0 && points.every((p) => p.showStatus === 1));
  return { points, got, full, isFull };
}

/**
 * 从【点拨】段提炼干净的法理 / 定性陈述句（cs=6 补定性采分点用）。
 * 做法：取【点拨】之后文本 → 砍掉“即/也就是…”引导的通用公式尾巴（其含“账面成本”等占位词，
 * 直接贴上去反而会让 AI 把定性句吞进计算维度）→ 按句读切分、丢弃纯公式与碎片，保留因果陈述。
 * 实测 1681680：等式句单独发只拿计算分(points 0/1)，叠加本句后 points 1/1、cs=2。
 */
function qualitativeAnswer(analysis) {
  const raw = stripHtml(analysis);
  const mark = raw.indexOf('【点拨】');
  if (mark < 0) return '';
  let seg = raw.slice(mark + '【点拨】'.length);
  seg = seg.split(/，?\s*(?:即|也就是|公式为|公式如下|具体公式)/)[0]; // 砍通用公式尾巴，保留因果陈述（内部逗号保留）
  return seg.split(/[。；;]/).map((s) => s.trim())
    .filter((s) => s.length >= 4 && !/^[（(]\d+[)）]$/.test(s)
      && !( /[=＝]/.test(s) && /(账面|成本|费用|收入|金额|价税|某\b)/.test(s) ))
    .join('；');
}

/**
 * 数题干「要求：…（1）…（2）…」里要求回答的小问数 N（从 1 连续递增 1..N 的长度）。
 * 只取「要求/根据上述资料/回答」之后的序号，避开题干业务描述里的括号数字（如 业务（4）、硫酸雾（100））。
 * 顶层独立 type6 大题的多个小问写在题干纯文本里（subQuestionList 为空），必须靠它识别要答几问。
 */
function countAskedSubs(title) {
  const t = stripHtml(title || '');
  const tail = t.split(/要求|根据上述资料|回答下列|回答问题|问题如下/).pop();
  const set = new Set();
  const re = /[（(]\s*(\d+)\s*[)）]/g; let mm;
  while ((mm = re.exec(tail))) set.add(parseInt(mm[1], 10));
  let n = 0; while (set.has(n + 1)) n += 1; // 最长 1..N 连续前缀
  return n;
}

/** 答案文本中实际出现的顶层小问序号集合（1..N 哪些在） */
function coveredSubs(text, askedN) {
  const have = new Set();
  const re = /[（(]\s*(\d+)\s*[)）]/g; let mm;
  while ((mm = re.exec(text || ''))) { const x = parseInt(mm[1], 10); if (x >= 1 && x <= askedN) have.add(x); }
  return have;
}

/**
 * 多小问主观大题的【提交答案】：完整保留解析里的全部小问，绝不按【点拨】截断。
 * 背景（2026-09-05 45题/1843142 实锤）：解析形态为 (1)(2)【点拨】…(3)…【点拨】…(4)，
 * 旧 canonAnswer 用 split('【点拨】')[0] 会把第一个点拨之后的(3)(4)正式小问整段丢弃，导致漏答丢分、知识源残缺。
 * 做法：去教辅标记但保留点拨内容（含采分语境、冗余不扣分）；在每个顶层小问序号前换行，保证(1)(2)…分点清晰。
 */
function multiSubAnswer(analysis, askedN) {
  let t = stripHtml(analysis)
    .replace(/【点拨】|【提示】/g, '；')
    .replace(/；\s*；+/g, '；').replace(/^；+|；+$/g, '')
    .replace(/\s+/g, ' ').trim();
  for (let n = askedN; n >= 1; n -= 1) { // 每个正式小问序号前换行分点（从大到小替换，避免位移；只换第一处=正式小问）
    t = t.replace(new RegExp(`\\s*[（(]\\s*${n}\\s*[)）]`), `\n（${n}）`);
  }
  return t.trim();
}

/**
 * 点拨段保守精简：去掉①-⑩条目编号；删「20XX 年取消/调整/变更…政策」这类纯政策变迁背景句，
 * 其余本题判定 / 法理 / 公式一律保留（6 卷实测含点拨满分率 8/9，8 道满分题采分点就藏在点拨，整段删除会丢分）。
 */
function pruneBasis(t) {
  if (!t) return '';
  const s = t.replace(/[①②③④⑤⑥⑦⑧⑨⑩]/g, '');
  const kept = s.split(/(?<=。|；|;)/).map((x) => x.trim()).filter(Boolean)
    .filter((x) => !( /20\d{2}\s*年/.test(x) && /(取消|调整|变更|改为|政策)/.test(x)
      && !/(不得|应当|免征|转出)/.test(x) ));
  return kept.join('').replace(/\s+/g, ' ').trim();
}

/**
 * 按题干要求的小问数 N，把整段解析切成 N 个小问块。正式小问序号位置必须从 1 开始严格递增，
 * 因而自动跳过点拨 / 正文内部的噪声括号（业务（1）、硫酸雾（100））；切不齐则返回整段兜底，绝不丢小问。
 */
function splitAskedBlocks(t, askedN) {
  if (askedN <= 1) return [t];
  const pos = []; let from = 0;
  for (let n = 1; n <= askedN; n += 1) {
    const m = new RegExp(`[（(]\\s*${n}\\s*[)）]`).exec(t.slice(from));
    if (!m) { pos.push(-1); continue; }
    const abs = from + m.index; pos.push(abs); from = abs + 1;
  }
  if (pos.filter((p) => p >= 0).length < askedN) return [t];
  const blocks = [];
  for (let n = 0; n < askedN; n += 1) blocks.push(t.slice(pos[n], n + 1 < askedN ? pos[n + 1] : t.length));
  return blocks;
}

/**
 * 主观题统一答案生成（2026-09-06 重构，统一旧 canon/judge/multiSub 三套互相矛盾口径）：
 *   每个小问 = 正式答案（算式/结论，主体） + 「依据：」+ 点拨里精简后的本题判定/法理；多小问 (1)..(N) 逐行分点。
 * 结论依据 6 卷列联表：含点拨 9 题满分 8、无点拨 6 题满分 4（1681714/1681715 零点拨逐字一致仍 0=平台误判），
 * 故点拨不是 0 分元凶、不能整段删，但要去条目化、删政策背景句，让答案像作答而不是照抄解析堆砌。
 * 交卷答案与 correct-ai 首次批改答案统一用本函数（旧 judgeAnswer 含点拨全文不再使用）。
 */
function cleanSubjectiveAnswer(analysis, askedN) {
  const raw = stripHtml(analysis);
  const blocks = splitAskedBlocks(raw, askedN);
  const lines = blocks.map((b, i) => {
    const parts = b.split(/【点拨】|【提示】/);
    const main = parts[0].replace(/^\s*[（(]\s*\d+\s*[)）]\s*/, '').replace(/\s+/g, ' ').trim();
    const basis = pruneBasis(parts.slice(1).join(' '));
    let line = main;
    if (basis) line += ` 依据：${basis}`;
    line = line.replace(/[;；\s]+$/, '').trim();
    // 官方"（1）、（2）略"合并略写被按序号切开时，空块或只剩顿号/标点的块补"略"，不输出看起来"没作答"的空序号（实测 82344 Q26）
    if (!line || !line.replace(/[\s\p{P}\p{S}]/gu, '')) line = '略';
    return askedN >= 2 ? `（${i + 1}）${line}` : line;
  });
  return lines.join('\n').trim();
}

/**
 * 主观题答案来源选择器（2026-09-08 人工核查修复，BUG-03/06）。
 * questionAnswer 有两个字段：answer=独立标准答案（权威、常带会计分录原始排版），analysis=解析。实测四种形态：
 *   B：answer="<p>无</p>"、analysis=完整解 → 从 analysis 提炼；
 *   C：answer=完整解、analysis="见答案/解析见答案" → 必须取 answer（旧逻辑误交"见答案"三字，82348 Q31）；
 *   D：answer=完整解、analysis=仅思路点拨 → 必须取 answer（旧逻辑只交了点拨，85418 Q2/Q3）。
 * 规则：answer 为实质内容则优先（保留排版）；answer 占位才从 analysis 提炼；两者都占位时兜底且由上层标记，绝不把占位词当答案。
 * @returns {{canon:string, from:'answer'|'analysis'|'answer-fallback'|'analysis-fallback'|'empty'}}
 */
function pickSubjectiveCanon(qa, askedN) {
  const ansRaw = htmlToTextKeepLayout(qa.answer);
  const ansValid = !!ansRaw && !isPlaceholderAnswerText(qa.answer);
  let ana = '';
  try { ana = cleanSubjectiveAnswer(qa.analysis, askedN); } catch { ana = ''; }
  const anaValid = !!ana && !isPlaceholderAnswerText(ana);
  if (ansValid) return { canon: ansRaw, from: 'answer' };
  if (anaValid) return { canon: ana, from: 'analysis' };
  if (ansRaw) return { canon: ansRaw, from: 'answer-fallback' };
  if (ana) return { canon: ana, from: 'analysis-fallback' };
  return { canon: '', from: 'empty' };
}

/**
 * 处理一个主观判分叶子（type6）：统一用于「type5 大题下的子题」与「顶层独立 type6（无 type5 包裹）」。
 * 答案取解析提炼（analysis），兜底 answer；按 aiCorrect.cpaBotType 分到可 AI 批改 / 平台未配 AI。
 */
function pushSubjectiveLeaf(leaf, userAnswerList, subjective, unsupported, askedN = 1, answerGaps = null) {
  const qa = leaf.questionAnswer || {};
  // 答案来源：独立标准答案 answer 为实质内容则优先（保留会计分录排版），answer 占位才从 analysis 提炼（BUG-03）
  const picked = pickSubjectiveCanon(qa, askedN);
  let canon = picked.canon;
  // 完整性校验门：题干要求的每个小问都必须出现在提交答案里，缺则放大序号范围重切、仍缺用保留排版标准答案/整段解析兜底并显式记录（禁止静默漏答）
  if (askedN >= 2 && answerGaps) {
    const have = coveredSubs(canon, askedN);
    const miss = [];
    for (let i = 1; i <= askedN; i += 1) if (!have.has(i)) miss.push(i);
    if (miss.length) {
      const reAna = cleanSubjectiveAnswer(qa.analysis, Math.max(askedN, 12));
      const ansLayout = htmlToTextKeepLayout(qa.answer);
      canon = (reAna && !isPlaceholderAnswerText(reAna)) ? reAna
        : ((ansLayout && !isPlaceholderAnswerText(qa.answer)) ? ansLayout : fullAnswer(qa.analysis));
      answerGaps.push({ questionId: leaf.questionId, askedN, missing: miss, fallbackUsed: true });
    }
  }
  userAnswerList.push({
    questionId: leaf.questionId, questionType: 6,
    userAnswer: canon, userClozeAnswers: [], userAnswerImageList: [],
  });
  const ai = leaf.aiCorrect || {};
  // qual/full 仅在解析非占位时用于 cs=6 逐级补全；解析为"见答案"占位时回退 canon，避免重发垃圾文本（BUG-06）
  const qual0 = qualitativeAnswer(qa.analysis);
  const full0 = fullAnswer(qa.analysis);
  const base = {
    questionId: leaf.questionId,
    canon,
    qual: (qual0 && !isPlaceholderAnswerText(qual0)) ? qual0 : canon,
    full: (full0 && !isPlaceholderAnswerText(full0)) ? full0 : canon,
    judge: canon, // 首次 AI 批改与交卷同版；cs=6 部分分时再由 correctSubjective 用 qual/full 逐级补全
    askedN,
    score: leaf.score,
    answerFrom: picked.from,
  };
  if (ai.cpaBotType === 3) {
    subjective.push({ ...base, aiCfg: { aiTutorConfigId: ai.aiTutorConfigId, botId: ai.botId, cpaBotType: ai.cpaBotType } });
  } else {
    unsupported.push({ questionId: leaf.questionId, cpaBotType: ai.cpaBotType, score: leaf.score });
  }
}

/**
 * 由 redo-paper 结果平铺出交卷答案。兼容两种主观题结构：type5 大题套 type6 子题、顶层独立 type6。
 * @returns {{userAnswerList:Array, subjective:Array, unsupported:Array}}
 *   userAnswerList 直接用于 submit-paper（所有子题都提交标准答案）；
 *   subjective 仅收录 aiCorrect.cpaBotType===3（题库配了 CPA 批改机器人）的 type6 子题，携带该题自己的 configId/botId；
 *   unsupported 收录 type6 但 cpaBotType!==3（题库未配 AI 评分标准，cpa 会回 11193401、UI 也无批改入口）的子题，答案照交但不请求批改。
 */
function buildUserAnswers(redo) {
  const userAnswerList = [];
  const subjective = [];
  const unsupported = [];
  const answerGaps = []; // 多小问大题答案覆盖缺口（完整性校验门，正常应为空）
  for (const m of redo.moduleList || []) {
    for (const q of m.questionList || []) {
      if (q.questionType === 5 && Array.isArray(q.subQuestionList) && q.subQuestionList.length) {
        // 大题容器自身不作答，按【子题题型】分流：
        //  - t6 主观子题走答案来源选择器；t1/2/3/4 客观子题直接用标准答案 answer（BUG-02：旧逻辑一律当主观、从解析提炼文字，致 82344 Q27/Q29 等客观子题答错）
        for (const sub of q.subQuestionList) {
          if (sub.questionType === 6) {
            pushSubjectiveLeaf(sub, userAnswerList, subjective, unsupported, 1, answerGaps);
          } else {
            const objAns = (sub.questionAnswer || {}).answer;
            // 提交前防呆断言（REQ-03）：客观子题必须拿到非空标准答案，否则宁可不交也不能瞎答
            if (objAns === null || objAns === undefined || objAns === '') {
              throw new Error(`客观子题 questionId=${sub.questionId}(t${sub.questionType}) 缺标准答案 answer，已中止交卷`);
            }
            userAnswerList.push({
              questionId: sub.questionId, questionType: sub.questionType,
              userAnswer: objAns, userClozeAnswers: [], userAnswerImageList: [],
            });
          }
        }
      } else if (q.questionType === 6) {
        // 顶层独立主观题：数题干要求的小问数，多小问必须完整覆盖（修复点拨截断漏答）
        const askedN = countAskedSubs(q.title);
        pushSubjectiveLeaf(q, userAnswerList, subjective, unsupported, askedN, answerGaps);
      } else {
        // 客观题（单选/多选/判断/填空等系统自动判分）：直接用标准答案 answer
        userAnswerList.push({
          questionId: q.questionId, questionType: q.questionType,
          userAnswer: (q.questionAnswer || {}).answer,
          userClozeAnswers: [], userAnswerImageList: [],
        });
      }
    }
  }
  return { userAnswerList, subjective, unsupported, answerGaps };
}

/** 对单个 type6 子题做 AI 批改直到终态，结果写回 out（aiFull/aiPartial/aiFailed/aiUnsupported） */
async function correctSubjective(call, logId, s, log, out) {
  const cfg = s.aiCfg || {};
  const body = (ans) => ({
    itemId: s.questionId, paperDataLogId: logId,
    aiTutorConfigId: cfg.aiTutorConfigId ?? CPA.aiTutorConfigId,
    sourceType: CPA.sourceType,
    cpaAiBotType: cfg.cpaBotType ?? CPA.cpaAiBotType,
    botId: cfg.botId ?? CPA.botId,
    userAnswer: ans, excelAnswer: '', openEnergyToEquity: 1,
  });
  const poll = async () => {
    let r = null;
    for (let i = 0; i < 15; i += 1) { // 每 5s，最多 75s
      await sleep(5000);
      const z = await call('GET',
        `/question/correct-ai/cpa/status?paperDataLogId=${logId}&itemId=${s.questionId}`, null, AITUTOR_BASE);
      r = z.result;
      if (r && r.correctStatus !== 1) return r;
    }
    return r;
  };

  // 首次直接提交"判分友好"完整答案（标准解+点拨判定语境），最大化一次命中，规避 cs=2 终态锁死
  const st = await call('POST', '/question/correct-ai/cpa', body(s.judge), AITUTOR_BASE);
  if (st.status === 11193404) { // 该题已批改过：直接读既有结果，按真实采分点核对（cs=2≠满分）
    const z = await call('GET',
      `/question/correct-ai/cpa/status?paperDataLogId=${logId}&itemId=${s.questionId}`, null, AITUTOR_BASE);
    const sp = aiPoints(z.result);
    if (z.result && z.result.correctStatus === 2 && sp.isFull) { out.aiFull += 1; log(`    子题${s.questionId} 已批过且采分点全命中 ${sp.got}/${sp.full} 满分`); return; }
    if (z.result && z.result.correctStatus === 2) {
      out.aiCeiling.push({ q: s.questionId, got: sp.got, full: sp.full, reason: 'already-graded-cs2-notfull' });
      log(`    子题${s.questionId} 已批过但未满分 ${sp.got}/${sp.full}，cs=2 锁死归判分上限`); return;
    }
  }
  if (st.status === 11193401) { // 题库未配该题 AI 评分标准：平台无判分通道，非我方失败（防御性，build 阶段通常已分流）
    out.aiUnsupported.push({ q: s.questionId, code: 11193401 });
    log(`    子题${s.questionId} 题库未配 AI 评分标准(11193401)，跳过`);
    return;
  }
  if (st.status !== 0 && st.status !== 11193404) {
    out.aiFailed.push({ q: s.questionId, code: st.status, msg: st.message });
    log(`    子题${s.questionId} 发起失败 ${st.status} ${st.message}`);
    return;
  }

  let r = await poll();
  // cs=6 部分得分：逐级补全答案重发（cs=6 允许覆盖同一条批改记录）
  // 1) 等式句+干净定性句；2) 整段解析兜底；3) 用 AI 自己标出的“未命中参考点”定向补（针对 semanticJudgment 维度漏点）
  const missPoints = (rr) => {
    const pts = [];
    ((rr && rr.corrects) || []).forEach((c) => {
      (((c.correctText || {}).correctPointList) || []).forEach((p) => {
        if (p.showStatus !== 1 && p.answer) pts.push(stripHtml(p.answer));
      });
    });
    return [...new Set(pts.filter(Boolean))];
  };
  let tries = [];
  let ri = 0;
  while (r && r.correctStatus === 6) {
    if (ri === 0) {
      if (s.qual) tries.push(`${s.canon}。${s.qual}`);
      tries.push(s.full);
      const miss = missPoints(r);
      if (miss.length) tries.push([s.canon, ...miss].join('。'));
      tries = [...new Set(tries.filter(Boolean))];
    }
    if (ri >= tries.length) break;
    const ans = tries[ri];
    ri += 1;
    log(`    子题${s.questionId} cs=6 部分得分，第 ${ri}/${tries.length} 次补全重发：${String(ans).slice(0, 42)}…`);
    await call('POST', '/question/correct-ai/cpa', body(ans), AITUTOR_BASE);
    r = await poll();
  }

  // 终态统一按真实采分点判定（cs=2 只代表批改完成，必须采分点全命中才是满分）
  const finish = (rr, tag) => {
    if (!rr) { out.aiFailed.push({ q: s.questionId, cs: null, tag }); log(`    子题${s.questionId} 无批改结果(${tag})`); return; }
    const sp = aiPoints(rr);
    if (rr.correctStatus === 2 && sp.isFull) { out.aiFull += 1; log(`    子题${s.questionId} ${tag} 采分点全命中 ${sp.got}/${sp.full} ✔满分`); return; }
    if (rr.correctStatus === 2) {
      out.aiCeiling.push({ q: s.questionId, got: sp.got, full: sp.full, reason: `cs2-notfull-${tag}` });
      log(`    子题${s.questionId} ${tag} 批改完成但未满分 ${sp.got}/${sp.full}，答案正确、归判分上限`); return;
    }
    if (rr.correctStatus === 6) {
      out.aiCeiling.push({ q: s.questionId, got: sp.got, full: sp.full, reason: `cs6-partial-${tag}` });
      log(`    子题${s.questionId} ${tag} 多次补全仍部分分 ${sp.got}/${sp.full}，归判分上限`); return;
    }
    out.aiFailed.push({ q: s.questionId, cs: rr.correctStatus, got: sp.got, full: sp.full });
    log(`    子题${s.questionId} 未达满分 cs=${rr.correctStatus} ${sp.got}/${sp.full}`);
  };

  if (r && r.correctStatus === 2) return finish(r, '首次');
  if (r && r.correctStatus === 6) {
    // best-of-N：补全文本仍 cs=6，答案内容已是标准答案、属 AI 语义判分波动，用整段解析再碰几次
    const rerunAns = s.full || s.judge || s.canon;
    for (let k = 1; k <= AI_CS6_RERUN; k += 1) {
      await sleep(3000);
      log(`    子题${s.questionId} cs=6 AI判分波动，best-of-N 重取 ${k}/${AI_CS6_RERUN}`);
      await call('POST', '/question/correct-ai/cpa', body(rerunAns), AITUTOR_BASE);
      r = await poll();
      if (!r || r.correctStatus !== 6) break; // 离开 cs=6（cs=2 成功 / 其它异常）即退出
    }
    return finish(r, 'best-of-N');
  }
  return finish(r, '终态');
}

/**
 * 纯接口做完一张卷。
 * @param {object} opts
 * @param {{paperId:number,csItemId:number,resourceId:number,title:string,num?:number}} opts.target
 * @param {string} opts.jwt authentication 头
 * @param {boolean} [opts.doAi=true] 交卷后是否对主观子题做 AI 批改（false=只交卷不冲主观分）
 * @param {number} [opts.dwellSecOverride] 自定义最小停留秒
 * @param {string} [opts.origin] 来源域（作业 glivepro / 专区 tiku），默认 glivepro
 * @param {Function} [opts.log] 日志函数
 * @returns {Promise<object>} 结构化结果（submitted=硬交卷完成；fullScore=满分；aiPartial/aiFailed=待补）
 */
async function doPaperViaApi(opts) {
  const { target, jwt } = opts;
  const log = opts.log || ((...a) => console.log(...a));
  const H = makeHeaders(jwt, { origin: opts.origin, referer: opts.referer });
  const call = async (method, urlPath, reqBody, base = MINERVA_BASE) => {
    const res = await fetch(base + urlPath, {
      method, headers: H,
      body: reqBody ? JSON.stringify(reqBody) : undefined,
    });
    return res.json();
  };

  const out = {
    paperId: target.paperId, title: target.title,
    submitted: false, fullScore: false, platformDone: false, objectiveAllRight: false,
    logId: null, userScore: null, totalScore: null,
    aiTotal: 0, aiFull: 0, aiPartial: [], aiFailed: [], aiUnsupported: [], aiCeiling: [],
    answerGaps: [], wrong: null, error: null,
  };

  try {
    // 1) record 取最近实例
    const rec = await call('GET',
      `/student/paper/record?paperId=${target.paperId}&sourceFromType=${SOURCE_FROM_TYPE}&needAuth=1`);
    let logId = rec.result && rec.result.paperDataLogId;
    const business = {
      courseId: COURSE_ID, csItemId: target.csItemId, resourceId: target.resourceId,
      paperId: target.paperId, sourceFromType: SOURCE_FROM_TYPE,
    };

    // 1.5) 首次作答（record 为 null）：必须先 create-paper 创建实例拿到 paperDataLogId，
    //      否则 redo-paper 报 10463001「用户做试卷记录ID不能为空」。重做卷则直接复用最近 logId。
    if (!logId) {
      const cp = await call('POST', '/create-paper', {
        paperId: target.paperId, sourceFromType: SOURCE_FROM_TYPE, businessParam: business,
      });
      if (cp.status !== 0) throw new Error(`create-paper失败 ${cp.status} ${cp.message}`);
      logId = cp.result.paperDataLogId;
      log(`  首次作答 create-paper -> logId=${logId} paperDataId=${cp.result.paperDataId}`);
    }

    // 2) redo 取题面与标准答案
    const redo = await call('POST', '/redo-paper', {
      paperDataLogId: logId, sourceFromType: SOURCE_FROM_TYPE, needReviewInfo: 1,
      businessParam: business, openEnergyToEquity: 1,
    });
    if (redo.status !== 0) throw new Error(`redo失败 ${redo.status} ${redo.message}`);
    const r = redo.result;
    out.logId = r.paperDataLogId;

    // 3) 平铺答案（subjective=配了 CPA 机器人可 AI 批改的子题；unsupported=题库未配 AI 评分标准、答案照交但不批改）
    const { userAnswerList, subjective, unsupported, answerGaps } = buildUserAnswers(r);
    if (answerGaps.length) {
      out.answerGaps = answerGaps;
      log(`  ⚠ 答案完整性校验：${answerGaps.length} 道多小问大题曾缺小问、已用整段解析兜底：${JSON.stringify(answerGaps)}`);
    }
    const hasSub = subjective.length > 0;
    // 真正由系统自动判分的客观题数：type5 子题与「顶层独立 type6」都是主观（questionType=6），不计入客观
    const objectiveCount = userAnswerList.filter((u) => u.questionType !== 6).length;
    out.aiTotal = subjective.length;
    out.aiUnsupported = unsupported;
    log(`  logId=${r.paperDataLogId} 题量=${r.questionTotal} 答案项=${userAnswerList.length} `
      + `可AI批改=${subjective.length} 平台未配AI=${unsupported.length}`);
    if (userAnswerList.length !== r.questionTotal) {
      log(`  ⚠ 答案项数 ${userAnswerList.length} ≠ questionTotal ${r.questionTotal}，以平铺结果为准`);
    }

    // 4) 最小作答时长
    const baseDwell = opts.dwellSecOverride || dwellSec(userAnswerList.length, hasSub);
    let dwell = baseDwell;
    log(`  等待 ${dwell}s 满足最小作答时长...`);
    await sleep(dwell * 1000);

    // 5) 交卷（10462203 作答太快 → 加 20s 重试一次）
    let sub;
    for (let attempt = 1; ; attempt += 1) {
      sub = await call('POST', '/submit-paper', {
        costTime: dwell, paperId: target.paperId, paperDataId: r.paperDataId,
        paperDataLogId: r.paperDataLogId, submitType: 1, userAnswerList,
        sourceFromType: SOURCE_FROM_TYPE, businessParam: business,
      });
      if (sub.status === 10462203 && attempt === 1) {
        dwell += 20;
        log('  ⚠ 作答时间太短，延长 20s 重试');
        await sleep(20000);
        continue;
      }
      break;
    }
    if (sub.status !== 0) throw new Error(`submit被拒 ${sub.status} ${sub.message}`);
    out.submitted = true;
    await sleep(1600);

    // 6) 交卷后逐题 AI 批改（仅主观卷；doAi=false 时只交卷）。小并发池 + 错峰发起。
    if (hasSub && opts.doAi !== false) {
      await sleep(1500);
      const conc = opts.aiConcurrency || AI_CONCURRENCY;
      log(`  主观子题 ${subjective.length} 个，并发=${conc} AI 批改...`);
      await mapLimit(subjective, conc, async (s, idx) => {
        await sleep(idx * 120); // 错峰发起，避免同一毫秒突发
        return correctSubjective(call, r.paperDataLogId, s, log, out);
      });
    }

    // 7) exam-report 最终核对
    await sleep(1500);
    const rep = await call('POST', '/exam-report', { paperDataLogId: r.paperDataLogId, needReviewInfo: 1 });
    const x = rep.result || {};
    out.userScore = x.userScore;
    out.totalScore = x.totalScore;
    out.wrong = x.wrongQuestionIds || [];
    const subStates = [];
    for (const m of x.answerSheetModuleList || []) {
      for (const q of m.questionList || []) for (const ss of q.subQuestion || []) subStates.push(ss);
    }
    // 客观题数以 build 平铺结果为准（非 type6）；exam-report 的 subQuestion 仅 type5 子题，
    // 顶层独立 type6 主观题不在其中，不能用 totalQuestionNum-subStates.length 反推（否则把顶层 type6 误当客观）
    const objectiveTotal = objectiveCount;
    out.objectiveAllRight = x.answerRightNum === objectiveTotal;
    const noCorrectAi = x.noCorrectAiQuestionScore || 0;
    const allAiDone = subStates.length ? subStates.every((ss) => ss.aiQuestionStatus === 2) : true;
    // 严格满分：所有子题（含平台未配 AI 的题）都判满分——未配 AI 卷天然达不到
    out.fullScore = out.submitted && x.userScore === x.totalScore && noCorrectAi === 0
      && out.wrong.length === 0 && allAiDone;
    // 平台最优：客观全对、无失败；配了 AI 的主观题要么判满、要么属 aiCeiling（标准答案原文重取 N 次仍被模型判部分分）；
    // 平台未配 AI（aiUnsupported）与 AI 判分上限（aiCeiling）都不阻断——答案内容均已 100% 正确提交，受限的是平台判分能力/稳定性。
    const aiConfiguredDone = out.aiTotal === 0
      ? true : (out.aiFull + out.aiCeiling.length) === out.aiTotal && out.aiPartial.length === 0;
    out.platformDone = out.submitted && out.objectiveAllRight && out.wrong.length === 0
      && out.aiFailed.length === 0 && aiConfiguredDone;
    const ceilingNote = out.aiCeiling.length ? `、${out.aiCeiling.length} 题 AI 反复重取仍判部分分（判分上限）` : '';
    const verdict = out.fullScore ? '✅满分'
      : out.platformDone ? `🟡平台最优（${out.aiUnsupported.length} 题题库未配AI无法判分${ceilingNote}，答案均已提交）`
        : '⏺已交卷/未满分';
    log(`  结果 ${x.userScore}/${x.totalScore} 客观对${x.answerRightNum}/${objectiveTotal} `
      + `可AI满分${out.aiFull}/${out.aiTotal} 未配AI=${out.aiUnsupported.length} 判分上限=${out.aiCeiling.length} `
      + `noCorrectAi=${noCorrectAi} wrong=${JSON.stringify(out.wrong)} ${verdict}`);
  } catch (e) {
    out.error = e.message;
    log('  ❌', e.message);
  }
  return out;
}

module.exports = {
  findJwt, makeHeaders, platformHeaders, PLATFORM_PROFILES,
  dwellSec, stripHtml, htmlToTextKeepLayout, isPlaceholderAnswerText, pickSubjectiveCanon,
  canonAnswer, fullAnswer, judgeAnswer, aiPoints,
  qualitativeAnswer, countAskedSubs, coveredSubs, multiSubAnswer, cleanSubjectiveAnswer, buildUserAnswers, doPaperViaApi,
  MINERVA_BASE, AITUTOR_BASE, COURSE_ID, SOURCE_FROM_TYPE,
};
