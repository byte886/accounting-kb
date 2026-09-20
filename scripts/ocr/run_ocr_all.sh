#!/bin/bash
# run_ocr_all.sh — 批量 OCR 一门课「原始资源/notes」下全部讲义 PDF（串行，逐个调 batch_ocr.sh）
#
# 现行范式（会计/税法一致）：
#   PDF：原始资源/notes/<NN_讲名>/<title>.pdf
#   输出：同目录 <title>_OCR.md；已存在且非空则跳过。
#
# 引擎：RapidOCR PP-OCRv6（scripts/ocr/ocr_pdf_rapid.py）。
# 断点缓存：<pdf名>.pages/<N>.txt（在 PDF 同目录，跨 PDF 不串，无需清理）。
# 错峰：nice -n19 低优先级。
# 课程选择走 profile（见 course_config.sh）：
#   COURSE_PROFILE=cpa-accounting-2026 bash scripts/ocr/run_ocr_all.sh [--dry]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/course_config.sh"
COURSE="$COURSE_LOCAL_ROOT"
NOTES="$COURSE/原始资源/notes"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1

if [ ! -d "$NOTES" ]; then echo "[run_ocr] notes 目录不存在: $NOTES" >&2; exit 1; fi
if [ ! -x "$ROOT/.venv-ocr/bin/python" ]; then
  echo "[run_ocr] .venv-ocr 不存在。请先执行:" >&2
  echo "  /usr/local/bin/python3.12 -m venv $ROOT/.venv-ocr" >&2
  echo "  $ROOT/.venv-ocr/bin/pip install rapidocr onnxruntime pymupdf" >&2
  exit 1
fi
TODO=0; SKIP=0
find "$NOTES" -name '*.pdf' -print0 | sort -z | while IFS= read -r -d '' pdf; do
  out="${pdf%.pdf}_OCR.md"
  if [ -s "$out" ]; then echo "[已有] ${pdf#"$NOTES"/}"; SKIP=$((SKIP+1)); continue; fi
  TODO=$((TODO+1))
  echo "[待OCR] ${pdf#"$NOTES"/}"
  if [ "$DRY" -eq 0 ]; then
    echo "==== OCR 开始：$(basename "$pdf") $(date '+%H:%M:%S') ===="
    if bash "$ROOT/scripts/batch_ocr.sh" "$pdf"; then
      echo "==== OCR 完成：$(basename "$pdf") -> $(basename "$out") $(date '+%H:%M:%S') ===="
    else
      echo "[失败] $pdf（继续下一本）"
    fi
  fi
done
if [ "$DRY" -eq 1 ]; then echo "（--dry 仅列出计划，未实际 OCR）"; fi
