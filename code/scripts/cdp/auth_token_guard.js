'use strict';
/**
 * auth_token_guard.js — 高顿本地 JWT 失效（553649434「登录超时,请重新登录」）的跨进程自动续命。
 *
 * 背景（I-013）：
 *   - 本地抓包 JWT 有效期约 7 天，一过期所有用 findJwt() 的高顿接口都返回 553649434；
 *   - 视频下载是多进程并行（throttled 调度器下 3 个消费者 + 1 个生产者），若每个进程各自去
 *     spawn refresh_auth_token.js，会同时连 Chrome、重复刷新并抢前台焦点；
 *   - 做题脚本（batch_redo_papers）是单进程串行，原本各自内联了一份刷新逻辑，统一收口到本模块，
 *     避免重复实现（项目原则：以精简删除历史冗余为荣，以堆砌重复实现为耻）。
 *
 * 机制：文件锁 single-flight。第一个发现失效的进程持锁、连接已登录日常 Chrome 抓新 token；
 *   其余进程发现锁存在就等待，锁释放且 auth 目录出现更新的 .jsonl 后直接 findJwt() 复用，不再连 Chrome。
 *
 * 不做的事：本模块只在「明确收到 553649434」时触发；做题风控码（10462221 等）不是 token 问题，绝不刷新。
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { findJwt } = require('./gaodun_paper_core');

const TOKEN_EXPIRED_CODE = 553649434; // 高顿「登录超时,请重新登录」
const REPO_ROOT = path.join(__dirname, '..', '..');
const AUTH_DIR = path.join(REPO_ROOT, 'data', '_workspace', '_account', 'auth');
const LOCK_FILE = path.join(AUTH_DIR, '.refresh.lock');
const REFRESH_SCRIPT = path.join(__dirname, 'refresh_auth_token.js');
const STALE_LOCK_MS = 120000; // 锁超过 120s 视为持有者崩溃，可被抢占
const WAIT_OTHER_MS = 90000;  // 等待其它进程刷新完成的最长时间

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const noop = () => {};

/** status（数字/字符串）或错误消息是否为 token 失效（做题侧以 e.message 携带 status） */
function isTokenExpired(statusOrMsg) {
  return statusOrMsg != null && String(statusOrMsg).includes(String(TOKEN_EXPIRED_CODE));
}

function latestTokenMtime() {
  try {
    return fs.readdirSync(AUTH_DIR)
      .filter((f) => f.endsWith('.jsonl'))
      .map((f) => fs.statSync(path.join(AUTH_DIR, f)).mtimeMs)
      .reduce((a, b) => Math.max(a, b), 0);
  } catch { return 0; }
}
function procAlive(pid) {
  if (!pid) return false;
  try { process.kill(pid, 0); return true; } catch { return false; }
}
function readLock() {
  try { return JSON.parse(fs.readFileSync(LOCK_FILE, 'utf8')); } catch { return null; }
}
/** 尝试独占建锁；锁被活跃持有时返回 false，陈旧锁可抢占（抢占遇竞态仍返回 false 走等待） */
function tryAcquire() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const write = () => {
    const fd = fs.openSync(LOCK_FILE, 'wx'); // O_EXCL：原子独占创建
    fs.writeSync(fd, JSON.stringify({ pid: process.pid, startedAt: Date.now() }));
    fs.closeSync(fd);
  };
  try { write(); return true; } catch (e) {
    if (e.code !== 'EEXIST') throw e;
    const lk = readLock();
    const stale = !lk || !procAlive(lk.pid) || Date.now() - (lk.startedAt || 0) > STALE_LOCK_MS;
    if (!stale) return false;
    try { fs.unlinkSync(LOCK_FILE); } catch { /* 可能被别人先抢 */ }
    try { write(); return true; } catch { return false; }
  }
}
function releaseIfOwner() {
  const lk = readLock();
  if (lk && lk.pid === process.pid) { try { fs.unlinkSync(LOCK_FILE); } catch { /* ignore */ } }
}
function runRefreshScript() {
  // stdio 用 pipe：多进程并行时不把子进程日志交错刷进各消费者日志；失败时把尾部输出带进错误
  const out = execFileSync('node', [REFRESH_SCRIPT], {
    cwd: REPO_ROOT, stdio: ['ignore', 'pipe', 'pipe'], timeout: 90000, encoding: 'utf8',
  });
  return out;
}

/**
 * 跨进程 single-flight 刷新并返回新 JWT。
 * @returns {Promise<string>} 新 token
 */
async function refreshJwtWithLock({ log = noop } = {}) {
  const mtimeBefore = latestTokenMtime();
  if (tryAcquire()) {
    log('[token] 命中 553649434，本进程持锁连接已登录 Chrome 刷新 token...');
    try { runRefreshScript(); }
    catch (e) {
      releaseIfOwner();
      const tail = String(e.stdout || e.stderr || e.message || '').slice(-300);
      throw new Error(`自动刷新 token 失败（请确认日常 Chrome 已打开且登录高顿）：${tail}`);
    }
    releaseIfOwner();
    return findJwt();
  }
  log('[token] 其它进程正在刷新 token，等待复用新 token...');
  const t0 = Date.now();
  while (Date.now() - t0 < WAIT_OTHER_MS) {
    await sleep(1000);
    if (!fs.existsSync(LOCK_FILE) && latestTokenMtime() > mtimeBefore) return findJwt();
  }
  // 等待超时兜底：自己再尝试持锁刷一次
  if (tryAcquire()) {
    try { runRefreshScript(); } finally { releaseIfOwner(); }
    return findJwt();
  }
  throw new Error('等待其它进程刷新 token 超时');
}

module.exports = { TOKEN_EXPIRED_CODE, isTokenExpired, refreshJwtWithLock };
