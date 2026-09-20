#!/bin/bash
# fetch_all_videos.sh — 视频总控：先跑「下载阶段」再跑「压缩阶段」（两段串行总入口）。
# 若要下载与压缩/其它任务并行调度，可分别手动运行 download_all.sh 与 encode_all.sh。
# 用法: bash scripts/cdp/fetch_all_videos.sh [idx ...]
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/download_all.sh" "$@" || true
bash "$DIR/encode_all.sh"
