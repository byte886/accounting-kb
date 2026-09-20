#!/usr/bin/env bash
# cdp_consent_guard.sh — 全局单例「Chrome 远程调试授权」守护
#
# 为什么需要它（B-104）：
#   代点循环原本只活在 connectDailyChrome() 的握手窗口内，连接一 return 就在 finally 里 stopPress。
#   但授权 sheet 可能晚到、可能点一次没真正关掉、也可能在连接进程退出后残留 —— 此后再没有任何
#   代点循环，sheet 就一直挂着、Chrome 抢占的焦点也不会还回用户正在用的 App（豆包）。
#
# 本守护由下载调度器（throttled_ep3_download.sh）在整个下载期间拉起、收工时回收：
#   - 全局单例（pidfile），重复启动安全退出；
#   - 每 1s 用「一条」轻量 AppleEvent 同时取「当前前台 App + Chrome 授权 sheet 数」，
#     只数 sheet、绝不遍历网页 AXWebArea（毫秒级，见 press_allow.applescript 血泪注释）；
#   - 记住最近一个「非 Chrome」前台 App；一旦发现授权 sheet，就在跨进程锁保护下代点「允许」，
#     没点掉下一秒继续，直到消失，并把焦点还给用户原来在用的 App；
#   - 无 sheet 时零动作、不抢焦、不打扰用户正常使用 Chrome。
#
# 它与 connect_browser.js 内的 startPressLoop 不重复：后者负责握手期 800ms 高频快速点按以减少
# 403 重试，本守护负责「整个下载周期」的残留/晚到兜底；两者共用 press_allow_locked.sh 的同一把锁。
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

WS="data/_workspace/_account/ep3/run"
mkdir -p "$WS"
PIDFILE="$WS/consent_guard.pid"
LOCKED_PRESS="scripts/cdp/press_allow_locked.sh"

# ---- 单例：已有存活守护则直接退出 ----
if [ -f "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null)"
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
    exit 0
  fi
fi
echo $$ > "$PIDFILE"
cleanup() { rm -f "$PIDFILE" 2>/dev/null; exit 0; }
trap cleanup EXIT INT TERM

# 阻止 Mac 空闲睡眠（守护通常已被外层 caffeinate 覆盖，这里兜底，-w 绑定自身生命周期）
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i -w $$ &
fi

last_human=""
# 一条 AppleEvent 同时返回：第1行=当前前台App，第2行=Chrome 授权 sheet 数（Chrome 没开则 0）
READ_SCRIPT='tell application "System Events"
set f to name of first process whose frontmost is true
set n to 0
if exists process "Google Chrome" then
tell process "Google Chrome" to set n to (count of sheets of windows)
end if
return f & linefeed & (n as string)
end tell'

while true; do
  read -r front n_sheet <<EOF
$(osascript -e "$READ_SCRIPT" 2>/dev/null | grep -v ApplePersistence | tr -d '\r')
EOF

  # 记住最近一个非 Chrome 前台 App，作为点中允许后的还焦目标
  if [ -n "${front:-}" ] && [ "$front" != "Google Chrome" ]; then
    last_human="$front"
  fi

  # 有授权 sheet 才代点（锁保护、没掉落下一秒继续）；无 sheet 零动作
  if [ -n "${n_sheet:-}" ] && [ "$n_sheet" != "0" ]; then
    bash "$LOCKED_PRESS" "$last_human" >/dev/null 2>&1
  fi

  sleep 1
done
