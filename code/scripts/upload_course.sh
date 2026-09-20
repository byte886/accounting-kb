#!/bin/bash
# 课程目录批量上传百度网盘脚本
# 自动过滤技术过程文档，只上传面向使用者的内容
#
# 用法:
#   bash upload_course.sh <本地课程目录> <网盘课程目录>
#
# 示例:
#   bash upload_course.sh \
#     "data/高顿/CPA/【26考季】VIPCPA系列-税法（蔡俊峻老师）/01_税法全面精讲01-税法总论" \
#     "/apps/CPA课程归档/会计知识库/高顿/CPA/【26考季】VIPCPA系列-税法（蔡俊峻老师）/01_税法全面精讲01-税法总论"
#
# 网盘路径必须以 /apps/CPA课程归档/ 开头。

set -euo pipefail

# 动态获取项目目录（脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"


set -e

# 配置
UPLOAD_SCRIPT="$PROJECT_DIR/scripts/baidu_upload.py"
# 主密码不写死：环境变量 > 本机600主密码文件 > 交互（lib/load_enc_pass.sh）
# shellcheck source=lib/load_enc_pass.sh
source "$SCRIPT_DIR/lib/load_enc_pass.sh"

# 参数检查
if [ $# -lt 2 ]; then
    echo "用法: bash upload_course.sh <本地课程目录> <网盘课程目录>"
    exit 1
fi

LOCAL_DIR="$1"
REMOTE_DIR="$2"

# 技术过程文档过滤模式（不上传，只传面向使用者的成品）
# 遍历用 "$dir"/*，bash glob 默认不匹配点开头项，故 .vfetch/、.uploaded 等隐藏项天然不遍历，无需在此列出。
# 参考: docs/project-management/standards/PROJECT_STRUCTURE_MAINTENANCE.md（产物落点与网盘上传边界）
SKIP_PATTERNS=(
    # —— 过程/验证/同步类文档（课程目录成品仅 知识拆解.md / 考试指导.md / transcript.md）——
    "VERIFICATION.md"       # 单讲验证记录（现行规范并入任务报告，不落课程目录）
    "VERIFICATION_*.md"
    "验证报告_*.md"
    "验证_*.md"
    "SYNC_REPORT_*.md"      # 网盘同步报告（已下线，历史遗留）
    "同步报告_*.md"
    "课程总览.md"           # 飞书课程根总览页的本地派生源（build_course_overview.py 可随时再生成；正式载体是飞书，不属网盘成品）
    # —— 转写/技术中间产物 ——
    "transcript.json"       # 转写原始 JSON（可读版 transcript.md 才上传）
    "*.tmp"                 # 临时文件
    "*.log"                 # 日志文件
    # —— 账号级动态台账（属 data/_workspace/_account/user-space，滚动留最新，绝不上网盘）——
    "账号课程清单.json"      # 账号课程清单（中文旧名，历史曾误传到 CPA 根）
    "account_courses.json"  # 账号课程清单（规范名）
    "user_space_*.json"     # 用户空间抓取快照
    # —— 系统文件 ——
    ".DS_Store"             # macOS 系统文件
)

# 检查本地目录是否存在
if [ ! -d "$LOCAL_DIR" ]; then
    echo "❌ 本地目录不存在: $LOCAL_DIR"
    exit 1
fi

echo "============================================"
echo "  课程目录批量上传百度网盘"
echo "  本地: $LOCAL_DIR"
echo "  网盘: $REMOTE_DIR"
echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# 统计
TOTAL=0
SUCCESS=0
SKIPPED=0
FAILED=0

# 检查文件是否应该跳过
should_skip() {
    local filename="$1"
    for pattern in "${SKIP_PATTERNS[@]}"; do
        # 使用bash的模式匹配
        if [[ "$filename" == $pattern ]]; then
            return 0  # 应该跳过
        fi
    done
    return 1  # 不应该跳过
}

# 遍历目录上传文件
upload_directory() {
    local local_base="$1"
    local remote_base="$2"
    
    # 遍历当前目录的文件和子目录
    for item in "$local_base"/*; do
        if [ -f "$item" ]; then
            # 是文件
            filename=$(basename "$item")
            TOTAL=$((TOTAL + 1))
            
            # 检查是否应该跳过
            if should_skip "$filename"; then
                echo "  [跳过] $filename (技术过程文档)"
                SKIPPED=$((SKIPPED + 1))
                continue
            fi
            
            # 计算相对路径
            rel_path="${item#$LOCAL_DIR/}"
            remote_file="$remote_base/$rel_path"
            
            # 上传文件
            echo "  [上传] $rel_path"
            if python3 "$UPLOAD_SCRIPT" "$item" "$remote_file" 2>&1 | tail -1; then
                SUCCESS=$((SUCCESS + 1))
            else
                echo "    ❌ 上传失败"
                FAILED=$((FAILED + 1))
            fi
            
        elif [ -d "$item" ]; then
            # 是子目录，递归处理
            dirname=$(basename "$item")
            echo "  [目录] $dirname/"
            upload_directory "$item" "$remote_base"
        fi
    done
}

# 开始上传
upload_directory "$LOCAL_DIR" "$REMOTE_DIR"

# 汇总报告
echo ""
echo "============================================"
echo "  批量上传完成"
echo "  完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  ----------------------------------------"
echo "  成功: $SUCCESS"
echo "  跳过(技术过程文档): $SKIPPED"
echo "  失败: $FAILED"
echo "  总计: $TOTAL"
echo "============================================"

if [ $FAILED -gt 0 ]; then
    exit 1
fi
