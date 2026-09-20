#!/usr/bin/env node
/**
 * collect_user_notes.js — 批量采集高顿题库所有题目的用户公开笔记
 *
 * 流程：
 *   1. 遍历 papers/ 目录所有试卷 JSON，收集所有 questionId（含子题），去重
 *   2. 对每个 questionId 调用 GET /minerva/api/v1/front/note/question
 *   3. 收集所有非空笔记，按 questionId 分组保存
 *   4. 输出统计和增量文件
 *
 * 用法：node scripts/cdp/collect_user_notes.js [--profile <key>] [--concurrency N] [--resume]
 *   --profile <key>  课程档案卡，缺省 cpa-tax-2026（或环境变量 GAODUN_COURSE_PROFILE）
 *   --concurrency N  并发数，默认 5
 *   --resume         断点续传，跳过已采集的 questionId
 *
 * 输入：<profile 课程>/原始资源/papers；输出按课程 key 隔离（env USER_NOTES_RAW_DIR 可覆盖，
 *   与 knowledge/organize_user_notes.py 对齐）：
 *   data/_workspace/<key>/notes-raw/all_notes.jsonl   所有笔记（JSONL，每行一条笔记）
 *   data/_workspace/<key>/notes-raw/progress.json     采集进度（已采集的 questionId 集合）
 *   data/_workspace/<key>/notes-raw/stats.json        统计信息
 */
'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');
const { findJwt, makeHeaders, MINERVA_BASE } = require('./gaodun_paper_core');
const { loadProfile, workspaceDirFor } = require('./load_profile');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const _argv = process.argv.slice(2);
function namedArg(name) {
  const i = _argv.indexOf(`--${name}`);
  if (i >= 0 && _argv[i + 1]) return _argv[i + 1];
  const e = _argv.find((a) => a.startsWith(`--${name}=`));
  return e ? e.slice(name.length + 3) : undefined;
}
const profile = loadProfile(namedArg('profile'));
// 输入：该 profile 课程的 papers 原料；输出按课程 key 隔离，避免不同课的题目/进度混在一起
const PAPERS_DIR = path.join(PROJECT_ROOT, profile.paths.localRoot, '原始资源', 'papers');
const OUT_DIR = process.env.USER_NOTES_RAW_DIR
  || workspaceDirFor(profile.key, 'notes-raw');
const NOTES_FILE = path.join(OUT_DIR, 'all_notes.jsonl');
const PROGRESS_FILE = path.join(OUT_DIR, 'progress.json');
const STATS_FILE = path.join(OUT_DIR, 'stats.json');

fs.mkdirSync(OUT_DIR, { recursive: true });

const args = _argv;
const concurrency = Number(namedArg('concurrency')) || 5;
const resume = args.includes('--resume');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// 收集所有 questionId
function collectAllQuestionIds() {
  const qids = new Set();
  const qidToPaper = {};
  const files = fs.readdirSync(PAPERS_DIR).filter(f => f.endsWith('.json'));

  for (const f of files) {
    const paper = JSON.parse(fs.readFileSync(path.join(PAPERS_DIR, f), 'utf8'));
    const paperId = paper.paperId;
    const paperTitle = paper.title || '';

    for (const mod of paper.moduleList || []) {
      for (const q of mod.questionList || []) {
        if (q.questionId) {
          qids.add(q.questionId);
          if (!qidToPaper[q.questionId]) qidToPaper[q.questionId] = [];
          qidToPaper[q.questionId].push({ paperId, paperTitle, type: 'main' });
        }
        for (const sub of q.subQuestionList || []) {
          if (sub.questionId) {
            qids.add(sub.questionId);
            if (!qidToPaper[sub.questionId]) qidToPaper[sub.questionId] = [];
            qidToPaper[sub.questionId].push({ paperId, paperTitle, type: 'sub' });
          }
        }
      }
    }
  }
  return { qids: [...qids], qidToPaper };
}

// 调用 API 获取单题笔记
function fetchNote(qid, headers) {
  return new Promise((resolve) => {
    const url = `${MINERVA_BASE}/note/question?questionId=${qid}`;
    const req = https.get(url, { headers, timeout: 15000 }, (res) => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try {
          const data = JSON.parse(body);
          resolve({ qid, status: res.statusCode, notes: data.result || [], error: null });
        } catch (e) {
          resolve({ qid, status: res.statusCode, notes: [], error: `parse: ${e.message}` });
        }
      });
    });
    req.on('error', e => resolve({ qid, status: 0, notes: [], error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ qid, status: 0, notes: [], error: 'timeout' }); });
  });
}

