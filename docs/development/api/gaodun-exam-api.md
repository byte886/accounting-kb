# 高顿作业接口档案（做题链路 API Reference）

> **文档类型**：Reference（参考资料 — 接口契约）
> **更新频率**：抓包验证到新接口/字段时
> **维护者**：AI自动维护
> **读者**：开发工程师（实现「接口为主、UI 兜底」做题链路）
> **证据基线**：2026-09-02 课程 42660 客观卷（消费税 6/9 题等）纯接口闭环 + 主观计算大题卷 82749（type5 套 type6、AI 批改）从带答案交卷到 11/11 的完整实测；原始报文在 `data/_workspace/<profile>/sniff/`（不入库），验证脚本在 `code/scripts/cdp/`

本文档只记录**已抓包/已实测**的接口契约，每条结论标注【实测】或【待验证】，推测不写成事实。连接/抓包手段见 [浏览器 CDP 连接手册](../tools/browser-cdp-connect-guide.md)，共享实现见 `code/scripts/cdp/gaodun_paper_core.js`。

---

## 0. 结论先行（一句话链路）

**除登录外，发现作业 → 取题与标准答案 → 交卷 →（主观题）逐题 AI 批改冲满分 → 回查，全程可由 HTTP 接口完成，无需 UI 点选、无需“先做一遍”、不依赖本地题库预置。**

```
vcourse/pc(盘点账号下全部课程，拿各门 saasCourseId —— 见 2.11)
  → syllabus(枚举全部作业+ID映射+完成状态 progress)
  → student/paper/record(取最近作答实例 paperDataLogId)；result=null 的【首次卷】先 create-paper 创建实例拿 logId
  → redo-paper(返回题面+选项+标准答案+解析；type5 父题套 type6 子题)
  → 平铺构造 userAnswerList（客观取 answer；主观子题从 analysis 提炼，父题不提交）
  → 等待满足“最小作答时长”
  → submit-paper 一次性交【全部】答案（主观子题必须一起交，绝不能留空）
  → 仅主观卷：对每个 type6 子题逐题 correct-ai/cpa，轮询到 cs=2（cs=6 逐级补全重发）
  → exam-report 回查 userScore===totalScore、noCorrectAiQuestionScore===0、wrongQuestionIds 空
```

- 客观卷（仅单选/多选）：纯接口满分已批量验证（一次 20 张全满）。
- 主观计算大题卷（type5/6）：2026-09-02 在 82749 干净实例上实测 **11/11**，8 个子题 AI 全部判满、分数回写正式成绩、UI 报告页同步满分。
- **交卷与 AI 批改解耦**：`submit-paper` 成功即“作业已交”（syllabus `progress=1`，课程进度完成），不耗 AI 权益；AI 批改负责把主观题冲到满分，若超时/权益耗尽/异常，交卷结果保留，只标记待补，不阻塞、不产生坏数据。

---

## 1. 通用约定

### 1.1 网关与统一响应包裹【实测】

- 业务网关：`https://apigateway.gaodun.com`，按子系统分前缀：
  - `/minerva/api/v1/front/`：做题/试卷（record、redo、submit、exam-report）
  - `/aitutor/api/v1/front/`：AI 答疑与**主观题 AI 批改**（correct-ai/cpa、equity）
  - `/g-study/api/v1/front/`：课程大纲/学习进度（syllabus）
- 统一响应包裹：`{ "status": 0, "message": "请求成功", "result": <业务数据> }`。**`status===0` 为成功**，非 0 即业务错误。
- 宿主页 `glivepro.gaodun.com`（课程作业），题库专区页 `tiku.gaodun.com`；均为同页微前端（**无 iframe**）。

### 1.2 鉴权：`authentication` 头（JWT，7 天）【实测】

