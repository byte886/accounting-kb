#!/usr/bin/env bash
# Worker Supervisor 模式跑 resync_wiki_content.py（2026-09-20 由"轮次+长休眠"重构而来）：
#   旧版每轮写满后 sleep 90s、零新增指数退避(PAUSE*2^empty 封顶900s)。
#   新版改为 Supervisor：worker（python resync_wiki_content.py）退出后【立即拉起新 worker】，
#   不再有轮间长休眠。单进程换全新 python 进程=新代理会话，绕豆包转发代理
#   （DOUBAO_OFFICE_FORWARD_PROXY）按"单进程累计请求"计的会话失效。
#
# worker 内部已自带（本脚本不重复实现）：
#   · 单进程新写满 RESYNC_MAX_NEW(默认20) 篇即 exit 0 主动退出；
#   · 错误分类：代理会话错(ext err/parse temporary token/invalid_response)原地重试1次再 exit 2；
#     HTTP429 读 Retry-After；其他网络错原地指数退避(1/2/4/8/16s 封顶30s±20%抖动)；
#   · 篇间 RESYNC_INTERVAL(本脚本设5s) 串行不并发；
#   · done 断点：resync_done/*.done 天然持久化任务队列，worker 自动跳过已 done，无需另建。
#
# Supervisor 仅在【连续 N 次"无进展重启"】时短休眠，其余情况一律立即续拉：
#   "无进展重启" = worker 非零退出(rc!=0) 或 本轮新增 gain<=0；
#   连续 RESYNC_FAIL_MAX(默认5) 次这样的重启，才 sleep RESYNC_COOLDOWN(默认30s) 再继续；
#   有任意进展(rc=0 且 gain>0) 立即把失败计数清零、立即续拉新 worker。
#
# 停止条件：done 数 >= 总篇数（默认 = wiki_node_map 行数 + 1 课程首页）时 Supervisor 自己退出，
#   不再起新 worker。
#
# 用法: bash run_resync_batches.sh [profile] [单进程新写上限]
#   profile      默认 cpa-accounting-2026
#   MAX_NEW      单进程新写上限，默认 20（= worker 的 RESYNC_MAX_NEW）
# 可选环境变量（旧版第3位"轮间休眠"已废弃，多余尾部参数被忽略）：
#   RESYNC_FAIL_MAX  连续多少次无进展重启才短休眠，默认 5
#   RESYNC_COOLDOWN  连续失败重启后的短休眠秒数，默认 30
#   RESYNC_TOTAL     总篇数覆盖（默认 = map 行数 + 1 课程首页；不同步首页时自行覆盖）
set -u
PROFILE=${1:-cpa-accounting-2026}
MAX_NEW=${2:-20}
FAIL_MAX=${RESYNC_FAIL_MAX:-5}
COOLDOWN=${RESYNC_COOLDOWN:-30}

WS="data/_workspace/$PROFILE"
DONE_DIR="$WS/logs/resync_done"
MAP="$WS/logs/wiki_node_map.tsv"
LOG="$WS/logs/resync_wiki.log"
MAP_LINES=$(wc -l < "$MAP" 2>/dev/null | tr -d ' ')
MAP_LINES=${MAP_LINES:-0}
TOTAL=${RESYNC_TOTAL:-$((MAP_LINES + 1))}   # map 子页面 + 课程首页
export GAODUN_COURSE_PROFILE="$PROFILE"

round=0
fail_streak=0  # 连续"无进展重启"次数：worker 非零退出 或 本轮新增<=0
while :; do
  d=$(ls "$DONE_DIR" 2>/dev/null | wc -l | tr -d ' ')
  round=$((round + 1))
  echo "" >> "$LOG"
  echo "######### Supervisor 第${round}次拉起 worker done=$d/$TOTAL $(date '+%T') #########" >> "$LOG"
  if [ "$d" -ge "$TOTAL" ]; then
    echo "######### 全部 $TOTAL 篇完成，Supervisor 退出 $(date '+%T') #########" >> "$LOG"
    break
  fi
  # 拉起全新 worker（新代理会话）；worker 内部自控写满 MAX_NEW 篇 exit 0、代理坏了 exit 2、
  # 篇间 RESYNC_INTERVAL 串行。外层只负责"worker 退出后立即拉起新 worker"。
  RESYNC_MAX_NEW="$MAX_NEW" \
  RESYNC_INTERVAL=5 \
    python3 scripts/knowledge/resync_wiki_content.py --profile "$PROFILE" >> "$LOG" 2>&1
  rc=$?
  nd=$(ls "$DONE_DIR" 2>/dev/null | wc -l | tr -d ' ')
  gain=$((nd - d))
  echo "--------- 第${round}次 worker退出 rc=$rc done=$nd/$TOTAL 本轮新增$gain $(date '+%T') ---------" >> "$LOG"
  if [ "$nd" -ge "$TOTAL" ]; then
    echo "######### 全部 $TOTAL 篇完成，Supervisor 退出 $(date '+%T') #########" >> "$LOG"
    break
  fi
  # Supervisor 核心：worker 退出后立即拉起新 worker，不长休眠。
  # 仅当"无进展重启"(worker 非零退出 或 本轮新增<=0) 连续 FAIL_MAX 次才短休眠 COOLDOWN。
  if [ "$rc" -ne 0 ] || [ "$gain" -le 0 ]; then
    fail_streak=$((fail_streak + 1))
    echo "  无进展重启第${fail_streak}次(rc=$rc gain=$gain) ${fail_streak}/${FAIL_MAX}" >> "$LOG"
    if [ "$fail_streak" -ge "$FAIL_MAX" ]; then
      echo "  连续${FAIL_MAX}次无进展重启，短休眠 ${COOLDOWN}s 后继续 $(date '+%T')" >> "$LOG"
      sleep "$COOLDOWN"
      fail_streak=0
    fi
  else
    # 有进展：rc=0 且新增>0，立即续拉新 worker，失败计数清零
    fail_streak=0
  fi
done
