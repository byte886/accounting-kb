# 项目任务状态（TASK_STATUS）

> **文档类型**：Active（全局活态台账）
> **更新频率**：阶段/课程状态切换、里程碑完成、全局断点或下一步变化时
> **维护者**：AI 自动维护
> **读者**：AI 代理（每次启动/接手任务时必读）+ 用户（看全局进度）

## 职责边界（先读）

- **这份文档装什么**：项目**跨课全局**的路线与里程碑、当前课程的**指针级**状态、全局断点与下一步。回答的是"**整个项目到哪了、接下来做什么**"。
- **谁在用**：AI 每次启动 / 接手 / 被问"现在做什么、任务状态"时先读本文件（AGENTS §2、§9-Q1）；用户用它看全局。
- **什么时候写**：阶段或课程状态切换、里程碑完成、全局断点 / 下一步发生变化时立即更新。
- **绝不装什么（边界）**：
  - 单门课的逐讲 / 逐卷 / 批次明细计数、工单勾选、侦查数据、日志、临时过程——一律在该课 `data/_workspace/<course>/`（`tickets/`、`manifest/`、`logs/` 等，**不入库**），本文件只放指向它的一句话指针，**不抄易变计数**（数字以 workspace 台账实时为准）。
  - 问题 / BUG 的生命周期登记在 [ISSUES.md](ISSUES.md)；本文件只在状态行引用其 ID，不重复描述。
  - 稳定、跨课复用的决策与方法在 `docs/project-management/decisions/`（ADR）与 `docs/project-management/memory/`（OKF），不在此展开。
- 易变值（进度数字、当天日期、SHA、剩余量）不固化进本文件，需要时实时读 workspace 台账。

