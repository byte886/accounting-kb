#!/bin/bash
# 本机名师课「压缩 + 网盘上传」常驻保活总管（由 launchd LaunchAgent 托管，抗 Doubao 会话清理）。
# 每 120 秒巡检：
#  - 压缩：无 compress 进程且 税法/经济法 仍有 h264 → 起压缩（倒序 jobs17，flock 单实例不双开）；
#  - 上传：整机无 sync 进程时，审计（已全hevc）优先传；其余科目【按科滚动】——某科全 hevc 且
#          当前没在压该科（该科 videos 下无 .compress_tmp 临时文件）即可传该科，不等其它科压缩结束
#          （上传走网络/限速、压缩吃 CPU，目录按 profile 隔离，可与另一科压缩并行）；
#          上传一律 并发1 + BAIDU_UPLOAD_RATE=1100k（实测上行34.6Mbps、满载延迟1.5s，两台各1100k
#          最坏合计占上行~52%，留余量给豆包/交互），整机一次只传一科；
#          科目全 hevc 首次上传前自动清“视频阶段”旧 done（保留讲义标记），强制 hevc 覆盖网盘旧 h264；
#  - 全部科目 hevc 且三科上传成功结束 → exit 0（launchd 配 SuccessfulExit=false，正常完成不重启、异常被杀才自愈）。
# 已在跑的同类 nohup 进程会被识别并跳过，不重复拉起，可平滑接管。
#
# 【运维注意】压缩是本总管 nohup 拉起的子进程，launchd unload/reload 会连坐杀掉它（幂等可恢复，但中断当前文件）。
#   压缩在跑时不要 reload；改本脚本后，等税法/经济法压缩自然结束（comp_running=false）再 reload 一次，
#   让新逻辑（log_done 修复、清视频旧 done）接管上传收尾。2026-09-16。
set -u
SD="$(cd "$(dirname "$0")" && pwd)"; RR="$(dirname "$SD")"; cd "$RR" || exit 1
export PATH=/usr/local/bin:$PATH
export BAIDU_ENC_PASS=lover123
export BAIDU_UPLOAD_RATE=1100k   # 单路上行≤约1.1MB/s；两台同时传最坏合计占上行~52%（上行34.6Mbps，留余量给豆包）
JOBS=13  # 闲时偏高档（20核留7核）；白天交付高峰用8，夜间满档17
FLAGDIR="data/_workspace/_account/ep3/supervisor"; mkdir -p "$FLAGDIR" logs
# 只认真正的执行进程（命令行带解释器前缀 python3/bash）；不要裸 pgrep -f 脚本名，
# 否则会匹配到仅在命令行里出现该脚本名字面的 grep/外层 shell，误判“在跑”而漏拉（2026-09-17 踩过）。
comp_running(){ pgrep -f 'python3 .*compress_ep3_videos\.py' >/dev/null 2>&1; }
up_running(){ pgrep -f 'bash .*sync_ep3_ready\.sh' >/dev/null 2>&1; }
# 某科是否正在被压缩写：该科 videos 下存在 .compress_tmp* 临时文件即视为在压（按科滚动上传用）。
# 一个 compress 进程可能同时带 --course 税法 --course 经济法，不能用进程名判断某科，只认真实临时文件。
compressing_course(){
  local d
  for d in data/高顿/CPA/*"名师专业课"*"$1"*/原始资源/videos; do
    [ -d "$d" ] || continue
    find "$d" -name '.compress_tmp*' -print -quit 2>/dev/null | grep -q . && return 0
  done
  return 1
}
up_done(){ [ -f "$FLAGDIR/$1.done" ]; }
mark_done(){ date > "$FLAGDIR/$1.done"; echo "[$(date '+%F %T')] $1 标记上传完成"; }
nothevc(){ # 压缩在跑时不调用（结果不可能已全hevc）；$1=科目
python3 - "$1" <<'PY'
import sys,subprocess,pathlib,concurrent.futures as cf
kw=sys.argv[1]; root=pathlib.Path("data/高顿/CPA")
d=next((p for p in root.iterdir() if "名师专业课" in p.name and kw in p.name),None)
if not d: print(-1); sys.exit()
v=list((d/"原始资源"/"videos").rglob("*_video.mp4"))
def cc(p):
    r=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=codec_name","-of","csv=p=0",str(p)],capture_output=True,text=True)
    return r.stdout.strip()
with cf.ThreadPoolExecutor(12) as ex: c=list(ex.map(cc,v))
print(sum(1 for x in c if x!="hevc"))
PY
}
log_done(){ # $1=日志路径；只认【最后一轮】（最后一个 “[ep3-ready] profile=” 到文件尾）：
  # 该区间含“本轮结束”且无真失败行（行首恰好 3 空格+“- 讲名”）才返回 0。日志是跨轮 >> 累积，早期轮次的
  # 瞬时失败（后来已重传成功）会留在文件前部；若扫整份日志会被这些历史失败行永久卡住、永不 mark_done 并每轮
  # 空转重拉（2026-09-18 经济法 189 讲已齐、却因第 345-347 行历史失败反复重拉的教训）。无 profile 标记的旧日志退化全文判断。
  [ -f "$1" ] || return 1
  local seg
  # LC_ALL=C：日志里混入 GBK/坏字节中文时，awk/grep 在 UTF-8 区域会报 multibyte/towc 警告，
  # 强制 C 区域按字节处理，保证"最后一轮"切分与失败行判定稳定（目标机看门 2026-09-18 已加，本机补齐）。
  seg="$(LC_ALL=C awk '/\[ep3-ready\] profile=/{buf=""} {buf=buf $0 ORS} END{print buf}' "$1")"
  printf '%s\n' "$seg" | LC_ALL=C grep -q "本轮结束" || return 1
  if printf '%s\n' "$seg" | LC_ALL=C grep -qE '^[[:space:]]{3}- '; then return 1; fi
  return 0
}
start_compress(){
  mkdir -p logs data/_workspace/_account/ep3/logs   # 拉起前重建日志目录：运行中 logs/ 若被（跨窗口清理）删掉，>> 重定向会静默失败、子进程不起（2026-09-19 税法因此空转 3.5h）
  nohup nice -n 20 caffeinate -dimsu python3 scripts/compress_ep3_videos.py --course 税法 --course 经济法 --reverse --jobs "$JOBS" >> data/_workspace/_account/ep3/logs/compress_ep3.log 2>&1 &
  echo "[$(date '+%F %T')] 已拉起压缩(税法+经济法 倒序 jobs=$JOBS)"; sleep 15
}
start_upload(){ mkdir -p logs; nohup caffeinate -dimsu bash scripts/sync_ep3_ready.sh "$1" 1 videos >> "logs/netdisk_$1.log" 2>&1 & echo "[$(date '+%F %T')] 已拉起上传 $1（限速1100k/并发1）"; sleep 10; }
# 科目已全 hevc、首次上传前：清“视频阶段”旧 done（保留 notes__ 讲义标记），强制所有视频以 hevc
# 重传并 rtype=3 覆盖网盘旧 h264；每科只清一次（<prof>.videoreset 标志）。done 名前缀是阶段名（非字面 videos）。
reset_videos_done_once(){
  local prof="$1" flag="$FLAGDIR/$1.videoreset" d="data/_workspace/$1/logs/netdisk_done" n
  [ -f "$flag" ] && return 0
  if [ -d "$d" ]; then
    n=$(find "$d" -name '*.done' ! -name 'notes__*' 2>/dev/null | wc -l | tr -d ' ')
    find "$d" -name '*.done' ! -name 'notes__*' -delete 2>/dev/null
    echo "[$(date '+%F %T')] $prof 清视频旧done ${n:-0} 个（全hevc，强制覆盖重传；讲义 notes__ 标记保留）"
  fi
  touch "$flag"
}

