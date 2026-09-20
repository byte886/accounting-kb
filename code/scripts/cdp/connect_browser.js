/**
 * connect_browser.js — 连接「用户正在使用的日常 Chrome」
 *
 * 两大职责：
 *   A. Chrome 生命周期：Chrome 没开时自动拉起（用「上次使用的 Profile」，第一次用第一个 Profile）；
 *   B. CDP 连接：经 Chrome 144+「运行时远程调试」通道连接，复用默认 Profile 的现有登录态，
 *      免重启、免独立 Profile、免重新登录；自动点授权、偶发 403 自动退避重试。
 *
 * 选型与原理（均已本机实测，证据见报告）：
 *   - ADR：docs/project-management/decisions/ADR-010-浏览器自动化连接通道与技术栈选型.md
 *   - 手册：docs/development/tools/browser-cdp-connect-guide.md
 *   - 实测：project-management/task-reports/任务报告_浏览器连接通道选型实测_2026-09-01.md
 *
 * 关键事实：
 *   - 该通道 WebSocket-only，没有 /json/version、/json/list 发现接口（返回 404 属正常，不是故障）；
 *   - 端点必须带 UUID：从 user-data-dir 根的 DevToolsActivePort 读取（首行端口、次行 /devtools/browser/<uuid>），
 *     Chrome 每次重启 UUID 会变，禁止硬编码、每次动态读取；
 *   - 远程调试勾选按 Profile 记忆（per-profile，持久化）：目标 Profile 需在 chrome://inspect/#remote-debugging
 *     至少手动勾选一次；之后无论谁启动 Chrome，该 Profile 都会自动恢复调试端口；
 *   - 每次新连接 Chrome 弹「要允许远程调试吗？」(官方刻意的显式同意，无法永久关闭)，本模块自动 AXPress 代点；
 *     代点必须「只查授权 sheet、跳过网页 AXWebArea（否则遍历上万节点要 9s+ 被超时杀）」且「串行不并发
 *     （否则多个 osascript 在 System Events 拥塞堆积、永久点不中）」，详见 press_allow.applescript 头注释与
 *     docs/development/guides/macos-accessibility-automation.md §5；
 *   - 使用 puppeteer-core（不是 puppeteer）：不下载 Chromium，只连接用户已打开的 Chrome。
 *
 * 新环境依赖恢复（node_modules 不入库）：
 *   - 依赖声明在仓库根 package.json；缺依赖时在仓库根执行 `npm install`；
 *   - 若 package.json 也缺失，按名字从官方恢复：npm 包 puppeteer-core（pptr.dev），
 *     检索关键词："puppeteer-core connect browserWSEndpoint running Chrome"。
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFile, execFileSync } = require('child_process');

const PRESS_SCRIPT = path.join(__dirname, 'press_allow.applescript');
// 跨进程串行化包装（B-103）：所有代点「允许」都经它拿全机互斥锁后再调 PRESS_SCRIPT，
// 避免多个取 key 进程各自的 press 循环并发访问 System Events 互相拥塞、谁都点不中。
const PRESS_LOCKED = path.join(__dirname, 'press_allow_locked.sh');
const USER_DATA_DIR = process.env.CHROME_USER_DATA_DIR
  || path.join(os.homedir(), 'Library/Application Support/Google/Chrome');
// DevToolsActivePort 位于 user-data-dir 根（不随具体 Profile 变化）
const DEFAULT_ACTIVE_PORT = path.join(USER_DATA_DIR, 'DevToolsActivePort');
const CHROME_APP_NAME = 'Google Chrome';
const PROCESS_MATCH = 'Google Chrome.app/Contents/MacOS/Google Chrome';

// ---------------------------------------------------------------------------
// 一、读取 CDP 端点
// ---------------------------------------------------------------------------

/**
 * 从 DevToolsActivePort 读取带 UUID 的浏览器 WebSocket 端点
 * @param {string} [activePortFile] 默认 user-data-dir 根；可用环境变量 CHROME_DEVTOOLS_ACTIVE_PORT 覆盖
 * @returns {string} ws://127.0.0.1:<port>/devtools/browser/<uuid>
 */
