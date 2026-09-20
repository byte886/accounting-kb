# ADR-018: 名师课 ep3 视频取流解密、平台路由与平台字幕替代本地转写

> **文档类型**：Active（决策记录）
> **更新频率**：决策变更时
> **维护者**：AI 自动维护 + 用户审核
> **读者**：AI 代理 + 人类

## 状态

已采纳（2026-09-09）。本决策确立名师专业课（ep3 / epiphany，`saasCourseType=13`）区别于正课（glive，`saasCourseType=16`）的视频采集技术路线，并以平台自带 VTT 字幕替代本地 FunASR 转写。不改变 ADR-002/003 对**正课**视频压缩、转写的既定方案——正课无平台字幕时仍走 FunASR；也不改变 ADR-012 三层数据模型与 ADR-016 工作区分区。

## 背景

总战略是"先横向备齐账号下所有课程的四来源（讲义 OCR + 视频文字稿 + 题/答/解析 + 用户笔记），知识库 Fan-In 统一放最后"。账号下课程分属两套学习平台：

1. **正课 glive**（`saasCourseType=16`，如税法 42660、会计 42656）：取流、解密、压缩、FunASR 转写链路早已打通（ADR-002/003、ADR-010）。
2. **名师专业课 6 科走另一套 ep3 / epiphany**（`saasCourseType=13`，会计=17244 等）：播放器是 g2player 微前端、接口前缀与加密机制不同。前期攻坚确认：
   - m3u8、ts 分片可免认证下载，但 **AES key 无法用纯 node 复现**——离线调 `authorize` 在各种 bellard 取值 / Origin / header / cookie 组合下全部 `40301 Illegal access TsKey`，页面内 fetch 被 CORS 拦；逆向 gdcrypto.wasm（wasm-bindgen/Rust）卡在 `__wbindgen_malloc`。
   - 原计划双老师 607 个视频 / 314.1 小时，若沿用正课 FunASR 本地转写，CPU 工时巨大。
   - 探路过程中用户指出"**新课程播放页自带字幕**"，需要核实能否直接取字幕原始稿、免去转写。

目标：确定一条可批量、可复用、项目自包含的 ep3 视频 + 文字稿采集路线，并明确它与正课路线的分工边界。

## 决策

### 1. 平台按 saasCourseType 路由（glive16 旧链 / ep313 新链）

- 正课 `saasCourseType=16` 走 glive 既有脚本链，保持不变。
- 名师课 `saasCourseType=13` 走 ep3 新链；正式的"平台适配器抽象 + 其余 5 科推广 + 课程库落位"作为重构工单 EP3-06（L1，先出全量方案经用户确认），本 ADR 只固化已被实测证明的技术事实。
- ep3 只读 / 取流接口只需 `makeHeaders(jwt)` + `Referer=https://epiphany.gaodun.com/`，**不需要 x_gdssid、不需要 cookie**（此前担心已证伪）。

### 2. ep3 取流解密的唯一可行路线：CDP 真实播放页 + Worker 边界截 key

放弃纯 node 复现 authorize、放弃逆向 gdcrypto.wasm，改为**复用日常 Chrome（CDP，登录态）打开真实播放页，让播放器真播，在 Worker↔主线程边界截获解密后的明文 key**：

- 讲次枚举：`/ep-study/front/course/<cid>/syllabus?gradation_id&syllabus_id` 返回的 grad 节点，章节树在 `g.syllabus`（全面精讲）或 `g.children`（基础必修）；递归到**带 `resource_id` 且无 children 的讲次叶子**，其 `id`=csItemId、路径上首个带 `cs_item_ids/video_total` 的节点 id=chapterId。实测 25 考季 412、26 考季 408，与接口 total 一致。
- videoId：`GET /ep-study/api/v1/front/resource/<rid>?courseId=<cid>&csItemId=<cs>&syllabusId=<sid>&is_show_live=0&isRelatedResource=1`（**四个上下文参数缺一不可**，缺参数报 10161000）；videoId 取 `result.resource.video_id`（= `sewise.source_id`），**顶层 `sewise_source_id` 是废弃字段、恒为 null，禁止使用**；`discriminator==='video'` 判定视频讲次。
- 取流：`GET /glive2-vod/api/v1/live/resource?code=<videoId>&res=<SD|HD|FHD>&lang=zh` → m3u8。
- 取 key（关键）：CDP 打开 learning 播放页，reload 前 hook `window.Worker` 双向消息；ep3 用 `window.gp.play()` 让视频真播（`gp.video` 在 closed shadow DOM，外部 querySelector 取不到但 `gp.video` 可用；DOM `.click()` 对播放键无效）；截获主线程回传 `{id,response:Uint8Array(32)}`。
- **★ AES key 形态（反直觉）**：32 个十六进制字符的**前 16 个字符的 ASCII/UTF-8 字节**（不是把 32 串 hex 解码成 16 字节）；IV = m3u8 `IV=0x<32hex>` 的 hex 解码；算法 `aes-128-cbc` + **`setAutoPadding(false)`**。ts 分片在 `glive2-video-resource.gaodun.com`，免认证、不校验 Referer。
- key 由 transcodeId 决定、固定可缓存；但跨视频不同，每个视频需真实播放取一次（约 26–30s）。