> 最后更新：**2026-09-20（ep3-econlaw-2026 经济法新空间建树+全量同步+双验收闭环，新空间 8 课模型至此 8 个课程容器全部闭环）**。**当前阶段＝在新飞书知识空间「CPA备考知识库」（space_id `7686897234545249236`，根节点「课程库」`K4IcwWg6HidyY6k6Z8hcdmGFnth`）按「课程库 → 全称课程容器 → 章/全局篇 → 知识点」的 8 课模型重建，本库 8 门课已全部建完并双验收闭环；权威同步 SOP＝`docs/development/guides/wiki-sync-sop.md`。**
> - **✅ 会计（罗翔正课 profile=`cpa-accounting-2026`）新空间重建 + 全量只读回读验收通过（2026-09-19）**：课程容器「【26考季】VIPCPA系列-会计（罗翔老师）」node `Z8AjwYUwvi11kJkO07tc4r36nib` / obj `SvfadwfgWokuB4xws99cwE03nev`（容器首页已写）；其下 30 章 + 2 全局篇（顶层 32）、章下 137 知识点 ＝ **169 子页面**。独立回读 **170/170 正文非空（0 空/0 薄/0 失败）、飞书标题 0 错配、frontmatter 已剥离**。map＝`data/_workspace/cpa-accounting-2026/logs/wiki_node_map.tsv`；回读报告＝同目录 `logs/content_readback.tsv`。**通用化验收脚本＝`scripts/knowledge/verify_wiki_tree.py`（结构，动态计数）+ `verify_wiki_content.py`（正文回读，`--refill` 只补非 OK 篇）**，会计 `verify_wiki_tree` 已跑通 0 差异。固化中还修掉一个真实缺陷：本地第 17 章目录被截断成 `17_收入`（frontmatter/飞书均为全称 `17_收入、费用和利润`），已改本地目录名 + 唯一跨章相对链接（09_负债/01_流动负债.md）+ map 标题键（token 不变），树核验复跑 0 差异。老空间 `7678261729456852192` 的会计树已删（仅余 CPA 级《通用做题思路解析》node `K12CwLuJsig6WHkVNOwcNiSrnog`），作废短名节点 `WPY3wlDy…` 勿用。
> - **✅ SOP/脚本固化完成（2026-09-19，L1，用户已授权并提交）**：① `build_tree.py` 重写为配置驱动——按配置卡 `primaryCourse.name` 在 rootParentNodeToken 下幂等建全称课程容器→回写 `wiki.courseNodeToken/courseObjToken`→在内容器建树（兼容旧 3 参用法）；② `resync_wiki_content.py` profile 加载容错、增 `--profile/--course-obj/--no-homepage`，**课程首页（知识详解根 README）写入容器**（done 名 `__COURSE_HOMEPAGE__.done`）；③ 会计配置卡补齐 key/subject/primaryCourse.saasCourseId 过校验，8 张卡全部挂新空间 wiki 块（其余 7 卡 courseNodeToken 留空、建树自动回写）；④ 两个批处理 sh 去硬编码 REPO、TOTAL 自动=map+首页、显式 `--profile`；⑤ 新增通用双验收 `verify_wiki_tree.py`/`verify_wiki_content.py`；⑥ 重写 `wiki-sync-sop.md` 为新空间 8 课模型，更新 scripts/README §十、WORKFLOW §飞书同步策略、wiki-link-verification-sop、feishu-api 引用；⑦ 退役 `sync_wiki_new.sh`、`auto_sync_all.py/.sh`、`verify_sync_completeness.py` 入 `.trash/*.20260919`。**实证批参数：每个新 lark-cli 进程最多写 20 篇（RESYNC_MAX_NEW=20）实测 0 失败；撞 `invalid_response/parse temporary token` 换新进程、外层满 3 轮换新 shell。**
> - **⏭️ 当前主线（2026-09-19 用户拍板；新窗口＝知识线长期负责人）**：会计（罗翔正课）已多智能体生成 + 双验收闭环；**其余 7 门本地知识详解逐门「重生成既有课程」**。固定流水线（结构对账→整目录备份→同名原地多智能体重做→整门深度审核+自检→**人工闸口停下等确认**→通过后飞书同步双验收→再开下一门）的权威步骤见 [生成SOP §六](../../docs/development/guides/knowledge-detail-build-sop.md)，从 [知识详解SOP总览](../../docs/development/knowledge/knowledge-sop-overview.md) 唯一入口进入；质量只认成文标准、**不依赖样板课**，标准有缺口先补标准再继续。
>   - **路线与状态（任务变量，随推进更新）**：① `cpa-tax-2026`（蔡俊峻正课税法）✅闭环（2026-09-19：92点+14README+2全局重生成，6维4.2/5，新空间课程容器 node `RuJlwr3ojifRHJkknupcImfwnOf`/obj `PzN1dm2vCoF9rdxdAIlcyUA0n1c`，109篇双验收0差异/109回读OK；题型口径经核实=26单选/16多选/4计算20+5英文/2综合30，讲义正确未改）→ ② `ep3-strategy-2026`（名师课战略）✅新空间首次建树+全量同步+双验收闭环（2026-09-19：课程容器「【VIPCPA专享】名师专业课-战略」node `T6I7waMheiMoxokxHQHcNLzMnsf`/obj `CtqadEAhEoPWIOxihk9cENj8n6d`；8章66点+8章README+2全局+课程首页=76子页/顶层10；树验收0差异、回读77/77 OK（0 EMPTY/0 FETCH_FAIL/0标题错配、frontmatter已剥离）；老空间遗留 map/resync_done 已改名 .oldspace 归档未删；ep3课型=讲义OCR+VTT字幕、全未做题按风控占位，03/04章题答待风控解除回补 status=draft）。**③起按用户空间顺序（账号台账 account_courses.json 的 courseListByProject[8] 序号，2026-09-19 用户拍板）：ep3-tax(杨志国税法) → ep3-accounting(姚远会计) → ep3-audit(王依然审计) → ep3-finance(李晶财管) → ep3-econlaw(沈甜甜经济法)**。各门备份/逐章/闸口明细落该课 `data/_workspace/<profile>/`，本文件不抄计数。
> - **✅ ep3-econlaw-2026（名师课·经济法，沈甜甜/齐萌双老师）新空间建树+全量同步+双验收闭环（2026-09-20，新空间第7门/最后一门）**：课程容器「【VIPCPA专享】名师专业课-经济法」node `LgjTw9dT5izT7lkAss3cnq5Fn5f`/obj `PilRdQxOAojCNhxSNbWc3tZunPf`；12章66点+2全局=80子页（顶层14：章12+全局2）+课程首页=81篇。树验收 0 差异（无重复/无错挂）、正文回读 81/81 OK（0 EMPTY/0 THIN/0 FETCH_FAIL、frontmatter 已剥离）。旧 9-17 旧讲次编号 map（74行，parent 节点在新空间已 not_found）与旧 resync_done 已改名 `.oldspace` 归档未删。同步中途撞转发代理深限流（第33篇起连续 rc=5 invalid_response），按 2026-09-20 新重试逻辑（进程内分类重试1次→exit2 交外层换新进程→外层指数退避 75→150→300→600→900s）自动恢复，串行未并发。唯一结构瑕疵：第11章第5点飞书节点标题被建成带顿号「05_滥用行政权力排除、限制竞争规制制度」（本地/map/frontmatter 均无顿号，建树笔误），已用 wiki update_title 改回无顿号、token/正文不变，复验 0 差异。**至此新空间 8 课模型全部闭环：会计罗翔正课 + 蔡俊峻税法正课 + 名师课战略/税法/会计/审计/财管/经济法 共 8 个课程容器。**
>   - **环境红线（流水线之外）**：做题账号风控冻结、不新做题；未获用户逐门确认前不碰飞书；视频/网盘 launchd 线（`com.gaodun.ep3-local-supervisor`、仓库根 `logs/`、netdisk/supervisor 标志）独立运行，知识线勿扰。git push 已修复（wj 机 github.com 固定 byte886 密钥 + `IdentitiesOnly yes`）。
> - **异步任务防并发教训（2026-09-18 夜，详见官方帮助《使用工作任务模式》）**：豆包"工作任务"是服务端异步、可跨重启/跨端恢复、目标驱动持续到完成；OS 层 `kill -9`/删脚本/整机重启/他端退出均不能停止（执行在本机、状态在服务端），停止入口＝打开该运行中任务、点输入框右下"发送键变停止"，或让其把目标做完自然结束。开长任务前先确认无同目标 run。视频/网盘 launchd `com.gaodun.ep3-local-supervisor` 与 `<root>/logs/` 是独立线，知识线勿扰。
>
> （以下为 2026-09-18 11:00 状态）
> 最后更新：2026-09-18 11:00（知识线·一卡两用根治）。**当前阶段＝名师课视频 H.265 压缩 + 按科滚动上百度网盘（双机并行，视频/网盘线）；知识线完成「一卡两用」根治（会计/税法正课与名师课配置卡/映射/脚本彻底分离）。**
> - **知识线·一卡两用根治（2026-09-18，ISSUES I-016）**：会计/税法历史上"一卡两用"（cpa-* 卡同时伺候正课和名师课，手改 localRoot 切换，映射文件后建覆盖先建）已根治为「一卡一课+脚本显式化+映射分离」。①配置卡各归各位：cpa-accounting 全程罗翔正课169、cpa-tax 全程蔡俊峻正课108（修复 localRoot=名师/remoteRoot=正课的撕裂）、ep3-accounting 全程名师176、ep3-tax 全程名师107，四张卡 name/localRoot/remoteRoot 三者自洽；②脚本显式化：resync_wiki_content.py 增加 --course-dir/--map 参数（默认回退 paths.localRoot，向后兼容），resync_all_courses.sh 改为只含名师六科（正课用 cpa-* 卡单独运行）；③映射归位：四棵树 wiki_node_map.tsv 按 profile 独立存放（169/176/108/107），蔡俊峻正课108映射从 .bak（137行混合版）按本地标题过滤提取恢复；④验证通过：四棵树"本地篇数=映射行数"全部一致，--dry-run 验证目录和映射解析正确。沉淀：wiki-sync-sop.md 新增「一卡一课与映射分离（强制）」专项章节。**视频线窗口注意：cpa 卡的临时指向已收口为正课专用，名师课同步请用 ep3-* 卡，不要再手改 cpa 卡 localRoot。**
> - **知识线（AI 主线）**：名师专业课 **596 知识点 + 108 章 README + 12 篇课程全局篇全部完成！🎉**（**会计 144 全齐（第3-32章整章齐）+2全局篇**、战略 67+2全局篇、**审计 106 全齐+2全局篇**、**财管 122 全齐+2全局篇**、**税法 91 全14章齐（第10章已从3合并文件拆分为7知识点）+2全局篇**、**经济法 66 全12章齐+2全局篇**）。**✅ 知识详解全面质量优化完成（2026-09-15）**：P0规范统一（frontmatter/标题/编号）、P1可读性提升（description压缩至100-150字、易错点格式统一为❌→✅对比表）、P2长期优化（新建六科统一写作风格指南、过长段落拆分）。遗留精细处理完成：易错点"正确处理"列通用话术**六科全部清零**（税法15篇逐篇补充）、description通用话术**716篇全部清零**、过长段落从989个减至107个（89%，剩余为教材例题/会计分录等合理长段落）。六科全量OKF校验**E=0**。**✅ 飞书知识库同步全部完成（2026-09-16）**：名师课六科**716篇知识详解全部同步到飞书知识库**（会计176、审计132、财管144、税法107、经济法80、战略77），三方数量一致性检查通过，飞书端六科各抽检1个知识点全部通过（内容非空、frontmatter已剥离、四节结构完整）。**同步最佳实践已更新到 wiki-sync-sop.md**：推荐使用简单逐个处理脚本（每次独立lark-cli进程、每次间隔10秒），复杂批量脚本容易遇到"parse temporary token from Authorization fail"错误（非真限流，是脚本实现问题）。逐章进度、实时计数与三线总账唯一真相＝`data/_workspace/_account/ep3/three_tracks_status.md`，本文件不抄易变计数。
> - **压缩线**：`scripts/compress_ep3_videos.py` nohup 后台（CRF30/libx265、断点续跑、顺序 战略→审计→经济法→财管→税法→会计），done 计数看 `data/_workspace/_account/ep3/compress_state.jsonl`，进程断了按 SOP nohup 续跑（hevc 自动跳过）。
> - **网盘线（2026-09-18，按科滚动，详见 concept `workflow-netdisk-hevc-sync`）**：6 科 notes 已「ALL6 NOTES RESYNC DONE」收口；videos 改**按科滚动**——某科全 hevc 且没在压该科即传（首次 reset 清该科视频 done、`rtype=3` 覆盖早期 h264，两台各限速 1100k/讲并发 1），不等其他科压完。已 hevc 上云并终态核验 rc=0：审计、战略（09-16）、**经济法（09-18，课程根 205 目录/1348 文件全等）**；进行中＝目标机会计（607 全 hevc、上传中）、目标机压财管、本机压税法。完成判定只看日志**最后一轮**、终态用 `verify_netdisk_final.py`（原始资源阶段 `-x 知识详解`）。实时计数看 `three_tracks_status` / 各 profile `netdisk_done`，本台账不抄。
> - **做题/试卷线**：账号风控 10462221 冻结，不试探、不申诉、等用户通知；按用户决策"风控拿不到的来源可忽略"不阻塞知识线，解封后只读回补题答并 draft→stable。
> - **存储架构（2026-09-14，ADR-021，去软链）**：`data/高顿` 已由指向 `~/Desktop/高顿` 的软链改为项目内**实体目录**（整体 gitignore、同卷秒换零丢失）；桌面不再有"高顿"文件夹，所有脚本统一相对路径 `data/高顿/...`、`find` 无需 `-L`，换机/克隆把数据放回 `data/高顿/`（网盘镜像拉回）即可；`setup_data_symlink.sh` 退役、`COURSE_DESKTOP_ROOT` 保留变量名但值=COURSE_LOCAL_ROOT；网盘远端与四地分工不变。
> - 更早历史（下载攻坚与节流模型、会计飞书三遍地建树、名师增量 zip 补遗、OKF×I2T 治理等）见 git log / CHANGELOG / three_tracks 进度日志，本活态台账不滚动保留。

