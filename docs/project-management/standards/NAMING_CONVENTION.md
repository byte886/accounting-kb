# 目录与文件命名规范

> **文档类型**：Governance（治理规范）
> **更新频率**：命名规范变更时
> **维护者**：AI自动维护
> **读者**：AI代理（所有操作必须遵守）

> 本规范分两部分：**第一~八章**规范课程数据（课程目录两层、统一运行时工作区 data/_workspace、百度网盘、飞书知识库节点）的命名；**第九章**规范 GitHub 仓库内工程目录与文件（脚本、规范、方法文档、过程产物等）的命名，是仓库命名的唯一事实源。
> 课程数据分层范式基线见 [ADR-012](../decisions/ADR-012-三层解耦与按知识点聚合.md)，运行时工作区的位置与分区见 [ADR-016](../decisions/ADR-016-统一运行时工作区与按profile分区.md)（课程目录物理两层，过程件统一上移 `data/_workspace/`）。所有自动化脚本和手动操作必须严格遵守本规范。

---

## 一、顶层目录结构

```
data/高顿/
└── CPA/
    ├── 通用做题思路解析.md            # CPA 层，跨课共用一份
    └── {课程目录}/                   # 内部两层：原始资源/知识详解（过程件在 data/_workspace，不进课程目录）
```

---

## 二、课程目录命名

### 格式

```
【{考季}考季】VIPCPA系列-{科目}（{老师}老师）
```

### 示例
- `【26考季】VIPCPA系列-税法（蔡俊峻老师）`
- `【26考季】VIPCPA系列-会计（罗翔老师）`

### 规则
1. 考季两位数字（`26`=2026）；
2. 必须含 `VIPCPA系列-` 前缀；
3. 科目用标准简称：税法、会计、审计、财管、经济法、战略；
4. 老师名后加 `老师`，用中文括号 `（）`；
5. **禁止**把 `基础必修`/`全面精讲` 等班次名放进课程目录层（班次体现在原始资源的讲题层）；
6. 课程名以官网实际课程名为准，不用 tax-2026 等工程化名。

---

## 三、课程目录两层命名

每个课程目录下固定为「一个 README + 两个层」，过程件不在课程目录内：

```
{课程目录}/
├── README.md            # 课程目录说明（结构图 + 各文件来源/作用 + 对应关系）
├── 原始资源/            # 用户接触层，中文
└── 知识详解/            # 用户接触层，中文（成品，同步飞书）
```
运行时过程件统一在仓库 `data/_workspace/`（见 3.2），不挂在课程目录下。

### 3.1 原始资源 / 知识详解（中文层）

```
原始资源/
├── videos/NN_讲题/      # 资源桶 videos 固定英文；其下 NN 两位序号_官方讲题全名
└── notes/NN_模块/       # 资源桶 notes 固定英文；其下 NN 两位序号_官方模块名

知识详解/
├── NN_官方模块组名/     # 如 02_增值税法（两位序号+下划线，编号=官方教材/课件模块序）
├── 课程做题思路解析.md  # 课程全局篇，固定名
└── 考试指导速查手册.md  # 课程全局篇，固定名
```

- **模块组目录**：`NN_组名`，两位序号 + 下划线 + 官方模块名（税法 14 组，编号见第八章）；
- **知识点篇**：`{官方知识点原名}.md`，**不加序号、不改写、不合并、不 AI 自造**；一个官方知识点一篇。

### 3.2 运行时工作区 data/_workspace（全英文、固定桶名，不得另造）

工作区不绑定具体课程：账号/跨课级用 `_account/`，每门课用 profile key 子目录正交区分。

```
data/_workspace/
├── _account/{auth,user-space}/        # 账号级：JWT 鉴权抓包、账号课程清单（跨课共享）
└── <profile-key>/                     # 课程级，如 cpa-tax-2026
    ├── manifest/          # course-manifest / papers_inventory / papers_audit / paper_index / syllabus
    ├── papers/            # {paperId}.json、做题结果、qvideo_keys
    ├── notes-raw/         # 用户留言/笔记原件，100% 吸收并归位后删
    ├── sniff/             # CDP 抓包/侦查，验证完即删
    ├── tmp/{download,transcribe}/NN_讲题/   # 单任务成功即清
    ├── pipeline/          # 总编排阶段断点 <n>.done
    └── logs/
```

