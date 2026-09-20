# AGENTS.md — AI代理操作手册

> **文档类型**：Governance（治理规范 — AI操作手册）
> **更新频率**：每次流程/工具/规范变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理（每次启动自动加载）

> 本文档是AI代理的操作手册，命令式、可执行。与README.md（给人看的项目介绍）互补。
> 执行任何任务前必须先阅读本文档对应部分，**核心规则在第3章，必须优先阅读**。
>
> **写作原则**：基于 [agents-md-best-practices.md](docs/development/guides/agents-md-best-practices.md)，只包含AI无法推断的内容，已在其他文档中的内容只链接不重复。

---

## 1. 文档边界

| 维度 | 本文档（AGENTS.md） | 其他文档 |
|------|---------------------|----------|
| **定位** | AI操作手册，命令式、可执行 | - |
| **读者** | AI代理（每次启动自动加载） | - |
| **包含** | 核心规则、执行前必读、禁止事项、工具版本、常用命令、异常处理 | - |
| **不包含** | 项目目标介绍、存储分工、课程列表 | → [README.md](README.md) |
| **不包含** | 详细操作流程、各环节步骤 | → [docs/WORKFLOW.md](docs/WORKFLOW.md) |
| **不包含** | 需求定义、功能清单、验收标准 | → [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) |
| **不包含** | 编码规范 | → [docs/project-management/standards/CODE_STYLE.md](docs/project-management/standards/CODE_STYLE.md) |
| **不包含** | 目录结构详细说明 | → [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md) |
| **不包含** | 系统要求与环境配置 | → [docs/SYSTEM_REQUIREMENTS.md](docs/SYSTEM_REQUIREMENTS.md) |

---

## 2. 执行前必读：分「冷启动 / 续接」两条路径（强制）

先判断本次属于哪种，再按对应路径读；**不靠对话记忆猜测、不引用已废弃的旧脚本名/旧目录**。

### 路径 A · 冷启动（满足任一即走 A）
首次接触本项目 / 跨阶段切换（如文档建设→课程生产）/ 用户要求全面梳理 / 对当前任务归属或前置依赖没把握。按序读：
1. `README.md` — 项目概览、存储分工、课程列表、常用查询话术（核心规则已在本文档第 3 章，不重复）
2. 工程记忆 `docs/project-management/memory/index.md` — 跨会话稳定结论与硬约束的"编译入口"，按需沿 concept「来源与下钻」深读源 ADR/规范；记忆层自身变更看同目录 `log.md`
3. `docs/REQUIREMENTS.md` — 项目目标、功能范围、验收标准
4. `docs/WORKFLOW.md` 对应环节 → 沿其「参考文档」链接读专项 SOP（如做题交互规范、压缩参数）
5. `project-management/TASK_STATUS.md` + `ISSUES.md` — 当前状态、前置依赖、跨课问题

### 路径 B · 续接（用户说"继续/接手/接着做 X"，且仍是同一阶段同类活）
如继续写知识详解、继续压缩、继续上传。只读：
1. `memory/index.md`（只扫结论定位）
2. `TASK_STATUS.md` + `ISSUES.md`（到哪、下一步、跨课问题）
3. 该课过程台账 `data/_workspace/<course>/` 与账号级 `data/_workspace/_account/ep3/three_tracks_status.md`（逐讲/逐卷/批次/断点）
4. **当前环节那一篇 SOP/guide 的相关小节 + 上一单元样板成品**（如写知识详解读 knowledge-base-organization §2.1/§2.12 + 上一章成品）

**续接路径不全文读 README/REQUIREMENTS/WORKFLOW**（冷启动已建立、memory 与台账有指针），确有需要沿指针下钻单节。**判不准走 A 还是 B 时，就高走 A。**

