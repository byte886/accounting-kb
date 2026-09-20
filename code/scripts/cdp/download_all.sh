#!/bin/bash
# download_all.sh — 视频「下载阶段」：逐讲 抓HLS key→下载解密，只产出 .vfetch/merged.ts，不压缩。
# 串行抓 key（同一 Chrome 一次只开一个播放标签，拟人、避免多标签 hls worker 互相干扰）；
# 网络 IO 为主、几乎不占 CPU，可与 OCR / 压缩 并行。讲间留 4s 间隔。
# 断点续跑：已有 video.mp4 或已下载 merged 的讲自动跳过。
# 用法: bash scripts/cdp/download_all.sh [idx ...]   # 不给参数则遍历 1..39
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG=/tmp/download_all.log
IDXS=("$@"); [ ${#IDXS[@]} -eq 0 ] && { for i in $(seq 1 39); do IDXS+=("$i"); done; }
ok=0; skip=0; fail=0; failed_list=()
echo "==== 下载阶段开始 $(date '+%F %T') idx=${IDXS[*]} ====" | tee "$LOG"
for idx in "${IDXS[@]}"; do
  prefix=$(printf '%02d' $((idx-1)))
  echo "------ [$prefix] idx=$idx ------" | tee -a "$LOG"
  if node "$ROOT/scripts/cdp/fetch_lecture_video.js" "$idx" 2>&1 | tee -a "$LOG"; then
    ok=$((ok+1))
  else
    echo "[$prefix] 抓取/下载失败，记录后继续" | tee -a "$LOG"; fail=$((fail+1)); failed_list+=("$prefix")
  fi
  sleep 4
done
echo "==== 下载阶段结束 $(date '+%F %T') 处理$ok 失败$fail ====" | tee -a "$LOG"
[ ${#failed_list[@]} -gt 0 ] && echo "失败讲: ${failed_list[*]}（重跑本脚本即可断点续跑）" | tee -a "$LOG"
