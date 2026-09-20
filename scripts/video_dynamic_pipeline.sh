#!/bin/bash
# video_dynamic_pipeline.sh — 视频「下载 / 压缩 / 转写」三阶段反馈式动态流水线
#
# 设计（与 docs/development/performance/parallel-processing-guide.md 一致）：
#   - 三阶段解耦成三个 worker 池，阶段间用【文件系统状态机】衔接，不靠 find -mmin 猜最新文件。
#   - 下载=网络 IO，并发度由「待压在制上限 K + 下载并发上限 D_MAX」反压驱动；
#   - 压缩/转写=CPU 密集，遵循项目实测铁律：x265、FunASR 都是【同任务单实例吞吐最优】，
#     故压缩池、转写池各自最多 1 个；但两类异构任务允许同时跑（压缩 N 与转写 N-1 重叠）。
#   - 【动态实时】每个 TICK 采样整机 ffmpeg/FunASR/OCR 已占用核数与 load，实时决定：
#     此刻是否起新 CPU worker、以及给 ffmpeg 分多少核（X265_POOLS），负载满就等、有空就补，
#     自动与讲义 OCR 等其它 CPU 任务互相避让，无需手工定死并发/核数。
#
# 状态机（编号 NN = idx-1，两位补零）：
#   TO_DOWNLOAD  工作区 dl-tmp/NN_*/.vfetch/merged.ts 不存在
#   TO_COMPRESS  工作区 dl-tmp/NN_*/.vfetch/merged.ts 已在（下载完待压）
#   TO_TRANSCRIBE 原始资源/videos/NN_*/video.mp4 在、transcript.md 不在（压完待转）
#   DONE         原始资源/videos/NN_*/transcript.md 在（成品级断点，重跑自动跳过）
#
# 过程件（.vfetch 分片/merged）一律落 $WS/dl-tmp，课程库根全程不出现讲目录（治理：过程件归 _workspace）。
#
# 用法：
#   bash scripts/video_dynamic_pipeline.sh [起始idx] [结束idx] [--dry-run]
#   --dry-run  只扫描一次并打印「此刻会启动什么」，不真正起进程、不循环（安全预览）
# 可调环境变量：TICK(轮询秒,15) K(待压在制上限,2) D_MAX(同时下载上限,2)
#               RESERVE(为系统预留核,4) MIN_COMPRESS(起压缩所需空闲核,8) MAXFAIL(单阶段重试上限,2)
#
# 注意：与旧 batch_video_pipeline.sh 二选一运行，切勿同时跑同一讲（都会改相同目录）。

set -uo pipefail

PROFILE="cpa-accounting-2026"
PROJECT_DIR="/Users/wenjiechen/Desktop/gaodun-course-knowledge-base"
WS="$PROJECT_DIR/data/_workspace/$PROFILE"
COURSE_ROOT="$PROJECT_DIR/data/高顿/CPA/【26考季】VIPCPA系列-会计（罗翔老师）"
VIDEOS="$COURSE_ROOT/原始资源/videos"
LOGD="$WS/logs"; RUND="$WS/run/dyn"; TMPBASE="$WS/dl-tmp"
VENV_PY="$PROJECT_DIR/transcription/venv/bin/python"
mkdir -p "$LOGD" "$RUND" "$TMPBASE"

TICK="${TICK:-15}"; K="${K:-2}"; D_MAX="${D_MAX:-2}"; RESERVE="${RESERVE:-4}"
MIN_COMPRESS="${MIN_COMPRESS:-8}"; MAXFAIL="${MAXFAIL:-2}"
DRY=0; START=""; END=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    *[!0-9]*) echo "未知参数: $a" >&2; exit 2 ;;
    *) [ -z "$START" ] && START="$a" || END="$a" ;;
  esac
done
START="${START:-18}"; END="${END:-46}"
LOGICAL=$(sysctl -n hw.logicalcpu)

padded(){ printf '%02d' "$1"; }
tmp_dir(){ find "$TMPBASE" -maxdepth 1 -type d -name "$1_*" 2>/dev/null | head -1; }
fin_dir(){ find "$VIDEOS" -maxdepth 1 -type d -name "$1_*" 2>/dev/null | head -1; }