- 所有业务请求带头 `authentication: Basic <JWT>`（字面量就是 `Basic`，不是 HTTP Basic Auth）。
- JWT HS256 三段式，**实测 `exp-iat = 604800s = 7 天`**，载荷无用户敏感体。
- 请求体均为**明文 JSON**，`content-type: application/json;charset=UTF-8`；**全链路未见 sign / nonce / 时间戳 / 加密 body**（无需逆向前端加密）。
- 导出与选取：连接日常 Chrome 后从任意业务请求头读取，存 `data/_workspace/_account/auth/*.jsonl`；`findJwt()` **按文件 mtime 升序、倒序提取最新文件**（不按文件名排序，否则新抓的 token 可能因文件名靠前后被旧文件遮蔽）。JWT/Cookie 禁止入库。
- **JWT 的 `exp` 未到 ≠ 服务端仍认**【实测】：高顿服务端可提前使会话失效，此时 HTTP 层仍 200、业务层返回 `status=553649434, info="登录超时,请重新登录", result="Unable to verify token"`（minerva 所有接口统一表现）。不能只解码 exp 判断有效性，必须以一次真实只读请求（如 student/paper/record）验活。
- **token 自愈**【实测】：底层 `code/scripts/cdp/refresh_auth_token.js` 连接已登录的日常 Chrome、reload 高顿页监听 `apigateway.gaodun.com` 请求头，自动抓新 token 落 auth 目录。上层统一收口到共享件 `code/scripts/cdp/auth_token_guard.js`（I-013）：导出 `isTokenExpired()`（只认 553649434，做题风控码 10462221 等不误触发）与 `refreshJwtWithLock()`，用 `.refresh.lock` 文件锁做**跨进程 single-flight**——下载是 3 消费者+1 生产者并行，只让第一个命中的进程连 Chrome 刷新，其余等待复用同一新 token，不重复连 Chrome/抢焦点，陈旧锁自动抢占。接入方：①做题 `batch_redo_papers.js` 捕获失效码后刷新并重试同一试卷（最多 2 次）；②下载 `ep3_download_videos.js` 在统一请求入口 `apiGet` 拦截→刷新→重试 1 次，覆盖 syllabus/getVideoInfo/getLiveResource，**修复了「JWT 过期→消费者枚举即 FATAL 秒退→调度器空转静默停摆」**。前提是日常 Chrome 仍保持登录；Chrome 也未登录时刷新抛错、才交用户。
- 建议带全：`accept`、`accept-language: zh`、与浏览器一致的 `user-agent`、来源域 `origin/referer`（见 1.4）。跨子域 POST 会先发一次 `OPTIONS` 预检（正常现象）。

### 1.3 关键 ID 与固定常量【实测】

| 名称 | 值 / 含义 | 来源 |
|---|---|---|
| `courseId` | **即 saasCourseId（SaaS 课程 ID），税法=42660**；syllabus/做题/进入课程 URL（`glivepro.gaodun.com/course/{saasCourseId}/...`）都用它，**不是 vcourseId** | URL / syllabus / 2.11 清单 |
| `vcourseId` | 学员购课实例（虚拟课程）ID，税法=96834；听课/学习进度类接口用它 | vcourse/pc 清单（见 2.11） |
| `projectId` | 考试项目 ID，CPA=8 | vcourse/pc |
| `subjectId` | 科目 ID：会计37 / 审计36 / 财管45 / 经济法39 / **税法38** / 战略46 | vcourse/pc、equity |
| `csItemId` | **章节 itemId（不是 paper 资源节点 id）**；一个章节可挂多张卷 | syllabus 章节节点 `itemId` |
| `paperId` | 试卷 ID | syllabus 中 `discriminator==='paper'` 节点 |
| `resourceId` | 资源 ID | 同上 |
| `paperDataId` | 试卷数据 ID（每卷不同），redo 不改它 | **redo-paper 响应 `result.paperDataId`**，以响应为准 |
| `paperDataLogId` | 单次作答实例 ID | record 取最近值；redo 返回当前值（未提交复用、提交后再 redo 新建） |
| `sourceFromType` | **作业卷 = 100533962**；题库专区卷 = 100534177 | redo/submit 都带；跨课程是否恒定【待验证】 |
| `courseSyllabusId` | 本课程 = 75181 | syllabus URL 末段；获取接口【待验证】 |
| `aiTutorConfigId` | **单题 AI 批改固定 = 55** | correct-ai/cpa body |
| cpa `sourceType` | **单题 AI 批改固定 = 100536073**（注意与卷来源 sourceFromType 不同） | correct-ai/cpa body |
| `cpaAiBotType` | = 3、`botId` 固定串 | 响应回显，请求可不传 |

> 易踩坑：syllabus 里 paper 资源节点自身的 `id`（如 929906）**不是** `csItemId`；`csItemId` 取其所属章节的 `itemId`（如 2074449）。解析时维护章节祖先栈。

### 1.4 来源域校验（origin/referer）【实测·关键】

- **作业卷**（sourceFromType=100533962）的 redo/submit/exam-report **和** AI 批改，`origin/referer` 必须是 `https://glivepro.gaodun.com`；
- **题库专区卷**（100534177）则必须是 `https://tiku.gaodun.com`；
- 用错来源域调 AI 批改会报 `11193060 权限不足`。共享模块 `makeHeaders(jwt,{origin})` 已默认 glivepro。

---

## 2. 接口清单

### 2.1 课程大纲 / 作业列表 / 完成判据：`GET /g-study/api/v1/front/course/{courseId}/syllabus/glive/{courseSyllabusId}`【实测】

- 一次返回整门课章节树与全部资源，**单接口全量、无分页**；本课程约 294KB、含 116 张 paper。
- 顶层统计：`resourceTotal`（资源总数）、`doneResourceTotal`（已完成）、`runResourceTotal`（进行中）。
- 试卷资源节点（章节的 `afterClassResource/inClassMainResource/preClassResource` 等数组里）关键字段：`discriminator:'paper'`、`paperId`、`resourceId`、`title`、`num`(题量)、`homework`、**`progress`（完成判据，见下）**。
- **`progress` 三态 = 课程侧“作业完成”判据【实测，对照 record】**：

  | progress | record.paperSubmitStatus | 含义 |
  |---|---|---|
  | `null` | 无记录 | 没做过 |
  | `2` | 0（未交卷） | 做过/暂存但**没交卷**（“要补”的就是这种） |
  | `1` | **1（已交卷）** | **已交卷＝课程进度完成**（不看分数、不等主观后批） |

  即：**课程判定作业完成只看“是否成功交卷”**。116 张卷实测分布 null=85、2=5、1=26。
