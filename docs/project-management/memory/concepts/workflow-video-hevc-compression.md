---
type: Workflow
title: 名师课 H.265 重压的双机并行分工与常驻保活
description: 六科名师课约 2062 个 h264 1080P（约 1TB）单机压约 8 天，改双机科目零重叠并行：本机（20核，主存储）压审计/战略/经济法/税法，目标机（16核+外置机械盘 /Volumes/backup）压会计/财管，数据 rsync 同构相对路径迁移、不走 git；compress_ep3_videos.py 用 --jobs N（x265 pools）按忙闲调档、--reverse 倒序，ffprobe 幂等 skip hevc、.compress_tmp 原子替换、flock 单实例；本机用 launchd LaunchAgent 常驻总管（抗 Doubao 会话清理），目标机用 nohup caffeinate 看门衔接会计→财管；改档即重启、约 2-4 分钟 probe 自愈；目标机压完 rsync 回传本机主存储闭环。
tags: [ep3, mingshi, video, h265, hevc, libx265, crf30, dual-machine, rsync, launchd, caffeinate, supervisor, workflow]
sources:
  - id: adr-022
    resource: ../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md
    title: ADR-022 双机并行 H.265 重压与整科门控网盘覆盖
  - id: adr-002
    resource: ../../decisions/ADR-002-视频压缩标准.md
    title: ADR-002 视频压缩标准（CRF30/libx265 参数基线）
  - id: video-processing
    resource: ../../../development/tools/video-processing.md
    title: 视频处理详细指南（双机并行重压与常驻保活小节）
generated: { by: "doubao/okf-wiki", at: "2026-09-16T23:10:00+08:00" }
status: stable
---

# 名师课 H.265 重压的双机并行分工与常驻保活

## 一句话结论

采集得到的 h264 1080P 用 `code/scripts/compress_ep3_videos.py` 离线重压为 hevc（参数同 ADR-002，**不走抽音频**）；为缩短约 8 天的单机压期，**两台 mac 科目零重叠并行**，本机 launchd 总管、目标机 nohup 看门各自常驻保活，`--jobs` 随忙闲调档、压完一科自动衔接/触发上云。决策与完整踩坑见 [ADR-022](../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md)，操作步骤见 [video-processing.md](../../../development/tools/video-processing.md)。

## 双机分工（零重叠，避免同文件双写分叉）

- **本机（20 逻辑核，项目主存储、git 仓所在）**：审计、战略、经济法、税法。
- **目标机（16 逻辑核，数据在外置机械盘 `/Volumes/backup`，HFS+）**：会计、财管。
- 代码/文档目标机 `git clone` 公有仓；**课程数据不走 git（gitignore）**，本机 `rsync -az` 推到目标机**同构相对路径** `data/高顿/CPA/【VIPCPA专享】名师专业课-<科>/...`，脚本全用相对路径。
- 目标机 ffmpeg/ffprobe 在 `/usr/local/bin`、python 用 `/usr/local/bin/python3`，远程命令先 `export PATH=/usr/local/bin:$PATH`。
- **闭环**：目标机压完的 hevc 要 rsync 回传本机主存储同名覆盖留档（防双机 h264/hevc 分叉），回传核验后再删目标机文件滚动腾空间。回传实操（2026-09-19 会计37G+财管27G 共 64G 已闭环）：①先 `rsync -ani --itemize-changes` dry-run 确认变更面——`>f` 才是传内容（实测全是 `_video.mp4`）、`.d..t` 仅目录时间戳、字幕等 size+mtime 一致不动；②macOS 自带 **openrsync（protocol 29）**，大文件经 ssh 偶发 `hash does not match, will redo`，是单文件校验失败自动重传、可自愈（本次 10 次、两科终 rc=0），非致命；③**回传后必须全量 ffprobe 双保险**——verify_netdisk_final 只比字节大小、不验可解码，回传覆盖后用 python 线程池并发 ffprobe 逐个确认 `codec_name=hevc` 且可解析（961 视频 0 异常才算闭环）；④含讲义整科网盘 rc0 只能在回传后的本机做（见 netdisk concept 跨机口径）。

## 压缩驱动与档位

- 参数：libx265 / CRF30 / preset fast / `-x265-params pools=N:frame-threads=4:wpp=1` / AAC 96k / hvc1 / faststart。
- `--jobs N` 控 x265 线程池、`--reverse` 倒序遍历（两台从两端推进）；flock 单实例锁 `data/_workspace/_account/ep3/compress.lock`，**绝不开第二个压缩实例**（x265 已吃满核，多开只互相抢）。
- 幂等：压前 ffprobe 读 v:0 编码，hevc 跳过、只压 h264；写 `.compress_tmp__<老师>_video.mp4`，验证（hevc/分辨率不变/时长容差 max(3s,0.1%)/可解析）通过才同名覆盖，失败删临时文件保留原片。
- 档位随忙闲（易变、以现场负载为准）：本机 20 核白天 8 / 闲时 12–13 / 夜间 17；目标机 16 核白天 6 / 闲时 9–11。**外置机械盘 IO 是瓶颈，目标机 jobs 超过约 11 后 ffmpeg 吃不满核、IO wait 明显，再高收益小。**
- 改档＝改脚本 `JOBS` 后重启压缩（本机 `launchctl unload/load` 总管、目标机 kill 看门与压缩后重启看门）＋清 `.compress_tmp__*`；只中断当前一个文件、幂等续压。**重启后约 2–4 分钟（全量 ffprobe probe）才重新拉起，是正常自愈，不要反复 reload 观察。**

