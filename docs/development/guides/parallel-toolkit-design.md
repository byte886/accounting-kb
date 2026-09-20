# 并行化工具与课程参数化设计方案（面向会计课复用）

> **文档类型**：Task（操作指南 — 工具设计与落地方案）
> 目标：在**不引入重型调度框架、不重写税法已完成产物**的前提下，让"采集 → 加工 → 生成 → 同步"整条流水线对**任意一门 CPA 课程**（首要：会计）可一键复用，并把目前散落、互不一致的并发实现收敛成一套可复用工具层。
> 本文只给设计、契约、改造清单与验收，不重复并发方法论；方法论见 [parallel-processing-guide.md](../performance/parallel-processing-guide.md)、[task-planning-and-parallel-scheduling.md](../methodology/task-planning-and-parallel-scheduling.md)，任务依赖与时长见 [project-dag.md](../project-dag.md)。

## 一、为什么要做（现状盘点，均为实测/实读）

### 1.1 并发能力已存在，但散落在 4 套写法里

| 范式 | 用在哪 | 机制 | 特点 |
|---|---|---|---|
| `xargs -P`（shell） | `sync_raw_resources.sh`、`sync_course_netdisk.sh` | 内核级分发，按目录并发 | 无竞态、自动负载均衡，**方法论推荐** |
| `Promise.all + worker 池`（node） | `download_question_videos.js`（CONCURRENCY=10）、`collect_user_notes.js`（=5） | 自写 worker 抢任务 | 适合分片/IO，保序需另写 |
| `mapLimit`（node） | `gaodun_paper_core.js`（AI 批改=3） | 限并发、保序、失败隔离 | 适合有序 API 调用 |
| 自建队列（shell） | `transcribe_parallel.sh` | `mkdir` 原子锁取队首、失败回队 | 支持回队重试，但属方法论里点名"易出竞态"的自建队列 |

**问题**：同一类任务在不同脚本里各写一遍，限流/重试/断点/失败隔离/日志的约定都不一致；换一门课就要再抄一遍。

### 1.2 课程参数只在 shell 层统一，JS/Python 仍硬编码税法

- `code/scripts/course_config.sh` 已用 `COURSE_NAME` 派生 shell 路径，shell 脚本 `source` 它即可换课——**但只覆盖 shell**。
- JS 硬编码：`refresh_inventory.js`（COURSE_ID=42660 / SYLLABUS_ID=75181）、`fetch_lecture_video.js`（42660/75181 + 税法桌面路径）、`collect_user_notes.js`（税法 papers 路径）；`gaodun_paper_core.js` 已支持 `GAODUN_COURSE_ID` 环境变量覆盖（方向正确，但不彻底）。
- Python 硬编码：`knowledge/build_course_overview.py`（税法课程目录、14 章名表、`COURSE_INFO` 税法层级、HTML title 课程名）。
- 后果：会计课开工时，要逐个脚本改 ID/路径/章数，既慢又容易漏改污染。

### 1.3 存在一处与实测结论矛盾的默认值

- 方法论与 DAG 均实测 **FunASR 转写串行吞吐最优**（1 进程 18.5x ＞ 6 进程 14.3x，见 parallel-processing-guide §二），但 `transcribe_parallel.sh` 默认并发 6。应统一为"单视频转写串行、多视频排队"，默认并发回到 1（保留参数，换模型重测后可调）。

### 1.4 没有跨课程的端到端编排

DAG 是依赖图、方法论是原则、`watch_stage_done.sh` 是阶段触发器，但缺一个"给一门课的 profile 就按 DAG 跑完整条线、可断点续跑"的总入口。

## 二、总体设计（三层，全部用现有技术栈）

```
┌─────────────────────────────────────────────────────────┐
│ 层3 编排：run_course_pipeline.sh <profile>  (轻量 shell)  │
│   按 DAG 串阶段，watch_stage_done 事件驱动，断点续跑        │
├─────────────────────────────────────────────────────────┤
│ 层2 统一并发执行器（收敛现有 4 套，只保留 2 个标准件）      │
│   · run_io_parallel：IO/API 类（node mapLimit / xargs -P） │
│   · run_cpu_queue：CPU 类（xargs -P 队列，并发度实测决定）  │
│   统一契约：限并发·错峰·重试·断点·失败隔离·结构化日志        │
├─────────────────────────────────────────────────────────┤
│ 层1 课程配置：config/courses/<key>.json（单一事实源）      │
│   JS/Py/sh 都读它，消灭硬编码；切换课程=换 profile          │
└─────────────────────────────────────────────────────────┘
```