- 递归时维护“最近章节祖先”给每张 paper 标 `csItemId`；参考 `gaodun_paper_core` 上游的 `resolvePaper()`（api_do_paper.js）。
- **安全分流**：标题含“冲刺模考”或 `num===48` 的卷在基础作业阶段排除，全部基础作业完成后的最后阶段单独处理。

### 2.2 作答记录：`GET /minerva/api/v1/front/student/paper/record?paperId=&sourceFromType=&needAuth=1`【实测】

- 返回最近实例：`paperDataLogId`、`times`(已做次数)、`score`(历史分)、`questionTotal`、`paperSubmitStatus`(1 已交/0 未交)；**从未做过的卷 `result=null`**。
- 分支：有最近实例 → 直接把其 `paperDataLogId` 交 redo-paper；`result=null` 的首次卷 → 先调 create-paper（见下）。

### 2.2.1 首次创建实例：`POST /minerva/api/v1/front/create-paper`【实测·首次必走】

- **触发条件**：record 返回 null（从未做过）。redo-paper 不能凭空建实例，缺 logId 直接报 `10463001「用户做试卷记录ID不能为空」`。
- 请求体（**不带 paperDataLogId**）：
```json
{"paperId":82710,"sourceFromType":100533962,
 "businessParam":{"courseId":42660,"csItemId":2074472,"resourceId":2459906,"paperId":82710,"sourceFromType":100533962}}
```
- 响应 `result`：`{paperDataId, paperDataLogId, autoSubmitStatus, canTrial, screenToggleNum, referenceMaterialList, displaySortNum}`；取 `paperDataLogId` 再调 redo-paper。
- 前端真实时序（抓包）：record(null) → **create-paper** → paper-data-log/status → redo-paper(带新 logId) → question/extra。create-paper 同样会建未提交实例，其后必须跟 submit 闭环。

### 2.3 取题（含标准答案与解析）：`POST /minerva/api/v1/front/redo-paper`【实测·核心】

- 请求体（明文）：
```json
{
  "paperDataLogId": <record 最近值>,
  "sourceFromType": 100533962,
  "needReviewInfo": 1,
  "businessParam": {"courseId":42660,"csItemId":2074449,"resourceId":2460121,"paperId":82749,"sourceFromType":100533962},
  "openEnergyToEquity": 1
}
```
- 响应 `result`：`paperDataLogId`、`paperDataId`、`questionTotal`、`totalScore`、`totalTakeTimes`(可重做次数)、`runtime`、`moduleList[]`。
- **题目结构 `moduleList[i].questionList[j]`**：
  - `questionType`：**1=单选、2=多选【实测】；5=计算/综合大题容器（自身不作答、optionNum=0、answer=null）；6=主观自由文本小问【实测于 82749】**；判断/填空等其余题型【待验证】。
  - **type6 有两种存在形态【2026-09-02 补，实测】**：① 套在 type5 父题的 `subQuestionList[]` 里（82749/85912 等，常见）；② **顶层独立 type6，questionList[j] 直接就是 type6、没有 type5 父容器**（85916 整卷 14 题、85917 整卷 11 题、85919 有 3 题均是）。两种形态答案都在 `questionAnswer.analysis`、都按 type6 项提交，`buildUserAnswers` 已统一处理（早期版本只认形态①，把形态②误当客观题提交了"见解析"而得 0 分，已修）。
  - **type5 父题的子题在 `subQuestionList[]`**（注意：exam-report 里同一结构字段名叫 `subQuestion`，勿混）。
  - 客观题：`questionAnswer.answer` 即正确选项（单选 `"C"`；多选 `"A,B,D"` 逗号拼接无空格）。
  - **主观 type6 子题：`questionAnswer.answer` 仅为“见解析。”，标准答案与采分点都在 `questionAnswer.analysis`（HTML 文本）**；子题另有 `artificialIntelligence/aiCorrect/score` 字段，标识由 AI 批改。
- **主观答案自动提炼（`gaodun_paper_core`，实测有效）**：
  - `canonAnswer(analysis)`：去 HTML → 取「【点拨】」**之前**的计算/结论句 → 去开头 `(n)` 序号与结尾句读。首版交卷与首次 AI 批改都用它；
  - `qualitativeAnswer(analysis)`：取「【点拨】」段，砍掉“即/也就是…”引导的**通用公式尾巴**（含“账面成本”等占位词，贴上去反而干扰判分），保留法理/因果陈述句，供 cs=6 补定性采分点；
  - `fullAnswer(analysis)`：整段去 HTML 解析，作最后兜底。
