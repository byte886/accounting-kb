# ADR-017: 采用 OKF v0.2 作为工程记忆格式层（project-memory bundle，项目自包含）

> **文档类型**：Active（决策记录）
> **更新频率**：决策变更时
> **维护者**：AI 自动维护 + 用户审核
> **读者**：AI 代理 + 人类

## 状态

已采纳（2026-09-07）。本决策只新增"工程记忆格式层"，不改变 ADR-012 的课程数据三层、ADR-016 的工作区结构与任何业务链路。

## 背景

项目积累了 16 篇 ADR、11 篇 standards 与多条链路 SOP，跨会话仍有效的稳定结论（存储分工、工作区收口、知识点范式、元数据边界、CDP 通道、做题接口、飞书链接事实、命名/变更分级等）散落各处。痛点：

1. 新会话恢复上下文主要靠"超长对话总结"硬撑，token 成本高、关键约束易丢、易凭记忆臆造已废弃的旧结论（如旧脚本名、旧目录）。
2. 已具备外部技能 `okf-wiki`（Google Cloud Open Knowledge Format v0.2 的中文使用层 + 零依赖校验器），但项目本身**尚未接入**，技能处于"软模式"，换个 Agent / 换台机器就不复存在。
3. 用户立了硬约束：**工程不得依赖全局 `~/Doubao/AGENTS.md` 或全局技能，切换到其它 Agent 也能无差别接手**。

目标：用一个轻量"编译层"把稳定结论收敛成少量高密度记忆页，做到可移植、可校验、且不与现有文档体系重复建设。

## 决策

### 1. 新增一个工程记忆 bundle：`docs/project-management/memory/`

```
docs/project-management/memory/
├── index.md            # 唯一可带 okf_version frontmatter 的根导航（有什么、在哪）
├── log.md              # 记忆层自身变更，## YYYY-MM-DD 倒序、不带 frontmatter
└── concepts/           # 10 篇高密度 concept（架构4 / 链路4 / 治理1 / 对照索引1）
```

- 每篇 concept 是"**编译后的稳定结论 + 指向源文档的相对链接**"，**不复制** ADR / standards / guides 正文，不替代源文档；细节有冲突时以被链接的源文档为准。
- concept 之间用普通 Markdown 相对链接互链（不用 `[[双链]]`），允许指向 bundle 外的项目真实文件（校验器按文件系统 `exists()` 判定，不报死链）。

### 2. 只叠加 OKF 格式层，不平行重建第二套记忆

- 映射关系：bundle = 记忆入口、concept = 稳定结论编译页、index = 记忆导航、log = 记忆层变更、项目 `AGENTS.md` = schema（规则）、易变状态仍读既有台账 / frontmatter。
- 现有 ADR、standards、目录结构、知识详解**一律不强制回填** frontmatter，保持原位。
- **易变值（进度计数、当天状态、日期、SHA、剩余权益等）不写进记忆正文**，需要时实时读台账，避免"复制即过期"。

### 3. frontmatter 约定（标准档，唯一必填 type）

- type 受控词表：`Architecture / Workflow / Standard / Reference`；并补 title / description / tags / sources（项目内源文档相对路径）/ generated / status。
- **机器初编一律不写 `verified: human`**：本轮 10 篇为 AI 编译，信任等级是 machine-confirmed / unverified；只有用户实际人核通过后，才逐篇补 `verified: { by: "human:<id>", at }`，禁止冒充人核。

### 4. 项目自包含 / 可移植（对应用户硬约束）

- 把零第三方依赖的校验器**复制进项目** `code/scripts/okf_validate.py`（系统 python3 直接跑），运行时**不依赖** `~/Doubao/skills` 下的技能；头部注明 vendored 来源与"勿本地改逻辑以免与上游脱节"。
- 校验接入项目**自有** `code/scripts/pre-commit`（新增 OKF 段，E 级硬错误阻断提交）；项目 `AGENTS.md` 增加记忆 bundle 的采用声明与恢复顺序，**只引用项目内相对路径**。
- **不动**全局 `~/Doubao/PROFILE.md`、不要求全局技能在场；全局 `~/Doubao/AGENTS.md` 里既有的一行 okf 指针可保留，但工程运行不依赖它。
- 新会话 / 新 Agent 的恢复顺序：根 `AGENTS.md`（规则）→ `memory/index.md`（定位）→ 根 `CHANGELOG.md`（最近变更）→ 按需沿 concept 的"来源与下钻"读源文档，不整库灌入。

### 5. Bundle A（课程知识详解接入 OKF）后置，不在本决策批量实施

`data` 下 108 篇知识详解是否加 frontmatter、如何让"frontmatter 机器权威 / 正文人读块派生 / 飞书同步不裸露 YAML"，属于另一项高扩散变更：先试点 3–5 篇定模板，之后随迭代补，**不一次性批量回填**，届时另出方案。

## 后果

### 正面
- 新会话只需读 index + 少量 concept 即可恢复项目骨架与硬约束，不再依赖超长对话总结，降低臆造废弃结论的风险。
- 记忆层可机械校验（frontmatter / 死链 / 孤儿页），并已纳入提交质量门。
- 工程自包含：校验器、规则、指针都在仓库内，换 Agent / 换机按仓库文档即可接手。

### 负面 / 代价
- 多了一层需要维护的编译产物：源 ADR/规范演进后，对应 concept 要同步（否则"记忆漂移"）；缓解：concept 只写稳定结论与指针、不抄细节，并在 pre-commit 校验死链。
- 10 篇当前为机器初编、未人核，信任等级偏低，需用户后续抽审。

### 后续
- 用户抽审后逐篇补 `verified: human`；每次 ADR/规范发生影响稳定结论的变更时，同步修订对应 concept 并在 `memory/log.md` 记一行。
- Bundle A（知识详解 frontmatter）按第 5 条另行试点立项。
- 若 OKF 上游升级版本，整体替换 vendored 校验器与内置 SPEC 口径，不在本地分叉改逻辑。

## 参考

- 记忆 bundle：[../memory/index.md](../memory/index.md)、[../memory/log.md](../memory/log.md)
- 项目内校验器：`code/scripts/okf_validate.py`（vendored from okf-wiki v0.2，零依赖；上游规范 Google Cloud Open Knowledge Format v0.2，Apache-2.0）
- 质量门：`code/scripts/pre-commit`；变更分级与精简原则见 [../standards/NAMING_CONVENTION.md](../standards/NAMING_CONVENTION.md) 与根 `AGENTS.md` 3.2/3.7
- 相关范式决策：[ADR-012](./ADR-012-三层解耦与按知识点聚合.md)、[ADR-016](./ADR-016-统一运行时工作区与按profile分区.md)