# ---------- 单讲 worker（后台子shell 执行，日志各自独立）----------
do_dl() { # $1=idx
  cd "$PROJECT_DIR"
  node scripts/cdp/fetch_lecture_video.js "$1" --profile "$PROFILE" --work-base "$TMPBASE"
}
do_cmp() { # $1=NN  $2=x265 pools
  local nn="$1" pools="$2" t merged out raw lec
  t="$(tmp_dir "$nn")"; [ -z "$t" ] && { echo "找不到课程根在制目录 $nn"; exit 1; }
  merged="$t/.vfetch/merged.ts"; out="$t/.vfetch/video.mp4"
  [ -s "$merged" ] || { echo "merged.ts 缺失: $merged"; exit 1; }
  cd "$PROJECT_DIR"
  X265_POOLS="$pools" COMPRESS_NONINTERACTIVE=1 bash scripts/compress.sh "$merged" "$out" || exit 1
  rm -f "$merged"; rm -rf "$t/.vfetch/segments"
  lec="$(basename "$t")"; raw="$VIDEOS/$lec"; mkdir -p "$raw"
  if [ -s "$raw/video.mp4" ]; then rm -f "$out"; else mv "$out" "$raw/video.mp4"; fi
}
do_tr() { # $1=NN
  local nn="$1" fin ttmp t
  fin="$(fin_dir "$nn")"; [ -z "$fin" ] && { echo "找不到成品目录 $nn"; exit 1; }
  [ -s "$fin/video.mp4" ] || { echo "成品 video.mp4 缺失: $fin"; exit 1; }
  ttmp="$LOGD/.tt_$nn"; rm -rf "$ttmp"; mkdir -p "$ttmp"
  cd "$PROJECT_DIR"
  "$VENV_PY" scripts/transcribe_pipeline.py "$fin/video.mp4" "$ttmp" || { rm -rf "$ttmp"; exit 1; }
  [ -f "$ttmp/video/transcript.md" ] || { rm -rf "$ttmp"; exit 1; }
  cp "$ttmp/video/transcript.md" "$fin/transcript.md"
  cp "$ttmp/video/transcript.json" "$fin/transcript.json" 2>/dev/null || true
  rm -rf "$ttmp"; t="$(tmp_dir "$nn")"; [ -n "$t" ] && rm -rf "$t"
}

# 启动器：spawn <stage> <NN/idx> <额外参数>
spawn(){
  local stage="$1" key="$2" extra="${3:-}" pf
  pf="$RUND/${stage}_${key}.pid"
  if [ "$DRY" = 1 ]; then echo "    [dry-run] 将启动 $stage $key ${extra:+pools=$extra}"; return; fi
  case "$stage" in
    dl)  ( do_dl  "$key" ) > "$LOGD/dyn_dl_$key.log" 2>&1 & ;;
    cmp) ( do_cmp "$key" "$extra" ) > "$LOGD/dyn_cmp_$key.log" 2>&1 & ;;
    tr)  ( do_tr  "$key" ) > "$LOGD/dyn_tr_$key.log" 2>&1 & ;;
  esac
  echo $! > "$pf"
}
alive(){ local pf="$1"; [ -f "$pf" ] && kill -0 "$(cat "$pf")" 2>/dev/null; }
count_running(){ ls "$RUND/$1"_*.pid 2>/dev/null | while read -r p; do alive "$p" && echo x; done | wc -l | tr -d ' '; }
blocked(){ [ -f "$RUND/blocked_$1_$2" ]; }

# 实时 CPU 采样：累加整机 ffmpeg / FunASR / OCR 占用核，动态算空闲核与是否超订
sample_cpu(){
  USED=$(ps -axo %cpu,comm 2>/dev/null | awk '/ffmpeg|transcribe_pipeline|ocr_vision/ && !/awk/{s+=$1} END{printf "%.1f", s/100}')
  FREE=$(awk -v l="$LOGICAL" -v r="$RESERVE" -v u="$USED" 'BEGIN{printf "%.1f", l-r-u}')
  LOAD1=$(sysctl -n vm.loadavg | awk '{print $2}')
  OVER=$(awk -v a="$LOAD1" -v l="$LOGICAL" 'BEGIN{print (a>l)?1:0}')
}

