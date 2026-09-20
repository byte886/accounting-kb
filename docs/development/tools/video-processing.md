# 视频处理详细指南

> **文档类型**：Task（操作指南）
> **更新频率**：工具变更时
> **维护者**：AI自动维护
> **读者**：AI代理

> 本文档详细说明高顿课程回放视频的下载、解密、压缩与归档流程。
> 包含加密方案逆向分析、详细操作步骤、关键陷阱汇总等内容。
> 总体工作流见 `../WORKFLOW.md` 阶段①。

## 0. 先判断走哪条视频链（务必先做）

账号下有两套平台、两条视频链，**不要用错脚本**：

| 判据 | 正课 glive（saasCourseType=16） | 名师课 ep3（saasCourseType=13） |
|---|---|---|
| 平台 / URL | glivepro.gaodun.com，`/course/{id}/...` | epiphany.gaodun.com，`/ep3/course/{id}` |
| 课程名规律 | 【26考季】VIPCPA系列-XX（某老师），如税法42660/会计42656 | 【VIPCPA专享】名师专业课-XX，会计17244/审计17245/财管17246/税法17247/经济法17248/战略17249 |
| 主控脚本 | `fetch_lecture_video.js`→`download_decrypt.js`→`compress.sh`→FunASR | `cdp/ep3_download_videos.js` 一体 |
| 压缩 / 文字稿 | H.265 CRF30 **重压** + **FunASR 转写**（本文步骤2/3） | 采集时 **copy 封装**、采集后用 `compress_ep3_videos.py` **批量 H.265 CRF30 重压** + **平台 VTT 字幕免转写**（见下方"名师课 ep3"小节） |

判别优先级：**saasCourseType（权威）＞ 域名 URL ＞ 课程名 ＞ 取流响应有无 `result.subtitle`**。判为 ep3 直接跳下方"名师课 ep3（saasCourseType=13）"小节，不要走 H.265 压缩与 FunASR。详见记忆层 `docs/project-management/memory/concepts/reference-course-profiles.md`。

## 前置条件

1. **Playwright Extension 模式**：用户 Chrome 已安装 Playwright Extension 并提供 token
   - 连接命令：`PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach --extension=chrome`
   - 会话名：`ga`
2. **Node.js**：用于下载解密脚本（`code/scripts/video/download_decrypt.js`）
3. **ffmpeg**：需支持 libx265，路径通常为 `/usr/local/bin/ffmpeg`
4. **iTerm2**：压缩命令在 iTerm 窗口中运行，用户可直接看进度

## 加密方案（核心知识）

### HLS 加密结构

高顿课程回放视频为标准 HLS，m3u8 文件包含加密密钥信息：

```
#EXT-X-KEY:METHOD=AES-128,URI=".../replay/authorize?...",IV=0x...
```

- `.ts` 分片可公开下载，但内容是 AES-128-CBC 加密
- 每个分片用相同 IV 独立解密（标准 HLS 行为）
- 解密时需 `setAutoPadding(false)`

### 密钥获取链路

密钥获取涉及浏览器端的复杂通信：

1. **authorize 接口**：返回 92 字节密文
2. **hls.js Worker**：发 `postMessage({type:"decrypt",...})` 给主线程
3. **主线程 WASM 解密**：解密后返回 32 字节响应
4. **实际 AES key**：响应前 16 字节的原始 ASCII 字符串（不是 hex 解码）

### 关键细节

- **密钥不是 hex 解码**：Worker 返回 32 字节 ASCII hex 字符串，但 hls.js 只读前 16 字节原始字节作为 AES key
- **IV 直接取自 m3u8**：`IV=0x...`，去掉 `0x` 前缀使用
- **每个视频密钥不同**：必须逐个捕获，不能复用
- **m3u8 token 会过期**：批量下载时需定期重新打开播放器获取新 token

详细逆向分析见 `encryption.md`。

## 名师课 ep3（saasCourseType=13）平台差异与采集流程

> 正课 glive（saasCourseType=16）走下面"详细操作流程"；**名师专业课（ep3/epiphany，saasCourseType=13）走本节**。决策见 ADR-018，记忆层见 `docs/project-management/memory/concepts/workflow-ep3-vod-decryption.md`，探路实测在过程件 `data/_workspace/_account/ep3-platform-probe.md`。

### 与正课的关键差异（务必先看）