**不做**：不引 Airflow / Celery / 消息队列 / 数据库；不做常驻服务；不改税法已交付产物（只读复用其脚本逻辑）。

## 三、层 1：课程配置 profile（单一事实源）

### 3.1 与 ADR-012 `course-manifest.json` 的区别（避免概念混淆）

| | `course-profile.json`（本方案新增，**入库**） | `data/_workspace/<profile>/manifest/course-manifest.json`（ADR-012，**不入库**） |
|---|---|---|
| 性质 | 课程**静态生产配置**（输入） | 课程**运行产物/映射快照**（输出，可 rebuild） |
| 内容 | 课程名、各类 ID、科目、官方章组、老师、路径模板 | 讲↔资源↔知识点映射、资源清单 |
| 谁维护 | 人手 + `fetch_user_space_courses.js` 半自动 | 脚本生成 |
| 位置 | `config/courses/<key>.json`（git 跟踪） | 统一工作区 `data/_workspace/<profile>/manifest/`（gitignore、不随网盘、可 rebuild） |

### 3.2 profile schema（字段契约，已按 2026-09-07 实测落地）

```json
{
  "key": "cpa-tax-2026",
  "project": { "id": 8, "name": "CPA" },
  "subject": { "id": 38, "name": "税法", "examTime": "..." },
  "teacher": "蔡俊峻",
  "primaryCourse": {
    "name": "【26考季】VIPCPA系列-税法（蔡俊峻老师）",
    "vcourseId": 96834, "saasCourseId": 42660,
    "syllabusId": 75181, "gradationId": null,
    "platform": "glivepro", "saasCourseType": 16,
    "learnStatus": 3, "learnStatusDesc": "已完结",
    "studyUrl": "//glivepro.gaodun.com/course/42660/guide-course"
  },
  "companionCourses": [
    { "name": "名师专业课-税法", "saasCourseId": 17247,
      "platform": "epiphany", "learnStatus": 2, "collect": false }
  ],
  "structure": { "officialGroupCount": 14, "pointCount": 92,
    "groups": [ { "code": "01", "name": "税法总论" } ] },
  "paths": { "localRoot": "data/...", "remoteRoot": "/apps/..." }
}
```

- **主采集源 vs 配套课（两套学习平台，字段级实测 2026-09-07）**：

  | 维度 | glivepro 正课 | epiphany 名师专业课 |
  |---|---|---|
  | `saasCourseType` | 16 | 13 |
  | 学习入口 | `glivepro.gaodun.com/course/{id}/guide-course` | `epiphany.gaodun.com/ep3/course/{id}` |
  | 本账号课程 | 税法 42660、会计 42656（均已完结） | 六科名师课（ID 见账号课程清单） |
  | 工具链 | 现有采集脚本同构，直接走 `primaryCourse` | 前端/接口不通用，须先单独探查适配 |

  名师课列入 `companionCourses` 且当前 `collect:false`，要采需先适配 epiphany 接口。六门名师课同属 epiphany 一个平台（彼此结构一致），真正的分界是"正课 vs 名师课"两类，而非每门课都不同。
- **学习状态看 `learnStatus`（不是 wareStatus）**：实测 `0=待学习 / 2=已学习 / 3=已完结`；`wareStatus` 语义不等于"是否开课/有无内容"（会计正课 wareStatus=0 但 learnStatus=已完结、有学习记录）。
- **采集优先级（"待学习"≠永久不录，而是排最后）**：① glivepro 正课 → ② 已学习的 epiphany 名师课（税法/会计/经济法，须先适配 epiphany）→ ③ 待学习名师课（战略/审计/财管，learnStatus=0）排最后，等学完或项目收尾阶段再录。
- **epiphany 探查时机（不阻塞当前会计正课）**：先把会计正课主链路（DAG 节点 1–9）跑通；在真正决定要采名师课之前，用真实 Chrome CDP 对一门已学习名师课（优先会计 epiphany saas=17244）做一次接口探查（大纲/视频资源/进度接口），产出 epiphany 适配结论后再决定是否批量接入，现阶段不提前投入。
- ID 口径以 [gaodun-exam-api.md §1.3/§2.11](../api/gaodun-exam-api.md) 为准：`saasCourseId`＝做题/内容接口的 courseId，`vcourseId`＝购课实例（听课/进度），二者不可混用。
- profile 由 `fetch_user_space_courses.js` 台账**半自动生成草稿**（ID/课程名/科目/平台/状态直接来自接口），`structure`（官方章组、考点数）由 syllabus 脚本补全，人手确认后入库。样板见 `config/courses/`（税法已填全、会计为草稿）。