### 3. 清晰度：正式采集一律 FHD-1080P

- SD/HD/FHD 三档各有独立 `transcode_id`，故 **m3u8 与 key 都不同**；`subtitle` 三档完全相同（唯一）。
- 用户拍板**正式下载与正课一致用 1080P(FHD)**，不用测试期的 SD。capture 切清晰度项 DOM（`.gp-setting-quality-item`，1080P超清/720P高清/540P标清）与 glive 完全一致，点含"1080"的项即可；一次播放可同时抓到 SD+FHD 两套 key。
- 代价：FHD 码率约 SD 的 2.8 倍（26 分钟样本 SD 69.5MB / FHD 167.8MB）。

### 4. ★平台 VTT 字幕替代本地 FunASR 转写（仅 ep3）

- `live/resource` 响应的 **`result.subtitle` 是完整 VTT URL（域名 video-resource.gaodun.com），免认证 GET 即得标准 WebVTT**；抽查 6 个不同 `encrypt_type`（0/1/2/7）、时长 1585–4157s 的视频，**100% 有字幕**，cue 数与时长成正比。播放器 UI 的"字幕开关"只控制界面显示，不影响接口直接返回 URL。
- **决策：ep3 名师课不再做 FunASR 本地转写**，直接下载 VTT，消解原 314.1 小时视频的转写 CPU 工时。正课 glive 平台不提供该字幕，仍按 ADR-003 走 FunASR，两条路线并存。
- **VTT 原始稿属于原始资源、必须原样保留**（`subtitle.vtt`）；同时转写为与正课同构的 `transcript.md`（去时间轴、相邻 cue 去重、按 200–400 字饱满分段，`# video / > 平台字幕(VTT，免转写) | 时长 | 约N字 / ## 第N段`）。

### 5. 薄编排复用，不重复造轮子

新增 `code/scripts/cdp/ep3_download_videos.js` 只做编排（枚举 → getVideoInfo → live/resource → 取 key → 下载解密 → ffmpeg 合并 → 下 VTT/转 transcript），其中：
- 取 key 复用扩展后的 `code/scripts/cdp/capture_video_key.js`（已支持 ep3：`gp.play()` + 点 1080P，输出顶层为数组的 SD/FHD 双 key）；
- 分片下载 + AES 解密 + 合并零改动复用 `code/scripts/download_decrypt.js`；
- ffmpeg `-c copy` 直接封装为 mp4（分片本身已是 h264/aac，FHD 无需再重压）；
- 断点续跑、key 按 `videoId:res` 缓存、单讲失败不中断批量（fails.json）、临时 `_work` 用完即清、`--dual-teacher` 时文件加老师前缀（目录不分老师，对齐 B 方案）。

## 后果

### 正面

- ep3 视频 + 文字稿采集链路端到端打通，经 25 考季（1585s/167.8MB/1080P/30 段）与 26 考季批量（2337s/205.2MB/41 段）双重验证，未学过的 26 考季同样成立。
- 平台字幕直接替代本地转写，省掉 314.1 小时的 FunASR CPU 工时，且字幕是平台官方稿、质量稳定。
- 讲次枚举不再依赖曾以为必需的 sewise 字段，26 考季 408 讲列表问题一并解决。
- 薄编排复用既有取 key / 解密组件，符合"以精简删除冗余为荣、反对堆砌重复实现"。

### 负面 / 代价

- 每个视频仍需 CDP 开一次真实播放页取 key（约 26–30s），607 个约 4.5–5 小时（后台可接受）；后续可优化为单页连续播放顺序取多 key（记为后续工单，不阻塞）。
- FHD 比 SD 多约 1.8 倍磁盘占用（数据盘空间充足，已评估可承受）。
- 取 key 依赖日常 Chrome 处于登录态——这与正课 CDP 路线（ADR-010）是同一约束，非新增；纯离线/无头环境无法取 key。

### 中性 / 边界

- 本 ADR 不决定名师课课程库最终目录落位、不做 glive/ep3 适配器的正式代码抽象，二者归 EP3-06（L1，先出方案）。
- ep3 题目采集（EP3-04）仍受账号风控 10462222 阻塞，与本决策无关；非视频讲次由 `discriminator` 分流到讲义 / 题目各自链路。

## 来源与下钻

- 完整探路与实测数据：`data/_workspace/_account/ep3-platform-probe.md` 第四 / 五轮（过程件，不入库）
- 工单台账：`data/_workspace/_account/ep3/tickets-index.md` EP3-05 / EP3-06
- 操作 SOP：[视频处理详细指南](../../development/tools/video-processing.md)（ep3 小节）
- 相关：[ADR-010 浏览器自动化连接通道](ADR-010-浏览器自动化连接通道与技术栈选型.md)、[ADR-002 视频压缩标准](ADR-002-视频压缩标准.md)、[ADR-003 音频转写方案](ADR-003-音频转写方案.md)（正课仍适用）