### 按需参考（两条路径都不强制每次读）
`docs/DIRECTORY_STRUCTURE.md`（目录）、`docs/SYSTEM_REQUIREMENTS.md`（环境）、`docs/DOCUMENTATION_MAP.md`（文档地图）、`docs/project-management/decisions/`（ADR，重要决策前先查历史避免冲突）、`docs/development/guides/multi-role-collaboration.md`（角色定义与协作）。

**为什么**：文档是项目的"集体记忆"，必须依赖文档而非对话记忆，否则会重复踩已解决的坑；但续接时重复全读稳定背景会白占上下文，故分层按需、沿指针下钻。

---

## 3. 核心规则（强制，必须遵守）

### 3.1 问题驱动更新（强制）

发现任何问题（文件位置不对、脚本有bug、流程有缺陷、文档缺失等）时，必须立即评估是否需要更新文档或自动化检查，评估后必须执行，不能只发现问题不更新。

### 3.2 按变更影响分级处理（强制：先确认再执行）

- **L0 顺手修复**（错字、单处断链、单文件明显小错、不牵动其它文件）：直接修复并记录到任务报告
- **L1 高扩散变更（必须先出方案、用户确认后才执行）**：批量重命名 / 跨目录移动、预计 ≥5 处引用级联、**修改命名或治理规范本身**、新增或删除"持久文档 / 机制"。必须先给"方案 + 全量影响清单（老→新 / 依据 / 影响面）"，用户确认后再动手；本地改完先不 push，交用户验收后再提交（此"验收后提交"仅适用 L1/L2 治理；日常开发与课程生产按里程碑及时 commit，见 [git-workflow.md 8.3](docs/development/guides/git-workflow.md)）
- **L2 架构 / 流程变更**（流程变更、架构调整、新增功能）：先和用户讨论，确认方案后再执行
- 拿不准属于哪一级时，**就高不就低**，先按 L1 出方案

### 3.3 定期检查项目结构

每次开始新任务前、完成大任务后，必须检查项目结构是否合理，发现问题主动梳理调整。

### 3.4 写文档前必须检查文档组织（强制）

**遇到问题需要写文档、更新文档或新增内容时，必须先检查项目文档组织和分工，禁止直接写到任意文档中。**

**检查流程**：
1. 查看文档目录结构：`ls -la docs/`
2. 查找相关文档：用 `grep -r "关键词" docs/` 查找是否已有相关内容
3. 确认文档分工（见本文档第1章）
4. 选择正确的文档，WORKFLOW.md只放概览和链接
5. 确保文档关联：新增或更新后，确保相关文档之间有链接

**新建持久文档 / 机制前的额外门禁（防重复建设）**：先列出它要承担的每一项职责，并逐一指认现有权威源；若这些职责已被现有文档 / 台账承担，则**不新建**（task-handover 重复建设后删除的教训），改为在权威源中补内容，或仅在对话内临时处理、不落盘。

### 3.5 文档同步规则（强制）

每次完成阶段性任务、生成新文档、或变化项目结构时，必须按 `docs/project-management/standards/DOC_SYNC_CHECKLIST.md` 检查并同步相关文档。

**同步时机**：完成单个讲座流程后 / 完成所有试卷后 / 发现问题并解决后 / 项目结构调整后 / 大阶段完成后

**核心原则**：本地文档为主，飞书表格为辅；问题驱动更新，发现问题立即评估是否需要更新文档。

### 3.6 大任务执行状态记录（强制）

**开始任何大任务前，必须先创建执行状态记录，异常恢复时必须先读取状态记录。**

**落点（分层）**：单门课的大任务状态记录（批次进度、工单、断点）落 `data/_workspace/<course>/`（不入库）；`TASK_STATUS.md` 只更新该课的**指针级**状态，不抄批次明细。

**详细规范**：`docs/project-management/standards/BATCH_TASK_EXECUTION.md`

**必须创建执行状态记录的场景**：
1. 批量处理 >3 个讲次
2. 预计执行时间 >1 小时
3. 涉及多个工具链（Playwright + ffmpeg + FunASR + 飞书API等）
4. 用户明确要求"批量处理"、"全部完成"