- **抽题/乱序【实测】**：同卷多次进入，questionId 序列、选项顺序、答案字母完全一致（固定题集固定顺序）；即便将来随机，按当次响应的 answer 选当次 selectList 即可。
- **redo 副作用【实测】**：redo 新建实例、`times+1` 并把 record“最近实例”切到该未提交实例（paperSubmitStatus 1→0、score 清零，历史成绩仍在）。**redo 后必须紧跟 submit 闭环，不可 redo 后中断**；同一未提交实例再 redo 复用、不重复 +1。
- **知识来源取数口**：题面 `title/selectList`、标准答案 `answer`、官方解析 `analysis` 即末期知识库的客观来源；自动化过程产生的错题不作来源；冲刺模考 48 题走同接口、最后阶段才采集。

### 2.4 逐题保存：`POST /minerva/api/v1/front/submit-question`【实测，非必需】

- UI 每选一次就发（`{paperId,paperDataId,paperDataLogId,questionId,userAnswer,costTime,practiceMode:0}`，可覆盖）。**纯接口交卷不需要它**，`submit-paper` 的 `userAnswerList` 才是最终答案。

### 2.5 交卷：`POST /minerva/api/v1/front/submit-paper`【实测·核心】

- 请求体（明文）：
```json
{
  "costTime": 25,
  "paperId": 82749, "paperDataId": 127705482, "paperDataLogId": 149470760, "submitType": 1,
  "userAnswerList": [
    {"questionId":1681471,"questionType":1,"userAnswer":"B","userClozeAnswers":[],"userAnswerImageList":[]},
    {"questionId":1681676,"questionType":6,"userAnswer":"业务（1）的销项税额=（800-40）×13%=98.8（万元）","userClozeAnswers":[],"userAnswerImageList":[]}
  ],
  "sourceFromType": 100533962,
  "businessParam": {"courseId":42660,"csItemId":2074449,"resourceId":2460121,"paperId":82749,"sourceFromType":100533962}
}
```
- **平铺规则【实测】**：type5 父题**不进** userAnswerList；把其 `subQuestionList` 每个 type6 子题作为一项（`questionType:6`、`userAnswer`=canon 文本）；**顶层独立 type6 同样直接作为一项**（答案取 analysis，不是 answer 里的"见解析"）。最终项数应等于 `questionTotal`（82749=3 客观+8 子题=11）。
- **主观子题必须随交卷一起提交，绝不能留空【实测·关键纠错】**：
  - 留空交卷：子题 `userAnswerStatus=0`（正式答题卡显示“未做”），此后即使 AI 辅导批改判满，**分数也不回写**正式成绩，作业等于没答全；
  - 带答案交卷：子题 `userAnswerStatus=4`（已提交·待批改），交卷后再 AI 批改，**分数逐题回写**（82749 实测 3→5→11）。
- **只交列出的题**：userAnswerList 缺题，服务端就按未答计，务必按 redo 平铺全量。
- **风控·最小作答时长【实测】**：按“redo 建实例→submit 的墙钟时长”校验，**与 body 的 costTime 无关**；太快被拒 `10462203「考试时间太短」`。安全值 `dwellSec = max(20, 答案项*1.5 向上取整到5s, 含主观再保底25s)`；遇 10462203 自动 +20s 重试一次。全程低频拟人。
- 成功 `status=0,result=true`。已交卷实例勿重复 submit（幂等【待验证】），交卷后走 record/exam-report。

### 2.6 主观题 AI 批改：`correct-ai/cpa`【实测·核心，2026-09-02 定稿】

**（1）发起批改** `POST /aitutor/api/v1/front/question/correct-ai/cpa`
```json
{
  "itemId": 1681676,                 // type6 子题 questionId
  "paperDataLogId": 149470760,       // 已交卷的实例
  "aiTutorConfigId": 55,
  "sourceType": 100536073,
  "userAnswer": "<完整答案：计算式+结果单位，必要时附定性句>",
  "excelAnswer": "",
  "openEnergyToEquity": 1            // ★必带！漏带会被受理(cs=1)但永不派发模型，且重发救不活
}
```
- **硬前提**：该实例已 `submit-paper` 交卷；来源域头与卷一致（作业 glivepro / 专区 tiku），错则 `11193060`。
- **`openEnergyToEquity:1` 必带**【实测】：前端就是固定附加它；漏带返回 cs=1 永久挂起（不派发模型），且对同一题重发只回同一条挂死记录、无法自救，只能 redo 新实例重来。
- 成功扣 **1 次 AI 批改权益/子题**；失败、重复（11193404）不扣。

**（2）轮询结果** `GET /aitutor/api/v1/front/question/correct-ai/cpa/status?paperDataLogId=&itemId=`
- 同结构返回，约 5–15s/题；每 5s 轮询，单题上限约 75s。
- **correctStatus（cs）状态码字典【实测】**：

  | cs | 含义 | 处理 |
  |---|---|---|
  | 1 | 批改中（缺 flag 时会永久停留） | 正常则继续等；超 75s 仍 1 记为 aiFailed |
  | **2** | **批改完成＝该题满分**（不是 3） | 完成 |
  | 6 | 部分得分/缺采分点 | **允许重发并覆盖同一条记录**，走下方「cs=6 补救链」 |