> 非用户接触层统一用英文（kebab/snake），便于 AI 与脚本处理；桶名固定，新增过程件经 `load_profile.js` 收口函数归入对应桶，不散到 data 根、课程目录或仓库根。脚本取路径一律走 `accountDir/accountAuthDir/workspaceDir/workspaceDirFor`，禁止硬编码旧目录名。

---

## 四、层内文件命名

### 4.1 原始资源/videos/NN_讲题（固定名）

| 文件 | 命名 | 说明 |
|------|------|------|
| 视频 | `video.mp4` | 压缩后成品（H.265） |
| 转写稿 | `transcript.md` | 面向使用者 |
| 转写原始 | `transcript.json` | FunASR 原始输出，技术件不传网盘 |

### 4.2 原始资源/notes/NN_模块

| 类型 | 命名 | 示例 |
|------|------|------|
| 讲义原件 | `讲义_{名称}.pdf` | `讲义_税法全面精讲01-税法总论.pdf` |
| 讲义 OCR | `讲义_{名称}_OCR.md` | OCR 稿统一加 `_OCR` 后缀，与原件对应 |

> 讲义按官网实际挂载归属：某讲有讲义才建 notes 子目录，纯试卷/纯视频讲为空；混合讲按其实际资源建。

### 4.3 知识详解

| 类型 | 命名 | 说明 |
|------|------|------|
| 知识点篇 | `{官方知识点原名}.md` | 篇内固定四节（知识拆解/考试指导/题答解析/学员补充） |
| 课程全局篇 | `课程做题思路解析.md`、`考试指导速查手册.md` | 固定中文名 |
| CPA 层通用篇 | `通用做题思路解析.md` | 放在 `高顿/CPA/` 下，跨课一份 |

### 4.4 运行时工作区（英文固定名，详见 3.2）

- 统一在 `data/_workspace/`：账号级 `_account/{auth,user-space}`，课程级 `<profile>/{manifest,papers,notes-raw,sniff,tmp,pipeline,logs}`；
- `manifest/` 放 course-manifest / papers_inventory / papers_audit / paper_index / syllabus；`papers/` 放 `{paperId}.json` 与做题结果；日志/临时文件一律英文小写。

---

## 五、飞书知识库节点命名（与本地"知识详解"同构）

| 层级 | 节点命名 | 对应本地 |
|------|----------|----------|
| 课程根 | 课程名（`{科目}（{老师}老师）`） | 课程目录 |
| 模块组父节点 | `NN_官方模块组名` | `知识详解/NN_组名/` |
| 知识点页面 | 官方知识点原名（不带 .md） | `知识详解/NN_组名/{原名}.md` |
| 课程全局 | 课程做题思路解析 / 考试指导速查手册 | 同名 .md |
| CPA 层 | 通用做题思路解析 | `高顿/CPA/通用做题思路解析.md` |

- 父节点必须包含全部子节点链接清单 + 一句摘要；子页面更新后父节点题量/摘要同步；
- 飞书只同步"知识详解"，不建原始资源、不建工作区过程件节点。

---

## 六、网盘与本地一致性规则

1. 网盘**只镜像"原始资源 + 知识详解"两层**，结构与本地完全一致；前缀 `/apps/CPA课程归档/会计知识库/高顿/`；
2. **不传 `data/_workspace/<profile>/`**，不传 `transcript.json`、tmp、logs；
3. 必传：`video.mp4`、`transcript.md`、讲义 PDF、OCR、知识详解全部成品与全局篇；
4. 本地改名时网盘走 rename 级联（不重传文件）；每次上传后核对本地↔网盘文件数/大小。

---

## 七、课程数据命名检查清单

- [ ] 课程目录符合 `【{考季}考季】VIPCPA系列-{科目}（{老师}老师）`，以官网课程名为准
- [ ] 课程目录两层齐全（`原始资源/ 知识详解/` + `README.md`），过程件在 `data/_workspace/<profile>/`
- [ ] 模块组为 `NN_官方模块名`，知识点篇为官方原名（无序号、无改写、无 AI 自造）
- [ ] videos 内固定 `video.mp4/transcript.md/transcript.json`；notes 内 OCR 带 `_OCR`
- [ ] 工作区桶名固定（账号级 `_account`、课程级七桶），无中文、无自创目录、无散落到 data 根/课程目录/仓库根的过程件
- [ ] 课程全局篇/跨课通用篇为固定中文名
- [ ] 网盘只镜像课程两层、无工作区过程件；飞书节点与知识详解同构

---

## 八、模块组与知识点的归组命名规则

