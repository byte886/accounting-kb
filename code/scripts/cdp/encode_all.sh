#!/bin/bash
# encode_all.sh — 视频「压缩阶段」。扫描各讲 .vfetch/manifest.json，把已下载的 merged.ts
# 逐个 H.265 压缩为 video.mp4（compress.sh 自带时长/moov 校验），成功后清理分片与 merged。
# CPU 密集：全局同时只允许一个 ffmpeg（x265 吃满核，第二个同类实例总吞吐不增反降）。
# 断点续跑：已有 video.mp4 跳过；压缩失败保留 merged，下一轮重试。
#
# 用法:
#   bash scripts/cdp/encode_all.sh            # 只扫一遍：把当前已下载的依次压完即退出
#   bash scripts/cdp/encode_all.sh --watch    # 守护模式：边下边压；等 download_all 结束且全部压完才退出
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../course_config.sh
source "$ROOT/scripts/course_config.sh"
COURSE="$COURSE_DESKTOP_ROOT"   # 由 profile/COURSE_NAME 派生，缺省税法，换课设 COURSE_PROFILE
LOG=/tmp/encode_all.log
WATCH=0; [ "${1:-}" = "--watch" ] && WATCH=1
read_field() { node -e "try{console.log(require('$1').$2||'')}catch(e){console.log('')}"; }
# 返回第一个「有 merged、无 video.mp4」的 manifest；没有则空
find_pending() { local mf lec merged target; shopt -s nullglob
  for mf in "$COURSE"/*/.vfetch/manifest.json; do
    lec="$(dirname "$(dirname "$mf")")"
    [ -f "$lec/video.mp4" ] && continue
    merged="$(read_field "$mf" merged)"; target="$(read_field "$mf" targetVideo)"
    [ -n "${merged:-}" ] && [ -f "$merged" ] && { echo "$mf"; return 0; }
  done; return 1; }
echo "==== 压缩阶段开始 $(date '+%F %T') watch=$WATCH ====" | tee "$LOG"
ok=0; fail=0
while true; do
  # 全局唯一压缩实例：已有 ffmpeg 在跑就等它
  if pgrep -x ffmpeg >/dev/null 2>&1; then sleep 30; continue; fi
  if mf="$(find_pending)"; then
    lec="$(dirname "$(dirname "$mf")")"; name="$(basename "$lec")"
    merged="$(read_field "$mf" merged)"; target="$(read_field "$mf" targetVideo)"
    echo "------ [$name] 压缩开始 $(date '+%T') ------" | tee -a "$LOG"
    if bash "$ROOT/scripts/compress.sh" "$merged" "$target" 30 2>&1 | tee -a "$LOG"; then
      echo "[$name] ✓ 完成，清理分片/merged $(date '+%T')" | tee -a "$LOG"
      rm -rf "$lec/.vfetch/segments" "$merged"; ok=$((ok+1))
    else
      echo "[$name] ✗ 压缩/校验失败，删除可能残缺的 mp4，60s 后重试" | tee -a "$LOG"; rm -f "$target"; fail=$((fail+1)); sleep 60
    fi
    continue
  fi
  # 没有待压缩
  if [ "$WATCH" -eq 1 ] && pgrep -f download_all.sh >/dev/null 2>&1; then
    echo "[watch] 当前无待压缩，下载仍在进行，60s 后再扫..." | tee -a "$LOG"; sleep 60; continue
  fi
  echo "==== 压缩阶段结束 $(date '+%F %T') 成功$ok 失败$fail ====" | tee -a "$LOG"; exit 0
done
