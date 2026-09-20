#!/usr/bin/env bash
# throttled_ep3_download.sh — EP3 名师课视频「节流下载」调度器（白天防风控 + 给前台/豆包留资源余量）
#
# 设计动机：
#   - 6 路消费者齐发 × 每路 64 分片并发会把网络/磁盘打满，挤掉豆包与后端的通信，表现为豆包卡死；
#     且业务网关取 key 接口密度过高有风控风险（视频分片本身走 CDN，带宽大小不是风控点）。
#   - 本脚本：只起 1 个生产者「串行」预取 key（全进程只有它操作 Chrome，避免多进程抢播放页），
#     消费者纯 --consumer 模式只从缓存读 key 下载、不碰 Chrome；同时在跑的消费者路数受 MAX_PARALLEL 限制；
#     所有子进程统一 nice -n 20 + taskpolicy -c utility 降到后台调度类，前台 App（豆包/Chrome）需要资源时立即让出。
#   - 分片并发的分时段自适应在 ep3_download_videos.js 内（白天 12 / 夜间 64），本脚本不重复控制。
#
# 2026-09-10 修复（补位模型，取代旧的一次性队列）：
#   - 旧版 for 队列每个阶段只起一次消费者，而消费者把"当前预取缓存"下完就退出；生产者后续才预取的 key
#     无人消费，阶段被提前判结束，后期只剩 1 路、空着并发槽，最终还会误报"全部完成"漏片。
#   - 新版以「本地完整性」为唯一完成判据（每个 *_meta.json 是否都有对应非空 *_video.mp4），主循环持续扫描：
#     某阶段未完整且当前无其消费者、且在跑数 < MAX_PARALLEL 就补一个消费者；消费者缓存耗尽退出后下一轮自动再拉起，
#     直到所有阶段本地完整才收工。断点续跑：已存在视频消费者自行跳过。
#
# 用法：
#   bash scripts/cdp/throttled_ep3_download.sh                # 跑下方全部未完成阶段，持续补位到完整
#   MAX_PARALLEL=6 bash scripts/cdp/throttled_ep3_download.sh # 夜间提速，覆盖同时在跑的消费者路数
#
# 断点续跑：消费者对已存在的视频会跳过，可随时中断重跑。

set -o pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

WS="data/_workspace/_account/ep3"
LOG_DIR="$WS/logs"
KC_DIR="$WS/keycache"
RUN_DIR="$WS/run"
mkdir -p "$LOG_DIR" "$KC_DIR" "$RUN_DIR"

# 同时在跑的消费者路数（白天默认 3，给网络/磁盘/豆包留余量；夜间想提速可 MAX_PARALLEL=6 重跑）
MAX_PARALLEL="${MAX_PARALLEL:-3}"

# 防 Mac 空闲睡眠导致下载「零报错静默停摆」。caffeinate -i -w $$：调度器存活期间阻止空闲睡眠，退出即清理。
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i -w $$ &
fi

# 消费者任务队列：profile|阶段(中文,与缓存命名一致)|tag(ASCII,用于PID/日志)
# 顺序即补位优先级；正课会计四阶段优先，其余名师课科目「基础必修+全面精讲」大头排中游交错，
# 量小的重点强化/考前冲刺统一垫后（2026-09-10 纳管审计/财管；2026-09-11 补齐税法四阶段、战略/经济法三阶段）
TASKS=(
  "ep3-accounting-2026|全面精讲|ac_quanjing"
  "ep3-accounting-2026|基础必修|ac_jichu"
  "ep3-accounting-2026|重点强化|ac_zhongdian"
  "ep3-accounting-2026|考前冲刺|ac_kaoqian"
  "ep3-tax-2026|全面精讲|tax_quanjing"
  "ep3-tax-2026|基础必修|tax_jichu"
  "ep3-audit-2026|基础必修|audit_jichu"
  "ep3-audit-2026|全面精讲|audit_quanjing"
  "ep3-strategy-2026|全面精讲|strategy_quanjing"
  "ep3-finance-2026|基础必修|fin_jichu"
  "ep3-finance-2026|全面精讲|fin_quanjing"
  "ep3-econlaw-2026|全面精讲|econlaw_quanjing"
  "ep3-audit-2026|重点强化|audit_zhongdian"
  "ep3-audit-2026|考前冲刺|audit_kaoqian"
  "ep3-finance-2026|重点强化|fin_zhongdian"
  "ep3-finance-2026|考前冲刺|fin_kaoqian"
  "ep3-tax-2026|重点强化|tax_zhongdian"
  "ep3-tax-2026|考前冲刺|tax_kaoqian"
  "ep3-strategy-2026|重点强化|strategy_zhongdian"
  "ep3-strategy-2026|考前冲刺|strategy_kaoqian"
  "ep3-econlaw-2026|重点强化|econlaw_zhongdian"
  "ep3-econlaw-2026|考前冲刺|econlaw_kaoqian"
)