### 3.3 三语言读取约定（不引第三方依赖）

- **shell**：`course_config.sh` 增加 `COURSE_PROFILE` 变量，用系统自带 `python3 -c`/`grep` 读取 JSON 派生现有路径变量（保持向后兼容：不传 profile 时默认税法）。
- **node**：新增极小 `code/scripts/cdp/load_profile.js`（`loadProfile(key)` 读 JSON、做字段校验），替换各脚本顶部硬编码常量。
- **python**：新增 `code/scripts/knowledge/course_profile.py`（`load_profile(key)`），替换 `build_course_overview.py` 等的 `COURSE_DIR/COURSE_INFO/章名表/title`。

### 3.4 硬编码消灭清单（改造点，逐个可独立提交）

| 文件 | 原硬编码 | 改造状态 |
|---|---|---|
| `cdp/refresh_inventory.js` | 42660 / 75181 | ✅ 读 profile（`--profile`/env） |
| `cdp/fetch_lecture_video.js` | 42660/75181 + 桌面路径 | ✅ 读 profile，去 `os.homedir` |
| `cdp/collect_user_notes.js` | 税法 papers 路径 | ✅ `profile.paths`，输出按 `key` 隔离 |
| `cdp/gaodun_paper_core.js` | 默认 42660 | ✅ env 优先、缺省读 profile 主源 ID |
| `knowledge/build_course_overview.py` | 税法路径/14 章名/层级/title | ✅ structure/paths + 可选 `overview` 段（空则省略） |
| `course_config.sh` | 默认税法名 | ✅ 支持 `COURSE_PROFILE` |
| `cdp/do_sprint_paper.js`、`fetch_sprint_video.js` | 税法冲刺卷/视频 ID | **保持税法专属**（冲刺卷每课不同，改为读 profile 内 sprint 段，不做通用化抽象） |

**刻意保留的例外（不参数化，grep 命中属预期）**——判据是"一次性任务/历史快照/手动默认，换课时本就重新枚举，参数化只会堆砌半通用壳"：

| 类别 | 文件 | 为什么保留 |
|---|---|---|
| 一次性枚举清单 | `cdp/fetch_question_video_keys.js`（题目 vid/PAPERS 全税法，文件头自述"key 抓一次即可离线重跑"）；`batch_transcribe.sh`/`batch_upload.sh` 曾属此类，2026-09-08 随基础必修课程清理删除（硬编码该课 12 讲、能力已被 `transcribe_all.sh`/`upload_course.sh` 覆盖）；自开独立 Profile 的 `poc_persistent_browser.js` 同于 2026-09-08 删除（路线被 ADR-010 否决） | 能力已被通用扫描脚本覆盖；枚举数据换课必须重列、非可复用逻辑，此类清单用完即删、不参数化 |
| 手动工具默认值 | `batch_ocr.sh` 的 `DEFAULT_*`（不传参时的上次文件） | 通用工具、实际均传参；默认含具体章节文件名，非可靠课程默认 |
| 缺省回退/注释示例 | `course_config.sh` 的默认税法名、`upload_course.sh`/`sync_course_netdisk.sh`/`watch_stage_done.sh` 注释、`gaodun_paper_core.js` 注释 | 默认回退是设计本身（向后兼容）；注释仅演示调用形态，非可执行硬编码 |

## 四、层 2：统一并发执行器与选型契约

### 4.1 只保留两个标准件（按资源瓶颈二选一）

| 标准件 | 适用 | 实现 | 并发度来源 |
|---|---|---|---|
| **IO 并行** | 下载/上传/API 采集/AI 调用/知识篇生成 | node 统一走 `mapLimit`（有序、保序）；shell 目录级走 `xargs -P` | 受对方限流约束，默认值见 4.3 |
| **CPU 队列** | 转写/压缩/OCR | 统一 `code/scripts/lib/parallel.sh` 的 `parallel_map`（NUL 任务流 \| `xargs -0 -P`，替代自建 mkdir/flock 锁队列） | **必须实测**，方法见 parallel-processing-guide |

> 选型铁律沿用方法论：**IO 密集可高并发（受限流约束）；CPU 密集必须实测总吞吐，串行最优就串行。**

