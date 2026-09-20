# 第三方 / AI 判分不确定性应对方法论（Flaky AI Judging）

> 适用场景：自动化流程中调用**外部 AI/LLM 做打分、判定、审核、批改**，而结果出现"同一份输入、多次结果不一致 / 标准答案仍被判错"时的识别、重试与完成口径设计。
> 本项目落点：高顿 CPA 主观题 `correct-ai/cpa` 批改；但方法可迁移到任何 LLM-as-judge / 第三方智能审核环节。
> 最近沉淀：2026-09-02（基础卷清盘阶段，攻克 AI 批改 cs=6 顽固题）。

---

## 1. 先认清：这是系统性现象，不是个例 bug

LLM 判分（LLM-as-a-judge）存在**固有非确定性**，并有公开研究与业界数据支撑：

- 即使 `temperature=0`（最确定解码），同一输入重复评分仍显著不一致，且**"完整性 / 语义类"判据波动最大**（arXiv《Same Input, Different Scores》）。
- 可靠性随重复次数非线性提升，有研究测得平均要约 11 次重复、多数表决才能以 95% 概率复现稳定结论（arXiv《The Coin Flip Judge?》）。
- 业界统计约 93% 用 LLM 判分的团队遇到可靠性问题，典型表现是"代码和输入都没变，同一对象两次分数差很多"（Galileo 等工程博客）。
- 常见偏差：prompt/context 敏感、长度偏见、位置偏见、版本漂移（Microsoft LLM-scoring 白皮书）。

**结论**：遇到"标准答案都发了还判不满 / 同文不同分"，第一反应不应是"我答案写错了"，而要按下面流程**先证实/证伪是不是判分侧抖动**，再决定投入。

> 证据分级：上述为「学术论文 / 厂商白皮书 / 社区实践」，非本平台官方文档；本项目自身结论均标注【实测】并可在 `data/_workspace/<profile>/sniff` 快照复算。

---

## 2. 识别：三步区分"我方问题"与"判分上限"

| 步骤 | 动作 | 判读 |
|---|---|---|
| ① 逐字比对 | 拉只读回看接口（本项目 `paper/analysis`），把 `userAnswer.我方提交` 与 `questionAnswer.analysis 标准答案` 去 HTML / 序号 / 标点后**逐字对比** | 不一致 → 我方提炼丢内容，先改答案提炼；**逐字一致仍判错 → 进入②** |
| ② 看判分维度 | 展开 `corrects[].correctText.correctPointList`，看每个采分点 `showStatus`（1 命中 / 其它未命中）与其参考答案 | 答案里明明包含该参考点却 show2 = 语义漏判；未命中点**参考答案为空** = 模型动态生成、无文本可补 |
| ③ 重复采样 | 同一实例原样重交 N 次 + 必要时跨实例观察 | 同实例 N 次结果都一样 = **稳定漏判**（再重交无用，别烧资源）；时好时坏 = **随机抖动**（best-of-N 有价值） |

本项目实测：1749889 跨实例一次命中、一次全灭（存在抖动），但同一实例内连续重交 4 次全为 cs=6（稳定）；1687633 答案逐字含全部采分点，仍稳定判部分分。

---

## 3. 应对层级（决策树，从便宜到昂贵）

```
cs=6 / 未判满
  │
  ├─ 层级1 排除我方问题：换答案形态重发（不额外依赖随机性）
  │    ① canon+qual（结论句 + 干净定性句）
  │    ② full（标准答案整段原文）
  │    ③ 用判分接口自己给出的"未命中参考点"定向拼补（用对方的判据补，最有的放矢）
  │    → 任一步判满即停
  │
  ├─ 层级2 best-of-N 有限重取（对冲随机抖动）
  │    原样重交标准答案，最多 N 次（本项目 AI_CS6_RERUN=4），碰到一次成功即停
  │    前提：操作幂等（见第4节）；每次都有成本（本项目=1次批改权益），必须设上限
  │
  └─ 层级3 判分上限 aiCeiling（不卡死流程）
       N 次后仍失败、且层级1证实"我方提交=标准答案原文"→ 单独立桶 aiCeiling：
       内容层面判定完成，显示分受第三方能力限制，记录证据、不阻断主流程
```

**关键取舍**：
- best-of-N 只对"随机抖动"有效；对"同实例稳定漏判"（步骤③判定）应**及早熔断**，避免对每张卷的每道难题无意义重烧额度。
- 我们不是在"猜答案"——标准答案已知且正确，所以用 **best-of-N 取最优**（碰到一次判满即停）比学术上的"多数表决"更省、目标更明确；多数表决适用于"答案本身也要靠模型产生"的场景。

