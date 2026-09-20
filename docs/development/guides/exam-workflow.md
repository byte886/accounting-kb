# 高顿做题/交卷任务执行指南（接口为主，UI 兜底）

> **文档类型**：Task（操作指南）
> **更新频率**：做题链路变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档说明"完成一批高顿作业"这个**任务怎么执行**：前置准备、枚举作业、跑接口主链路、回查、异常分流、UI 兜底、知识反哺。

**分工（不重复堆叠）**：

| 你想查的 | 看哪份 |
|----------|--------|
| 接口 URL / 字段 / 时序 / 错误码 / 已实测边界（契约） | [gaodun-exam-api.md](../api/gaodun-exam-api.md) |
| 通用 Web 交互（页面/标签管理、命令超时、session 异常） | [interaction-workflow.md](interaction-workflow.md) |
| 题/答/解析如何加工成知识库 | [knowledge-detail-build-sop.md](knowledge-detail-build-sop.md) |
| 在总流程第几步、冲刺模考前置条件 | [WORKFLOW.md 步骤5](../../WORKFLOW.md) |
| AI 判分抖动的原理与应对 | [flaky-ai-judging.md](flaky-ai-judging.md) |

> **2026-09-04 重定位说明**：做题链路已由 Playwright UI 点选改为**纯接口**（redo-paper 进卷即返回题面/标准答案/解析，见 ADR-010 与接口档案）。本文档据此重写：删除旧 UI 时代的"做题前查知识库 L1/L2/L3 分级、JS 点选 hack、错题加练、✓/AI 选错做题记录、错题补知识库"等内容；UI 操作仅作为接口失败时的**兜底最小集**保留在第七章。

---

## 一、结论先行：主链路是纯接口

**除登录外，发现作业 → 取题与标准答案 → 交卷 →（主观题）AI 批改冲满分 → 回查，全程 HTTP 接口完成，不做 UI 点选、不需要"先做一遍"、不依赖本地题库预置、做题前不需要查知识库猜答案。**

```
连接日常 Chrome(CDP，取 JWT)
  → refresh_inventory 只读刷新作业基线（syllabus + record 审计，判完成度）
  → batch_redo_papers 先 dry-run 再 --go：
       record（首次卷先 create-paper）→ redo-paper（题面+标准答案+解析）
       → 平铺 userAnswerList（客观取 answer；主观 type6 按 `pickSubjectiveCanon` 选 answer/analysis，保留分录排版）
       → 满足最小作答时长 → submit-paper 一次性交全卷
       → 仅主观：逐题 correct-ai/cpa，cs=6 三级补全/best-of-N/aiCeiling
       → exam-report 两层回查（fullScore / platformDone）
  → 结果落 batch_result_<日期>.json，单张失败不中断
```

**新旧链路根本区别（避免回退到旧做法）**：

| 维度 | 旧 UI 时代（已废弃） | 现在纯接口 |
|------|--------------------|-----------|
| 答案来源 | AI 查知识库/凭记忆点选，会选错 | redo-paper 直给标准答案，客观题必然对 |
| 做题前 | 逐题查知识库、L1/L2/L3 分级 | 不需要，直接取标准答案 |
| 稳定性 | 选择器/时序/跳题导致正确率波动 | 接口确定性，客观卷批量满分 |
| 错题 | 有"AI 选错"、错题加练、错题补知识库 | 无 AI 错题；非满分=需排查的异常，AI 错题不作知识来源 |
| 主观题 | UI 填答 | 答案来源选择器(answer 优先/analysis 兜底，保留分录排版)交卷 + 逐题 AI 批改 |

---

## 二、执行前准备

1. **登录态（唯一需要用户的环节）**：日常 Chrome 保持登录高顿。JWT 存于业务请求头 `authentication`，HS256、**声明有效期 7 天，但服务端可提前使其失效**（返回业务码 553649434「登录超时」，HTTP 仍 200，不能只看 JWT 的 exp）。token 获取分两级：① 常规由 `findJwt()` 从 `data/_workspace/_account/auth/*.jsonl` **按文件 mtime 取最新**；② 失效时 `node code/scripts/cdp/refresh_auth_token.js` 连接已登录的日常 Chrome、reload 高顿页自动抓新 token（批量脚本已内置：捕获 553649434 自动刷新并重试同一试卷，最多 2 次）。**只有日常 Chrome 也未登录/需验证码时才暂停交用户**，不读取密码。JWT/Cookie 禁止入库。
2. **连接自检**：`node code/scripts/cdp/connect_browser.js`（连接→列标签→断开）。连接通道与"允许远程调试"弹窗处理见 ADR-010 与 [浏览器 CDP 连接手册](../tools/browser-cdp-connect-guide.md)。
3. **刷新作业基线（只读，必做）**：`node code/scripts/cdp/refresh_inventory.js`（约1–2分钟，低频只读）。它拉 syllabus 枚举全部 paper、对每张只读 record 审计，产出：
   - `data/_workspace/<profile>/manifest/papers_inventory.json`（全量）
   - `data/_workspace/<profile>/manifest/papers_audit.json`（待做：非满分且非冲刺）
   - **作用：避免重复做已完成卷**，批量脚本以它为输入。