1. **平台自带 VTT 字幕 → ep3 不做 FunASR 转写**。`live/resource` 响应的 `result.subtitle` 是完整 VTT URL（video-resource.gaodun.com），免认证 GET 即标准 WebVTT，抽查覆盖率 100%。直接下 VTT 转 transcript，**省掉本地转写环节**；播放器里的"字幕开关"只控 UI、不影响取 URL。
2. **正式清晰度一律 FHD-1080P**（与正课成片一致）。SD/HD/FHD 三档各有独立 `transcode_id`，故 **m3u8 与 key 三档各不相同**（subtitle 三档相同、唯一）；要 FHD 必须在播放页切到 1080P 取对应 key。
3. **VTT 原始稿属于原始资源**：每讲同时保留 `subtitle.vtt`（原样）与 `transcript.md`（转换稿），不得只留转换稿。
4. **取 key 路线相同但播放动作不同**：key 仍是"32 hex 串前 16 字符的 ASCII 字节、IV=m3u8 IV(hex)、aes-128-cbc + setAutoPadding(false)"；但 ep3 必须调 `window.gp.play()` 让视频真播（`gp.video` 在 closed shadow DOM，DOM 点击播放键无效），清晰度点 `.gp-setting-quality-item` 含"1080"的项（DOM 与 glive 一致），一次播放可同时抓 SD+FHD。**纯 node 调 authorize 全 40301、逆向 gdcrypto.wasm 是已证死路，不要再试**。
5. **讲次/视频 ID 获取链不同**：syllabus 递归到带 `resource_id` 的讲次叶子 → `getVideoInfo` 拿 videoId。
   - getVideoInfo：`/ep-study/api/v1/front/resource/<rid>?courseId=<cid>&csItemId=<cs>&syllabusId=<sid>&is_show_live=0&isRelatedResource=1`，**四个上下文参数缺一不可**（缺报 10161000）。
   - videoId 取 `result.resource.video_id`（= `sewise.source_id`）；**顶层 `sewise_source_id` 恒为 null 是废弃字段，禁用**；`discriminator==='video'` 判定视频讲次。
   - 只读/取流只需 `makeHeaders(jwt)` + `Referer=https://epiphany.gaodun.com/`，不需要 x_gdssid/cookie。
6. **采集时 FHD 分片本就是 h264/aac，ffmpeg `-c copy` 直接封装 mp4（下载阶段不重压，保证取流速度）**。但 copy 产出的是**未压缩 H.264**，单讲常达数百 MB~1GB；**采集完成后另有独立的批量重压环节**（见下方「名师课采集后批量 H.265 重压」）——2026-09-13 用户决策：名师视频也要压缩到"能基本看清课件文字"，**不走抽音频方案**。

### 采集命令（薄编排，复用取 key/解密组件）

```bash
# 1) 先枚举讲次、核对数量与章节路径（不下载）
node code/scripts/cdp/ep3_download_videos.js --course 17244 --parent-grad 23408 \
  --grad 76232 --syllabus 76456 --list

# 2) 批量下载（默认 FHD；断点续跑，单讲失败记 .ep3cache/fails.json 不中断）
node code/scripts/cdp/ep3_download_videos.js --course 17244 --parent-grad 23408 \
  --grad 76232 --syllabus 76456 --out <输出目录> [--limit N] [--dual-teacher]

# 单讲（给 learning URL 即可）
node code/scripts/cdp/ep3_download_videos.js --learning-url "<ep3 learning URL>" --out <目录>
```

- 每讲产出 `<NN_讲名>/{video.mp4(1080P),subtitle.vtt,transcript.md,meta.json}`，临时 `_work` 用完即清（成功路径自动清；中断被杀会残留，见下方完整性核对）。
- **离线完整性核对（每阶段收尾必跑，零网络/零风控）**：`node code/scripts/cdp/ep3_verify_local.js`（加 `--clean` 删除"成品视频已在"的中断残留 `_work`，加 `--json <f>` 落结构化结果）。判级：完整=视频非空且配 VTT；待下=有 meta/字幕但视频未到（进行态正常）；异常=0 字节视频或有视频缺字幕（退出码 1）。它**不武断报"缺老师"**：双老师科目只见 1 位老师的讲列为"单老师讲·待在线核对"（可能本就是老师独有讲，权威以在线 enum 清单为准，离线无法判定）。`--clean` 绝不删"讲内尚无成品视频"的活跃 `_work`（正在下载）。
- 取 key 复用 `code/scripts/cdp/capture_video_key.js`（输出顶层数组 `[{quality,m3u8,keyAscii}]`，按 `videoId:res` 缓存），下载解密复用 `code/scripts/video/download_decrypt.js`。
- 每个视频 CDP 取 key 约 26–30s（后台批量可接受）；双老师资源目录不分老师、文件名加老师前缀用 `--dual-teacher`（姚远_/陈蓓蓓_）。
- 错误码：553649434=token 失效（须只读回包硬证据，先怀疑自身）；10161000=getVideoInfo 缺参数；40301=离线取 key 死路、必须走 CDP 真实播放。**553649434 已在消费者 `apiGet` 层自动续命**（`auth_token_guard.js` 跨进程 single-flight 刷新后重试，I-013），正常情况下无需人工处理；只有日常 Chrome 未登录导致刷新失败时才需介入。

