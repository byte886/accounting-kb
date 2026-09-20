# 工作流文档

> **文档类型**：Task（操作指南 — 主工作流）
> **更新频率**：每次流程变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理（执行任务前必读）和人类（了解流程时）

本文档是课程知识库项目的**主工作流索引**，只保留总体流程、全局规则和每个阶段的摘要+参考文档链接。详细操作步骤、参数、常见问题查阅对应专项文档与阶段 SOP。

> **范式基线（2026-09-04 起）**：课程数据按 **原始资源 / 知识详解 / 运行时工作区 三类解耦**组织（过程件统一在 `data/_workspace/`，ADR-016），知识加工单元是**官方知识点（跨讲聚合）**而非"讲"，主流程为**四阶段**。决策依据见 [ADR-012](project-management/decisions/ADR-012-三层解耦与按知识点聚合.md)（工作区位置经 [ADR-016](project-management/decisions/ADR-016-统一运行时工作区与按profile分区.md) 修订），目录落点见 [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md)。

---

## 文档边界

| 维度 | 本文档（WORKFLOW.md） | 其他文档 |
|------|---------------------|----------|
| **定位** | 主工作流索引，操作流程指南 | - |
| **读者** | AI代理（执行任务前必读）和人类 | - |
| **包含** | 总体流程、阶段校验门、全局规则、各阶段摘要+参考链接 | - |
| **不包含** | 项目目标介绍、存储分工、课程列表 | → [README.md](../README.md) |
| **不包含** | AI执行规则、命令、Things to Avoid | → [AGENTS.md](../AGENTS.md) |
| **不包含** | 需求定义、功能清单、验收标准 | → [REQUIREMENTS.md](REQUIREMENTS.md) |
| **不包含** | 文档索引、所有文档清单 | → [DOCUMENTATION_MAP.md](DOCUMENTATION_MAP.md) |
| **不包含** | 数据分层与目录结构的完整定义、命名细则 | → DIRECTORY_STRUCTURE.md、[NAMING_CONVENTION.md](project-management/standards/NAMING_CONVENTION.md) |
| **不包含** | 各阶段详细操作步骤、参数、常见问题 | → 对应阶段 SOP 与 development/ 下专项文档 |

---

## 总体流程

### 三层数据模型（先理解数据去哪）

| 层 | 位置 | 内容 | 去向 |
|----|------|------|------|
| **原始资源** | `data/高顿/CPA/<课程>/原始资源/{videos,notes}/` | 视频+转写、讲义+OCR（按资源类型分桶，不按讲混放） | 永久保留，传网盘 |
| **知识详解** | `data/高顿/CPA/<课程>/知识详解/14组/92知识点.md` | 成品：一个知识点一篇、篇内 4 节；加 2 篇课程全局篇 | 可迭代，传网盘并同步飞书 |
| **运行时工作区** | `data/_workspace/_account/`（账号级）、`data/_workspace/<profile>/`（课程级 manifest/papers/notes-raw/sniff/tmp/pipeline/logs） | 运行时过程件，统一工作区不绑定具体课程、按 profile 分区（ADR-016） | Git忽略+网盘排除，分层清退 |

> 逻辑上分三类（原料/成品/过程件）即"三层解耦"；**物理上课程目录只看到「原始资源 + 知识详解」两层，过程件统一在独立的 `data/_workspace/`**。

### 四阶段流水线

```
①资源采集(视频下载/压缩/转写 + 讲义下载/OCR → 原始资源；过程件→data/_workspace/<profile>/tmp)
   → ②做题/交卷与试卷采集(帮用户100%完成作业 + 采 papers + 生成 course-manifest)
   → ③知识详解生成(按官方知识点跨讲聚合，14组→92篇×4节 + 2篇课程全局篇)
   → ④收尾(阶段校验门 → 备份百度网盘 → 统一同步飞书知识库 → 分层清理工作区)
```

**特殊分支：冲刺模考**（做题/交卷的一种特殊模式，所有基础作业完成后才触发）：
```
冲刺模考视频解析(走阶段①) → 冲刺模考做题/交卷与采集(走阶段②) → 题/答/解析并入知识详解(走阶段③) → 更新考试指导速查手册 → 最终统一同步飞书
```