- **cs=6 补救链（`correctSubjective`，2026-09-02 定稿）**：
  1. **三级文本补全**：① `canon+qual`（结论句+干净定性句）→ ② `full`（整段解析原文）→ ③ 按本次 status 里 `correctPointList` 中 `showStatus!==1`（未命中）且 `answer` 非空的**AI 自给参考点**定向拼补；
  2. **best-of-N 原样重取（常量 `AI_CS6_RERUN=4`）**：三级后仍 cs=6，把标准答案原文再原样重交最多 4 次、碰到一次 cs=2 即停——用于对冲 AI 判分的随机抖动；
  3. **aiCeiling（AI 判分上限）**：N 次后仍 cs=6，且我方提交内容归一化后就是标准答案原文，单独立桶 `aiCeiling`，**视同平台最优、不阻断完成**（详见 [第三方 AI 判分不确定性应对](../guides/flaky-ai-judging.md)）。
- **按题分流（`aiCorrect.cpaBotType`，build 阶段确定）【实测·关键】**：redo / paper-analysis 每个 type6 都带 `aiCorrect`：`cpaBotType===3`（同时有 `botId/aiTutorConfigId/costEnergy=1`）= 题库配了 CPA 批改机器人，才对它发 cpa，且 body 的 configId/botId **取该题自己的值**（不写死 55）；`cpaBotType===0`（botId 空、configId=0、costEnergy=0）= **题库未配评分标准，平台无判分通道（UI 无"帮我批改"、paperReviewInfo=null 无教师），cpa 必回 `11193401`，答案照交但不批改、不计失败**。前端判据 `E=(aiCorrect.cpaBotType===3)` 才渲染批改按钮（chunk 469.*.js）。
- **并发批改**：不同 itemId 相互独立，`mapLimit` 限并发 `AI_CONCURRENCY=3`、发起前 `idx*120ms` 错峰（可用 `opts.aiConcurrency` 覆盖）；73/28/19 题等多卷实测未触发风控。

- 返回 `corrects[]` 为各评分维度：`questionTypeLabel`（computationalAnalysis 计算分析 / points 定性结论）、`correctText.questionScore/userScore`、`correctPointList[]`。**points 定性维度可能由模型动态生成、参考答案字段为空且有判分抖动**——故 userAnswer 要覆盖“计算式+结果单位+必要法理结论”。
- **常见错误码**：`11193403` 学员答案为空；`11193060` 权限不足（未交卷/来源域错/被占用，**也可能是 body 缺 `excelAnswer/openEnergyToEquity` 字段**）；`11193404` 批改状态错误（题已批过 cs=2，别重复，直接读 status）；**`11193401` 题目未配置评分标准（题库未配 AI 机器人，非答案错、非风控、不扣权益，归 unsupported 不重发）**；`10462408` 整卷一键批改失败（见 2.9 死路）。
- **AI 判分存在固有抖动【实测+外部研究】**：同一份标准答案重复提交，`semanticJudgment/points` 等语义维度可能这次命中、下次漏判（1749889 跨实例一次中、一次全灭；1687633 答案逐字含采分点仍判未命中）。这是 LLM-as-judge 的已知非确定性（即使 temperature=0 也存在、完整性维度波动最大），不是我方答案问题；同一实例内连续重交通常结果趋同，故 best-of-N 对"稳定漏判"题可能无效（实测 2 题各重交 4 次仍 cs=6 → aiCeiling）。应对方法论见 [flaky-ai-judging](../guides/flaky-ai-judging.md)。
- **已验证死路（勿重复）**：① 漏 flag→cs=1 永久挂死；② 交卷留空（uAns=0）后批改不回写；③ 未交卷就批改/来源域错→11193060；④ 空 userAnswer→11193403；⑤ 不会“服务端自动批改”，必须主动逐题调；⑥ 整卷一键 `one-key-correct/start` 对本类卷（openAiCorrectStatus=0）恒返 10462408，不用。

### 2.7 考试报告 / 回查：`POST /minerva/api/v1/front/exam-report`【实测】

- 请求体 `{paperDataLogId, needReviewInfo:1}`。
- **结构（注意命名）**：逐题在 `result.answerSheetModuleList[].questionList[]`（不是 moduleList）；type5 大题下子题数组字段是 **`subQuestion[]`**（redo 里叫 subQuestionList）。
- 顶层关键字段：
  - `userScore/totalScore`（**AI 批改分会回写 userScore**，前提是交卷时带了主观答案）、`answerRightNum`（只计客观题数）、`totalQuestionNum`（含子题）、`answerRightPercent`；
  - `allRightStatus`、`wrongQuestionIds`（空=无错题）、`subjectiveQuestionScore`（主观总分）；
  - **`noCorrectAiQuestionScore`（未批改 AI 题分值，=0 即主观全部处理完）**、`noCorrectSubjectiveQuestionScore`；
  - `correctStatus=3`（已交卷）、`oneKeyCorrect{openAiCorrectStatus,aiCorrectStatus}`（本类卷=0，不开放整卷一键）、`paperReviewInfo`（教师批改，本场景全空）。