4. **确认范围**：只处理**可重做的基础卷**（知识点测试/课后练习/分章真题/强化专题）；标题含"冲刺模考"或 `num===48` 的卷被脚本硬排除，留到最后阶段（见第九章）。

---

## 三、枚举作业与完成判据

### 3.1 作业模式与顺序

知识点测试 / 课后练习 → 分章真题测 → 强化专题；**冲刺模考（3张48题）是特殊模式、所有基础作业完成后最后做**。

### 3.2 "作业完成"判据 = syllabus `progress`（不看分数）

| progress | record.paperSubmitStatus | 含义 | 处理 |
|----------|--------------------------|------|------|
| `null` | 无记录 | 从没做过 | 首次卷：create-paper 建实例再 redo |
| `2` | 0（未交卷） | 做过/暂存但没交 | **要补**：redo→submit 闭环 |
| `1` | 1（已交卷） | **已交＝课程进度完成** | 不再重复交；分数是否满走回查/只读复核 |

> 课程侧只认"是否成功交卷"；但本项目**作业目标是 100% 正确**，故 progress=1 但非满分的卷仍由 refresh_inventory 的只读 `paper/analysis` 复核、纳入 audit 补到满分/平台最优。

### 3.3 建目录阶段就要说清有无作业

每讲开工时即通过 syllabus/audit 说明本讲有几张卷、什么模式、完成状态，**不允许留到任务结束写"待确认"**；无作业的讲（如00开班）明确写"本讲无课后作业"。

---

## 四、执行做题（接口主链路）

### 4.1 批量（推荐）

```bash
node code/scripts/cdp/batch_redo_papers.js          # dry-run：只列出将处理的卷与停留，不写
node code/scripts/cdp/batch_redo_papers.js --go     # 实跑 audit 中全部待补基础卷
node code/scripts/cdp/batch_redo_papers.js --go 82174 82175   # 只跑指定 paperId
# 加 --no-ai：只交卷、不做交卷后主观 AI 批改（主观停在"待批改"，作业仍算已交）
```

- 默认 dry-run 是安全护栏，**先看清单确认无误再 `--go`**。
- 单张失败不中断其它卷；结果落 `data/_workspace/<profile>/papers/batch_result_<日期>.json`；卷间停 4s 低频拟人。
- **token 失效自愈**：批量过程中任一接口返回 553649434（登录超时），脚本自动调 `refresh_auth_token.js` 从已登录 Chrome 抓新 token，并用新 token 重试当前试卷（同一卷最多刷新 2 次）；2 次后仍失败才标记该卷异常、继续下一张。因此长跑期间 token 中途过期无需人工介入，前提是日常 Chrome 保持登录。
- **长跑必须套守护器，不要裸跑 `--go`**：`batch_redo_papers.js` 连续跑数十张后会「零错误静默退出」（进程消失、日志停在 `[N/M]`、无异常栈，caffeinate 也拦不住）。而 redo 不回写 audit，**直接重启会按启动时的旧 audit 从 `[1]` 重做已满分卷**，陷入"永远前几十张"的死循环。标准启动用做题守护启动器，它让守护器每一轮严格「先 `refresh_inventory` 从平台回查重建 audit（已满分自动剔除）→ 再 `--go` 只续跑剩余」，redo 一退出 5 秒后自动进入下一轮，PPID=1 脱离 AI 会话，无需 AI 在线或定时巡检：
  ```bash
  nohup bash code/scripts/cdp/run_papers_supervised.sh <profile> \
    > data/_workspace/<profile>/logs/supervisor_papers.log 2>&1 & disown
  ```
  全部达成（refresh 后 audit=0）或连续 3 轮平台已达成数不增长（个别卷客观无法满分）时写终态日志（`[NOTIFY]`）并退出。**做题线默认不弹 macOS 通知**（`SUPERVISE_NO_OSASCRIPT=1`），终态由 15 分钟定时任务唤醒 AI 识别、自动做终态核对/推进冲刺卷并在豆包通知；封装已套 `caffeinate -i` 防 Mac 空闲睡眠。三份日志分工：`supervisor_papers.log`（守护轮次/停滞/`[NOTIFY]` 终态）、`refresh_supervised.log`（每轮平台回查）、`batch_do_paper.log`（做题明细，追加）。