**必须立即更新TASK_STATUS.md的场景（强制，不得延迟）**：
1. 任务开始时（更新状态为"进行中"）
2. 每个子任务完成时（更新进度）
3. 任务完成时（更新状态为"完成"）
4. 遇到问题或阻塞时（更新问题描述）
5. 项目结构/文档体系/工具链有重大变更时
6. 每次git提交前（检查任务状态是否最新）

**更新要求**：
- 必须立即更新，不得延迟到"以后再更新"
- 更新后必须在提交信息中说明"更新TASK_STATUS.md"
- 如果忘记更新，在文档健康度检查中会被发现并要求补更新

### 3.7 清理与维护原则

**核心价值观（强制）：以精简并删除历史冗余为荣，以堆彻重复实现为耻。**

- **代码/脚本**：新增脚本前必须检查是否已有同类实现；发现 0 引用的一次性脚本、旧版已替代脚本、重复实现时，主动清理（移废纸篓带时间戳，不硬删），同步更新 code/scripts/README.md 与相关文档引用
- **文档**：新增文档前必须检查职责是否已被现有文档承担（见 3.4 防重复建设门禁）；发现过时文档、已废弃 SOP、重复内容时，标注退役或清理，不保留"以防万一"的僵尸文档
- **结构**：定期检查目录结构是否合理，空目录、空章节、0 条目分类不保留（如"计算/综合大题（0 道大题、0 个小问）"这类空标题必须删除）
- **"不改写历史"的适用边界（别用过头）**：
  - **只保护编年/记录体**——`CHANGELOG.md`、ADR（`decisions/`）、`memory/log.md`、git 提交历史、任务报告原文：价值在如实记录"当时怎么定/发生了什么"，**只增不改**；结论被取代时在新 ADR/新条目说明，或在旧文末尾加一行"演进注记"指向前文，不抹原文（即便其引用了已删脚本/旧结构）。
  - **不保护现行规范/手册/活态台账**——AGENTS、README、WORKFLOW、REQUIREMENTS、guides/tools、standards、DOCUMENTATION_MAP 的现行清单、TASK_STATUS/ISSUES、code/scripts/README：价值在"**当前正确**"，其中**完全过期、被取代、失效、写死的旧数字直接删/改**，不承担历史职责；被删内容在 git 历史与 CHANGELOG 永久可溯，不在现行文档里留僵尸。
  - **判据看段落性质、不看整份文件**：同一文件内现行条文保持当前态，只有其中专门带日期的"更新记录/变更日志/整改轨迹"小节才按编年体只增；拿不准一段算编年还是现行时，先当现行清理并在 CHANGELOG 留一行。
- 测试文件、临时日志、残留目录及时清理
- 完成任务后检查是否有中间产物需要清理
- 不要在项目根目录散落临时文件
- **文件和目录有变化时必须检查 .gitignore**：新增/移动/删除文件或目录后，检查 .gitignore 是否需要更新
- **提交前运行 `git status` 检查**：确认没有不该提交的文件
- **发现新文件类型时及时补充**：遇到之前没有的文件类型，必须检查是否需要添加到 .gitignore

### 3.8 知识库生成规则（强制）

**详细规范**：`docs/development/knowledge/knowledge-base-organization.md`

**核心规则**：
1. **本地是唯一源头**：所有知识成品必须先在课程目录 `知识详解/` 完成并过校验门，再统一同步飞书，禁止直接修改飞书
2. **父节点必须含子节点链接+摘要**：每个模块组（章）父节点必须列出本组全部知识点子页面链接与一句摘要
3. **通用方法独立成篇**：跨课程通用方法论放CPA 层 `通用做题思路解析.md`；课程级套路放 `知识详解/课程做题思路解析.md`
4. **过程留痕不上传飞书**：验证/同步为必做动作但默认并入任务报告、不单独成文；如确需留存仅本地保留
5. **子页面更新后同步父节点**：知识点篇更新时，所属模块组父节点的概览/题量/摘要同步更新
6. **冲突处理**：当用户留言与讲义内容冲突时，以讲义为准