1. **组**＝官方教材/课件模块（税法 14 组），`NN` 编号按官方模块序；**知识点**＝papers 的 `knowledgePointList` 官方标签去重集合（税法 92 个）；
2. 只用官方分类，禁止 AI 自造组、禁止改名/合并官方知识点；
3. **归组用"显式映射 + 脚本 assert"**：易混点（名称不含模块字样者）逐条显式指定，脚本校验每组点数与总数（税法基线 6/14/7/12/10/3/5/2/2/7/3/6/8/7＝92），不靠运行时关键词兜底；
4. 已知特例（税法）：土地增值税归组10（不被"增值税"误归02）；委托加工/应税消费品/进口环节消费税归03；非居民企业归04；非居民个人归05；主观小问泛标签 id=112376 等价并入"增值税一般计税方法应纳税额的计算"；
5. 换课程/考季按其官方体系重建，不套用本课清单；完整"组→知识点"清单是**课程派生数据**，落 `data/_workspace/<profile>/manifest/course-manifest.json`，不写进本通用规范。

---

## 九、Git 仓库工程目录与文件命名规范（2026-08-31 新增）

> 本章规范 **GitHub 仓库内**的工程目录与文件命名，是仓库命名的**唯一事实源（SSOT）**，遵循两条：
> 1. **只此一处写规则**：其它任何文档（含 `CODE_STYLE.md`、`DIRECTORY_STRUCTURE.md`、`DOCUMENTATION_GUIDE.md`、各目录 README、`code/scripts/README.md`、目录树注释）涉及命名处**只引用本章、不复述阈值或清单**，避免多处复述导致互相矛盾（曾出现 code/scripts/README 把 1MB/10MB 误写成 50MB）；规则变更只改本章。
> 2. **判型以正文实质为准**：头部「文档类型」仅作声明，与正文实质冲突时以实质为准并回头修正头部（见 9.1.1，code-style 即此类）。
>
> 第一~八章的课程/网盘/飞书命名与本章并行，互不覆盖。巡检 / 改名影响面 / 整改回归用 `code/scripts/check/check_naming_consistency.py`。

### 9.1 总原则

1. **先判性质，再定名字**：按 9.2 决策树判定，不凭"在哪个目录"或个人偏好。
2. **工程侧用英文，内容侧用中文**：
   - 工程侧（给 AI/开发者看的规范、方法、脚本、台账、模板）用英文；
   - 内容侧（同步给学习者的知识库成品、每次任务产出且 H1 为中文的过程产物）用中文，且文件名与一级标题（H1）语义对应，便于和飞书节点、文档标题对齐。
3. **大小写与分隔符可机械判定**：同职责文件风格一致，禁止同一单词大小写混排（如 `VERIFICATION_TEMPLATE_knowledge_base`）、禁止中英文前缀混排。
4. **业界依据**：文件/目录名用小写可规避"Linux 区分大小写、macOS/Windows 不区分"导致的跨平台与 URL 问题，连字符被搜索引擎视为词分隔符（Google Developer Documentation Style Guide《Filenames and file types》、Google JavaScript Style Guide）；Python 模块名用全小写下划线 snake_case（PEP 8）。

**分层总览（先看这张表）**：

| 层 | 类别 | 语言 / 风格 | 典型位置 | 示例 |
|----|------|-------------|----------|------|
| L0 | 平台/工具固定名 | 原样（白名单，9.3） | 各处 | `README.md`、`pre-commit`、`.github/` |
| L1 | 治理规范/标准/模板/状态台账/全局索引/顶层骨架 | 英文 UPPER_SNAKE_CASE（9.6） | `docs/` 根、`standards/`、`templates/`、`active/` 台账 | `NAMING_CONVENTION.md`、`REPORT_TEMPLATE.md`、`TASK_STATUS.md`、`WORKFLOW.md` |
| L2 | 方法/操作/流程/工具 API/最佳实践 | 英文小写 kebab-case（9.7） | `guides/api/tools/knowledge/methodology/` | `git-workflow.md`、`multi-role-collaboration.md` |
| L3 | 可执行脚本 | 英文小写 snake_case（9.4） | `code/scripts/` | `baidu_upload.py` |
| L4 | 知识库成品（同步飞书，不入库） | 中文，对应飞书节点/H1（9.5） | `data/.../知识详解/`（gitignore） | `增值税税率.md`、`考试指导速查手册.md` |
| L5 | 单课过程产物（任务报告/测试计划/侦查/工单记录） | 中文，对应 H1、ISO 日期（9.5） | `data/_workspace/<course>/{task-reports,tickets}/`（gitignore 不入库） | `任务报告_对象_2026-08-31.md` |
| L6 | 架构决策记录 | `ADR-NNN-中文`（9.8） | `decisions/` | `ADR-012-三层解耦与按知识点聚合.md` |