## 任务总览（全局里程碑）

```
1. 基础设施与流水线        ✅（仓库/飞书/网盘/CDP/视频下载-压缩-转写/做题纯接口，通用能力）
2. 税法课（蔡俊峻）         ✅ finalize（39讲原料 + 116套作业 + 108篇知识详解，本地/网盘/飞书三地同步）
3. 项目管理与文档体系       ✅（ADR-001~019、OKF 工程记忆、SOP/规范/模板体系、I2T 任务工程方法论）
4. 会计课（罗翔）           ✅ 知识库建设完成 / ⏸️ 做题暂停（正课四来源已齐：视频转写46/46、讲义OCR44、题答176卷、笔记4473条；知识详解本地 **169 篇全齐 = 137 知识点 + 30 章 README + 2 全局 Reference**，全库 OKF E=0；**飞书第一遍建树 169/169 + 第三遍 resync 全量重刷完成**，前向关联链接已解析为 `<cite>` 可点击内链（修复 resolver 漏传 WIKI_MAP 致内链退化 bug），6 篇金融工具悬空链接降级为纯文本，飞书端抽检通过；百度网盘知识详解已全传；做题线因风控关闭不追分，等用户通知解除）
5. 名师课6科目              ✅ 视频 1483/1483 全齐 / ✅ 知识详解本地716篇全齐 / ✅ 飞书知识库同步716/716全部完成（2026-09-16） / 🔄 H.265压缩→网盘传压缩版进行中。知识详解实时进度/计数看 `data/_workspace/_account/ep3/three_tracks_status.md`、本里程碑不抄计数；视频核对权威结论 `data/_workspace/_account/ep3/video_gap_verified.md`，复核脚本 `scripts/cdp/ep3_diff_online_local.js`
```

