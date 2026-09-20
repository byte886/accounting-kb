# 目录结构详细说明

> **文档类型**：Reference（参考资料）
> **更新频率**：目录结构变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理 + 人类

本文档说明四类存储的目录结构与分工：**GitHub 仓库（工程）、本地课程数据（data）、百度网盘（备份）、飞书知识库（成品知识系统）**。范式基线 [ADR-012](project-management/decisions/ADR-012-三层解耦与按知识点聚合.md)。

> README.md 只留摘要与链接，详细内容见本文档。
> **命名唯一事实源**：[NAMING_CONVENTION.md](project-management/standards/NAMING_CONVENTION.md)（第九章管 Git 工程命名，第一~八章管课程数据三层命名）。

---

## 〇、四地存储分工总表（先看这张）

| 内容 | Git 仓库 | 本地 data | 百度网盘 | 飞书知识库 |
|------|:---:|:---:|:---:|:---:|
| 规范/模板/SOP/脚本/ADR | ✅ 唯一源 | — | — | — |
| 原始资源（视频/转写/讲义/OCR/题答JSON/用户笔记） | ❌ 忽略 | ✅ | ✅ 备份 | ❌ |
| 知识详解成品（14 组→106 篇 + 2 全局篇，共 108 篇） | ❌ 不入 Git | ✅ | ✅ 备份 | ✅ 唯一对外知识系统 |
| `data/_workspace/` 运行时过程件（账号级 `_account` + 课程级 `<profile>`，分层清退，见 ADR-016） | ❌ 忽略 | ✅（运行时） | ❌ 不传 | ❌ |
| 加密凭证 `.secrets/*.enc`、工具链 venv/node_modules | 见 .gitignore | ✅ | ❌ | ❌ |

**一句话**：Git 只放"怎么做"的工程资产；课程"原料 + 成品"在本地 data，原料与成品备份网盘，**成品知识系统最终落飞书**；所有运行时过程件只在本地唯一工作区 `data/_workspace/`（不绑定具体课程、按 profile 子目录区分），分层清退。

---

## 一、项目仓库目录结构（GitHub，只放工程）

```
gaodun-course-knowledge-base/
├── docs/                          # 工程文档（静态：方法论/规范/流程/模板/API）
│   ├── WORKFLOW.md                # 主工作流（四阶段总纲）
│   ├── REQUIREMENTS.md
│   ├── DIRECTORY_STRUCTURE.md     # 本文档
│   ├── DOCUMENTATION_MAP.md
│   ├── development/
│   │   ├── api/                   # API 文档（feishu / gaodun-exam / netdisk / encryption）
│   │   ├── guides/                # 阶段 SOP 与操作指南（resource-collection / paper-manifest /
│   │   │                          #   knowledge-detail-build / finalize / exam-workflow 等）
│   │   ├── knowledge/             # 知识库方法论（organization 组织规范 / sources 来源清单）
│   │   ├── templates/             # 模板（KNOWLEDGE_BASE_TEMPLATE / REPORT_TEMPLATE / VERIFICATION_TEMPLATE等）
│   │   ├── methodology/           # 通用方法论（调试/并发/任务规划等，课程无关）
│   │   ├── performance/           # 性能/并行
│   │   └── tools/                 # 工具文档（video-processing/transcription/ocr/document-download/browser-cdp）
│   └── project-management/
│       ├── decisions/             # ADR（只增不改）
│       └── standards/             # 治理规范（NAMING/QUALITY/CODE_STYLE/DOC_* 等）
├── project-management/            # 项目管理：只放 active/ 两份跨课全局活态台账（TASK_STATUS/ISSUES）；单课过程件在 data/_workspace
├── config/
│   └── courses/                    # 课程档案卡 profile（一门课一个 JSON，脚本统一读取，换课只换卡，见 parallel-toolkit-design）
├── code/scripts/                       # 可执行脚本（下载/压缩/转写/OCR/上传/做题/校验，snake_case）
├── transcription/                 # 转写工具链：requirements.txt 入库，venv/ 忽略
├── .secrets/                      # 加密凭证（*.enc；*.json/*.txt 忽略）
├── data/                          # 本地运行数据，整体 gitignore（见第二章）：「高顿」课程库实体目录（ADR-021 去软链）+「_workspace」唯一运行时工作区
├── node_modules/                  # 依赖，gitignore（注：仓库根不再产生 logs/，所有运行日志/断点统一进 data/_workspace，见 2.3）
└── README.md / AGENTS.md / CHANGELOG.md / LICENSE / .gitignore
```

