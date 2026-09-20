#!/bin/bash
# 飞书知识库同步外层调度器
# 解决问题：lark-cli 经豆包转发代理访问飞书，单进程累计请求到阈值后代理层返回 invalid_response
# 解决方案：按批换新进程，每批处理 MAX_NEW 个文件后主动干净退出，由本脚本重启续跑
#
# 用法：
#   ./scripts/knowledge/sync_with_restart.sh <profile> [max_new] [interval] [batch_pause] [batch_rest]
#   示例：./scripts/knowledge/sync_with_restart.sh ep3-audit-2026 15 3 10 30
#
# 参数说明：
#   profile      - 课程配置名（必填）
#   max_new      - 每批处理的新写文件数，默认15
#   interval     - 每篇间隔秒数，默认3
#   batch_pause  - 每15篇暂停秒数，默认10
#   batch_rest   - 批间休息秒数，默认30

set -e

PROFILE=${1:?"用法: $0 <profile> [max_new] [interval] [batch_pause] [batch_rest]"}
MAX_NEW=${2:-15}           # 每批处理的新写文件数，默认15（保守值，避免单进程累计过多请求）
RESYNC_INTERVAL=${3:-3}    # 每篇间隔秒数，默认3
RESYNC_BATCH_PAUSE=${4:-10} # 每15篇暂停秒数，默认10
BATCH_REST=${5:-30}        # 批间休息秒数，默认30（给代理层计数清零的时间）
ERROR_REST=120               # 异常退出后等待秒数（2026-09-16 从60增加到120，给代理层更多时间清零）

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE="$REPO/data/_workspace/$PROFILE"
LOG_DIR="$WORKSPACE/logs"
RESYNC_DONE="$LOG_DIR/resync_done"

cd "$REPO"

echo "========================================"
echo "飞书知识库同步外层调度器"
echo "Profile: $PROFILE"
echo "每批处理: $MAX_NEW 个文件"
echo "每篇间隔: ${RESYNC_INTERVAL}秒"
echo "分批暂停: 每15篇暂停${RESYNC_BATCH_PAUSE}秒"
echo "批间休息: ${BATCH_REST}秒"
echo "异常等待: ${ERROR_REST}秒"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 统计总文件数（map 子页面 + 课程首页 __COURSE_HOMEPAGE__）
MAP_LINES=$(wc -l < "$LOG_DIR/wiki_node_map.tsv" 2>/dev/null | tr -d ' ')
MAP_LINES=${MAP_LINES:-0}
TOTAL_FILES=$((MAP_LINES + 1))
echo "总文件数: $TOTAL_FILES（map $MAP_LINES + 课程首页 1）"

BATCH=0
TOTAL_ERRORS=0
while true; do
    BATCH=$((BATCH + 1))

    # 统计已完成数
    DONE_COUNT=$(ls "$RESYNC_DONE"/*.done 2>/dev/null | wc -l | tr -d ' ')

    echo ""
    echo "--- 第 $BATCH 批 ---"
    echo "已完成: $DONE_COUNT / $TOTAL_FILES"
    echo "开始时间: $(date '+%H:%M:%S')"

    # 如果全部完成，退出
    if [ "$DONE_COUNT" -ge "$TOTAL_FILES" ]; then
        echo ""
        echo "========================================"
        echo "✅ 全部完成！"
        echo "总批次数: $BATCH"
        echo "总异常次数: $TOTAL_ERRORS"
        echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "========================================"
        exit 0
    fi

    # 启动新进程，每批处理 MAX_NEW 个文件后主动退出
    GAODUN_COURSE_PROFILE="$PROFILE" \
    RESYNC_MAX_NEW="$MAX_NEW" \
    RESYNC_INTERVAL="$RESYNC_INTERVAL" \
    RESYNC_BATCH_PAUSE="$RESYNC_BATCH_PAUSE" \
    python3 scripts/knowledge/resync_wiki_content.py --profile "$PROFILE" 2>&1 | tee -a "$LOG_DIR/sync_restart.log"

    EXIT_CODE=${PIPESTATUS[0]}

    echo "第 $BATCH 批结束，退出码: $EXIT_CODE"
    echo "结束时间: $(date '+%H:%M:%S')"

    # 如果退出码不是0（异常退出），等待一段时间后重试
    if [ "$EXIT_CODE" -ne 0 ]; then
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
        echo "⚠️  异常退出（第 $TOTAL_ERRORS 次），等待 ${ERROR_REST}秒后重试..."
        sleep $ERROR_REST
    fi

    # 批间休息，给代理层计数清零的时间
    echo "批间休息 ${BATCH_REST}秒..."
    sleep $BATCH_REST
done
