#!/usr/bin/env node
/**
 * ep3_download_videos.js — 名师专业课（ep3/epiphany，saasCourseType=13）视频采集薄编排
 *
 * 链路（全部机制已端到端验证，见 ADR-018 / video-processing.md ep3 小节）：
 *   syllabus 树递归枚举讲次
 *     → getVideoInfo(resourceId) 拿 video_id / teacher / discriminator（非 video 跳过）
 *     → glive2-vod live/resource?res=FHD 拿 m3u8 + subtitle(VTT) + duration
 *     → capture_video_key.js（CDP 复用日常 Chrome 播放页，gp.play()+切1080P）拿 FHD keyAscii（按 videoId:res 缓存）
 *     → download_decrypt.js（HLS 分片下载 + AES-128-CBC 解密 + 合并 ts）
 *     → ffmpeg -c copy 转 mp4
 *     → 下载平台 VTT 原始稿 subtitle.vtt，并转 transcript.md（替代 FunASR；平台自带字幕）
 *
 * 设计原则：薄编排，不重复实现取 key / 下载解密（复用既有脚本）；断点续跑；单讲失败不中断批量。
 *
 * 用法：
 *   # 1) 枚举某 syllabus 下全部视频讲次（不下载）
 *   node ep3_download_videos.js --course 17244 --parent-grad 23408 --grad 62676 --syllabus 57580 --list
 *
 *   # 2) 下载单个讲次（直接给播放页 URL，最稳，用于试点）
 *   node ep3_download_videos.js --learning-url "<ep3 learning url>" --out data/_workspace/_account/ep3/downloads/17244
 *
 *   # 3) 批量下载整个 syllabus（递归枚举 + 逐个下载，断点续跑）
 *   node ep3_download_videos.js --course 17244 --parent-grad 23408 --grad 62676 --syllabus 57580 \
 *        --out <dir> [--res FHD] [--limit N] [--concurrency 16] [--dual-teacher]
 *
 *   # 4) 生产者-消费者模型（生产端：只预取key不下载）
 *   node ep3_download_videos.js --profile ep3-accounting-2026 --stage 基础必修 --dual-teacher \
 *        --global-key-cache data/_workspace/_account/ep3/global_keycache.json --prefetch-only
 *
 *   # 5) 生产者-消费者模型（消费端：只从全局缓存读key下载，不主动取key）
 *   node ep3_download_videos.js --profile ep3-accounting-2026 --stage 基础必修 --dual-teacher \
 *        --global-key-cache data/_workspace/_account/ep3/global_keycache.json --consumer
 *
 * 注意：取 key 依赖日常 Chrome 已登录且可播放 ep3（CDP 复用登录态，绝不用自带浏览器）。
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const core = require('./gaodun_paper_core');
const tokenGuard = require('./auth_token_guard');

const GATEWAY = 'https://apigateway.gaodun.com';
const TEACHER_NAME = {
  22455: '姚远', 14178: '陈蓓蓓', 11138: '罗翔', 15038: '郁刚', 57023: '王潇粒', // 会计
  24825: '杨志国', 50070: '高蒙', // 税法名师
  15317: '吴奕', // 战略名师（陈岩宣传2套师资但26考季实际未挂视频，出现 id 再补）
  24042: '沈甜甜', 15466: '齐萌', // 经济法名师
  15251: '王依然', 15463: '陈岩', // 审计名师（26考季主老师王依然；陈岩15463挂25考季，不取）
  11134: '李晶', // 财管名师（26考季主老师李晶；另一套周越26考季未挂视频，出现 id 再补）
};
const SCRIPT_DIR = __dirname;
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..');

// ---------- 参数 ----------
function parseArgs(argv) {
  const a = {};
  for (let i = 2; i < argv.length; i += 1) {
    const k = argv[i];
    if (k.startsWith('--')) a[k.slice(2)] = (argv[i + 1] && !argv[i + 1].startsWith('--')) ? argv[++i] : true;
  }
  a.res = a.res || 'FHD';           // 默认 1080P
  // 分片并发分时段：白天 6:00-24:00 温和(12，配合最多3路消费者)防风控/留带宽，夜间 0:00-6:00 拉满(64)；显式 --concurrency 优先
  const _nightH = new Date().getHours();
  const _night = _nightH >= 0 && _nightH < 6;
  a.concurrency = parseInt(a.concurrency || (_night ? "64" : "12"), 10);
  a['global-key-cache'] = a['global-key-cache'] || '';  // 全局key缓存路径（生产者-消费者模型）
  a['prefetch-only'] = !!a['prefetch-only'];  // 生产者模式：只取key不下载
  a.consumer = !!a.consumer;  // 消费者模式：只从缓存读key，不主动取
  return a;
}
const ARGS = parseArgs(process.argv);
if (!ARGS.out && !ARGS.list && !ARGS.profile) { console.error('需要 --out <输出目录>（或 --list 仅枚举，或 --profile 自动落位）'); process.exit(2); }

function ep3Headers() {
  return core.platformHeaders(core.findJwt(), 'ep3');
}
async function apiGet(p, _attempt) {
  const attempt = _attempt || 0;
  const r = await fetch(GATEWAY + p, { headers: ep3Headers() });
  const j = await r.json();
  // token 自动续命（I-013）：本地 JWT 7 天过期返回 553649434，跨进程 single-flight 刷新后重试 1 次；
  // 统一在此拦截，fetchSyllabus/getVideoInfo/getLiveResource 全部覆盖，生产者/消费者都受益。
  if (tokenGuard.isTokenExpired(j.status) && attempt < 1) {
    log(`[token] ${j.status} 登录超时，自动刷新后重试：${p.slice(0, 70)}`);
    await tokenGuard.refreshJwtWithLock({ log });
    return apiGet(p, attempt + 1);
  }
  return j;
}
const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
function log(...x) { console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...x); }

// ---------- 1. syllabus 树递归，收集视频讲次叶子 ----------
async function fetchSyllabus(cid, grad, syllabus, teacherId) {
  // teacherId 不传=默认折叠树（按主老师折叠，会漏其它老师整套）；B 方案双老师必须逐 teacher_id 各拉一套
  const tq = teacherId ? `&teacher_id=${teacherId}` : '';
  const r = await apiGet(`/ep-study/front/course/${cid}/syllabus?gradation_id=${grad}&syllabus_id=${syllabus}${tq}`);
  if (r.status !== 0) throw new Error(`syllabus 接口失败 status=${r.status} ${r.info || r.message || ''}`);
  return r.result;
}

// 简单并发池：并发 n 路对 items 调 fn，返回等序结果（单项失败落 {_err}，不中断整体）
async function poolMap(items, n, fn) {
  const out = new Array(items.length);
  let i = 0;
  const worker = async () => {
    while (i < items.length) { const k = i++; try { out[k] = await fn(items[k], k); } catch (e) { out[k] = { _err: e.message }; } }
  };
  await Promise.all(Array.from({ length: n }, worker));
  return out;
}

// 老师名字 → id（profile.teachers 存名字，接口要 id）；--teacher-ids 可直接覆盖
const TEACHER_ID_BY_NAME = Object.fromEntries(Object.entries(TEACHER_NAME).map(([id, name]) => [name, Number(id)]));
function resolveTeacherIds(profile) {
  if (ARGS['teacher-ids']) return String(ARGS['teacher-ids']).split(',').map((s) => Number(s.trim())).filter(Boolean);
  const names = (profile && profile.teachers) || [];
  const ids = names.map((nm) => TEACHER_ID_BY_NAME[nm]).filter(Boolean);
  return ids;
}

// 拉某老师在该梯度的「视频叶子」：带 teacher_id 拉树 → 并发 getVideoInfo 判视频，info 挂回 leaf（下载时复用，不重复请求）
async function enumTeacherVideos(cid, grad, syllabus, teacherId) {
  const result = await fetchSyllabus(cid, grad, syllabus, teacherId);
  const gn = locateGradTree(result, grad);
  if (!gn) throw new Error(`teacher_id=${teacherId} 未找到 gradation 节点 ${grad}`);
  const parentGrad = findParentGrad(result, grad) || grad;
  const leaves = leavesOfGrad(gn);
  leaves.forEach((l, i) => { l.seq = i + 1; });
  await poolMap(leaves, 12, async (l) => { l.info = await getVideoInfo(cid, l.csItemId, syllabus, l.resourceId); });
  const videos = leaves.filter((l) => !l._err && l.info && l.info.discriminator === 'video' && l.info.video_id);
  return { teacherId, parentGrad, videos };
}

// 多老师视频按 chapterPath 归并成统一讲目录：同章节路径=同一讲（姚/陈落同一目录、文件名前缀区分），
// 老师独有讲各自成目录。目录序号以第一套老师（profile.teachers 顺序，通常主老师）树序为锚、其它老师独有讲按其树序插入。
// 返回任务数组 [{dirSeq, teacherId, leaf(已挂 info/dirSeq)}]，并附统计。
function buildDualTasks(perTeacher) {
  const pathOrder = new Map(); // chapterPath -> 排序锚点（首见老师的树序）
  const grouped = new Map();   // chapterPath -> [{teacherId, leaf}]
  perTeacher.forEach(({ teacherId, videos }) => videos.forEach((leaf) => {
    const p = leaf.chapterPath;
    if (!pathOrder.has(p)) pathOrder.set(p, leaf.seq);
    if (!grouped.has(p)) grouped.set(p, []);
    grouped.get(p).push({ teacherId, leaf });
  }));
  const paths = [...pathOrder.keys()].sort((a, b) => pathOrder.get(a) - pathOrder.get(b));
  const tasks = [];
  paths.forEach((p, idx) => {
    const dirSeq = idx + 1;
    grouped.get(p).forEach(({ teacherId, leaf }) => { leaf.dirSeq = dirSeq; tasks.push({ dirSeq, teacherId, leaf }); });
  });
  return { tasks, dirCount: paths.length };
}

// 在某顶层阶段里找到 grad 节点（可能在顶层或其 children），返回它的章节树（g.syllabus 或递归 children）
function locateGradTree(result, gradId) {
  const stages = result.syllabus || [];
  for (const st of stages) {
    if (String(st.id) === String(gradId)) return st;
    if (Array.isArray(st.children)) {
      for (const c of st.children) if (String(c.id) === String(gradId)) return c;
    }
  }
  return null;
}

// 子树是否含某 id（children / syllabus 两种挂载都递归）
function subtreeHasId(node, id) {
  if (String(node.id) === String(id)) return true;
  for (const key of ['children', 'syllabus']) {
    if (Array.isArray(node[key]) && node[key].some((c) => subtreeHasId(c, id))) return true;
  }
  return false;
}
// 找包含 gradId 的顶层阶段 id（= learning URL 的 parentGrad 段：基础必修21348/精讲23408/强化26320/冲刺27295）
function findParentGrad(result, gradId) {
  for (const st of (result.syllabus || [])) if (subtreeHasId(st, gradId)) return st.id;
  return null;
}

// 递归：把树里所有"带 resource_id 的讲次叶子"收集起来，同时记录章路径与顶层 chapterId
function collectLeaves(node, ctx, acc) {
  const myCtx = { ...ctx };
  // 顶层"章"节点：带 cs_item_ids / video_total，记录其 id 作为 learning URL 的 chapterId
  const isChapter = Array.isArray(node.cs_item_ids) || (node.video_total !== undefined && (!ctx.chapterId));
  if (isChapter && !ctx.chapterId) myCtx.chapterId = node.id;
  myCtx.path = ctx.path ? `${ctx.path}/${node.name}` : node.name;

  if (node.resource_id != null && (!Array.isArray(node.children) || node.children.length === 0)) {
    acc.push({
      csItemId: node.id,
      resourceId: node.resource_id,
      chapterId: myCtx.chapterId,
      name: node.name,
      chapterPath: myCtx.path,
    });
  }
  if (Array.isArray(node.children)) node.children.forEach((c) => collectLeaves(c, myCtx, acc));
  // g.syllabus 是另一种存章节树的字段
  if (Array.isArray(node.syllabus)) node.syllabus.forEach((c) => collectLeaves(c, myCtx, acc));
  return acc;
}

// grad 节点的章节树可能挂在 .syllabus（25/26 全面精讲）或 .children（基础必修）
function leavesOfGrad(gradNode) {
  const acc = [];
  const roots = Array.isArray(gradNode.syllabus) ? gradNode.syllabus
    : Array.isArray(gradNode.children) ? gradNode.children : [];
  roots.forEach((n) => collectLeaves(n, { chapterId: null, path: '' }, acc));
  return acc;
}

// ---------- 2. getVideoInfo：resourceId → video_id / teacher / 类型 ----------
async function getVideoInfo(cid, csItemId, syllabusId, resourceId) {
  const p = `/ep-study/api/v1/front/resource/${resourceId}`
    + `?courseId=${cid}&csItemId=${csItemId}&syllabusId=${syllabusId}&is_show_live=0&isRelatedResource=1`;
  const r = await apiGet(p);
  if (r.status !== 0) throw new Error(`getVideoInfo ${resourceId} status=${r.status}`);
  return r.result && r.result.resource;
}

// ---------- 3. live/resource：videoId → m3u8 / subtitle / duration ----------
async function getLiveResource(videoId, res) {
  const r = await apiGet(`/glive2-vod/api/v1/live/resource?code=${videoId}&res=${res}&lang=zh`);
  if (r.status !== 200 && r.status !== 0) throw new Error(`live/resource ${videoId} status=${r.status} ${r.message || ''}`);
  const item = r.result.list && r.result.list[res];
  if (!item || !item.available) throw new Error(`清晰度 ${res} 不可用: ${videoId}`);
  return { m3u8Url: item.path, subtitleUrl: r.result.subtitle || null, duration: r.result.duration || 0, transcodeId: item.transcode_id };
}

// ---------- 4. 取 key（复用 capture_video_key.js，带缓存） ----------
function captureKey(learningUrl, cache, cachePath) {
  const tmpOut = path.join(cache._work, `cap_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.json`);
  execFileSync('node', [path.join(SCRIPT_DIR, 'capture_video_key.js'), learningUrl, tmpOut], { stdio: ['ignore', 'ignore', 'inherit'], timeout: 120000 });
  const arr = JSON.parse(fs.readFileSync(tmpOut, 'utf8'));
  fs.rmSync(tmpOut, { force: true });
  const byQ = {};
  for (const s of arr) byQ[s.quality.startsWith('FHD') ? 'FHD' : 'SD'] = s;
  return byQ;
}

// ---------- 5. 下载 m3u8 + 解密 + ffmpeg（复用 download_decrypt.js） ----------
function downloadHttp(url, outFile, headers) {
  // 用 curl 落盘（支持重定向、稳定）
  const args = ['-sL', '--fail', '-o', outFile];
  if (headers) Object.entries(headers).forEach(([k, v]) => { args.push('-H', `${k}: ${v}`); });
  args.push(url);
  execFileSync('curl', args, { timeout: 300000 });
}
function decryptToMp4(m3u8Url, keyAscii, outMp4, workDir, concurrency) {
  fs.mkdirSync(workDir, { recursive: true });
  const m3u8File = path.join(workDir, 'index.m3u8');
  const tsFile = path.join(workDir, 'out.ts');
  const segDir = path.join(workDir, 'segs');
  downloadHttp(m3u8Url, m3u8File);
  const m3u8 = fs.readFileSync(m3u8File, 'utf8');
  const ivM = m3u8.match(/IV=0x([0-9a-fA-F]+)/);
  if (!ivM) throw new Error('m3u8 中未找到 IV');
  const ivHex = ivM[1];
  fs.rmSync(segDir, { recursive: true, force: true });
  execFileSync('node', [path.join(REPO_ROOT, 'scripts', 'download_decrypt.js'), m3u8File, tsFile, segDir, keyAscii, ivHex, String(concurrency)], { stdio: ['ignore', 'inherit', 'inherit'], timeout: 1800000 });
  execFileSync('ffmpeg', ['-y', '-i', tsFile, '-c', 'copy', outMp4], { stdio: ['ignore', 'ignore', 'ignore'], timeout: 600000 });
  fs.rmSync(segDir, { recursive: true, force: true });
  fs.rmSync(tsFile, { force: true });
  fs.rmSync(m3u8File, { force: true });
  return ivHex;
}

// ---------- 6. VTT → transcript.md（对齐正课格式：# video / 元信息 / ## 第N段） ----------
function parseVtt(text) {
  const cues = [];
  const blocks = text.replace(/^WEBVTT.*\n/, '').split(/\n\s*\n/);
  for (const b of blocks) {
    const lines = b.split('\n').map((l) => l.trim()).filter(Boolean);
    if (!lines.length) continue;
    const tl = lines.findIndex((l) => l.includes('-->'));
    if (tl < 0) continue;
    const tm = lines[tl].match(/(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})/);
    if (!tm) continue;
    const toSec = (h, m, s) => parseInt(h, 10) * 3600 + parseInt(m, 10) * 60 + parseInt(s, 10);
    const start = toSec(tm[1], tm[2], tm[3]);
    const t = lines.slice(tl + 1).join('').replace(/<[^>]+>/g, '').trim();
    if (t) cues.push({ start, text: t });
  }
  return cues;
}
function vttToTranscript(vttText, durationSec, sourceLabel) {
  const cues = parseVtt(vttText);
  // 相邻去重（滚动字幕可能重复上一句）
  const uniq = [];
  for (const c of cues) {
    const prev = uniq[uniq.length - 1];
    if (prev && prev.text === c.text) continue;
    uniq.push(c);
  }
  // 聚合成饱满段落（对齐正课 FunASR 大段风格，目标 200–400 字/段）：
  //  - 达 200 字且当前 cue 以句末标点结尾 → 断段
  //  - 达 400 字 → 强制断段（即使无标点）
  //  - 停顿 >4s 且当前段已 ≥120 字 → 断段（话题切换）
  const paras = [];
  let buf = ''; let prevStart = null;
  const flush = () => { if (buf.trim()) paras.push(buf.trim()); buf = ''; };
  const SENT_END = /[。？!?；;]$/;
  for (const c of uniq) {
    const gap = prevStart == null ? 0 : c.start - prevStart;
    if (buf && gap > 4 && buf.length >= 120) flush();
    buf += c.text;
    if ((buf.length >= 200 && SENT_END.test(c.text)) || buf.length >= 400) flush();
    prevStart = c.start;
  }
  flush();
  const totalChars = uniq.reduce((n, c) => n + c.text.length, 0);
  const mm = Math.round((durationSec || 0) / 60);
  const durLabel = durationSec ? `${(durationSec / 3600).toFixed(1)}小时` : '未知时长';
  const head = `# video\n\n> ${sourceLabel || '平台字幕(VTT)'} | 时长${mm >= 60 ? durLabel : mm + '分钟'} | 约${totalChars}字\n`;
  const body = paras.map((p, i) => `## 第${i + 1}段\n\n${p}`).join('\n\n');
  return head + '\n' + body + '\n';
}

// ---------- 单讲完整下载 ----------
function safeName(s) { return String(s).replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, '').slice(0, 60); }

async function downloadOne(leaf, ctx) {
  const { cid, parentGrad, grad, syllabus, outDir, res, concurrency, dualTeacher, keyCache, keyCachePath, isGlobal, prefetchOnly, consumer } = ctx;
  // learning URL（capture 取 key 用）
  const learningUrl = `https://epiphany.gaodun.com/ep3/course/${cid}/learning/1/${parentGrad}/${grad}/${syllabus}/${leaf.chapterId}/${leaf.csItemId}/${leaf.resourceId}/0`;

  const info = leaf.info || await getVideoInfo(cid, leaf.csItemId, syllabus, leaf.resourceId);
  if (!info || info.discriminator !== 'video' || !info.video_id) {
    return { skipped: true, reason: `非视频(${info && info.discriminator})`, name: leaf.name };
  }
  const videoId = info.video_id;
  const teacher = TEACHER_NAME[info.teacher_id] || (info.teacher_id ? `T${info.teacher_id}` : '');
  const lr = await getLiveResource(videoId, res);

  // 双老师归并时用统一目录序号 dirSeq（同讲姚/陈同目录）；单老师/单讲回退树序 seq
  const seqNo = leaf.dirSeq ?? leaf.seq;
  const dirName = `${String(seqNo).padStart(2, '0')}_${safeName(leaf.name)}`;
  const lessonDir = path.join(outDir, dirName);
  fs.mkdirSync(lessonDir, { recursive: true });
  const pfx = dualTeacher && teacher ? `${teacher}_` : '';
  const mp4 = path.join(lessonDir, `${pfx}video.mp4`);
  const vtt = path.join(lessonDir, `${pfx}subtitle.vtt`);
  const md = path.join(lessonDir, `${pfx}transcript.md`);

  // 获取/预取key
  const cacheKey = `${videoId}:${res}`;
  let streams = keyCache[cacheKey];
  let keyFetched = false;

  if (!streams || !streams[res]) {
    if (consumer) {
      // 消费者模式：缓存中没有key，等待60秒后重试，最多重试30次（总共30分钟）
      // 轮询生产者需要约27秒/个来预取key，且是轮询方式，所以需要更长的等待时间
      for (let retry = 0; retry < 30; retry += 1) {
        log(`  ⏳ 消费者等待key（${dirName}），重试 ${retry + 1}/30...`);
        await sleep(60000);
        // 重新读取缓存（生产者可能已经写入）
        if (fs.existsSync(keyCachePath)) {
          const freshCache = JSON.parse(fs.readFileSync(keyCachePath, 'utf8'));
          streams = freshCache[cacheKey];
          if (streams && streams[res]) {
            keyCache[cacheKey] = streams;
            break;
          }
        }
      }
      if (!streams || !streams[res]) {
        return { skipped: true, reason: `消费者等待key超时（${dirName}）`, name: leaf.name };
      }
    } else {
      // 生产者模式或普通模式：主动取key
      log(`  取 key（CDP 播放）: ${dirName}`);
      streams = captureKey(learningUrl, keyCache, keyCachePath);
      keyCache[cacheKey] = streams;
      saveCacheAtomic(keyCachePath, keyCache);
      keyFetched = true;
    }
  }

  // 生产者模式：只取key不下载
  if (prefetchOnly) {
    log(`  ✓ key已预取: ${dirName} (key=${streams[res] && streams[res].keyAscii})`);
    // 生产者模式也下载VTT字幕（不需要key，轻量操作）
    if (lr.subtitleUrl) {
      if (!fs.existsSync(vtt)) downloadHttp(lr.subtitleUrl, vtt);
    }
    fs.writeFileSync(path.join(lessonDir, `${pfx}meta.json`), JSON.stringify({
      videoId, transcodeId: lr.transcodeId, teacherId: info.teacher_id, teacher, res,
      durationSec: lr.duration, csItemId: leaf.csItemId, resourceId: leaf.resourceId, chapterPath: leaf.chapterPath,
      keyPrefetched: true,
    }, null, 2));
    return { ok: true, name: dirName, teacher, keyPrefetched: true, durationSec: lr.duration };
  }

  // 断点续跑：视频
  if (fs.existsSync(mp4) && fs.statSync(mp4).size > 0) {
    log(`  跳过视频(已存在 ${(fs.statSync(mp4).size / 1e6).toFixed(1)}MB): ${dirName}`);
  } else {
    const wanted = streams[res];
    if (!wanted || !wanted.keyAscii) throw new Error(`capture 未取到 ${res} key（${dirName}）`);
    // 消费者模式：key长期有效，但缓存的 m3u8 URL 里 token 会过期(403)。实时刷新 m3u8、复用缓存 key
    let m3u8Url = wanted.m3u8;
    if (consumer) {
      try {
        const fresh = await getLiveResource(videoId, res);
        m3u8Url = fresh.m3u8Url;
      } catch (e) {
        log(`  ⚠ 实时刷新m3u8失败，回退缓存URL: ${e.message}`);
      }
    }
    log(`  下载解密 ${res} key=${wanted.keyAscii}: ${dirName}`);
    decryptToMp4(m3u8Url, wanted.keyAscii, mp4, path.join(lessonDir, '_work'), concurrency);
    fs.rmSync(path.join(lessonDir, '_work'), { recursive: true, force: true });
    log(`  ✓ 视频完成: ${dirName} (${(fs.statSync(mp4).size / 1e6).toFixed(1)}MB)`);
  }

  // VTT 原始稿 + transcript（断点续跑）
  if (lr.subtitleUrl) {
    if (!fs.existsSync(vtt)) downloadHttp(lr.subtitleUrl, vtt);
    if (!fs.existsSync(md)) {
      const vttText = fs.readFileSync(vtt, 'utf8');
      fs.writeFileSync(md, vttToTranscript(vttText, lr.duration, '平台字幕(VTT，免转写)'));
    }
  } else {
    log(`  ⚠ 无字幕: ${dirName}`);
  }
  fs.writeFileSync(path.join(lessonDir, `${pfx}meta.json`), JSON.stringify({
    videoId, transcodeId: lr.transcodeId, teacherId: info.teacher_id, teacher, res,
    durationSec: lr.duration, csItemId: leaf.csItemId, resourceId: leaf.resourceId, chapterPath: leaf.chapterPath,
  }, null, 2));
  return { ok: true, name: dirName, teacher, durationSec: lr.duration };
}

function buildLearningUrlFromArg(u) {
  // /ep3/course/<cid>/learning/1/<parentGrad>/<grad>/<syllabus>/<chapter>/<csItem>/<resource>/0
  const m = u.match(/\/course\/(\d+)\/learning\/\d+\/(\d+)\/(\d+)\/(\d+)\/(\d+)\/(\d+)\/(\d+)/);
  if (!m) throw new Error(`无法解析 learning URL: ${u}`);
  return { cid: m[1], parentGrad: m[2], grad: m[3], syllabus: m[4], chapterId: m[5], csItemId: m[6], resourceId: m[7] };
}

// ---------- main ----------
function initCache(outDir, globalCachePath) {
  // 全局缓存模式：所有科目共享同一个缓存文件
  if (globalCachePath) {
    const cacheDir = path.dirname(globalCachePath);
    fs.mkdirSync(cacheDir, { recursive: true });
    const keyCachePath = globalCachePath;
    const keyCache = fs.existsSync(keyCachePath) ? JSON.parse(fs.readFileSync(keyCachePath, 'utf8')) : {};
    keyCache._work = cacheDir;
    return { cacheDir, keyCachePath, keyCache, isGlobal: true };
  }
  // 本地缓存模式：每个任务独立缓存
  fs.mkdirSync(outDir, { recursive: true });
  const cacheDir = path.join(outDir, '.ep3cache');
  fs.mkdirSync(cacheDir, { recursive: true });
  const keyCachePath = path.join(cacheDir, 'keycache.json');
  const keyCache = fs.existsSync(keyCachePath) ? JSON.parse(fs.readFileSync(keyCachePath, 'utf8')) : {};
  keyCache._work = cacheDir;
  return { cacheDir, keyCachePath, keyCache, isGlobal: false };
}

// 原子写入缓存（避免多进程同时写入冲突）
function saveCacheAtomic(keyCachePath, keyCache) {
  const tmpPath = keyCachePath + `.tmp.${process.pid}.${Date.now()}`;
  fs.writeFileSync(tmpPath, JSON.stringify(keyCache, null, 2));
  fs.renameSync(tmpPath, keyCachePath);
}

(async () => {
  // 模式 A：单讲（--learning-url）
  if (ARGS['learning-url']) {
    const outDir = ARGS.out;
    if (!outDir) { console.error('单讲模式需要 --out'); process.exit(2); }
    const { keyCache, keyCachePath, isGlobal } = initCache(outDir, ARGS['global-key-cache']);
    const p = buildLearningUrlFromArg(ARGS['learning-url']);
    const leaf = { csItemId: Number(p.csItemId), resourceId: Number(p.resourceId), chapterId: Number(p.chapterId), name: ARGS.name || 'single', seq: 0 };
    const ctx = { cid: p.cid, parentGrad: p.parentGrad, grad: p.grad, syllabus: p.syllabus, outDir, res: ARGS.res, concurrency: ARGS.concurrency, dualTeacher: !!ARGS['dual-teacher'], keyCache, keyCachePath, isGlobal, prefetchOnly: ARGS['prefetch-only'], consumer: ARGS.consumer };
    const r = await downloadOne(leaf, ctx);
    log('单讲结果:', JSON.stringify(r));
    process.exit(0);
  }

  // 模式 B/C：枚举 syllabus。参数来源：命令行手传优先（探路用），否则从 --profile 档案卡读
  const profile = ARGS.profile ? require('./load_profile').loadProfile(ARGS.profile) : null;
  const stageLabel = ARGS.stage || '';
  let cid = ARGS.course;
  let grad = ARGS.grad;
  let syllabus = ARGS.syllabus;
  if (profile) {
    cid = cid || profile.primaryCourse.saasCourseId;
    if (stageLabel && (!grad || !syllabus)) {
      const stg = (profile.stages || []).find((s) => s.label === stageLabel);
      if (!stg) { console.error(`profile 无此梯度「${stageLabel}」，可选：${(profile.stages || []).map((s) => s.label).join('/')}`); process.exit(2); }
      grad = grad || stg.gradationId; syllabus = syllabus || stg.syllabusId;
    }
  }
  if (!cid || !grad || !syllabus) {
    console.error('批量/枚举需要 --course --grad --syllabus，或用 --profile <key> --stage <梯度名>'); process.exit(2);
  }
  // 枚举讲次：双老师按 teacher_id 分拉两套、按章节路径归并到统一讲目录；单老师走默认折叠树
  let tasks = [];
  let parentGrad;
  if (ARGS['dual-teacher']) {
    const teacherIds = resolveTeacherIds(profile);
    if (!teacherIds.length) { console.error('--dual-teacher 需要 profile.teachers（老师名字）或 --teacher-ids <id,id>'); process.exit(2); }
    const perTeacher = [];
    for (const tid of teacherIds) {
      const r = await enumTeacherVideos(cid, grad, syllabus, tid);
      log(`老师 ${TEACHER_NAME[tid] || tid}：视频 ${r.videos.length} 个`);
      perTeacher.push(r); parentGrad = parentGrad || r.parentGrad;
    }
    const built = buildDualTasks(perTeacher);
    tasks = built.tasks;
    log(`双老师归并：统一讲目录 ${built.dirCount} 个，视频任务共 ${tasks.length} 个`);
    // 结构化归并计划（迁移旧目录序号 / 排查用）：dirSeq+老师+章节路径+讲名，与下载同源
    if (ARGS['dump-plan']) {
      const plan = tasks.map((t) => ({ dirSeq: t.dirSeq, teacherId: t.teacherId, teacher: TEACHER_NAME[t.teacherId] || String(t.teacherId), chapterPath: t.leaf.chapterPath, name: t.leaf.name, cs: t.leaf.csItemId, rid: t.leaf.resourceId }));
      fs.writeFileSync(ARGS['dump-plan'], JSON.stringify(plan, null, 2));
      log(`归并计划 -> ${ARGS['dump-plan']}（${plan.length} 条）`);
      process.exit(0);
    }
    if (ARGS.list) {
      perTeacher.forEach(({ teacherId, videos }) => console.log(`# ${TEACHER_NAME[teacherId] || teacherId}: ${videos.length} 视频`));
      console.log(`# 统一讲目录 ${built.dirCount} 个 / 总视频 ${tasks.length} 个`);
      tasks.forEach((t) => console.log(`${String(t.dirSeq).padStart(3)} [${TEACHER_NAME[t.teacherId] || t.teacherId}] ${t.leaf.chapterPath}`));
      process.exit(0);
    }
  } else {
    const result = await fetchSyllabus(cid, grad, syllabus);
    const gradNode = locateGradTree(result, grad);
    if (!gradNode) { console.error('未找到 gradation 节点', grad); process.exit(1); }
    // parentGrad（learning URL 必需段）：命令行优先，否则按子树归属自动定位顶层阶段
    parentGrad = findParentGrad(result, grad) || grad;
    const leaves = leavesOfGrad(gradNode);
    leaves.forEach((l, i) => { l.seq = i + 1; });
    log(`枚举到 ${leaves.length} 个讲次叶子（parentGrad=${parentGrad}）`);
    if (ARGS.list) {
      for (const l of leaves) console.log(`${String(l.seq).padStart(3)} cs=${l.csItemId} rid=${l.resourceId} ch=${l.chapterId} | ${l.chapterPath}`);
      process.exit(0);
    }
    tasks = leaves.map((leaf) => ({ leaf }));
  }
  if (ARGS['parent-grad']) parentGrad = ARGS['parent-grad'];

  // 批量下载落位：--out 优先；否则按 profile 落正式课程库 原始资源/videos/<梯度>
  let outDir = ARGS.out;
  if (!outDir && profile) {
    outDir = path.join(REPO_ROOT, profile.paths.localRoot, '原始资源', 'videos', stageLabel || String(grad));
  }
  if (!outDir) { console.error('批量下载需要 --out，或用 --profile 自动落位课程库'); process.exit(2); }
  log('输出目录:', path.relative(REPO_ROOT, outDir));
  const { cacheDir, keyCache, keyCachePath, isGlobal } = initCache(outDir, ARGS['global-key-cache']);
  if (ARGS['global-key-cache']) log('全局key缓存:', ARGS['global-key-cache']);
  if (ARGS['prefetch-only']) log('模式: 生产者（只预取key不下载）');
  if (ARGS.consumer) log('模式: 消费者（只从缓存读key下载）');
  const limit = ARGS.limit ? parseInt(ARGS.limit, 10) : tasks.length;
  const offset = ARGS.offset ? parseInt(ARGS.offset, 10) : 0;
  if (ARGS.offset) log(`偏移量: ${offset}（从第${offset + 1}个视频开始）`);
  let okN = 0, skipN = 0, failN = 0; const fails = [];
  for (let i = offset; i < Math.min(offset + limit, tasks.length); i += 1) {
    const leaf = tasks[i].leaf;
    try {
      const r = await downloadOne(leaf, { cid, parentGrad: parentGrad || grad, grad, syllabus, outDir, res: ARGS.res, concurrency: ARGS.concurrency, dualTeacher: !!ARGS['dual-teacher'], keyCache, keyCachePath, isGlobal, prefetchOnly: ARGS['prefetch-only'], consumer: ARGS.consumer });
      if (r.skipped) { skipN += 1; log(`跳过(${r.reason}): ${r.name}`); } else { okN += 1; }
    } catch (e) {
      failN += 1; fails.push({ leaf: leaf.name, err: e.message });
      log(`✗ 失败: ${leaf.name} — ${e.message}`);
    }
  }
  const modeLabel = ARGS['prefetch-only'] ? 'key预取' : (ARGS.consumer ? '消费者下载' : '下载');
  log(`批量结束：成功/已${modeLabel} ${okN}，非视频跳过 ${skipN}，失败 ${failN}`);
  if (fails.length) { fs.writeFileSync(path.join(cacheDir, 'fails.json'), JSON.stringify(fails, null, 2)); log('失败明细 -> .ep3cache/fails.json'); process.exit(1); }
  process.exit(0);
})().catch((e) => { console.error('[FATAL]', e.stack || e.message); process.exit(1); });
