---
type: Architecture
title: 统一运行时工作区与 profile 分区
description: 所有运行时临时物收口到唯一 data/_workspace，账号级与课程级两层正交、按课程 profile-key 隔离，路径必须经收口函数获取，禁止硬编码 data。
tags: [workspace, runtime, profile, architecture, 临时文件]
sources:
  - id: adr-016
    resource: ../../decisions/ADR-016-统一运行时工作区与按profile分区.md
    title: ADR-016 统一运行时工作区与按 profile 分区
  - id: load-profile
    resource: ../../../../code/scripts/cdp/load_profile.js
    title: code/scripts/cdp/load_profile.js 路径收口函数
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 统一运行时工作区与 profile 分区

## 一句话结论
**全项目运行时临时物只有一个家：`data/_workspace/`**（gitignore、不传网盘、不同步飞书）。它内部按"账号级 / 课程级"两层正交组织；任何脚本取工作区路径都必须走收口函数，**禁止再 `path.join(ROOT,'data',...)` 硬编码**或在课程目录旁自建临时目录。

## 目录契约
```
data/_workspace/
├── _account/                     # 账号级（跨课程共享，与具体课程无关）
│   ├── auth/                     #   JWT / 登录态（findJwt 缺省从这里取）
│   └── user-space/               #   用户空间"我的课程"清单 account_courses.json
└── <profile-key>/                # 课程级（一门课一个 key，如 cpa-tax-2026）
    ├── manifest/  papers/  notes-raw/   # 加工各阶段产物
    ├── sniff/                    #   CDP 抓包原始报文
    ├── tmp/download/             #   临时下载
    ├── pipeline/                 #   流水线中间态
    ├── dl-tmp/                   #   视频下载/压缩过程件（.vfetch 的 ts 分片/merged.ts，压完归位即清）
    └── logs/                     #   该课程日志
```
- **正交原则**：`_workspace` 是**全局唯一工作区、不专属某门课**；区分课程靠子目录名 `<profile-key>`，区分账号共享物靠 `_account/`。账号课程清单这类"动态、跨课程、临时"的文件也归 `_account/`，不落到固定课程目录。
- **课程目录只留两层**：`原始资源/` + `知识详解/`，不再在旁边堆 notes / cdp-sniff / logs。

## 关键规则
- **路径收口函数**在 `code/scripts/cdp/load_profile.js`：`WORKSPACE_ROOT / currentKey / accountDir / accountAuthDir / workspaceDir / workspaceDirFor`。新脚本一律调用它们取路径。
- `gaodun_paper_core.findJwt()` 缺省从 `_account/auth` 倒序提取 JWT。
- **分级生命周期替代一刀切清退**：不同子目录按用途决定保留/可重建/可清，不再"每次跑完全删"。
- `paper_index.json` 缺失是**可重建的预期状态**（联网从 syllabus/redo 重算），不是错误。
- 历史迁移（57 项 = 38 归位 + 19 清退）已一次性完成，清退物走带时间戳回收站、不硬删。

## 易踩坑
- 看到 `data/` 下又冒出 `user-notes/`、`notes/`、`cdp-sniff/`、`logs/` 这类目录，基本都是旧脚本没走收口函数，应归位到 `_workspace` 对应子目录而不是新建第二套。
- 视频下载/压缩的 `.vfetch`（上千 ts 分片、merged.ts）同样**禁止落课程库根**：曾误建 `高顿/CPA/<课程>/NN_讲名/.vfetch`，只靠转写末尾 `rm -rf` 自清，一旦主控中断/讲次被拉黑就永久残留。现由 `fetch_lecture_video.js --work-base` 统一指向 `_workspace/<profile>/dl-tmp/`，压缩后成品才归 `原始资源/videos/`，课程库根全程不出现讲目录（commit 2b1f892）。
- 账号级文件（auth、用户空间清单）不要放进某个 `<profile-key>`，否则换课时重复且会漂移。

## 来源与下钻
- [ADR-016 统一运行时工作区与按 profile 分区](../../decisions/ADR-016-统一运行时工作区与按profile分区.md)（完整契约、迁移记录、收口函数清单）
- 收口实现：[code/scripts/cdp/load_profile.js](../../../../code/scripts/cdp/load_profile.js)
- 上层存储版图见 [四地存储分工](architecture-storage-layout.md)；课程 key 从哪起见 [课程 profile 与 ID 对照](reference-course-profiles.md)。
