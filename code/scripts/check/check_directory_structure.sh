#!/bin/bash
# 目录结构检查脚本
# 检查本地和网盘的目录命名规范、空目录、一致性
#
# 用法:
#   bash check_directory_structure.sh local   # 检查本地
#   bash check_directory_structure.sh remote  # 检查网盘
#   bash check_directory_structure.sh both    # 检查本地和网盘
#   bash check_directory_structure.sh clean   # 清理空的不完整命名目录

set -euo pipefail

# 动态获取项目目录（脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck source=course_config.sh
source "$SCRIPT_DIR/course_config.sh"


set -e

# 配置（本地真实目录走 Desktop 根，网盘走 REMOTE_ROOT；均由 profile/COURSE_NAME 派生）
LOCAL_ROOT="$COURSE_DESKTOP_ROOT"
REMOTE_ROOT="$COURSE_REMOTE_ROOT"
CREDENTIALS_FILE="$PROJECT_DIR/.secrets/baidu_credentials.enc"
# 主密码不写死：已在上方 source course_config.sh 时经 lib/load_enc_pass.sh 导出 BAIDU_ENC_PASS

# 使用python检查目录命名规范
check_naming_python() {
    local dir="$1"
    local source="$2"
    
    echo ""
    echo "=== 检查 $source 目录命名规范 ==="
    
    python3 << PYEOF
import os
import re

dir_path = "$dir"
source = "$source"

if not os.path.isdir(dir_path):
    print(f"⚠️  目录不存在: {dir_path}")
    exit(0)

issues = 0
total = 0

for name in sorted(os.listdir(dir_path)):
    full_path = os.path.join(dir_path, name)
    if not os.path.isdir(full_path):
        continue
    
    total += 1
    
    # 检查是否以两位数字开头
    if not re.match(r'^\d{2}_', name):
        print(f"⚠️  命名不规范（不是两位序号开头）: {name}")
        issues += 1
        continue
    
    # 开班典礼例外（用&）
    if name.startswith("00_开班典礼"):
        print(f"✓ {name}（开班典礼，命名规范）")
        continue
    
    # 检查是否包含 - 分隔符和中文章节名
    if re.search(r'-[\u4e00-\u9fff]', name):
        print(f"✓ {name}（命名规范）")
    else:
        print(f"⚠️  命名不完整（缺少章节名）: {name}")
        issues += 1

print()
print(f"检查结果: {total} 个目录, {issues} 个问题")
PYEOF
}

# 使用python检查空目录
check_empty_dirs_python() {
    local dir="$1"
    local source="$2"
    
    echo ""
    echo "=== 检查 $source 空目录 ==="
    
    python3 << PYEOF
import os

dir_path = "$dir"
source = "$source"

if not os.path.isdir(dir_path):
    print(f"⚠️  目录不存在: {dir_path}")
    exit(0)

empty_count = 0

for name in sorted(os.listdir(dir_path)):
    full_path = os.path.join(dir_path, name)
    if not os.path.isdir(full_path):
        continue
    
    # 统计文件数
    file_count = 0
    for root, dirs, files in os.walk(full_path):
        file_count += len(files)
    
    if file_count == 0:
        print(f"⚠️  空目录: {name}")
        empty_count += 1

print()
print(f"空目录数量: {empty_count}")
PYEOF
}

# 使用python清理空的不完整命名目录
clean_incomplete_empty_dirs_python() {
    local dir="$1"
    
    echo ""
    echo "=== 清理空的不完整命名目录 ==="
    
    python3 << PYEOF
import os
import re
import shutil

dir_path = "$dir"

if not os.path.isdir(dir_path):
    print(f"⚠️  目录不存在: {dir_path}")
    exit(0)

cleaned = 0

for name in sorted(os.listdir(dir_path)):
    full_path = os.path.join(dir_path, name)
    if not os.path.isdir(full_path):
        continue
    
    # 统计文件数
    file_count = 0
    for root, dirs, files in os.walk(full_path):
        file_count += len(files)
    
    # 只删除空的且命名不完整的目录
    if (file_count == 0 and 
        re.match(r'^\d{2}_', name) and 
        not re.search(r'-[\u4e00-\u9fff]', name) and 
        not name.startswith("00_开班典礼")):
        print(f"删除空的不完整命名目录: {name}")
        shutil.rmtree(full_path)
        cleaned += 1

print()
print(f"已清理目录数量: {cleaned}")
PYEOF
}

# 获取网盘access_token
get_access_token() {
    if [ ! -f "$CREDENTIALS_FILE" ]; then
        echo ""
        return 1
    fi
    
    openssl enc -aes-256-cbc -d -pbkdf2 -pass pass:"$BAIDU_ENC_PASS" -base64 -in "$CREDENTIALS_FILE" 2>/dev/null | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null
}

# 检查网盘目录
check_remote() {
    local access_token=$(get_access_token)
    
    if [ -z "$access_token" ]; then
        echo "⚠️  无法获取网盘access_token，跳过网盘检查"
        return
    fi
    
    echo ""
    echo "=== 检查网盘目录结构 ==="
    
    local encoded_dir=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$REMOTE_ROOT'))")
    
    local response=$(curl -s "https://pan.baidu.com/rest/2.0/xpan/file?method=list&access_token=$access_token&dir=$encoded_dir" 2>/dev/null)
    
    echo "$response" | python3 -c "
import sys, json, re

try:
    data = json.load(sys.stdin)
    if 'list' not in data:
        print('错误: 无法获取网盘目录列表')
        sys.exit(1)
    
    items = data['list']
    print(f'网盘目录数量: {len(items)}')
    print()
    
    issues = 0
    for item in items:
        if item.get('isdir') != 1:
            continue
        
        name = item.get('server_filename', '')
        
        # 检查命名规范
        if re.match(r'^\d{2}_', name):
            if name.startswith('00_开班典礼'):
                print(f'✓ {name}（开班典礼，命名规范）')
            elif re.search(r'-[\u4e00-\u9fff]', name):
                print(f'✓ {name}（命名规范）')
            else:
                print(f'⚠️  {name}（命名不完整，缺少章节名）')
                issues += 1
        else:
            print(f'⚠️  {name}（命名不规范）')
            issues += 1
    
    print()
    print(f'网盘检查结果: {issues} 个问题')
except Exception as e:
    print(f'解析失败: {e}')
"
}

# 主函数
main() {
    local mode="${1:-both}"
    
    echo "============================================"
    echo "  目录结构检查"
    echo "  模式: $mode"
    echo "============================================"
    
    case "$mode" in
        local)
            check_naming_python "$LOCAL_ROOT" "本地"
            check_empty_dirs_python "$LOCAL_ROOT" "本地"
            ;;
        remote)
            check_remote
            ;;
        both)
            check_naming_python "$LOCAL_ROOT" "本地"
            check_empty_dirs_python "$LOCAL_ROOT" "本地"
            check_remote
            ;;
        clean)
            clean_incomplete_empty_dirs_python "$LOCAL_ROOT"
            ;;
        *)
            echo "用法: $0 {local|remote|both|clean}"
            exit 1
            ;;
    esac
    
    echo ""
    echo "============================================"
    echo "  检查完成"
    echo "============================================"
}

main "$@"