### 3.9 文档健康度检查（强制）

**每次大任务完成后，必须执行文档健康度检查，确保文档体系的完整性、关联性和质量。**

**详细规范**：`docs/project-management/standards/DOCUMENTATION_OPTIMIZATION.md` 第十二章

**必须执行文档健康度检查的场景**：
1. 每个课程/每个大任务完成后
2. 项目结构重大调整后
3. 新增/删除/移动大量文档后
4. 用户明确要求检查时

**检查内容**：
1. 完整性：所有文档是否在DOCUMENTATION_MAP.md中有记录，新增文档是否有类型标注
2. 关联性：文档中的链接是否有效，是否存在文档孤岛
3. 结构：目录结构是否与DIRECTORY_STRUCTURE.md一致，是否存在空目录
4. 质量：是否存在重叠内容，大文档是否需要分解
5. 维护：.gitignore是否合理，核心文档是否最新

**自动化保障与边界**：
- pre-commit hook自动检查机械项（文档关联性、类型标注、大文件、命名一致性提示）
- 每次git提交前自动触发，不需要手动执行
- ⚠️ pre-commit 只拦截机械级硬错误；内容过时、职责重复、台账与实际不符、文件去留价值等**语义项它检不出**，仍须按本节人工体检，**不得因 pre-commit 通过就跳过健康度检查**

### 3.10 长对话处理规则（强制）

**当对话超过50轮，或发现自己开始遗忘早期规则/决策时，必须主动建议用户开启新对话。**

**根本原因**：AI模型有上下文窗口限制，对话太长时早期内容会被截断或压缩，导致遗忘规则和决策。

**必须建议开启新对话的场景**：
1. 对话超过50轮
2. 发现自己重复询问已经回答过的问题
3. 发现自己忘记了早期的规则或决策
4. 项目进入新阶段（如从文档建设进入课程执行）
5. 用户明确表示"感觉你忘了"或"之前说过的"

**开启新对话前必须完成的工作**：
1. 确保所有重要决策已记录到ADR（`docs/project-management/decisions/`）
2. 确保任务状态已更新到`project-management/TASK_STATUS.md`
3. 确保所有文档已提交并推送到GitHub

> 是否在新会话前准备摘要由使用者自行决定，不强制生成交接文件/摘要；新会话按第 2 章 A/B 路径恢复、启动方式见下。

**新窗恢复走第 2 章路径**：冷启动走路径 A、续接走路径 B，不强制生成交接文件/摘要（靠读文档 + 用户话术恢复）。用户最简启动方式＝把项目文件夹拖入新对话 + 说角色名（如"产品经理，继续 XX"），无需完整句子。

**四角色关注点速查**（职责详表、管理统一与变更驱动原则见 [multi-role-collaboration.md](docs/development/guides/multi-role-collaboration.md)，为唯一权威、不在此复制）：
- **开发工程师**：技术实现、代码结构、待开发功能、脚本开发与排错
- **项目架构师**：目录/流程/命名/文档体系设计、台账与风险、下一步规划、跨角色协调（统一负责管理）
- **产品经理**：知识拆解、考试指导、做题分析、PRD 需求梳理、产品测试与知识库质量
- **私人秘书**：个人记忆、日程、通用助手，并作为用户代表协调其他角色
- **未指定角色**：先按 TASK_STATUS 总结项目状态，询问用户以什么角色参与、确认后再执行；用户说"继续/接手"则按 TASK_STATUS"下一步" + 对应角色职责推进
- 不依赖对话记忆，重要信息一律从文档（含工程记忆 bundle）获取，发现遗忘主动查文档而非猜测

### 3.11 工程记忆（OKF bundle）与项目自包含（强制）

项目在 `docs/project-management/memory/` 维护一个 OKF v0.2 工程记忆 bundle（决策见 ADR-017），是跨会话的"稳定结论编译层"：

