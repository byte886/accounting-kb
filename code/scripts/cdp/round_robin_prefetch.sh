#!/bin/bash
# round_robin_prefetch.sh — 轮询预取key生产者（支持n个科目×n阶段，按「profile×阶段」独立key缓存，按需滚动预取）
#
# 工作原理：
#   按 TASKS 队列顺序轮询每个「科目×阶段」，只给当前确有活跃消费者（--consumer 进程）的阶段预取 key，
#   每轮为该阶段向后滚动推进 PREFETCH_COUNT 个，offset 到 total 即该阶段完成。
#   每个「profile×阶段」独立 key 缓存文件（<profile>__<阶段>.json），阶段间互不饿死；
#   没有消费者在下载的阶段不提前取 key，避免 m3u8 token 长时间闲置过期。
#
# 用法：
#   bash scripts/cdp/round_robin_prefetch.sh [科目列表]
#   示例：bash scripts/cdp/round_robin_prefetch.sh accounting tax strategy econlaw
#   默认：使用配置文件中的所有科目
#
# 配置文件：
#   config/ep3_subjects.json - 定义科目列表，支持n个科目
#   添加新科目时，只需在配置文件中添加，不需要修改本脚本
#
# 注意：
#   - 生产者只控制Chrome取key，消费者只负责下载，互不干扰
#   - 每个「profile×阶段」独立 key 缓存：data/_workspace/_account/ep3/keycache/<profile>__<阶段>.json
#   （同一 profile 多阶段必须分文件，否则先跑阶段把共享缓存总条数顶高会连带饿死后跑阶段）
#   - 全局key缓存作为后备：data/_workspace/_account/ep3/global_keycache.json
#   - 日志目录：data/_workspace/_account/ep3/logs/
#   - 支持有老师信息（--dual-teacher）和无老师信息（单老师）的科目
#   - 按需滚动预取：只给有活跃消费者的阶段取 key、每轮推进固定窗口，不用缓存总条数做硬跳过

# 不用 -e（errexit）：这是长跑轮询生产者，单条命令瞬时失败（CDP 抖动/枚举为空）不应整体退出；
# 关键步骤在下方显式判断成败并重试。
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

WS="data/_workspace/_account/ep3"
CONFIG_FILE="config/ep3_subjects.json"
GLOBAL_CACHE="$WS/global_keycache.json"
CACHE_DIR="$WS/keycache"
LOG_DIR="$WS/logs"
mkdir -p "$LOG_DIR" "$CACHE_DIR"

# 从配置文件读取默认配置
PREFETCH_COUNT=$(jq -r '.prefetch_count // 8' "$CONFIG_FILE" 2>/dev/null || echo "8")
GLOBAL_CACHE=$(jq -r '.global_cache // "'"$GLOBAL_CACHE"'"' "$CONFIG_FILE" 2>/dev/null || echo "$GLOBAL_CACHE")
CACHE_DIR=$(jq -r '.cache_dir // "'"$CACHE_DIR"'"' "$CONFIG_FILE" 2>/dev/null || echo "$CACHE_DIR")
LOG_DIR=$(jq -r '.log_dir // "'"$LOG_DIR"'"' "$CONFIG_FILE" 2>/dev/null || echo "$LOG_DIR")
# 注：旧版按「缓存总条数 min/max 阈值」节流，在「消费者只读不删 key、多阶段共享缓存」下会饿死后序阶段，已废弃；
# 现改为「只给有活跃消费者的阶段、每轮滚动推进 PREFETCH_COUNT 个」，故不再需要 min/max 阈值。

# 科目配置：从配置文件读取（支持n个科目）
# 格式："科目名:profile名:梯度列表（空格分隔）:是否双老师(1/0):独立缓存路径"
SUBJECT_CONFIG=()
if [ -f "$CONFIG_FILE" ]; then
  # 使用jq解析配置文件，生成科目配置数组
  while IFS= read -r config; do
    SUBJECT_CONFIG+=("$config")
  done < <(jq -r '.subjects[] | "\(.name):\(.profile):\(.stages | join(" ")):\(if (.teachers | length) > 0 then 1 else 0 end):\(.key_cache)"' "$CONFIG_FILE" 2>/dev/null)
  echo "✅ 从配置文件读取科目配置: ${#SUBJECT_CONFIG[@]}个科目"