echo "[$(date '+%F %T')] 本机supervisor启动"
while :; do
  mkdir -p logs "$FLAGDIR"   # 每轮巡检确保日志目录在：运行中 logs/ 被删后，>> 重定向会静默失败致上传空转
  # —— 压缩 ——
  if ! comp_running; then
    nt=$(nothevc 税法); ne=$(nothevc 经济法)
    if [ "$nt" != "0" ] || [ "$ne" != "0" ]; then start_compress; fi
  fi
  # —— 上传（整机互斥一次一科；审计优先；税法/经济法按科滚动，不等全局压缩结束）——
  if ! up_running; then
    if ! up_done ep3-audit-2026; then
      if log_done logs/netdisk_audit_videos.log || log_done logs/netdisk_ep3-audit-2026.log; then mark_done ep3-audit-2026
      else start_upload ep3-audit-2026; fi
    else
      # 按科：该科全 hevc 且 当前没在压该科（无临时文件）即可传，可与另一科压缩并行
      for pair in ep3-tax-2026:税法 ep3-econlaw-2026:经济法; do
        prof="${pair%%:*}"; kw="${pair##*:}"
        if up_done "$prof"; then continue; fi
        if log_done "logs/netdisk_${prof}.log"; then mark_done "$prof"; continue; fi
        if [ "$(nothevc "$kw")" = "0" ] && ! compressing_course "$kw"; then
          reset_videos_done_once "$prof"; start_upload "$prof"; break
        fi
      done
    fi
  fi
  # —— 终止：压缩结束(税法/经济法全hevc) 且 三科上传done ——
  if ! comp_running && up_done ep3-audit-2026 && up_done ep3-tax-2026 && up_done ep3-econlaw-2026; then
    nt=$(nothevc 税法); ne=$(nothevc 经济法)
    if [ "$nt" = "0" ] && [ "$ne" = "0" ]; then echo "[$(date '+%F %T')] 本机压缩+上传全部完成，supervisor退出"; break; fi
  fi
  sleep 120
done