#### 9.1.1 五类命名形态速查（按"文件名长什么样"反查）

> 判型只看文档头部「文档类型」与正文实质，**不看标题用词、也不看所在目录**——标题写"规范/指南"不算数，要看正文是强制标准（Governance）还是操作教程（Task）；头部类型与正文实质冲突时以实质为准并回头修正头部（例：`CODE_STYLE.md` 一度标 Task 改小写，复核通篇为"必须/禁止"的强制规范，改回大写并移至 standards/）。

| 形态 | 分隔符 | 什么时候用（头部类型 / 文档性质） | 真实例子 |
|------|--------|----------------------------------|----------|
| ① 固定名 | 原样不改 | 工具/社区钉死的名字（L0，9.3） | `README.md`、`pre-commit`、`requirements.txt` |
| ② 大写 UPPER_SNAKE | 词间下划线 `_` | Governance 规范 / Template 模板 / Active 持续台账 / 全局索引与顶层骨架——回答"必须遵守什么、标准或当前状态是什么、供复制的骨架" | `NAMING_CONVENTION.md`、`CODE_STYLE.md`、`REPORT_TEMPLATE.md`、`TASK_STATUS.md`、`DIRECTORY_STRUCTURE.md` |
| ③ 小写 kebab-case | 词间连字符 `-` | Task 方法流程 / Concept 概念 / 工具类 Reference——回答"怎么一步步做一件事" | `git-workflow.md`、`video-processing.md`、`feishu-api.md` |
| ④ 脚本 snake_case | 全小写、词间 `_` | `.py/.sh/.js` 可执行脚本（L3，9.4） | `baidu_upload.py`、`check_kb_structure.sh` |
| ⑤ 中文 | 段间 `_`、日期 ISO | Knowledge 学习成品 / 中文过程产物 / ADR（L4/L5/L6） | `增值税税率.md`、`任务报告_项目检查与维护_2026-09-03.md`、`ADR-001-文档结构优化.md` |

> **一句话判据**："是什么 / 必须怎样"→ ②大写；"怎么做"→ ③小写；给学习者的中文成品 → ⑤；代码脚本 → ④；工具钉死的 → ①。
> **两个最易混点**：(a) `docs/` 根 5 个顶层骨架（WORKFLOW/REQUIREMENTS/SYSTEM_REQUIREMENTS/DOCUMENTATION_MAP/DIRECTORY_STRUCTURE）虽标 Task/Concept/Reference，仍固定按 ②大写（见 9.6）；(b) `active/` 只放持续状态台账（大写），不设任务交接文件，新会话按使用者话术读实时台账了解情况（见 9.10）。

> 下文 9.3–9.8 的**小节顺序跟随 9.2 决策树的判定顺序**（固定名→脚本→内容产物→治理/方法→ADR）；L0–L6 是类别标签，并非小节先后顺序。

### 9.2 命名决策树（从上到下，命中即停）

1. 是平台/工具**固定名**？→ 走 9.3 白名单，原样不改。
2. 是**脚本**（`.py/.sh/.js/.mjs`）？→ 9.4，全小写 snake_case。
3. 是**内容/过程产物**（H1 为中文、面向学习者，或某次任务产出的中文记录）？→ 9.5，用中文、与 H1 对应。
4. 其余为**工程文档**（英文），再二选一：
   - 讲"必须遵守什么 / 标准是什么 / 供复制的模板 / 当前状态 / 清单索引"（规范、标准、模板、台账、索引）→ 9.6，全大写 UPPER_SNAKE_CASE；
   - 讲"怎么做一件事"（方法、操作、流程、工具/API 用法、最佳实践、交接流程）→ 9.7，全小写 kebab-case。
5. 架构决策记录 → 9.8，`ADR-NNN-中文标题`。
6. 目录 → 9.9。

> **怎么区分 9.6 大写与 9.7 小写（最易混）**：回答"规则/标准/状态是什么"用大写（如命名规范、质量标准、任务状态表、文档模板）；回答"怎么操作、怎么做"用小写（如 Git 工作流、视频处理、编码方法、AGENTS 写作方法、多角色协作）。