状态标记：✅ 完成 | 🔄 进行中 | ⏳ 待启动 | ⏸️ 暂停 | ⚠️ 有阻塞 | ❌ 取消

---

## 当前阶段：名师课6科目三线并行（H.265 压缩 / 网盘 / 知识详解；ep3平台，profile=`ep3-*-2026`）

> 单课工单拆解、实时计数、侦查与日志以 `data/_workspace/_account/ep3/`（`manifest/`、`logs/`、`keycache/`）与各课 `data/_workspace/<profile>/` 为唯一权威；本节只放跨会话必须先知道的**指针与硬约束**，不抄计数。

> **✅ 视频下载线已收尾（2026-09-13，六科归并 1483 讲全齐、0 缺、全片解码 0 错误）**：方法定稿＝浏览器桥只读 syllabus 树、用叶子**内嵌 `resource.discriminator/video_id`** 判真视频（不逐个调 front/resource，避免业务码 10161000；node 直连 apigateway 被 Tengine 指纹拦 405，业务接口必须走浏览器页面内 fetch，视频分片走 CDN 可 node 直连）。当年中断的 5 讲残缺已用 `data/_workspace/_account/ep3/patch_missing_videos.js` 补成 1080P、四件套齐全。**下载不再进行；2026-09-13 用户拍板后续走 H.265 压缩（CRF30/libx265、能看清课件文字）、明确不走抽音频**；下载节流模型的完整设计与"勿回退"要点见工程记忆 concept `workflow-ep3-vod-decryption` 与 `scripts/cdp/throttled_ep3_download.sh` 头注释。