要点：
1. **Git 不再版本化课程成品**（旧 `knowledge-base/organized-content`、`source-materials` 已在阶段④清退、空壳目录 2026-09-07 移除；旧 `lecture-resource-map.json` 及其校验脚本已按 ADR-012 退役——讲↔资源↔知识点路由统一由 `data/_workspace/<profile>/manifest/course-manifest.json` 承接，可 rebuild、不入库）。
2. 工程文档怎么分类、何时新建/删除/调整目录，见本文档第六章。

---

## 二、本地运行数据（data，整体 gitignore）

`data/` 顶层只有两个条目，职责正交、不再把过程件散落在课程目录或 data 根：

```
data/
├── 高顿/                          # 课程库实体目录（原桌面软链已移除，ADR-021）：只放「原始资源 + 知识详解」两层成品/原料（传网盘）
└── _workspace/                     # 唯一运行时工作区：所有过程件（gitignore·不传网盘·不同步飞书，ADR-016）
```

### 2.1 课程目录（data/高顿 下，封板两层结构）

单个**课程目录**只保留成品与永久原料两层，不再内嵌 `_workspace`：

```
data/高顿/CPA/【26考季】VIPCPA系列-税法（蔡俊峻老师）/
├── README.md                          # 课程目录说明：结构图 + 各文件来源/作用 + 对应关系
├── 原始资源/                          # 第一层：按资源类型分桶的原始原料（永久、传网盘）
│   ├── videos/
│   │   └── NN_讲题/
│   │       ├── video.mp4              # 压缩成品（H.265）
│   │       ├── transcript.md          # 转写文字稿（面向人）
│   │       └── transcript.json        # 转写原始数据（技术件，不传网盘）
│   ├── notes/
│   │   └── NN_模块/
│   │       ├── 讲义_{名称}.pdf        # 官方讲义原件（有则建，试卷/纯视频讲可为空）
│   │       └── 讲义_{名称}_OCR.md     # 讲义 OCR 文字稿
│   ├── papers/                        # 题答 JSON（试卷题目/标准答案/官方解析/知识点标签），封板时从工作区归位
│   └── user-notes/                    # 用户笔记/留言原件（按章分子目录），封板时从工作区归位
├── 知识详解/                          # 第二层：成品（传网盘 + 同步飞书，与飞书同构）
│   ├── 01_税法总论/
│   │   ├── 税法概念.md                # 一个官方知识点 = 一篇，篇内固定 4 节
│   │   └── …（本组 N 篇）
│   ├── …（共 14 组、106 篇知识点详解）
│   ├── 课程做题思路解析.md            # 课程全局篇（带本科目特征）
│   └── 考试指导速查手册.md            # 课程全局篇（只通用，冲刺后定稿）
```

CPA 层（跨课）另有一份：`data/高顿/CPA/通用做题思路解析.md`。

### 2.2 统一运行时工作区 data/_workspace（ADR-016）

工作区**不绑定某一门课**：账号/跨课级共享件放 `_account/`，每门课的过程件放以 profile key 命名的子目录；"是否过程件（进不进工作区）"与"属于哪门课（哪个 profile 子目录）"是两件正交的事。脚本统一经 `code/scripts/cdp/load_profile.js` 的 `accountDir/accountAuthDir/workspaceDir/workspaceDirFor` 取路径，禁止再硬编码 `data/cdp-sniff` 等旧目录。