### 9.3 L0 固定名白名单（与目录、语言无关，必须原样）

| 固定名 | 说明 |
|--------|------|
| `README.md` / `LICENSE` / `CHANGELOG.md` / `CONTRIBUTING.md` / `AGENTS.md` | 开源/社区约定名 |
| `.gitignore` / `requirements.txt` | 工具固定名 |
| `pre-commit` | Git hook 固定名，**无扩展名**，不改成 snake/kebab |
| `.github/` 及其下 `ISSUE_TEMPLATE/`、issue/PR 模板 | GitHub 平台固定路径，允许平台大写 |
| `.secrets/*.enc` | 加密凭证，主体名小写 snake、扩展名 `.enc` |
| `video.mp4` / `transcript.md` / `transcript.json` | 课程固定件，见第四章 |

除白名单外，不得新造全大写"固定名"。

### 9.4 L3 脚本：全小写 snake_case

- 适用 `code/scripts/` 下 `.py/.sh/.js/.mjs`：多词用下划线 `_`，**禁止连字符 `-`、禁止大写**。
- 正例：`baidu_upload.py`、`check_directory_structure.sh`、`fetch_lecture_video.js`。
- 反例：`check-kb-structure.sh`、`setup-transcription-env.sh`、`SetupTranscribe.js`。
- 依据 PEP 8（Python 模块全小写、可用下划线）；Google JS 指南允许下划线或连字符但要求"跟随项目既有约定"，本项目主流为下划线，统一为 snake_case。
- 唯一例外 `pre-commit`（见 9.3）。

### 9.5 L4/L5 内容与过程产物：中文，文件名对应 H1 标题

**L4 知识库成品**（位于 `data/.../知识详解/`，整体 gitignore **不入 Git**，同步飞书并与中文节点对齐）：

| 类别 | 命名 | 示例 |
|------|------|------|
| 知识点篇 | 官方知识点原名 | `增值税税率.md`、`企业所得税应纳税额的计算.md`（篇内四节，见第一~八章） |
| 课程/跨课全局篇 | 固定中文名 | `课程做题思路解析.md`、`考试指导速查手册.md`、`通用做题思路解析.md` |
| 用户留言原件 | 归 `data/_workspace/<profile>/notes-raw/`（过程件，吸收后清） | — |

> 题/标准答案/官方解析由接口落 `data/_workspace/<profile>/papers/*.json`，不再手抄成中文 md；旧 `知识拆解.md/考试指导.md` 双文档已废止（ADR-012）。

**L5 单课过程产物**（任务报告/测试计划/侦查/工单记录，统一落该课 `data/_workspace/<course>/`、不入库；`project-management/` 只留 TASK_STATUS/ISSUES 两份全局台账）：每次任务生成、H1 为中文，文件名用中文并与 H1 对应：

- 统一格式：`{中文类型}_{对象}_{日期}.md`；日期用 ISO `YYYY-MM-DD`，无日期的持续性记录可省略日期段，但**不得中英前缀混排、不得用紧凑日期 `YYYYMMDD`**。
- 中文类型词：任务报告 / 测试计划 / 问题调研 / 整改方案 / 优化记录 等（验证默认并入任务报告，不单设「同步报告/验证报告」类型；仅视频等非标准对象专项质检可用 `VERIFICATION.md`）。
- 正例：`任务报告_项目检查与维护_2026-09-03.md`；无日期者用对象命名，如 `测试计划_<课程名>.md`。
- 反例：`REPORT_02消费税法_完成_20260829.md`、`TEST_PLAN_税法01.md`、`SYNC_REPORT_税法总论_20260828.md`。
- **英文前缀→中文类型映射（整改对照）**：`REPORT_→任务报告`、`SYNC_REPORT_→同步报告`、`VERIFICATION_→验证报告`、`TEST_PLAN_→测试计划`；紧凑日期 `20260828→2026-08-28`。

### 9.6 L1 治理/规范/模板/台账/索引：全大写 UPPER_SNAKE_CASE

