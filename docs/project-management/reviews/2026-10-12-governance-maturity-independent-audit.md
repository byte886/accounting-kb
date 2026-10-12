# 全仓旁观者评审报告（2026-10-12·治理成熟度模板自评）

> **文档类型**：Governance（治理规范 — 旁观者评审报告）
> **评审者**：MainAgent 独立旁观者视角（非治理 Agent 自评）
> **对象**：accounting-kb 全仓（顶层 README/AGENTS/CHANGELOG + docs/ + project-management/ + code/scripts/ 治理相关）
> **定位**：本仓是体系的**治理成熟度模板/对照基准**，故判据从严——报告本身也须符合模板标准。评审方法＝用本仓自身模板（README 文档边界表、AGENTS 冷/续接路径、decisions/memory/standards 分层）与 content-pipeline 权威源（DOCUMENTATION_PRINCIPLES 8 类词典+README 防则、ADR-001 五原则）做**自我一致性检验**。
> **范围**：仅治理与文档，不含代码功能评审。content-pipeline 本轮只读、未写任何文件。

---

## 一、基础结论

整体治理成熟度高，自我一致性大体成立，**核心骨架通过**：

- **ADR 体系齐全**：`decisions/` 实有 ADR-001~022，`decisions/README.md` 索引逐条对应、只增不改、命名规范；退役脚本清单（文末）清晰。
- **工程记忆编译层合格**：`memory/index.md` 链接与磁盘 `concepts/` 15 篇**完全一一对应**（无缺登记/幽灵登记）；`python3 code/scripts/check/okf_validate.py docs/project-management/memory` **无硬错误（E=0）**，仅 I10（AI 初编未标 human verified）/I11（sources 脚注）信息级提示——符合本仓"机器初编不冒充人核"纪律，非缺陷。
- **活态台账分层清晰**：`project-management/` 仅 TASK_STATUS/ISSUES 两份全局活态台账，单课过程件明确落 `data/_workspace/`；`docs/project-management/` 下 decisions/memory/standards/templates 分层与本仓 README 声明一致。
- **旧仓名 0 残留**：全仓 `.md` grep `ai-video-studio/self-media-ops/multi-repo-orchestration/ai-intel-monitor/multiplatform-content-pipeline` **0 命中**。
- **"五仓体系"说法经核实未过时**：本仓 README 自称"五仓体系治理方法论标杆"，对照 control-tower 今日（2026-10-12）逐仓核对的权威 `docs/五层现状总表.md`——该表开篇即"本表是**五仓体系**现状的唯一权威总表"，五仓＝content-pipeline/research-toolkit/trend-radar/video-studio/we-media-ops，accounting-kb 单列"治理参考/标杆"行。故"五仓"表述与权威源**一致，不改**。
- **两份已废弃 SOP**（`lecture-knowledge-build-sop.md`、`knowledge/chapter-mapping-draft.md`）均带规范"已废弃·被 ADR-012 取代·正文仅追溯"头部，符合"废弃件留追溯"纪律，非僵尸文档。

发现的问题集中在**现行参考文档与仓库现状漂移**（目录树残留已删目录、路径改深/改浅、remote 改名未同步、ADR 计数停在旧值），共 13 项可修 + 2 项待拍板/待核。

---

## 二、问题清单

