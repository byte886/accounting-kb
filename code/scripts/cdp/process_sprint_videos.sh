#!/bin/bash
# process_sprint_videos.sh — 冲刺模考视频解析「转写 + 压缩」后处理
# 输入：data/_workspace/<profile>/tmp/download/sprint-videos/<标题>/.vfetch/merged.ts（fetch_sprint_video.js 产物，未加密已合并）
# 阶段1：3 个视频并行 FunASR 转写（每进程限 5 线程，3×5≈15 核，本机 20 线程留余量）
# 阶段2：串行 H.265 压缩为 video.mp4（x265 吃满核，全局唯一 ffmpeg，复用 compress.sh 校验）
# 成品（落在每个视频目录）：transcript.md / transcript.json（知识来源）、video.mp4（网盘归档）
# 断点续跑：已有 >1000 字 transcript 跳过转写；已有 video.mp4 跳过压缩。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/code/venvs/transcription/bin/python"
PIPE="$ROOT/scripts/transcribe_pipeline.py"
RP="${GAODUN_COURSE_PROFILE:-cpa-tax-2026}"
SV="$ROOT/data/_workspace/$RP/tmp/download/sprint-videos"
LOGDIR="$ROOT/data/_workspace/$RP/logs"
LOG="$LOGDIR/sprint_video_process.log"
mkdir -p "$LOGDIR"
THREADS_PER=5
: > "$LOG"
log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

shopt -s nullglob
DIRS=( "$SV"/*/ )   # bash 3.2 兼容（macOS 自带 bash 无 mapfile）
log "发现冲刺视频 ${#DIRS[@]} 个，开始阶段1：并行转写（每进程 ${THREADS_PER} 线程）"

# ---- 阶段1：并行转写 ----
pids=()
for d in "${DIRS[@]}"; do
  name="$(basename "$d")"; merged="$d/.vfetch/merged.ts"; tmp="$d/.vfetch/tr_tmp"
  if [ -f "$d/transcript.md" ] && [ "$(wc -m < "$d/transcript.md")" -gt 1000 ]; then log "[$name] transcript 已存在，跳过转写"; continue; fi
  [ -f "$merged" ] || { log "[$name] 缺 merged.ts，跳过"; continue; }
  (
    rm -rf "$tmp"; mkdir -p "$tmp"
    export OMP_NUM_THREADS=$THREADS_PER MKL_NUM_THREADS=$THREADS_PER
    t0=$(date +%s)
    if "$PY" "$PIPE" "$merged" "$tmp" >> "$LOG" 2>&1 && [ -f "$tmp/merged/transcript.md" ]; then
      cp "$tmp/merged/transcript.md" "$d/transcript.md"
      cp "$tmp/merged/transcript.json" "$d/transcript.json" 2>/dev/null || true
      rm -rf "$tmp"
      echo "[$(date '+%F %T')] [✓转写] $name ($(wc -m < "$d/transcript.md")字, $((($(date +%s)-t0)/60))分钟)" >> "$LOG"
    else
      echo "[$(date '+%F %T')] [✗转写] $name 失败，见日志" >> "$LOG"
    fi
  ) &
  pids+=($!)
  sleep 3   # 错开模型加载峰值
done
for p in "${pids[@]}"; do wait "$p"; done
log "阶段1转写全部结束"

# ---- 阶段2：串行 H.265 压缩（全局唯一 ffmpeg）----
log "开始阶段2：串行 H.265 压缩"
for d in "${DIRS[@]}"; do
  name="$(basename "$d")"; merged="$d/.vfetch/merged.ts"; out="$d/video.mp4"
  [ -f "$merged" ] || continue
  if [ -f "$out" ]; then log "[$name] video.mp4 已存在，跳过压缩"; continue; fi
  while pgrep -x ffmpeg >/dev/null 2>&1; do sleep 20; done
  log "[$name] 压缩开始"
  if bash "$ROOT/scripts/compress.sh" "$merged" "$out" 30 >> "$LOG" 2>&1; then
    log "[✓压缩] $name → $(du -h "$out" | cut -f1)"
  else
    rm -f "$out"; log "[✗压缩] $name 失败"
  fi
done
log "===== 冲刺视频后处理全部完成 ====="
