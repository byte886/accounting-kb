#!/bin/bash
# setup_transcription_env.sh
# 用途：在新电脑上快速搭建音频转写环境（FunASR + VAD）
# 说明：Python虚拟环境不建议直接复制，在新电脑上运行此脚本重新创建
#
# 用法：
#   ./scripts/setup_transcription_env.sh           # 使用默认 Python 3.10
#   ./scripts/setup_transcription_env.sh 3.11      # 指定 Python 版本
#   ./scripts/setup_transcription_env.sh --check   # 只检查当前环境状态

set -euo pipefail

# 动态获取项目目录（脚本所在目录的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"


set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TRANSCRIPTION_DIR="$PROJECT_DIR/transcription"
VENV_DIR="$TRANSCRIPTION_DIR/venv"
REQUIREMENTS="$TRANSCRIPTION_DIR/requirements.txt"

# 解析参数
if [ "$1" = "--check" ]; then
    echo "=== 检查转写环境状态 ==="
    if [ -d "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python" ]; then
        echo "虚拟环境: ✅ 存在"
        echo "Python版本: $($VENV_DIR/bin/python --version 2>&1)"
        echo "FunASR版本: $($VENV_DIR/bin/pip show funasr 2>/dev/null | grep Version || echo '未安装')"
        echo "PyTorch版本: $($VENV_DIR/bin/pip show torch 2>/dev/null | grep Version || echo '未安装')"
    else
        echo "虚拟环境: ❌ 不存在"
        echo "请运行此脚本创建环境"
    fi
    exit 0
fi

PYTHON_VERSION="${1:-3.10}"
PYTHON_CMD="python$PYTHON_VERSION"

echo "=== 搭建音频转写环境 ==="
echo "项目目录: $PROJECT_DIR"
echo "虚拟环境: $VENV_DIR"
echo "Python版本: $PYTHON_VERSION"
echo ""

# 检查 Python 是否可用
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "❌ 未找到 $PYTHON_CMD"
    echo "请先安装 Python $PYTHON_VERSION"
    echo "macOS: brew install python@$PYTHON_VERSION"
    exit 1
fi

echo "✅ 找到 $PYTHON_CMD: $($PYTHON_CMD --version 2>&1)"
echo ""

# 检查 requirements.txt 是否存在
if [ ! -f "$REQUIREMENTS" ]; then
    echo "❌ 未找到 requirements.txt: $REQUIREMENTS"
    echo "请先从旧电脑导出依赖: pip list --format=freeze > transcription/requirements.txt"
    exit 1
fi

# 创建 transcription 目录
mkdir -p "$TRANSCRIPTION_DIR"

# 如果虚拟环境已存在，询问是否重建
if [ -d "$VENV_DIR" ]; then
    echo "⚠️  虚拟环境已存在: $VENV_DIR"
    read -p "是否删除并重建？(y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo "删除旧环境..."
        rm -rf "$VENV_DIR"
    else
        echo "保留现有环境，退出"
        exit 0
    fi
fi

# 创建虚拟环境
echo ""
echo "=== 创建虚拟环境 ==="
"$PYTHON_CMD" -m venv "$VENV_DIR"
echo "✅ 虚拟环境创建成功"

# 升级 pip
echo ""
echo "=== 升级 pip ==="
"$VENV_DIR/bin/pip" install --upgrade pip
echo "✅ pip 升级完成"

# 安装依赖
echo ""
echo "=== 安装依赖（约64个包，可能需要5-10分钟）==="
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS"
echo "✅ 依赖安装完成"

# 验证安装
echo ""
echo "=== 验证安装 ==="
echo "Python版本: $($VENV_DIR/bin/python --version 2>&1)"
echo "FunASR版本: $($VENV_DIR/bin/pip show funasr 2>/dev/null | grep Version || echo '未安装')"
echo "PyTorch版本: $($VENV_DIR/bin/pip show torch 2>/dev/null | grep Version || echo '未安装')"
echo "librosa版本: $($VENV_DIR/bin/pip show librosa 2>/dev/null | grep Version || echo '未安装')"
echo "modelscope版本: $($VENV_DIR/bin/pip show modelscope 2>/dev/null | grep Version || echo '未安装')"

echo ""
echo "=== 环境搭建完成 ==="
echo "虚拟环境路径: $VENV_DIR"
echo "激活环境: source $VENV_DIR/bin/activate"
echo "运行转写: bash scripts/transcribe_all.sh   # 换课先 export GAODUN_COURSE_PROFILE=<key>"
echo "检查状态: ./scripts/setup_transcription_env.sh --check"
echo ""
echo "=== 注意事项 ==="
echo "1. 首次运行转写会自动下载模型（约几百MB），需要网络连接"
echo "2. 模型缓存目录: ~/.cache/modelscope/ 或 ~/.cache/huggingface/"
echo "3. 如需GPU加速，请安装对应CUDA版本的PyTorch"
echo "4. 虚拟环境不要直接复制到其他电脑，用此脚本重新创建"