| 科目 | profile | 状态 | 指针级说明（细节看 workspace） |
|------|---------|------|-------------------------------|
| **会计** | ep3-accounting-2026 | ✅视频齐 | 四阶段（全面精讲/基础必修/重点强化/考前冲刺）全部完整、607 视频 0 缺（I-014 已澄清早前「缺30」是单老师时代裸 meta 误报并清理），双老师（姚远/陈蓓蓓）；讲义OCR 16/16。**作业 26 考季 48 张基础卷未做、155 已完成（140满分+15平台最优）+ 冲刺3**（09-13 只读刷新）。实时缺量以 `throttled_ep3_download.sh` 本地完整性统计为准、只认带老师前缀 meta，不看缓存条数 |
| **税法** | ep3-tax-2026 | ✅视频齐 / ⏸做题等通知 | 全面精讲完整（313 视频）；基础必修/重点强化/考前冲刺已补齐（新增 95 视频），双老师（杨志国/高蒙）；讲义OCR 26/26 + 高蒙思维导图70张Vision合并稿。**作业 26 考季仅 13 张基础卷未做 + 冲刺3**（109 张已完成，2026-09-13 只读刷新） |
| **战略** | ep3-strategy-2026 | ✅视频齐 / ⏸做题等通知 | 全面精讲完整（94 视频）；重点强化/考前冲刺已补齐（新增 35 视频），吴奕主讲（陈岩26考季未挂视频）；讲义OCR 36/36（+陈岩强化真题解析8）。**作业 26 考季 78 张基础卷全未做 + 冲刺3，从未做过题**（2026-09-13 只读刷新） |
| **经济法** | ep3-econlaw-2026 | ✅视频齐 / ⏸做题等通知 | 全面精讲完整（266 视频）；重点强化/考前冲刺已补齐（新增 48 视频，本科无基础必修），双老师（沈甜甜/齐萌）；讲义OCR 46/46（+齐萌强化10）。**作业 26 考季 83 张基础卷全未做 + 冲刺3，从未做过题**（2026-09-13 只读刷新，已抽查 record=null 证实） |
| **审计** | ep3-audit-2026 | ✅视频齐 / ⏸️做题等通知 | **有视频有讲义**（2026-09-10 晚纠正"纯试卷"误判，见 ISSUES I-010）：四阶段、26考季**单老师王依然**（15251；陈岩15463仅25考季不取），共 314 视频/153 试卷资源/48 讲义；视频/讲义接口不受做题风控连带，已纳入 throttled 下载。**做题线**触发账号风控 10462221，剩余队列见该课 `papers_audit.json`（**2026-09-13 只读刷新：仅 15 张基础卷未做、135 张已完成 + 冲刺3**），**AI 不申请/不申诉/不反复试探，等用户通知**；解除后用 batch_ep3_papers 做 audit、fetch_ep3_paper_readonly 只读回补（见 ISSUES I-009） |
| **财管** | ep3-finance-2026 | ✅视频齐 / ⏸️做题等通知 | **有视频有讲义**（同 I-010）：四阶段、26考季**单老师李晶**（11134；周越26考季未挂视频，但 09-13 经 zip 补遗补入周越基础7+精讲11份讲义 PDF），共 389 视频/174 试卷资源；讲义 PDF 35（17 原有+周越18）。**作业 26 考季仅 27 张基础卷未做、144 已完成 + 冲刺3**（09-13 只读刷新）。做题线同审计、等用户通知；已做卷题面/答案/解析待解除后只读回补 |

