#!/bin/bash
# Compress a merged .ts file to H.265 MP4 using ffmpeg, then verify.
# Runs in current terminal (iTerm) with live progress — do NOT run in background.
#
# Usage:
#   bash compress.sh <input.ts> <output.mp4> [crf]
#
# Arguments:
#   input.ts   - merged decrypted transport stream
#   output.mp4 - output MP4 path
#   crf        - x265 CRF value (default 30; lower = better quality/larger file)
#
# After encoding, automatically runs ffprobe verification.

set -euo pipefail

# 动态获取项目目录（脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"


set -euo pipefail

# ⚠️ 运行时检测：必须在终端中运行，禁止后台运行。
# 例外：被动态流水线 video_dynamic_pipeline.sh 后台调度时，它会显式传
# COMPRESS_NONINTERACTIVE=1（调度器自身有日志/状态机，不需要 iTerm 前台进度）。
if [ ! -t 1 ] && [ "${COMPRESS_NONINTERACTIVE:-0}" != "1" ]; then
  echo "========================================"
  echo "⚠️  警告：检测到非终端环境运行！"
  echo "========================================"
  echo ""
  echo "本脚本必须在 iTerm 终端窗口中运行，禁止使用 & 后台运行。"
  echo "原因："
  echo "  1. 用户需要实时看到 ffmpeg 编码进度"
  echo "  2. 后台运行可能因进程管理问题导致异常退出"
  echo "  3. 压缩完成后需要终端输出验证结果"
  echo ""
  echo "正确方式：在 iTerm 新标签页中运行"
  echo "  osascript -e 'tell application \"iTerm\""
  echo "    tell current window"
  echo "      create tab with default profile"
  echo "      tell current session"
  echo "        write text \"cd $(pwd) && bash $0 $*\""
  echo "      end tell"
  echo "    end tell"
  echo "  end tell'"
  echo ""
  echo "========================================"
  echo "继续运行（5秒后自动继续，按 Ctrl+C 停止）..."
  echo "========================================"
  sleep 5
fi

INPUT="${1:?Usage: compress.sh <input.ts> <output.mp4> [crf]}"
OUTPUT="${2:?Usage: compress.sh <input.ts> <output.mp4> [crf]}"
CRF="${3:-30}"

if [ ! -f "$INPUT" ]; then
  echo "ERROR: input file not found: $INPUT"
  exit 1
fi

# x265 线程池：默认吃满全部逻辑核；动态流水线可通过 X265_POOLS 按实时空闲核注入，
# 避免与同时运行的 FunASR 转写互相超订（见 video_dynamic_pipeline.sh 的 CPU 联合预算）。
CORES="${X265_POOLS:-$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 8)}"

echo "=== FFmpeg H.265 Compression ==="
echo "Input:    $INPUT ($(du -h "$INPUT" | cut -f1))"
echo "Output:   $OUTPUT"
echo "CRF:      $CRF"
echo "Cores:    $CORES"
echo ""

ffmpeg -y -i "$INPUT" \
  -map 0:v:0 -map 0:a:0 \
  -c:v libx265 -crf "$CRF" -preset fast \
  -x265-params "pools=${CORES}:frame-threads=4:wpp=1" \
  -c:a aac -b:a 96k \
  -tag:v hvc1 \
  -movflags +faststart \
  "$OUTPUT"

echo ""
echo "=== Compression Complete ==="
ls -lh "$OUTPUT" | awk '{print "Size:", $5}'

# Verify output
echo ""
echo "=== Verification ==="
DURATION_IN=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT" 2>/dev/null)
DURATION_OUT=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$OUTPUT" 2>/dev/null)
VCODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 "$OUTPUT" 2>/dev/null)
BITRATE=$(ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1 "$OUTPUT" 2>/dev/null)

echo "Input duration:  ${DURATION_IN}s"
echo "Output duration: ${DURATION_OUT}s"
echo "Video: $VCODEC"
echo "Bitrate: $((BITRATE / 1000)) kbps"

# Check duration difference.
# 容差 = max(3s, 输入时长×0.1%)：AAC 重编码 + MP4 容器首尾填充会让长视频出现数秒正常偏移，
# 用「绝对 3s 或相对千分之一取大者」既吸收正常偏移，又能拦住真正的截断（真损坏通常差几十秒以上）。
DUR_DIFF=$(echo "$DURATION_IN - $DURATION_OUT" | bc 2>/dev/null || echo "999")
DUR_DIFF_ABS=$(echo "${DUR_DIFF#-}" | bc 2>/dev/null || echo "999")
DUR_TOL=$(echo "t=$DURATION_IN*0.001; if(t<3) t=3; t" | bc -l)
if (( $(echo "$DUR_DIFF_ABS < $DUR_TOL" | bc -l) )); then
  echo "✅ Duration matches (diff ${DUR_DIFF_ABS}s < tol ${DUR_TOL}s)"
else
  echo "⚠️  Duration mismatch! Input=${DURATION_IN}s Output=${DURATION_OUT}s tol=${DUR_TOL}s"
  exit 1
fi

# Check moov atom (playability)
if ffprobe -v error "$OUTPUT" >/dev/null 2>&1; then
  echo "✅ File is valid and playable"
else
  echo "❌ File is invalid (moov atom missing or corrupt)"
  exit 1
fi