### 名师课采集后批量 H.265 重压（2026-09-13 新增）

名师 copy 成片是未压缩 H.264 1080P（六科 2062 个 mp4、约 1.04TB、总时长约 1281h）。采集齐后用专用驱动离线重压为 H.265，参数与正课 `compress.sh` 完全一致（libx265 / CRF30 / preset fast / AAC 96k / hvc1 / faststart）。

- 驱动：`code/scripts/compress_ep3_videos.py`。**幂等**——压前 ffprobe 读 v:0 编码，已是 hevc 跳过、只压 h264，可任意重跑；压到同目录 `.compress_tmp__` 临时文件，验证（hevc/分辨率不变/时长容差 max(3s,0.1%)/可解析）通过才**同名替换** `<老师>_video.mp4`（meta/vtt/网盘判重不受影响），失败删临时文件、保留原片、记 failed 不中断。
- **全局单实例**：脚本内 fcntl.flock 占 `data/_workspace/_account/ep3/compress.lock`；x265 内部已吃满逻辑核，**不要再开第二个 ffmpeg**（多开不线性提速反互相抢核）。
- 后台长跑（非交互）：`nohup python3 code/scripts/compress_ep3_videos.py > data/_workspace/_account/ep3/logs/compress_run.nohup.log 2>&1 & disown`（脚本内部置 COMPRESS_NONINTERACTIVE=1，符合 compress.sh 的非交互豁免）。先 `--dry-run` 看待压清单、`--limit N` 试跑、`--report` 看进度；断点结果在 `compress_state.jsonl`。
- 顺序默认 战略→审计→经济法→财管→税法→会计（小到大，早出整课）；`--course 战略 --crf 28` 可指定课/调质量。
- 实测样本（财管·关键绩效指标法 37min）：938MB/3540kbps → 73MB/179kbps（**约 1/13**），1080P 与时长零损失，课件印刷字/红蓝重点/手写批注清晰，达标"能看清视频中文字"。单实例 speed≈6.3x，1281h 内容约需 8 天连续，属超长后台任务，**期间可与知识详解生成（LLM/网络）、非视频网盘上传（IO）并行**（资源不重叠）。
- 与网盘衔接：阶段④只传**重压后**视频；某课全部 hevc 后再对该课 `sync_ep3_ready.sh ... videos`。

### 名师课双机并行重压与常驻保活（2026-09-16，ADR-022）

六科约 2062 个 h264 1080P（约 1TB）单机压约 8 天，故用两台 mac **科目零重叠**并行。决策见 [ADR-022](../../project-management/decisions/ADR-022-名师课双机并行H265重压与整科门控网盘覆盖.md)，记忆 concept `workflow-video-hevc-compression`。

**① 分工（零重叠，避免同文件双写分叉）**

| 机器 | 负责科目 | 说明 |
|------|----------|------|
| 本机（20 逻辑核，项目主存储、git 仓） | 审计、战略、经济法、税法 | 目标机成品 rsync 回传后本机为唯一主存储 |
| 目标机（16 逻辑核，外置机械盘 `/Volumes/backup`，HFS+） | 会计、财管 | 外置盘 IO 是瓶颈，jobs 上限约 11 |

**② 数据迁移（代码走 git，数据走 rsync）**：目标机 `git clone` 公有仓拿代码/文档；课程数据 gitignore，由本机 `rsync -az -e "ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes" <本机数据根>/ chenwenjie@<目标IP>:<目标机项目根>/data/高顿/CPA/...` 推到**完全同构的相对路径**。脚本一律相对路径。目标机 ffmpeg/ffprobe 在 `/usr/local/bin`、python 用 `/usr/local/bin/python3`，远程命令先 `export PATH=/usr/local/bin:$PATH`。SSH 免密用 ed25519 公钥且必须显式 `-i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes`（目标机 config 未指定 IdentityFile）；IP 随 WiFi/有线切换，以现场 `ping` 为准（曾用 .14 WiFi、.8 有线）。