- **只读用法**：新会话按第 2 章顺序读 `memory/index.md` 定位，再沿 concept 的「来源与下钻」读源 ADR/规范；**concept 只写结论与相对指针、不复制源文档正文**，冲突时以源文档为准。
- **维护时机**：当 ADR/规范/链路的**稳定结论**发生变化时，同步修订对应 concept 并在 `memory/log.md` 倒序记一行；易变值（进度、计数、当天日期、SHA、剩余权益）**不进记忆**，需要时实时读台账。
- **信任标注**：AI 机器初编/改写的 concept 不得写 `verified: human`（不冒充人核）；只有用户实际审核后才补 `verified: { by: "human:<id>", at }`。
- **机械校验（提交前必过）**：`python3 code/scripts/okf_validate.py docs/project-management/memory`，硬错误 E 必须为 0（已挂入 `code/scripts/pre-commit`）；警告 W 需逐条确认。
- **项目自包含 / 可移植（硬约束）**：工程运行**不得依赖全局 `~/Doubao/AGENTS.md` 或任何全局技能**——校验器等工具一律 vendor 进本仓库 `code/scripts/`，规则与指针只引用仓库内相对路径；保证仅 clone 本仓库、换一个 Agent 也能按自身文档接手。

### 3.12 知识详解 OKF frontmatter（格式层延伸，强制）

课程库 `知识详解/` 成品统一采用 OKF v0.2 标准档 frontmatter（ADR-017 格式层延伸）；各课章数/知识点数/成品篇数以该课 manifest 为准，不在此写死。

- **type 词表（项目统一，不得自造）**：
  - `KnowledgePoint`：知识点详解（一个官方知识点一篇）
  - `Reference`：课程全局篇（《考试指导速查手册》《课程做题思路解析》）
  - `ChapterIndex`：章 README（每个模块组/章一篇）
- **标准档字段**：`type` + `title` + `description` + `tags` + `sources`（讲义 OCR / 题目 paperId）+ `generated`（`process:knowledge-build`）+ `status: stable` + `stale_after`（新教材发布前复审，默认 `2027-03-31T23:59:59+08:00`）+ 自定义 key（`chapter` / `exam_season` / `question_count` / `point_count` / `scope`）
- **与正文分工**：frontmatter 是机器权威（结构化元数据、可校验、可查询）；正文顶部 `>` Context Block 保留为人读展示（飞书读者看到的就是它），二者内容对齐、不重复维护；正文四节结构（知识拆解 / 考试指导 / 题答解析 / 学员补充）一律不动
- **飞书同步自动剥离**：`code/scripts/knowledge/resync_wiki_content.py` 写入飞书前自动剥离顶部 frontmatter（`strip_frontmatter()`，仅认文件顶部连续 `---...---`），飞书读者不看到 YAML；剥离后正文与原文逐字一致。新增 / 改写知识详解后必须重跑 resync 同步
- **信任标注**：机器初编的 frontmatter 不写 `verified: human`（不冒充人核）；用户实际审核后才补 `verified: { by: "human:<id>", at }`
- **校验与推广**：`python3 code/scripts/okf_validate.py <知识详解目录>`，硬错误 E 必须为 0；新课全量推广前先试点 3–5 篇定模板，随迭代补、不一次性批量。Context Block 题量/点数解析口径（冒号可选、全文正则）、飞书批量同步的 token 退避批次等实现细节见知识生成 SOP 与 `resync_wiki_content.py` 脚本注释，不在此复述

---

### 3.13 Idea-to-Tickets 任务工程方法论（强制）

**核心原则**：把模糊需求一步步变成 Agent 可稳定执行的任务。四个模式（clarify/spec/slice/explain）可单用、可串联，**不依赖特定 IDE、任务系统或画图工具**。

> 通用方法论（四个模式详解、组合套路、三条纪律）见全局技能 `~/Doubao/skills/idea-to-tickets/SKILL.md`；本项目只记录**特有约定**，不重复通用内容。

