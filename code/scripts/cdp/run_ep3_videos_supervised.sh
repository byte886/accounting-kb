#!/bin/bash
# ep3 名师课视频批量「守护启动器」：通用守护器 run_supervised.sh 在 ep3 视频场景的薄封装（各科/各梯度可复用）
#
# 解决的问题：
#   ep3_download_videos.js 长跑时，若 Mac 空闲睡眠或日常 Chrome 的 CDP 连接瞬断，主进程会
#   「零报错静默终止」（日志停在"取 key（CDP 播放）"、无异常栈、无结束标记）。裸 nohup 没人拉起，
#   任务就永久停在中途（2026-09-09 会计全面精讲曾在第 91 讲这样停摆 8 小时）。
#
# 本启动器让通用守护器每一轮：
#   - 断点续跑一遍 ep3_download_videos.js：已下视频幂等跳过、上轮"capture 未取到 key"的重试、
#     没跑到的继续向后；一轮自然结束（或再次静默退出）后 5 秒进入下一轮，只补剩余。
#   - caffeinate -i 在整个生命周期防止 Mac 空闲睡眠（治本）。
#   - 已下 *video.mp4 数 >= 目标数 → [NOTIFY]✅ 完成并退出；连续 3 轮数量不增长 → ❌ 判异常退出。
#
# 用法:
#   nohup bash scripts/cdp/run_ep3_videos_supervised.sh <profile> <梯度> <目标视频数> [dual标志] \
#     > data/_workspace/_account/ep3/logs/superv_<profile>_<梯度>.log 2>&1 & disown
# 例（会计全面精讲，双老师 485 个视频文件）:
#   nohup bash scripts/cdp/run_ep3_videos_supervised.sh ep3-accounting-2026 全面精讲 485 --dual-teacher \
#     > data/_workspace/_account/ep3/logs/superv_acct_jingjiang.log 2>&1 & disown
#
# 目标视频数 = 该梯度 *video.mp4「文件」总数（双老师要把各老师视频数相加，不是讲目录数）。
# 会计全面精讲：姚远236+陈蓓蓓249=485 个视频文件，归并到 261 个统一讲目录（--dump-plan 实测）。
# 单老师梯度才等于 outline videoTotal（税法170/战略122/经济法157，均为单口径，双老师时同样要相加）。
# 明细日志在 data/_workspace/_account/ep3/logs/<profile>_<梯度>.log（追加不覆盖）。

set -u

PROFILE="${1:?用法: run_ep3_videos_supervised.sh <profile> <梯度> <目标视频数> [--dual-teacher]}"
STAGE="${2:?缺少梯度名，如 全面精讲}"
TARGET="${3:?缺少目标视频数（该梯度视频叶子数，见 outline 实测 videoTotal）}"
DUAL="${4:---dual-teacher}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

# 视频成品目录从 profile 卡读 localRoot 拼，避免在脚本里写死各课中文路径
VDIR=$(node -e 'const {loadProfile}=require("./scripts/cdp/load_profile");const p=loadProfile(process.argv[1]);process.stdout.write(p.paths.localRoot+"/原始资源/videos/"+process.argv[2])' "$PROFILE" "$STAGE")
LOGDIR="data/_workspace/_account/ep3/logs"
mkdir -p "$LOGDIR"
DETAIL="$LOGDIR/${PROFILE}_${STAGE}.log"

RUN_CMD="node scripts/cdp/ep3_download_videos.js --profile $PROFILE --stage $STAGE $DUAL >> $DETAIL 2>&1"
DONE_TEST="test \$(find \"$VDIR\" -name '*video.mp4' 2>/dev/null | wc -l | tr -d ' ') -ge $TARGET"
PROG_CMD="find \"$VDIR\" -name '*video.mp4' 2>/dev/null | wc -l | tr -d ' '"

# 视频线不依赖屏幕弹窗（终态由 AI 巡检日志接手）；caffeinate -i 防空闲睡眠
export SUPERVISE_NO_OSASCRIPT=1
exec caffeinate -i bash scripts/run_supervised.sh "${PROFILE}-${STAGE}-videos" "$RUN_CMD" "$DONE_TEST" "$PROG_CMD"
