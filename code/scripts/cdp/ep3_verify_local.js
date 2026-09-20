#!/usr/bin/env node
/**
 * ep3_verify_local.js — 名师课六科「本地成品」离线完整性核对（零网络、零风控）
 *
 * 为什么需要它：
 *   - 下载是「1 生产者 + 多消费者」长跑、断点续跑，过程中会留下进行态条目、中断残留，
 *     靠手工 find 无法稳定区分「正常待下 / 残缺异常 / 中断残留 / 老师独有讲」。
 *   - 「应有哪些讲、哪些老师」的权威口径在运行时在线树（enumTeacherVideos），离线拿不到，
 *     因此本脚本只做**不依赖在线清单也能确定**的内部完整性判断，不武断报「缺老师」。
 *
 * 判级（每个 <讲目录>/<老师前缀>）：
 *   - complete 完整：<老师>_video.mp4 存在且非空 且 <老师>_subtitle.vtt 存在
 *   - pending  待下：有 _meta.json / _subtitle.vtt 但还没 _video.mp4（字幕/meta 先行，下载进行或排队，正常）
 *   - anomaly  异常：_video.mp4 为 0 字节；或有 video 却缺 subtitle（平台每视频配 VTT，ADR-018）
 * 讲目录级：
 *   - stale_work 可安全清理的残留：存在 _work，且该讲已有完整成品 video（成功本应自洁，_work 必是中断残留）
 *   - active_work 活跃工作区：存在 _work 但讲内还没有成品 video（可能正在下载，--clean 也绝不动）
 *   - single_teacher 单老师讲：双老师科目的讲里只出现 1 位老师前缀（可能是老师独有讲，列「待在线核对」，不算异常）
 *
 * 用法：
 *   node scripts/cdp/ep3_verify_local.js                 # 只读报告
 *   node scripts/cdp/ep3_verify_local.js --clean         # 额外删除 stale_work（绝不删 active_work）
 *   node scripts/cdp/ep3_verify_local.js --json out.json # 同时落一份结构化结果
 *   node scripts/cdp/ep3_verify_local.js --root <课程库根>
 *
 * 退出码：存在 anomaly 返回 1（可接巡检）；pending / stale_work / single_teacher 不视为硬错误，返回 0。
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const ARGS = Object.fromEntries(process.argv.slice(2).map((a, i, arr) => {
  if (a.startsWith('--')) {
    const next = arr[i + 1];
    return [a.slice(2), (!next || next.startsWith('--')) ? true : next];
  }
  return [null, null];
}).filter(([k]) => k));

const ROOT = ARGS.root || path.join(os.homedir(), 'Desktop', '高顿', 'CPA');
const DO_CLEAN = !!ARGS.clean;
const COURSE_GLOB = /【VIPCPA专享】名师专业课-(.+)$/;
const FILE_RE = /^(.+?)_(video\.mp4|subtitle\.vtt|meta\.json|transcript\.md)$/;
const MIN_VIDEO_BYTES = 100 * 1024; // 小于 100KB 的 mp4 视为残缺

function loadSubjectTeachers() {
  // 科目中文名 → 老师名数组（用于判断单/双老师科目）；读不到则全部按未知、不做 single_teacher 判断
  const cfgPath = path.join(__dirname, '..', '..', 'config', 'ep3_subjects.json');
  const map = {};
  try {
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    for (const s of cfg.subjects || []) {
      const m = (s.description || '').match(/(会计|税法|战略|经济法|审计|财管)/);
      if (m) map[m[1]] = s.teachers || [];
    }
  } catch { /* 配置缺失不致命，只是不判 single_teacher */ }
  return map;
}

function fileSize(p) { try { return fs.statSync(p).size; } catch { return -1; } }
function isDir(p) { try { return fs.statSync(p).isDirectory(); } catch { return false; } }
function listDirs(p) { try { return fs.readdirSync(p, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name); } catch { return []; } }

function verifyCourse(courseDir, subjectName, teacherMap) {
  const videosRoot = path.join(courseDir, '原始资源', 'videos');
  const expectedTeachers = teacherMap[subjectName] || [];
  const stages = listDirs(videosRoot);
  const byStage = {};
  const anomalies = []; const staleWork = []; const activeWork = []; const singleTeacher = [];

  for (const stage of stages) {
    const st = byStage[stage] = { lessons: 0, complete: 0, pending: 0, anomaly: 0, staleWork: 0, activeWork: 0, singleTeacher: 0 };
    const stageDir = path.join(videosRoot, stage);
    for (const lesson of listDirs(stageDir)) {
      const lessonDir = path.join(stageDir, lesson);
      st.lessons += 1;
      const files = fs.readdirSync(lessonDir, { withFileTypes: true });
      const teachers = new Map(); // teacher -> {video,vtt,meta,transcript,videoBytes}
      for (const f of files) {
        if (f.isDirectory()) continue;
        const mm = f.name.match(FILE_RE);
        if (!mm) continue;
        const [, t, kind] = mm;
        if (!teachers.has(t)) teachers.set(t, { video: false, vtt: false, meta: false, transcript: false, videoBytes: 0 });
        const rec = teachers.get(t);
        if (kind === 'video.mp4') { rec.video = true; rec.videoBytes = fileSize(path.join(lessonDir, f.name)); }
        else if (kind === 'subtitle.vtt') rec.vtt = true;
        else if (kind === 'meta.json') rec.meta = true;
        else if (kind === 'transcript.md') rec.transcript = true;
      }

      // _work：成品已在→残留可清；无成品→活跃不动
      const workDir = path.join(lessonDir, '_work');
      if (isDir(workDir)) {
        const hasCompleteVideo = [...teachers.values()].some((r) => r.video && r.videoBytes >= MIN_VIDEO_BYTES);
        if (hasCompleteVideo) { st.staleWork += 1; staleWork.push(path.relative(ROOT, workDir)); }
        else { st.activeWork += 1; activeWork.push(path.relative(ROOT, workDir)); }
      }

      for (const [t, r] of teachers) {
        const where = `${subjectName}/${stage}/${lesson}/${t}`;
        if (r.video && r.videoBytes < MIN_VIDEO_BYTES) { st.anomaly += 1; anomalies.push(`${where}：video 仅 ${r.videoBytes}B（疑似残缺）`); continue; }
        if (r.video && !r.vtt) { st.anomaly += 1; anomalies.push(`${where}：有视频缺 VTT 字幕`); continue; }
        if (r.video && r.vtt) { st.complete += 1; continue; }
        if (!r.video && (r.meta || r.vtt)) { st.pending += 1; }
      }

      if (expectedTeachers.length > 1 && teachers.size === 1) {
        st.singleTeacher += 1;
        singleTeacher.push(`${subjectName}/${stage}/${lesson}（仅 ${[...teachers.keys()].join('/')}，待在线核对是否独有讲）`);
      }
    }
  }
  return { subject: subjectName, expectedTeachers, byStage, anomalies, staleWork, activeWork, singleTeacher };
}

