#!/bin/bash
# transcribe_one.sh — 单讲转写（被 xargs -P 并发调用，每个讲只出现一次，天然无竞态）。
# 用法: bash scripts/transcribe_one.sh <讲目录绝对路径>
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/code/venvs/transcription/bin/python"
PIPE="$ROOT/scripts/transcribe_pipeline.py"
RP="${GAODUN_COURSE_PROFILE:-_shared}"
WORK="$ROOT/data/_workspace/$RP/tmp/parallel_work"
LOGDIR="$ROOT/data/_workspace/$RP/logs"; MAINLOG="$WORK/parallel.log"
mkdir -p "$WORK" "$LOGDIR"

D="${1:-}"; [ -d "$D" ] || { echo "[$(date '+%H:%M:%S')] ✗ 目录不存在: $D" | tee -a "$MAINLOG"; exit 1; }
NAME=$(basename "$D"); PREFIX="${NAME%%_*}"
# 已有合格 transcript 则跳过
if [ -f "$D/transcript.md" ] && [ "$(wc -m < "$D/transcript.md")" -gt 1000 ]; then
  echo "[$(date '+%H:%M:%S')] ⊘ 跳过(已有) $NAME" | tee -a "$MAINLOG"; exit 0
fi
TMP="$WORK/${PREFIX}"; rm -rf "$TMP"; mkdir -p "$TMP"
echo "[$(date '+%H:%M:%S')] ▶ 开始 $NAME" | tee -a "$MAINLOG"
if "$PY" "$PIPE" "$D/video.mp4" "$TMP" > "$LOGDIR/${PREFIX}.log" 2>&1 \
   && [ -f "$TMP/video/transcript.md" ]; then
  cp "$TMP/video/transcript.md" "$D/transcript.md"
  cp "$TMP/video/transcript.json" "$D/transcript.json" 2>/dev/null || true
  rm -rf "$TMP"
  echo "[$(date '+%H:%M:%S')] ✓ 完成 $NAME ($(wc -m < "$D/transcript.md")字)" | tee -a "$MAINLOG"; exit 0
else
  rm -rf "$TMP"
  echo "[$(date '+%H:%M:%S')] ✗ 失败 $NAME (见 $LOGDIR/${PREFIX}.log)" | tee -a "$MAINLOG"; exit 1
fi