### 4.2 单卷

```bash
node code/scripts/cdp/api_do_paper.js <paperId 或 标题关键字> [最小停留秒] [--no-ai]
# 例：node code/scripts/cdp/api_do_paper.js 82749
```

退出码：**0=严格满分或平台最优**；4=已交卷但未达平台最优（可补批）；1/2=未交卷成功或异常。

### 4.3 题型分流（细节契约见接口档案 §2.3/2.6）

| 题型 | questionType | 答案来源与处理 |
|------|--------------|----------------|
| 单选 | 1 | 直接取 `questionAnswer.answer` |
| 多选 | 2 | 取 answer（形如 "A,B,D"，逗号无空格） |
| 大题容器 | 5 | **自身不答、不进 userAnswerList**，平铺其 subQuestionList；**子题按题型分流**：客观子题(t1/t2/t3)直接取 `answer` 选项字母，主观子题(t6)走下方答案来源选择器（2026-09-08 修复：旧逻辑一律当主观从 analysis 提炼文字，致大题下客观子题答错） |
| 主观小问 | 6 | **答案来源有 4 种形态**（2026-09-08 人工核查实锤）：①answer=选项/完整解、analysis=解析；②answer="无"、analysis=完整解；③answer=完整解、analysis="见答案/解析见答案"占位；④answer=完整解、analysis=仅思路点拨。**统一由 `pickSubjectiveCanon` 选择：answer 为实质内容则优先（保留会计分录换行/缩进排版），answer 为"无/见答案"占位才从 analysis 提炼；analysis 占位词绝不可当答案提交**。交卷后 AI 批改；可套在 type5 下、也可顶层独立 |
| 未配 AI 的主观 | `aiCorrect.cpaBotType===0` | UI 无"帮我批改"、cpa 必回 11193401；**答案照交、不批改、不计失败**（unsupported） |

- type5 子题**必须随交卷一起提交、绝不能留空**（留空则 AI 批改也不回写分数）；最终项数=questionTotal。
- 判断/填空等其它题型【待验证】：遇到先只读侦查、单独打通，不硬闯（见第六章出口②）。

### 4.3.2 answerMode=5 表格作答题（Excel/Luckysheet；机制已逆向，待实现）

> 2026-09-08 从做题前端源码逆向定稿（会计课因账号风控未做线上实测）；后续课程遇到表格填空类主观题按此实现，**先单卷验证再批量**。

- **前端形态**：做题页是独立 qiankun 子应用 `sub-tiku.gaodun.com`（主应用只做容器，业务 bundle 为其 `static/js/index.*.js`）；题面 questionItem 带 `answerMode=5` 与空白模板 `excelAnswerContent`——后者本身就是 Luckysheet sheet 数组的 JSON 字符串。
- **双字段缺一不可**（前端 onChange/提交契约）：这类题每题提交项同时含
  - `userAnswer`：表格旁的文字解答（计算过程+会计分录），来源与普通 type6 主观题相同（`pickSubjectiveCanon`，保留分录换行/缩进排版）；
  - `excelAnswer`：**`JSON.stringify(luckysheet.getAllSheets())`**，即在 `excelAnswerContent` 模板上把最终数值填进对应格子后的完整 sheet 数组（与模板同结构）；`excelAnswer` 非空即算"已作答"。
- **纯接口实现路径**：`gaodun_paper_core.js` 的 `pushSubjectiveLeaf` 对 answerMode=5 题，除 userAnswer 外要补 `excelAnswer`——解析 excelAnswerContent 得到空白 celldata 坐标，把标准答案数值回填后 `JSON.stringify`。
- **卡点（不可臆造）**：标准答案 `answer` 末尾的目标表格常是 `<img>` 截图（非结构化），需视觉/OCR 判定"哪个格子填什么值"；无法可靠映射坐标时，只交文字 userAnswer 并显式标记，**不要编表格坐标**。
- 样例：会计课 85425 14-1（qid=1955394）；逆向细节与字段出处见 `data/_workspace/cpa-accounting-2026/tickets/BUG_BACKLOG.md` 关联观察。

### 4.3.1 主观题答案生成与完整性校验门（2026-09-06 第二次重构定稿）

> **铁律：答案要像"会做题的人写的"——正式算式/结论为主体、判定法理精简为「依据：」、多小问逐行分点；先保证与官方解析一致且覆盖每一小问，再谈 AI 判分。有解析的题不能写错、写漏，也不能把教辅解析整段照抄堆砌。**

