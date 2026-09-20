# 项目管理规范

> **文档类型**：Reference（参考资料 — 文档索引）
> **更新频率**：结构变更时
> **维护者**：AI自动维护
> **读者**：AI代理+人类

> 本文档是项目管理文档的快速索引。**完整的项目文档地图请参考 [DOCUMENTATION_MAP.md](../DOCUMENTATION_MAP.md)**。

---

## 目录结构

```
docs/project-management/        # 项目管理方法论（静态内容）
├── README.md                    # 本文档，项目管理规范总览
├── standards/                   # 规范/指南类（教你如何做）
│   ├── PROJECT_MAINTENANCE.md   # 项目维护规范索引（拆分为三个子文档）
│   ├── PROJECT_STRUCTURE_MAINTENANCE.md # 项目结构维护规范
│   ├── DOCUMENTATION_GUIDE.md   # 文档写作指南
│   ├── DOCUMENTATION_OPTIMIZATION.md # 文档优化流程与变更驱动
│   ├── QUALITY_ASSURANCE.md     # 质量保证规范（验证标准和流程）
│   ├── BATCH_TASK_EXECUTION.md  # 大任务执行状态记录与异常恢复机制
│   ├── PROJECT_STATUS_QUERY.md  # 状态查询协议、意图分类、模糊表达映射
│   ├── NAMING_CONVENTION.md     # 命名规范（文件、目录、变量）
│   └── DOC_SYNC_CHECKLIST.md    # 文档同步清单
├── decisions/                   # 决策记录（ADR，半静态，只增不改）
│   ├── README.md                # ADR索引
│   └── ADR-*.md                 # 各决策记录（ADR-001~019）
├── memory/                      # OKF工程记忆bundle（跨会话稳定结论编译层）
│   ├── index.md                 # 记忆入口（有什么、在哪）
│   ├── log.md                   # 记忆层自身变更（倒序）
│   └── concepts/                # 高密度concept（架构4/链路5/治理3/对照1）
└── templates/                   # 任务工程模板（vendor进项目，不依赖全局技能）
    └── idea-to-tickets/         # Idea-to-Tickets 模板（clarify/spec/slice + 过程台账）
        ├── consensus.md         # clarify模式：共识小结
        ├── spec.md              # spec模式：带验收的规范
        ├── ticket.md            # slice模式：垂直切片工单
        ├── tickets-index.md     # slice模式：工单台账与依赖图
        ├── requirements.md      # 需求与决策溯源模板（实例落 _workspace，不入库）
        └── bug-backlog.md       # BUG 生命周期台账模板（实例落 _workspace，不入库）
```

> **动态内容**（任务状态、问题跟踪、测试计划、报告等）已移到项目根目录下的 `project-management/` 目录，详见 [project-management/README.md](../../project-management/README.md)。
> **具体课程的专项质检/任务产物**放在对应课程目录下（和被验证对象在一起）；验证默认不单独成文、结论并入任务报告。
> **一次性施工方案 / 迁移脚本等任务过程件不进 docs/**：执行期间落 `data/_workspace/<course>/`，完成后把稳定、可复用的结论提炼进 ADR/OKF，过程件即清理（git 历史可溯），不在持久文档区保留"施工记录"僵尸文件。

---

## 核心规范

### 唯一任务状态来源

**`project-management/TASK_STATUS.md`**（Markdown 文档）

- 所有任务状态、进度、详情以本文档为准
- AI 助手直接编辑本文档更新任务状态
- Git 版本控制，可追溯历史
- 在 GitHub 仓库中，随时可查

**飞书 Base**：保留作为可视化模板，供其他同事参考，不日常更新（避免双轨维护）。

### 测试驱动原则

- 每个新功能/新流程先做**单样本测试**，验证通过后再批量执行
- 测试前明确**测试目标、范围、步骤、通过标准**，用 [TEST_PLAN_TEMPLATE](../development/templates/TEST_PLAN_TEMPLATE.md) 记录；测试计划是过程件，落 `data/_workspace/<course>/`（不入库），不再设常驻 `test-plans/` 目录
- 测试过程中发现的问题立即记录，分类处理

### 缺陷分类与处理

| 严重程度 | 定义 | 处理时机 |
|----------|------|----------|
| 致命（Blocker） | 核心流程完全不可用、数据丢失 | 立即停止，讨论解决 |
| 严重（Critical） | 主要功能受损，影响关键流程 | 记录，讨论处理 |
| 一般（Major） | 次要功能异常，不影响核心流程 | 顺手修复 |
| 轻微（Minor） | 界面/文案/路径错误，改进类建议 | 顺手修复或积压处理 |

**小问题顺手修复，大问题讨论处理。**

---

## 常用查询话术

想了解项目状态时，直接复制下面的话术发送给AI：

| 你想知道 | 直接复制 |
|----------|----------|
| 还有哪些任务要做 | `查询任务状态：还有哪些待完成的任务？` |
| 有什么问题/BUG | `查询问题：当前有哪些未解决的问题或BUG？` |
| 需要做什么维护 | `查询维护：当前有哪些待完成的维护工作？` |
| 项目整体进度 | `查询概览：给我一个项目整体状态的总结` |
| 为什么这样做 | `查询历史：为什么[某个决策]是这样做的？` |

**完整速查表**：[PROJECT_STATUS_QUERY.md](standards/PROJECT_STATUS_QUERY.md)

---

## 维护规则

1. **新增文档时**：必须在本文档对应分类中添加条目，确保可发现
2. **删除文档时**：必须从本文档中移除条目，并检查是否有其他文档引用它
3. **文档移动/重命名时**：必须更新本文档和所有引用该文档的链接
4. **定期检查**：每次大阶段完成后，检查本文档与实际文件是否一致

---

**完整文档地图**：[DOCUMENTATION_MAP.md](../DOCUMENTATION_MAP.md)
