# 工程记忆 bundle 变更日志（log）

> 只记**记忆层本身**的结构变更（新增/退役/合并 concept、采用决策变化）。
> 业务与代码的完整变更时间线看仓库根 `CHANGELOG.md`；本页不重复业务流水。
> 规则：日期标题 `## YYYY-MM-DD`，最新在最上（倒序）。

## 2026-09-19

- **Update（workflow-netdisk-hevc-sync / workflow-video-hevc-compression）**：六科 hevc 网盘主线终态完成（2026-09-19 晚），沉淀 5 条收尾结论：①**含讲义整科终核口径**——目标机只拷视频压、无 notes，仅配 `videos` 子目录 rc0（整科比会报"网盘多 notes"假差异，会计曾报 10 处皆此）；会计/财管 hevc 必须 rsync 回传讲义最全的本机后，再跑"原始资源"根整科 rc0；六科含讲义整科全部 rc0、2062 视频全 hevc 上云。②**空讲义占位目录假差异**——本地空目录（源站该专题无独立讲义、内容在合集 PDF）对象存储不保留，verify 报"目录缺失-网盘"但文件数相等；确认无知识缺口后 rmdir 收口（**不**改 verify 静默忽略空目录，保留其发现能力）。③**rsync 回传实操**——macOS 自带 openrsync(protocol29)，`-ani` itemize 判变更（`>f` 传内容、`.d..t` 仅目录时间戳），大文件偶发 `hash does not match, will redo` 单文件自愈（本次 10 次终 rc0），回传后必须 ffprobe 全量双保险（verify 只比字节大小、不验可解码）。④**logs 目录运行中被删静默停摆**——总管仅启动时 mkdir logs，被跨窗口清理删除后 `>>` 重定向失败、nohup 子进程静默不起（税法空转 3.5h），改为每轮巡检+start 函数内 mkdir；log_done awk/grep 加 LC_ALL=C 防 GBK 乱码（详见 I-017）。⑤**看门时序**——完成判定必须整段先于启动判定，否则传齐秒退后被每轮重拉且 `>` 覆盖日志、永不写 done 空转（目标机看门 09-18 已修，结论补记）。另：任务终态后 `launchctl unload` 本机总管防登录空跑、两台 pmset 恢复默认；目标机临时适配若上游已含等价功能，`git stash` 后 `pull --ff-only` 取权威版、不在目标机维护分叉。AI 编译，未标 verified。
- **Update（workflow-feishu-sync）**：飞书同步范式由旧"四棵树/课程根→组→点"切换为**新空间 8 课模型**——新空间「CPA备考知识库」`7686897234545249236`、根「课程库」`K4IcwWg6HidyY6k6Z8hcdmGFnth`，层级＝课程库→全称课程容器（容器本身=课程首页）→章/全局篇→知识点；标题/space/root 全读配置卡。链路配置驱动：`build_tree.py`（幂等建容器+回写 courseNodeToken/courseObjToken+内容器建树）→`resync_wiki_content.py`（根 README 写入容器首页 `__COURSE_HOMEPAGE__.done`、frontmatter 剥离）→只读双验收 `verify_wiki_tree.py`/`verify_wiki_content.py`（动态计数、--refill）。固化易踩：换空间重建先归档旧 map（否则按标题幂等复用老 token）；标题以本地目录名/frontmatter 为准（会计第 17 章目录截断 `17_收入` 已改全称、token 不变）；限流真因＝豆包转发代理按单进程累计请求（换新进程即恢复、外层约 3 轮换新 shell、单进程 20 篇 0 失败），旧"简单逐个脚本最可靠"结论证伪；同一空间唯一写进程、服务端异步任务 OS kill 不停。退役 sync_wiki_new.sh/auto_sync_all.*/verify_sync_completeness 入 .trash。会计已闭环（169 子页+首页、双验收 0 差异），其余 7 课待建。权威 SOP＝wiki-sync-sop.md。AI 编译，未标 verified。

## 2026-09-18

