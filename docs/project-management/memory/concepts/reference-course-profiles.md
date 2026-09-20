---
type: Reference
title: 课程 profile 机制与多课程 ID 对照
description: 一门课一张 profile 档案卡、脚本统一读卡、换课只换卡不改代码；CPA 六科 subjectId、税法/会计的正课(glivepro)与名师课(epiphany)各套 ID、学习状态与结构回填口径。
tags: [course-profile, config, 课程id, 多课程, reference]
sources:
  - id: tax-profile
    resource: ../../../../config/courses/cpa-tax-2026.json
    title: config/courses/cpa-tax-2026.json 税法档案
  - id: accounting-profile
    resource: ../../../../config/courses/cpa-accounting-2026.json
    title: config/courses/cpa-accounting-2026.json 会计档案
  - id: exam-api
    resource: ../../../development/api/gaodun-exam-api.md
    title: 接口档案 1.3 常量 / 2.11 用户空间
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 课程 profile 机制与多课程 ID 对照

## "课程 profile"是什么（先解释概念）
**一门课一张 JSON 档案卡** `config/courses/<profile-key>.json`，把这门课的所有差异（课程 ID、科目、老师、章节结构、本地/网盘路径、学习 URL、有效期）集中在一张卡里；所有脚本**统一读卡取值，代码里不写死某门课**。换一门课（税法→会计）= 新增/切换一张卡，**不改脚本**，这就是"课程 profile 单一配置"。

## 固定常量（全 CPA 通用）
- `projectId` CPA = **8**。
- `subjectId`：会计 **37** / 审计 36 / 财管 45 / 经济法 39 / **税法 38** / 战略 46。
- 做题链路的 `courseId` 就是 **saasCourseId**（不是 vcourseId）；听课/进度用 vcourseId。

## 正课 vs 名师课：是两套独立课程
每科通常有两条线，**ID、平台、页面排版都不同**，别混：
| 线 | 平台 | 说明 |
|---|---|---|
| **正课（主课）** | `glivepro.gaodun.com`（`/course/{saasCourseId}/guide-course`），saasCourseType=16 | 体系正课，做题/作业链路主要对象 |
| **名师专业课（companion）** | `epiphany.gaodun.com`（`/ep3/course/{saasCourseId}`），type=13 | 智能学习平台页面，排版与正课不同 |

名称以平台完整名为准（如「【VIPCPA 专享】名师专业课-税法」），口头简称"名师专业课-税法/会计/…"不完整。

**两线采集链路也不同（按 saasCourseType 路由，ADR-018）**：正课 glive(16) 视频走 H.265 压缩 + FunASR 转写，见 [视频压缩与转写](workflow-video-transcription.md)；名师课 ep3(13) 走 [ep3 取流解密与平台字幕](workflow-ep3-vod-decryption.md)——FHD-1080P、ffmpeg copy 不重压、平台 VTT 字幕免转写、取 key 用 `gp.play()` 真播。做题/讲义链路同样分平台，别把正课脚本直接套到 ep3。

**拿到一门课怎么判断走哪条视频链（按优先级，命中即定）**：
1. **saasCourseType（权威）**：账号清单/用户空间接口里 `=16`→glive 正课链；`=13`→ep3 名师链。
2. **平台域名/URL**：`glivepro.gaodun.com/course/{id}/...`→glive；`epiphany.gaodun.com/ep3/course/{id}`→ep3。
3. **课程完整名规律**：「【26考季】VIPCPA系列-XX（某老师）」=正课(glive)；「【VIPCPA专享】名师专业课-XX」=名师课(ep3)。
4. **能力旁证**：取流响应有 `result.subtitle`(平台 VTT) 的是 ep3、免 FunASR；无平台字幕、需本地转写的是 glive。

**两条视频链对照**：

| 维度 | 正课 glive(16) | 名师课 ep3(13) |
|---|---|---|
| 主控脚本 | `cdp/fetch_lecture_video.js` + `download_decrypt.js` | `cdp/ep3_download_videos.js`（一体编排） |
| 取 key | CDP Worker hook（glive 播放） | CDP `gp.play()` 真播 + 点 1080P（同为 Worker hook） |
| 清晰度/封装 | 下载后 `compress.sh` H.265 CRF30 重压 | FHD-1080P，ffmpeg `-c copy` 不重压 |
| 文字稿 | **FunASR 本地转写**（平台无字幕） | **平台 VTT 直下**（subtitle.vtt+transcript.md，免转写） |

**六科名师课（ep3/type13）全名与 ID**：17244【VIPCPA专享】名师专业课-会计（试点已通）、17245 审计、17246 财管、17247 税法、17248 经济法、17249 战略（审计/财管未走学习引导、大纲树空报 11063019，但讲义清单可拉）。正课只有两门：税法 42660、会计 42656。

## 税法 cpa-tax-2026（已完结，结构齐全）
- 老师 蔡俊峻；考试 2026-08-29 13:00–15:00；账号有效期至 2026-10-31。
- 正课 glivepro：vcourseId **96834** / saasCourseId **42660** / syllabusId **75181** / gradationId null / learnStatus **3（已完结）**。
- 名师 epiphany：vcourseId 50122 / saasCourseId 17247。
- 结构：**官方 14 组 / 92 知识点**（profile 内 code01–14 组名齐全）。
- 本地根 `data/高顿/CPA/【26考季】VIPCPA系列-税法（蔡俊峻老师）`；网盘根 `/apps/CPA课程归档/会计知识库/高顿/CPA/同名`。

## 会计 cpa-accounting-2026（在建，结构待回填）
- 老师 罗翔。正课 glivepro：vcourseId **96760** / saasCourseId **42656** / syllabusId **75086** / gradationId **74570** / learnStatus 3；名师 epiphany：vcourseId 50126 / saasCourseId 17244。
- **`structure` 组为空**（officialGroupCount/pointCount = null）：历史提示"36 章 164 考点"仅供参考，**必须用 syllabusId 实际拉取后回填，禁止拿税法结构或历史章数臆造**。

## 学习状态与采集顺序
- `learnStatus` / 用户空间 `wareStatus`（"1"已开课/"0"未开课）、`learnStatusDesc` 区分进度；显示"**待学习**"的内容**不是不录，而是放到最后处理**。
- 开工前先调用户空间 `ep-course/.../space/vcourse/pc` 盘点账号全部课程（无分页、一次全量），精简台账落 `data/_workspace/_account/user-space/account_courses.json`（覆盖式、不入库）；脚本 `code/scripts/cdp/fetch_user_space_courses.js`。
- 本账号 2026-09-07 实测 CPA 共 8 门：26 考季 VIPCPA 税法/会计 + 名师专业课六科（税法17247、会计17244、战略17249、审计17245、财管17246、经济法17248）。

## 来源与下钻
- [cpa-tax-2026.json](../../../../config/courses/cpa-tax-2026.json)、[cpa-accounting-2026.json](../../../../config/courses/cpa-accounting-2026.json)（字段以卡片现状为准）
- [接口档案 1.3/2.11](../../../development/api/gaodun-exam-api.md)（ID 常量、用户空间清单字段）
- 工作区落点见 [统一运行时工作区](architecture-runtime-workspace.md)；取题流程见 [做题/试卷采集链路](workflow-exam-paper-pipeline.md)。