#### 本项目工单落点（强制）

| 层级 | 位置 | 装什么 | 不装什么 |
|------|------|--------|----------|
| **单课工单** | `data/_workspace/<course>/tickets/`（过程件，不入库） | 工单 01..N、BUG_BACKLOG、REQUIREMENTS、tickets-index | 全局状态、跨课机制问题 |
| **全局任务状态** | `project-management/TASK_STATUS.md` | 指针级状态、全局里程碑、下一步 | 单课逐讲/逐卷计数、工单勾选 |
| **全局问题/BUG** | `project-management/ISSUES.md` | 跨课/机制级问题（换课还会踩） | 单课一次性问题（进该课 BUG_BACKLOG） |
| **稳定决策** | `docs/project-management/decisions/`（ADR） | 不可逆决策、只增不改 | 易变状态、临时方案 |
| **工程记忆** | `docs/project-management/memory/`（OKF bundle） | 跨会话稳定结论编译层 | 进度、计数、当天日期 |

#### 模板位置（vendor 进项目，不依赖全局技能）

- 共识小结：`docs/project-management/templates/idea-to-tickets/consensus.md`
- 规范 Spec：`docs/project-management/templates/idea-to-tickets/spec.md`
- 工单 Ticket：`docs/project-management/templates/idea-to-tickets/ticket.md`
- 工单台账：`docs/project-management/templates/idea-to-tickets/tickets-index.md`
- 需求与决策溯源：`docs/project-management/templates/idea-to-tickets/requirements.md`（实例落 `_workspace`）
- BUG 过程台账：`docs/project-management/templates/idea-to-tickets/bug-backlog.md`（实例落 `_workspace`）

#### 与 OKF 的关系（互补，不重复建设）

- **I2T 负责"生产"**：clarify/spec 里稳定、不可逆的结论，按 OKF 沉淀成 concept/log
- **OKF 负责"记忆"**：跨会话恢复时读 memory/index.md 定位，再沿 concept 下钻源 ADR/规范
- **二者互补**：I2T 不另建记忆体系，OKF 不替代工单系统

#### 过程件写法与融合纪律（首次试跑教训，强制）

- **落点补充**：单课工单落 `data/_workspace/<course>/tickets/`；跨多个 profile、同一平台的共性工作（如名师课六科目共用账号级取流/取 key）落账号级 `data/_workspace/_account/<平台>/`，不强行拆进每个 profile。
- **单一进度真相**：一个工作区"当前做什么、到哪"只在 tickets-index 实时维护；REQUIREMENTS 只记需求与决策溯源，BUG_BACKLOG 只记开放缺陷，三者不写成互相重复的状态板。
- **稳定结论单向流动、过程件只放指针**：clarify/spec 里一旦判定为稳定、不可逆的结论，权威版只写一份进 ADR/OKF；过程件保留 `→ 见 ADR-xxx / concept xxx` 指针，**不复制结论正文**（复制即双写，方案一变过程件先过时、反而误导）。
- **方案被取代即时关单**：某方案/工单/缺陷被新方案取代时，当场标注"被 X 取代·关闭"，不留"绕过中/待修复"僵尸项；机制级缺陷关单时把共性解法提炼到全局 ISSUES/OKF。
- **易变值不抄进过程件正文**：逐讲/逐卷计数、页数、当天进度看 manifest/现场，过程件只写口径与获取命令。

---

## 4. Things to Avoid（明确禁止事项）

### 4.1 操作禁止

- ❌ **不要用Chrome浏览器手动下载文件**——必须用脚本（`code/scripts/download_decrypt.js`或curl）后台下载
- ❌ **不要在一个Bash命令中做多道题**——每个命令只做一道题，避免超时移到后台导致输出丢失
- ✅ **做题必须用纯接口脚本**——`code/scripts/cdp/api_do_paper.js`（单卷）/`code/scripts/cdp/batch_redo_papers.js`（批量）/`code/scripts/cdp/do_sprint_paper.js`（冲刺模考），零 UI 点选
- ❌ **不要跳过"做题前查询知识库"步骤**——必须先读对应知识库文档再答题
- ❌ **不要自行关闭用户打开的Chrome窗口**——只关闭Playwright管理的多余tab页

