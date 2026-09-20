#!/bin/bash
# sync_ep3_ready.sh — 名师课(ep3)「已就绪内容」安全同步百度网盘
#
# 背景：视频仍在下载时，不能把只有字幕/meta、缺 video 的半成品讲传上去并打 done
# （done 会让该讲以后被永久跳过、网盘缺件）。本脚本：
#   - 讲义 notes：已 OCR 完成、不会再变，整目录同步
#   - 视频 videos：只传「完整讲」——讲目录内每个 *_meta.json（或裸 meta.json）
#     都有对应、非空的 *_video.mp4；未下完的讲不匹配、不打 done，下次重跑自动补
# 核心上传/秒传/断点仍复用 sync_course_netdisk.sh + upload_course.sh，本脚本只做"就绪筛选"。
#
# 用法: bash scripts/sync_ep3_ready.sh <profile> [并发=2] [notes|videos|all(默认)]
# 例:   bash scripts/sync_ep3_ready.sh ep3-accounting-2026 2 all
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

PROFILE="${1:?用法: sync_ep3_ready.sh <profile> [并发=2] [notes|videos|all]}"
PAR="${2:-2}"
WHAT="${3:-all}"
export GAODUN_COURSE_PROFILE="$PROFILE"

# 从 profile 读本地/网盘根（与 Node/Python 读取器同源，不 source 旧单课配置）
read L R < <(python3 - "$PROFILE" <<'PY'
import json,sys
p=json.load(open(f"config/courses/{sys.argv[1]}.json",encoding="utf-8"))
print(p["paths"]["localRoot"], p["paths"]["remoteRoot"])
PY
)
echo "[ep3-ready] profile=$PROFILE  并发=$PAR  范围=$WHAT"
echo "[ep3-ready] L=$L"
echo "[ep3-ready] R=$R"

# 输出某阶段下「完整讲」目录名的转义正则交替（供 sync_course_netdisk 的 FILTER 用）
ready_filter() {
  python3 - "$1" <<'PY'
import sys,re,pathlib
stage=pathlib.Path(sys.argv[1]); out=[]
for lec in sorted(stage.iterdir()):
    if not lec.is_dir() or lec.name.startswith("."):
        continue
    # 只认双老师改造后的 <老师>_meta.json；裸 meta.json 为单老师时代遗留（视频已在带前缀文件中），
    # 若计入会因找不到裸 video.mp4 而把整讲误判为不完整、漏传网盘（2026-09-11 对齐 throttled 口径）
    metas=list(lec.glob("*_meta.json"))
    if not metas:
        continue  # 非视频讲保守不传
    ok=True
    for m in metas:
        stem=m.name[:-len("_meta.json")] if m.name.endswith("_meta.json") else ""
        v=lec/(f"{stem}_video.mp4" if stem else "video.mp4")
        if not (v.exists() and v.stat().st_size>1000):
            ok=False; break
    if ok: out.append(re.escape(lec.name))
print("|".join(out))
PY
}

case "$WHAT" in
  notes|all)
    if [ -d "$L/原始资源/notes" ]; then
      echo "### notes 讲义 $(date +%T)"
      bash scripts/sync_course_netdisk.sh "$L/原始资源/notes" "$R/原始资源/notes" "$PAR"
    fi
    ;;
esac

case "$WHAT" in
  videos|all)
    for stage in "$L/原始资源/videos"/*/; do
      [ -d "$stage" ] || continue
      bn="$(basename "$stage")"
      flt="$(ready_filter "$stage")"
      if [ -z "$flt" ]; then echo "[跳过阶段 $bn：当前无完整讲]"; continue; fi
      echo "### videos/$bn 完整讲同步 $(date +%T)"
      bash scripts/sync_course_netdisk.sh "${stage%/}" "$R/原始资源/videos/$bn" "$PAR" "$flt"
    done
    ;;
esac

echo "[ep3-ready] 本轮结束 $(date +%T)"