- **子题状态字段**：
  - `userAnswerStatus`：0=未答、1=客观已答判分、2=大题容器、**4=主观已交答案待批改**；
  - `aiQuestionStatus`：0=非AI/未进入、1=待 AI 批改、**2=AI 批改完成（满分）**、6=部分；
  - `userScore`：子题得分（满分=子题 score，通常 1）。
- **满分通过判据**：`userScore===totalScore && noCorrectAiQuestionScore===0 && wrongQuestionIds 为空 && 所有子题 aiQuestionStatus===2`（无主观卷则后两项天然满足）。交卷后立即查可能未出分，客观等 1.2–1.5s、主观随 AI 批改进度。

### 2.8 AI 批改权益：`GET /aitutor/api/v1/front/equity/student/equity/info?projectId=8&subjectId=38`【实测】

- 返回 `aiCorrectNum`（**AI 批改剩余次数，实时准确**）、`lucaAskNum/teacherAskNum`、`aiCorrectAuth`（是否有权限）、`orderRecords[]`（每笔来源/次数/到期日）。
- 本账户实测：3 笔赠送共 1800 次、均到期 2028-08-31，跨 CPA 六科共享；成功批改 1 子题扣 1、失败/重复不扣。
- 另有 `equity/list?projectId=8&subjectId=38`（权益包）、`equity/check`（发起前校验，纯接口可省略）。
- **策略（用户拍板）**：不做余额预检/熔断，总结时顺带报剩余次数即可；交卷不耗权益，真用完也只影响主观 AI 即时判分、不影响“作业已交”，之后可补批。

### 2.9 其它已见接口（次要）

| 接口 | 方法 | 实测用途 |
|---|---|---|
| `student/paper-data-log/status?paperDataLogId=` | GET | 作答/交卷状态（questionTotal、score、paperSubmitStatus） |
| `one-key-correct/start` | POST | 整卷一键 AI 批改；本类卷 openAiCorrectStatus=0，**恒返 10462408，已证伪不用** |
| `question/extra` | POST | 收藏/错题/历年题 |
| `g-study/.../syllabus/glive/{id}` | GET | 课程大纲与 progress（见 2.1） |
| `ep-course/.../course/{courseId}` | GET | 课程详情，疑为 courseSyllabusId 来源【待验证】 |

### 2.10 只读探查接口（不建新实例、不写成绩）【2026-09-02 实测】

| 接口 | 方法/体 | 用途与注意 |
|---|---|---|
| `paper/analysis` | POST `{paperDataLogId, openEnergyToEquity:1}` | **交卷后整卷只读回看首选**。返回 `moduleList`（题面 + `questionAnswer` 标准答案 + `userAnswer` 我方作答 + 每题 `aiCorrect`：cpaBotType/configId/botId/correctStatus/corrects 采分维度）与顶层 `correctStatus/payCorrectStatus/paperCorrectStatus/paperReviewInfo`。判平台最优、逐题核对、取 aiCeiling 证据都用它。⚠ 其 `questionAnswer`、`userAnswer` 子对象也带同一个 `questionId`，递归定位"题节点"时必须加"该节点含 questionAnswer 字段"判断，否则会被子对象覆盖。 |
| `question/info/{qid}` | GET | 单题详情：type5 外壳、其下 `subQuestionList[0]` 为**同 qid** 的 type6 叶子（父子同 id 是接口固定包装，不代表 redo 两层嵌套）；`artificialIntelligence` 等标识多为 null，**不能用来分流**，分流只认 redo/analysis 的 `aiCorrect.cpaBotType`。 |

### 2.11 用户空间 / 我的课程清单：`GET /ep-course/api/v2/front/space/vcourse/pc`【实测，2026-09-07】

- **用途**：登录后"用户空间/我的课程"页的数据源，一次返回当前账号在各 project 下购买/开通的**全部课程**，是"开工前先盘点账号有哪些课、拿到各门课 saasCourseId"的入口（在调 2.1 syllabus 之前先调它）。无 query 参数、单接口全量、无分页。
- **来源域**：`origin/referer = https://glivepro.gaodun.com`，鉴权同 1.2（`authentication` JWT）。
- **响应结构**：`result.projectList[]`（项目，如 `{id:8,name:'CPA'}`）；`result.courseList` 是**以 projectId 为键**的对象（如 `courseList["8"]=[]`），每门课关键字段：

  | 字段 | 含义 |
  |---|---|
  | `id` / `vcourseId` | 购课实例 ID（听课/进度用） |
  | `saasCourseId` / `relationCourse` | **SaaS 课程 ID＝做题链路的 courseId**（syllabus/内容接口用） |
  | `subjectId` / `subjectName` | 科目 ID / 名（见 1.3） |
  | `wareStatus` | `"1"`=已开课、`"0"`=未开课（**26 考季会计正课=0，名师专业课-会计已开课，备料时注意区分**） |
  | `learnStatusDesc` / `leftDays` / `courseStartTime` / `courseExpireTime` | 学习状态 / 剩余天数 / 开课 / 到期 |
  | `currentStudyUrl` | 进入课程 URL，模式 `//glivepro.gaodun.com/course/{saasCourseId}/guide-course` |