### 4.2 每个并发任务统一遵守的 6 条契约

1. **限并发**：并发度为显式常量/参数，不写死魔法数且注释来源（实测/对方限流）。
2. **错峰**：任务间最小间隔（如 API 250ms、飞书写 1.5s），拟人低频。
3. **重试**：网络/限流类瞬时错误指数退避、上限 3 次；业务错误（参数/权限）不重试。
4. **断点续跑**：以"完成标记文件/输出存在即跳过"实现幂等，中断后重跑不重复劳动。
5. **失败隔离**：单项失败记录到结果文件并继续，不中断整批；末尾汇总失败清单（沿用 `batch_redo_papers.js` 模式）。
6. **结构化日志**：每任务一行 `[阶段][项] OK/FAIL 耗时`，末尾输出成功/失败/跳过计数。

### 4.3 会计课各阶段推荐并发度（IO 类可沿用税法经验，CPU 类必须重测）

| 阶段 | 类型 | 税法经验值 | 会计课建议 |
|---|---|---|---|
| syllabus/讲义下载 | IO(CDN) | 串行 400ms 错峰 | 沿用 |
| 视频分片下载 | IO | 单讲 20 分片并发 | 沿用 |
| 抓 HLS key | Chrome 单标签 | **串行** | 沿用（不可并发） |
| 线 B 采题 / 用户笔记 | IO(API) | 采题串行、笔记 worker=5 | 沿用，遇限流降到 3 |
| AI 批改 / 知识篇生成 | IO(AI API) | 批改 mapLimit=3、按知识点并行 | 按知识点并行，起步 3，按配额调 |
| 视频压缩 x265 | CPU(11核) | **全局 1 实例** | 必须重测（会计视频时长不同） |
| FunASR 转写 | CPU(2核) | **串行最优** | 必须重测（换模型/机器时） |
| Vision OCR | CPU(1核) | 1–2，可与压缩并行 | 沿用，与压缩错峰 |
| 网盘/飞书同步 | IO | 网盘 xargs -P、飞书篇间隔 1.5s | 沿用 |

## 五、层 3：流水线总编排（轻量 shell）

新增 `code/scripts/run_course_pipeline.sh <profile-key> [--from 阶段] [--only 阶段]`：

- 严格按 [project-dag.md](../project-dag.md) 的依赖顺序，阶段内部用层 2 标准件并发，阶段之间用 `watch_stage_done.sh` 事件驱动（完成标记计数），不空等。
- **阶段级断点**：每阶段完成写 `data/_workspace/<profile>/pipeline/<stage>.done`，重跑自动跳过；`--from/--only` 支持从任意阶段恢复。
- **Fan-In 守护**：知识生成阶段启动前校验上游（OCR/采题/转写/章组映射）全部 `.done`，缺一则明确报缺哪项，不硬跑。
- 只做调度，不含业务逻辑（业务仍在各专用脚本），符合"精简、不堆重复实现"。

## 六、落地步骤（每步独立可验收、不破坏税法现状）