**③ 常驻保活（裸 nohup 会随 Doubao 会话关闭被连带 KILL，曾夜间停摆约 6h）**
- **本机 launchd 总管**：`code/scripts/ep3_local_supervisor.sh` + `~/Library/LaunchAgents/com.gaodun.ep3-local-supervisor.plist`（RunAtLoad + `KeepAlive{SuccessfulExit=false}`），每 120s 巡检：无压缩进程且仍有 h264 就拉起压缩，按门控拉起上传，全部 hevc 且上传成功后 `exit 0`（正常完成不重启、异常被杀自愈）。launchd 的 PATH 只有系统目录，脚本内已 `export PATH=/usr/local/bin:$PATH`。
- **目标机（不跑 Doubao）两个 nohup 看门**：`nohup caffeinate -dimsu bash logs/target_compress_watch.sh`（会计→财管压缩衔接）、`nohup caffeinate -dimsu bash logs/target_netdisk_watch.sh`（**按科滚动**限速上云：某科全 hevc 且没在压该科即传、可与另一科压缩并行，整机一次一科，见 [finalize-sop.md](../guides/finalize-sop.md) 步骤 1）。看门为过程件、在 `logs/` 不入库。
- 两台均 `sudo pmset -a sleep 0 disksleep 0 disablesleep 1` 防睡眠；**全部任务结束后恢复默认**（`sudo pmset -a disablesleep 0` 并把 sleep/disksleep 改回）。

**④ `--jobs` 档位与改档**：`--jobs N` 控 x265 `pools=N`，`--reverse` 倒序遍历（两台从两端推进）。参考档（易变、以现场负载为准）：本机 20 核白天 8 / 闲时 12–13 / 夜间 17；目标机 16 核 + 外置 IO 白天 6 / 闲时 9–11（再高受 IO 瓶颈收益小）。改档＝改脚本顶部 `JOBS` → 本机 `launchctl unload <plist> && sleep 3 && find data/高顿/CPA -name '.compress_tmp__*' -delete && launchctl load -w <plist>`；目标机 kill 看门与压缩（PGID 排除法，见⑥）→ 删 `.compress_tmp` → 重启看门。**只中断当前一个文件、幂等续压；重启后约 2–4 分钟（全量 ffprobe probe）才重新拉起压缩，是正常自愈，不要在这段时间反复 reload 观察。** 压缩在跑时不要为观察而 `launchctl unload`——会连坐杀死它拉起的压缩子进程。

**⑤ 进度统计口径（必须排除临时文件）**：用 python subprocess + 线程池并发 ffprobe 读 `v:0 codec_name`，遍历 `rglob('*_video.mp4')` 后**排除含 `.compress_tmp` 的路径**——临时名 `.compress_tmp__<老师>_video.mp4` 以 `_video.mp4` 结尾会被多算（会计 607 曾误报 608）。不要用 `xargs -I{}` 批量 ffprobe 中文超长路径（command line too long 误报）。进度一律现算，不抄 done/记忆计数。

**⑥ 进程清理（禁 pkill -f）**：`pkill -f` / `pgrep -f <脚本> | xargs kill` 的模式串会匹配命令自身命令行导致自杀（exit 137）。可靠做法按进程组排除当前 shell：
```bash
PGID=$(ps -o pgid= -p $$ | tr -d ' ')
ps -axo pid,pgid,command | awk -v g="$PGID" '$2!=g && /x265|VIPCPA|高顿/{print $1}'   # 先看再杀
```

**⑦ 目标机 bash 3.2 兼容**：`"$JOBS"` 后紧跟中文全角括号（如 `JOBS（当前）`）会被 shell 吞进变量名、在 `set -u` 下触发 unbound variable；一律用 `${JOBS}` 定界，看门日志文案用 ASCII。

**⑧ 闭环**：目标机会计/财管压完全 hevc 后，`rsync` 回传本机 `data/高顿/CPA/` 同名覆盖留档（避免本机留 h264、目标机留 hevc 的分叉），跑终态核验（见 [netdisk-final-verification-sop.md](../guides/netdisk-final-verification-sop.md)）后再删目标机已回传文件滚动腾空间。

### 多科目节流调度（白天防风控 + 给前台/豆包留资源，2026-09-10）

**为什么需要**：多路消费者齐发 × 每路 64 分片并发会把网络/磁盘打满，挤掉豆包与后端通信（表现为豆包卡死不回答）；业务网关取 key 接口密度过高也有账号风控风险。注意区分：视频 ts 分片走 CDN，下载带宽大小（如 14MB/s）本身不是风控点；真正敏感的是 apigateway.gaodun.com 取 key/学习接口的调用频率，以及高并发连接的"爬虫化"密度。

**唯一推荐入口**：bash code/scripts/cdp/throttled_ep3_download.sh（任务队列在脚本内 TASKS，科目/阶段由 config/ep3_subjects.json 驱动）。