```
data/_workspace/
├── _account/                      # 账号/跨课级（不随单课清退）
│   ├── auth/                      # JWT/抓包鉴权 jsonl（findJwt 唯一来源，滚动留最新）
│   └── user-space/                # 「用户空间」全课程清单快照（滚动留最新）
└── <profile-key>/                 # 课程级，如 cpa-tax-2026 / cpa-accounting-2026
    ├── manifest/                  # course-manifest / papers_inventory / papers_audit / paper_index / syllabus 快照（可 rebuild）
    ├── papers/                    # 题答 JSON、做题结果 exam_result/redo/batch、qvideo_keys（封板归位原始资源/papers）
    ├── notes-raw/                 # 用户留言/笔记原件 all_notes/progress/stats（封板归位原始资源/user-notes，100% 吸收进成品）
    ├── sniff/                     # CDP/手动侦查抓包与截图（验证完即删）
    ├── tmp/download/              # 视频下载/转写临时（.vfetch 分段、merged.ts，单任务成功即清）
    ├── pipeline/                  # 总编排器阶段断点 <n>.done（重跑跳过）
    ├── tickets/                   # 工单/spec/需求表 REQUIREMENTS/BUG 表 BUG_BACKLOG（I2T，过程件）
    ├── task-reports/              # 任务报告、侦查/检查报告（过程件，模板在 docs/development/templates）
    └── logs/                      # 该课运行日志与断点哨兵（含编排层，仓库根不再建 logs/）
```

**分层生命周期**（替代旧"工作区整体一刀切清退"）：

| 分区 | 内容 | 清退策略 |
|---|---|---|
| `_account/auth`、`_account/user-space` | JWT、账号课程清单 | 长期保留，滚动只留最新；JWT 过期重抓 |
| `<profile>/manifest`、`pipeline` | 台账、断点 | 可 rebuild，封板后可清，重跑自动再生 |
| `<profile>/papers`、`notes-raw` | 题答、留言原件 | **封板时归位**该课「原始资源」对应桶后清工作区副本 |
| `<profile>/sniff`、`tmp`、`logs` | 抓包、下载/转写临时、日志 | 验证/单任务成功即清，不跨阶段留存 |

### 2.3 边界与例外

- 课程目录（`data/高顿`）只放成品与永久原料；任何运行时过程件都进 `data/_workspace`，不在课程目录、data 根或仓库根新建过程目录。
- `.secrets/*.enc`：加密、跨课复用，留仓库根；`node_modules/`、`transcription/venv/`：工具链标准位置，留原位 + gitignore；`package.json`/`requirements.txt` 与 `code/scripts/` 入 Git。
- **仓库根不产生运行日志或断点目录**（含工程编排 / 同步脚本，2026-09-08 起取代旧"编排层日志可放仓库根 logs/"的约定）：所有 `*.log`、断点 `.done`、转写临时工作区一律进 `data/_workspace/<profile>/`；账号级 / 跨课共享脚本没有明确 profile 时用 `data/_workspace/_shared/`。脚本统一用可覆盖的工作区变量（`GAODUN_COURSE_PROFILE` / `WS_DIR`），**禁止硬编码仓库根 `logs/`、`transcription/.parallel_work`、`transcription/.qv_work`**。

### 2.4 旧散落件最终去向（2026-09-07 迁移落定）

- 旧 `data/cdp-sniff/*`：鉴权 jsonl → `_account/auth`；账号课程清单 → `_account/user-space`；试卷台账 → `<profile>/manifest`；做题结果/题答 → `<profile>/papers`；侦查 probe/json/png 验证后清（入回收站）；
- 旧 `data/knowledge-source/{papers,paper_index}`、`data/user-notes-raw/<key>`、`data/sprint-videos` → 分别归 `<profile>/{papers,manifest}`、`<profile>/notes-raw`、`<profile>/tmp/download/sprint-videos`；
- 旧课程目录内嵌 `_workspace/`（仅余空 pipeline）删除，断点改由 `data/_workspace/<profile>/pipeline` 承接；旧按讲目录 `.vfetch/` 下载缓存 → `<profile>/tmp/download` 后清。