function readWSEndpoint(activePortFile = process.env.CHROME_DEVTOOLS_ACTIVE_PORT || DEFAULT_ACTIVE_PORT) {
  if (!fs.existsSync(activePortFile)) {
    throw new Error(
      `找不到 DevToolsActivePort 文件：${activePortFile}\n` +
      '请确认：① 日常 Chrome 已打开（或允许本模块自动拉起）；② 该 Profile 已在 ' +
      'chrome://inspect/#remote-debugging 开启远程调试（每个 Profile 勾选一次即持久化）。'
    );
  }
  const raw = fs.readFileSync(activePortFile, 'utf8').trim();
  const [portLine, wsPath] = raw.split('\n');
  const port = Number((portLine || '').trim());
  if (!port || !wsPath || !wsPath.trim().startsWith('/devtools/')) {
    throw new Error(`DevToolsActivePort 内容异常：\n${raw}`);
  }
  return `ws://127.0.0.1:${port}${wsPath.trim()}`;
}

function loadPuppeteer() {
  try {
    return require('puppeteer-core');
  } catch (e) {
    throw new Error(
      '缺少依赖 puppeteer-core。请在仓库根目录执行 `npm install`（依赖声明见 package.json，node_modules 不入库）。\n' +
      `原始错误：${e.message}`
    );
  }
}

// ---------------------------------------------------------------------------
// 二、Chrome 生命周期：检测 / 选择 Profile / 冷启动拉起
// ---------------------------------------------------------------------------

/** Chrome 主进程是否正在运行 */
function isChromeRunning() {
  try {
    const out = execFileSync('pgrep', ['-f', PROCESS_MATCH], { encoding: 'utf8' });
    return out.trim().length > 0;
  } catch {
    return false; // pgrep 无匹配时退出码非 0
  }
}

/**
 * 选择要使用的 Profile 目录名（如 "Default" / "Profile 1"）
 * 规则：优先 Local State 的 profile.last_used（上次使用）；
 *       没有记录（第一次）时取 info_cache 的第一个，且若存在 Default 优先 Default；再不行兜底 "Default"。
 */
function pickProfile() {
  const localState = path.join(USER_DATA_DIR, 'Local State');
  try {
    const data = JSON.parse(fs.readFileSync(localState, 'utf8'));
    const prof = data.profile || {};
    if (prof.last_used && typeof prof.last_used === 'string') return prof.last_used;
    const keys = Object.keys(prof.info_cache || {});
    if (keys.length) return keys.includes('Default') ? 'Default' : keys.sort()[0];
  } catch {
    /* Local State 不存在或解析失败，走兜底 */
  }
  return 'Default';
}

/** 用指定 Profile 启动 Chrome（仅在 Chrome 未运行时调用） */
function launchChrome(profileDir) {
  const args = ['-a', CHROME_APP_NAME];
  if (profileDir) args.push('--args', `--profile-directory=${profileDir}`);
  execFileSync('open', args, { stdio: 'ignore' });
}

/**
 * 确保 Chrome 已运行且调试端口文件就绪
 * @param {object} [opt]
 * @param {string}  [opt.profile]            强制指定 Profile 目录名；缺省自动选择（上次使用/第一个）
 * @param {boolean} [opt.launchIfMissing=true] Chrome 未运行时是否自动拉起
 * @param {number}  [opt.waitMs=25000]       冷启动后等待调试端口文件的最长毫秒
 * @param {string}  [opt.activePortFile]     DevToolsActivePort 路径
 * @returns {Promise<{alreadyRunning:boolean, started:boolean, profile:string}>}
 */