---

## 4. 工程铁律：重试之前先确认幂等

外部调用重试的第一原则是**幂等性**（AWS / Microsoft WAF / RFC 9110 一致建议）：

1. **只对幂等操作自动重试**：重复调用不产生额外副作用。本项目 cpa 对同一 `paperDataLogId+itemId` 重发是**覆盖该题判分记录**（cs=6 可覆盖、已判满返回 11193404），不新建答卷、不重复交卷，近似幂等；唯一成本是成功批改扣 1 权益。
2. **非幂等 POST（创建订单/提交/扣款类）不能裸重试**，要带幂等键（idempotency key）或先查询上一次是否已生效，否则会重复创建。
3. **区分错误类型再决定是否重试**：瞬时错误（超时 / 429 / 5xx，配合指数退避 + 抖动、尊重 `Retry-After`）可重试；确定性业务拒绝（如本项目 11193401 未配评分标准、11193403 答案空）重试无意义，直接分流。
4. **重试预算与错峰**：设最大次数与总预算；并发场景错峰发起（本项目 `idx*120ms`、并发=3），避免重试风暴。
5. **异常 body 会把状态打成永久挂起**：本项目漏带 `openEnergyToEquity` 会让该题停在 cs=1"批改中"且重发救不活、只能重建实例——**重试必须用与成功请求完全一致的契约，不能拿残缺 body 试**。

---

## 5. 完成口径：把"内容正确"与"第三方显示分"解耦

当第三方判分不代表事实正确性时，完成判据要分两层（本项目用户已拍板）：

- **fullScore（严格满分）**：第三方显示分 = 满分，所有子题都判满。
- **platformDone（平台最优）**：我方应做的全部做到——已成功提交、客观全对、所有"平台有能力判的"都判满；失分**只可能**来自平台自身能力边界，且每种都要有证据：
  - `unsupported`：平台压根没配判分能力（`cpaBotType=0`、UI 无入口）；
  - `aiCeiling`：配了判分但模型对标准答案仍稳定判不满（经第 2 节逐字比对 + 重取证实）。
- **放行 aiCeiling 必须带"答案≈标准答案"的强校验**（归一化去空白/标点后包含比对 + 最短长度阈值），防止把"真答错"误判成"判分上限"而放水。审计侧（`refresh_inventory.inspectSubmitted`）用同一套校验，保证基线不是自说自话。

> 通用原则：**自动化系统对"自己产出的内容正确性"负责到底，对"第三方黑盒给的显示分"只做如实记录与分类，不被其抖动卡死，也不拿它当放水借口。**

---

## 6. 本项目落地映射

| 位置 | 内容 |
|---|---|
| `code/scripts/cdp/gaodun_paper_core.js` | `correctSubjective`：三级文本补全 → best-of-N（`AI_CS6_RERUN`）→ `out.aiCeiling`；`buildUserAnswers` 按 `cpaBotType` 分 subjective/unsupported；`doPaperViaApi` 两层完成判据 fullScore/platformDone；并发 `AI_CONCURRENCY=3` + `mapLimit` 错峰 |
| `code/scripts/cdp/refresh_inventory.js` | `inspectSubmitted` 只读复核：cs=6 且"我方答案≈标准答案"才计 ceiling，否则仍算真·非满分 |
| `code/scripts/cdp/batch_redo_papers.js` / `api_do_paper.js` | 透传 aiCeiling、三态标签（✅满分 / 🟡平台最优 / ⏺未满分），ok=fullScore||platformDone |
| 接口细节 | 见 [gaodun-exam-api.md](../api/gaodun-exam-api.md) §2.6/§2.10/§5 |

---

## 7. 参考来源（外部，供进一步调研；链接可能随时间失效，以标题检索为准）

- arXiv 2603.04417 *Same Input, Different Scores: A Multi-Model Study on the Inconsistency of LLM Judge*
- arXiv 2606.13685 *The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation*
- arXiv 2412.12509 *Can You Trust LLM Judgments? Reliability of LLM-as-a-Judge*
- Microsoft *Measuring Quality with LLM Judges*（LLM 1–5 直接打分为何脆弱）
- Galileo AI *Why Is Your LLM-as-a-Judge Inconsistent?*
- 工程模式：Self-Consistency / Best-of-N Sampling（N≈5 为性价比甜点，高风险阈值下转人工）
- 重试与幂等：AWS *Making retries safe with idempotent APIs*；Microsoft Azure Well-Architected *Handling transient faults*；RFC 9110 安全/幂等方法语义