> 名师课六科讲义/OCR 已全齐（含 zip 补遗，缺文稿 PDF=0）；做题统一走纯接口 `batch_ep3_papers.js`、分时段拟人节奏，现因账号风控全线挂起、等用户通知（见 I-009），不试探、不重做。

### 下载调度（已收尾，仅留指针，勿回退）

- 节流模型＝1 生产者 `round_robin_prefetch.sh` 串行预取 key + 最多 `MAX_PARALLEL` 个纯消费者只读缓存下载；key 缓存按「profile×阶段」独立、只给活跃消费者滚动预取；`nice -n 20 taskpolicy -c utility` 降后台、`caffeinate` 防睡眠；完整性唯一判据＝每个带老师前缀 `*_meta.json` 有对应非空 `*_video.mp4`（不数单老师时代裸 meta，I-014）；新课两道闸（outline ep-study fallback、stage_missing 补位，I-010/I-011）；**重启禁用 `pkill -f`，按 PPID=1 根 BFS 收集后代 kill -9、确认残留 0 再启动防双开**。
- 完整权威：工程记忆 concept `docs/project-management/memory/concepts/workflow-ep3-vod-decryption.md`、`scripts/cdp/throttled_ep3_download.sh` 头注释、ISSUES I-010/I-011/I-014。下载阶段已收尾，通常无需再动。