**两段历史教训（都曾实锤翻车）**：
1. *多小问截断（09-05）*：顶层独立 type6 解析形态为 `(1)(2)【点拨】…(3)…【点拨】…(4)`，旧 `canonAnswer` 用 `split('【点拨】')[0]` 会把点拨之后的 (3)(4) 正式小问整段丢弃；
2. *点拨照抄堆砌（09-06）*：旧 `judgeAnswer` 把【点拨】整段（含①②政策科普）塞进交卷/AI 批改答案，答案被教辅背景淹没、不像作答。

**关键证据（09-06 六卷列联表 + 对照实验，推翻"点拨导致 0 分、应全删"的直觉）**：

| 维度 | 数据 | 结论 |
|---|---|---|
| 含【点拨】题 | 9 道里满分 8（89%） | 点拨**不是** 0 分元凶 |
| 无点拨题 | 6 道里满分 4，1681714/1681715 逐字=标准答案仍 0 | 纯算式也会被平台误判 |
| 1681705 | 逐字/语境/分步/干净结构化 **4 种表述全 0** | 平台对特定题稳定误判 |
| 1681735 | **同一答案逐字相同**，s2 试卷判满分、m2 机考判 0 | 平台 AI **跨实例随机波动**，与答案无关 |

→ 8 道满分题的采分点恰恰藏在【点拨】里（如"管理不善属非正常损失应进项转出""鸭蛋 50% 流通环节免税"），**整段删点拨会丢采分点**；但政策科普堆砌也不可取。

**定稿机制（`gaodun_paper_core.js`，交卷答案与 correct-ai 首次批改答案同一版）**：

| 步骤 | 函数 | 作用 |
|------|------|------|
| ① 数题干要求几问 | `countAskedSubs(title)` | 取「要求/根据上述资料」之后连续序号 1..N，避开「业务（4）」「硫酸雾（100）」噪声 |
| ② 切小问块 | `splitAskedBlocks(t,N)` | 正式序号位置严格递增切块，自动跳过点拨内部噪声括号；切不齐整段兜底，绝不丢小问 |
| ③ 统一生成答案 | `cleanSubjectiveAnswer(analysis,N)` | 每小问=正式答案（主体）+「依据：」+精简后的点拨判定；多小问 `(1)..(N)` 逐行分点 |
| ④ 点拨保守精简 | `pruneBasis` | 去①-⑩条目编号；只删「20XX 年取消/调整…政策」纯背景句；**本题判定/法理/公式一律保留**（采分点） |
| ⑤ 完整性校验门 | `coveredSubs`+`answerGaps` | 提交前比对 1..N 覆盖，缺则放大序号重切、仍缺整段兜底并显式记录，**禁止静默漏答** |
| ⑥ cs=6 逐级补全 | `correctSubjective` | 部分得分时才用 `qual`/`full`（整段解析）/AI 未命中点逐级补，首次不送含点拨全文 |

> 旧 `canonAnswer`（仅 refresh_inventory 清单摘要仍用）、`judgeAnswer`/`multiSubAnswer`（主路径已停用，保留避免连锁）不要再用于交卷与 AI 批改。

**2026-09-08 第三次重构（答案来源选择器 + 排版保留 + 判满口徑，人工核查 6 问触发）**：

| 修复项 | 函数/位置 | 规则 |
|--------|----------|------|
| 答案来源选择器 | `pickSubjectiveCanon(qa,N)` | answer 为实质内容（非"无/见答案/解析见答案/略"占位）则**优先用 answer**（官方标准答案、常带会计分录原始排版）；answer 占位才 `cleanSubjectiveAnswer(analysis,N)`；两者都占位时兜底并标记，**绝不把"见答案"三字当答案提交**（旧逻辑无脑优先 analysis，致 82348 Q31 交了"见答案"） |
| 保留排版渲染 | `htmlToTextKeepLayout` | `<br>/<p>/<div>` 转换行、`&nbsp;` 转空格、**保留制表符与行首缩进**（借/贷、金额对齐）；与 `stripHtml`（折叠所有空白）的区别是分录题必须用它，否则平台 AI 无法按"借/贷"逐笔识别（实测 85418 2-2 题 5 笔全 0 分，修复后 3.5/3.5 满分）。**br 正则必须匹配带属性形式 `<br class="markdown-return"/>`（平台标准答案主流换行标签，用 `<br\b[^>]*>` 而非 `<br\s*/?>`），否则段内借贷仍被压成一行、分录判分模块 0 分（2026-09-08 实锤 85425 14-2、82357，16 张平台最优卷 130 个分录失分采分点中 87 个源于此）** |
| 占位判断 | `isPlaceholderAnswerText` | 去小问序号、标点、空白后只剩"无/略/见答案/解析见答案"等词即判占位；`cleanSubjectiveAnswer` 空块或只剩顿号的块补"略"（官方"（1）、（2）略"合并略写被切开时不输出空序号） |
| t5 子题分流 | `buildUserAnswers` | 大题容器下的子题**按 sub.questionType 分流**：t6 走主观选择器，t1/t2/t3 客观直接用 `answer` 字母并加非空防呆断言（旧逻辑一律当主观，致 82344 Q27/Q29 客观子题交了解析文字） |
| cs=6 补全回退 | `pushSubjectiveLeaf`→base | `qual`/`full` 取自 analysis，若为占位则回退 `canon`，避免部分得分重发时发"见答案"垃圾文本 |
| 判满口徑 | `refresh_inventory.inspectSubmitted` | **已交卷一律 `paper/analysis` 逐题判**：客观逐题拿满 + 配AI主观 cs=2/判分上限 + 未配AI忽略；best 即"到顶"，再按有无未配AI/判分上限区分真满分与平台最优。**禁止用 `score>=questionTotal` 判满分**（score 是得分、questionTotal 是题数，量纲不同，百分制卷 80>=5 恒真会把错题卷误判满分并冻结永不再刷——实锤 82337 判"满分"实际只有 16 分） |