- 1 个生产者串行轮询所有「科目×阶段」预取 key（round_robin_prefetch.sh，全进程只有它操作 Chrome，避免多进程抢播放页）；消费者纯 --consumer 只从 keycache 读 key 下载、不碰 Chrome。
- **key 缓存按「profile×阶段」独立成文件 `<profile>__<阶段>.json`，且生产者只给"当前确有活跃消费者进程"的阶段、每轮滚动预取 prefetch_count 个**（pgrep 识别 `--stage X --consumer`，生产者自身是 --prefetch-only 不会误匹配）。没有消费者在下载的阶段不提前取 key，避免 m3u8 token 闲置过期。
- 同时在跑的消费者路数受 MAX_PARALLEL 限制（默认 3），结束一路自动补下一路；夜间提速用 MAX_PARALLEL=6 重跑（断点续跑，已存在跳过）。
- 所有子进程统一 nice -n 20 taskpolicy -c utility 降到后台调度类：前台 App（豆包/Chrome）需要资源时立即让出；这是解决"下载把豆包挤死"的关键。
- 分片并发分时段自适应（在 ep3_download_videos.js 内）：白天 6:00–24:00 单路 12、夜间 0:00–6:00 单路 64；显式 --concurrency 优先。config/ep3_subjects.json 的 prefetch_count 白天取 8。
- 并发计数只统计消费者 PID（kill -0 探测），不能用 jobs -rp——后者会把生产者后台 job 也算进去，生产者 1+消费者 2 即误顶满上限、把第三路永久卡死（macOS 自带 bash 3.2 不支持 wait -n，故用 PID 数组轮询）。
- 消费者偶发启动卡死（进程在、CPU=0、零日志、无网络连接）多为启动拉课程树时请求挂起；直接 kill -9 该消费者，调度器下一轮检测到退出会自动补位（已下载视频断点跳过，无损失）。
- 单讲 m3u8/分片偶发 curl 失败不中断，记 fails，待主体下完后重跑调度器统一补。
- **踩坑（2026-09-10 修复，勿回退）**：① 同一 profile 多阶段（会计四阶段）绝不能共用一个 key 缓存文件——消费者只读不删 key、缓存只增不减，旧版用"缓存总条数 ≥ max 阈值就跳过整个 profile"会让先跑阶段把缓存顶高、连带把后跑阶段（重点强化）永久饿死、消费者等 key 30 分钟超时漏片。② 长跑生产者不要 `set -e`，单条命令瞬时失败会整体退出；任务 total/offset 字段必须做纯数字兜底，否则空值进整数比较会报 `integer expression expected` 空转。

## 详细操作流程

### 步骤1：下载与解密（CDP 自动化主链路）

现役链路**不需要**手动 attach 浏览器、手动点回放或手动抓密钥——保持日常 Chrome 已登录高顿即可，脚本经 CDP 自动连接、抓流、解密合并：

- **单讲**：`node code/scripts/cdp/fetch_lecture_video.js <idx> [--profile <key>]`
  - 一轮内连续完成：从 syllabus 取该讲最新回放 token → CDP 抓 HLS（SD/FHD）密钥 → 下 m3u8 解析 IV → 下载分片并解密合并为 `merged.ts`（底层复用 `download_decrypt.js`，20 并发、断点续传）
  - `idx` 为 course_catalog / syllabus children 下标；课程目录、courseId、syllabusId 全部读 `config/courses/<key>.json`（缺省税法，或用 `GAODUN_COURSE_PROFILE` / `--profile` 指定）
  - **讲目录命名（统一规则，只约束未来下载）**：目录名 `NN_平台讲名`，`NN = String(idx-1)` 两位补零——**idx=1 的开班典礼前缀 `00`、正课从 `01` 起**（`fetch_lecture_video.js` / `download_lecture_notes.js` 同一规则，视频与讲义讲目录一致）；目录名**只替换文件系统非法字符，忠实保留平台标题里的中文 `&`、`、`、（）、·**，不做跨课程分隔符归一化（强改会与平台标题不一致、断链）。历史既成不回溯：税法（蔡俊峻）为早期规则、开班=`01`、正课从 `02`，保持原样。
  - 幂等：目标讲目录已有成品则跳过；m3u8 / authorize token 会过期，故抓流→下载必须同一轮连续完成
