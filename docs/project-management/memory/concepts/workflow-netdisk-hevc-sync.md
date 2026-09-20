---
type: Workflow
title: 名师课网盘 hevc 按科滚动门控覆盖同步与终态核验
description: 压好的 hevc 上百度网盘替换早期 h264 备份，核心是"按科滚动门控"（2026-09-17 由整科门控放宽）——某科全部视频 ffprobe 非 hevc=0 且当前没在压该科（本机看该科 videos 无 .compress_tmp、目标机按 --course 进程判）即传该科，可与他科压缩并行、整机一次只传一科，在压科绝不传（ready_filter 只挑完整讲、不判编码，编码门在总管/看门侧；在跑检测只匹配带 python3/bash 前缀的真进程防自匹配漏拉）；首次 hevc 上传前删该 profile netdisk_done 下非 notes__ 的视频 done（保留讲义标记），rtype=3 同名覆盖、每科一次（.videoreset）；两台各自上传、讲并发 1 + BAIDU_UPLOAD_RATE=1100k（networkQuality 实测共享上行 34.6Mbps、满载延迟 1.5s/40RPM，两台各 1100k 最坏合计占~52%、留半给豆包）；网盘真实状态以 verify_netdisk_final.py 递归比对集合+字节大小为准、不信 done，网盘不能 ffprobe，靠"本地 hevc 小 vs 网盘 h264 大"的大小不一致识别旧版。
tags: [netdisk, baidu, hevc, h264, rtype3, done, gate, verify, rate-limit, upload, workflow, mingshi]
sources:
  - id: adr-022
    resource: ../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md
    title: ADR-022 双机并行 H.265 重压与整科门控网盘覆盖
  - id: adr-020
    resource: ../../decisions/ADR-020-课程存储去课程库层与网盘会计知识库分库及百度沙箱根名不可改.md
    title: ADR-020 网盘分库与沙箱根名不可改
  - id: netdisk-setup
    resource: ../../../development/api/netdisk-setup.md
    title: 百度网盘开放平台 API 文档（OAuth/rtype/错误码）
  - id: finalize-sop
    resource: ../../../development/guides/finalize-sop.md
    title: 阶段④收尾 SOP（步骤1 网盘备份：hevc 按科滚动门控覆盖与双机限速）
  - id: netdisk-verify-sop
    resource: ../../../development/guides/netdisk-final-verification-sop.md
    title: 课程 finalize 终态检查 SOP（网盘终态核验、大小判旧版）
generated: { by: "doubao/okf-wiki", at: "2026-09-16T23:10:00+08:00" }
status: stable
---

# 名师课网盘 hevc 按科滚动门控覆盖同步与终态核验

## 一句话结论

**一门课 100% 压成 hevc 且当前没在压该科，就按科上传百度网盘、同名覆盖早期 h264**（2026-09-17 起不必等其他科压完，可与他科压缩并行；整机一次只传一科）；上传前清掉该科的视频 done 标记强制重传、固定 `rtype=3`，两台各自限速并发 1；**是否真的传成 hevc 只认 `verify_netdisk_final.py` 终态核验、不信 done 标记**。决策见 [ADR-022](../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md)，门控/覆盖操作见 [finalize-sop.md](../../../development/guides/finalize-sop.md) 步骤 1、终态核验见 [netdisk-final-verification-sop.md](../../../development/guides/netdisk-final-verification-sop.md)，网盘 API/rtype 见 [netdisk-setup.md](../../../development/api/netdisk-setup.md)。

## 按科滚动门控（防 h264 混传，最重要）

