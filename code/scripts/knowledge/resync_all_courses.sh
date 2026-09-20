#!/bin/bash
# 全课程知识详解重同步调度器（名师六科专用）
# 功能：循环处理名师课六科，每批新写20篇后主动退出换新进程（解决代理层限流/token过期）
# 用法：bash scripts/knowledge/resync_all_courses.sh
# 依赖：scripts/knowledge/resync_wiki_content.py（已含frontmatter剥离/章节点同步/链接解析/断点续跑）
# 注意：本调度器只处理名师六科（ep3-*）；正课（罗翔会计/蔡俊峻税法，cpa-*）不进批量器，
#       需要刷时用 cpa-* 卡单独运行 resync_wiki_content.py（一卡一课，配置卡已各归各位）。

set -u

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

# 名师课六科的profile key（正课 cpa-accounting/cpa-tax 不进批量器，单独运行）
COURSES=(
    "ep3-accounting-2026"
    "ep3-audit-2026"
    "ep3-finance-2026"
    "ep3-tax-2026"
    "ep3-econlaw-2026"
    "ep3-strategy-2026"
)

# 每批新写上限（达到后主动退出换新进程）
MAX_NEW=20
# 批次间等待时间（秒），让代理层计数清零
BATCH_WAIT=10
# 单课程最大重试轮次（避免死循环）
MAX_ROUNDS=20

echo "============================================================"
echo "全课程知识详解重同步调度器启动"
echo "课程数: ${#COURSES[@]}"
echo "每批新写上限: $MAX_NEW 篇"
echo "批次间等待: $BATCH_WAIT 秒"
echo "============================================================"
echo ""

total_success=0
total_failed=0

for course in "${COURSES[@]}"; do
    echo "------------------------------------------------------------"
    echo "处理课程: $course"
    echo "------------------------------------------------------------"
    
    round=0
    while [ $round -lt $MAX_ROUNDS ]; do
        round=$((round + 1))
        echo ""
        echo "=== 第 $round 轮 (课程: $course) ==="
        
        # 运行resync_wiki_content.py，设置单批新写上限
        GAODUN_COURSE_PROFILE="$course" \
        RESYNC_MAX_NEW="$MAX_NEW" \
        python3 scripts/knowledge/resync_wiki_content.py 2>&1 | tee "/tmp/resync_${course}_round${round}.log"
        
        exit_code=${PIPESTATUS[0]}
        
        # 统计本轮结果（grep -c无匹配时返回非零，用; true避免双输出）
        ok_count=$(grep -c "✓" "/tmp/resync_${course}_round${round}.log" 2>/dev/null; true)
        fail_count=$(grep -c "✗" "/tmp/resync_${course}_round${round}.log" 2>/dev/null; true)
        skip_count=$(grep -c "· 已同步跳过" "/tmp/resync_${course}_round${round}.log" 2>/dev/null; true)
        # 确保是纯数字（取最后一行，去除可能的空行）
        ok_count=$(echo "$ok_count" | tail -1 | tr -d '[:space:]')
        fail_count=$(echo "$fail_count" | tail -1 | tr -d '[:space:]')
        skip_count=$(echo "$skip_count" | tail -1 | tr -d '[:space:]')
        [ -z "$ok_count" ] && ok_count=0
        [ -z "$fail_count" ] && fail_count=0
        [ -z "$skip_count" ] && skip_count=0
        
        echo "本轮结果: 成功$ok_count, 失败$fail_count, 已跳过$skip_count"
        
        # 判断是否需要继续下一轮
        # 如果没有新写成功（全部是跳过），说明该课程已完成
        if [ "$ok_count" -eq 0 ] && [ "$fail_count" -eq 0 ]; then
            echo "课程 $course 已全部完成（无新写、无失败）"
            break
        fi
        
        # 如果有失败，记录但继续（断点续跑会在下轮重试）
        if [ "$fail_count" -gt 0 ]; then
            echo "警告: 本轮有 $fail_count 个失败，将在下轮重试"
            total_failed=$((total_failed + fail_count))
        fi
        
        total_success=$((total_success + ok_count))
        
        # 等待一段时间，让代理层计数清零
        echo "等待 $BATCH_WAIT 秒后开始下一轮..."
        sleep "$BATCH_WAIT"
    done
    
    if [ $round -ge $MAX_ROUNDS ]; then
        echo "警告: 课程 $course 达到最大重试轮次 $MAX_ROUNDS，可能仍有未完成项"
    fi
    
    echo ""
done

echo ""
echo "============================================================"
echo "全部课程处理完成"
echo "累计成功: $total_success"
echo "累计失败: $total_failed"
echo "============================================================"
echo ""
echo "注意:"
echo "1. 失败项无done标记，可重新运行本脚本进行断点续跑"
echo "2. 如需强制全量重刷，可修改脚本添加 --force 参数"
echo "3. 单课程日志保存在 /tmp/resync_<course>_round<N>.log"