### 网盘同步（当前策略＝方案甲）

- 6 科 notes（讲义/转写/增量补遗文稿）已全量收口；videos 改为**某课全部 H.265 压缩完成后只传压缩版**，旧已传的 465 讲未压缩视频保留不折腾、剩余不再传未压缩视频
- 上传走百度 API、不碰高顿；已存在文件 MD5 秒传、可中断重跑；脚本与参数见 `docs/development/api/netdisk-setup.md`

### 硬约束（恢复时第一优先，禁止违反）

- **凭证失效（553649434 等）最后怀疑**：须有只读请求返回登录超时的硬证据；排查先怀疑 AI 自身（端点/参数/ID/文件选取逻辑/最近改动，约九成在此）
- 下载/取流阶段的平台专属约束（CDP hook 截 key、双老师按 teacher_id 归并、ep3 VTT 字幕优先于转写）已随下载收尾固化进工程记忆 concept `workflow-ep3-vod-decryption`，不再下载时无需读取

---

## 已完成课程（履历，明细见 CHANGELOG / ADR / 该课 workspace）

- **税法（26考季·蔡俊峻）✅ finalize**：39 讲视频下载-压缩-转写、18 子目录讲义 OCR、116 套基础作业满分/平台最优 + 6 套冲刺模考；按官方 14 模块组/92 知识点聚合成 108 篇知识详解（14 章 README + 92 知识点 + 2 全局篇），本地/百度网盘/飞书知识库三地同步、元数据（点赞数/学员名）清零。过程件归档于 `data/_workspace/cpa-tax-2026/`（含任务报告）。

---

## 暂停课程（等条件满足后恢复）

- **会计（26考季·罗翔）⏸ 仅做题线暂停**：四来源采集、169 篇知识详解、笔记 Fan-In（1035 条）、飞书三遍地同步均已完成（见顶部任务总览第 4 条）；仅做题线因账号风控 10462222 关闭、用户拍板不重刷追分，等通知后只读回补剩余解析，不阻塞其它线。

---

## 跨任务协调记录（2026-09-15，避免多窗口冲突）

> **背景**：用户在另一窗口（CPA知识库对话）同时安排了知识库结构设计任务，为避免冲突，已协调如下。