**判读口径**：
- `answerGaps=[]` 是答案完整性的**硬验收线**，非空即有题漏小问、必须排查，不能宣布完成；
- `cpaBotType===0`：答案完整提交但平台不配 AI（须人工批改权益、本账户不买），分数不涨是平台限制、不是答案问题；
- `cpaBotType===3` 但 correct-ai 回 `11193401`：以接口实际为准归 unsupported，不重试；
- **三类"非满分"严格区分，不能混为一谈**：
  1. *答案残缺/写错*＝我方 bug，改 `cleanSubjectiveAnswer`/校验门；
  2. *平台稳定误判*（多种表述都 0）＝归 `aiCeiling`，只能人工批改，不重赌；
  3. *平台跨实例波动*（同答案另一卷满分）＝同样归 `aiCeiling`，**不要整卷重做赌分**（record 只留最新，可能越赌越低）；
- 免费 AI 通道存在 ±1 分随机波动，6 卷成绩小幅不一致属正常，以"客观全对 + answerGaps=0 + 答案逐题核对正确"为质量线，不追求 AI 分数每次完全一致。

### 4.4 拟人与风控（脚本已内置，了解即可）

- **最小作答时长按 redo→submit 墙钟判定、与 body.costTime 无关**；太快被拒 `10462203`，脚本自动 +20s 重试。安全值 `max(20, 项数*1.5 向上取整到5s, 含主观保底25s)`。
- AI 批改并发=3、发起前错峰 120ms；全程低频拟人，不压测高并发。
- 全链路明文 JSON、**无 sign/nonce/加密 body**，无需逆向前端（做题 UI 本体在独立子应用 `sub-tiku.gaodun.com`，逆向前端题型组件时去那里找）。
- **账号级风控 `10462222`「做题行为异常，请联系学管师」**：短时间大量 redo 后可能触发，**与单卷 / times / 章节无关——redo 写操作全账号被拒**（2026-09-08 满分 t1、平台最优 t1、对照卷三类实测 redo 全拦），只读 record/analysis 不受影响。冷却时长未知；期间**禁止一切 redo/submit 探测，也不要让守护器空转重试**（只会加重）。是否停止/恢复做题以用户明确指令为准；恢复前先用单张只读 record + 一次 redo 探测确认不再回 10462222。
- **卷间节奏分时段自适应（`batch_ep3_papers.js` 内置，2026-09-10）**：单卷内 dwell 是平台硬墙（见上），卷间停顿才是拟人关键——交卷即开下一卷的固定 500ms 过于机械。现按本地时间切换：**白天 6:00–24:00 拟人慢节奏**（卷间随机 6–15s，每 8–12 张插一次 40–90s 长休息）；**夜间 0:00–6:00 恢复快节奏**（卷间 1–3s、不长休息，窗口起止由 `NIGHT_START_HOUR/NIGHT_END_HOUR` 调）。进程跨时段长跑时每次停顿实时判时，不靠启动时一次性判断。多科目并行时**错峰启动**（如审计立即、财管延后 90s），避免两个账号会话同一刻并发提交。改节奏参数后必须重启做题进程才生效。

### 4.5 AI 批改权益（用户已拍板策略）

- 成功批改 1 个主观子题扣 1 次、失败/重复不扣；`equity/info` 可实时查 `aiCorrectNum`。
- **不做余额预检/熔断**：交卷不耗权益，真用完也只影响主观即时判分、不影响"作业已交"，之后可补批；任务总结顺带报一次剩余次数即可。

---

## 五、回查与完成判据（两层，脚本自动做）