else
  # 配置文件不存在时，使用默认配置（向后兼容）
  echo "⚠️ 配置文件不存在，使用默认配置"
  SUBJECT_CONFIG=(
    "accounting:ep3-accounting-2026:基础必修 全面精讲:1:$CACHE_DIR/ep3-accounting-2026.json"
    "tax:ep3-tax-2026:全面精讲:1:$CACHE_DIR/ep3-tax-2026.json"
    "strategy:ep3-strategy-2026:全面精讲:1:$CACHE_DIR/ep3-strategy-2026.json"
    "econlaw:ep3-econlaw-2026:全面精讲:1:$CACHE_DIR/ep3-econlaw-2026.json"
  )
fi

# 解析参数
SELECTED_SUBJECTS=("$@")
if [ ${#SELECTED_SUBJECTS[@]} -eq 0 ]; then
  # 默认使用配置文件中的所有科目
  SELECTED_SUBJECTS=($(jq -r '.subjects[].name' "$CONFIG_FILE" 2>/dev/null || echo "accounting tax strategy econlaw"))
fi

echo "=========================================="
echo "轮询预取key生产者（支持n个科目，独立缓存，动态轮询）"
echo "=========================================="
echo "科目: ${SELECTED_SUBJECTS[*]}"
echo "每轮预取key数量: $PREFETCH_COUNT"
echo "每轮每活跃阶段预取key数量: $PREFETCH_COUNT（只给在跑消费者的阶段，滚动领先窗口）"
echo "独立缓存目录: $CACHE_DIR"
echo "全局key缓存: $GLOBAL_CACHE"
echo "日志目录: $LOG_DIR"
echo "配置文件: $CONFIG_FILE"
echo ""

# 根据选中的科目筛选配置
SELECTED_CONFIG=()
for subject in "${SELECTED_SUBJECTS[@]}"; do
  for config in "${SUBJECT_CONFIG[@]}"; do
    config_subject=$(echo "$config" | cut -d: -f1)
    if [ "$config_subject" = "$subject" ]; then
      SELECTED_CONFIG+=("$config")
      break
    fi
  done
done

# 函数：获取某个科目的key缓存数量
get_cache_count() {
  local cache_file="$1"
  if [ -f "$cache_file" ]; then
    python3 -c "
import json
try:
    with open('$cache_file') as f:
        c = json.load(f)
    keys = [k for k in c if k != '_work']
    print(len(keys))
except:
    print(0)
" 2>/dev/null || echo "0"
  else
    echo "0"
  fi
}

# 构建任务列表：每个科目+梯度组合为一个任务
# 格式："科目名:profile名:梯度名:总视频数:当前offset:是否双老师(1/0):独立缓存路径"
TASKS=()
for config in "${SELECTED_CONFIG[@]}"; do
  subject=$(echo "$config" | cut -d: -f1)
  profile=$(echo "$config" | cut -d: -f2)
  stages=$(echo "$config" | cut -d: -f3)
  dual_teacher=$(echo "$config" | cut -d: -f4)
  profile_cache=$(echo "$config" | cut -d: -f5)

  # 构建--dual-teacher参数
  DUAL_TEACHER_FLAG=""
  if [ "$dual_teacher" = "1" ]; then
    DUAL_TEACHER_FLAG="--dual-teacher"
  fi

  for stage in $stages; do
    # 每个「profile×阶段」用独立缓存文件：同一 profile 多阶段（如会计四阶段）共享一个缓存时，
    # 缓存总条数会被先跑的阶段顶高、连带饿死后跑阶段（消费者只读取不删 key，缓存只增不减）。
    stage_cache="${profile_cache%.json}__${stage}.json"
    # 总视频数健壮计数（[[:space:]] 兼容 BSD/GNU grep；--list 失败时 grep -c 输出 0，
    # 禁止再 `|| echo 0` 以免得到 "0\n0" 污染整数字段）
    total=$(node scripts/cdp/ep3_download_videos.js --profile "$profile" --stage "$stage" $DUAL_TEACHER_FLAG --list 2>/dev/null | grep -c '^[[:space:]]*[0-9]' || true)
    case "$total" in ''|*[!0-9]*) total=0;; esac
    cache_count=$(get_cache_count "$stage_cache")
    echo "[$subject/$stage] 总视频数: $total (双老师: $dual_teacher, 本阶段缓存: $cache_count)"
    TASKS+=("$subject:$profile:$stage:$total:0:$dual_teacher:$stage_cache")
  done
done

echo ""
echo "=========================================="
echo "开始轮询预取key（动态轮询策略）"
echo "=========================================="

# 判断某 profile×stage 当前是否有活跃「消费者」进程在下载。
# 生产者自身命令带 --prefetch-only、不带 --consumer，故不会误匹配自己。
stage_has_consumer() {
  local profile="$1" stage="$2"
  pgrep -f "ep3_download_videos[.]js.*--profile ${profile}.*--stage ${stage}.*--consumer" >/dev/null 2>&1
}

# 轮询循环（按需滚动预取，不再用「缓存总条数 ≥ 阈值就硬跳过」——消费者只读不删 key，缓存只增不减，那种判据会饿死后序阶段）
ROUND=0
while true; do
  ROUND=$((ROUND + 1))
  ALL_DONE=1
  PROGRESS_MSG=""
  STANDBY_MSG=""

  # 按 TASKS 队列顺序轮询（顺序即优先级，会计阶段在前）；每阶段独立 offset、独立缓存文件
  for i in "${!TASKS[@]}"; do
    IFS=':' read -r subject profile stage total offset dual_teacher stage_cache <<< "${TASKS[$i]}"
    # 字段健壮性：空值/非整数兜底，禁止空值进入整数比较（旧版曾因此 integer expression expected 空转）
    case "$total" in ''|*[!0-9]*) total=0;; esac
    case "$offset" in ''|*[!0-9]*) offset=0;; esac

    # 该阶段 key 已全部预取
    if [ "$offset" -ge "$total" ]; then
      PROGRESS_MSG="$PROGRESS_MSG [$subject/$stage:完成$offset/$total]"
      continue
    fi

    # 还有未预取的 key
    ALL_DONE=0

    # 只给「当前确有活跃消费者」的阶段预取：没有消费者在下载就不提前取 key，避免 token 长时间闲置过期
    if ! stage_has_consumer "$profile" "$stage"; then
      STANDBY_MSG="$STANDBY_MSG [$subject/$stage:待机$offset/$total(无消费者)]"
      continue
    fi

    # 滚动领先窗口：每轮为该活跃阶段向后推进 PREFETCH_COUNT 个（与消费速度自然匹配，不一次性取完）
    REMAINING=$((total - offset))
    if [ "$REMAINING" -lt "$PREFETCH_COUNT" ]; then
      ACTUAL_PREFETCH=$REMAINING
    else
      ACTUAL_PREFETCH=$PREFETCH_COUNT
    fi

    DUAL_TEACHER_FLAG=""
    if [ "$dual_teacher" = "1" ]; then
      DUAL_TEACHER_FLAG="--dual-teacher"
    fi

    echo ""
    echo "--- 第${ROUND}轮: $subject/$stage (第$((offset + 1))-$((offset + ACTUAL_PREFETCH))/$total个，预取$ACTUAL_PREFETCH个) ---"

    # CDP 取 key 重试（最多3次，每次间隔5秒）
    PREFETCH_SUCCESS=0
    for RETRY in 1 2 3; do
      if node scripts/cdp/ep3_download_videos.js \
        --profile "$profile" \
        --stage "$stage" \
        $DUAL_TEACHER_FLAG \
        --global-key-cache "$stage_cache" \
        --prefetch-only \
        --offset "$offset" \
        --limit "$ACTUAL_PREFETCH" \
        >> "$LOG_DIR/round_robin_${subject}_${stage}.log" 2>&1; then
        PREFETCH_SUCCESS=1
        break
      else
        echo "  ✗ 预取失败（第$RETRY次），5秒后重试..."
        sleep 5
      fi
    done

    if [ "$PREFETCH_SUCCESS" -eq 1 ]; then
      echo "  ✓ 预取成功 ($ACTUAL_PREFETCH个)"
      new_offset=$((offset + ACTUAL_PREFETCH))
      TASKS[$i]="$subject:$profile:$stage:$total:$new_offset:$dual_teacher:$stage_cache"
      PROGRESS_MSG="$PROGRESS_MSG [$subject/$stage:$new_offset/$total]"
    else
      echo "  ✗ 预取失败（已重试3次），下一轮重试..."
      # 失败不更新 offset，下一轮重试
      PROGRESS_MSG="$PROGRESS_MSG [$subject/$stage:$offset/$total(失败)]"
    fi
  done

  echo ""
  echo "=== 第${ROUND}轮完成 ==="
  echo "进度:$PROGRESS_MSG"
  if [ -n "$STANDBY_MSG" ]; then
    echo "待机:$STANDBY_MSG"
  fi

  # 所有阶段 offset 都到 total 才算预取完成
  if [ "$ALL_DONE" -eq 1 ]; then
    echo ""
    echo "=========================================="
    echo "所有阶段的 key 已全部预取完成！总轮数: $ROUND"
    echo "=========================================="
    break
  fi

  # 短暂休息，避免 Chrome 过载
  sleep 1
done

echo ""
echo "轮询预取生产者退出"