### 核心原则

1. **采集与生成解耦**：资源按类型采集、知识按知识点聚合，不再要求"一讲端到端走完再下一讲"；层间靠 `data/_workspace/<profile>/manifest/course-manifest.json`（讲↔资源↔知识点）维系。
2. **知识详解一次性聚合生成**：集齐来源（讲义OCR + 视频转写 + 题/标准答案/官方解析 + 用户笔记）后，按知识点一次性生成，不做两阶段。
3. **做题/交卷首要目的是帮用户把作业 100% 正确完成**，题/答/解析同时作为知识来源反哺；它包含知识点测试/课后练习、分章真题、强化专题等模式，**冲刺模考必须在所有基础作业完成后才进行**。
4. **分类骨架只用官方知识点**（14 模块组、92 知识点，脚本现算校验），不 AI 自造分类；知识与应试在一篇内分节而非分文档。
5. **先本地后飞书、先校验后同步**；任何永久产物落地前不清理 工作区。

---

## 阶段校验门（强制，必须执行）

### 为什么需要

无论走完整流程还是中途补齐，**每个阶段完成后必须通过该阶段的校验门**才能进入下一阶段，避免遗漏关键步骤（历史教训：2026-09-03 曾因缺少强制校验，中途补齐时漏掉"上传百度网盘"）。校验对象从"每讲"改为"每阶段的应产出集合"。

### 检查规则

1. **阶段交接必过门**：进入下一阶段前逐项核对本阶段校验门，标注 已完成✅ / 未完成❌ / 不适用N/A。
2. **中途补齐先盘点**：补齐任务先对照四阶段门，确认缺在哪一阶段，只补该阶段缺口，补完重过该门。
3. **未完成项必须说明原因**；校验结果在任务总结中体现。
4. **以脚本/接口可复算结果为准**，不凭印象判完成（如知识点数、题量对账、文件大小校验）。

### 四阶段校验门

| 阶段 | 应产出 | 通过判据（要点） |
|------|--------|------------------|
| **①资源采集** | `原始资源/videos/NN_讲题/{video.mp4,transcript.md,transcript.json}`；`原始资源/notes/NN_模块/{讲义.pdf,OCR.md}` | 视频数与 syllabus 一致、压缩 H.265 CRF30 且时长误差<1s、转写完整；讲义数与 syllabus 的 lecture_note 清单一致（17 份，混合讲以实际清单为准，空讲不复制）；`tmp/download`、`tmp/transcribe` 已即时清 |
| **②做题/交卷 + 采集** | 作业 100% 完成；`data/_workspace/<profile>/papers/` 全量试卷 JSON；`data/_workspace/<profile>/manifest/` 台账与 course-manifest | exam-report 全对；papers 份数与 syllabus 枚举一致；客观题取顶层、主观题下钻 `subQuestionList`；manifest 讲↔资源↔知识点映射可校验、知识点合计 92 |
| **③知识详解生成** | `知识详解/01..14_组/` 共 92 篇知识点 md（每篇 4 节）+ 课程两全局篇 | 92 篇齐全无遗漏/无未归类；题量与 papers 对账一致；来源标注完整、无 AI 错题；旧骨架已复用核对；用户留言已归入"学员补充" |
| **④收尾** | 网盘备份、飞书知识库、干净的工作区 | 原始资源+知识详解已传网盘且大小校验；飞书 14 组→知识点结构校验通过；工作区 按清理时序清空（详见阶段④） |

### 批量任务规则

- 阶段内可按资源/知识点批量并行（并发度见"多任务并发调度"）；阶段间必须前一阶段过门后再整体推进。
- 全部完成后做一次总校验：四张校验门逐列复核，并输出整体结果。

---

## 全局规则（所有阶段必须遵守）

### 大任务检查与报告约定（必须遵守）

**核心原则：子任务主动上报 + 定期检查防异常，两者结合。**