# 后台降级包装：CPU nice 最低 + macOS utility 调度类（IO/CPU 均让位于前台）
low() { nice -n 20 taskpolicy -c utility "$@"; }

echo "=========================================="
echo "EP3 节流下载调度器(持续补位版) 启动 $(date '+%F %T')"
echo "同时在跑消费者上限: $MAX_PARALLEL"
echo "=========================================="

# 1) 启动唯一生产者：轮询六科全部阶段、串行预取 key（只有它操作 Chrome）
low bash scripts/cdp/round_robin_prefetch.sh accounting tax strategy econlaw audit finance \
  >> "$LOG_DIR/round_robin_all.log" 2>&1 &
PRODUCER_PID=$!
echo "生产者已启动 PID=${PRODUCER_PID}（轮询预取 key）"

# 单例「远程调试授权」守护：整个下载周期持续兜底代点 Chrome「允许远程调试」sheet、没点掉就重点、并还焦，
# 补上 connect 内 press 循环只覆盖握手窗口的缺口（B-104）；脚本自带 pidfile 单例，重复启动安全退出。
low bash scripts/cdp/cdp_consent_guard.sh >> "$LOG_DIR/consent_guard.log" 2>&1 &
GUARD_PID=$!
echo "授权守护已启动 PID=${GUARD_PID}（单例兜底代点 + 还焦）"

# 2) 一个阶段缺多少个视频文件（本地完整性，唯一完成判据；只 exists 不读内容，毫秒级）
stage_missing() {
  local profile="$1" stage="$2"
  python3 - "$profile" "$stage" <<'PY'
import sys
from pathlib import Path
name={"ep3-accounting-2026":"会计","ep3-tax-2026":"税法","ep3-strategy-2026":"战略","ep3-econlaw-2026":"经济法","ep3-audit-2026":"审计","ep3-finance-2026":"财管"}
p,stage=sys.argv[1],sys.argv[2]
c=Path("data/高顿/CPA")/f"【VIPCPA专享】名师专业课-{name[p]}"/"原始资源"/"videos"/stage
miss=0
total_meta=0
if c.exists():
    for lec in c.iterdir():
        if not lec.is_dir() or lec.name.startswith("."): continue
        # 只认双老师改造后的 <老师>_meta.json（消费者 --dual-teacher 落盘格式）。
        # 裸 meta.json 是单老师时代历史遗留，其视频已由带老师前缀文件覆盖；不计入完整性，
        # 否则已完整阶段会被误报缺量、消费者反复空转占槽（2026-09-11 会计/税法全面精讲各误报30/29）。
        metas=list(lec.glob("*_meta.json"))
        for m in metas:
            total_meta+=1
            stem=m.name[:-len("_meta.json")] if m.name.endswith("_meta.json") else ""
            v=lec/(f"{stem}_video.mp4" if stem else "video.mp4")
            if not v.exists(): miss+=1
# 阶段目录不存在、或存在但尚无任何 meta（新课未开始）：返回哨兵 -1 触发补位，
# 否则空目录会被当成 miss=0「已完整」而永远不下载（审计/财管纳管时暴露）
if not c.exists() or total_meta==0:
    print(-1)
else:
    print(miss)
PY
}

