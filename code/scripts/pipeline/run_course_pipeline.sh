#!/bin/bash
# run_course_pipeline.sh — 单门 CPA 课程「采集→加工→生成→同步」总编排器（层3，只调度不含业务）。
#
# 严格按 docs/development/project-dag.md 的依赖顺序推进；阶段内部并发由各专用脚本自负其责
# （下载/转写内部已用标准件，见 parallel-toolkit-design.md 层2），本脚本只做：
#   - 阶段级断点：data/_workspace/<profile>/pipeline/<n>.done，重跑自动跳过；
#   - Fan-In 守护：进入「9 知识库生成」前校验 5/6/7 的 .done 与 8 的 profile.structure.groups，
#     缺哪项明确报哪项，绝不硬跑；
#   - 半自动/未实现阶段（manual/todo）只给指引与就绪检查，不伪造自动命令。
#
# 用法:
#   bash scripts/run_course_pipeline.sh <profile-key> [选项]
#     （profile-key 缺省 cpa-tax-2026；例：cpa-accounting-2026）
#   选项:
#     --dry-run        只打印将执行的阶段/命令与依赖就绪情况，不执行、不写 marker
#     --from <n>       从第 n 阶段开始（忽略其前的完成标记）
#     --only <n>       只跑第 n 阶段
#     --list           列出全部阶段与状态后退出
#
# 阶段类型：auto=有确定脚本可自动执行；manual=需人工/AI 介入（编排器只做产物检查与提示）；todo=尚未实现。
set -uo pipefail
# 兜底 UTF-8 locale：后台/C locale 下 $VAR 紧跟中文会被并入变量名而报 unbound
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------- 参数解析 ----------
PROFILE="cpa-tax-2026"; FROM=0; ONLY=""; DRY=0; LIST=0
POS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --from) FROM="${2:?--from 需要阶段编号}"; shift 2 ;;
    --only) ONLY="${2:?--only 需要阶段编号}"; shift 2 ;;
    --list) LIST=1; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) POS+=("$1"); shift ;;
  esac
done
[ ${#POS[@]} -ge 1 ] && PROFILE="${POS[0]}"
export GAODUN_COURSE_PROFILE="$PROFILE"
# shellcheck source=course_config.sh
source "$ROOT/scripts/course_config.sh" || { echo "无法加载课程 profile: $PROFILE" >&2; exit 2; }

# 阶段断点统一放 data/_workspace/<profile>/pipeline（过程件不进课程成品目录，见 ADR-016）
MARKER_DIR="$ROOT/data/_workspace/$PROFILE/pipeline"
mkdir -p "$MARKER_DIR"
[ -n "$ONLY" ] && FROM="$ONLY"

log(){ echo "[pipeline:$PROFILE] $*"; }

# ---------- 阶段元数据（case 函数，兼容 macOS bash 3.2，不用关联数组） ----------
stage_name(){ case "$1" in
  0) echo "课程发现/建 profile";; 1) echo "syllabus 与作业基线";; 2) echo "讲义 PDF 补齐";;
  3) echo "视频下载解密";; 4) echo "视频 H.265 压缩";; 5) echo "讲义 OCR";; 6) echo "线B 题答采集";;
  7) echo "视频 FunASR 转写";; 8) echo "官方组↔知识点映射";; 9) echo "知识库成篇生成(Fan-In)";;
  10) echo "知识库做题验证";; 11) echo "冲刺模考3张";; 12) echo "百度网盘备份";; *) echo "未知阶段$1";; esac; }
stage_kind(){ case "$1" in
  0|2|8|9) echo manual;; 10|11) echo todo;; *) echo auto;; esac; }
stage_deps(){ case "$1" in
  0) echo "";; 1) echo 0;; 2|3|6) echo 1;; 4) echo 3;; 5) echo 2;; 7) echo 4;; 8) echo "";;
  9) echo "5 6 7 8";; 10) echo 9;; 11) echo "9 10";; 12) echo "1 3 4 5 7 9";; esac; }
# auto 阶段的实际命令（manual/todo 返回空）
stage_cmd(){ case "$1" in
  1) echo "node scripts/cdp/refresh_inventory.js";;
  3) echo "bash scripts/cdp/download_all.sh";;
  4) echo "bash scripts/cdp/encode_all.sh";;
  5) echo "bash scripts/ocr/run_ocr_all.sh";;
  6) echo "node scripts/cdp/collect_paper_sources.js --all";;
  7) echo "bash scripts/transcribe_parallel.sh";;
  12) echo "bash scripts/sync_course_netdisk.sh \"\$COURSE_LOCAL_ROOT\" \"\$COURSE_REMOTE_ROOT\"";;
  *) echo "";; esac; }