---

## 三、百度网盘（备份：镜像原始资源 + 知识详解）

- 网盘根：`/apps/CPA课程归档/会计知识库/高顿/CPA/`，与本地**同构镜像"原始资源 + 知识详解"两层**；
- **不传 `data/_workspace/`**（过程件可由接口/脚本重建），不传 `transcript.json`、tmp、logs；
- 上传凭证与命令见 [netdisk-setup.md](development/api/netdisk-setup.md)；上传后做本地↔网盘文件数/大小核对。

```
/apps/CPA课程归档/会计知识库/高顿/CPA/【26考季】VIPCPA系列-税法（蔡俊峻老师）/
├── 原始资源/
│   ├── videos/      # 每讲 video.mp4 + transcript.md（不传 transcript.json）
│   ├── notes/       # 官方讲义 PDF + OCR.md
│   ├── papers/      # 题答 JSON（试卷题目/标准答案/解析/知识点标签）
│   └── user-notes/  # 用户笔记/留言原件（按章分子目录）
└── 知识详解/        # 14 组 + 2 全局篇，共 108 篇 md
```

---

## 四、飞书知识库（只同步知识详解成品）

知识库「CPA备考知识库」，结构与本地 `知识详解/` **同构**，只同步成品：

```
CPA备考知识库/
└── 课程库/
    ├── 通用做题思路解析（跨课一份）
    └── 【26考季】VIPCPA系列-税法（蔡俊峻老师）
        ├── 01_税法总论（父节点）→ 知识点子页面…
        ├── …14 组
        ├── 课程做题思路解析
        └── 考试指导速查手册
```

- 不同步原始资源（视频/讲义在网盘）、不同步 `data/_workspace`；
- **本地全量生成并通过阶段③校验门后统一同步**，冲刺模考后做最终一次同步；不在飞书直接编辑（紧急修复除外）；
- 节点模板见 [KNOWLEDGE_BASE_TEMPLATE.md](development/templates/KNOWLEDGE_BASE_TEMPLATE.md)，接口见 [feishu-api.md](development/api/feishu-api.md)。

---

## 五、目录结构维护原则

### 5.1 基本原则
1. **四地分工不串味**：工程入 Git、原料/成品入 data/高顿、原料+成品备份网盘、成品同步飞书、一切过程件入唯一工作区 data/_workspace（按 `_account` 与 `<profile>` 分区）；
2. 项目仓库只放代码和文档，大体积课程数据不进 GitHub；
3. 模板统一放 `docs/development/templates/`；
4. 目录结构变更必须同步本文档、NAMING、README、DOCUMENTATION_MAP 与 .gitignore。

### 5.2 新建文档前（强制）
先 `grep -r 关键词 docs/` + 查 DOCUMENTATION_MAP 确认无重复；按 Diátaxis 判型、按 NAMING 第九章定文件名与归属目录；预计≥3 个同类文件才新建子目录；建好后更新文档地图与目录 README。

### 5.3 删除文档前（强制）
先 `grep -r 文档名 docs/ code/scripts/` 查引用，先改/删引用再删；评估是否已融入他文、有无追溯价值；删后更新文档地图与所有引用。

### 5.4 调整目录前（强制）
先评估必要性（职责重叠/文件过多/新类型无归属/结构重大变化），产出"前结构→后结构→逐文件移动路径→引用更新清单→文档更新清单"，执行后用 grep 验证无旧路径残留；改名用 `git mv` 保留历史。

### 5.5 通用原则
目录先于文档、职责单一、归属唯一、深度适中（docs 内≤4 层）、名称稳定、空目录及时清理。常见错误纠正沿用"先搜再建/改引用再删/改完验证"的闭环。