1. **子任务主动上报（主要方式）**：子任务完成后立即主动上报结果（成功/失败、输出文件、关键指标）。
2. **定期检查（兜底方式）**：预计运行超过 5 分钟的任务，最大 5 分钟检查一次，目的是**发现异常**（卡住、进程退出、不主动上报），不是汇报进度。
3. **一切正常不刷"还在运行"**，只在子任务完成后上报结果。
4. **发现异常立即处理并上报**。检查内容：进程是否在运行、输出大小是否增长、是否有错误日志。异常处理：进程退出→删不完整文件→重启；大小不增长但进程在→判断是否卡住→必要时重启。

### 窗口管理规则（必须遵守）

开启新 iTerm 窗口或 Chrome TAB 前，先检查并关闭未使用的窗口/TAB。iTerm 任务完成立即关窗；Chrome 开始新任务前关无关 TAB、视频下载完成立即关播放 TAB。详见 [interaction-workflow.md](development/guides/interaction-workflow.md) 第1节。

### 统一使用已有工具（必须遵守）

项目已有成熟脚本/工具，**禁止重复造轮子**。

| 任务 | 统一使用 |
|------|----------|
| 连接日常 Chrome（主通道，ADR-010） | `code/scripts/cdp/connect_browser.js`（puppeteer-core 经 CDP 连已登录日常 Chrome，免重登） |
| 视频下载解密 | `code/scripts/video/download_decrypt.js`（glive/ep3 共用） |
| 名师课 ep3 视频+字幕采集（type=13） | `code/scripts/cdp/ep3_download_videos.js`（FHD-1080P + 平台 VTT 字幕，免 FunASR；ADR-018） |
| 视频压缩（仅正课 glive） | `code/scripts/video/compress.sh`（ep3 FHD 用 ffmpeg -c copy，不重压） |
| 讲义 OCR | `code/scripts/ocr/batch_ocr.sh` |
| 音频转写 | `code/scripts/transcribe/transcribe_pipeline.py` |
| 网盘上传 | `code/scripts/netdisk/baidu_upload.py` |
| 做题/交卷（接口主链路） | `code/scripts/cdp/api_do_paper.js`（syllabus→redo取答案→submit交卷→exam-report回查） |
| 做题/交卷（纯接口主链路） | `cdp/api_do_paper.js`（单卷）、`cdp/batch_redo_papers.js`（批量，内置 token 失效自愈重试）、`cdp/do_sprint_paper.js`（冲刺） |
| 鉴权 token 自愈 | `cdp/refresh_auth_token.js`（从已登录日常 Chrome 自动抓新 authentication；findJwt 按文件 mtime 取最新） |

完整索引见 [code/scripts/README.md](../code/scripts/README.md)。

### 重要决策前查看历史 ADR（必须遵守）

做目录结构、工具选型、流程变更、存储分工、知识组织等重要决策前，先读 [ADR 索引](project-management/decisions/README.md)；与历史冲突时评估演进或废弃，新的重要决策执行后补 ADR。当前组织范式以 **ADR-012** 为准。

### 文档健康度检查（必须遵守）

每个课程/大任务完成、结构重大调整、批量增删文档后执行：完整性（DOCUMENTATION_MAP 有登记、有类型标注）、关联性（链接有效、无孤岛）、结构（与 DIRECTORY_STRUCTURE 一致、无空目录）、质量（无重叠、大文档适时分解）、维护（.gitignore 合理、核心文档最新）。规范见 [DOCUMENTATION_OPTIMIZATION.md](project-management/standards/DOCUMENTATION_OPTIMIZATION.md)；pre-commit hook 会自动检查关联性与类型标注。

### 任务状态实时更新（必须遵守）

任务状态变更立即更新 `project-management/TASK_STATUS.md`，不得延迟；它是唯一任务状态来源。规范见 [AGENTS.md 3.6节](../AGENTS.md)。

### 飞书同步策略（必须遵守）

**核心原则：本地全量生成并校验后统一同步，冲刺模考后做最终一次同步；不做分讲同步、也不在飞书直接编辑。**

