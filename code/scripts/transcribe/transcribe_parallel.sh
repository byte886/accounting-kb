#!/bin/bash
# transcribe_parallel.sh — FunASR 批量转写，xargs -P 任务队列式动态调度（内核分发，无锁竞态）。
#
# FunASR(SenseVoiceSmall) 实测【串行总吞吐最优】：1 并发 18.5x，6 并发仅 14.3x（单进程已吃 2 核，
# 多开因内存带宽/cache 争用反而更慢，见 docs/development/performance/parallel-processing-guide.md）。
# 故默认并发 1；确需覆盖可传参，但换机器/模型后应按指南重测，不要凭核数估算。
#
# 断点续跑：讲目录已有 >1000 字 transcript.md 自动跳过；单讲失败不阻塞其余，结束后汇总未完成，
# 重跑本脚本即可续（幂等，不做自动 requeue 以免坏任务无限重试）。
# 用法:
#   bash scripts/transcribe_parallel.sh [并发N]        # 默认 1（串行）
#   bash scripts/transcribe_parallel.sh --worker <讲目录>   # 内部 worker（parallel_map 调用，勿手动）
set -uo pipefail
# 兜底 UTF-8 locale：后台/C locale 下 $VAR 紧跟中文会被并入变量名而报 unbound
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/code/venvs/transcription/bin/python"
PIPE="$ROOT/scripts/transcribe_pipeline.py"
# 加载课程配置（环境变量可覆盖默认值）
# shellcheck source=course_config.sh
source "$ROOT/scripts/course_config.sh"
# shellcheck source=lib/parallel.sh
source "$ROOT/scripts/lib/parallel.sh"
COURSE="$COURSE_DESKTOP_ROOT"
RP="${COURSE_PROFILE:-${GAODUN_COURSE_PROFILE:-_shared}}"
WORK="$ROOT/data/_workspace/$RP/tmp/parallel_work"   # 并行任务队列工作区（过程件，不入库）
LOGDIR="$ROOT/data/_workspace/$RP/logs"
mkdir -p "$WORK" "$LOGDIR"

# ---------- 单讲 worker（自递归，任务=讲目录，作为最后参数 $2 传入） ----------
if [ "${1:-}" = "--worker" ]; then
  d="$2"; prefix=$(basename "$d" | cut -c1-2)
  tmp="$WORK/w_${prefix}_$$"; rm -rf "$tmp"; mkdir -p "$tmp"
  if "$PY" "$PIPE" "$d/video.mp4" "$tmp" > "$LOGDIR/${prefix}.log" 2>&1 \
     && [ -f "$tmp/video/transcript.md" ]; then
    cp "$tmp/video/transcript.md" "$d/transcript.md"
    cp "$tmp/video/transcript.json" "$d/transcript.json" 2>/dev/null || true
    rm -rf "$tmp"; echo "✓ $(basename "$d") ($(wc -m < "$d/transcript.md")字)"; exit 0
  fi
  rm -rf "$tmp"; echo "✗ $(basename "$d")（见 $LOGDIR/${prefix}.log）"; exit 1
fi

# ---------- 主流程：生成 NUL 分隔队列 ----------
N="${1:-1}"
QUEUE="$WORK/pending.nul"; : > "$QUEUE"
shopt -s nullglob
for d in "$COURSE"/[0-9][0-9]_*; do
  [ -f "$d/video.mp4" ] || continue
  if [ -f "$d/transcript.md" ] && [ "$(wc -m < "$d/transcript.md")" -gt 1000 ]; then continue; fi
  printf '%s\0' "$d" >> "$QUEUE"
done
TOTAL=$(tr -cd '\0' < "$QUEUE" | wc -c | tr -d ' ')
echo "==== 转写开始 $(date '+%F %T') 待转写 ${TOTAL} 讲 并发 ${N}（FunASR 默认串行最优）===="

if [ "$TOTAL" -eq 0 ]; then
  echo "没有待转写讲（全部已有 >1000 字 transcript），结束。"
  exit 0
fi

# xargs -P 内核级调度；任一失败 xargs 返回 123，但不影响其它任务继续
parallel_map "$N" bash "$0" --worker < "$QUEUE"
RC=$?

DONE=$(find "$COURSE" -maxdepth 2 -name transcript.md -size +1000c 2>/dev/null | wc -l | tr -d ' ')
echo "==== 转写结束 $(date '+%F %T') 课程库成品 $DONE 份 ===="
[ "$RC" -eq 0 ] || echo "⚠️ 有讲失败（xargs rc=${RC}），查看 ${LOGDIR} 后重跑本脚本即可续。"
exit "$RC"