- **本账号 2026-09-07 实测 8 门**（CPA 项目）：26 考季 VIPCPA 系列 税法(96834/42660)、会计(96760/42656)；名师专业课全科六科 税法50122/17247、会计50126/17244、战略50128/17249、审计50130/17245、财管50132/17246、经济法50124/17248（括号内 vcourseId/saasCourseId）。
- **采集脚本**：`node code/scripts/cdp/fetch_user_space_courses.js [--print]`（JWT 直连、可重复跑）；精简结构化台账落 `data/_workspace/_account/user-space/account_courses.json`（覆盖式、带 fetchedAt，不入库、不传网盘），当次原始响应留同目录 `user_space_vcourse_<ts>.json`。
- 同页伴随的只读接口：`ep-course/.../space/student/info`（student_id、item_done）、`space/student/exam-date?subjectIds=...`（考试日期）。

## 3. 纯接口做卷时序（实现蓝本 = gaodun_paper_core.doPaperViaApi）

1. **会话**：取 `authentication`（`findJwt` 按 mtime 取最新）；缺失或返回 553649434 时先 `refresh_auth_token.js` 自动从已登录 Chrome 重取，仅当 Chrome 也未登录/需验证码时才交用户，不读取密码。
2. **发现**：拉 syllabus，递归解析目标卷 `{csItemId,paperId,resourceId,title,num}`，用 `progress` 判完成度，排除冲刺模考。
3. **建实例**：record 取最近 logId；record 为 null 的首次卷先 create-paper 拿 logId → redo-paper 得题面与标准答案。
4. **平铺答案（buildUserAnswers）**：客观取 answer；type5 平铺 subQuestionList、以及顶层独立 type6，都作为 type6 项、userAnswer=canon(analysis)，type5 父题不提交；同时按每题 `aiCorrect.cpaBotType` 分流：=3 进 subjective（带该题 aiCfg、备 canon/qual/full 三版），=0 进 unsupported（答案照交、不批改）。
5. **拟人等待**：`dwellSec(项数,含主观)`，遇 10462203 +20s 重试。
6. **交卷**：submit-paper 一次性交全部答案；status!==0 判失败（交卷都没成功才走 UI 兜底）。
7. **主观 AI 批改（仅 cpaBotType=3 的 type6）**：并发=3、错峰发起；逐题 cpa（带 flag、来源域头、该题 aiCfg）→ 轮询 cs：2 完成 / 6 走「三级文本补全 → best-of-N 重取 → aiCeiling」补救链 / 1 超 75s 记 aiFailed / 11193401 归 unsupported / 11193404 读既有结果。
8. **回查与两层完成判据**：exam-report 核对。**fullScore（严格满分）**=userScore=totalScore 且 noCorrectAi=0 且 wrong 空 且所有子题 aiQuestionStatus=2（未配 AI 卷天然达不到）；**platformDone（平台最优）**=已交卷 + 客观全对（客观数以 build 的非 type6 项为准，顶层 type6 不算客观）+ 无 aiFailed + 配了 AI 的题全部 cs=2 或 aiCeiling；unsupported（未配 AI）与 aiCeiling（AI 判分上限）都不阻断。交卷成功但未达平台最优 → 标 submitted/aiPartial/aiFailed，不崩、不影响下一张。
9. **沉淀**：题面/选项/答案/解析/来源卷/抓取时间作为末期知识库来源（自动化错题除外）；不建重型题库，知识成型后中间数据可弃。

命令入口：单卷 `code/scripts/cdp/api_do_paper.js <paperId|标题关键字> [停留秒] [--no-ai]`；批量 `code/scripts/cdp/batch_redo_papers.js [--go] [paperId...] [--no-ai]`（默认 dry-run、硬排除冲刺）。

---

## 4. 题型 / 状态码 / 错误码速查