| 同步时机 | 同步内容 |
|---------|---------|
| 课程知识详解全部生成、四阶段校验门通过后 | 按新空间 8 课模型整体同步：课程库→全称课程容器（=课程首页）→ 章/全局篇 → 知识点 |
| 冲刺模考完成后（最终一次） | 冲刺题/答/解析并入的知识点更新 + 更新后的考试指导速查手册 |

- 飞书结构与本地 `知识详解/` **同构**：课程容器下章＝父节点、知识点篇＝子页面、根 README＝容器首页。
- 现役链路（配置驱动、一门一验收）：`code/scripts/knowledge/build_tree.py` 建树 → `run_resync_batches.sh`/`resync_wiki_content.py` 分批同步正文（含首页）→ `verify_wiki_tree.py` + `verify_wiki_content.py` 只读双验收；完整步骤、8 课坐标、限流处置见 **[wiki-sync-sop.md](development/guides/wiki-sync-sop.md)**。
- 先本地生成、校验通过再同步；同步后做结构检查：节点层级、重复节点、空节点、父节点链接。
- 必须用 API 同步，禁止直接在飞书编辑（紧急修复除外）；同一空间同一时刻只允许一个写进程；连续失败 3 次以上暂停并报告。
- 飞书写操作前先读 lark-wiki / lark-doc 相关 Skill。

### 数据分层与统一工作区管理（必须遵守）

**核心原则：永久层与成品层保留并备份；一切运行再生成的过程件集中在唯一工作区 `data/_workspace/`（账号级 `_account` + 课程级 `<profile>` 正交分区），达到门禁才分层清退。**

| 类别 | 位置 | 处置 |
|------|------|------|
| 原始资源（视频/转写、讲义/OCR） | `原始资源/` | 永久保留、传网盘 |
| 知识详解成品（92 篇 + 全局篇） | `知识详解/` | 保留、传网盘、同步飞书 |
| 账号鉴权 JWT、账号课程清单 | `data/_workspace/_account/{auth,user-space}/` | 跨课共享、长期留、滚动留最新 |
| 试卷原始 JSON、台账、course-manifest | `data/_workspace/<profile>/{papers,manifest}/` | 可重采/rebuild，封板归位后清 |
| 抓包侦查报文 | `data/_workspace/<profile>/sniff/` | 验证完即删 |
| 用户留言原件 | `data/_workspace/<profile>/notes-raw/` | **100% 吸收进"学员补充"、封板归位后才删（门槛最高）** |
| 下载/转写临时（分片、merged、切片） | `data/_workspace/<profile>/tmp/{download,transcribe}/` | **单任务成功即清**（避免与成品双占空间） |
| 阶段断点、运行日志 | `data/_workspace/<profile>/{pipeline,logs}/` | 断点可 rebuild、日志随收尾清 |

**清理时序**：`tmp/*` 单任务成功即清 → `sniff/` 验证完即删 → `notes-raw/` 确认全吸收、与 `papers/` 一并**归位到课程「原始资源」**后清工作区副本 → 阶段④双门禁（成品校验通过 且 原始资源传完网盘）且飞书同步完成后，`manifest/pipeline/logs` 可清（可 rebuild）；`_account` 不随单课清退。**不属运行时过程件不进工作区**：`.secrets/*.enc` 留仓库根（加密、跨课复用）；`node_modules`、`transcription/venv` 是工具链环境，留标准位置并 gitignore，靠 package.json/requirements.txt 重建。

### 多任务并发调度（必须遵守）

**核心原则：依赖关系定顺序，实测数据定并发，事件驱动触发衔接，总调度实时决策。**

1. **大任务先拆 DAG**：标注依赖（Linear/Fan-Out/Fan-In）、任务名、预估时长、资源类型、最优并发度、状态。
2. **评估时长并按需测试**：经验可估则估，测试成本低但影响大的必须小样本测。
3. **实时调度、完成即通知**：阶段内用 `xargs -P N` 动态调度（禁自建 flock 队列，多进程子 shell 有竞态）；阶段间事件监听衔接，禁止人工长间隔巡检。
4. **并发度基于实测**，不凭核数估算；串行吞吐最高则串行最优。

