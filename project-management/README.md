# 活动文档目录（active）

> **文档类型**：Active（全局活态台账）
> **更新频率**：状态变化时实时更新
> **维护者**：AI 自动维护
> **读者**：AI 代理 + 用户（了解项目当前状态）

本目录**只放两份跨课全局活态台账**，是新会话 / 接手任务时的入口。

## 文档清单（仅两份，不再增加常驻文件）

| 文档 | 一句话职责 | 谁在用 / 何时写 |
|------|-----------|----------------|
| `TASK_STATUS.md` | **进度视图**：项目到哪了、全局里程碑、当前课程指针、断点与下一步 | AI 启动/接手/被问状态时读；阶段或课程状态切换时写 |
| `ISSUES.md` | **问题视图**：跨课/机制级 BUG、风险的 open→closed 生命周期与解法 | AI 排障先查、被问"有什么问题"时读；发现/解决机制级问题时写 |

## 边界（什么不放这里）

- **单门课的一切过程件**——逐讲/逐卷/批次状态、工单、任务报告、侦查、检查报告、日志、断点哨兵、需求/BUG 过程台账——一律落 `data/_workspace/<course>/`（不入库）：
  - 工单与实时进度：`data/_workspace/<course>/tickets/`
  - 任务报告：`data/_workspace/<course>/task-reports/`
  - 日志/断点：`data/_workspace/<course>/logs/`
- **稳定、跨课复用的决策与方法**落 `docs/project-management/`（standards 规范、decisions 的 ADR、memory 的 OKF），不写进活态台账。
- TASK_STATUS 只放当前课**指针**、不抄 workspace 的易变计数；ISSUES 只收**换课还会踩**的机制问题，单课一次性问题进该课 `tickets/BUG_BACKLOG.md`。

## 使用原则

1. 接手任务前先读 `TASK_STATUS.md`，再按其指针读对应课程 `data/_workspace/<course>/`。
2. 状态变化即时更新 TASK_STATUS；机制问题发现/闭环即时更新 ISSUES。
3. 课程 finalize 后，其 workspace 过程件本地留底（不入库），TASK_STATUS 把该课移入"已完成课程"履历。