- **questionType**：1 单选、2 多选、5 计算/综合大题容器（不答）、6 主观自由文本（AI 批改；可套在 type5 下，也可顶层独立）；其余【待验证】。
- **aiCorrect.cpaBotType**：3=题库配了 CPA 批改机器人（才发 cpa、configId/botId 取该题值）；0=未配（cpa 必回 11193401、UI 无入口，答案照交不批改）。
- **cpa correctStatus**：1 批改中 / 2 完成满分 / 6 部分分（三级补全→best-of-N→aiCeiling）。
- **报告 aiQuestionStatus**：0 非AI / 1 待批 / 2 完成满分 / **3 平台未配 AI 不可批** / 6 部分；**userAnswerStatus**：0 未答 / 1 客观已判 / 2 大题容器 / 4 主观已交待批。
- **syllabus progress**：null 未做 / 2 做过未交 / 1 已交（完成）。
- **错误码**：10462203 作答太快；10462408 整卷一键批改不可用；10463001 redo 缺 paperDataLogId（首次卷要先 create-paper）；11193060 权限不足（未交卷/来源域错/body 缺 excelAnswer、openEnergyToEquity）；11193403 答案为空；11193404 已批过；**11193401 题目未配置评分标准（未配 AI，非失败）**。

---

## 5. 已验证边界 与 待验证清单

### 5.1 已实测成立

- 客观卷（知识点/课后/分章真题）：redo 进卷即回答案、明文无签名、纯接口满分，批量 20 张全满；
- **主观计算大题卷（type5/6）**：带答案交卷（uAns=4）→ 逐题 cpa（带 openEnergyToEquity:1）→ 分数回写，82749 实测 11/11、8 子题全 ai=2、UI 报告页同步满分；
- cs=6 部分分可用「等式+干净定性句」重发覆盖到 cs=2（1681680 实测计算 2/2+定性 1/1）；
- 课程完成判据 = 交卷成功（progress=1），与分数/主观是否后批解耦；
- AI 权益可实时查（aiCorrectNum），成功扣 1、失败不扣，额度充足、有效期至 2028-08；
- **首次作答路径**：record=null → create-paper 建实例 → redo，已在多张未做卷实测满分（与“已有实例直接 redo”统一进 core）；
- redo 副作用、固定题集不乱序、JWT 7 天、最小作答时长按墙钟判定。
- **【2026-09-02 全量清卷】基础卷 116 张全部达成：109 严格满分 + 7 平台最优**；73 张精讲客观卷纯接口一次满分零失败；强化主观卷验证了「顶层独立 type6」「按题 cpaBotType 分流」「并发=3 批改（多卷百+子题未触发风控）」「平台最优/AI 判分上限口径」。
- **平台未配 AI（cpaBotType=0）**：85912 等卷大量子题题库侧未配判分机器人，UI 也无入口/无教师，任何手段拿不到分；我方提交标准答案原文、归 unsupported，不阻断平台最优。
- **AI 判分上限（aiCeiling）**：个别题（1749889/1687633）提交内容逐字=标准答案、三级补全与 best-of-N×4 仍 cs=6，经 paper/analysis 逐字比对确认非我方问题，归 aiCeiling 视同完成。

### 5.2 待验证（扩样时验证，不臆断）

1. 判断/填空等 questionType 3/4 等的取值与提交格式（本批强化卷顶层均为 type6，未出现 3/4）；
2. canon/qual 提炼已在 82749、85912–85919 数百道主观子题扩样，绝大多数 cs=2，残余个别 cs=6 由 aiCeiling 兜底；
3. 48 题冲刺模考：是否仍走 redo、是否交卷前回答案、dwell 阈值——**所有基础作业完成后最后单独验证，当前坚决不碰**；
4. sourceFromType 是否跨课程恒定；courseSyllabusId(75181) 获取接口；submit 幂等；JWT 刷新接口；
5. 并发=3 已在多卷百+子题实测稳妥（未触发风控），更高并发的提速/风控比未压测（`opts.aiConcurrency` 可调）；直接 HTTP 与真实浏览器的风控差异仍按低频拟人控制。

---

## 6. 证据与相关物

- 原始报文（不入库）：`data/_workspace/<profile>/sniff/quiz_load_*.jsonl`、`submit_*.jsonl`、`schedule_*.jsonl`、`*sniff*.jsonl`（含 UI「帮我批改」真实 cpa 请求，证实 openEnergyToEquity）。
- 共享实现：`code/scripts/cdp/gaodun_paper_core.js`（buildUserAnswers / canon/qual/full 答案提炼 / doPaperViaApi）；入口 `api_do_paper.js`、`batch_redo_papers.js`；连接见 `connect_browser.js`（脚本索引见 [code/scripts/README.md](../../../code/scripts/README.md)）。
- 课程发现：`code/scripts/cdp/fetch_user_space_courses.js`（拉 vcourse/pc 全课程清单，台账 `data/_workspace/_account/user-space/account_courses.json`，见 2.11）。
- 2026-09-02 主观闭环侦查蓝本与响应快照留存于本机 `/tmp`（hw_empty_sub/hw_cpa_clean/hw_rest_clean/retry6/decisive/finish6 等，临时可弃）。
- 连接与抓包：[浏览器 CDP 连接手册](../tools/browser-cdp-connect-guide.md)；做题任务怎么执行（前置准备/枚举作业/批量与单卷/回查/异常分流/UI 兜底/知识反哺）：[做题/交卷任务执行指南](../guides/exam-workflow.md)。