# 某阶段当前是否有活着的消费者（按启动时记录的 PID 判定，不依赖 pgrep 匹配中文阶段名）
stage_alive() {
  local pidf="$RUN_DIR/$1.pid"
  [ -f "$pidf" ] || return 1
  local pid; pid="$(cat "$pidf" 2>/dev/null)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

count_alive() {
  local n=0 t tag
  for t in "${TASKS[@]}"; do
    tag="${t##*|}"
    stage_alive "$tag" && n=$((n+1))
  done
  echo "$n"
}

run_consumer() {
  local profile="$1" stage="$2" tag="$3"
  local cache="$KC_DIR/${profile}__${stage}.json"   # 与生产者 stage_cache 命名一致：profile×阶段独立
  local log="$LOG_DIR/consumer_${tag}.log"
  echo "[$(date '+%T')] 启动消费者 $profile/$stage"
  low node scripts/cdp/ep3_download_videos.js \
    --profile "$profile" --stage "$stage" --dual-teacher \
    --consumer --global-key-cache "$cache" >> "$log" 2>&1
  echo "[$(date '+%T')] 消费者退出 $profile/$stage（缓存本轮耗尽则等待下轮补位）"
}

# 3) 持续补位主循环：直到所有阶段本地完整
IDLE_STREAK=0
while true; do
  all_done=1
  for t in "${TASKS[@]}"; do
    IFS='|' read -r profile stage tag <<< "$t"
    pidf="$RUN_DIR/$tag.pid"
    if stage_alive "$tag"; then
      all_done=0
      continue
    fi
    rm -f "$pidf"
    miss="$(stage_missing "$profile" "$stage")"
    if [ "$miss" = "0" ]; then
      echo "[$(date '+%T')] 阶段完整 $profile/$stage ✓"
      continue
    fi
    all_done=0
    miss_show="$miss"; [ "$miss" = "-1" ] && miss_show="未开始(整阶段待下)"
    # 未完整且无消费者：在跑数达上限就等，有空位就补
    while [ "$(count_alive)" -ge "$MAX_PARALLEL" ]; do sleep 5; done
    run_consumer "$profile" "$stage" "$tag" &
    echo $! > "$pidf"
    echo "[$(date '+%T')] 补位 $profile/$stage（缺 $miss_show），在跑 $(count_alive)/$MAX_PARALLEL"
    sleep 8   # 错峰启动，避免同时初始化抢资源/抢 Chrome
  done

  if [ "$all_done" = "1" ]; then
    echo "[$(date '+%T')] 所有阶段本地完整，收工"
    break
  fi

  # 还有未完成阶段：消费者会因等 key 阻塞（最多重试 30 轮），这里按节奏重扫补位
  sleep 20
  IDLE_STREAK=$((IDLE_STREAK+1))
  if [ "$IDLE_STREAK" -ge 90 ]; then
    # 约 30 分钟仍未全部完整且无任何消费者存活时提示一次（可能生产者未喂上 key），但不退出
    if [ "$(count_alive)" = "0" ]; then
      echo "[$(date '+%T')] ⚠️ 连续多轮无消费者且仍有缺量，请检查生产者/keycache"
    fi
    IDLE_STREAK=0
  fi
done

# 4) 收尾：停掉生产者（while-true 轮询）、授权守护与残留消费者
kill "$PRODUCER_PID" 2>/dev/null || true
kill "$GUARD_PID" 2>/dev/null || true
pkill -f round_robin_prefetch 2>/dev/null || true
pkill -f cdp_consent_guard 2>/dev/null || true
rm -f "$RUN_DIR"/*.pid 2>/dev/null || true
echo "=========================================="
echo "EP3 节流下载调度器  全部完成 $(date '+%F %T')"
echo "=========================================="
