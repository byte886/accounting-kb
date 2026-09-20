# ADR-016: 统一运行时工作区 data/_workspace（账号级与课程级正交分区）

> **文档类型**：Active（决策记录）
> **更新频率**：决策变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理+人类

## 状态

已采纳（2026-09-07）。**修订 ADR-012** 中"运行时工作区内嵌在单个课程目录第三层"的位置约定：过程件统一上移到 `data/_workspace/`，课程目录回归"原始资源 + 知识详解"两层。适用于全部课程（税法已完成迁移与只读回归，会计直接遵循）。

## 背景

ADR-012 把 `_workspace/` 定义为课程目录内的第三层（可重建过程件，finalize 后整体清退）。但随着采集/做题/视频下载脚本增多，运行时过程件实际散落到了多处，与设计脱节：

- `data/cdp-sniff/`：JWT 抓包、试卷台账、做题结果、侦查 probe 混在一起，且是**跨课共享的单目录**，多门课靠文件名后缀 `__<profile>` 勉强隔离；
- `data/knowledge-source/`：更早期（M3）的题答目录，已被 cdp-sniff 取代却仍被两个脚本引用；
- `data/user-notes-raw/`：用户笔记原件，按课程子目录分；
- `data/sprint-videos/`：冲刺/题目视频下载缓存；
- 仓库根 `logs/`（19MB 历史）、根 `_workspace/research-demo`（与课程无关的实验残留）、根 `knowledge-base/`（旧范式墓碑空壳）；
- 两门课的课程目录内还各挂了一个只剩空 `pipeline/` 的 `_workspace/`。

用户在 VSCode 侧边栏看到 `data/` 下并列 `高顿/CPA`、`cdp-sniff`、`user-notes-raw` 等目录，两次纠正并给出决定性裁定：

> "_workspace 只是定义为工作区，但**没有定义为专属于某个课程，所以都要放进去**，如何区别/识别课程是另外一件事。"

这澄清了两个被混为一谈的正交维度：**①某文件是不是运行时过程件（进不进工作区）；②它属于哪门课（用哪个 profile 子目录区分）**。早期方案 A（把 cdp-sniff"正名"为 data 下跨课共享区、不碰脚本）因此被否决。

## 决策

### 1. 唯一工作区 data/_workspace，账号级与课程级正交分区

```
data/
├── 高顿 -> ~/Desktop/高顿     # 只放原始资源 + 知识详解（两层，传网盘）
└── _workspace/                # 唯一运行时工作区（gitignore·不传网盘·不同步飞书）
    ├── _account/{auth,user-space}     # 账号/跨课级，不随单课清退
    └── <profile-key>/                 # 课程级，如 cpa-tax-2026、cpa-accounting-2026
        ├── manifest/  papers/  notes-raw/
        ├── sniff/  tmp/download/  pipeline/  logs/
```

- 账号级 `_account/`：JWT 鉴权抓包、"用户空间"全课程清单等跨课共享件；
- 课程级 `<profile-key>/`：该课的台账、题答、笔记原件、下载临时、阶段断点、日志；
- 多课隔离从"同目录文件名插 `__<key>` 后缀"改为"不同子目录"，子目录内文件名回归无后缀，更直观且不会互相覆盖。`load_profile.js` 原有的 `scopedName/scopedPath` 保留但新代码不再使用。

### 2. 脚本统一经收口函数取路径，禁止再硬编码散落目录

`code/scripts/cdp/load_profile.js` 新增并导出：`WORKSPACE_ROOT`、`currentKey`、`accountDir`、`accountAuthDir`、`workspaceDir`、`workspaceDirFor`。`gaodun_paper_core.findJwt(dir)` 在缺参时统一从 `data/_workspace/_account/auth` 取最新鉴权 jsonl。全部活跃脚本（14 个 Node、4 个 Shell、4 个 Python）改为经这些函数定位；一次性历史迁移工具 `code/scripts/migrate/*` 保留旧路径不动（仅历史用途，文档标注）。

### 3. 分层生命周期替代"工作区整体一刀切清退"

