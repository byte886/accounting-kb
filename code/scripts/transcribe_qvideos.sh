#!/bin/bash
# transcribe_qvideos.sh — 题目级讲解视频批量转写（FunASR，xargs -P 内核调度，无锁竞态）。
# 与 transcribe_parallel.sh 的区别：对象是 data/_workspace/<profile>/tmp/download/sprint-videos/题目级讲解/qvideo_*/video.mp4，
# 临时目录用 vid 目录名唯一化（transcribe_one.sh 取首段前缀会都变成 qvideo 而撞车）。
# 题目级视频属税法冲刺专属数据（路径固定）；但 FunASR 转写机制与课程无关，实测串行总吞吐最优
# （18.5x > 6 并发 14.3x，见 parallel-processing-guide.md），默认并发 1，可传参覆盖。
# 用法:
#   bash scripts/transcribe_qvideos.sh [并发N]
#   bash scripts/transcribe_qvideos.sh --worker <qvideo目录>   # 内部 worker，勿手动
set -uo pipefail
# 兜底 UTF-8 locale：后台/C locale 下 $VAR 紧跟中文会被并入变量名而报 unbound
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/code/venvs/transcription/bin/python"
PIPE="$ROOT/scripts/transcribe_pipeline.py"
# shellcheck source=lib/parallel.sh
source "$ROOT/scripts/lib/parallel.sh"
RP="${GAODUN_COURSE_PROFILE:-cpa-tax-2026}"
SRC="$ROOT/data/_workspace/$RP/tmp/download/sprint-videos/题目级讲解"
WORK="$ROOT/data/_workspace/$RP/tmp/qv_work"
LOGDIR="$ROOT/data/_workspace/$RP/logs"
mkdir -p "$WORK" "$LOGDIR"

# ---------- 单个 qvideo worker（自递归，目录作为最后参数 $2） ----------
if [ "${1:-}" = "--worker" ]; then
  d="$2"; tag=$(basename "$d")
  tmp="$WORK/w_${tag}_$$"; rm -rf "$tmp"; mkdir -p "$tmp"
  if "$PY" "$PIPE" "$d/video.mp4" "$tmp" > "$LOGDIR/${tag}.log" 2>&1 \
     && [ -f "$tmp/video/transcript.md" ]; then
    cp "$tmp/video/transcript.md" "$d/transcript.md"
    cp "$tmp/video/transcript.json" "$d/transcript.json" 2>/dev/null || true
    rm -rf "$tmp"; echo "✓ ${tag} ($(wc -m < "$d/transcript.md")字)"; exit 0
  fi
  rm -rf "$tmp"; echo "✗ ${tag} (见 ${LOGDIR}/${tag}.log)"; exit 1
fi

# ---------- 主流程：NUL 分隔队列 ----------
N="${1:-1}"
QUEUE="$WORK/pending.nul"; : > "$QUEUE"
shopt -s nullglob
for d in "$SRC"/qvideo_*/; do
  [ -f "$d/video.mp4" ] || continue
  if [ -f "$d/transcript.md" ] && [ "$(wc -m < "$d/transcript.md")" -gt 1000 ]; then continue; fi
  printf '%s\0' "$d" >> "$QUEUE"
done
TOTAL=$(tr -cd '\0' < "$QUEUE" | wc -c | tr -d ' ')
echo "==== 题目级转写开始 $(date '+%F %T') 待转 ${TOTAL} 并发 ${N}（FunASR 默认串行最优）===="

if [ "$TOTAL" -eq 0 ]; then
  echo "没有待转 qvideo（全部已有 >1000 字 transcript），结束。"
  exit 0
fi

parallel_map "$N" bash "$0" --worker < "$QUEUE"
RC=$?
echo "==== 结束 $(date '+%F %T') ===="
ls "$SRC"/qvideo_*/transcript.md 2>/dev/null | wc -l | xargs echo "已生成 transcript 数:"
[ "$RC" -eq 0 ] || echo "⚠️ 有 qvideo 失败（xargs rc=${RC}），查看 ${LOGDIR} 后重跑即可续。"
exit "$RC"