# 扫描一讲状态，回显到全局 STATE_*
scan(){ # $1=idx；讲目录编号 NN = idx-1（idx 从 1 起，目录前缀从 00 起）
  local nn fin tmp
  nn="$(padded "$(( $1 - 1 ))")"; fin="$(fin_dir "$nn")"; tmp="$(tmp_dir "$nn")"
  NN="$nn"
  if [ -n "$fin" ] && [ -s "$fin/transcript.md" ]; then STATE=DONE
  elif [ -n "$fin" ] && [ -s "$fin/video.mp4" ]; then STATE=TO_TRANSCRIBE
  elif [ -n "$tmp" ] && [ -s "$tmp/.vfetch/merged.ts" ]; then STATE=TO_COMPRESS
  else STATE=TO_DOWNLOAD; fi
}

# reap：清理已结束 pidfile；阶段没推进则累计失败，超上限拉黑
reap(){
  local pf stage key pid fail n
  for pf in "$RUND"/*.pid; do
    [ -e "$pf" ] || continue
    stage="$(basename "$pf" | cut -d_ -f1)"; key="$(basename "$pf" .pid | cut -d_ -f2-)"
    pid="$(cat "$pf")"; kill -0 "$pid" 2>/dev/null && continue
    # 进程已结束，判断是否推进
    local advanced=0
    case "$stage" in
      dl)  idx=$((10#$key+1)); scan "$idx"; [ "$STATE" = TO_COMPRESS ] || [ "$STATE" = TO_TRANSCRIBE ] || [ "$STATE" = DONE ] && advanced=1 ;;
      cmp) scan $((10#$key+1)); { [ "$STATE" = TO_TRANSCRIBE ] || [ "$STATE" = DONE ]; } && advanced=1 ;;
      tr)  scan $((10#$key+1)); [ "$STATE" = DONE ] && advanced=1 ;;
    esac
    rm -f "$pf"
    if [ "$advanced" = 1 ]; then rm -f "$RUND/${stage}_${key}.fail"
    else
      fail="$RUND/${stage}_${key}.fail"; n=$(( $(cat "$fail" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$fail"
      [ "$n" -ge "$MAXFAIL" ] && { touch "$RUND/blocked_${stage}_${key}"; echo "  ⚠️ $stage $key 连续 $n 次未推进，拉黑待人工: $LOGD/dyn_${stage}_${key}.log"; }
    fi
  done
}

# 结束清扫（幂等兜底，绝不误删在制）：只把「成品 transcript 已在 videos、却漏删」的 NN_讲名 残留
# 移到 macOS 废纸篓（带时间戳，不硬删）；成品未齐＝在制/blocked，一律保留并列出，交人工。
# 同时扫两个基准：旧契约残留落在课程根、新契约落在 $TMPBASE（dl-tmp）。
sweep_base(){ # $1=基准目录  $2=标签
  local base="$1" tag="$2" d nn fin stamp moved=0 kept=0 keptlist=""
  for d in "$base"/[0-9][0-9]_*/; do
    [ -d "$d" ] || continue
    d="${d%/}"; nn="$(basename "$d" | cut -c1-2)"; fin="$(fin_dir "$nn")"
    if [ -n "$fin" ] && [ -s "$fin/transcript.md" ]; then
      if [ "$DRY" = 1 ]; then echo "    [dry-run][sweep:$tag] 将移废纸篓(成品已完成的漏删残留): $(basename "$d")"; moved=$((moved+1)); else
        stamp=$(date +%Y%m%d%H%M%S)
        mv "$d" "$HOME/.Trash/$(basename "$d")__sweep__$stamp" && { echo "  [sweep:$tag] 漏删残留已移废纸篓: $(basename "$d")"; moved=$((moved+1)); }
      fi
    else kept=$((kept+1)); keptlist="$keptlist $(basename "$d")"; fi
  done
  echo "  [sweep:$tag] 移废纸篓 $moved，保留(在制/blocked) $kept${keptlist:+ ->$keptlist}"
}
sweep_course_root(){ sweep_base "$COURSE_ROOT" "课程根"; sweep_base "$TMPBASE" "工作区"; }