**本项目已验证并发特性**：
| 任务 | 瓶颈 | 最优并发 |
|------|------|---------|
| FunASR 转写 | CPU+内存带宽 | 1（串行） |
| x265 压缩 | CPU（单实例吃多核） | 1（全局单实例） |
| macOS Vision OCR | CPU（1核/实例） | 可与压缩并行，1–2 个 |
| 视频下载/解密 | 网络 IO | 可并发（20 分片） |
| 抓 HLS key | Chrome 单标签 | 必须串行 |
| AI API 调用 | 网络+限流 | 按知识点/章并发 |

可并行组合：压缩期间并行 OCR；下载与不依赖视频的任务并行；多资源下载、多讲 OCR 可适度并行。**换环境/换模型必须重新实测。** 方法论见 [task-planning-and-parallel-scheduling.md](development/methodology/task-planning-and-parallel-scheduling.md)、[parallel-processing-guide.md](development/performance/parallel-processing-guide.md)。

---

## 阶段① 资源采集

### 摘要

按 syllabus 官方清单采集视频与讲义：视频捕获 HLS（m3u8+key）→ 下载分片解密合并 → H.265 CRF30 压缩并验证 → FunASR 转写；讲义取 CDN 直链 curl 下载 → 图片型 PDF 走 macOS Vision OCR。成品落 `原始资源/{videos,notes}/`，下载/转写临时落 `data/_workspace/<profile>/tmp/` 且单任务成功即清。

### 关键要点

- **以 syllabus 接口清单为唯一权威**：`discriminator` 区分 lecture_note(讲义)/live_new(视频)/paper(试卷)；是否混合讲、空讲一律以实际清单为准，不靠编号推断（ADR-011）。
- 视频：切 1080P 后抓 m3u8/AES key/IV，多线程下分片、AES-128-CBC 解密合并；压缩参数 libx265/CRF30/preset fast/AAC 96k/hvc1/faststart；压缩后验证时长误差<1s、moov 存在、开头无黑屏。
- 讲义：**禁止点 Chrome 下载按钮**（弹对话框），用 CDN 直链 curl；PDF 多为图片型，必须 OCR，表格/公式/图表用 AI 视觉补。
- 转写：FunASR SenseVoiceSmall（本地、0 成本），虚拟环境 `transcription/venv/`，**串行最优、禁止并发转写**。
- 命名与落点遵循 NAMING_CONVENTION / DIRECTORY_STRUCTURE：`videos/NN_讲题/`、`notes/NN_模块/`。
- **先按 saasCourseType 分流（ADR-018）**：正课 glive(type=16) 走上面"H.265 压缩 + FunASR 转写"全流程；**名师课 ep3/epiphany(type=13) 走 `code/scripts/cdp/ep3_download_videos.js` 独立链路**——正式 FHD-1080P、ffmpeg `-c copy` 不重压、**平台自带 VTT 字幕直接下载（subtitle.vtt 原始稿 + transcript.md），不做 FunASR 转写**；取 key 仍走 CDP 真实播放（gp.play + 点1080P）。详见 [video-processing.md](development/tools/video-processing.md) 的"名师课 ep3"小节。

### 参考文档

- 配套阶段 SOP：[资源采集 SOP](development/guides/resource-collection-sop.md)
- [video-processing.md](development/tools/video-processing.md)（含名师课 ep3 小节）、[transcription.md](development/tools/transcription.md)、[document-download.md](development/tools/document-download.md)、[ocr.md](development/tools/ocr.md)
- 脚本：正课 `download_decrypt.js`、`compress.sh`、`transcribe_pipeline.py`、`batch_ocr.sh`；名师课 ep3 `cdp/ep3_download_videos.js`（复用 `capture_video_key.js`/`download_decrypt.js`）
- 决策：[ADR-018 名师课 ep3 取流解密与平台字幕](project-management/decisions/ADR-018-名师课ep3取流解密平台路由与平台字幕替代转写.md)

---

## 阶段② 做题/交卷与试卷采集、manifest 生成

### 摘要

**双重目的**：①帮用户把作业 100% 正确完成（首要）；②采集题/标准答案/官方解析落 `data/_workspace/<profile>/papers/`，并生成/刷新 `data/_workspace/<profile>/manifest/` 台账与 course-manifest。做题链路已接口化：redo-paper 进卷即返回题面/标准答案/解析，submit 一次性交卷，exam-report 回查；UI 仅用于登录与未覆盖异常兜底。