> **回查查的是"提交是否被平台正确结算"（技术闭环），不是"答案对不对"。** 答案直接取自 redo 接口返回的标准答案、提交即标准，无需再验证正确性；因此出现非满分不代表"答错"，而是漏交某题、主观题留空 / AI 批改未跑完、新题型未覆盖等**技术异常**，一律按异常排查分流（见第七章），不存在"猜答案→验证对错→补知识"这回事。

交卷后 `exam-report` 回查（字段字典见接口档案 §2.7）：

| 判据 | 条件 | 含义 |
|------|------|------|
| **fullScore 严格满分** | userScore=totalScore 且 noCorrectAiQuestionScore=0 且 wrongQuestionIds 空 且所有子题 aiQuestionStatus=2 | 最理想 |
| **platformDone 平台最优** | 已交卷 + 客观全对 + 无 aiFailed + 配了 AI 的题全 cs=2 或 aiCeiling | **视同完成**（未配 AI、AI 判分上限不阻断） |

- `aiCeiling`：我方提交内容归一化后就是标准答案、三级补全与 best-of-N×4 仍 cs=6，经 paper/analysis 逐字比对确认非我方问题，归 AI 判分上限、视同平台最优（依据见 flaky-ai-judging）。
- **作业目标 100%**：非满分且不属于 unsupported/aiCeiling 的，视为需排查异常，记录原因，不允许默默放过。
- **refresh 判满口徑（2026-09-08 修复）**：`refresh_inventory` 对已交卷**一律走 `paper/analysis` 逐题判**（客观逐题拿满 + 配AI主观 cs=2/判分上限 + 未配AI忽略），best 即到顶，再按有无未配AI/判分上限区分真满分与平台最优。**绝对禁止用 `record.score >= record.questionTotal` 判满分**——score 是得分、questionTotal 是题数，量纲不同，百分制卷恒真会把错题卷误判满分并冻结永不再刷（实锤 82337 判"满分"实际 16 分、82339 判"满分"实际 10.25 分）。
- **cs=3 / cs=1 归平台最优（2026-09-08 补充）**：配了 AI(cpaBotType=3) 但 `correctStatus=3`（AI 批改返回空结果，pointList/corrects 全空、已耗权益，实锤 82337 Q1757524）或 `correctStatus=1`（批改中/多次重做仍不出分）均属**平台侧不出分，非答案错误**，归 aiCeiling/平台最优，不纳入 bad、不触发重刷。
- **禁止为刷满分反复重刷同一批卷（2026-09-08 风控教训）**：短时间内对同一批卷反复 redo 会触发平台 `10462222 做题行为异常，请联系学管师` 风控拦截，所有 redo 被拒。主观题（AI 评判/人工评判）**做到答案质量到位即可，不强制刷满分**——符合 ADR-014"不追求刷满分、知识覆盖优先"。守护器连续 3 轮进度无变化会自动退出，不空转重试。

---

## 六、异常三出口（不做常规双轨）

| 情形 | 处理 |
|------|------|
| ① token 失效（553649434）但 Chrome 仍登录 | 脚本自动 `refresh_auth_token.js` 刷新并重试（最多 2 次），不交用户 |
| ①' Chrome 也未登录 / 需验证码 | **立即暂停交用户**，不自行试探、不读取密码 |
| ② 没见过的卷型/题型/报错 | 不硬闯、不交正式卷；先用只读基线脚本（`refresh_inventory.js` 刷新作业基线、`collect_paper_sources.js` 只读补采题源）定位，发起针对性测试或功能迭代，打通再纳入主链路 |
| ③ 接口链路失败（连 submit 都没成功） | 降级 **第七章 UI 兜底**，保证"作业最终交得上"，并记录降级原因 |

- 批量中单张异常按上表分流、标状态后继续下一张，不被一张卡死。
- 验证顺序固定：**只读接口重放 → 可重做/练习卷试提交 → 正式作业**，全程低频拟人。

> **判定「token 失效」前先自查（先验概率原则，详见 [问题排查方法论 §一.9](debugging-and-collaboration.md)）**：约 10 天运行统计，做题失败九成以上是自身问题——端点/域用错（做题走 `minerva`，不是 `g-study`）、参数或 courseId 张冠李戴（别拿税法课 42660 的 token 会话去跑会计课 42656）、`findJwt` 文件选取逻辑、最近代码改动。**只有真实只读请求明确返回 553649434 才算 token 失效**，不能凭「请求失败/连续报错/JWT 快到 exp」就推断并交用户登录；走完出口①的自动刷新仍失败、且排除了自身问题，才走①'交用户。

---

## 七、UI 兜底最小操作集（仅第六章出口③时用）

> 仅当纯接口无法完成交卷时才回到 UI；能用接口就不用 UI。通用页面/标签管理、session 异常、命令超时分级处理见 [interaction-workflow.md](interaction-workflow.md)，本章只列做题动作要点。连接技术栈按 ADR-010（CDP 为主、Playwright 扩展为备）。

