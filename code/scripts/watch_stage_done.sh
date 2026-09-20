#!/bin/bash
# watch_stage_done.sh — 通用阶段完成事件监听（零依赖，60秒轮询）。
# 用途：监听某目录下匹配指定模式的文件数量达到预期值时，写完成标记文件并退出。
#       替代人工长间隔巡检，消除"任务已完成但总调度未发现"的空窗（空窗≤60秒）。
# 用法: bash scripts/watch_stage_done.sh <监听目录> <文件名匹配> <预期数量> <标记文件路径> [检查间隔秒]
# 示例: bash scripts/watch_stage_done.sh "data/高顿/.../税法（蔡俊峻老师）" "transcript.md" 39 "transcription/.transcribe_done"
set -uo pipefail
WATCH_DIR="${1:?用法: watch_stage_done.sh <目录> <文件名匹配> <预期数量> <标记文件> [间隔秒]}"
PATTERN="${2:?缺少文件名匹配模式}"
EXPECTED="${3:?缺少预期数量}"
MARKER="${4:?缺少标记文件路径}"
INTERVAL="${5:-60}"
LOG="$(dirname "$MARKER")/watch_$(basename "$MARKER").log"
mkdir -p "$(dirname "$MARKER")" "$(dirname "$LOG")"

echo "[$(date '+%F %T')] 监听开始: 目录=$WATCH_DIR 模式=$PATTERN 预期=$EXPECTED 标记=$MARKER 间隔=${INTERVAL}s" | tee -a "$LOG"
while true; do
  # 计数：在 WATCH_DIR 下 maxdepth 3 查找匹配 PATTERN 且 >1000字节的文件（排除空壳/半成品）
  count=$(find "$WATCH_DIR" -maxdepth 3 -name "$PATTERN" -size +1000c 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -ge "$EXPECTED" ]; then
    touch "$MARKER"
    echo "[$(date '+%F %T')] ✅ 阶段完成: $count/$EXPECTED 个 $PATTERN，标记已写 $MARKER" | tee -a "$LOG"
    exit 0
  fi
  sleep "$INTERVAL"
done