### 另一窗口任务状态
- **知识库结构设计线**：✅ 已停止，全程只读探查（find/grep/head），**零写入**，未修改任何知识详解文件或飞书节点
- **双老师结构设计**：⏸️ **挂起不碰**——双老师三科（经济法沈甜甜+齐萌、税法杨志国+高蒙、会计姚远+陈蓓蓓）怎么合并、标题怎么标，等本窗口飞书同步告一段落、用户发令后，再按"先出方案、用户确认后才改"的方式执行
- **视频/网盘线（2026-09-18）**：🔄 双机并行（本机 launchd 总管 + 目标机 nohup 看门，有线 192.168.2.8），**只读写原始资源/videos、不碰知识详解/**。全局 hevc 截至 09-18 上午约 83%（本机审计/战略/经济法已压完并上云、税法压中；目标机会计全 hevc 上传中、财管压中；实时一律 ffprobe 现算为准）。两台各自按科滚动、限速上云；会计/财管 hevc 完成并上云后 rsync 回传本机留档、终态核验后删目标机文件腾空间。完成判定/终态核验两个 bug 已修（CHANGELOG 09-18）。

### 本窗口任务（飞书知识库同步）
- **当前阶段**：✅ 六科知识详解同步到飞书知识库**全部完成**（2026-09-16）
- **会计**：✅ 176/176篇全部同步完成（A方案已执行：删除旧节点→重新建树→全量同步）
- **审计**：✅ 132/132篇全部同步完成
- **财管**：✅ 144/144篇全部同步完成
- **税法**：✅ 107/107篇全部同步完成（已清理wiki_node_map中30个旧正课节点）
- **经济法**：✅ 80/80篇全部同步完成
- **战略**：✅ 77/77篇全部同步完成
- **合计**：✅ 716/716篇全部同步完成，飞书端质量抽检六科各1个知识点全部通过
- **同步最佳实践**：已更新到 wiki-sync-sop.md，推荐使用简单逐个处理脚本（每次独立lark-cli进程、每次间隔10秒）

### 协调原则
1. **本窗口优先执行飞书同步**，另一窗口不碰知识详解和飞书节点
2. **双老师结构设计挂起**，等飞书同步完成后由用户统一发令
3. **视频/网盘线独立运行**，不与知识库同步冲突
4. **任何窗口要修改知识详解或飞书节点前，必须先确认另一窗口无相关操作**

---

## 全局下一步（按优先级）

1. **知识详解本地生成（AI 主线，✅全部完成）**：按知识生成 SOP §2.12 逐章闭环（manifest 钉点→主干精讲 OCR 分段读→成稿+手写章 README→`okf_validate` E=0→find 现算计数→回写 three_tracks→单章 commit/push）。**六科知识点 596/596 + 108 章 README + 12 篇课程全局篇全部完成！** 税法第 10 章「房产税法、契税法和土地增值税法」已从 3 个合并文件拆分为 7 个独立知识点文件（与 manifest point_id 对应），整章 OKF E=0。六科课程全局篇（《考试指导速查手册》《课程做题思路解析》各6科共12篇）全部生成完成。总账与实时计数唯一真相＝`data/_workspace/_account/ep3/three_tracks_status.md`，本文件不抄计数。
2. **视频 H.265 压缩（后台 nohup）**：`scripts/compress_ep3_videos.py` 断点续跑（CRF30/libx265、顺序 战略→审计→经济法→财管→税法→会计）；某课全部 hevc 后才传该课压缩版 videos。存活/done 看 `compress_state.jsonl` 与日志，断了按 video-processing SOP 用 `nohup ... & disown` 续跑（hevc 自动跳过）。
3. **百度网盘**：6 科 notes 已收口；只在某课压缩全完后传该课压缩版 videos、知识详解成品生成后同步；旧 465 讲未压缩视频保留不折腾（方案甲）。
4. **做题/试卷（挂起等用户通知）**：名师 282 套（基础卷 264＋冲刺 18）与正课会计做题线均因账号风控冻结，**不试探、不申诉、不重做**；等用户通知解除后只做没做过的，再只读回补题面/答案/解析、把 draft 升 stable。
5. **项目治理**：课程级过程件落 `data/_workspace/<course>/` 不入库；稳定结论才提炼进 ADR/OKF/SOP；按里程碑及时 commit、已授权自主 push（提交信息写清、含 TASK_STATUS 更新）。

## 恢复检查清单（异常恢复 / 新会话续接时逐项确认）

- [ ] 按 AGENTS §2 判断冷启动/续接路径；读本文件 + `memory/index.md` + `three_tracks_status.md` 确认三线当前位置（数字一律以 workspace 现算为准，不看本文件或对话里的旧值）
- [ ] 查压缩后台：`ps aux | grep compress_ep3_videos` 看存活、`grep -c '"status": "done"' data/_workspace/_account/ep3/compress_state.jsonl` 看 done；进程没了就 `nohup+disown` 续跑（hevc 自动跳过；长跑禁用会被回收的 run_in_background、禁 `pkill -f`）
- [ ] 知识线：从该课 manifest 现读章/点/讲次（`groups[].code` 为整数、`pointIndex[str(pid)]` 取点），按 SOP §2.12 续写下一未完成章，整章 `okf_validate` E=0
- [ ] 确认做题/试卷线仍风控挂起（不试探）；网盘线是否出现"某课已全 hevc、待传压缩版 videos"
- [ ] 先 `git status` / `git log -1` 确认本地与 origin 同步、工作区干净再动手