- **Update（workflow-netdisk-hevc-sync）**：上云完成判定口径修正为**只判日志最后一轮**（总管 `log_done`、目标机看门；跨轮 `>>` 累积日志里早期轮次的瞬时失败行不得永久卡住 done，经济法 189 讲已齐却被历史失败行卡住反复重拉即此）；终态核验 `verify_netdisk_final.py` 默认排除点开头隐藏/缓存（修 `os.walk` 未原地剪枝致 `.ep3cache/keycache.json` 误报缺失），新增 `-x/--exclude` 供原始资源阶段显式排除尚在生成的 `知识详解`（定稿两层全量核验时不带 -x，不硬编码抹掉知识详解）。经济法 314 hevc 上云课程根 `-x 知识详解` 核验 rc=0（205 目录/1348 文件）。finalize-sop 步骤1、code/scripts/README、CHANGELOG 同步。AI 编译，未标 verified。

## 2026-09-17

- **Update（workflow-netdisk-hevc-sync / workflow-video-hevc-compression）**：网盘门控由"整科全 hevc 且压缩进程结束才传"放宽为**按科滚动**（某科全 hevc 且没在压该科即传、可与他科压缩并行、整机一次一科；本机以该科 videos 下无 `.compress_tmp` 判"没在压"，目标机按 `--course` 进程判）；上传限速经 `networkQuality -s` 实测（两台共享上行 34.6Mbps、满载响应 Low：延迟 1.5s/40RPM）由 1000k 定值 **1100k**（两台各 1100k、同时传最坏合计占上行 ~52%，留约一半给豆包）；总管/看门在跑检测改为只匹配带 `python3`/`bash` 前缀的真进程，根除裸 `pgrep -f 脚本名` 误匹配 grep/外层 shell 的漏拉。对应 ADR-022 文末"演进注记（2026-09-17）"，finalize-sop 步骤 1、video-processing、code/scripts/README 同步；经济法已在税法压缩中按科先行上传。AI 编译，未标 verified。

## 2026-09-16

- **Add**：新增链路 concept `workflow-video-hevc-compression`（六科名师课 h264→hevc 的双机科目零重叠并行：本机压审计/战略/经济法/税法、目标机压会计/财管，rsync 同构相对路径迁移不走 git，`--jobs` 按忙闲调档/`--reverse`，本机 launchd LaunchAgent 常驻总管抗会话清理、目标机 nohup caffeinate 看门衔接，ffprobe 幂等 skip + `.compress_tmp` 原子替换 + flock 单实例，压完 rsync 回传闭环）与 `workflow-netdisk-hevc-sync`（整科全 hevc 且压缩结束才上传的门控、清视频 done 保 notes + rtype=3 覆盖早期 h264、双机各并发 1 限速 1000k、verify_netdisk_final 按集合+字节大小核验为准不信 done、网盘靠 hevc 小/h264 大的大小差识别旧版），在 index 链路类登记；对应新增 ADR-022，操作细则落到 video-processing.md 与 netdisk-setup.md 新增小节。来源：双机压缩/上云实战（审计 257、战略 129 已 hevc 上云终态核验 rc=0 零差异；目标机 961 个视频与本机源 diff 一致、ffprobe 全可解析；夜间 nohup 随会话被 KILL 停摆 6h 后改 launchd；log_done 误判"失败讲"标题恒假卡死上传、战略漏在总管循环外靠一次性补传等定位）。AI 编译，未标 verified。

## 2026-09-14

- **Update（architecture-storage-layout）**：按新增 ADR-021 去桌面软链——`data/高顿` 由指向 `~/Desktop/高顿` 的符号链接改为项目内**实体目录**（同 APFS 卷 rename 秒换、迁移前后 12401 条目/10448 文件/935G 零丢失、整体 gitignore）；删除"`find data/高顿` 必须带 `-L`、换机用 setup_data_symlink 重建软链"旧结论，改为"实体目录直接遍历无需 `-L`、换机把数据放回 `data/高顿/`（网盘镜像拉回）"；本地大文件目录载体由 `~/Desktop/高顿` 改记 `data/高顿`。配套：`course_config.COURSE_DESKTOP_ROOT` 保留变量名、值=COURSE_LOCAL_ROOT（下游 4 脚本零改动）；`setup_data_symlink.sh` 退役；百度网盘远端结构与四地分工不变。另清退 15 个写死桌面绝对路径、0 现役引用的一次性知识详解清洗脚本（fix_p*/fix_error*/count/assess，移废纸篓），现役 `batch_ocr.sh`/`watch_stage_done.sh` 改 data 相对路径保留。AI 编译，未标 verified。

## 2026-09-13

