#!/bin/bash
# transcribe_all.sh — 对税法课程库所有讲的 video.mp4 用 FunASR(SenseVoiceSmall+VAD) 批量转写。
# 逐讲用独立临时目录调用 transcribe_pipeline.py（规避所有视频同名 video.mp4 导致输出互相覆盖），
# 完成后把 transcript.md / transcript.json 拷回各讲目录（与 00/01/02 样板一致）。
# 断点续传：讲目录已有 transcript.md 且 >1000 字自动跳过；单讲失败记录后继续。
# CPU 密集：请在视频「压缩全部完成后」再跑，避免与 x265 叠加争抢/降频。
# 用法: bash scripts/transcribe_all.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=course_config.sh
source "$ROOT/scripts/course_config.sh"
PY="$ROOT/code/venvs/transcription/bin/python"
PIPE="$ROOT/scripts/transcribe_pipeline.py"
# 遍历根默认课程根（旧布局：课程根/讲次/video.mp4）；成品已归位时用 TRANSCRIBE_ROOT 指向「原始资源/videos」
COURSE="${TRANSCRIBE_ROOT:-$COURSE_DESKTOP_ROOT}"   # 由 profile/COURSE_NAME 派生，缺省税法，换课设 COURSE_PROFILE
RP="${COURSE_PROFILE:-${GAODUN_COURSE_PROFILE:-_shared}}"
TMPROOT="$ROOT/data/_workspace/$RP/tmp/tmp_transcribe"
LOG="$ROOT/data/_workspace/$RP/logs/transcribe_all.log"
mkdir -p "$TMPROOT" "$(dirname "$LOG")"
# 退出兜底：正常结束/报错/Ctrl-C 都清掉当前讲的中转子目录（TMPROOT 根目录保留供断点续跑）
cleanup() { local t="${tmp:-}"; [ -n "$t" ] && rm -rf "$t"; }
trap cleanup EXIT
echo "==== 批量转写开始 $(date '+%F %T') ====" | tee "$LOG"
ok=0; skip=0; fail=0; failed_list=()
shopt -s nullglob
for d in "$COURSE"/[0-9][0-9]_*; do
  name="$(basename "$d")"; v="$d/video.mp4"; out="$d/transcript.md"
  if [ -f "$out" ] && [ "$(wc -m < "$out")" -gt 1000 ]; then echo "[$name] 已有转写，跳过"; skip=$((skip+1)); continue; fi
  if [ ! -f "$v" ]; then echo "[$name] 无 video.mp4（可能尚未压缩），跳过"; fail=$((fail+1)); failed_list+=("$name"); continue; fi
  tmp="$TMPROOT/${name:0:2}"; rm -rf "$tmp"; mkdir -p "$tmp"
  echo "------ [$name] 转写 $(date '+%T') ------" | tee -a "$LOG"
  if "$PY" "$PIPE" "$v" "$tmp" 2>&1 | tee -a "$LOG" && [ -f "$tmp/video/transcript.md" ]; then
    cp "$tmp/video/transcript.md" "$d/transcript.md"
    cp "$tmp/video/transcript.json" "$d/transcript.json"
    echo "[$name] ✓ 完成 约$(wc -m < "$d/transcript.md")字" | tee -a "$LOG"; ok=$((ok+1))
  else
    echo "[$name] ✗ 转写失败" | tee -a "$LOG"; fail=$((fail+1)); failed_list+=("$name")
  fi
  rm -rf "$tmp"
done
echo "==== 批量转写结束 $(date '+%F %T') 成功$ok 跳过$skip 失败$fail ====" | tee -a "$LOG"
[ ${#failed_list[@]} -gt 0 ] && printf '失败/未就绪: %s\n' "${failed_list[@]}" | tee -a "$LOG"