| # | 级别 | 问题 | 证据（文件:行 / 原文） | 建议修正（已执行见第四节） |
|---|------|------|----------------------|--------------------------|
| 1 | **P2** | README「项目仓库结构（摘要）」列了**已不存在的顶层目录** `knowledge-base/`、`transcription/`；漏列实存的 `config/` | README.md:104 `├── knowledge-base/ …`；:106 `├── transcription/ …`；实际顶层仅 `code/ config/ data/ docs/ project-management/`（+`.secrets/`） | 删两行幽灵目录，补 `config/`（课程档案卡 profile） |
| 2 | **P2** | DIRECTORY_STRUCTURE 仓库根名仍写**旧仓名** `gaodun-course-knowledge-base/`（此为现行参考文档，非 ADR，应反映现状） | DIRECTORY_STRUCTURE.md:32；实际仓库目录名/remote 均为 `accounting-kb` | 根名改 `accounting-kb/` |
| 3 | **P2** | DIRECTORY_STRUCTURE 仍写 `project-management/ … 只放 **active/** 两份活态台账`——`active/` 已于 commit `1076912`（refactor: 去掉 active/ 目录）移除 | DIRECTORY_STRUCTURE.md:50 | 删 `active/`，改为直接放两份台账 |
| 4 | **P2** | DIRECTORY_STRUCTURE 把 `transcription/`、`node_modules/` 画在**仓库根**；实际在 `code/` 下（`code/venvs/transcription`、`code/node_modules`） | DIRECTORY_STRUCTURE.md:54 `├── transcription/`、:57 `├── node_modules/` | 移入 `code/` 子树、删根级幽灵行 |
| 5 | **P2** | pre-commit vendored 路径写错：现行规则 AGENTS 指 `code/scripts/pre-commit`，实际 vendored hook 在 `code/scripts/check/pre-commit`（仓库内仅此一份） | AGENTS.md:215 `（已挂入 code/scripts/pre-commit）`；`ls code/scripts/pre-commit` 不存在 | **已修**：AGENTS:215 改指 `code/scripts/check/pre-commit`。注：DOCUMENTATION_MAP:246 同字样位于「文档优化记录·2026-09-07」编年段，按本仓"编年体只增不改"原则保留，不回改历史记录 |
| 6 | **P2** | git-workflow.md 教用户把 origin 设为**旧仓名** `gaodun-course-knowledge-base.git`（3 处），实际 remote＝`byte886/accounting-kb.git`——照做会配错 remote | git-workflow.md:64 `git remote set-url origin …gaodun-course-knowledge-base.git`、:67（HTTPS）、:210（filter-repo 后 add origin） | 3 处改 `accounting-kb.git` |
| 7 | **P2** | `code/scripts/README.md` 两条 docs 链接**相对深度错**（一层太浅）：`../docs` 解析到不存在的 `code/docs` | code/scripts/README.md:630 `[高顿作业接口档案](../docs/development/api/gaodun-exam-api.md)`、:656 `[flaky-ai-judging.md](../docs/development/guides/flaky-ai-judging.md)` | `../docs`→`../../docs` |
| 8 | **P2** | `project-management/TASK_STATUS.md` 两条 docs 链接**相对深度错**（一层太深）：`../../docs` 解析到仓库外 | TASK_STATUS.md:22 `[生成SOP §六](../../docs/…/knowledge-detail-build-sop.md)`、`[知识详解SOP总览](../../docs/…/knowledge-sop-overview.md)` | `../../docs`→`../docs` |
| 9 | **P3** | `docs/project-management/README.md` 两处计数/登记停在旧值：ADR 范围写 `ADR-001~019`（实到 022）；standards 树漏列实存的 `CODE_STYLE.md`；concept 分组写"链路 5"（实 7） | docs/project-management/README.md:29 `ADR-001~019`；:18-26 standards 树无 CODE_STYLE；:33 `架构4/链路5/治理3/对照1` | ADR 改 `~022`；补 CODE_STYLE.md 行；链路 5→7 |
| 10 | **P3** | TASK_STATUS 任务总览里程碑③写 `ADR-001~019`（实到 022） | project-management/TASK_STATUS.md:43 | 改 `ADR-001~022` |
| 11 | **P3** | DOCUMENTATION_MAP 工程记忆句写"13 篇 concept"（实 15 篇） | DOCUMENTATION_MAP.md:153 `架构/链路/治理/对照 13 篇 concept` | 改 15 篇 |
| 12 | **P3** | CHANGELOG `[未发布]` 漏登 2026-10-08/09 三个总控仓指针同步 commit（fbfa624 / 70af906 / 7af4b8a），与 git log 不符 | CHANGELOG `[未发布]` 最新条目止于 2026-09-19；git log 顶端 3 条为 10-08/10-09 README 总控指针同步 | `[未发布]` 补一行（指针同步 chore） |
| 13 | **P2** | **README 正文偏膨胀，且与其自身文档边界表不完全自洽**：边界表声明 README"不包含 AI 执行规则/命令"，但正文仍展开「项目维护规则/核心原则/三层保障」(:161-186)、「技术方案」(:213-221)、「密钥管理」(:224-230)，部分与 AGENTS §3/§6 重复 | README.md:161-230 vs 其 :17-20 边界表；对照 content-pipeline DOCUMENTATION_PRINCIPLES §3「README 只导航」 | **待用户拍板**（见三·D1）：是否把上述正文下沉到对应 Standard/SOP，README 只留指针 |