async function ensureChromeRunning(opt = {}) {
  const {
    profile,
    launchIfMissing = true,
    waitMs = 25000,
    activePortFile = process.env.CHROME_DEVTOOLS_ACTIVE_PORT || DEFAULT_ACTIVE_PORT,
  } = opt;

  if (isChromeRunning()) {
    return { alreadyRunning: true, started: false, profile: profile || pickProfile() };
  }
  if (!launchIfMissing) {
    throw new Error('Chrome 未运行，且 launchIfMissing=false（不自动拉起）。');
  }
  const useProfile = profile || pickProfile();
  launchChrome(useProfile);

  // 冷启动后轮询等待 sticky 的远程调试恢复、端口文件写好（两行齐全才算就绪）
  const t0 = Date.now();
  while (Date.now() - t0 < waitMs) {
    if (fs.existsSync(activePortFile)) {
      try {
        readWSEndpoint(activePortFile);
        // 冷启动：给 Chrome UI 与辅助功能(AX)树一点就绪时间；授权代点交给连接阶段的串行点击循环统一处理
        await new Promise((r) => setTimeout(r, 1500));
        return { alreadyRunning: false, started: true, profile: useProfile };
      } catch {
        /* 文件刚写入可能不完整，继续轮询 */
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(
    `已启动 Chrome（Profile=${useProfile}），但 ${waitMs}ms 内未等到调试端口。\n` +
    '常见原因：该 Profile 从未在 chrome://inspect/#remote-debugging 勾选过远程调试（每个 Profile 需勾选一次，会持久化）。'
  );
}

// ---------------------------------------------------------------------------
// 三、授权弹窗自动化
// ---------------------------------------------------------------------------

/**
 * 调用 macOS 辅助功能代点一次「允许」。无弹窗时 pressed=false、无副作用。
 * @returns {Promise<{pressed:boolean, detail:string}>}
 */
function pressConsentOnce(restoreTo = '') {
  return new Promise((resolve) => {
    // 经跨进程锁包装（不再直接调 osascript），超时含等锁预算故放宽到 4s
    execFile('bash', [PRESS_LOCKED, restoreTo || ''], { timeout: 4000 }, (err, stdout) => {
      if (err) return resolve({ pressed: false, detail: err.message });
      const out = (stdout || '').trim();
      resolve({ pressed: /pressed=true/.test(out), detail: out });
    });
  });
}

/**
 * 串行授权点击循环
 * 关键：同一时刻最多一个 osascript 子进程。实测 setInterval 不等上次完成就并发派生时，
 * 多个 AppleScript 同时访问 System Events 会串行拥塞/死等（子进程堆积在 S 状态、无一执行到 AXPress），
 * 导致授权弹窗在时序不利时永远点不掉（「有时好有时坏」的根因之一）。
 * 改为「上一次结束或超时后再排下一次」，并对单次点按设硬超时，绝不堆积。
 * @returns {() => void} stop()：停止循环
 */
function startPressLoop({ intervalMs = 800, pressTimeoutMs = 4000, debug = !!process.env.DEBUG_CDP, restoreTo = '' } = {}) {
  let stopped = false;
  let inFlight = false;
  let timer = null;
  let currentChild = null;
  const runOnce = () => new Promise((resolve) => {
    const t0 = Date.now();
    // 经跨进程锁包装：全机同一时刻只允许一个代点 osascript（B-103），超时含等锁预算
    currentChild = execFile('bash', [PRESS_LOCKED, restoreTo || ''], { timeout: pressTimeoutMs }, (err, stdout, stderr) => {
      currentChild = null;
      const out = (stdout || '').trim();
      resolve({
        pressed: !err && /pressed=true/.test(out),
        cost: Date.now() - t0,
        err: err && err.message,
        stderr: (stderr || '').trim(),
        out,
      });
    });
  });
  async function tick() {
    if (stopped) return;
    if (inFlight) return schedule(); // 上一次仍在跑：本轮不并发，直接重排，杜绝堆积
    inFlight = true;
    try {
      const r = await runOnce();
      if (debug) {
        const tail = r.pressed ? '' : ` :: ${[r.err, r.stderr, r.out].filter(Boolean).join(' | ')}`.slice(0, 200);
        console.log(`[press] pressed=${r.pressed} cost=${r.cost}ms${tail}`);
      }
    } finally {
      inFlight = false;
      schedule();
    }
  }
  function schedule() { if (!stopped) timer = setTimeout(tick, intervalMs); }
  tick(); // 立即先点一次，抢在握手挂起前
  return function stop() {
    stopped = true;
    if (timer) clearTimeout(timer);
    if (currentChild) { try { currentChild.kill(); } catch { /* 已退出则忽略 */ } currentChild = null; }
  };
}

// ---------------------------------------------------------------------------
// 四、连接
// ---------------------------------------------------------------------------

/**
 * 连接用户正在使用的日常 Chrome（必要时先自动拉起），复用登录态
 *
 * 该通道在「发起连接」与「弹出授权窗」之间存在偶发竞态：多数情况下 WebSocket 挂起，
 * 点「允许」后握手成功；少数情况下在弹窗出现前直接回 HTTP 403。因此内置有限次退避重试，
 * 并在整个连接/重试周期持续代点授权，把偶发 403 / 握手失败吸收掉（实测重试 1~2 次即稳定通过）。
 *
 * @param {object} [opt]
 * @param {boolean} [opt.ensureRunning=true] Chrome 没开时是否自动拉起
 * @param {string}  [opt.profile]           强制指定 Profile（缺省：上次使用，第一次取第一个）
 * @param {number}  [opt.timeoutMs=30000]   单次连接的协议超时
 * @param {number}  [opt.retries=3]         握手失败(如 403)时的最大尝试次数
 * @param {number}  [opt.retryGapMs=1200]   两次尝试之间的退避毫秒
 * @param {boolean} [opt.autoPress=true]    连接期间是否自动 AXPress 授权弹窗
 * @param {string}  [opt.activePortFile]    DevToolsActivePort 路径
 * @returns {Promise<import('puppeteer-core').Browser>}
 */
async function connectDailyChrome(opt = {}) {
  const {
    ensureRunning = true,
    profile,
    timeoutMs = 30000,
    retries = 3,
    retryGapMs = 1200,
    autoPress = true,
    activePortFile,
  } = opt;
  const puppeteer = loadPuppeteer();

  // 0) 确保 Chrome 在运行、调试端口就绪
  if (ensureRunning) {
    await ensureChromeRunning({ profile, activePortFile,
      launchIfMissing: opt.launchIfMissing !== false });
  }

  // 串行授权点击循环（同一时刻只允许一个 osascript；并发访问 System Events 会拥塞死等、
  // 子进程堆积导致授权窗永远点不掉，详见 startPressLoop 注释与实测报告）
  // 连接前先记前台 App：授权 sheet 出现时系统会把 Chrome 置前，代点脚本在「点中允许的同一时刻」
  // 立刻把前台还给它（consentFront），不用等整个采集结束；外层 finally 的 restoreFrontmost 兜底。
  const consentFront = autoPress ? captureFrontmost() : null;
  const stopPress = autoPress
    ? startPressLoop({ debug: !!process.env.DEBUG_CDP, restoreTo: consentFront ? consentFront.name : '' })
    : null;
  try {
    let lastErr = null;
    for (let attempt = 1; attempt <= retries; attempt += 1) {
      // 每次尝试都重新读取端点（UUID 理论上单次 Chrome 运行期不变，重读更稳妥）
      const browserWSEndpoint = readWSEndpoint(activePortFile);
      try {
        return await puppeteer.connect({
          browserWSEndpoint,
          defaultViewport: null,       // 不改变用户真实窗口尺寸
          targetFilter: () => true,    // 接受全部 target（含扩展 / service worker）
          handleDevToolsAsPage: true,  // 官方点名：兼容 Chrome 144+ 运行时通道 / DevTools target
          protocolTimeout: timeoutMs,
        });
      } catch (e) {
        lastErr = e;
        if (attempt === retries) break;
        await new Promise((r) => setTimeout(r, retryGapMs));
      }
    }
    throw new Error(`连接日常 Chrome 失败（已尝试 ${retries} 次）：${lastErr && lastErr.message}`);
  } finally {
    if (stopPress) stopPress();
  }
}

/** 列出全部标签的 url + 标题（调试用） */
async function listPages(browser) {
  const pages = await browser.pages();
  return Promise.all(pages.map(async (p) => {
    let url = '', title = '';
    try { url = p.url(); } catch { /* target 可能无 url */ }
    try { title = await p.title(); } catch { /* 忽略 */ }
    return { url, title };
  }));
}

/**
 * 按 URL 匹配找到一个标签
 * @param {import('puppeteer-core').Browser} browser
 * @param {RegExp|string} match 正则，或字符串做包含匹配
 * @returns {Promise<import('puppeteer-core').Page|null>}
 */
async function findPage(browser, match) {
  const pages = await browser.pages();
  const hit = (u) => (match instanceof RegExp ? match.test(u) : u.includes(match));
  for (const p of pages) {
    let u = '';
    try { u = p.url(); } catch { continue; }
    if (hit(u)) return p;
  }
  return null;
}

/** 只断开调试连接，绝不关闭用户的标签和 Chrome 窗口 */
async function safeDisconnect(browser) {
  try {
    if (browser && browser.connected !== false) await browser.disconnect();
  } catch { /* 已断开则忽略 */ }
}

/**
 * 在「后台」新建一个标签：不激活、不抢占用户当前前台标签的输入焦点。
 *
 * 背景：browser.newPage() 底层 Target.createTarget 默认会激活新标签，取 key 每轮预取都
 * newPage+close，会反复把用户正在打字的标签切走（丢输入焦点）。改用 CDP 的 background:true
 * （Chrome 111+）后台建标签——标签在后台加载，静音视频仍可播放、Web Worker 不受后台节流影响，
 * 因此不影响 hls worker 取 key。
 *
 * 注意：本函数只负责后台建一个 about:blank 标签并返回 Page，**不替调用方 goto**，
 * 以便调用方保持「先 evaluateOnNewDocument 注入 hook、再 goto」的顺序。
 * 若当前 Chrome/协议不支持 background，则退回普通 newPage（功能优先，仅会短暂抢焦）。
 *
 * @param {import('puppeteer-core').Browser} browser
 * @returns {Promise<import('puppeteer-core').Page>}
 */
async function newBackgroundPage(browser) {
  try {
    const browserSession = await browser.target().createCDPSession();
    const { targetId } = await browserSession.send('Target.createTarget', {
      url: 'about:blank',
      background: true,   // 关键：创建但不激活，不抢前台焦点
      newWindow: false,
    });
    await browserSession.detach().catch(() => {});
    const target = await browser.waitForTarget(
      (t) => t._targetId === targetId
        || (typeof t.targetId === 'function' && t.targetId() === targetId),
      { timeout: 8000 },
    );
    const page = await target.page();
    if (page) return page;
    throw new Error('后台 target 转 Page 失败');
  } catch (e) {
    console.warn(`[cdp] 后台建标签不可用，退回普通 newPage（可能短暂抢焦）：${e && e.message}`);
    return browser.newPage();
  }
}

// ---------------------------------------------------------------------------
// 五、前台焦点记忆与归还（缓解官方授权弹窗抢焦）
// ---------------------------------------------------------------------------
//
// 背景：每次新连接 Chrome 都会弹官方强制的「要允许远程调试吗？」sheet（无法永久关闭），
// 该 sheet 出现时 macOS 会自动把 Google Chrome 置前，抢走用户正在打字的 App（如豆包）焦点；
// press_allow.applescript 只负责 AXPress 关掉弹窗、并不会把焦点还回去。
// 策略（best-effort，绝不因焦点逻辑影响采集主流程）：
//   采集「开始前」用 captureFrontmost() 记住当前前台 App；
//   采集「结束后」用 restoreFrontmost(prev) —— 仅当此刻前台是 Google Chrome
//   （说明确实是被我们的授权弹窗抢过去的）才 activate 回原 App；
//   若用户中途自己切到了别的 App（前台已不是 Chrome），则不强行切、尊重用户操作。

/** 同步跑一段 osascript，短超时、失败安静返回 null（焦点逻辑不得抛错影响主流程） */
function runOsa(appleScript, timeoutMs = 1500) {
  try {
    return execFileSync('osascript', ['-e', appleScript], { timeout: timeoutMs, encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

/**
 * 记录当前前台 App。系统进程（如 loginwindow/锁屏）也能取到 name、bundleId 可能为空。
 * @returns {{name:string, bundleId:string}|null}
 */
function captureFrontmost() {
  const out = runOsa(
    'tell application "System Events"\n'
    + 'set ps to (processes whose frontmost is true)\n'
    + 'if (count of ps) is 0 then return ""\n'
    + 'set p to item 1 of ps\n'
    + 'set n to name of p\n'
    + 'set b to ""\n'
    + 'try\nset b to bundle identifier of p\nend try\n'
    + 'return n & "\\t" & b\n'
    + 'end tell',
  );
  if (!out) return null;
  const [name, bundleId = ''] = out.split('\t');
  return name ? { name, bundleId: bundleId || '' } : null;
}

/**
 * 若前台焦点确实被 Chrome 抢走，则归还给 prev；否则不动。
 * @param {{name:string,bundleId:string}|null} prev captureFrontmost() 的结果
 * @returns {boolean} 是否执行了归还
 */
function restoreFrontmost(prev) {
  if (!prev || !prev.name || prev.name === CHROME_APP_NAME) return false; // 原本就在 Chrome / 无记录：无需还
  const cur = runOsa('tell application "System Events" to name of first process whose frontmost is true');
  if (cur !== CHROME_APP_NAME) return false; // 用户中途自己切走了，尊重、不强切
  // 走 System Events 的 set frontmost（只需 System Events 辅助功能权限，已具备）；
  // 不用 `tell application X to activate`——node 宿主下该 AppleEvent 会被系统静默丢弃、不真正前置。
  const name = String(prev.name).replace(/"/g, ''); // 防 AppleScript 注入
  const script = 'tell application "System Events"\n'
    + 'try\n'
    + `set frontmost of (first process whose name is "${name}") to true\n`
    + 'end try\n'
    + 'end tell';
  return runOsa(script, 2000) !== null; // 未抛错即视为已发起；目标进程已退出则 try 内安静失败
}

// 直接运行本文件 = 环境自检：确保 Chrome 运行 → 连接 → 打印浏览器版本与标签 → 断开
// 用法：node scripts/cdp/connect_browser.js
if (require.main === module) {
  (async () => {
    const t0 = Date.now();
    const state = await ensureChromeRunning();
    const note = state.alreadyRunning
      ? `Chrome 已在运行（Profile=${state.profile}）`
      : `Chrome 未运行，已自动拉起（Profile=${state.profile}）`;
    console.log('[life]', note);
    const browser = await connectDailyChrome({ ensureRunning: false });
    const version = await browser.version();
    const pages = await listPages(browser);
    console.log(`[OK] ${version}，连接耗时 ${Date.now() - t0}ms，当前 ${pages.length} 个标签：`);
    pages.forEach((p, i) => console.log(`  ${i + 1}. ${p.title || '(无标题)'}  ${p.url}`));
    await safeDisconnect(browser);
    console.log('[OK] 已断开调试连接（你的浏览器与标签原样保留）');
    process.exit(0);
  })().catch((e) => {
    console.error('[FAIL]', e.message);
    process.exit(1);
  });
}

module.exports = {
  readWSEndpoint,
  loadPuppeteer,
  isChromeRunning,
  pickProfile,
  launchChrome,
  ensureChromeRunning,
  pressConsentOnce,
  startPressLoop,
  connectDailyChrome,
  listPages,
  findPage,
  newBackgroundPage,
  captureFrontmost,
  restoreFrontmost,
  safeDisconnect,
  PRESS_SCRIPT,
  USER_DATA_DIR,
};