### 关键要点

- **接口主链路**：syllabus 枚举卷与完成状态 → record → redo-paper（当场拿题+答案+解析）→ 满足最小作答墙钟时长 → submit 一次性交全卷 → exam-report 回查全对。契约见 [gaodun-exam-api.md](development/api/gaodun-exam-api.md)，入口 `code/scripts/cdp/api_do_paper.js`。
- **题型两型**：客观题（type1/2）取顶层标准答案；**主观大题（type5 容器）必须下钻 `subQuestionList`（type6 小问），答案在小问 `analysisText`**，按"大题→小问"组织；其他题型遇新先只读侦查再打通。
- **异常出口分级**：token 失效（业务码 553649434，JWT 未到 exp 也可能发生）但日常 Chrome 仍登录 → `refresh_auth_token.js` 自动刷新重试（批量脚本内置，最多 2 次）；仅当 Chrome 也未登录/需验证码 → 暂停交用户；遇未见过的卷型/题型/报错 → 不硬闯，停下发起针对性测试或迭代。
- **manifest**：汇总 syllabus + papers 生成讲↔资源↔知识点映射，承载知识点等价/归并（如 id=112376"应纳税额的计算"并入"增值税一般计税方法应纳税额的计算"）；脚本校验知识点合计 92、无未归类。
- **知识来源口径**：初始知识库 + 题/标准答案 + 官方解析 + 用户笔记 + 末期冲刺模考；**自动化作业产生的 AI 错题不作来源**；考点图谱已否决。详见 [knowledge-base-sources.md](development/knowledge/knowledge-base-sources.md)。

### 冲刺模考（特殊分支，所有基础作业完成后）

3 张 48 题综合模考，必须在全部视频/讲义/基础作业完成后才做；其视频解析走阶段①，做题采集走阶段②，题答并入阶段③，并更新考试指导速查手册，最后随统一同步上飞书。

### 参考文档

- 配套阶段 SOP：[做题交卷与试卷采集/manifest SOP](development/guides/paper-manifest-sop.md)
- [exam-workflow.md](development/guides/exam-workflow.md)、[gaodun-exam-api.md](development/api/gaodun-exam-api.md)、[browser-cdp-connect-guide.md](development/tools/browser-cdp-connect-guide.md)

---

## 阶段③ 知识详解生成

### 摘要

以 course-manifest 为索引，**按官方知识点跨讲聚合**全部来源，生成 `知识详解/`：14 组下共 92 篇知识点 md（每篇固定 4 节）+ 课程两全局篇。这是旧"按讲生成双文档"的替代范式（ADR-012）。

### 一篇知识点 md 的 4 节

1. **一、知识拆解**：客观知识（定义/分类/原则/表格），以讲义 OCR+转写为主干；
2. **二、考试指导**：考情/高频/易错/口诀/技巧，用题量定高频；
3. **三、题答解析**：聚合本知识点全部题（题面/选项/标准答案/官方解析），主观题按大题→小问；
4. **四、学员补充**：学员讨论/助记/易错补充（无则省）。

### 关键要点

- **跨讲聚合、不按视频时间线**：同一知识点在多讲/多卷出现要合并；14 组按官方教材模块序，组内用官方知识点原名，脚本对账题量。
- **归并特例**：土地增值税归组10（非增值税组02）、委托加工/应税消费品/进口消费税归组03、非居民企业归组04、非居民个人归组05。
- **两种生成路径**：首次从零＝原料搭建；存量（本次税法）＝**旧 organized-content 骨架复用 + 多源核对 + 题答校验增强**，不推倒重写也不照抄，用官方解析逐题校验、补真题细节、剔除 AI 错题。
- **课程全局篇**：`课程做题思路解析.md`（结合本课）、`考试指导速查手册.md`（只汇总通用考点/税率/对比，**不含具体指定业务的题目或场景**）；CPA 层另有跨课的 `通用做题思路解析.md`。
- 单篇自检不过不进入下一篇：题量对账、来源标注、无 AI 错题、四节完整。