tick_once(){
  reap; sample_cpu
  local todo_dl="" todo_cmp="" todo_tr="" n_done=0 idx nn
  for idx in $(seq "$START" "$END"); do
    scan "$idx"; nn="$NN"
    case "$STATE" in
      DONE) n_done=$((n_done+1)) ;;
      TO_DOWNLOAD)   blocked dl  "$nn" || todo_dl="$todo_dl $idx" ;;
      TO_COMPRESS)   blocked cmp "$nn" || todo_cmp="$todo_cmp $nn" ;;
      TO_TRANSCRIBE) blocked tr  "$nn" || todo_tr="$todo_tr $nn" ;;
    esac
  done
  local rdl rcmp rtr; rdl=$(count_running dl); rcmp=$(count_running cmp); rtr=$(count_running tr)
  local actions=""
  # 1) 转写优先（FunASR 单实例，仅需 2 核空闲）
  if [ "$rtr" = 0 ] && [ -n "$todo_tr" ] && [ "$OVER" = 0 ] && \
     awk -v f="$FREE" 'BEGIN{exit !(f>=2)}'; then
    local k=$(echo $todo_tr | awk '{print $1}'); spawn tr "$k"; actions="$actions tr:$k"
  fi
  # 2) 压缩（x265 单实例，需足够空闲核；pools 按实时空闲动态算并 clamp 6..16）
  if [ "$rcmp" = 0 ] && [ -n "$todo_cmp" ] && [ "$OVER" = 0 ] && \
     awk -v f="$FREE" -v m="$MIN_COMPRESS" 'BEGIN{exit !(f>=m)}'; then
    local k=$(echo $todo_cmp | awk '{print $1}')
    local reserve_tr=2; # 给可能并行的转写预留 2 核
    local pools=$(awk -v f="$FREE" -v r="$reserve_tr" 'BEGIN{p=int(f-r+0.5); if(p<6)p=6; if(p>16)p=16; print p}')
    spawn cmp "$k" "$pools"; actions="$actions cmp:$k(pools=$pools)"
  fi
  # 3) 下载（反压：下载领先压缩的在制 < K；同时下载 ≤ D_MAX）
  # K 只卡「下载领先压缩」：TO_COMPRESS（merged 就绪，含正在压的——压缩完成才删 merged）
  # + 正在下载(rdl)。已压完待转 TO_TRANSCRIBE 已流过压缩关、rcmp 已含在 TO_COMPRESS，都不计入，避免重复占槽。
  local queued=$(( $(echo $todo_cmp | wc -w) + rdl ))
  if [ "$rdl" -lt "$D_MAX" ] && [ "$queued" -lt "$K" ] && [ -n "$todo_dl" ]; then
    local k=$(echo $todo_dl | awk '{print $1}'); spawn dl "$k"; actions="$actions dl:$k"
  fi
  printf '[%s] DONE %d/%d | 待下%s 待压%s 待转%s | 在跑 dl=%s cmp=%s tr=%s | used=%s核 free=%s核 load=%s |%s\n' \
    "$(date '+%H:%M:%S')" "$n_done" "$((END-START+1))" \
    "[$todo_dl ]" "[$todo_cmp ]" "[$todo_tr ]" "$rdl" "$rcmp" "$rtr" "$USED" "$FREE" "$LOAD1" "${actions:-（本tick不新增）}"
  # 终止条件
  local total=$((END-START+1))
  if [ "$n_done" = "$total" ] && [ -z "$(ls "$RUND"/*.pid 2>/dev/null)" ]; then echo "ALL_DONE"; sweep_course_root; return 1; fi
  local nb=$(ls "$RUND"/blocked_* 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n_done" -lt "$total" ] && [ -z "$todo_dl$todo_cmp$todo_tr" ] && [ "$rdl$rcmp$rtr" = "000" ]; then
    echo "STALLED：剩余未完成但无在跑、无待办（可能全部被拉黑），blocked=$nb"; sweep_course_root; return 1
  fi
  return 0
}

echo "=== 动态视频流水线 idx=$START..$END 逻辑核=$LOGICAL 预留=$RESERVE K=$K D_MAX=$D_MAX dry=$DRY ==="
if [ "$DRY" = 1 ]; then
  sample_cpu
  echo "[实时] used=${USED}核 free=${FREE}核 load1=$LOAD1 over=$OVER"
  tick_once
  echo "(dry-run 仅扫描一次，未启动任何进程)"
  exit 0
fi
while true; do
  tick_once || { echo "主控退出于 $(date '+%F %T')"; break; }
  sleep "$TICK"
done