# manual 阶段的人工指引
stage_manual_hint(){ case "$1" in
  0) echo "  └ 手动: node scripts/cdp/fetch_user_space_courses.js --print 拉账号课程，据结果建/核 config/courses/${PROFILE}.json（课程ID/科目/structure）";;
  2) echo "  └ 手动: 无单一脚本；按阶段1 inventory 的资源 URL 把讲义 PDF 补齐到各讲 docs/（CDN 免认证）";;
  8) echo "  └ 设计: 按 ADR-012 在 ${PROFILE}.json 的 structure.groups 定稿官方组↔知识点（不占 CPU，应在转写期间提前完成）";;
  9) echo "  └ 半自动: python3 scripts/knowledge/collect_point_questions.py --all 聚合 → AI 写每点头部 → assemble_point.py 成篇 → build_course_overview.py 出总览";;
  *) echo "";; esac; }

# ---------- 就绪检查 ----------
marker_of(){ echo "$MARKER_DIR/$1.done"; }
is_done(){ [ -f "$(marker_of "$1")" ]; }
# manual 阶段8 的就绪判据：profile.structure.groups 非空
groups_ready(){ node -e '
const {loadProfile}=require("./scripts/cdp/load_profile.js");
try{const g=loadProfile().structure?.groups||[];process.exit(g.length>0?0:1);}catch(e){process.exit(1);}'; }

# Fan-In：阶段9 前校验 5/6/7 marker + 8 groups
fanin_check(){
  local miss=()
  for d in 5 6 7; do is_done "$d" || miss+=("$d $(stage_name "$d")"); done
  groups_ready || miss+=("8 $(stage_name 8)（profile.structure.groups 为空）")
  if [ ${#miss[@]} -gt 0 ]; then
    echo "✗ Fan-In 未满足，缺以下上游，不能进入阶段9：" >&2
    printf '    - %s\n' "${miss[@]}" >&2
    return 1
  fi
  log "Fan-In 校验通过（5 OCR / 6 采题 / 7 转写 / 8 映射均就绪）"
}

# ---------- 单阶段执行 ----------
run_stage(){
  local n="$1" kind; kind=$(stage_kind "$n")
  local inrange=1
  if [ -n "$ONLY" ]; then [ "$n" = "$ONLY" ] || inrange=0
  else [ "$n" -ge "$FROM" ] || inrange=0; fi
  [ "$inrange" = 1 ] || return 0
  if [ -z "$ONLY" ] && is_done "$n"; then log "阶段 ${n}（$(stage_name "$n")）已完成，跳过；重跑删 $(marker_of "$n")"; return 0; fi
  echo "────────────────────────────────────────"
  log "阶段 ${n}：$(stage_name "$n")  [$kind]"

  case "$kind" in
    todo)
      log "  ⏳ 尚未实现（见 project-dag 节点${n}），跳过" ;;
    manual)
      stage_manual_hint "$n"
      if [ "$n" = "9" ]; then
        if [ "$DRY" = 1 ]; then fanin_check || log "  [dry-run] ↑当前上游未齐（正式运行时会在此阻断）"
        else fanin_check || return 1; fi
      fi
      # manual 阶段不自动写 marker；dry-run 仅展示
      [ "$DRY" = 1 ] && log "  [dry-run] 将在此等待人工/AI 完成并自检产物" ;;
    auto)
      local cmd; cmd=$(stage_cmd "$n")
      if [ "$DRY" = 1 ]; then
        log "  [dry-run] 将执行: $cmd"
      else
        log "  ▶ $cmd"
        eval "$cmd" || { echo "✗ 阶段 $n 失败，停止（修复后重跑，已完成阶段自动跳过）" >&2; return 1; }
        : > "$(marker_of "$n")"
        log "  ✓ 完成，写 marker $(marker_of "$n")"
      fi ;;
  esac
}

# ---------- --list ----------
if [ "$LIST" = 1 ]; then
  echo "profile=$PROFILE  LOCAL=$COURSE_LOCAL_ROOT"
  for n in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
    st="·"; is_done "$n" && st="✓"; printf '  [%s] %2s %-22s %-6s 依赖:%s\n' "$st" "$n" "$(stage_name "$n")" "$(stage_kind "$n")" "$(stage_deps "$n")"
  done
  exit 0
fi

# ---------- 主流程（DAG 线性检查点顺序；阶段内并发由脚本自负） ----------
log "开始推进 profile=${PROFILE}（dry-run=${DRY} from=${FROM} only=${ONLY:-无}）"
[ "$DRY" = 1 ] && log "DRY-RUN：只演示，不执行、不写 marker"
for n in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
  run_stage "$n" || exit 1
done
echo "════════════════════════════════════════"
if [ "$DRY" = 1 ]; then
  log "dry-run 走查结束。核对无误后去掉 --dry-run 正式执行。"
else
  log "已推进到当前可自动完成的最远阶段；manual/todo 阶段按上方指引处理后重跑即可续。"
fi
