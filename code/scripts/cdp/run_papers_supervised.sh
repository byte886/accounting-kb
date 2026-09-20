#!/bin/bash
# 批量做题「守护启动器」：通用守护器 run_supervised.sh 在做题场景的薄封装（每门课可复用）
#
# 解决的问题：
#   batch_redo_papers.js 长跑会「零错误静默退出」（进程消失、日志停在 [N/M]、无异常栈）。
#   若直接把它重启，会按旧 audit 从 [1] 重做已满分的卷，形成「永远做前几十张」的死循环；
#   靠 30 分钟定时巡检事后拉起又有固有延迟、且治标不治本。
#
# 本启动器让守护器每一轮严格按顺序执行：
#   1) refresh_inventory 从平台只读回查、重建 audit（只保留真正未达成的卷，已满分自动剔除）
#   2) batch_redo_papers --go 续跑这批剩余卷
#   redo 一旦退出（正常做完 / 再次静默退出），5 秒后自动进入下一轮：重新 refresh → 只补剩余。
#   - 全部完成（refresh 后 audit 长度=0）：写终态日志（[NOTIFY] ✅ 完成）并 exit 0
#   - 连续 3 轮「平台满分+平台最优数」不增长（如个别卷客观上无法满分）：判异常、写终态日志、exit 1
#   做题线不弹 macOS 通知（SUPERVISE_NO_OSASCRIPT=1）：终态由「定时唤醒的 AI」巡检日志/进程后接手
#   推进、并在豆包内通知用户；caffeinate -i 防止 Mac 空闲睡眠导致进程暂停。
#
# 用法:
#   nohup bash scripts/cdp/run_papers_supervised.sh <profile> \
#     > data/_workspace/<profile>/logs/supervisor_papers.log 2>&1 & disown
# 例:
#   nohup bash scripts/cdp/run_papers_supervised.sh cpa-accounting-2026 \
#     > data/_workspace/cpa-accounting-2026/logs/supervisor_papers.log 2>&1 & disown
#
# 日志分工（均在 data/_workspace/<profile>/logs/）：
#   supervisor_papers.log  守护轮次/进度/停滞判定/完成通知
#   refresh_supervised.log 每轮平台回查（refresh_inventory）输出
#   batch_do_paper.log     做题明细（追加，不覆盖）

set -u

PROFILE="${1:?用法: run_papers_supervised.sh <profile-key>，如 cpa-accounting-2026}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

WS="data/_workspace/$PROFILE"
MAN="$WS/manifest"
mkdir -p "$WS/logs"

if [ ! -f "$MAN/papers_audit.json" ] || [ ! -f "$MAN/papers_inventory.json" ]; then
  echo "[run_papers_supervised] 缺少 $MAN 下的 audit/inventory，请先跑 refresh_inventory 初始化。" >&2
  exit 2
fi

# 单轮：先 refresh 重建 audit，再 redo 续跑（顺序不可颠倒，否则按旧 audit 从头重做）
RUN_CMD="node scripts/cdp/refresh_inventory.js --profile $PROFILE >> $WS/logs/refresh_supervised.log 2>&1 && node scripts/cdp/batch_redo_papers.js --profile $PROFILE --go >> $WS/logs/batch_do_paper.log 2>&1"
# 完成判据：refresh 后待做 audit 为空
DONE_TEST="node -e 'process.exit(require(\"./$MAN/papers_audit.json\").length===0?0:1)'"
# 进度标量：平台已达成（满分+平台最优）张数，随轮次单调不减，用于停滞检测
PROG_CMD="node -e 'const a=require(\"./$MAN/papers_inventory.json\");process.stdout.write(String(a.filter(p=>p.cls===\"满分\"||p.cls===\"平台最优\").length))'"

# 做题线不弹 macOS 通知；caffeinate -i 在守护器整个生命周期内防止 Mac 空闲睡眠
export SUPERVISE_NO_OSASCRIPT=1
exec caffeinate -i bash scripts/run_supervised.sh "${PROFILE}-papers" "$RUN_CMD" "$DONE_TEST" "$PROG_CMD"