- 启动某科视频上传的充要条件：**该科全部 `*_video.mp4` 经 ffprobe 为 hevc（非 hevc 计数=0）且当前没在压该科**（2026-09-17 由"等压缩进程整体结束"放宽为按科）。"没在压该科"判据：本机看该科 videos 下有无 `.compress_tmp*`（一个 compress 进程可带多个 `--course`，不能只看进程名）；目标机看门按 `pgrep --course <科>`。**正在压的那一科**绝不探测/上传（压几讲传几讲会让网盘同科 h264/hevc 混杂）；其他科全 hevc 即可与在压科并行上传，整机一次只传一科。
- 在跑检测只匹配带解释器前缀的真进程（`pgrep -f 'python3 .*compress_ep3_videos\.py'`、`'bash .*sync_ep3_ready\.sh'`）；裸 `pgrep -f 脚本名` 会误匹配命令行含该文本的 grep/外层 shell（含运维查询命令）而漏拉压缩。
- `code/scripts/sync_ep3_ready.sh <profile> 1 videos` 的 ready_filter 只挑"完整讲"（每个 `*_meta.json` 有对应非空 `*_video.mp4`）、**不判编码**；所以编码门控必须在调用方（本机 `ep3_local_supervisor.sh`、目标机 `target_netdisk_watch.sh`）实现，不能指望 sync 脚本。
- 链路：`sync_ep3_ready.sh`（读 config 的 localRoot/remoteRoot、挑完整讲）→ `sync_course_netdisk.sh`（xargs -P 并发派生 upload_one）→ `upload_course.sh`（讲内串行逐文件，过滤 transcript.json/*.tmp/*.log/.DS_Store）→ `baidu_upload.py`（precreate/upload/create，分片串行、MD5 秒传、固定 rtype=3）。

## hevc 覆盖早期 h264：清视频 done + rtype=3

- 早期已传过一轮 h264 并留有 done 标记，sync 见 done 会跳过 → 网盘残留 h264。
- 某科全 hevc **首次**上传前跑 `reset_videos_done_once`：删 `data/_workspace/<profile>/logs/netdisk_done/` 下所有**非 `notes__` 前缀**的 `.done`（视频标记），**保留 `notes__` 讲义标记**；每科只清一次，用标志 `data/_workspace/_account/ep3/supervisor/<prof>.videoreset`（目标机在 `netdisk_watch/`）。
- done 文件名前缀是**阶段名**（如"全面精讲"），不是字面"videos"；只有讲义那次前缀是 `notes__`。
- 覆盖靠 `rtype=3`（precreate/create 两步都传，见 netdisk-setup 的 rtype 表）；`ondup` 对上传三步无效，误传会静默产生 `_时间戳` 改名副本。

## 双机各自限速

- 两台分别上传自己负责的科目（目标机会计/财管的 done、看门在目标机本地），互不等待。
- 每台**讲并发=1**、`BAIDU_UPLOAD_RATE=1100k`（只给分片 curl 加 `--limit-rate`，list/mkdir 小请求不限）。依据 `networkQuality -s`：两台共享出口上行 34.6 Mbps（≈4.3 MB/s）、满载响应 Low（延迟 1.5s、40 RPM，缓冲膨胀严重）；两台对等各 1100k（≈1.1 MB/s），同时传最坏合计 ≈18 Mbps、占上行 ~52%，留约一半给豆包/交互，再高会重现秒级卡顿（用户硬约束：不影响豆包做事）。

## 终态核验：只认 verify、不信 done

- done 只证明"某次上传动作完成"，不证明网盘当前是 hevc。权威核验：`BAIDU_ENC_PASS=… python3 code/scripts/verify_netdisk_final.py <本地课程根> <网盘课程根> [-x 知识详解]`（递归比对目录/文件集合与**字节大小**，rc=0 才完全一致）。脚本默认排除点开头隐藏/缓存（`.ep3cache` 等，`os.walk` 必须原地剪枝 `dirnames[:]`）；**原始资源滚动备份阶段**知识详解尚在生成/走飞书，用 `-x/--exclude 知识详解`（可重复）显式排除，不拿半成品卡视频备份完成判定；课程完整 finalize、知识详解定稿传云后，再跑一次**不带 -x** 的两层（原始资源+知识详解）全量核验。`code/scripts/netdisk_verify_summary.py <核验日志...>` 分类汇总（讲义缺/不一致、视频缺、视频大小不一致、其中网盘是旧大版、缺讲目录、垃圾分片）。
- 网盘文件无法 ffprobe；识别网盘残留 h264 靠大小——本地 hevc 显著小于 h264（实测样本约 1/13），核验"大小不一致且网盘更大（旧大版）"即需 reset 后覆盖重传。
- 已验证：审计 257、战略 129（2026-09-16）、**经济法 314（2026-09-18，课程根 `-x 知识详解` 核验 rc=0：205 目录/1348 文件本地=网盘，视频 0 缺/0 大小不一致/0 旧大版）**全 hevc 上云。
- 2026-09-17 按科滚动生效：经济法 314 全 hevc 后，在税法仍压缩时即启动上传（本机进入"压税法 + 传经济法"并行）。
- **六科终态（2026-09-19 全部 rc=0）**：审计 276目录/1090文件、战略 144/588、经济法 204/1348、税法 259/1727、会计 345/2460、财管 373/1486，"原始资源（videos+notes）"本地＝网盘逐文件、逐字节一致；2062 视频全 hevc 上云。
- **跨机整科终核口径（重要）**：目标机只 rsync 拷了 videos 压、没拷 notes，在目标机跑整科 verify 会报一堆"网盘有、本机无"的讲义假差异（会计曾报 10 处，皆因目标机缺讲义）；**目标机只配 `verify … 原始资源/videos`（local_root 指 videos 子目录）做视频层 rc0**；含讲义的整科 rc0 必须等会计/财管 hevc **rsync 回传本机后、在讲义最全的本机**跑"原始资源"根。
- **空讲义占位目录＝对象存储假差异**：本地 0 文件空目录（源站该专题无独立讲义、内容在同级合集 PDF+OCR）网盘（对象存储不保留空目录）会报"目录缺失-网盘"，但两侧文件数相等；核实无知识缺口后 `rmdir`（只能删空目录）收口即可，**不要**为此改 verify 静默忽略空目录（保留它发现真缺口的能力）。财管即此 1 处。

## 踩坑（勿重犯）

- `sync_course_netdisk.sh` 无论成败都固定打印"失败讲（无 done 标记且本次匹配）:"标题；**真正失败行才是行首恰好 3 空格 + `- `**。判定成功要 `grep -q "本轮结束" && ! grep -qE '^[[:space:]]{3}- '`；只 grep"失败讲"标题恒为假，会导致总管每轮空转重拉、永不 mark_done、并卡死后续科目上传。**且只扫日志最后一轮**（从最后一个 `[ep3-ready] profile=` 到文件尾）：日志跨轮 `>>` 累积，早期轮次的瞬时失败（后已重传成功）永久留在文件前部，扫整份会被历史失败行卡住、已传齐却反复空转重拉不写 done（2026-09-18 经济法 189 讲已齐、被第 345-347 行历史失败卡住每 2 分钟重拉即此；总管 `log_done` 与目标机看门均已改为只判最后一轮，无 profile 标记的旧日志退化全文判断）。
- xargs 父 bash 被杀后，上传子进程成**孤儿被 launchd 收养继续派生**。清理分层：①杀顶层 sync_ep3_ready/sync_course →②按 upload_one 匹配杀孤儿 xargs 与 `bash -c` →③杀 upload_course/baidu_upload →④`pgrep -x curl`；全程用进程组 PGID 排除当前 shell 防自匹配，连续两轮计数 0 才算根除。禁 `pkill -f`（会匹配自身命令行自杀）。
- **自动上传清单要覆盖全部负责科目**：本机总管循环曾只列审计/税法/经济法而漏了战略，战略实际靠 2026-09-15 一次性补传传齐 hevc（终态核验零差异）；新增/调整负责科目时必须同步进自动覆盖清单，不能依赖人工补传。
- 网盘沙箱根 `/apps/CPA课程归档` 名与授权绑定、禁止 API 改名（ADR-020）；凭证 `.secrets/baidu_credentials.enc` 用 `BAIDU_ENC_PASS` 解密、不入库。
- **运行中 `logs/` 目录被删会让上传静默不起**：总管只在启动时 `mkdir logs` 一次，长跑中项目根 `logs/` 若被（跨窗口清理）删掉，`start_upload` 的 `nohup … >> logs/x.log` 重定向失败、sync 子进程根本不启动，而总管进程照常巡检、零报错（税法 hevc 压完后因此空转约 3.5h，I-017）。修：`mkdir -p logs` 放进每轮巡检循环体 + start_compress/start_upload 内各一次。判活不能只看总管，要查实际 sync 进程与日志 mtime。
- **日志文本判定统一 `LC_ALL=C`**：日志混入 GBK/坏字节中文时，UTF-8 区域的 awk/grep 报 multibyte/towc 警告，可能干扰"最后一轮"切分；`log_done` 的 awk 与 grep 一律加 `LC_ALL=C` 按字节处理。
- **看门"完成判定"必须整段先于"启动判定"**：目标机看门若每轮先判启动、后判完成，某科传齐后 sync 秒退，下一轮先被启动判定拉起、且 `>` 覆盖日志，完成判定永远看到"刚启动/未结束"→ 不写 done、每轮空转重拉（2026-09-18 已修：完成判定前置）。

## 来源与下钻

- [ADR-022 双机并行 H.265 重压与整科门控网盘覆盖](../../decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md)
- [ADR-020 网盘分库与沙箱根名不可改](../../decisions/ADR-020-课程存储去课程库层与网盘会计知识库分库及百度沙箱根名不可改.md)
- [百度网盘开放平台 API 文档](../../../development/api/netdisk-setup.md)（OAuth、rtype、错误码、限速实现）
- [阶段④收尾 SOP · 步骤1 网盘备份](../../../development/guides/finalize-sop.md)（hevc 按科滚动门控覆盖、清 done、双机限速、失败判定）
- [课程 finalize 终态检查 SOP](../../../development/guides/netdisk-final-verification-sop.md)（verify_netdisk_final、大小判旧版、补传）
- 关联：[双机 H.265 重压与保活](workflow-video-hevc-compression.md)（门控的上游）、[四地存储分工](architecture-storage-layout.md)
