#!/bin/bash
# 一键查询后台长任务进度（只读，不影响任务运行）
# 用法: bash scripts/progress.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
# shellcheck source=course_config.sh
source "$PROJECT_DIR/scripts/course_config.sh"   # 导出 COURSE_LOCAL_ROOT 等，换课设 COURSE_PROFILE
RP="${COURSE_PROFILE:-${GAODUN_COURSE_PROFILE:-_shared}}"
RD="data/_workspace/$RP/logs"                      # 运行断点/日志统一进工作区，仓库根不产生 logs/
export RAW_DONE_DIR="$RD/raw_done" WIKI_DONE_DIR="$RD/wiki_done" SUP_VIDEOS_LOG="$RD/supervisor_videos.log"

bar() {
  # $1=已完成 $2=总数
  local done=$1 total=$2 width=30
  local filled=$(( done * width / total ))
  local empty=$(( width - filled ))
  local pct=0
  [ "$total" -gt 0 ] && pct=$(( done * 100 / total ))
  printf "["
  [ "$filled" -gt 0 ] && printf '█%.0s' $(seq 1 $filled 2>/dev/null)
  [ "$empty" -gt 0 ] && printf '░%.0s' $(seq 1 $empty 2>/dev/null)
  printf "] %d%% (%d/%d)" "$pct" "$done" "$total"
}

echo "═══════════════════════════════════════════════════"
echo " 后台任务进度  $(date '+%H:%M:%S')"
echo "═══════════════════════════════════════════════════"

# ---- videos ----
v_done=$(find "$RD/raw_done" -name 'videos_*.done' 2>/dev/null | wc -l | tr -d ' ')
v_total=39
echo ""
echo "📹 视频上传网盘"
echo "   $(bar "$v_done" "$v_total")"
if [ "$v_done" -lt "$v_total" ]; then
  if pgrep -f run_supervised.sh >/dev/null 2>&1; then
    echo "   状态: 🟢 守护器运行中"
  else
    echo "   状态: 🔴 守护器未运行（任务可能已结束或异常）"
  fi
  # ETA：基于最近完成的 done 文件时间戳与剩余视频大小估算
  python3 - <<'PY' 2>/dev/null
import os
from pathlib import Path
from datetime import datetime, timedelta
PARALLEL=2
base = Path(os.environ["COURSE_LOCAL_ROOT"])/"原始资源/videos"
ddir = Path(os.environ["RAW_DONE_DIR"])
done = set(f.stem[len("videos_"):] for f in ddir.glob("videos_*.done"))
def sz(d):
    p=d/"video.mp4"; return p.stat().st_size if p.exists() else 0
dones = sorted(ddir.glob("videos_*.done"), key=lambda f:f.stat().st_mtime)[-9:]
if len(dones)>=3:
    span = dones[-1].stat().st_mtime - dones[0].stat().st_mtime
    recent_names=[f.stem[len("videos_"):] for f in dones]
    n=len(dones)
    sent=sum(sz(d) for d in base.iterdir() if d.is_dir() and d.name in recent_names)
    rate = sent/span if span>0 else 0          # 并发合计速率
    avg_sz = sent/n                             # 平均每个大小
    single_rate = rate/PARALLEL                 # 单路速率
    wall_each = span/n                          # 并发下平均每个墙钟时间
    remain=sum(sz(d) for d in base.iterdir() if d.is_dir() and d.name not in done)
    if rate>0:
        eta=remain/rate
        fin=datetime.now()+timedelta(seconds=eta)
        single_min=avg_sz/single_rate/60
        print(f"   速率: {rate/1024/1024:.1f} MB/s（并发{PARALLEL}合计，单路 {single_rate/1024/1024:.1f}）")
        print(f"   均个: {avg_sz/1024/1024:.0f}MB，单个传 {single_min:.1f} 分钟，并发下均 {wall_each/60:.1f} 分钟完成1个")
        print(f"   剩余: {remain/1024/1024/1024:.1f}G，预计还需 {eta/60:.0f} 分钟，约 {fin.strftime('%H:%M')} 完成")
PY
  echo "   正在上传:"
  ps aux | grep baidu_upload | grep -v grep | grep -oE 'videos/[^/]+' | sort -u | sed 's/^/     - /'
else
  echo "   状态: ✅ 全部完成"
fi

# ---- notes ----
n_done=$(find "$RD/raw_done" -name 'notes_*.done' 2>/dev/null | wc -l | tr -d ' ')
n_total=17
echo ""
echo "📝 讲义笔记上传网盘"
echo "   $(bar "$n_done" "$n_total")"

# ---- 飞书 ----
w_done=$(find "$RD/wiki_done" -name '*.done' 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "📚 飞书知识库同步"
echo "   $(bar "$w_done" 107)"

echo ""
echo "═══════════════════════════════════════════════════"
echo " 最近日志（videos 守护器）:"
tail -3 "$SUP_VIDEOS_LOG" 2>/dev/null | sed 's/^/   /'
echo "═══════════════════════════════════════════════════"
