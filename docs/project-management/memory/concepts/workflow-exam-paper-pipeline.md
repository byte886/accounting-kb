---
type: Workflow
title: 做题与试卷采集接口链路
description: 除登录外全程 HTTP 接口：用户空间盘点→syllabus 枚举→record/create→redo 取题与标准答案→submit 一次交卷→主观题逐题 AI 批改→exam-report 回查；JWT 7 天、题型与来源域、只读采集 vs 交卷边界。
tags: [exam, api, 试卷采集, 交卷, ai批改, jwt, workflow]
sources:
  - id: exam-api
    resource: ../../../development/api/gaodun-exam-api.md
    title: 高顿作业接口档案（做题链路 API Reference）
  - id: adr-014
    resource: ../../decisions/ADR-014-考试成绩与AI批改边界.md
    title: ADR-014 考试成绩与 AI 批改边界
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 做题与试卷采集接口链路

## 一句话链路
**除登录外，发现课程 → 枚举作业 → 取题与标准答案 → 交卷 →（主观题）逐题 AI 批改 → 回查，全程可由 HTTP 接口完成**，无需 UI 点选、无需"先做一遍"、不预置本地题库。连接真实 Chrome 仅为复用登录态取 JWT（见 [浏览器连接通道](workflow-browser-cdp.md)）。

```
vcourse/pc（盘点账号全部课程、拿 saasCourseId）
 → syllabus（枚举全部作业 + ID 映射 + progress 完成状态）
 → student/paper/record（取最近作答实例 logId；result=null 的首次卷先 create-paper）
 → redo-paper（题面+选项+标准答案+解析；type5 容器套 type6 子题）
 → 平铺 userAnswerList（客观取 answer；主观子题从 analysis 提炼，父题不提交）
 → 满足最小作答时长 → submit-paper 一次性交全部答案
 → 仅主观卷：逐 type6 子题 correct-ai/cpa，轮询 cs=2（cs=6 逐级补全重发）
 → exam-report 回查
```

## 必须记住的稳定契约
- **网关**：`apigateway.gaodun.com`，做题 `/minerva`、AI 批改 `/aitutor`、大纲进度 `/g-study`、用户空间 `/ep-course`；统一包裹 `status===0` 为成功。
- **鉴权**：头 `authentication: Basic <JWT>`（字面 Basic，非 HTTP Basic Auth）；**JWT 声明有效期 7 天，但服务端可提前失效**（业务码 553649434「登录超时」，HTTP 仍 200，不能只看 exp）；`findJwt()` 从 `_account/auth` **按文件 mtime 取最新**（曾因按文件名排序、新 token 被旧文件遮蔽导致批量失败）；失效由 `refresh_auth_token.js` 从已登录 Chrome 自动重取、批量脚本捕获 553649434 自动刷新重试（最多 2 次），仅 Chrome 也未登录才交用户；**禁止入库**；明文 JSON、全链路无签名/加密 body。
- **ID 区分**：做题用 `saasCourseId`（=courseId，税法 42660），听课/进度用 `vcourseId`（96834）；`csItemId` 是**章节** itemId（不是 paper 节点自身 id），解析需维护章节祖先栈。
- **题型**：1 单选 / 2 多选 / **5 大题容器（不答）/ 6 主观自由文本小问**；type6 既可套在 type5 的 `subQuestionList`，也可**顶层独立**；客观答案在 `questionAnswer.answer`，type6 标准答案在 `questionAnswer.analysis`（answer 仅"见解析"）。
- **来源域**：作业卷（sourceFromType=100533962）origin/referer 必须 `glivepro.gaodun.com`；题库专区卷（100534177）必须 `tiku.gaodun.com`，错则 AI 批改报 11193060。
- **交卷**：type5 父题不进列表、type6 子题平铺且**绝不能留空**（留空则 AI 判分不回写）；项数=questionTotal；受**墙钟最小作答时长**风控（与 body costTime 无关），太快报 10462203，按公式等待、必要时 +20s 重试。
- **AI 批改**：仅 `aiCorrect.cpaBotType===3` 的题发 cpa（=0 是平台未配评分，归 unsupported 不重试）；body 必带 `openEnergyToEquity:1`（漏带 cs=1 永久挂死、救不活）；cs：1 批改中 / **2 完成满分** / 6 缺采分点（三级补全→best-of-N×4→aiCeiling 视同平台最优）；成功扣 1 次权益/子题、失败不扣。
- **answerMode=5 表格作答题（双字段提交，2026-09-08 逆向定稿）**：除 `userAnswer`（表格旁文字解答，同普通 type6）外必须带 `excelAnswer = JSON.stringify(luckysheet.getAllSheets())`，与题面空白模板 `excelAnswerContent` 同结构、回填数值；做题 UI 在独立 qiankun 子应用 `sub-tiku.gaodun.com`（主应用 bundle 搜不到这些字段）；标准答案表格常是 `<img>` 截图、需视觉映射格子坐标，无法可靠映射时只交文字并标记、不臆造坐标。实现路径见 exam-workflow §4.3.2。
- **错误码分层**：token 失效 `553649434`（最后怀疑、须只读硬证据）/ 作答太快 `10462203`（墙钟，+20s 重试）/ **账号级风控 `10462222`**（短时大量 redo 后 redo 写操作全账号被拒，与单卷/times/章节无关，只读 record/analysis 正常；识别后停止一切 redo 与守护器空转，等冷却且用户明确重启，不自动重刷）。
- **完成判据两层**：课程侧只看"是否成功交卷"（syllabus `progress=1`，与分数解耦）；严格满分 fullScore vs 平台最优 platformDone（unsupported/aiCeiling 不阻断）。

## 只读采集 vs 交卷（边界）
- **纯采集知识来源**：redo-paper / paper-analysis 取题面、标准答案、官方解析即可（注意 redo 有"新建实例、times+1"副作用，redo 后必须 submit 闭环，不可中断）。
- **交卷/AI 批改是外部写操作**：会改平台成绩、扣 AI 权益，属需用户授权的动作；冲刺模考（48 题/标题含"冲刺模考"）基础阶段硬排除、最后阶段才处理。
- 采集到的题面/答案/解析是末期知识库的客观来源；**自动化过程产生的错题不作来源**。
- 脚本：共享实现 `code/scripts/cdp/gaodun_paper_core.js`（含 `findJwt` 按 mtime 取最新 token）；单卷 `api_do_paper.js`、批量 `batch_redo_papers.js`（默认 dry-run，内置 553649434 token 自愈重试）；token 刷新 `refresh_auth_token.js`；课程清单 `fetch_user_space_courses.js`。默认**优先用本地已采数据**，不重复联网。

## 来源与下钻
- [高顿作业接口档案](../../../development/api/gaodun-exam-api.md)（逐接口字段、错误码字典、已验证/待验证清单——实现前必读）
- [ADR-014 考试成绩与 AI 批改边界](../../decisions/ADR-014-考试成绩与AI批改边界.md)（为何不刷满分）
- 知识如何聚合成品见 [三层解耦与按知识点聚合](architecture-knowledge-paradigm.md)；课程各 ID 见 [课程 profile 对照](reference-course-profiles.md)。