function main() {
  const teacherMap = loadSubjectTeachers();
  const courses = listDirs(ROOT).filter((n) => COURSE_GLOB.test(n)).sort();
  if (!courses.length) { console.error(`未在 ${ROOT} 找到名师课目录`); process.exit(2); }
  const results = [];
  for (const c of courses) {
    const subject = c.match(COURSE_GLOB)[1];
    results.push(verifyCourse(path.join(ROOT, c), subject, teacherMap));
  }

  // 汇总
  console.log('名师课本地成品完整性（离线，不触网）  ' + new Date().toLocaleString('zh-CN') + (DO_CLEAN ? '  [--clean 已清理安全残留]' : ''));
  console.log('='.repeat(96));
  for (const r of results) {
    const tot = { lessons: 0, complete: 0, pending: 0, anomaly: 0, staleWork: 0, activeWork: 0, singleTeacher: 0 };
    for (const st of Object.values(r.byStage)) for (const k of Object.keys(tot)) tot[k] += st[k] || 0;
    console.log(`\n■ ${r.subject}（配置老师：${r.expectedTeachers.join('、') || '未知'}）`);
    console.log('  阶段'.padEnd(10) + '讲目录'.padStart(6) + '完整视频'.padStart(8) + '待下'.padStart(6) + '异常'.padStart(6) + '可清_work'.padStart(9) + '活跃_work'.padStart(9) + '单老师讲'.padStart(8));
    for (const [stage, st] of Object.entries(r.byStage)) {
      console.log(stage.padEnd(12) + String(st.lessons).padStart(6) + String(st.complete).padStart(8) + String(st.pending).padStart(6)
        + String(st.anomaly).padStart(6) + String(st.staleWork).padStart(9) + String(st.activeWork).padStart(9) + String(st.singleTeacher).padStart(8));
    }
    console.log('  合计'.padEnd(12) + String(tot.lessons).padStart(6) + String(tot.complete).padStart(8) + String(tot.pending).padStart(6)
      + String(tot.anomaly).padStart(6) + String(tot.staleWork).padStart(9) + String(tot.activeWork).padStart(9) + String(tot.singleTeacher).padStart(8));
  }

  // 明细
  const allAnomaly = results.flatMap((r) => r.anomalies);
  const allStale = results.flatMap((r) => r.staleWork);
  const allActive = results.flatMap((r) => r.activeWork);
  const allSingle = results.flatMap((r) => r.singleTeacher);
  console.log('\n' + '='.repeat(96));
  console.log(`❌ 异常 ${allAnomaly.length}：`); allAnomaly.slice(0, 50).forEach((x) => console.log('   ' + x));
  if (allAnomaly.length > 50) console.log(`   …其余 ${allAnomaly.length - 50} 条见 --json`);
  console.log(`\n🧹 可安全清理的 _work 残留 ${allStale.length}（成品视频已在）；活跃 _work ${allActive.length}（下载中，绝不清理）`);
  allStale.slice(0, 10).forEach((x) => console.log('   残留: ' + x));
  console.log(`\n🔎 单老师讲 ${allSingle.length}（双老师科目仅见 1 位老师，可能为独有讲，最终以在线清单核对，不算异常）`);
  allSingle.slice(0, 15).forEach((x) => console.log('   ' + x));
  if (allSingle.length > 15) console.log(`   …其余 ${allSingle.length - 15} 条见 --json`);

  // 安全清理
  let cleaned = 0;
  if (DO_CLEAN && allStale.length) {
    for (const rel of allStale) {
      const abs = path.join(ROOT, rel);
      try { fs.rmSync(abs, { recursive: true, force: true }); cleaned += 1; } catch (e) { console.log('   清理失败(跳过): ' + rel + ' ' + e.message); }
    }
    console.log(`\n已清理安全残留 _work：${cleaned}/${allStale.length}（活跃 _work 全部保留）`);
  }

  if (ARGS.json) fs.writeFileSync(ARGS.json, JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2));
  process.exit(allAnomaly.length ? 1 : 0);
}

main();
