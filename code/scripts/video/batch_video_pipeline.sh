#!/bin/bash
# 会计课全量视频下载+压缩+转写批量脚本
# 处理 idx=2 到 44（43个精讲章节）
# 支持断点续跑：已完成的章节跳过

set -euo pipefail

PROFILE="cpa-accounting-2026"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_DIR/data/_workspace/$PROFILE/logs"
mkdir -p "$LOG_DIR"

START_IDX=${1:-2}
END_IDX=${2:-44}
COURSE_ROOT="$PROJECT_DIR/data/高顿/CPA/【26考季】VIPCPA系列-会计（罗翔老师）"
# 下载/压缩过程件（.vfetch 分片/merged）统一落工作区，课程库根不留讲目录（成品才进 原始资源/videos）
TMPBASE="$PROJECT_DIR/data/_workspace/$PROFILE/dl-tmp"
mkdir -p "$TMPBASE"

echo "=== 会计课全量视频下载+压缩+转写 ==="
echo "Profile: $PROFILE"
echo "章节范围: idx=$START_IDX 到 $END_IDX"
echo "日志目录: $LOG_DIR"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo

for idx in $(seq $START_IDX $END_IDX); do
  echo "=========================================="
  echo "[$(date '+%H:%M:%S')] 处理章节 idx=$idx"
  echo "=========================================="
  
  LOG_FILE="$LOG_DIR/video_idx_${idx}.log"

  # 断点续跑（成品级）：原始资源/videos/<idx-1>_*/transcript.md 已存在则整讲跳过，不重复抓取
  PREFIX="$(printf '%02d' $((idx-1)))"
  DONE_DIR=$(find "$COURSE_ROOT/原始资源/videos" -maxdepth 1 -type d -name "${PREFIX}_*" 2>/dev/null | head -1)
  if [ -n "$DONE_DIR" ] && [ -s "$DONE_DIR/transcript.md" ]; then
    echo "  ⏭️  idx=$idx 已完成（$(basename "$DONE_DIR") 已有 transcript），跳过"
    continue
  fi
  
  # 步骤1：下载视频（fetch_lecture_video.js 退出码：0=成功，3=平台未上线"待学习"跳过，1=真失败）
  echo "  [1/4] 下载视频..."
  cd "$PROJECT_DIR"
  set +e
  node scripts/cdp/fetch_lecture_video.js "$idx" --profile "$PROFILE" --work-base "$TMPBASE" > "$LOG_FILE" 2>&1
  fetch_rc=$?
  set -e
  if [ "$fetch_rc" -eq 3 ]; then
    echo "  ⏳ idx=$idx 平台未上线（待学习），跳过；上线后重跑本脚本即断点续做"
    continue
  elif [ "$fetch_rc" -ne 0 ]; then
    echo "  ❌ 视频下载失败(rc=$fetch_rc)，详见 $LOG_FILE"
    continue
  fi
  echo "  ✅ 视频下载完成"
  
  # 查找下载的merged.ts（取最新的一个）
  MERGED_TS=$(find "$TMPBASE" -name "merged.ts" -mmin -10 2>/dev/null | head -1)
  if [ -z "$MERGED_TS" ]; then
    MERGED_TS=$(find "$TMPBASE" -name "merged.ts" 2>/dev/null | head -1)
  fi
  
  if [ -z "$MERGED_TS" ]; then
    echo "  ❌ 未找到merged.ts，详见 $LOG_FILE"
    continue
  fi
  
  VIDEO_DIR=$(dirname "$MERGED_TS")
  OUTPUT_MP4="$VIDEO_DIR/video.mp4"

  LEC_DIR="$(dirname "$VIDEO_DIR")"              # .vfetch 的父目录 = dl-tmp/NN_讲名（工作区）
  LEC_NAME="$(basename "$LEC_DIR")"
  RAW_DIR="$COURSE_ROOT/原始资源/videos/$LEC_NAME"  # 税法同款成品归位
  VENV_PY="$PROJECT_DIR/code/venvs/transcription/bin/python"

  # 步骤2：压缩（先压到 .vfetch/video.mp4）
  echo "  [2/4] 压缩视频 (merged.ts -> video.mp4)..."
  if ! bash scripts/compress.sh "$MERGED_TS" "$OUTPUT_MP4" >> "$LOG_FILE" 2>&1; then
    echo "  ❌ 视频压缩失败，详见 $LOG_FILE"; continue
  fi
  [ -s "$OUTPUT_MP4" ] || { echo "  ❌ 压缩产物为空，详见 $LOG_FILE"; continue; }
  echo "  ✅ 视频压缩完成"

  # 压缩成功即清原始流（merged.ts + segments 分片），不依赖后续转写成败，避免残留占盘
  rm -f "$MERGED_TS"; rm -rf "$VIDEO_DIR/segments"

  # 步骤3：归位到 原始资源/videos/<讲名>/（课程根不留散落讲目录）
  echo "  [3/4] 归位 -> 原始资源/videos/$LEC_NAME"
  mkdir -p "$RAW_DIR"
  if [ -s "$RAW_DIR/video.mp4" ]; then rm -f "$OUTPUT_MP4"; else mv "$OUTPUT_MP4" "$RAW_DIR/video.mp4"; fi
  if [ -s "$RAW_DIR/transcript.md" ]; then
    rm -rf "$LEC_DIR"
    echo "  ✅ idx=$idx 全部完成（已有转写，直接清理工作目录）"; echo; continue
  fi

  # 步骤4：转写（必须用 venv python；funasr 只在 venv，系统 python3 会 ModuleNotFoundError）
  echo "  [4/4] 转写（venv FunASR）..."
  TTMP="$LOG_DIR/.tt_$idx"; rm -rf "$TTMP"; mkdir -p "$TTMP"
  if "$VENV_PY" scripts/transcribe_pipeline.py "$RAW_DIR/video.mp4" "$TTMP" >> "$LOG_FILE" 2>&1 \
     && [ -f "$TTMP/video/transcript.md" ]; then
    cp "$TTMP/video/transcript.md" "$RAW_DIR/transcript.md"
    cp "$TTMP/video/transcript.json" "$RAW_DIR/transcript.json"
    rm -rf "$TTMP" "$LEC_DIR"
    echo "  ✅ 视频转写完成，章节 idx=$idx 全部完成（已归位+转写+清理）"
  else
    rm -rf "$TTMP"
    echo "  ⚠️ 转写失败（成品已归位，可事后用 transcribe_all.sh 断点补跑），详见 $LOG_FILE"
  fi
  echo
done

echo "=========================================="
echo "全部章节处理完成"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
