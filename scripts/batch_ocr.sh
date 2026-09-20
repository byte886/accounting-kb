#!/bin/bash
# 高顿课程PDF批量OCR脚本（RapidOCR PP-OCRv6 版，2026-09 起替换 macOS Vision）
#
# 用法:
#   bash scripts/batch_ocr.sh <PDF路径> [输出目录]
#   示例: bash scripts/batch_ocr.sh "课程/docs/讲义.pdf" "课程/docs"
#
# 实现：调用 scripts/ocr/ocr_pdf_rapid.py（RapidOCR PP-OCRv6 + PyMuPDF）。
# 原 macOS Vision 方案已退役；scripts/ocr/ocr_vision.swift 保留备查，不再默认调用。
# 断点续跑缓存：<pdf名>.pages/<N>.txt（与旧版 /tmp/gaodun_ocr_pages 不同，跨PDF不串）。

set -euo pipefail
# 兜底 UTF-8 locale
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 1 ]; then
  echo "用法: bash scripts/batch_ocr.sh <PDF路径> [输出目录]" >&2
  exit 1
fi
PDF_PATH="$1"
if [ $# -ge 2 ]; then OUTPUT_DIR="$2"; else OUTPUT_DIR="$(dirname "$PDF_PATH")"; fi

[ -f "$PDF_PATH" ] || { echo "[错误] PDF不存在: $PDF_PATH" >&2; exit 1; }

# 选 Python：项目 .venv-ocr（RapidOCR 装在这里）
VENV_PY="$PROJECT_DIR/.venv-ocr/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "[错误] .venv-ocr 不存在。请先执行:" >&2
  echo "  /usr/local/bin/python3.12 -m venv $PROJECT_DIR/.venv-ocr" >&2
  echo "  $PROJECT_DIR/.venv-ocr/bin/pip install rapidocr onnxruntime pymupdf" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)
OUTPUT_MD="$OUTPUT_DIR/$(basename "$PDF_PATH" .pdf)_OCR.md"

exec nice -n 19 "$VENV_PY" "$PROJECT_DIR/scripts/ocr/ocr_pdf_rapid.py" "$PDF_PATH" --out "$OUTPUT_MD"
