#!/bin/bash
# 原始资源补传到百度网盘（notes + videos），断点续传，单讲失败不影响其他
#
# 用法:
#   bash scripts/sync_raw_resources.sh <类型> [并发数]
#   类型: notes | videos | all
#
# 特性:
#   - 按子目录（讲）为单位并发上传，xargs -P
#   - 断点续传：成功的讲在 data/_workspace/<profile>/logs/raw_done/ 写标记，重跑自动跳过（profile 取 COURSE_PROFILE/GAODUN_COURSE_PROFILE，缺省 _shared）
#   - 百度侧已存在文件走 MD5 秒传（baidu_upload.py precreate）
#   - 每讲独立日志 data/_workspace/<profile>/logs/raw_<类型>_<讲名>.log

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 加载课程配置（环境变量可覆盖默认值）
source "$SCRIPT_DIR/course_config.sh"
TAX="$COURSE_LOCAL_ROOT"
REMOTE="$COURSE_REMOTE_ROOT"

TYPE="${1:?用法: sync_raw_resources.sh <notes|videos|all> [并发数]}"
PARALLEL="${2:-2}"

_RP="${COURSE_PROFILE:-${GAODUN_COURSE_PROFILE:-_shared}}"
WS="$PROJECT_DIR/data/_workspace/$_RP"
DONE_DIR="$WS/logs/raw_done"
mkdir -p "$DONE_DIR"

upload_one() {
  local type="$1" name="$2"
  local local_dir="$TAX/原始资源/$type/$name"
  local remote_dir="$REMOTE/原始资源/$type/$name"
  local done_flag="$DONE_DIR/${type}_$(echo "$name" | tr '/' '_').done"

  if [ -f "$done_flag" ]; then
    echo "[跳过] $type/$name（已完成）"
    return 0
  fi
  [ -d "$local_dir" ] || { echo "[不存在] $local_dir"; return 1; }

  local logf="$WS/logs/raw_${type}_$(echo "$name" | tr '/' '_').log"
  echo "[开始] $type/$name $(date '+%H:%M:%S')"
  if bash "$PROJECT_DIR/scripts/upload_course.sh" "$local_dir" "$remote_dir" > "$logf" 2>&1; then
    echo "OK $type/$name $(date '+%H:%M:%S')" > "$done_flag"
    echo "[完成] $type/$name"
  else
    echo "[失败] $type/$name（见 $logf）"
    return 1
  fi
}
export -f upload_one
export DONE_DIR PROJECT_DIR TAX REMOTE WS

run_type() {
  local t="$1"
  local src="$TAX/原始资源/$t"
  [ -d "$src" ] || { echo "[跳过] $t 目录不存在"; return; }
  echo "============================================"
  echo " 补传原始资源/$t  并发=$PARALLEL"
  echo "  本地: $src"
  echo "  网盘: $REMOTE/原始资源/$t"
  echo "  开始: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "============================================"
  ls "$src" | xargs -P "$PARALLEL" -I{} bash -c 'upload_one "$@"' _ "$t" {}
  local done_cnt=$(ls "$DONE_DIR" 2>/dev/null | grep -c "^${t}_" || true)
  local total=$(ls "$src" | wc -l | tr -d ' ')
  echo "============================================"
  echo "  $t 批次结束: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "  完成标记: $done_cnt / $total"
  echo "============================================"
}

case "$TYPE" in
  notes|videos) run_type "$TYPE" ;;
  all) run_type notes; run_type videos ;;
  *) echo "未知类型: $TYPE（应为 notes|videos|all）"; exit 1 ;;
esac