- **整门课批量（首选·动态并行）**：`bash code/scripts/video/video_dynamic_pipeline.sh <start> <end>`（下载/压缩/转写三阶段反馈式动态并行，按整机空闲核实时调度，`--dry-run` 只扫描预览不启动）
- **整门课批量（串行后备）**：`bash code/scripts/video/batch_video_pipeline.sh <start> <end>`（断点续跑，已完成讲自动跳过；下载后串行压缩并衔接转写）
- **过程件落位（两条链路一致）**：下载/压缩的 `.vfetch`（ts 分片、merged.ts）统一落 `data/_workspace/<profile>/dl-tmp/NN_讲名/`，压缩后成品归位 `原始资源/videos/NN_讲名/`，转写完成即删工作区，**课程库根全程不出现讲目录**。单独跑 fetch 可用 `--work-base <dir>` 覆盖工作区基准（缺省为课程根，仅供旧链路兼容）
- **进程观测（避坑）**：`ps | grep video_dynamic_pipeline` 会把主控 fork 的 worker 子 shell 一并列出（子 shell 继承脚本命令行，看起来像又起了一个主控）；辨认唯一主控要看 PPID 链（worker 的父即主控），勿据此误判双开

解密原理（密钥取 hls.js Worker 返回前 16 字节原始 ASCII、IV 取 m3u8 `#EXT-X-KEY` 去 `0x` 前缀、分片解密后首字节应为 `0x47` TS sync byte）见上文「加密方案」与 `encryption.md`，日常下载无需手动操作。

> 旧的手动 Playwright run-code 路线（`attach --extension` → 手动遍历回放 → `run-code capture_key.js` → 手动 curl m3u8）已被上述 CDP 链路完全取代，相关脚本于 2026-09-08 清理。

### 步骤2：压缩（必须在 iTerm 中运行，禁止后台运行）

> ⚠️ **强制要求：必须在 iTerm 终端窗口中运行，禁止使用 `&` 后台运行！**
>
> **为什么必须在 iTerm 中运行：**
> 1. 用户可以实时看到 ffmpeg 编码进度（frame、time、speed、bitrate 等）
> 2. 可以及时发现编码错误或异常
> 3. 后台运行可能因进程管理问题导致异常退出（已发生过：输出只有8.3MB不完整）
> 4. 压缩完成后脚本会自动验证时长和可播放性，需要终端输出验证结果
>
> **违反后果：** 如果发现使用后台运行压缩，必须立即停止，删除不完整文件，在 iTerm 中重新运行。

```bash
# ✅ 正确方式：在 iTerm 新标签页中运行（用户可见 ffmpeg 实时进度）
osascript -e "tell application \"iTerm\"
  tell current window
    create tab with default profile
    tell current session
      write text \"cd '<output_dir>'; bash '<skill_dir>/code/scripts/video/compress.sh' merged.ts video.mp4 30\"
    end tell
  end tell
end tell"

# ❌ 错误方式：禁止后台运行
# bash compress.sh merged.ts video.mp4 30 &
# nohup bash compress.sh merged.ts video.mp4 30 &
```

**压缩参数**：
- 视频编码：libx265 (H.265)
- CRF：30（课件文字清晰、头像略糊但不影响学习）
- preset：fast（编码速度与压缩率的平衡）
- 音频：AAC 96kbps
- 标签：hvc1（Apple 设备兼容）
- faststart：开启（支持边下边播）

**ffmpeg 进度解读**：
- `frame=98521`：已编码帧数
- `fps=168`：编码速度（帧/秒）
- `q=32.0`：量化参数
- `size=171776KiB`：当前输出大小
- `time=01:48:22.25`：已编码视频时长
- `bitrate=216.4kbits/s`：当前码率
- `speed=11.1x`：编码速度是播放速度的11.1倍
- `elapsed=0:09:45.79`：已用时间

**进度计算**：已编码时长 / 总时长 × 100%

**检查时间约定（必须遵守）**：
- 压缩启动后，**每5分钟检查一次进度**（不要等待10分钟以上）
- 检查内容：ffmpeg进程是否在运行、视频文件大小是否在增长、最新编码时长
- 如果发现ffmpeg进程异常退出（不在运行但文件大小不增长），立即删除不完整文件，在iTerm中重新启动压缩
- 压缩完成后（ffmpeg进程退出且日志显示"encoded"），立即验证视频完整性（时长、编码格式、可播放性）
- **禁止长时间不检查**：已发生过压缩异常退出但未及时发现的情况，浪费了大量时间

压缩完成后 compress.sh 自动验证时长和可播放性。

### 步骤3：下载讲义文档

在课程表页，每个直播场次下有"讲义|"/"课件|"前缀的条目，带"下载"链接。

#### 6.1 后台自动下载（必须遵守）

**⚠️ 约束：必须使用后台自动下载，禁止弹出下载确认对话框。**

此问题已发生多次，必须严格遵守以下流程：

**方法1：关闭Chrome下载询问（推荐，一次性设置）**

1. 打开 Chrome 设置 → 下载内容（chrome://settings/downloads）
2. 关闭"下载前询问每个文件的保存位置"开关
3. **不需要改变默认下载目录**，保持Chrome默认设置即可
4. 设置完成后，后续所有下载都会自动后台进行，不会弹出确认框
5. 下载完成后，按6.2节流程将文件从默认下载目录移动到流程规定的指定位置

