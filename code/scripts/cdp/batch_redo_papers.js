/**
 * batch_redo_papers.js — 批量纯接口补做到 100%（知识点/课后/分章真题等可重做基础卷）
 *
 * 安全护栏：
 *   - 默认 dry-run：只打印将处理的卷与预计停留，不 redo、不 submit；加 --go 才真正执行；
 *   - 硬排除标题含「冲刺模考」/num===48 的卷（最后阶段单独处理）；
 *   - 每张交给 gaodun_paper_core：record→redo(取标准答案，平铺 type5/6 主观)→按题量停留
 *     →submit 全量交卷→交卷后逐题 AI 批改主观子题→exam-report 回查满分；
 *   - 交卷与 AI 批改解耦：submit 成功即“已交卷(progress=1)”，主观 AI 未满分也不中断，单独标记可补批；
 *   - 单张失败不中断其它卷，结果落 data/_workspace/<profile>/papers/batch_result_<日期>.json；
 *   - 卷间停 4s 低频拟人。全程不依赖 UI 点选。
 *
 * 用法：
 *   node scripts/cdp/batch_redo_papers.js            # dry-run：列出 audit 中待补做基础卷
 *   node scripts/cdp/batch_redo_papers.js --go       # 实跑全部待补做卷
 *   node scripts/cdp/batch_redo_papers.js --go 82174 82175   # 只跑指定 paperId
 *   加 --no-ai：只交卷、不做交卷后 AI 批改
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { findJwt, doPaperViaApi, dwellSec } = require('./gaodun_paper_core');
const tokenGuard = require('./auth_token_guard');
const { loadProfile, workspaceDirFor, argvProfileKey } = require('./load_profile');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// token 失效(553649434)自动续命统一走 auth_token_guard（跨进程 single-flight，I-013），本脚本不再内联刷新逻辑。
const GO = process.argv.includes('--go');
const DO_AI = !process.argv.includes('--no-ai');
const idArgs = process.argv.slice(2).filter((a) => /^\d+$/.test(a)).map(Number);
const isSprint = (t) => /冲刺模考/.test(t);
// 章节自然排序键：全面精讲(段1) → 强化冲刺(段2) → 其它(段3)，段内按首个数字升序，避免字符串序把“精讲33”排到“精讲09”前
function chapterKey(ch) {
  const s = String(ch || '');
  const seg = /全面精讲/.test(s) ? 1 : /强化冲刺/.test(s) ? 2 : 3;
  const m = s.match(/(\d+)/);
  return seg * 1000 + (m ? Number(m[1]) : 999);
}

(async () => {
  const profile = loadProfile(argvProfileKey());
  const manifestDir = workspaceDirFor(profile.key, 'manifest');
  const papersDir = workspaceDirFor(profile.key, 'papers');
  const inv = JSON.parse(fs.readFileSync(path.join(manifestDir, 'papers_inventory.json'), 'utf8'));
  let audit = [];
  try { audit = JSON.parse(fs.readFileSync(path.join(manifestDir, 'papers_audit.json'), 'utf8')); } catch { audit = []; }
  console.log(`[profile] ${profile.key}｜inventory/audit 按 profile 读取`);
  const auditMap = new Map(audit.map((r) => [r.paperId, r]));

  let todo;
  if (idArgs.length) {
    todo = inv.filter((p) => idArgs.includes(p.paperId));
  } else {
    // audit 中非满分、且非冲刺
    todo = audit.filter((r) => r.cls !== '满分' && !isSprint(r.title))
      .map((r) => inv.find((p) => p.paperId === r.paperId)).filter(Boolean);
  }
  // 硬排除冲刺
  const blocked = todo.filter((p) => isSprint(p.title) || p.num === 48);
  if (blocked.length) { console.log('已硬排除冲刺卷:', blocked.map((p) => p.paperId)); todo = todo.filter((p) => !isSprint(p.title) && p.num !== 48); }
  todo.sort((a, b) => chapterKey(a.chapter) - chapterKey(b.chapter) || a.paperId - b.paperId);

  // 预计停留按题量保守估（含主观保底 25s），实际以 redo 平铺结果为准
  const totalDwell = todo.reduce((s, p) => s + dwellSec(p.num, true), 0);
  console.log(`待处理 ${todo.length} 张，预计纯停留 ${totalDwell}s ≈ ${Math.ceil(totalDwell / 60)} 分钟（主观卷另含逐题 AI 批改，约 5-15s/题）；模式=${GO ? '实跑 --go' : 'DRY-RUN（不提交）'}，AI批改=${DO_AI ? '开' : '关'}`);
  todo.forEach((p, i) => { const a = auditMap.get(p.paperId);
    console.log(` ${String(i + 1).padStart(2)}. ${p.paperId} [${p.num}题 停${dwellSec(p.num, true)}s] 上次=${a ? a.score + '/' + a.total + ' ' + a.cls : '?'} 《${p.title}》`); });
  if (!GO) { console.log('\n[dry-run] 确认无误后加 --go 实跑。'); process.exit(0); }

  let jwt = findJwt();
  const results = [];
  for (let idx = 0; idx < todo.length; idx += 1) {
    const p = todo[idx];
    const rec = { paperId: p.paperId, title: p.title, num: p.num };
    const dbg = [];
    // token 失效自动刷新重试：最多刷新2次（同一试卷最多尝试3轮）
    let tokenRefreshed = 0;
    let done = false;
    while (!done) {
      try {
        const out = await doPaperViaApi({
          target: { paperId: p.paperId, csItemId: p.csItemId, resourceId: p.resourceId, title: p.title, num: p.num },
          jwt, doAi: DO_AI, log: (m) => dbg.push(m),
        });
        rec.submitted = out.submitted;
        rec.logId = out.logId;
        rec.score = out.userScore; rec.total = out.totalScore;
        rec.ai = `${out.aiFull}/${out.aiTotal}`;
        rec.aiPartial = out.aiPartial; rec.aiFailed = out.aiFailed;
        rec.aiUnsupported = out.aiUnsupported; rec.aiCeiling = out.aiCeiling;
        rec.fullScore = out.fullScore; rec.platformDone = out.platformDone;
        rec.wrong = out.wrong; rec.error = out.error;
        // 成功完成 = 严格满分，或平台最优（客观全对+可AI题判满/判分上限，未配AI与AI判分上限题不阻断）
        rec.ok = out.fullScore || out.platformDone;
        const pdNote = out.aiCeiling.length
          ? `${out.aiUnsupported.length}题未配AI/${out.aiCeiling.length}题AI判分上限`
          : `${out.aiUnsupported.length}题未配AI`;
        const tag = out.fullScore ? '✅满分'
          : out.platformDone ? `🟡平台最优(${pdNote})`
            : (out.submitted ? '⏺已交卷/未满分' : '❌未交卷');
        console.log(`[${idx + 1}/${todo.length}] ${p.paperId} -> ${out.userScore}/${out.totalScore} AI${out.aiFull}/${out.aiTotal} ${tag} 《${p.title}》`);
        if (!out.fullScore) dbg.forEach((m) => console.log('     ' + m));
        done = true;
      } catch (e) {
        const isTokenExpired = e.message && tokenGuard.isTokenExpired(e.message);
        if (isTokenExpired && tokenRefreshed < 2) {
          tokenRefreshed += 1;
          console.log(`[${idx + 1}/${todo.length}] ${p.paperId} token失效，第${tokenRefreshed}次自动刷新后重试...`);
          try { jwt = await tokenGuard.refreshJwtWithLock({ log: (m) => console.log('  ' + m) }); } catch (refreshErr) {
            console.log(`  [token] 自动刷新失败: ${refreshErr.message}`);
            rec.ok = false; rec.error = e.message;
            console.log(`[${idx + 1}/${todo.length}] ${p.paperId} -> ❌异常 ${e.message}`);
            done = true;
          }
          continue;  // 用新 token 重试同一试卷
        }
        rec.ok = false; rec.error = e.message;
        console.log(`[${idx + 1}/${todo.length}] ${p.paperId} -> ❌异常 ${e.message}`);
        done = true;
      }
    }
    results.push(rec);
    fs.writeFileSync(path.join(papersDir, `batch_result_${new Date().toISOString().slice(0, 10)}.json`), JSON.stringify(results, null, 1));
    if (idx < todo.length - 1) await sleep(4000);
  }
  const full = results.filter((r) => r.fullScore).length;
  const platform = results.filter((r) => !r.fullScore && r.platformDone).length;
  const submitted = results.filter((r) => r.submitted).length;
  const done = results.filter((r) => r.ok).length;
  console.log(`\n===== 批量完成：严格满分 ${full}，平台最优 ${platform}，合计达成 ${done}/${results.length}；已交卷 ${submitted}/${results.length} =====`);
  results.filter((r) => !r.ok).forEach((r) => console.log('  未达成:', r.paperId, r.error || (`${r.score}/${r.total} AI${r.ai} ${JSON.stringify(r.aiFailed || [])}`)));
  process.exit(done === results.length ? 0 : 4);
})().catch((e) => { console.error('[batch FAIL]', e.stack || e.message); process.exit(1); });
