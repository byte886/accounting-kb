#!/bin/bash
# parallel.sh — shell 侧统一并发标准件（层2 IO·CPU 两标准件之一）。
#
# 只暴露一个入口 parallel_map：从 stdin 读【NUL 分隔】任务，用 xargs -P 做内核级
# 调度与负载均衡。不允许再自建 flock/mkdir 锁队列（macOS 多进程子 shell 有竞态，
# 曾出现 6 个 worker 重复取到同一讲，见 docs/development/performance/parallel-processing-guide.md §四）。
#
# 并发度选型（同指南，必须实测、不能凭核数估算）：
#   - IO 密集（下载分片/上传/API）：可高并发，受对端限流约束；
#   - CPU 密集：FunASR 转写、x265 压缩实测【串行=1 最优】（FunASR 串行 18.5x > 6 并发 14.3x），
#     OCR 单实例只吃 1 核、可在压缩之余开 1–2；换机器/模型必须重测。
#
# 用法:
#   while ...; do printf '%s\0' "$task"; done | parallel_map <并发N> <worker命令...>
# worker 命令会把单个任务作为【最后一个位置参数】追加调用（xargs -n1）。
# 任务含空格/中文也安全（NUL 分隔 + xargs -0）。
#
# 推荐 worker 形态：主脚本以 `--worker <任务>` 自递归（见 transcribe_parallel.sh），
# 避免依赖 bash export -f（macOS 自带 bash 3.2 下不稳）。
parallel_map() {
  local concurrency="$1"; shift
  if [ "$#" -eq 0 ]; then
    echo "[parallel_map] 用法: <NUL任务流> | parallel_map <并发N> <worker命令...>" >&2
    return 2
  fi
  if ! [[ "$concurrency" =~ ^[0-9]+$ ]] || [ "$concurrency" -lt 1 ]; then
    echo "[parallel_map] 并发数必须是 >=1 的整数，收到: '$concurrency'" >&2
    return 2
  fi
  xargs -0 -P "$concurrency" -n 1 "$@"
}