**方法2：直接获取下载链接用curl下载（备选）**

如果无法调整Chrome设置，可以通过拦截网络请求获取下载链接，然后用curl下载到指定位置：

```bash
# 1. 点击下载按钮前，开启网络请求监听
# 2. 点击下载按钮，捕获下载请求的URL
# 3. 用curl直接下载到目标目录（不需要后续移动）
curl -L -o "原始资源/notes/NN_模块/讲义_名称.pdf" "下载链接" \
  -H "Cookie: 从浏览器复制" \
  -H "User-Agent: Mozilla/5.0 ..."
```

#### 6.2 下载操作流程

```bash
# 1. 用 snapshot 找到讲义下载按钮的 ref
npx playwright cli -s=ga snapshot | grep -A 3 "讲义\|下载"

# 2. 使用原生 click 命令点击下载按钮（不要用 eval click）
npx playwright cli -s=ga click <ref>

# 3. 等待下载完成（根据文件大小等待，小文件5秒，大文件30秒）
sleep 10

# 4. 检查 ~/Downloads/ 目录中的新文件
ls -lt ~/Downloads/ | head -5

# 5. 移动并重命名到目标目录
mv ~/Downloads/下载的文件.pdf "原始资源/notes/NN_模块/讲义_名称.pdf"
```

**注意事项：**
- 下载按钮可能在折叠的讲义列表中，需要先点击讲次标题展开
- Chrome 下载的临时文件名格式为 `.com.google.Chrome.xxxxx`，下载完成后会自动重命名
- 如果临时文件没有自动重命名，说明下载可能未完成，需要等待或重新下载

#### 6.3 完整性验证（必须执行）

下载完成后，必须验证文件完整性：

```bash
# 1. 检查文件类型
file "原始资源/notes/NN_模块/讲义_名称.pdf"

# 2. 检查PDF页数（macOS）
mdls -name kMDItemNumberOfPages "原始资源/notes/NN_模块/讲义_名称.pdf"

# 3. 检查PDF是否以%%EOF结尾（完整性标记）
tail -c 100 "原始资源/notes/NN_模块/讲义_名称.pdf" | grep -q "%%EOF" && echo "✓ 完整" || echo "⚠️ 可能不完整"

# 4. 对比文件大小与页面显示的大小
ls -lh "原始资源/notes/NN_模块/讲义_名称.pdf"
```

**验证标准：**
- PDF 文件必须有 `%%EOF` 结尾标记
- 文件大小应与页面显示的大小一致（误差 < 5%）
- 页数应合理（讲义通常5-50页，课件通常10-100页）
- 文件类型应为 `PDF document`

**文档格式**：可能是 PDF、PPT、DOC 等，以实际下载为准。下载后用 `file` 命令确认格式。

### 步骤4：目录结构

```
<download_root>/
├── 税法-蔡俊峻/
│   ├── 01_税法全面精讲01-税法总论/
│   │   ├── video.mp4          # 压缩后视频（最终归课程 原始资源/videos/NN_讲题/）
│   │   ├── playlist.m3u8      # m3u8 备份
│   │   ├── segments/          # 解密分片缓存（可删除）
│   │   ├── merged.ts          # 合并后原始TS（可删除）
│   │   └── notes/             # 讲义课件 PDF（最终归课程 原始资源/notes/NN_模块/）
│   ├── 02_.../
│   └── ...
├── 会计-罗翔/
│   └── ...
└── _reports/                  # 任务报告
```

### 步骤5：验证清单

每个视频压缩后必须确认：
- [ ] ffprobe 能正常读取（moov atom 存在）
- [ ] 输出时长与输入时长差 < 2 秒
- [ ] 视频编码为 hevc，分辨率 1920x1080
- [ ] 音频编码为 aac
- [ ] 文件可正常播放（首尾都有画面）

### 步骤6：百度网盘上传（可选）

百度网盘开放平台 REST API 支持文件上传、目录管理（mkdir/move/delete/rename）。
配置和使用见 `netdisk-setup.md`。

## 关键陷阱汇总

### 浏览器与 Playwright

1. **Extension 模式下 CDP 不可用**（"Not allowed"），只能用 Playwright CLI 命令
2. **Worker hook 必须在 reload 前注入**（addInitScript），否则 Worker 已创建无法拦截
3. **ref 是动态的**：每次页面变化后重新 snapshot/find
4. **播放器自定义元素在 closed shadow DOM 内**：通过 `.gp-video-wrap` 子元素的 `.video` 属性访问

### 加密与密钥