1. **配置层** ✅ 已完成（2026-09-07）：建 `config/courses/`，落 `cpa-tax-2026.json`（样板，14 组已填）与 `cpa-accounting-2026.json`（草稿，课程级 ID 已填、章组待 syllabus），附目录 README。
2. **读取器** ✅ 已完成（2026-09-07）：`code/scripts/cdp/load_profile.js`、`code/scripts/knowledge/course_profile.py`、改造 `course_config.sh`（认 `COURSE_PROFILE`/`GAODUN_COURSE_PROFILE`，向后兼容默认税法）；三者均支持命令行打印关键 ID 自检，已验证。
3. **去硬编码 ✅ 已完成（2026-09-07）**：按 3.4 清单逐脚本改，每个用**税法 profile 回归**（产物与改前一致才过）、分步提交；另把运维/知识 shell·python 统一收口到 course_config/profile，刻意保留的例外见 3.4 末表。
4. **并发收敛 ✅ 已完成（2026-09-07）**：新增 shell 标准件 `code/scripts/lib/parallel.sh`（`parallel_map`：NUL 任务流经 `xargs -0 -P` 内核调度，含并发度校验，根除自建 mkdir/flock 锁队列竞态）；`transcribe_parallel.sh`、`transcribe_qvideos.sh` 改为「主脚本生成 NUL 队列 + `--worker` 自递归」，FunASR 默认并发 **1（串行最优，可传参覆盖）**，并加 UTF-8 locale 兜底。回归：bash -n 通过、税法 TOTAL=0 零副作用退出、/tmp 假课程验证并发调度与失败隔离、C locale 不 unbound。网盘上传（sync_*_netdisk/raw_resources）本就 `xargs -P`（IO 类）保持不动；Node 侧 IO 并发（笔记 worker=5、分片 20、mapLimit=3）是单进程异步、无多进程锁竞态、默认值符合 4.3，按精简原则存量不重写。
5. **编排器 ✅ 已完成（2026-09-07）**：`code/scripts/run_course_pipeline.sh <profile> [--dry-run/--from n/--only n/--list]`。按 project-dag 13 节点线性检查点推进，阶段级 marker 落在 `data/_workspace/$PROFILE/pipeline/<n>.done`，阶段9 前 Fan-In 校验 5/6/7 marker + 8 的 `structure.groups`；auto 阶段登记真实脚本命令，manual（0/2/8/9）给人工/AI 指引，todo（10/11）标注未实现，不伪造自动命令（兼容 macOS bash 3.2，case 函数而非关联数组）。已用税法 `--dry-run` 走查核对 DAG 一致，并验证 --only/--from 范围、坏 profile 拒绝(exit2)、会计切换、`--only 7` 正式跑的 marker 写入与二次跳过。
6. **会计试跑 ✅ 首跑完成（2026-09-07）**：课程发现确认账号 8 门课，会计正课（glivepro saasCourseId=42656 / vcourse=96760）learnStatus=**已完结**（旧记 wareStatus=0 不为准，统一以 learnStatus 为口径），**取数源定为 26 考季正课**，不用名师专业课（epiphany 17244）。`refresh_inventory --profile cpa-accounting-2026` 纯只读跑通：paper 共 177（基础 174 / 冲刺 3 排除），满分 4、未做 170。为此补齐**过程件按 profile 隔离**：`load_profile` 增 `scopedName/scopedPath/argvProfileKey`，`papers_inventory/papers_audit/paper_index/batch_result` 均按 profile 分文件（默认税法保持历史原名、md5 校验零变化），`collect_paper_sources`、`batch_redo_papers` 同步改读隔离文件并支持 `--profile`。会计编排器 `--dry-run` 全流程路径正确、Fan-In 精准报出缺 5/6/7 与 groups 为空。**groups 暂留空属预期**：按 ADR-012 官方组↔知识点须从 papers 的 `knowledgePointList` 现算，而会计 174 卷中 170 卷未做、无交卷 record 即无 paper/analysis，须等节点10做题、节点6采题后才能现算填充（现阶段不臆造）。

## 七、验收清单

- [x] 切换课程只改 `--profile`/一个环境变量，**全仓库 grep 不到税法课程 ID/课程名硬编码**（冲刺卷等明确专属的除外，已在 §3.4 末表列明并说明保留理由）。
- [x] 税法 profile 回归：资源采集/知识生成/总览构建产物与改造前字节级或结构化一致（步骤3/4/6 分别零差异回归；步骤6会计试跑前后税法 inventory md5 不变）。
- [x] 并发任务全部满足 4.2 六条契约；`transcribe_parallel` 默认值与方法论结论一致（默认并发 1 串行最优，parallel_map 单测与假课程失败隔离通过）。
- [x] `run_course_pipeline.sh cpa-tax-2026 --dry-run` 打印的阶段/依赖与 project-dag 一致；阶段 kill 后重跑靠 `data/_workspace/<profile>/pipeline/<n>.done` 从断点继续（--only 7 实测 marker 写入与二次跳过）。
- [x] 会计 profile 能正确解析出 saasCourseId=42656、subjectId=37（已实测）；课程发现已确认会计正课 learnStatus=已完结、取数源为正课（旧"未开课"前提作废，坏 profile 会 exit2 并列出可用 profile）。

## 八、相关文档

- [project-dag.md](../project-dag.md)（任务依赖/时长/并发度，本方案的调度依据）
- [parallel-processing-guide.md](../performance/parallel-processing-guide.md)（CPU 并发实测方法论）
- [task-planning-and-parallel-scheduling.md](../methodology/task-planning-and-parallel-scheduling.md)（DAG 拆解与调度原则）
- [gaodun-exam-api.md §1.3/§2.11](../api/gaodun-exam-api.md)（课程 ID 口径、用户空间课程清单接口）
- ADR-012（知识点结构定稿：14 官方组 92 知识点、一篇四节）、ADR-005（data 只走网盘不入库）