1. **优先在未完成卷页面操作**：URL 中 `resState/0`=未完成、`resState/1`=已完成；同一卷可能两个标签并存，选 resState/0。
2. **单选题**：选中选项后通常**自动跳题**；没跳先检查答题卡是否遮挡（点页面空白处关闭）。
3. **多选题**：选中后**不自动跳题**，需手动点"下一题"；各选项点击间隔 ≥1000ms，每次点击后确认选中态再点下一个。
4. **补题走答题卡、禁止从头依次重做**：交卷前打开答题卡逐题检查，发现未做题从答题卡**单独挑出**作答（从头重做会把已选反向取消）；补完再次确认答题卡全做完。
5. **交卷确认**：有未做题时弹窗"还有X题未做"→选"继续做题"返回补；确认全做完再"交卷→确认交卷"。时间到弹窗则直接"立即交卷"。
6. **命令拆分**：单个命令只做一道题/少量动作，避免 sleep 堆叠导致命令超时被转入后台；动作后用页面状态（题号变化/选中态）验证，不盲点。
7. **取解析**：交卷后错题/逐题解析优先用只读接口 `paper/analysis`，而非 UI 逐屏翻。

> 已删除的旧 UI 做法（勿恢复）：做题前逐题查知识库与 L1/L2/L3 分级、固定 JS 文本匹配点选 hack、"错题加练"循环、✓/AI选错标记的做题记录、把 AI 错题补进知识库。

---

## 八、知识反哺（做题产出 → 知识库）

1. **只读采集题源**：`node code/scripts/cdp/collect_paper_sources.js [--all] [paperId...]`，对已交卷卷经 record→paper/analysis 只读拉取题面/选项/标准答案/官方解析/知识点标签，落：
   - `data/_workspace/<profile>/papers/<paperId>.json`（每卷精简题答解析）
   - `data/_workspace/<profile>/manifest/paper_index.json`（paperId→章/标题/题量/文件，`chapter`=官方讲次标题）
   - 纯只读、不 redo、不建实例、不交卷、不耗 AI 权益。
2. **加工成知识库**：按 [knowledge-detail-build-sop.md](knowledge-detail-build-sop.md)，用 paper_index / manifest 定位知识点对应的全部卷、脚本按知识点聚合题量定高频、官方解析逐题校验知识拆解（主观题下钻小问）；来源口径与冲突优先级见 [knowledge-base-sources.md](../knowledge/knowledge-base-sources.md)。
3. **AI 错题不作来源**：自动化过程中因旧 UI BUG 产生的"AI 选错"不是知识，不写入知识库；"发现漏洞"由题/答/官方解析承担。

---

## 九、冲刺模考（特殊分支，所有基础作业完成后进行）

### 9.1 定位与现状
- **前置**：所有讲座视频、讲义、基础作业（100%）完成后才进入；冲刺是与基础作业并列的一条分支，不是同步飞书之后的步骤。
- 每"套"冲刺含三类对象：**试卷**（origin=glivepro）、**机考**（origin=mock-cpa，paperType=109，题目与对应试卷相同）、**课后整卷视频解析**。26 税法考季共 3 套 = 6 卷 + 3 整卷视频。
- 试卷/机考同样走接口主链路（redo 取题、submit 交卷），已全部跑通；主观答案与平台 AI 判分边界见 §4.3.1 与 [flaky-ai-judging.md](flaky-ai-judging.md)。

### 9.2 冲刺的三类知识源与分流
| 知识源 | 获取方式 | 加密 | 内容定位（分流） |
|---|---|---|---|
| 试卷/机考 题面+标准答案+解析 | `collect_paper_sources.js`（只读） | 无 | 题答解析、知识点 |
| 整卷视频解析（126 分钟级串讲） | `fetch_sprint_video.js` | encrypt=0 不加密 | 考点串讲 → 知识拆解 |
| **题目级讲解视频**（按大题，18–42 分钟/个） | 见 9.3 | **encrypt=1 AES-128** | "这道大题怎么一步步解" → 做题思路/题答解析 |

### 9.3 题目级讲解视频抓取 SOP（加密，三段式）
**事实（2026-09-06 CDP 侦查实证）**
- vid 挂在子题 `questionAnswer.questionVideo.vid`，**按 type5 综合大题聚合**（一道大题一个 vid，其下子题共用）；解析页 URL 的 `cs_item_id/resource_id` 从 `syllabus_full.json` 取（每卷 `resourceIds[0]` = 试卷解析页 resource_id），答题卡入口是大题主序号"N-1"（普通题与大题父级各占一个主序号，子题不占）。
- m3u8 为标准 HLS AES-128，分片在 glive2-video-resource。**key 不直接下发**：`replay/authorize` 直连返 40301、带 cookie fetch 报登录超时；播放器 sub-study-player 用 wasm 把 authorize 的 108B 加密包解成 16B key，明文只存在于 Worker 内存。
- **key 是视频级固定值**（同 vid 跨会话抓取一致），故只需 CDP 抓一次，之后全部离线。