| 分区 | 清退策略 |
|---|---|
| `_account/auth`、`_account/user-space` | 长期保留，滚动只留最新；JWT 过期重抓 |
| `<profile>/manifest`、`pipeline` | 可 rebuild，封板后可清，重跑自动再生 |
| `<profile>/papers`、`notes-raw` | **封板时归位**该课「原始资源」对应桶后清工作区副本 |
| `<profile>/sniff`、`tmp`、`logs` | 验证/单任务成功即清，不跨阶段留存 |

### 4. 课程目录回归两层，工程日志与课程日志分开

课程目录只留「原始资源 + 知识详解」，不再内嵌 `_workspace`；总编排阶段断点改落 `data/_workspace/<profile>/pipeline/<n>.done`。仓库根 `logs/` 只承接工程编排层日志、历史滚动清，课程级日志进 `data/_workspace/<profile>/logs/`。

## 迁移与验证（2026-09-07）

- 原 `data/cdp-sniff` 共 57 项分流，数字闭合：**38 项归位**（auth 2、user-space 1、税法 manifest 2、税法 papers 29、会计 manifest 4）+ **19 项侦查件清退**（12 json + 7 png）；`user-notes-raw` 8 文件归位 `cpa-tax-2026/notes-raw/`；会计台账去后缀归位；空的课程内 `_workspace`、根 `_workspace` demo、根 `knowledge-base` 墓碑、根 `logs` 490 个历史日志全部 `mv` 到带时间戳回收站 `~/.Trash/gkb-workspace-cleanup-20260907_185614/`（不硬删、可恢复）。
- 迁移后 `data/` 顶层仅「高顿」软链与「_workspace」两项。
- 校验：全部改动脚本 `node --check` / `bash -n` / `py_compile` 通过；`grep` 确认活跃脚本零旧路径残留（migrate 除外）；只读回归验证收口函数路径正确、`findJwt()` 能从 `_account/auth` 解析到 token、消费侧读取的台账结构兼容（税法 inventory 3 条、会计 audit 170 条与既有记录一致）、Python 侧 `papers_view/collect_point_questions/organize_user_notes/assemble_point` 均定位到新路径。
- `paper_index.json` 等可重建件当前不在工作区（封板后未保留），由对应采集脚本重跑再生，属预期，非迁移丢失。

## 后果

- **正面**：过程件有唯一归宿，新增课程只需新增一个 profile 子目录、不改任何路径代码；data 顶层与课程目录都回归简洁；账号级与课程级生命周期各自合理，不再误清共享鉴权。
- **代价/注意**：脚本路径约定集中到 `load_profile.js`，新增过程件必须走收口函数、不得私自 `path.join(ROOT,'data',...)`；文档中凡出现"课程内 `_workspace/`"的旧表述都以 `docs/DIRECTORY_STRUCTURE.md` 第二章为准。
- **不改变**：四地分工（Git/本地/网盘/飞书）边界、知识详解成品结构、ADR-012 的按知识点聚合方法；本决策只调整运行时过程件的物理位置与隔离/清退方式。

## 参考

- [ADR-012 三层解耦与按知识点聚合](ADR-012-三层解耦与按知识点聚合.md)（本决策修订其工作区位置）
- [DIRECTORY_STRUCTURE 第二章](../../DIRECTORY_STRUCTURE.md)
- 收口实现：`code/scripts/cdp/load_profile.js`、`code/scripts/cdp/gaodun_paper_core.js#findJwt`

---

> **2026-09-08 演进注记**：正文第 49 行所述"一次性历史迁移工具 `code/scripts/migrate/*` 保留旧路径不动"已随项目管理分层治理调整——`code/scripts/migrate/`（align_m0 / build_course_manifest / migrate_resources / verify_migration）为税法存量迁移定格快照、现役零调用、会计 manifest 由独立的 `cdp/refresh_inventory.js` 生成，故整体清理出工作树（移入带时间戳废纸篓，git 历史永久保留可复现性）。本 ADR 记录的运行时收口决策不变。