---

## 三、观察项 / 待用户拍板 / 待核

- **O-1（已核验通过，非问题）**：「五仓体系」表述——经 control-tower `五层现状总表.md`（今日逐仓核对）证实与权威源一致，**不属过时**。本报告不做改动，仅备案。
- **O-2（观察）**：`code/scripts/README.md:879`、`KNOWLEDGE_BASE_TEMPLATE.md`、`wiki-link-verification-sop.md` 中形如 `[标题](./标题.md)`、`./{同名}.md` 的"断链"均为**模板占位语法/示例**，非真实导航链接，不修。
- **O-3（观察）**：`lecture-knowledge-build-sop.md`、`chapter-mapping-draft.md` 内旧文件名链接为已废弃文档的历史正文，按"编年/追溯体只增不改"保留，不修。
- **D1（P2·待用户拍板）**：问题 #13 README 正文精简。涉及**内容取舍**（技术方案/密钥管理是否下沉、下沉到哪篇），按 AGENTS §3.2 属"L1 修改治理规范本身"，先出方案不擅动。方案：①「技术方案」bullet 下沉 `docs/SYSTEM_REQUIREMENTS.md` 或新建 `docs/development/TECH_STACK.md`，README 留一行指针；②「密钥管理」并入 AGENTS §6 存储分工或 SYSTEM_REQUIREMENTS；③「维护核心原则/三层保障」本就与 AGENTS §3 重复，README 删正文改指 AGENTS。**待用户确认后执行。**
- **D2（待核·未擅动）**：工作树当前有**未提交的删除**——`.trash/` 下 5 个文件（`auto_sync_all.py/.sh.20260919`、`fix_old_sources_format.py.20260914`、`sync_wiki_new.sh.20260919`、`verify_sync_completeness.py.20260919`）被 git 跟踪、本地已删，且 `.gitignore` **未忽略 `.trash/`**。这是评审前既存状态、非本次评审产生。是否：(a) 提交这批删除、(b) 顺手把 `.trash/` 加入 `.gitignore`，**待用户拍板**；本次评审不代决、不提交这批删除。

---

## 四、修正验收标准（迭代闭环）

1. 问题 #1~#12 在边界内就地修正完成，每项写明"做了什么"（见提交说明与下轮复评）；#13/D1、D2 标"待拍板/待核"，不擅自执行；
2. `python3 code/scripts/check/okf_validate.py docs/project-management/memory` 保持 **E=0**；
3. 重跑全仓 Markdown 相对链接校验，本报告修掉的死链（#5/#7/#8）归零；模板占位类不计；
4. DOCUMENTATION_MAP / docs/project-management/README / TASK_STATUS 同步登记（#9/#11）；
5. CHANGELOG `[未发布]` 补登本轮指针同步与本次评审修正（#12）；
6. git 提交并 push origin，工作树干净（D2 待拍板删除除外）；
7. 复评对照本清单逐项标注：已修 / 已标待拍板 / 已标待核，无漏项。