### 参考文档

- **总览入口（先看这个）**：[知识详解SOP总览](development/knowledge/knowledge-sop-overview.md)（按工作流串联所有知识详解相关文档）
- 配套阶段 SOP：[知识详解生成 SOP（核心）](development/guides/knowledge-detail-build-sop.md)（已替代旧 lecture-knowledge-build-sop）
- [knowledge-base-organization.md](development/knowledge/knowledge-base-organization.md)、[knowledge-base-sources.md](development/knowledge/knowledge-base-sources.md)、[KNOWLEDGE_BASE_TEMPLATE.md](development/templates/KNOWLEDGE_BASE_TEMPLATE.md)

---

## 阶段④ 收尾：校验 → 网盘 → 飞书 → 清理

### 摘要

按固定顺序收尾：过阶段③校验门 → 备份百度网盘 → 统一同步飞书 → 确认永久产物都落地后分级清理 工作区。

### 关键要点

1. **校验先行**：92 篇成品齐全且自检通过、原始资源齐全（过阶段①③门）。
2. **备份百度网盘**（在同步飞书前）：上传原始资源（压缩视频、讲义、转写、OCR）与知识详解成品、课程全局篇；**不传原始未压缩视频、不传 工作区**；分片上传后 list 校验大小一致。应用 `CPA课程归档`(AppID 124199604)，凭证 `.secrets/baidu_credentials.enc`，国内直连不走代理，路径含 `高顿/` 层且与本地一致。
3. **统一同步飞书**：按"飞书同步策略"与 [wiki-sync-sop.md](development/guides/wiki-sync-sop.md) 走新空间 8 课模型（建树→分批正文→双验收），同步后做结构校验。
4. **分层清理工作区**：按"数据分层与统一工作区管理"的清理时序执行；`notes-raw` 必须确认全吸收、归位后才删。
5. 清理前确认：永久层已传网盘、成品已同步飞书、待删件确实不在使用。

### 参考文档

- 配套阶段 SOP：[收尾 SOP（网盘/飞书/清理）](development/guides/finalize-sop.md)
- [netdisk-setup.md](development/api/netdisk-setup.md)、[feishu-api.md](development/api/feishu-api.md)、[feishu-knowledge-base-maintenance.md](development/guides/feishu-knowledge-base-maintenance.md)

---

## 任务总结

每阶段或批量任务完成后，在对话中总结（不单独生成飞书报告）：本阶段产出物与数量、关键校验结果（题量/知识点数/文件大小对账）、遇到的问题与处理、网盘与飞书结果、工作区 清理情况、下一阶段入口。批量任务完成后做整体总结并附四阶段校验门结果。

---

## 项目管理规范

遵循测试驱动与缺陷管理：单样本测试优先；缺陷按严重度+优先级分类；小问题顺手修、大问题先讨论；缺陷走 发现→分类→记录→处理→验证→关闭→报告。详见 [project-management/README.md](project-management/README.md)。

---

## 注意事项

- m3u8 token 与 authorize token 会过期，每个视频需重新捕获。
- 课程表 TAB 可能因 ffmpeg 占内存崩溃，需重新加载。
- 不要在浏览器点"下载"按钮（触发 Chrome 下载弹窗），讲义用 CDN 直链 curl。
- 代理：GitHub/Homebrew/npm 走 ClashX（127.0.0.1:7890）；高顿课程页、百度 API/网盘直连。
- 密钥管理用全局命令 `secrets`（原 `code/scripts/secrets.sh` 已抽离为全机唯一工具，规范见 mac-system-toolkit 的 secret-encryption.md），本项目加密凭证在 `.secrets/`（留仓库根、不进工作区）。
- 业务数据在 `data/`（`高顿/` 课程库实体目录，ADR-021 去软链），不入 Git；Git 只版本化规范/模板/SOP/脚本等文本。

---

*本文档是主工作流索引，只保留总体流程、阶段门与摘要。详细步骤见各阶段 SOP 与专项文档；流程变更时必须同步本文档与对应专项文档。*