### 4.2 文档禁止

- ❌ **不要把详细技术内容写到WORKFLOW.md**——WORKFLOW只放概览和链接
- ❌ **不要不检查已有文档就新建文档**——先用 `grep -r "关键词" docs/` 查找
- ❌ **不要把交互规范写到技术文档中，或把技术规范写到交互文档中**
- ❌ **不要新增内容后不更新相关文档的链接**

### 4.3 流程禁止

- ❌ **不要不查阅文档就直接执行**——按本文档第 2 章「冷启动/续接」路径读对应文档后再动手
- ❌ **不要操作失败就直接要求用户手动操作**——必须先查文档、尝试自动修复，无法解决再请求帮助
- ❌ **不要大任务不创建执行状态记录就开始**——批量>3个讲次或预计>1小时必须先创建状态记录
- ❌ **不要对批量重命名 / 跨目录移动 / 治理规范修订"先执行后报批"**——属 L1 高扩散变更，必须先出全量影响清单、用户确认后再做（见 3.2）
- ❌ **不要把生成结果（视频/PDF/文字稿）提交到GitHub**——.gitignore已忽略，不要强制添加

---

## 5. 浏览器操作任务强制检查清单

**开始任何需要浏览器操作的任务前，必须按以下清单逐项检查：**

| 序号 | 检查项 | 检查方法 | 处理方式 |
|------|--------|----------|----------|
| 1 | 关闭无关tab页 | `npx playwright cli -s=ga tab-list` | 超过2个tab时，关闭除工作页面外的所有页面 |
| 2 | 检查Playwright连接状态 | `npx playwright cli -s=ga tab-list` | 如果报错，执行连接恢复流程 |
| 3 | 连接失败自动刷新Token | 连接超时或报错 | 按 `docs/development/tools/playwright-cli-guide.md` 第4节自动刷新，**禁止直接要求用户手动操作** |
| 4 | 检查当前页面是否正确 | `npx playwright cli -s=ga eval "() => window.location.href"` | 如果不是目标页面，导航到正确URL |
| 5 | 检查任务前置依赖 | 查看 `TASK_STATUS.md` | 确认前置任务已完成 |

---

## 6. 存储分工（硬约束）

| 位置 | 内容 | 说明 |
|------|------|------|
| GitHub仓库 | 代码+文档 | **禁止**放视频、PDF、文字稿等生成结果 |
| 项目内 `data/高顿/`（实体目录、gitignore 忽略） | 视频、讲义、文字稿 | 生成结果的主存储，统一相对路径访问（2026-09-14 去软链，见 ADR-021） |
| 百度网盘 | 与本地完全镜像 | 备份+跨设备访问 |
| 飞书知识库 | 知识梳理内容 | 结构化知识，面向学习 |
| 飞书文档 | 任务报告 | 过程记录 |

> 详细的目录结构说明见 [docs/DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md)。

---

## 7. 异常处理流程（任何操作失败时）

**任何操作失败时，必须按以下流程处理，禁止直接要求用户手动操作：**

1. **先检查文档中是否有解决方案**：用 `grep -rn "关键词" docs/` 搜索相关文档
2. **按文档中的解决方案尝试自动修复**：如连接失败→自动刷新Token；命令卡住→按分级处理流程恢复
3. **如果文档中没有解决方案**：先尝试通用故障排除方法（重启进程、清理缓存、检查网络），仍然无法解决时再请求用户帮助，并说明已尝试的方法

### 常见异常的自动处理