- 判定：回答"必须遵守什么、标准是什么、当前状态、供复制的骨架、清单索引"。
- 位置：`docs/` 根、`docs/project-management/standards/`、`docs/development/templates/`、`project-management/` 的状态台账。
- 正例：`NAMING_CONVENTION.md`、`CODE_STYLE.md`、`QUALITY_ASSURANCE.md`、`REPORT_TEMPLATE.md`、`TASK_STATUS.md`、`ISSUES.md`。
- 模板统一以 `_TEMPLATE` 结尾；禁止同词大小写混排（反例 `VERIFICATION_TEMPLATE_knowledge_base.md`）。
- **`docs/` 根顶层骨架文档固定大写**：`WORKFLOW.md`、`REQUIREMENTS.md`、`SYSTEM_REQUIREMENTS.md`、`DOCUMENTATION_MAP.md`、`DIRECTORY_STRUCTURE.md` 是全局主工作流/需求/总览/索引/结构骨架，统一 UPPER_SNAKE，**不随其内容类型（Task/Concept/Reference）改小写**，与子目录里的具体方法文档（小写）形成层级区分。

### 9.7 L2 方法/操作文档：全小写 kebab-case

- 判定：回答"怎么做一件事"，含步骤/流程/工具用法/API/最佳实践/交接流程。**无论放在 `guides/api/tools/knowledge/methodology` 还是 `project-management/`，方法性文档一律小写连字符。**
- 正例：`git-workflow.md`、`video-processing.md`、`feishu-api.md`、`multi-role-collaboration.md`、`knowledge-detail-build-sop.md`。
- 方法文档的 **H1 标题仍用中文**（文件名是对应中文标题的英文短名，语义对应即可）。
- 依据：Google 开发者文档风格指南要求文件/目录名小写（Unix 区分大小写），多词用连字符且为搜索引擎词分隔符。

### 9.8 L6 架构决策记录：ADR-NNN-中文标题

- 形如 `ADR-012-三层解耦与按知识点聚合.md`：编号三位、连字符分隔、描述用中文；ADR 半静态、只增不改。

### 9.9 目录命名

- **工程目录**：全小写 kebab-case，如 `decisions/`、`standards/`、`guides/`、`methodology/`；不用空格、不用大写；`.github/`、`.secrets/` 等隐藏/平台目录从平台约定。
- **课程数据目录分两类**（详见第一~八章）：用户接触层 `原始资源/ 知识详解` 及其下中文组目录 `NN_官方模块名` 用中文体系；非用户接触层统一工作区 `data/_workspace/`（账号级 `_account`、课程级 `<profile>` 各桶 `manifest/papers/notes-raw/sniff/tmp/pipeline/tickets/task-reports/logs`）用英文。旧 `organized-content/`、`source-materials/` 已废止（ADR-012），旧课程内 `_workspace`、`cdp-sniff` 已上移统一（ADR-016）。
- 目录名与其中文件的命名风格相互独立：目录按本节，文件按 9.3–9.8。

### 9.10 跨类目录说明（避免误判"同目录不一致"）

- `project-management/` 只放**两份跨课全局状态台账**（L1，大写：`TASK_STATUS.md`、`ISSUES.md`）；原 `COURSE_INDEX.md`、`BATCH_TASK_STATUS.md` 等课程级定格件已于 2026-09-08 删除，单课过程件按 L5 落 `data/_workspace/<course>/`。**不设任务交接文件**：角色职责见 multi-role-collaboration 专档（AGENTS 只留速查）、项目当前情况由使用者用话术让 AI 读这些实时台账即可，原 `task-handover.md` 已删除。
- `docs/development/guides/` 只放方法/最佳实践文档（L2 小写），如 `agents-md-best-practices.md`；`CODE_STYLE.md` 正文是"必须/禁止"的强制编码与文档规范（Governance），已移至 `standards/` 并大写，不放 guides。

### 9.11 仓库命名检查清单（新增/改名文件时逐项过）

- [ ] 是否命中 L0 固定名白名单（9.3）？是则原样
- [ ] 脚本是否全小写 snake_case（9.4）
- [ ] 知识成品/中文过程产物是否用中文、与 H1 对应、日期 ISO（9.5）
- [ ] 治理/规范/模板/台账是否 UPPER_SNAKE_CASE（9.6）
- [ ] 方法/操作文档是否全小写 kebab-case（9.7）
- [ ] 是否存在大小写混排、中英前缀混排、空格、紧凑日期 `YYYYMMDD`
- [ ] 目录是否符合 9.9；改名是否用 `git mv` 并级联更新引用、`DOCUMENTATION_MAP.md`、`DIRECTORY_STRUCTURE.md`

### 9.12 历史文件整改原则

规范定稿后，**存量文件一律按本章整改，不设历史豁免**；old→new 逐文件映射、引用级联与验证见整改方案。改名一律用 `git mv` 保留历史，并同步更新所有引用路径、文档地图与目录结构树。