**三段式流程**
1. **抓 key（唯一需要 Chrome 的一步，一次性）**
   `node code/scripts/cdp/fetch_question_video_keys.js`
   CDP 打开逐题解析页→全部解析→对每个大题：开答题卡点"N-1"→点 `.sub-tiku__video-box img` 封面加载播放器→注入 Worker hook（hook `postMessage`，从 `to_worker` 的 `response` 取前 16B ASCII 即 key）→落 `data/_workspace/<profile>/papers/qvideo_keys.json`。
2. **下载解密（纯 Node，可并发/断点重跑，不再依赖浏览器）**
   `node code/scripts/cdp/download_question_videos.js all`
   JWT 取 **SD** m3u8（转写对分辨率不敏感，SD 又快又小；要高清改 res=FHD 需播放器切档另抓 key）→解析全局 IV→并发下载→逐片 `AES-128-CBC` 解密（校验首字节 0x47=MPEG-TS 同步字节）→顺序合并 merged.ts。**完成后必须 ffprobe 校验时长 == 接口 duration**。
3. **remux + 并发转写**
   `ffmpeg -i merged.ts -c copy -bsf:a aac_adtstoasc video.mp4`（TS→MP4 必须带 aac_adtstoasc），再 `bash code/scripts/transcribe_qvideos.sh 6`（FunASR，本机约 20x 实时、单进程约 2 核 3.3G，20 逻辑核默认并发 6）。
4. **归置到课程目录两层桶（下载只是到工作区 data/_workspace/<profile>/tmp/download/sprint-videos，成品必须归位）**
   成品三件套（video.mp4 + transcript.md/json）移入课程目录 `原始资源/videos/`，延续正课 `NN_讲次/` 扁平范式、正课已到 39，冲刺顺延：40–42 为三套整卷视频解析、43–49 为题目级大题讲解（`43_冲刺模考01-题目讲解-卷烟厂消费税` 等，大题中文名取 redo 题面）；6 卷题答在分流阶段从 redo 精简为 `原始资源/papers/`。归位后 data/_workspace/<profile>/tmp/download/sprint-videos 的 `.vfetch`（merged.ts+分片，可由脚本重下）移废纸篓。**网盘不在此步传**：按 [finalize-sop.md](finalize-sop.md)，等知识详解生成自检通过后随"原始资源+知识详解"整层一次性镜像。

### 9.4 踩坑（macOS）
- **无 `flock`、无 `timeout`**：并发队列互斥锁不能用 flock（会静默失效、多 worker 重复抢同一任务），改用 `mkdir` 原子锁（见 transcribe_qvideos.sh / transcribe_parallel.sh）；限时等待用 node `setTimeout` 或后台任务，不用 timeout。
- 抓 key 必须在 `evaluateOnNewDocument` 注入 hook（晚于播放器创建就 hook 不到 Worker）；切下一大题前以注入后 `__wd` 长度为基线，只取本次新增消息，避免串 vid。

---

## 十、做题任务检查清单（接口版）

**执行前**
- [ ] 日常 Chrome 已登录、connect_browser 自检通过、JWT 经一次只读请求验活有效（失效先自动 refresh，仅 Chrome 未登录才交用户）
- [ ] 已跑 refresh_inventory，audit 清单与实际一致、已排除冲刺模考
- [ ] 批量先 dry-run 确认待做卷清单

**执行中**
- [ ] 首次卷走 create-paper；每张 redo 后紧跟 submit 闭环、不中途中断
- [ ] type5 父题不答、其 type6 子题与顶层独立 type6 全部平铺、无留空，项数=questionTotal
- [ ] 满足最小作答时长；低频拟人、AI 并发≤3
- [ ] 主观题按 cpaBotType 分流（=3 批改、=0 只交不批）；cs=6 走补全链、残余归 aiCeiling

**回查**
- [ ] 每张达到 fullScore 或 platformDone；非满分异常已记录原因并分流
- [ ] batch_result 与 audit 状态一致，无遗漏卷
- [ ] 题源经 collect_paper_sources 落 papers/ 与 paper_index，供知识生成
- [ ] 未把 AI 错题当知识；冲刺模考未被提前处理

---

**文档维护**：接口契约/字段/错误码变更改 gaodun-exam-api.md；通用交互变更改 interaction-workflow.md；本文件只维护"做题任务怎么执行、怎么分流、怎么兜底"。
