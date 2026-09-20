#!/bin/bash
# 知识库结构检查脚本
# 用途：检查飞书知识库节点结构，检测重复节点、空节点、链接问题
# 用法：./scripts/check_kb_structure.sh <parent_node_token> [space_id]
# 示例：./scripts/check_kb_structure.sh XTJFwu5zBiUNCDkXqEgcTI2fnPg 7678261729456852192

set -e

# 参数检查
if [ $# -lt 1 ]; then
    echo "用法: $0 <parent_node_token> [space_id]"
    echo "示例: $0 XTJFwu5zBiUNCDkXqEgcTI2fnPg 7678261729456852192"
    exit 1
fi

PARENT_NODE_TOKEN="$1"
SPACE_ID="${2:-7678261729456852192}"
BASE_URL="https://zcnjheoajxng.feishu.cn/wiki"

echo "=========================================="
echo "知识库结构检查"
echo "=========================================="
echo "父节点: $PARENT_NODE_TOKEN"
echo "空间ID: $SPACE_ID"
echo "检查时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 列出子节点
echo "【1/4】列出子节点..."
NODE_LIST=$(lark-cli wiki +node-list \
    --space-id "$SPACE_ID" \
    --parent-node-token "$PARENT_NODE_TOKEN" 2>&1)

if echo "$NODE_LIST" | grep -q '"ok": false'; then
    echo "❌ 获取子节点列表失败:"
    echo "$NODE_LIST" | grep -A5 '"error"'
    exit 1
fi

# 提取节点信息
NODE_TOKENS=$(echo "$NODE_LIST" | grep -o '"node_token": "[^"]*"' | sed 's/"node_token": "//;s/"//')
NODE_TITLES=$(echo "$NODE_LIST" | grep -o '"title": "[^"]*"' | sed 's/"title": "//;s/"//')
NODE_COUNT=$(echo "$NODE_LIST" | grep -o '"count": [0-9]*' | sed 's/"count": //')

echo "子节点数量: $NODE_COUNT"
echo ""

# 2. 检查重复节点
echo "【2/4】检查重复节点..."
DUPLICATE_TITLES=$(echo "$NODE_TITLES" | sort | uniq -d)
if [ -n "$DUPLICATE_TITLES" ]; then
    echo "⚠️  发现重复节点:"
    echo "$DUPLICATE_TITLES" | while read title; do
        echo "  - $title"
    done
    HAS_DUPLICATE=1
else
    echo "✅ 无重复节点"
    HAS_DUPLICATE=0
fi
echo ""

# 3. 检查空节点
echo "【3/4】检查空节点..."
EMPTY_NODES=""
EMPTY_COUNT=0
echo "$NODE_TOKENS" | while read token; do
    if [ -z "$token" ]; then
        continue
    fi
    
    # 获取节点内容
    NODE_CONTENT=$(lark-cli docs +fetch \
        --doc "$BASE_URL/$token" 2>&1)
    
    # 提取内容长度（去除title标签）
    CONTENT_LENGTH=$(echo "$NODE_CONTENT" | grep -o '"content": "[^"]*"' | head -1 | sed 's/"content": "//;s/"$//' | wc -c)
    
    # 如果内容只有title或很短，认为是空节点
    if [ "$CONTENT_LENGTH" -lt 100 ]; then
        TITLE=$(echo "$NODE_CONTENT" | grep -o '<title>[^<]*</title>' | sed 's/<title>//;s/<\/title>//')
        echo "⚠️  空节点: $TITLE (token: $token, 内容长度: $CONTENT_LENGTH)"
        EMPTY_COUNT=$((EMPTY_COUNT + 1))
    fi
done

if [ "$EMPTY_COUNT" -eq 0 ]; then
    echo "✅ 无空节点"
fi
echo ""

# 4. 检查父节点链接
echo "【4/4】检查父节点内容中的链接..."
PARENT_CONTENT=$(lark-cli docs +fetch \
    --doc "$BASE_URL/$PARENT_NODE_TOKEN" 2>&1)

# 检查是否有完整URL链接
FULL_URL_COUNT=$(echo "$PARENT_CONTENT" | grep -o 'https://zcnjheoajxng.feishu.cn/wiki/[a-zA-Z0-9]*' | wc -l)
RELATIVE_URL_COUNT=$(echo "$PARENT_CONTENT" | grep -o '\./[a-zA-Z0-9]*' | wc -l)

echo "完整URL链接数量: $FULL_URL_COUNT"
echo "相对路径链接数量: $RELATIVE_URL_COUNT"

if [ "$RELATIVE_URL_COUNT" -gt 0 ]; then
    echo "⚠️  发现相对路径链接，建议使用完整URL"
else
    echo "✅ 无相对路径链接"
fi

# 检查是否所有子节点都在父节点链接中
echo ""
echo "检查子节点是否都在父节点链接中..."
MISSING_LINKS=""
echo "$NODE_TOKENS" | while read token; do
    if [ -z "$token" ]; then
        continue
    fi
    if ! echo "$PARENT_CONTENT" | grep -q "$token"; then
        TITLE=$(echo "$NODE_LIST" | grep -B5 "$token" | grep '"title"' | head -1 | sed 's/"title": "//;s/"//')
        echo "⚠️  子节点未在父节点链接中: $TITLE (token: $token)"
    fi
done
echo ""

# 总结
echo "=========================================="
echo "检查总结"
echo "=========================================="
echo "子节点数量: $NODE_COUNT"
echo "重复节点: $([ $HAS_DUPLICATE -eq 1 ] && echo '有' || echo '无')"
echo "空节点数量: $EMPTY_COUNT"
echo "完整URL链接: $FULL_URL_COUNT"
echo "相对路径链接: $RELATIVE_URL_COUNT"
echo ""

if [ $HAS_DUPLICATE -eq 1 ] || [ "$EMPTY_COUNT" -gt 0 ] || [ "$RELATIVE_URL_COUNT" -gt 0 ]; then
    echo "⚠️  发现问题，建议修复后重新检查"
    exit 1
else
    echo "✅ 结构检查通过，无问题"
    exit 0
fi