## 常驻保活（关键：必须与会话解耦）

- 裸 `nohup` 只挡 SIGHUP，启动它的 Doubao 会话关闭时会被进程组连带 KILL（曾夜间静默停摆约 6h）。
- **本机**：launchd LaunchAgent `~/Library/LaunchAgents/com.gaodun.ep3-local-supervisor.plist`（RunAtLoad + `KeepAlive{SuccessfulExit=false}`）跑 `code/scripts/ep3_local_supervisor.sh`，每 120s 巡检压缩+上传，全完成 `exit 0` 不重启、异常被杀才自愈；launchd 的 PATH 只有系统目录，脚本内必须 `export PATH=/usr/local/bin:$PATH`。
- **目标机（不跑 Doubao）**：`nohup caffeinate -dimsu bash logs/target_compress_watch.sh`（会计→财管压缩衔接）与 `target_netdisk_watch.sh`（按科滚动限速上云：某科全 hevc 即传、可与他科压缩并行）。
- 两台均 `sudo pmset -a sleep 0 disksleep 0 disablesleep 1` 防睡眠，**任务结束要恢复默认**（2026-09-19 收尾实测：`sudo pmset -a disablesleep 0 disksleep 10 displaysleep 10`，台式 sleep 保持 0；恢复后 pmset 不再显示 SleepDisabled 行）。
- **任务终态收尾清单**：①本机 `launchctl unload ~/Library/LaunchAgents/com.gaodun.ep3-local-supervisor.plist` 停总管开机自启（plist 文件保留、未来 load 复用），确认两台无 sync/看门/compress/ffmpeg/caffeinate 残留；②目标机本地适配若上游已含等价功能（如 compress `--jobs/--reverse`），`git stash` 留存后 `git pull --ff-only` 取权威版，**不在目标机维护代码分叉**；③目标机会计/财管 hevc 副本（64G）在回传+整科 rc0 后是冗余第三份；**删前必须 rsync 干跑（目标机→本机）确认 itemize 0 差异**——讲目录里除 `*_video.mp4` 还有每讲 `_subtitle.vtt`/`_transcript.md`/`_meta.json` 与 `.ep3cache`，不能只数视频，要确认本机连字幕/文稿/元数据也一份不缺。本次 2026-09-19 干跑两科均 0 差异、叠加网盘两科整科 rc0 后已提前删除（会计 2435 文件/37G、财管 1417 文件/27G），外置盘可用 601G→664G；data 在 gitignore，删除不影响 git 仓。

## 踩坑（勿重犯）

- `launchctl unload` 总管会**连坐杀死**它 nohup 拉起的压缩子进程（同 launchd job 进程组）；压缩在跑时别为观察而 reload。
- 统计/遍历视频必须排除 `.compress_tmp__*`——临时名以 `_video.mp4` 结尾，`rglob('*_video.mp4')` 会多算（会计 607 曾误报 608）。
- 禁 `pkill -f` / `pgrep -f <脚本>|xargs kill`（模式串匹配自身命令行→自杀 exit 137）；按进程组排除：`PGID=$(ps -o pgid= -p $$)` 后 `ps -axo pid,pgid,command|awk -v g=$PGID '$2!=g&&/正则/{print $1}'`。
- 目标机 bash 3.2 下 `"$JOBS"` 紧跟中文全角括号会被吞进变量名触发 `set -u` unbound；用 `${JOBS}` 定界、看门日志文案用 ASCII。
- 统计编码用 python subprocess + 线程池并发 ffprobe 取 `v:0 codec_name`；不要 `xargs -I{}` 批量 ffprobe 中文超长路径（command line too long 误报）。
- 进度一律 ffprobe 现算（不抄 done/记忆计数）；两台口径偶有 ±1（会计 607/608）即临时文件或 manifest 口径差，以课程 manifest 校正、不影响按实际文件遍历。

## 来源与下钻

- [ADR-022 双机并行 H.265 重压与整科门控网盘覆盖](../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md)
- [ADR-002 视频压缩标准](../../decisions/ADR-002-视频压缩标准.md)
- [视频处理详细指南](../../../development/tools/video-processing.md)（采集后批量重压、双机并行与保活操作小节）
- 关联：[名师课 ep3 取流解密与平台字幕](workflow-ep3-vod-decryption.md)（h264 成片来源）、[网盘 hevc 整科门控覆盖同步](workflow-netdisk-hevc-sync.md)（压完如何上云）、[四地存储分工](architecture-storage-layout.md)