| 异常情况 | 自动处理方式 | 参考文档 |
|----------|-------------|----------|
| Playwright连接失败 | 自动刷新Token后重连 | playwright-cli-guide.md 第4节 |
| 命令卡住/超时 | 检查session→刷新页面→重连 | interaction-workflow.md 第4.5节 |
| 页面元素找不到 | 等待页面加载→刷新页面→检查选择器 | interaction-workflow.md |
| 脚本执行报错 | 查看错误日志→检查依赖→按文档修复 | 对应脚本的README |

---

## 8. 文档快速入口

按任务类型查找文档：

| 任务类型 | 先看 | 再看 |
|----------|------|------|
| 视频下载/压缩 | `docs/WORKFLOW.md` 第2节 | `docs/development/tools/video-processing.md` |
| 文档下载 | `docs/WORKFLOW.md` 第3节 | - |
| 百度网盘同步 | `docs/WORKFLOW.md` 第4节 | `docs/development/api/netdisk-setup.md` |
| 视频转文字 | `docs/WORKFLOW.md` 第5节 | `docs/development/tools/transcription.md` |
| 知识库生成 | `docs/development/knowledge/knowledge-sop-overview.md`（总览入口） | `docs/WORKFLOW.md` 第6节 |
| **做题验证** | `docs/WORKFLOW.md` 第7节 | **`docs/development/guides/exam-workflow.md`** |
| 任务报告（过程件，不入库） | `docs/WORKFLOW.md` 第8节 | 模板 `docs/development/templates/REPORT_TEMPLATE.md`，产出落 `data/_workspace/<course>/task-reports/` |
| Git操作 | `docs/development/guides/git-workflow.md` | - |
| 项目维护 | `docs/project-management/standards/PROJECT_MAINTENANCE.md` | - |
| 编码规范 | `docs/project-management/standards/CODE_STYLE.md` | - |
| OCR识别 | `docs/development/tools/ocr.md` | - |
| 飞书API | `docs/development/api/feishu-api.md` | - |

---

## 9. 状态查询协议（收到用户查询时必须遵守）

当用户询问项目状态、任务、问题、维护工作等信息时，**必须先参考 [PROJECT_STATUS_QUERY.md](docs/project-management/standards/PROJECT_STATUS_QUERY.md) 识别查询意图**，再读取对应文档，按标准格式响应。

**6类查询意图：**
- Q1 任务状态查询 → 读 `TASK_STATUS.md`
- Q2 问题/BUG查询 → 读 `ISSUES.md`（跨课/机制级）+ 该课 `data/_workspace/<course>/tickets/BUG_BACKLOG.md`（单课一次性问题）
- Q3 维护工作查询 → 读 `PROJECT_MAINTENANCE.md` + 待优化项
- Q4 文档/操作查询 → 读 `DOCUMENTATION_MAP.md` + `WORKFLOW.md`
- Q5 项目概览查询 → 读 `README.md` + `TASK_STATUS.md`
- Q6 决策/历史查询 → 读 `docs/project-management/decisions/`（ADR）

**关键规则：**
- 用户表达模糊时，根据映射表识别意图，**不要猜测**
- 如果映射到多个意图，**主动询问**用户想了解哪方面，给出2-3个选项
- 按标准响应格式回答，结构化呈现
- 完整映射表和响应格式见 [PROJECT_STATUS_QUERY.md](docs/project-management/standards/PROJECT_STATUS_QUERY.md)

---

## 10. Definition of Done（任务完成标准）

任务完成前，必须逐项验证：

- [ ] 所有生成文件已验证可用（视频可播放、文字稿无明显错误、知识库内容准确）
- [ ] 所有错题已分析原因（知识错误→检查知识库，交互错误→修复脚本）
- [ ] 相关文档已同步（按DOC_SYNC_CHECKLIST.md检查）
- [ ] 临时文件已清理
- [ ] 任务状态已更新（TASK_STATUS.md）
- [ ] 生成结果已上传到对应位置（本地+百度网盘+飞书知识库，按存储分工）

---

*本文档随项目演进持续更新。发现规则缺失或不准确时，按"问题驱动更新"原则立即补充。*
