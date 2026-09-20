#!/usr/bin/env node
/**
 * ep3_course_outline.js — 拉取 ep3（epiphany 名师专业课, saasCourseType=13）单课的
 * 「26 考季梯度 → 章节树 → 讲义清单」基线 manifest（纯只读 GET，复用同一套 JWT）。
 *
 * 与正课（glive/saasType=16）区别：ep3 多「梯度(gradation)×多老师」两层，
 * 章节树优先走 student-learning/analysis/chapter（走完学习引导后含聚合计数）；
 * 未走「入门测试+选老师」引导（返回 11063019/result=null）时自动 fallback 到
 * ep-study/gradation + ep-study/syllabus（不依赖引导状态）。讲义清单走 ep-course/.../gradation/handout。
 *
 * 用法：
 *   node scripts/cdp/ep3_course_outline.js <courseId> [--all-season]
 *   默认只取「26 考季」梯度；--all-season 保留全部（含 25）。
 * 输出（账号级跨课过程件，不入库）：
 *   data/_workspace/_account/ep3/manifest/<courseId>.outline.json
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { findJwt, platformHeaders } = require('./gaodun_paper_core');

const ROOT = path.resolve(__dirname, '..', '..');
const OUT_DIR = path.join(ROOT, 'data/_workspace/_account/ep3/manifest');
const GW = 'https://apigateway.gaodun.com';

const slimChapter = (n) => ({
  id: n.id, name: n.name, itemId: n.itemId,
  totalResource: n.totalResource, videoTotal: n.videoTotal,
  paperTotal: n.paperTotal, lectureNoteTotal: n.lectureNoteTotal,
  csItemIds: Array.isArray(n.csItemIds) ? n.csItemIds : undefined,
  children: Array.isArray(n.children) ? n.children.map(slimChapter) : undefined,
});
const count = (node, key) => {
  let s = Number(node[key] || 0);
  (node.children || []).forEach((c) => { s += count(c, key); });
  return s;
};
// csItemIds 挂在中间章节点（非叶子），需递归所有层汇总
const countCs = (n) => (Array.isArray(n.csItemIds) ? n.csItemIds.length : 0)
  + (n.children || []).reduce((s, c) => s + countCs(c), 0);
const flattenLeaves = (n, acc = []) => {
  if (!n.children || !n.children.length) acc.push(n);
  else n.children.forEach((c) => flattenLeaves(c, acc));
  return acc;
};

// ---- ep-study/syllabus 树（未走学习引导时的 fallback 来源）----
// 与 analysis/chapter 不同：子节点键可能是 children 或 syllabus，叶子带 resource_id，
// 节点没有 videoTotal/paperTotal 聚合计数（精确视频数由 ep3_download_videos --list 逐资源判别）。
const epKids = (n) => [
  ...(Array.isArray(n.children) ? n.children : []),
  ...(Array.isArray(n.syllabus) ? n.syllabus : []),
];
const slimEp3 = (n) => {
  const kd = epKids(n);
  return {
    id: n.id, name: n.name,
    resourceId: n.resource_id != null ? n.resource_id : undefined,
    children: kd.length ? kd.map(slimEp3) : undefined,
  };
};
const epLeaves = (n, acc = []) => {
  const kd = epKids(n);
  if (n.resource_id != null && !kd.length) acc.push(n);
  kd.forEach((c) => epLeaves(c, acc));
  return acc;
};
const findNode = (root, id) => {
  for (const top of root) {
    let hit = null;
    (function w(n) {
      if (hit) return;
      if (String(n.id) === String(id)) { hit = n; return; }
      epKids(n).forEach(w);
    })(top);
    if (hit) return hit;
  }
  return null;
};
// 未走「入门测试+选老师」引导时，analysis/chapter 返回 11063019/result=null；
// 改用不依赖引导状态的 ep-study/gradation + ep-study/syllabus 重建 26 考季章节树。
async function buildFallbackGrads(get, cid, wantSeason) {
  const grad = await get(`/ep-study/front/course/${cid}/gradation`);
  const seasonNodes = [];
  (grad.result || []).forEach((stage) => {
    (stage.children || []).forEach((sn) => { if (wantSeason(sn.name)) seasonNodes.push(sn); });
  });
  const out = [];
  for (const sn of seasonNodes) {
    const syl = await get(`/ep-study/front/course/${cid}/syllabus?gradation_id=${sn.id}&syllabus_id=${sn.syllabus_id}`);
    const root = (syl.result && syl.result.syllabus) || [];
    const seasonNode = findNode(root, sn.id); // 定位该考季节点，其下即章节目录
    const tree = seasonNode ? epKids(seasonNode).map(slimEp3) : [];
    const leaves = tree.flatMap((t) => epLeaves(t));
    out.push({
      gradationId: Number(sn.id), syllabusId: Number(sn.syllabus_id), name: sn.name,
      syllabusName: sn.syllabus_name, attribute: Number(sn.attribute),
      chapterTree: tree, treeSource: 'ep-study-fallback',
      stats: {
        chapters: tree.length,
        leafSections: leaves.length,
        csItems: leaves.length,
        videoTotal: null, paperTotal: null, lectureNoteTotal: null, // fallback 不逐资源分类
        resourceLeaves: leaves.length,
      },
    });
  }
  return out;
}

(async () => {
  const cid = process.argv[2];
  if (!cid) { console.error('用法: node ep3_course_outline.js <courseId> [--all-season]'); process.exit(1); }
  const allSeason = process.argv.includes('--all-season');
  const H = platformHeaders(findJwt(), 'ep3');
  const get = async (p) => (await fetch(GW + p, { headers: H })).json();

  const course = await get(`/ep-course/api/v1/front/course/${cid}`);
  const courseName = course.result && course.result.courseName;
  const chapter = await get(`/student-learning/api/v1/analysis/chapter?courseId=${cid}`);
  const handout = await get(`/ep-course/api/v1/course/${cid}/gradation/handout`);

  const wantSeason = (name) => allSeason || /26\s*考季/.test(name || '');
  // 章节树：优先 analysis/chapter（走完学习引导后含 video/paper 聚合计数）；
  // 未走引导（result=null / 11063019）时 fallback 到不依赖引导的 ep-study/gradation+syllabus
  let treeSource = 'analysis-chapter';
  let grads;
  if (Array.isArray(chapter.result?.gradationSyllabuses) && chapter.result.gradationSyllabuses.length) {
    grads = chapter.result.gradationSyllabuses
      .filter((g) => wantSeason(g.name))
      .map((g) => {
        const tree = (g.syllabus || []).map(slimChapter);
        const leaves = tree.flatMap((t) => flattenLeaves(t));
        return {
          gradationId: Number(g.id), syllabusId: Number(g.syllabusId), name: g.name,
          syllabusName: g.syllabusName, attribute: g.attribute,
          chapterTree: tree,
          stats: {
            chapters: tree.length,
            leafSections: leaves.length,
            csItems: tree.reduce((s, t) => s + countCs(t), 0),
            videoTotal: tree.reduce((s, t) => s + count(t, 'videoTotal'), 0),
            paperTotal: tree.reduce((s, t) => s + count(t, 'paperTotal'), 0),
            lectureNoteTotal: tree.reduce((s, t) => s + count(t, 'lectureNoteTotal'), 0),
          },
        };
      });
  } else {
    treeSource = 'ep-study-fallback';
    grads = await buildFallbackGrads(get, cid, wantSeason);
  }

  // 讲义清单：handoutCategories[].courseHandouts[] 扁平化，只留选中梯度
  const sylSet = new Set(grads.map((g) => g.syllabusId));
  const handouts = [];
  (handout.result || [])
    .filter((g) => wantSeason(g.gradationName))
    .forEach((g) => {
      (g.handoutCategories || []).forEach((cat) => {
        (cat.courseHandouts || []).forEach((h) => {
          handouts.push({
            id: h.id, gradationId: g.gradationId, syllabusId: g.syllabusId,
            gradationName: g.gradationName, category: cat.name, teacherCategory: cat.name,
            name: h.fileName || h.name, format: h.format, fileSize: h.fileSize,
            sizeText: h.size, symlink: h.symlink,
          });
        });
      });
    });

  const manifest = {
    platform: 'ep3', saasCourseType: 13, courseId: Number(cid), courseName,
    fetchedAt: new Date().toISOString(), seasonFilter: allSeason ? 'all' : '26考季',
    // 章节/视频树依赖「学习引导」状态：未走完引导时 analysis/chapter 返回 11063019、result=null，自动改走 ep-study fallback
    guideReady: !!chapter.result, chapterCode: chapter.status, chapterMessage: chapter.message,
    treeSource,
    gradations: grads, handouts,
  };
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const out = path.join(OUT_DIR, `${cid}.outline.json`);
  fs.writeFileSync(out, JSON.stringify(manifest, null, 2));

  console.log(`课程: ${courseName} (${cid})，梯度${grads.length}个，讲义文件${handouts.length}个，章节树来源=${treeSource}${treeSource === 'ep-study-fallback' ? '（未走学习引导，已自动绕过）' : ''}`);
  if (!grads.length) console.log(`  ⚠️ 章节/视频学习树为空（analysis/chapter code=${chapter.status} ${chapter.message}；ep-study fallback 也未取到）`);
  grads.forEach((g) => {
    const ho = handouts.filter((h) => h.syllabusId === g.syllabusId).length;
    const vid = g.stats.videoTotal == null
      ? `资源叶${g.stats.resourceLeaves}(精确视频数用 ep3_download_videos --list)`
      : `视频${g.stats.videoTotal} 题${g.stats.paperTotal} 讲义节点${g.stats.lectureNoteTotal}`;
    console.log(`  ${g.name} grad=${g.gradationId} syl=${g.syllabusId} | 章${g.stats.chapters} 叶节${g.stats.leafSections} csItem${g.stats.csItems} ${vid} 讲义文件${ho}`);
  });
  const byFmt = {}; handouts.forEach((h) => { byFmt[h.format] = (byFmt[h.format] || 0) + 1; });
  console.log('讲义格式分布:', byFmt);
  console.log('已写:', path.relative(ROOT, out));
})().catch((e) => { console.error('[OUTLINE-FAIL]', e.stack || e.message); process.exit(1); });
