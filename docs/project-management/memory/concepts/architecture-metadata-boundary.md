---
type: Architecture
title: 静态/动态分离与知识库元数据边界
description: docs 只放静态规范、project-management 放动态状态；最终知识详解只留纯知识，学员名/点赞数/userId/日期/noteId 一律不进成品；做题为获取知识来源而非刷满分。
tags: [metadata, 隐私, 静态动态分离, 边界, architecture]
sources:
  - id: adr-007
    resource: ../../decisions/ADR-007-静态文档与动态内容分离.md
    title: ADR-007 静态文档与动态内容分离
  - id: adr-013
    resource: ../../decisions/ADR-013-知识库元数据边界.md
    title: ADR-013 知识库元数据边界
  - id: adr-014
    resource: ../../decisions/ADR-014-考试成绩与AI批改边界.md
    title: ADR-014 考试成绩与 AI 批改边界
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 静态/动态分离与知识库元数据边界

## 一句话结论
两条边界：①**文档层**静态规范（docs）与动态状态（project-management）分离；②**知识成品层**只保留对学习有用的纯知识，**一切平台元数据与个人标识不进知识详解**，原始资料里可以完整留底。做题/交卷的目的是**采集知识来源，不是追求平台满分**。

## 一、静态文档 vs 动态内容（ADR-007）
- `docs/` 只放静态内容：方法论、流程、规范、ADR 决策记录（standards/、decisions/ 半静态、只增不改）。
- 动态内容（任务状态、问题跟踪、测试计划、任务报告、验证报告）归 `project-management/` 下相应目录。
- 决策记录 standards/decisions 是"半静态历史"，不随状态频繁改写。

## 二、知识详解的元数据边界（ADR-013，硬约束）
**最终知识详解中禁止出现**：学员名（如"（学员 XXX）"标注）、点赞/赞助数 `fabulousNum`、`userId`、日期、`noteId` 等一切平台元数据与个人标识。
- **原始资料**（notes-raw、抓包 JSON）保留完整字段，便于追溯；剥离只发生在"原始 → 成品"的加工环节。
- 「四、学员补充」每条只输出 `- {纯文本经验}`；节标题与分类子标题（记忆口诀/易错点辨析/解题技巧/知识补充）是**内容分类标签、不含个人信息，保留**。
- 已根治 `code/scripts/knowledge/organize_user_notes.py`（不再输出 studentName/fabulousNum）；历史清理：点赞 524 处、学员名 745 处。
- 注意别误杀正常词：正文里的"赞/赞助"、文档版本日期"2026-"不是元数据，不清理。

## 三、分数不是目标（ADR-014）
- 每套卷都有 11–15 分主观题是平台"AI 不支持批改（aiUnsupported）"，拿满需人工批改权益（可能付费）；用户已明确不额外花钱，**不追求刷满分**，接受平台最优。
- 知识详解已按官方知识点全覆盖，**平台分数缺失不影响知识系统完整性**。
- 做题/交卷首要目的 = 获取题面、标准答案、解析、用户笔记等知识来源。

## 易踩坑
- "分类标签"和"个人信息"要分清：「学员补充」「记忆口诀」这类标题留；"（学员张三）""点赞 12"这类删。
- 元数据清理要在成品与飞书同步两侧都干净；同步到飞书的版本同样不得裸露这些字段。

## 来源与下钻
- [ADR-007 静态文档与动态内容分离](../../decisions/ADR-007-静态文档与动态内容分离.md)
- [ADR-013 知识库元数据边界](../../decisions/ADR-013-知识库元数据边界.md)（剥离清单、脚本、清理规模）
- [ADR-014 考试成绩与 AI 批改边界](../../decisions/ADR-014-考试成绩与AI批改边界.md)
- 成品结构见 [三层解耦与按知识点聚合](architecture-knowledge-paradigm.md)；做题链路见 [做题/试卷采集接口链路](workflow-exam-paper-pipeline.md)。