- **Update（standard-naming-change-control）**：把"不改写历史"从一句模糊例外细化为**适用边界**——只保护编年/记录体（ADR/CHANGELOG/memory-log/git/任务报告原文，只增不改），不保护现行规范/手册/活态台账（过期/被取代/写死旧数字直接删改，可溯靠 git+CHANGELOG），判据看段落性质而非整份文件；同步删 AGENTS 3.8/3.12 与 DOC_MAP 里写死的税法旧数（108/92/14 组）与一次性推广经验，并更正"只 commit 不 push"旧约定（用户已授权按里程碑自主 push）。来源：用户指出该原则被用过头、现行文档过期货应删。AI 编译，未标 verified。
- **Update**：`architecture-knowledge-paradigm` 易踩坑补「名师课本地 manifest 读取口径 + 风控期 AI 直接成稿作业法」——`ep3-{subject}-2026/manifest/course-manifest.json` 取 `['knowledge']`、`groups[].code` 是整数非零填充串、`pointIndex[str(pid)]` 取点、章目录＝`NN_`+组名原样；一科选一套体系最完整精讲 OCR 作主干（审计＝王依然上下册、陈岩稿补充、独立课件仅 03/17/18 章），大 OCR 用 awk 定行边界后分段读尽再写、一章一闭环。操作细则同步落到知识生成 SOP 新增 §2.12 与 §2.1 末尾（manifest 读取口径）。来源：审计第 7-12 章连续 24 点成稿实战（code 当字符串比较取不到组、行边界需当场复核等坑）。AI 编译，未标 verified。

## 2026-09-12

- **Update**：`architecture-storage-layout` 按 ADR-020 更新物理课程层——本地/网盘去掉"课程库"中间层（课程直挂 `高顿/CPA/<课程>`、跨课《通用做题思路解析》在 CPA 层），网盘根内插"会计知识库"领域分库层（`/apps/CPA课程归档/会计知识库/高顿/CPA/<课程>`，股票/珠宝知识库平级）；新增硬约束：百度沙箱根名 `/apps/CPA课程归档` 与应用授权绑定、**禁止 API 改名**（实测改名即写操作 31064、改回即恢复），飞书"课程库"是浏览节点不在此列。同步把层级术语"课程库层"改"CPA 层"（泛称"课程库=成品区"保留）。AI 编译，未标 verified。

## 2026-09-10

- **Update**：`workflow-ep3-vod-decryption` 长跑模型从「单路 supervised 串行」补成「单路兜底 vs 多科目节流调度」双模型：多科目总入口 `throttled_ep3_download.sh`（1 生产者 round_robin 串行预取 key + 最多 MAX_PARALLEL 个纯消费者只读缓存下载、nice/taskpolicy 降后台类、自带 caffeinate 防睡眠）；记录三条勿回退硬经验——key 缓存按 profile×阶段独立（共用会被先跑阶段饿死）、只给活跃消费者阶段滚动预取（废弃缓存总数阈值硬跳过）、长跑生产者不 set -e 且计数字段纯数字兜底。来源：会计重点强化被共享缓存饿死漏片的实战定位与修复（离线正则三验证 + 运行时端到端验证）。AI 编译，未标 verified。
- **Update**：`workflow-browser-cdp`「采集不抢用户输入焦点」两层结论再细化：①建标签层 newPage 默认激活→`newBackgroundPage()`（CDP background:true，hidden 下静音+Worker 取 key 不受影响）；②连接授权层——每次新连接弹官方强制授权 sheet、macOS 自动把 Chrome 置前（无法消除），改为**点中即还**：连接前 captureFrontmost 记名传给 `press_allow.applescript`，AXPress 点中「允许」同一刻 System Events `set frontmost` 还回（pressed=false/当前非 Chrome 不动作），实测 Chrome 仅在前台约 0.7s、整个 ~28s 采集期焦点不离开原 App；finally restoreFrontmost 兜底。必须 set frontmost（`tell app activate` 在 node 宿主被静默丢弃、对 Doubao 反切走）；代点间隔维持 800ms 防拥塞。对应 ISSUES I-008、CDP 手册 §4.5。AI 编译，未标 verified。
- **Update（architecture-knowledge-paradigm）**：新增 ADR-019，补「成品编号与著录口径」——知识章目录号取官方 `groups[].code`、跳过预科组不重编号（会计 `01_总论` 已改回 `03_总论`）；讲目录 `NN=idx-1`（开班 00）、忠实平台标题字符、只约束未来不回溯税法；frontmatter type/tags/sources.lecture 著录讲目录的标准档回灌入库脚本与模板。结论由本次会计 vs 税法成品对齐实查得到，AI 初编、未标 verified human。