async function main() {
  console.log('=== 高顿题库用户笔记批量采集 ===');
  console.log(`课程profile: ${profile.key}（${profile.subject.name}）`);
  console.log(`Papers目录: ${PAPERS_DIR}`);
  console.log(`输出目录: ${OUT_DIR}`);
  console.log(`并发数: ${concurrency}, 断点续传: ${resume}`);

  // 收集 questionId
  const { qids, qidToPaper } = collectAllQuestionIds();
  console.log(`\n试卷: ${fs.readdirSync(PAPERS_DIR).filter(f => f.endsWith('.json')).length} 份`);
  console.log(`去重 questionId: ${qids.length} 个`);

  // 加载进度
  let done = new Set();
  if (resume && fs.existsSync(PROGRESS_FILE)) {
    done = new Set(JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8')));
    console.log(`已采集(断点): ${done.size} 个`);
  }
  const todo = qids.filter(id => !done.has(id));
  console.log(`待采集: ${todo.length} 个`);

  if (todo.length === 0) {
    console.log('全部已采集，无需重复。');
    return;
  }

  // 获取 JWT
  const jwt = findJwt();
  const headers = makeHeaders(jwt);
  console.log(`JWT长度: ${jwt.length}`);

  // 打开输出文件（追加模式）
  const outStream = fs.createWriteStream(NOTES_FILE, { flags: resume ? 'a' : 'w' });

  // 并发采集
  let index = 0;
  let success = 0, failed = 0, withNotes = 0, totalNotes = 0;
  const failures = [];
  const startTime = Date.now();

  async function worker(id) {
    while (index < todo.length) {
      const myIndex = index++;
      const qid = todo[myIndex];

      const result = await fetchNote(qid, headers);

      if (result.error) {
        failed++;
        failures.push({ qid, error: result.error });
        console.log(`  [worker${id}] ❌ q${qid}: ${result.error}`);
      } else {
        success++;
        done.add(qid);
        if (result.notes.length > 0) {
          withNotes++;
          totalNotes += result.notes.length;
          // 写入每条笔记
          for (const note of result.notes) {
            outStream.write(JSON.stringify({
              questionId: qid,
              papers: qidToPaper[qid] || [],
              ...note,
            }) + '\n');
          }
        }
      }

      // 每 50 个保存一次进度
      if (myIndex % 50 === 0) {
        fs.writeFileSync(PROGRESS_FILE, JSON.stringify([...done]));
        const elapsed = (Date.now() - startTime) / 1000;
        const rate = myIndex / elapsed;
        const eta = (todo.length - myIndex) / rate;
        console.log(`  进度: ${myIndex}/${todo.length} (${(myIndex/todo.length*100).toFixed(1)}%), ` +
          `成功=${success}, 失败=${failed}, 有笔记=${withNotes}, 笔记总数=${totalNotes}, ` +
          `速度=${rate.toFixed(1)}/s, ETA=${eta.toFixed(0)}s`);
      }

      // 轻微限流
      await sleep(50);
    }
  }

  // 启动并发 worker
  const workers = [];
  for (let i = 0; i < concurrency; i++) {
    workers.push(worker(i));
  }
  await Promise.all(workers);

  outStream.end();
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify([...done]));

  // 统计
  const elapsed = (Date.now() - startTime) / 1000;
  const stats = {
    totalQuestionIds: qids.length,
    collected: success,
    failed,
    withNotes,
    totalNotes,
    elapsedSec: elapsed,
    rate: success / elapsed,
    failures: failures.slice(0, 50),
    collectedAt: new Date().toISOString(),
  };
  fs.writeFileSync(STATS_FILE, JSON.stringify(stats, null, 2));

  console.log('\n=== 采集完成 ===');
  console.log(`总 questionId: ${qids.length}`);
  console.log(`成功: ${success}, 失败: ${failed}`);
  console.log(`有笔记的题目: ${withNotes} (${(withNotes/success*100).toFixed(1)}%)`);
  console.log(`笔记总数: ${totalNotes}`);
  console.log(`耗时: ${elapsed.toFixed(1)}s, 速度: ${(success/elapsed).toFixed(1)}/s`);
  console.log(`输出: ${NOTES_FILE}`);
  console.log(`统计: ${STATS_FILE}`);
}

main().catch(e => {
  console.error('采集失败:', e);
  process.exit(1);
});