5. **密钥不是 hex 解码**：Worker 返回 32 字节 ASCII hex 字符串，但 hls.js 只读前 16 字节原始字节作为 AES key
6. **m3u8 token 会过期**：批量下载时需定期重新打开播放器获取新 token
7. **每个视频密钥不同**：必须逐个捕获，不能复用

### 压缩与处理

8. **课程表 tab 可能因内存崩溃**（ffmpeg 占内存），需重新加载
9. **压缩参数 CRF 30**：经测试课件文字清晰、头像略糊但不影响学习，如需更高质量可降低 CRF（如 28），但体积会增大

### 知识库操作（扩展）

10. **知识库操作必须使用API**：所有知识库操作（创建、更新、删除、移动节点）必须使用lark-cli，不使用Playwright手动操作
11. **站内导航链接用 `<cite>` 内部引用，不用完整 URL**：同步飞书的文档内，指向其他知识库节点的链接一律由 `wiki_link_resolve.py` 转成 `<cite type="doc" doc-id="obj_token"/>`（渲染为目标标题、obj 强绑定可回读校验）；完整飞书 URL（`https://.../wiki/[node_token]`）冗长、易随节点变动失效，仅外链才用。**注意（2026-09-07 真实 Chrome CDP 可信点击实测）**：cite 与完整 URL 点击都在新标签页打开，飞书正文跨文档跳转统一新开、写入格式无法改本窗口，唯一当前窗口切换是左侧知识库目录树；导航型页面（总览、章 README）顶部加引导说明。本地源文件仍保留 `./标题.md` 相对链接。
12. **同步后必须执行结构检查**：避免出现重复节点、空节点、错误位置等问题，使用`code/scripts/check/check_kb_structure.sh`
13. **具体产出物放对应课程目录**：专项质检（VERIFICATION.md，按需）等放在对应课程目录下，不放在通用目录；做题/同步验证默认并入任务报告、不单独成文
14. **删除节点是异步操作**：`lark-cli wiki +node-delete`是异步的，需要轮询任务状态确认完成

## 相关脚本

| 脚本 | 位置 | 说明 |
|------|------|------|
| 单讲下载主控 | `code/scripts/cdp/fetch_lecture_video.js` | 取回放token→CDP抓key→下m3u8→解密合并（内部调下面两个） |
| CDP 密钥捕获 | `code/scripts/cdp/capture_video_key.js` | CDP 连日常 Chrome、注入 Worker hook，抓 m3u8(SD/FHD) 与 AES key；支持正课 glive 与名师课 ep3（ep3 用 gp.play() 真播+点1080P，输出顶层数组） |
| 下载解密 | `code/scripts/video/download_decrypt.js` | HLS分片下载解密合并脚本（glive/ep3 零改动复用） |
| **名师课 ep3 采集编排** | `code/scripts/cdp/ep3_download_videos.js` | ep3(saasType13) 讲次枚举→getVideoInfo→FHD m3u8+VTT→取key→解密→ffmpeg copy→subtitle.vtt/transcript.md；`--list`/`--learning-url`/批量，断点续跑、双老师前缀 |
| 压缩脚本 | `code/scripts/video/compress.sh`（正课单讲）、`code/scripts/compress_ep3_videos.py`（名师批量） | 正课 glive 用 compress.sh；名师 ep3 采集时 copy、采集后用 compress_ep3_videos.py 批量 H.265 CRF30 重压（幂等/单实例/断点，见「名师课采集后批量 H.265 重压」） |
| 知识库结构检查 | `code/scripts/check/check_kb_structure.sh` | 自动检测重复节点、空节点、链接问题 |

## 参考文档

| 文档 | 位置 | 说明 |
|------|------|------|
| 加密逆向分析 | `docs/development/api/encryption.md` | HLS AES-128 加密详细逆向分析 |
| ep3 取流决策 | `docs/project-management/decisions/ADR-018-名师课ep3取流解密平台路由与平台字幕替代转写.md` | 名师课 ep3 平台路由、取 key、FHD、VTT 替代转写的决策记录 |
| ep3 链路记忆 | `docs/project-management/memory/concepts/workflow-ep3-vod-decryption.md` | ep3 采集稳定结论编译页 |
| 百度网盘 | `docs/development/api/netdisk-setup.md` | 百度网盘API配置和使用 |
| 总体工作流 | `../WORKFLOW.md` | 完整工作流（下载→压缩→转写→知识库→做题验证） |
| 知识库组织规范 | `knowledge-base-organization.md` | 知识库结构设计、节点命名规范、父页面规范 |
| 飞书API使用说明 | `feishu-api.md` | wiki节点删除、文档更新、权限设置、常见问题 |