## 2026-09-09

- **Update**：`workflow-ep3-vod-decryption` 补两条 T3 会计全面精讲批量实战结论：①清晰度只能由 m3u8 URL 鲁棒判——两路 CDN 命名 `glive2-video-resource/.../tc/FHD_xxx`（含 FHD 字样）vs `glive-video-cdn/outputm3u8/<uuid>_1080_xxx`（分辨率后缀、无 FHD），播放器默认就起播 1080 时整段只 init 一次 hls，`includes('FHD')` 会把真 1080 误标 SD、key 已截获却报「未取到 FHD key」稳定漏采 16 讲；capture 改 `classifyQuality`（先 FHD|1080、再 HD|720、余 SD），且分类函数必须在 `page.evaluate` 浏览器作用域内。②ep3 视频长跑必须套 `run_ep3_videos_supervised.sh`（`caffeinate -i` 防 Mac 睡眠/CDP 瞬断导致的零报错静默停摆——裸 nohup 曾停约 8h 仅落 36/261；断点续跑 + 连续 3 轮无增长判 ❌），不裸 nohup、同一时刻只跑一条（共用日常 Chrome）。来源 commit 32e8ac7 + 05 讲修复前后端到端对照。AI 编译，未标 verified。
- **Add**：新增链路 concept `workflow-ep3-vod-decryption`（名师课 ep3/saasType13 平台路由、讲次枚举/getVideoInfo、CDP Worker 截 AES key=32hex 前16字符 ASCII、FHD-1080P、平台 VTT 字幕免 FunASR）与治理 concept `standard-dynamic-observation`（动态交互取证优先于静态逆向/纯接口复现的跨项目方法），并在 index 链路类/治理类登记；正课视频 concept 补"本链路只用于 glive、ep3 走 VTT"分流。来源：ADR-018 + ep3 key 攻坚第五轮双重端到端验证（25/26 考季）。AI 编译，未标 verified（machine-confirmed，待人核）。
- **Update**：工作区收口 concept 补「视频下载/压缩过程件 `.vfetch` 落 `_workspace/<profile>/dl-tmp/`、课程库根不留讲目录」——`fetch_lecture_video.js` 新增 `--work-base`（缺省课程根、向后兼容），动态/串行两条流水线统一指向 dl-tmp，成品仍归 `原始资源/videos/`；根因是 .vfetch 曾建在课程库根、仅靠转写末尾自清，主控中断即永久残留（commit 2b1f892）。

## 2026-09-08

- **Update**：做题链路 concept 补 answerMode=5 表格题双字段提交契约（`userAnswer` + `excelAnswer=JSON.stringify(luckysheet.getAllSheets())`，做题 UI 在独立子应用 sub-tiku.gaodun.com）与错误码分层（token 553649434 / 作答太快 10462203 / 账号级风控 10462222）；结论由 sub-tiku 前端源码逆向 + 三类卷（满分 t1/平台最优 t1/对照）redo 全拦的对照实测得到，细节指针到 exam-workflow §4.3.2/§4.4。
- **Add**：新增治理 concept `standard-debugging-first-principles`（故障排查先验顺序：九成失败是 AI/脚本自身问题、凭证最后怀疑、token 失效须有只读回包硬证据），并在 index 治理类登记；同步更新做题链路与浏览器 CDP 两篇 concept 的 token 自愈描述。
- 来源：会计课 token 失效排查实战（误打端点、刷错课程页、findJwt 排序 bug 均为自身问题）+ 用户约 10 天运行经验。

## 2026-09-07

- **Creation**：建立工程记忆 bundle（ADR-017），初版编译 10 篇 concept——架构 4、链路 4、治理 1、对照索引 1；结论全部从既有 ADR-002/003/005/007/010/012/013/014/015/016、standards 与接口档案编译，未新增事实。
- 初版由 AI 编译，`generated.by=doubao/okf-wiki`、**未标 verified（machine-confirmed，待人核）**；人核通过后再逐篇加 `verified: human:`。
- 校验器 `code/scripts/check/okf_validate.py` 自 okf-wiki 技能 vendor 进项目（零第三方依赖），工程自包含、不依赖全局技能。
