# 脚本索引（Scripts Reference）

> **文档类型**：Reference（参考资料 — 脚本说明）
> **更新频率**：新增/修改脚本时
> **维护者**：AI自动维护
> **读者**：AI代理（执行任务前查脚本用途）和人类（了解脚本功能）

本文档是项目所有脚本的完整索引，按功能分类。每个脚本说明用途、用法、可靠性、相关文档。

---

## 脚本总览（按用途分类，与 `scripts/` 磁盘文件对应；新增脚本须按文末维护规则登记）

| 分类 | 脚本数 | 说明 |
|------|--------|------|
| 做题自动化（旧·UI） | 3 | 单选题、多选题、交卷（UI 点选，接口链路的兜底） |
| 视频处理 | 10 | 单文件下载解密/压缩；CDP 抓 HLS key、单讲下载、分阶段下载/压缩与总控；冲刺点播视频侦查/纯接口下载/转写压缩后处理（scripts/cdp/） |
| 音频转写 | 6 | 单文件、批量、队列并发、单讲 worker、环境搭建 |
| OCR文字提取 | 3 | 单目录批量 OCR、全课程批量、OCR 完整性复核（scripts/ocr/） |
| 百度网盘上传 | 6 | 单文件上传、批量上传、课程上传、整课程并发同步、原始资源(notes/videos)断点补传、名师课下载进行中只传完整讲的就绪同步 |
| 环境与工具 | 8 | Playwright连接、密钥管理(全局命令secrets)、数据目录布局、pre-commit、通用阶段完成监听、长任务守护器、一键进度查询、单课总编排器(run_course_pipeline)、并发标准件(lib/parallel.sh) |
| 检查与验证 | 8 | 目录/知识库结构、命名一致性、Git 卫生、讲次映射校验、papers 按讲视图、课程库逐讲体检、OKF 工程记忆校验 |
| 数据采集 | 2 | 按键捕获、解析采集 |
| 浏览器CDP连接 | 5 | 日常Chrome连接、授权自动点（含跨进程锁包装、单例授权守护）、网络抓包骨架（scripts/cdp/） |
| 高顿做题接口链路 | 12 | 只读侦查、抓大纲/取题、UI对照、纯接口做卷与批量补做、papers 原料只读补采、冲刺 6 卷统一入口（scripts/cdp/） |
| 飞书知识库同步 | 4 | 新结构(14组→92知识点)同步、批量同步建节点、节点内容更新两版 |
| 侦查/PoC 网络采集 | 3 | 持久化浏览器 PoC、Playwright 网络钩子注入与导出（备用/备查路线） |
| 高顿课程/讲义采集 | 3 | 正课 glive 讲义 CDN 批量下载；名师课 ep3(saasType13) 大纲梯度章节树清单、讲义 CDN 下载（scripts/cdp/） |

> **全量对齐（2026-09-05；2026-09-07 增补）**：历史脚本已一次性补登；2026-09-07 多课程/并行化改造新增单课总编排器 `run_course_pipeline.sh` 与并发标准件 `lib/parallel.sh`（见「课程配置」末小节），并同步更新各去硬编码脚本条目。新增脚本必须按文末「维护规则」同步登记，并定期用 `ls scripts/ scripts/cdp scripts/ocr scripts/knowledge scripts/lib` 核对，避免再次出现"在跑但没上台账"。

---

## 课程配置（多课程支持）

所有课程相关脚本通过 `scripts/course_config.sh` 统一配置，默认指向税法课。**推荐用课程 profile 切换**（`config/courses/<key>.json`，含课程 ID/章组/overview，见该目录 README）：

```bash
# 切换到会计课（shell 用 COURSE_PROFILE，node 用 GAODUN_COURSE_PROFILE，course_config 两者都认）
export COURSE_PROFILE=cpa-accounting-2026
export GAODUN_COURSE_PROFILE=cpa-accounting-2026

# 然后运行任意课程脚本（会自动读取配置）；多数脚本也支持 --profile <key>
bash scripts/sync_raw_resources.sh all
bash scripts/transcribe_parallel.sh        # FunASR 默认串行最优，不传参即并发1
bash scripts/ocr/run_ocr_all.sh --dry
python3 scripts/knowledge/collect_point_questions.py --all
```

**配置变量**：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COURSE_NAME` | 税法课（蔡俊峻） | 课程名称，用于拼接路径（显式设置优先级高于 profile） |
| `COURSE_LOCAL_ROOT` | `data/高顿/CPA/$COURSE_NAME` | 仓库内课程根目录 |
| `COURSE_REMOTE_ROOT` | `/apps/CPA课程归档/会计知识库/高顿/CPA/$COURSE_NAME` | 网盘课程根目录 |
| `COURSE_DESKTOP_ROOT` | 等同 `COURSE_LOCAL_ROOT`（历史变量名，ADR-021 去软链后不再指向桌面） | 转写/编码/结构检查脚本沿用，值=`data/高顿/CPA/$COURSE_NAME` |
| `BAIDU_ENC_PASS` | 主密码，不入库（环境变量 > 本机 `~/.doubao/secrets/master.pass` > 交互） | 百度网盘加密密码 |

**已参数化（读 profile/config 或 env）的脚本**：采集下载线 `cdp/refresh_inventory.js`、`cdp/collect_user_notes.js`、`cdp/fetch_lecture_video.js`、`cdp/download_lecture_notes.js`、`cdp/ep3_course_outline.js`、`cdp/ep3_download_handouts.js`、`cdp/ep3_download_videos.js`、`cdp/ep3_verify_local.js`（ep3 名师课本地成品离线完整性核对，零网络：完整/待下/残缺、清中断残留 `_work`、列单老师讲）、`cdp/gaodun_paper_core.js`、`cdp/batch_ep3_papers.js`（ep3 名师课批量做题，分时段拟人节奏）、`cdp/fetch_ep3_paper_readonly.js`（ep3 试卷只读取题面/答案/解析，只到 redo-paper 绝不 submit，风控期遇 10462221 第 1 张即退出）；加工线 `transcribe_parallel.sh`、`transcribe_qvideos.sh`、`cdp/encode_all.sh`、`ocr/run_ocr_all.sh`、`sync_raw_resources.sh`、`sync_course_netdisk.sh`、`sync_ep3_ready.sh`、`check_directory_structure.sh`、`progress.sh`；知识线 `knowledge/build_course_overview.py`、`knowledge/collect_point_questions.py`、`knowledge/build_notes_mapping.py`、`knowledge/organize_user_notes.py`、`knowledge/resync_wiki_content.py`、`ocr/verify_ocr.py`。刻意保留专属/一次性的例外见 `docs/development/guides/parallel-toolkit-design.md` §3.4 末表。

### 总编排器与并发标准件

- **`run_course_pipeline.sh <profile> [--dry-run|--from n|--only n|--list]`**：按 `docs/development/project-dag.md` 的 13 节点顺序做单课总调度，阶段 marker 落在 `data/_workspace/$PROFILE/pipeline/<n>.done`（重跑跳过），进入「9 知识库生成」前做 Fan-In 校验。auto 阶段直接调用下列专用脚本，manual/todo 阶段只给指引，**只调度、不含业务逻辑**。首次先 `--dry-run` 走查。
- **`lib/parallel.sh` 的 `parallel_map`**：shell 侧唯一并发标准件，`<NUL任务流> | parallel_map <并发N> <worker命令...>`，底层 `xargs -0 -P`，替代有竞态的自建 mkdir/flock 锁队列。CPU 任务（FunASR/x265）并发度必须实测、默认串行；IO 任务可高并发受限流约束，选型见 `docs/development/performance/parallel-processing-guide.md`。

---

---


---


---

## 二、视频处理（12个）

### `download_decrypt.js` — HLS视频下载解密合并

| 项目 | 说明 |
|------|------|
| **用途** | 下载高顿网站HLS分片视频，AES-128解密，合并为完整MP4 |
| **用法** | `node scripts/download_decrypt.js <m3u8_url> <output.mp4>` |
| **可靠性** | ✅ 高（已验证，支持加密视频） |
| **相关文档** | `docs/development/tools/video-processing.md` |

**原理**：解析m3u8播放列表，下载所有.ts分片，使用AES-128密钥解密，ffmpeg合并为MP4。

---

### `compress.sh` — 视频批量压缩

| 项目 | 说明 |
|------|------|
| **用途** | 使用ffmpeg H.265 CRF30压缩视频，支持单文件和批量目录 |
| **用法** | `bash scripts/compress.sh <input.mp4> <output.mp4>` 或 `bash scripts/compress.sh <input_dir> <output_dir>` |
| **可靠性** | ✅ 高（已验证，压缩比约8:1） |
| **相关文档** | `docs/development/tools/video-processing.md` |

**参数**：libx265 / CRF 30 / preset fast / AAC 96k / hvc1标签 / faststart。
**验证**：压缩后自动检查时长误差<2秒、编码格式、可播放性。

---

### `compress_ep3_videos.py` — 名师课(ep3)视频批量 H.265 重压驱动（断点续跑/全局单实例）

| 项目 | 说明 |
|------|------|
| **用途** | ep3 链路 `-c copy` 原样封装的是 H.264 1080P（单讲常达数百 MB~1GB）；本脚本把仍是 H.264 的 `*_video.mp4` 用与 `compress.sh` 一致参数（libx265/CRF30/preset fast/AAC96k/hvc1/faststart）重压为 H.265，已是 hevc 的自动跳过；断点落 `data/_workspace/_account/ep3/compress_state.jsonl`。参数：`--jobs N`（x265 `pools=N` 线程池，按机器核数与忙闲调档）、`--reverse`（倒序遍历，双机从两端推进）、`--course <名> --crf N`、`--dry-run/--limit N/--report`；写 `.compress_tmp__` 验证通过才同名替换，flock 占 `compress.lock` 保证单实例 |
| **用法** | 单机直跑：`nohup python3 scripts/compress_ep3_videos.py --jobs 12 > logs/compress_run.nohup.log 2>&1 & disown`；双机并行/常驻保活优先用 launchd 总管（见下 `ep3_local_supervisor.sh`），勿用会被回收的 run_in_background |
| **相关文档** | `docs/development/tools/video-processing.md`（双机并行/保活/调档小节）、ADR-022、`compress.sh` |

---

### `ep3_local_supervisor.sh` — 本机名师课 H.265 重压 + 按科滚动门控上云的 launchd 常驻总管

| 项目 | 说明 |
|------|------|
| **用途** | 每 120s 巡检：无压缩进程且仍有 h264 就按顶部 `JOBS` 拉起 `compress_ep3_videos.py`；某科全 hevc 且当前没在压该科（该科 videos 无 `.compress_tmp`）即按科滚动覆盖上云（可与他科压缩并行、整机一次一科），清该科视频 done（保 notes__）、讲并发 1 + `BAIDU_UPLOAD_RATE=1100k`；全部 hevc 且上传成功后 `exit 0`。替代裸 nohup（会随 Doubao 会话关闭被连带 KILL，曾夜间停摆约 6h）。失败判定只认真失败行（行首 3 空格+`- `），不被恒打印的"失败讲:"标题误导 |
| **用法** | 由 `~/Library/LaunchAgents/com.gaodun.ep3-local-supervisor.plist`（RunAtLoad + KeepAlive{SuccessfulExit=false}）托管：`launchctl load -w <plist>` 启动、`launchctl unload <plist>` 停；改档改顶部 `JOBS` 后 unload→删 `.compress_tmp__*`→load（约 2–4 分钟 probe 后才拉起压缩，勿反复 reload；压缩在跑时 unload 会连坐杀子进程）。脚本内已 `export PATH=/usr/local/bin:$PATH` |
| **相关文档** | `docs/development/tools/video-processing.md` 双机小节、`docs/development/guides/finalize-sop.md` 步骤 1、ADR-022；目标机对应看门为过程件 `logs/target_compress_watch.sh`、`logs/target_netdisk_watch.sh`（nohup caffeinate，不入库） |

---

### `cdp/capture_video_key.js` — CDP 抓 HLS 流地址与密钥

| 项目 | 说明 |
|------|------|
| **用途** | 经 CDP（puppeteer-core）打开回放页、注入 Worker hook，捕获 m3u8(SD/FHD) 与 AES key；现役取密钥主链路（连日常 Chrome、复用登录态；旧 Playwright run-code 路线已清理）。**同时支持正课 glive 与名师课 ep3**：ep3 用 `window.gp.play()` 真播（gp.video 在 closed shadow DOM）、点 `.gp-setting-quality-item` 1080P 切清晰度（DOM 与 glive 一致），一次运行同时抓 SD+FHD 两套（两档 transcodeId 不同故 key 不同） |
| **用法** | `node scripts/cdp/capture_video_key.js "<回放/learning URL>" [输出json路径]`，**输出顶层是数组** `[{quality:'FHD-1080P'|'HD-720P'|'SD-540P',m3u8,keyAscii,keyBytes}]`；清晰度由 m3u8 URL 鲁棒判定（兼容两路 CDN：`.../tc/FHD_xxx.m3u8` 与 `.../outputm3u8/<uuid>_1080_xxx.m3u8`，只认 `FHD` 字符串会把"默认就起播1080、只 init 一次"的讲误判 SD 而漏采）；ep3 key 形态=32hex 串前 16 字符的 ASCII 字节（非 hex 解码） |
| **可靠性** | ✅ 高（纯采集，只开一个临时静音播放标签触发 worker 流量、抓完即关，不动用户其它页）；ep3 经 25/26 考季双重验证 |
| **相关文档** | `docs/development/tools/video-processing.md`、ADR-010、`data/_workspace/_account/ep3-platform-probe.md` 第四/五轮 |

---

### `cdp/fetch_lecture_video.js` — 单讲下载解密合并主控

| 项目 | 说明 |
|------|------|
| **用途** | 取回放 URL → CDP 抓 HLS key → 下 m3u8 取 IV → 下载解密合并为 `merged.ts`（**不做压缩**，压缩交队列脚本）；幂等（已有 video.mp4 跳过）；每讲实时取最新 token（m3u8/authorize token 会过期） |
| **用法** | `node scripts/cdp/fetch_lecture_video.js <idx> [--profile <key>]`（idx=课程表下标，idx1=开班前缀00；课程目录/ID 读 profile，缺省税法） |
| **可靠性** | ✅ 高；产物 `<讲>/.vfetch/manifest.json + merged.ts`（压缩阶段读取） |
| **相关文档** | video-processing.md、ADR-010 |

---

### `cdp/download_all.sh` — 批量「下载阶段」

| 项目 | 说明 |
|------|------|
| **用途** | 逐讲 抓 key→下载解密，只产出 `.vfetch/merged.ts`、不压缩；串行抓 key（同一 Chrome 一次只开一个播放标签，拟人、避免多标签 hls worker 互扰）；网络 IO 为主、几乎不占 CPU，**可与 OCR/压缩并行**；讲间留 4s；断点续跑（已有 video.mp4 或 merged 自动跳过） |
| **用法** | `bash scripts/cdp/download_all.sh [idx ...]`（不给参数遍历 1..39） |
| **可靠性** | ✅ 高 |
| **相关文档** | video-processing.md、WORKFLOW「多任务并发调度」 |

---

### `cdp/encode_all.sh` — 批量「压缩阶段」

| 项目 | 说明 |
|------|------|
| **用途** | 扫描各讲 `.vfetch/manifest.json`，把已下载的 merged.ts 逐个 H.265 压成 video.mp4（compress.sh 自带时长/moov 校验），成功后清分片与 merged；全局同时只允许一个 ffmpeg（x265 吃满核，第二个实例吞吐反降）；断点续跑 |
| **用法** | `bash scripts/cdp/encode_all.sh`（扫一遍压完即退）；`--watch` 守护模式边下边压、等下载结束且全压完才退 |
| **可靠性** | ✅ 高（CPU 密集，与下载阶段错峰） |
| **相关文档** | video-processing.md |

---

### `cdp/fetch_all_videos.sh` — 下载+压缩两段总控

| 项目 | 说明 |
|------|------|
| **用途** | 先跑「下载阶段」再跑「压缩阶段」的串行总入口；若要与其它任务并行调度，可分别手动跑 download_all.sh 与 encode_all.sh |
| **用法** | `bash scripts/cdp/fetch_all_videos.sh [idx ...]` |
| **可靠性** | ✅ 高 |
| **相关文档** | video-processing.md |

---


---

### `cdp/fetch_sprint_video.js` — 冲刺视频纯接口下载器（不加密、并发下 ts 合并）

| 项目 | 说明 |
|------|------|
| **用途** | JWT 调取流接口拿 FHD m3u8 → 并发 12 下载相对分片 → 顺序合并 `.vfetch/merged.ts`（无需 CDP/解密）；幂等，已合并则跳过 |
| **用法** | `node scripts/cdp/fetch_sprint_video.js 1|2|3|all`，产物在 `data/_workspace/<profile>/tmp/download/sprint-videos/<标题>/.vfetch/` |
| **实测** | 单卷约 480 片 / 300MB / 约 24 秒（FHD 126 分钟） |
| **可靠性** | ✅ 高（分片 3 次重试、断点续下） |

---

### `cdp/process_sprint_videos.sh` — 冲刺视频「并行转写 + 串行压缩」后处理

| 项目 | 说明 |
|------|------|
| **用途** | 阶段1：3 个 merged.ts 并行 FunASR 转写（每进程限 5 线程）出 transcript.md/json；阶段2：复用 compress.sh 串行 H.265 压 video.mp4；均断点续跑 |
| **用法** | `bash scripts/cdp/process_sprint_videos.sh`，日志 `logs/sprint_video_process.log` |
| **注意** | macOS 自带 bash 3.2，已用 glob 数组替代 mapfile；压缩阶段全局只允许一个 ffmpeg |
| **可靠性** | ✅ 高 |

---

### `cdp/fetch_question_video_keys.js` — 题目级讲解视频抓 AES key（一次性，需 Chrome）

| 项目 | 说明 |
|------|------|
| **用途** | 题目级视频 encrypt=1、key 不下发（authorize 被鉴权拦，wasm 解密后只在 Worker 内存）；CDP 打开逐题解析页→点封面加载播放器→hook Worker `postMessage`，从 `to_worker.response` 取前 16B ASCII key，落 `data/_workspace/<profile>/papers/qvideo_keys.json` |
| **用法** | `node scripts/cdp/fetch_question_video_keys.js`（卷/大题入口/vid 已在脚本内配置，来自 syllabus_full.json 与 redo） |
| **关键事实** | key 为视频级固定值、跨会话不变，故只需抓一次；hook 必须 evaluateOnNewDocument 注入 |
| **可靠性** | ✅ 高（7/7 一次成功；缺哪个补哪个，已抓自动跳过） |

---

### `cdp/download_question_videos.js` — 题目级视频纯接口下载解密（离线可重跑）

| 项目 | 说明 |
|------|------|
| **用途** | 读 qvideo_keys.json 固定 key，JWT 取 SD m3u8→解析 IV→并发 10 下载→逐片 AES-128-CBC 解密（校验 0x47）→合并 merged.ts；产物 `data/_workspace/<profile>/tmp/download/sprint-videos/题目级讲解/qvideo_<pid>_<entry>_<vid8>/.vfetch/` |
| **用法** | `node scripts/cdp/download_question_videos.js all` 或 `<vid8>`；分片落盘缓存、断点续跑 |
| **实测** | 7 个共 175 分钟 / 约 458MB(SD)，全量下载解密约 40 秒；ffprobe 时长逐一==接口 duration |
| **可靠性** | ✅ 高（分片 3 次重试、解密非 TS 立即报错） |

---

## 三、音频转写（6个）

> **如何选用（这些入口对象/粒度不同，不是重复实现，勿误删）**
>
> | 入口 | 对象 / 粒度 | 何时用 |
> |---|---|---|
> | `transcribe_all.sh` | 整门正课 · 串行 | 正课讲次批量转写**默认入口**；成品已归位时 `TRANSCRIBE_ROOT=<课程>/原始资源/videos bash scripts/transcribe_all.sh` |
> | `transcribe_one.sh` | 单个讲目录 | 一般不单独用，是 parallel 的 xargs -P worker |
> | `transcribe_parallel.sh` | 整门正课 · xargs 调度 | 需要并发时用；实测**串行吞吐最优**（18.5x > 6 并发 14.3x），默认并发 1 |
> | `transcribe_qvideos.sh` | 题目级讲解视频（冲刺，`_workspace/.../qvideo_*`） | 仅冲刺模考题目级视频，数据源不同于正课，会计冲刺仍要用 |
> | `batch_video_pipeline.sh` | 下载链内联 | 下载→压缩→归位→转写一条龙，断点续跑（**串行后备**；动态并行首选 `video_dynamic_pipeline.sh`）；过程件落 `_workspace/<profile>/dl-tmp` |
>
> **铁律**：转写必须走 `transcription/venv/bin/python`（FunASR 只装在 venv，系统 `python3` 会 `ModuleNotFoundError: funasr`）；下载/压缩过程件（`.vfetch` 分片、merged.ts）统一落 `data/_workspace/<profile>/dl-tmp/`，成品统一归位 `原始资源/videos/<讲名>/`，**课程库根全程不留散落讲目录**。

### `transcribe_pipeline.py` — 单视频音频转写

| 项目 | 说明 |
|------|------|
| **用途** | 从视频提取音频，使用faster-whisper/FunASR转写为文字 |
| **用法** | `python3 scripts/transcribe_pipeline.py <video.mp4> [output.md]` |
| **可靠性** | ✅ 中（依赖模型质量，专业术语可能出错） |
| **相关文档** | `docs/development/tools/transcription.md` |

**输出**：带时间戳的文字稿（Markdown格式）。

---

### `setup_transcription_env.sh` — 转写环境搭建

| 项目 | 说明 |
|------|------|
| **用途** | 创建Python虚拟环境，安装faster-whisper/FunASR及依赖 |
| **用法** | `bash scripts/setup_transcription_env.sh` |
| **可靠性** | ✅ 高（首次设置后不需要重复运行） |
| **相关文档** | `docs/development/tools/transcription.md` |

**输出**：`.venv-transcribe/` 虚拟环境目录（已在.gitignore中忽略）。

---

### `transcribe_all.sh` — 全课程批量转写（串行）

| 项目 | 说明 |
|------|------|
| **用途** | 对课程库所有讲的 video.mp4 用 FunASR（SenseVoiceSmall+VAD）批量转写；逐讲用独立临时目录调 transcribe_pipeline.py（规避所有视频同名 video.mp4 互相覆盖），完成后拷回 transcript.md/json；断点续传（已有 transcript.md 且 >1000 字自动跳过），单讲失败记录后继续 |
| **用法** | `bash scripts/transcribe_all.sh` |
| **可靠性** | ✅ 高；**CPU 密集**，须在视频「压缩全部完成后」再跑，避免与 x265 叠加争抢/降频 |
| **相关文档** | `docs/development/tools/transcription.md`、ADR-003 |

---

### `transcribe_one.sh` — 单讲转写（并发 worker）

| 项目 | 说明 |
|------|------|
| **用途** | 转写单个讲目录，被 `xargs -P` 并发调用；每个讲只出现一次，天然无竞态 |
| **用法** | `bash scripts/transcribe_one.sh <讲目录绝对路径>` |
| **可靠性** | ✅ 高 |
| **相关文档** | transcription.md |

---

### `transcribe_parallel.sh` — 批量转写（xargs 内核调度，默认串行）

| 项目 | 说明 |
|------|------|
| **用途** | 扫描正课课程库生成 NUL 待转队列，经 `lib/parallel.sh` 的 `parallel_map`（`xargs -0 -P`）内核级调度 `--worker` 自递归，无自建锁竞态；FunASR 实测**串行总吞吐最优**（1 并发 18.5x > 6 并发 14.3x），默认并发 1，可传参覆盖（换机器/模型须按性能指南重测）；单讲失败隔离、不自动 requeue，重跑幂等续（已有 >1000 字 transcript 跳过） |
| **用法** | `bash scripts/transcribe_parallel.sh [并发数N]`（默认 1，对象=正课课程库，读 profile/config） |
| **可靠性** | ✅ 高（内核动态调度 + 幂等断点续跑） |
| **相关文档** | `docs/development/performance/parallel-processing-guide.md`、ADR-003 |

---

### `transcribe_qvideos.sh` — 题目级讲解视频批量转写（默认串行）

| 项目 | 说明 |
|------|------|
| **用途** | 机制同 transcribe_parallel（`parallel_map` + `--worker` 自递归、默认并发 1）；对象是 `data/_workspace/<profile>/tmp/download/sprint-videos/题目级讲解/qvideo_*/video.mp4`（税法冲刺专属数据），临时目录用 vid 目录名唯一化（避免首段前缀都叫 qvideo 撞车），输出 transcript.md/json 到各目录 |
| **用法** | `bash scripts/transcribe_qvideos.sh [并发数N]`（默认 1，已有 >1000 字 transcript 自动跳过） |
| **实测** | FunASR 约 20x 实时；并发度总吞吐以性能指南为准（串行最优，旧默认 6 已收敛） |
| **可靠性** | ✅ 高 |

---

## 四、OCR文字提取（3个）

### `batch_ocr.sh` — 批量PDF/讲义OCR

| 项目 | 说明 |
|------|------|
| **用途** | 使用macOS Vision框架批量提取PDF中的文字，支持图片型PDF |
| **用法** | `bash scripts/batch_ocr.sh <pdf_dir> <output_dir>` |
| **可靠性** | ✅ 中高（macOS原生OCR，文字清晰时准确率高；表格/图表需AI补充） |
| **相关文档** | `docs/development/tools/ocr.md` |

**注意**：表格和图表中的文字OCR可能不完整，需要AI视觉模型补充识别。

---

### `ocr/run_ocr_all.sh` — 全课程批量 OCR

| 项目 | 说明 |
|------|------|
| **用途** | 批量 OCR 课程库全部讲义 PDF（串行，逐个调 batch_ocr.sh）；每处理一个 PDF 前清空 /tmp 分页缓存，避免不同 PDF 断点缓存串用；输出 `docs/<x>.pdf → docs_text/<x>_OCR.md`，已存在且非空则跳过 |
| **用法** | `bash scripts/ocr/run_ocr_all.sh [--dry]` |
| **可靠性** | ✅ 中高（macOS 原生 OCR） |
| **相关文档** | `docs/development/tools/ocr.md` |

---

### `ocr/verify_ocr.py` — OCR 完整性复核（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 逐份比对 `docs/*.pdf` 实际页数与 `docs_text/<名>_OCR.md` 中 `## 第N页` 分节数（允许相等，少于即残缺），输出逐份 OK/残缺清单与汇总 |
| **用法** | `transcription/venv/bin/python scripts/ocr/verify_ocr.py`（残缺时退出码 1） |
| **可靠性** | ✅ 高（PyMuPDF 机械计数） |
| **相关文档** | ocr.md、SOP 步骤0「生成前 verify 前置」 |

---

## 五、百度网盘上传（6个）

### `baidu_upload.py` — 单文件上传到百度网盘

| 项目 | 说明 |
|------|------|
| **用途** | 使用百度网盘API分片上传单个文件 |
| **用法** | `python3 scripts/baidu_upload.py <local_path> <remote_path>` |
| **可靠性** | ✅ 高（已验证，支持大文件分片上传） |
| **相关文档** | `docs/development/api/netdisk-setup.md` |

**注意**：上传时不要通过代理（百度网盘API直连更快）。上传后验证文件大小与本地一致。

---

### `upload_course.sh` — 完整课程上传

| 项目 | 说明 |
|------|------|
| **用途** | 上传一个完整课程目录（视频+讲义+文字稿）到百度网盘对应位置 |
| **用法** | `bash scripts/upload_course.sh <course_name>` |
| **可靠性** | ✅ 中（依赖目录结构规范） |
| **相关文档** | `docs/development/api/netdisk-setup.md` |

---

### `sync_course_netdisk.sh` — 课程目录并发同步网盘

| 项目 | 说明 |
|------|------|
| **用途** | 把一整个课程根按讲并发同步到百度网盘（通用，可复用于会计等其他课程）：xargs -P 并发、断点续传（`logs/netdisk_done/` 标记成功讲、重跑自动跳过）、单讲失败不影响其他讲、百度侧已存在文件走 MD5 秒传；逐讲调用 upload_course.sh 过滤技术过程文件 |
| **用法** | `bash scripts/sync_course_netdisk.sh <本地课程根> <网盘课程根> [并发数=3] [编号正则过滤]`（网盘 IO 建议并发 2–3） |
| **可靠性** | ✅ 高（已用于 S1 39 讲同步；每讲独立日志 `logs/netdisk_<讲>.log`） |
| **相关文档** | `docs/development/api/netdisk-setup.md`、standards 2.2（L1/L2 备份） |

---

### `sync_raw_resources.sh` — 原始资源(notes/videos)断点补传网盘

| 项目 | 说明 |
|------|------|
| **用途** | 阶段④门禁：把课程「原始资源」下的 notes（用户笔记/留言正本/题答解析）与 videos（压缩视频）按讲并发补传到百度网盘。xargs -P 并发、断点续传（`logs/raw_done/{notes,videos}_*.done` 标记成功讲、重跑跳过）、单讲失败不影响其他、百度侧已存在走 MD5 秒传。配合 run_supervised.sh 可脱离 AI 会话自动续跑到底 |
| **用法** | `bash scripts/sync_raw_resources.sh <notes\|videos\|all> [并发数=2]`（网盘 IO 建议并发 2） |
| **可靠性** | ✅ 高（已用于税法课 notes 17/17、videos 39/39；每讲独立日志 `logs/raw_<类型>_batch.log`） |
| **相关文档** | long-task-supervisor-guide.md、finalize-sop.md、standards 2.2（L1/L2 备份） |

---

### `sync_ep3_ready.sh` — 名师课(ep3)「已就绪内容」安全同步网盘

| 项目 | 说明 |
|------|------|
| **用途** | 视频仍在下载时安全备份：讲义 notes 整目录同步；视频只传「完整讲」——讲目录内每个 `*_meta.json`（或裸 `meta.json`）都有对应、非空的 `*_video.mp4`，缺视频的半成品讲不匹配、**不打 done**（否则以后补齐会被断点标记永久跳过、网盘缺件），下次重跑自动带上。核心上传/秒传/断点复用 sync_course_netdisk.sh，本脚本只做"就绪筛选"，profile 驱动、兼容双老师前缀与单老师无前缀两种命名 |
| **用法** | `bash scripts/sync_ep3_ready.sh <profile> [并发=2] [notes\|videos\|all(默认)]`，如 `bash scripts/sync_ep3_ready.sh ep3-accounting-2026 2 all`；可在下载进行中反复重跑（断点续传、已存在 MD5 秒传） |
| **可靠性** | ✅ 高（完整讲判定离线、零网络；不完整讲绝不打 done） |
| **相关文档** | `docs/development/api/netdisk-setup.md`、ADR-018（字幕替代转写）、双老师文件名前缀约定 |

---

### `verify_netdisk_final.py` — 课程 finalize 网盘/本地终态递归对比（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 递归对比本地课程目录与网盘目录的结构、文件数、文件名集合、文件大小，finalize 前三地一致性核验 |
| **用法** | `BAIDU_ENC_PASS=<加密密码> python3 scripts/verify_netdisk_final.py <本地课程根> <网盘课程根> [-x 知识详解]`；默认排除点开头隐藏/缓存（`.ep3cache` 等），`-x/--exclude` 可重复、按目录名排除任意层级——原始资源滚动备份阶段排尚在生成的 `知识详解`，课程完整 finalize、知识详解定稿传云后做两层全量核验时不带 `-x` |
| **相关文档** | `docs/development/guides/netdisk-final-verification-sop.md` |

---

### `netdisk_verify_summary.py` — 网盘终态核验日志分类汇总（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 吃一份或多份 `verify_netdisk_final.py` 的核验日志，按类别汇总：讲义缺/不一致、视频缺、视频大小不一致（其中标注"网盘旧大版"=残留 h264，需清视频 done 后 rtype=3 覆盖）、缺讲目录、缺配套、垃圾分片；把 `知识详解`/.ep3cache/.DS_Store 归 noise、_work/.dec.ts 归 junk |
| **用法** | `python3 scripts/netdisk_verify_summary.py <核验日志...>` |
| **相关文档** | `docs/development/guides/netdisk-final-verification-sop.md` §2.1.1、ADR-022 |

---

## 六、环境与工具（8个；凭证加解密另用全局命令 `secrets`）


---

### `secrets`（全局命令；原 scripts/secrets.sh 已抽离）

> 凭证工具已升级为**全机唯一全局命令** `secrets`（权威源在 `mac-system-toolkit` 技能，软链于 `~/.local/bin/secrets`；新机器执行一次 `secrets install`）。本项目不再保留 `scripts/secrets.sh` 副本，只保留自己的 `.secrets/*.enc` 密文；统一规范见 mac-system-toolkit 的 `references/secret-encryption.md`。

| 项目 | 说明 |
|------|------|
| **用途** | 加密/解密敏感凭证（GitHub Token、百度网盘API密钥等） |
| **解密百度凭证字段** | `ENC_PASS=密码 secrets json .secrets/baidu_credentials.enc access_token` |
| **GitHub PAT 登录** | `secrets decrypt .secrets/gh_token.enc \| gh auth login --with-token` |
| **加密新凭证** | `secrets encrypt '<明文>' .secrets/xxx.enc` |
| **可靠性** | ✅ 高（OpenSSL AES-256-CBC+PBKDF2+salt+base64；密码走 ENC_PASS 或交互，不硬编码） |

**规则**：加密文件（*.enc）可以提交到GitHub，明文文件（*.json, *.txt）在.gitignore中忽略。

---

### `pre-commit` — Git提交前检查

| 项目 | 说明 |
|------|------|
| **用途** | Git 提交前自动检查（检查项与阈值以 git-workflow 9.2 为准）：大文件 >1MB 警告 / >10MB 硬阻止；音视频、PDF 等生成文件误提交警告；敏感信息（明文 password/token/secret/key）警告；新增 .md 未登记 DOCUMENTATION_MAP 或缺头部类型标注警告；暂存 .md 相对链接断链硬阻止；文档类型词不在 7 类白名单（Task/Concept/Reference/Governance/Active/Knowledge/Template）硬阻止；**运行产物/环境/数据误入暂存（命中模式表 ARTIFACT_RE，或被 .gitignore 忽略却 `git add -f` 强塞）硬阻止**；**本次暂存触及 `docs/project-management/memory/` 或校验器本身时，跑 `okf_validate.py`，OKF 工程记忆 bundle 存在硬错误(E)硬阻止（W/I 不阻断）** |
| **用法** | 安装后每次 `git commit` 自动执行（激活副本位于 `.git/hooks/pre-commit`） |
| **可靠性** | ✅ 高（不依赖读文档，自动执行） |
| **相关文档** | `docs/development/guides/git-workflow.md` 第 9 节 |

**安装**：`cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`

---

### `okf_validate.py` — OKF 工程记忆 bundle 一致性校验（vendored，零依赖）

| 项目 | 说明 |
|------|------|
| **用途** | 校验 `docs/project-management/memory/` 工程记忆 bundle：非保留 .md 必须有 frontmatter 且含非空 `type`（E1/E2 硬错误）；index/log 保留文件结构（E3）；缺 title/description、非法 status、时间格式、死链 W80、孤儿页 W81、脚注与 sources 对账等为警告 W；信任等级现算等为信息 I。只扫指定 bundle 目录，不要求全项目 .md 加 frontmatter |
| **用法** | `python3 scripts/okf_validate.py docs/project-management/memory`（`--strict` 把 W 也判失败、`--max-warnings N`、`--json`）；E 必修、退出码 1，W 逐条确认，I 仅参考。已由 pre-commit 第 8 段在相关提交时自动调用 |
| **可靠性** | ✅ 高（纯 Python 标准库、确定性、系统 python3 直接跑） |
| **来源/边界** | vendored 自全局技能 okf-wiki v0.2（上游 Google Cloud OKF v0.2，Apache-2.0）；为项目自包含而复制进仓库，**勿本地分叉改逻辑**，上游升级整体替换（见 ADR-017） |

---

### `watch_stage_done.sh` — 通用阶段完成事件监听

| 项目 | 说明 |
|------|------|
| **用途** | 零依赖、60 秒轮询：监听某目录下匹配指定模式的文件数量达到预期值时，写完成标记文件并退出。替代人工长间隔巡检，消除"任务已完成但总调度未发现"的空窗（空窗 ≤60 秒）——即"子任务主动上报为主、定期检查仅防异常" |
| **用法** | `bash scripts/watch_stage_done.sh <监听目录> <文件名匹配> <预期数量> <标记文件路径> [检查间隔秒]` |
| **可靠性** | ✅ 高（纯文件计数，无外部依赖） |
| **相关文档** | WORKFLOW「多任务并发调度」 |

---

### `run_supervised.sh` — 长任务守护器（脱离 AI 会话自动续跑）

| 项目 | 说明 |
|------|------|
| **用途** | 解决 AI `run_in_background` 约 8 分钟被回收、且 AI 是请求-响应模式无法被系统进程反向唤醒的问题：用 `nohup ... & disown` 让进程 PPID=1 被 launchd 接管，while 循环反复执行断点续传命令，用完成检测命令判终，连续 3 轮无进展判异常，完成/异常调 osascript 发 macOS 通知。配套「定时唤醒 AI + 临门一脚 + 完成自清理」实现 AI 自动接续 |
| **用法** | `nohup bash scripts/run_supervised.sh <任务名> "<单次命令>" "<完成检测test命令>" ["<进度标量命令>"] > logs/supervisor_<任务名>.log 2>&1 & disown`；第 4 参可选——输出一个随推进单调变化的标量供停滞检测（不产 `.done` 标记的任务用），缺省统计 `logs/raw_done/<任务名>_*.done` |
| **可靠性** | ✅ 高（已用于 videos 39 个自动续跑到完成；BSD 兼容：完成统计用 `find -name` 不用 `ls glob`，画进度条前先判数量>0 避开 `seq 1 0`） |
| **相关文档** | docs/development/performance/long-task-supervisor-guide.md（含第七章 AI 自动接续）；做题场景直接用下面的 `cdp/run_papers_supervised.sh` 薄封装 |

### `cdp/run_papers_supervised.sh` — 批量做题守护启动器（run_supervised 的做题薄封装，每门课复用）

| 项目 | 说明 |
|------|------|
| **用途** | 针对 `batch_redo_papers.js` 长跑「零错误静默退出」：封装好"每轮先 `refresh_inventory` 从平台回查重建 audit（已满分剔除）→ 再 `batch_redo --go` 续跑剩余"的正确顺序与完成/停滞判据，避免裸跑或直接重启按旧 audit 从头重做（死循环根因）。redo 退出后 5 秒自动续跑，PPID=1 脱离 AI 会话 |
| **用法** | `nohup bash scripts/cdp/run_papers_supervised.sh <profile> > data/_workspace/<profile>/logs/supervisor_papers.log 2>&1 & disown` |
| **日志** | `supervisor_papers.log`（守护轮次/停滞）+ `refresh_supervised.log`（每轮平台回查）+ `batch_do_paper.log`（做题明细，追加），均在 `data/_workspace/<profile>/logs/` |
| **终态/防眠** | audit=0 → 写 `[NOTIFY]✅` 日志并 exit 0；连续 3 轮平台已达成数不增长 → `[NOTIFY]❌` exit 1。做题线默认 `SUPERVISE_NO_OSASCRIPT=1` 不弹 macOS 弹窗，终态由 15 分钟定时唤醒的 AI 识别后接手推进并在豆包通知；已套 `caffeinate -i` 防 Mac 空闲睡眠 |

---

### `cdp/run_ep3_videos_supervised.sh` — ep3 名师课视频批量守护启动器（run_supervised 的 ep3 视频薄封装，各科/各梯度复用）

| 项目 | 说明 |
|------|------|
| **用途** | 针对 `ep3_download_videos.js` 长跑在 Mac 睡眠 / 日常 Chrome CDP 瞬断时「零报错静默终止」（日志停在"取 key"、无栈）：每轮断点续跑（已下幂等跳过、上轮 capture 失败重试、没跑完的继续），退出 5 秒后自动续下一轮，PPID=1 脱离 AI 会话，套 `caffeinate -i` 防空闲睡眠（治本） |
| **用法** | `nohup bash scripts/cdp/run_ep3_videos_supervised.sh <ep3-profile> <梯度> <目标视频数> [--dual-teacher] > data/_workspace/_account/ep3/logs/superv_<x>.log 2>&1 & disown`；目标数取该梯度 outline 实测 videoTotal（会计全面精讲261/税法170/战略122/经济法157）；成品目录从 profile 卡 localRoot 自动拼 |
| **日志** | `superv_*.log`（守护轮次/停滞）+ `data/_workspace/_account/ep3/logs/<profile>_<梯度>.log`（下载明细，追加） |
| **终态** | 该梯度 `*video.mp4` 数 ≥ 目标 → `[NOTIFY]✅` exit 0；连续 3 轮数量不增长 → `[NOTIFY]❌` exit 1（通常是个别讲反复取不到 key，需人工看明细，不空转） |

---

### `progress.sh` — 后台长任务一键进度查询（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 一条命令查看后台长任务：进度条、守护器是否存活、正在处理的单元、最近日志；并取最近 9 个 done 标记时间戳与实际文件大小现算合计/单路速率、平均单耗、剩余总量与 ETA、预计完成时刻。只读，不影响任务运行 |
| **用法** | `bash scripts/progress.sh`（已 chmod 755，也可直接 `./scripts/progress.sh`） |
| **可靠性** | ✅ 高（纯文件/日志统计，无外部依赖；ETA 为基于近期完成速率的估算） |
| **相关文档** | long-task-supervisor-guide.md 3.4 节 |

---

## 七、检查与验证（5个）

### `check_directory_structure.sh` — 目录结构检查

| 项目 | 说明 |
|------|------|
| **用途** | 检查本地课程目录结构是否符合规范（高顿/CPA/课程名/章节名/） |
| **用法** | `bash scripts/check_directory_structure.sh <data_dir>` |
| **可靠性** | ✅ 中高（基于命名规范检查） |
| **相关文档** | `docs/project-management/standards/NAMING_CONVENTION.md` |

---

### `check_kb_structure.sh` — 知识库结构检查

| 项目 | 说明 |
|------|------|
| **用途** | 检查本地知识成品结构是否符合规范（14 组 / 知识点单篇 4 节） |
| **用法** | `bash scripts/check_kb_structure.sh <kb_dir>` |
| **可靠性** | ✅ 中（基于文件命名检查） |
| **相关文档** | `docs/development/knowledge/knowledge-base-organization.md` |

---

### `check_naming_consistency.py` — 命名一致性巡检 / 影响面 / 回归

| 项目 | 说明 |
|------|------|
| **用途** | 按 NAMING 第九章（SSOT）巡检"文档类型↔文件名风格"自洽、客观列出类型复核候选；对 task/test/verification/knowledge-base 下中文文件名提示"段间下划线、日期除外"；改名前 `--impact 老名` 查看引用影响面；整改后 `--regression` 跑自洽+断链回归。所有候选均为警告级、不阻断 |
| **用法** | `python3 scripts/check_naming_consistency.py`（另有 `--impact NAME` / `--regression`） |
| **可靠性** | ✅ 高（风格规则可机械判定；语义判型只列候选、通读后可维持原判，不臆断） |
| **相关文档** | `NAMING_CONVENTION.md` 第九章、`PROJECT_STRUCTURE_MAINTENANCE.md` 第六章 SOP |

---

### `check_git_hygiene.sh` — Git 仓库卫生体检（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 全量只读体检：①已跟踪文件是否混入运行产物（模式表与 pre-commit 的 ARTIFACT_RE 一致）；②未跟踪项分类（像运行产物则提示补 .gitignore，否则提示确认入库）；③被跟踪的 >1MB 大文件；④`.git` 与工作区体积。不改任何文件/暂存区 |
| **用法** | `bash scripts/check_git_hygiene.sh`（发现存量漏网退出码 1、否则 0） |
| **可靠性** | ✅ 高（模式机械匹配；pre-commit 拦增量、本脚本查存量，互补） |
| **相关文档** | `PROJECT_STRUCTURE_MAINTENANCE.md` 2.1、`git-workflow.md` 第 9 节 |

---

### `papers_view.py` — papers 题源按讲只读视图

| 项目 | 说明 |
|------|------|
| **用途** | 遵循 standards 2.2.4「物理集中存、逻辑按讲视图」，由 `paper_index.json` 的 chapter 字段现场 group by 出「每讲几套卷 / 多少题 / paperId」；只读，不落盘、不生成第二份物理副本 |
| **用法** | `python3 scripts/papers_view.py`（全讲概览）；`--lecture 01` 或 `--lecture 增值税`（讲号/关键词）；`--json`（结构化输出供脚本消费） |
| **可靠性** | ✅ 高（实测 34 讲 / 116 套 / 1296 题；chapter 前导空格自动 strip） |
| **相关文档** | standards 2.2.4、ADR-011 |

---

## 八、浏览器 CDP 连接（4个，位于 `scripts/cdp/`）

> 用 puppeteer-core 经 Chrome 144+ 运行时调试通道连接用户**正在使用的日常 Chrome**（默认 Profile、复用登录态、免重启免重登）。选型见 ADR-010，手册见 `docs/development/tools/browser-cdp-connect-guide.md`。依赖在仓库根 `npm install`（node_modules 不入库）。

### `cdp/connect_browser.js` — 连接日常 Chrome（可复用模块 + 自检）

| 项目 | 说明 |
|------|------|
| **用途** | 读取带 UUID 的 CDP 端点、自动 AXPress 授权、403 退避重试，导出 `connectDailyChrome/findPage/listPages/safeDisconnect` |
| **用法** | `node scripts/cdp/connect_browser.js`（环境自检：连接→列标签→断开）；业务脚本 `require('./cdp/connect_browser')` |
| **可靠性** | ✅ 高（已实测，连续连接稳定，1.4~3.6s 连上且保留用户页面） |
| **相关文档** | `docs/development/tools/browser-cdp-connect-guide.md`、ADR-010 |

---

### `cdp/press_allow.applescript` — 自动点「允许远程调试」

| 项目 | 说明 |
|------|------|
| **用途** | 递归遍历 Chrome 控件，对「允许」按钮执行元素级 AXPress（文字在 AXDescription），多屏可靠；无弹窗时无副作用 |
| **用法** | 一般由 connect_browser.js 自动调用；手工调试：`osascript scripts/cdp/press_allow.applescript` |
| **可靠性** | ✅ 高（需在系统设置授予「辅助功能」权限） |
| **相关文档** | `docs/development/guides/macos-accessibility-automation.md` |

### `cdp/press_allow_locked.sh` — 代点「允许」的跨进程互斥包装

| 项目 | 说明 |
|------|------|
| **用途** | 透明代理 `press_allow.applescript`，用 mkdir 原子锁保证**全机同一时刻只跑一个代点 osascript**，根治多取 key 进程并发访问 System Events 拥塞点不中（I-015/B-103）；陈旧锁按持锁 PID 存活性抢占，等锁约 2.5s 超时则本轮安静放弃 |
| **用法** | 一般由 connect_browser.js 自动调用；手工：`bash scripts/cdp/press_allow_locked.sh ["还焦App名"]` |
| **可靠性** | ✅ 高，已测锁等待/陈旧锁抢占 |

### `cdp/cdp_consent_guard.sh` — 单例「远程调试授权」守护

| 项目 | 说明 |
|------|------|
| **用途** | 长跑下载期间常驻：每 1s 一条合并 AppleEvent 探测 Chrome 授权 sheet，发现即经锁包装代点、没掉下一秒重点、并还焦给最近的非 Chrome 前台 App，无 sheet 零动作不抢焦；补上连接内 press 循环只覆盖握手窗口、残留/晚到弹窗无人点的缺口（I-015/B-104） |
| **用法** | 由 `throttled_ep3_download.sh` 拉起/收工 kill（pidfile 单例，重复启动安全退出）；手工：`bash scripts/cdp/cdp_consent_guard.sh` |
| **可靠性** | ✅ 高，已测单例 + `autoPress:false` 只靠守护真实连接 1.8s 通过 |

---


---

## 九、高顿做题接口链路（17个，位于 `scripts/cdp/`）

> 「接口为主、UI 兜底」的纯接口做题脚本，契约见 [高顿作业接口档案](../docs/development/api/gaodun-exam-api.md)。报文落 `data/_workspace/<profile>/sniff/`（不入库）。


---


---


---


---


---


---

### `cdp/gaodun_paper_core.js` — 纯接口做卷共享核心（客观 + type5/6 主观）

| 项目 | 说明 |
|------|------|
| **用途** | 被 `api_do_paper.js`/`batch_redo_papers.js` 复用：record→(首次先 create-paper)→redo→平铺答案（type5 父题不答、平铺其 type6 子题；顶层独立 type6 同样处理）→按 `aiCorrect.cpaBotType` 分流（=3 进 AI 批改、=0 未配 AI 只交答案）→最小停留→submit 全量交卷→交卷后并发=3 逐题 correct-ai/cpa：cs=6 走「canon+qual / full / AI 未命中点」三级补全 → best-of-N×4 原样重取 → 仍不满且答案=标准答案则归 aiCeiling→exam-report 两层核对（fullScore / platformDone）。主观答案统一走 `cleanSubjectiveAnswer`（算式主体+点拨精简「依据：」+多小问分点，交卷与首次 AI 批改同版；点拨不全删——六卷实证其含采分点，只删年份政策背景句）。导出 `doPaperViaApi/buildUserAnswers/cleanSubjectiveAnswer/canonAnswer/qualitativeAnswer/findJwt` 等 |
| **答案来源** | 客观取 `questionAnswer.answer`；主观（type5 子题与顶层 type6）从 `questionAnswer.analysis` 提炼（canon 等式句 / qual 点拨定性句 / full 整段兜底），无需本地题库 |
| **可靠性** | ✅ 基础卷 116 张全部达成（109 严格满分 + 7 平台最优）；73 张客观精讲卷一次满分零失败；交卷与 AI 批改解耦（交卷即完成，批改异常只标记不崩）；AI 判分抖动应对见 [flaky-ai-judging.md](../docs/development/guides/flaky-ai-judging.md) |
| **相关文档** | gaodun-exam-api.md §2.3/2.5/2.6/2.7、§3 |

---

### `cdp/auth_token_guard.js` — token 失效自动续命共享件（跨进程 single-flight，I-013）

| 项目 | 说明 |
|------|------|
| **用途** | 统一收口「本地 JWT 7 天过期返回 553649434」的自动刷新，替代各脚本内联实现。导出 `isTokenExpired()`（只认 553649434，做题风控码 10462221 等不误判）与 `refreshJwtWithLock()`：第一个命中的进程持文件锁 `.refresh.lock`、spawn `refresh_auth_token.js` 连已登录日常 Chrome 抓新 token；并行的其它进程（下载是 3 消费者+1 生产者多进程）发现锁则等待复用，**不会重复连 Chrome / 抢焦点**；陈旧锁（持有者崩溃/超 120s）自动抢占 |
| **接入方** | `ep3_download_videos.js` 在统一请求入口 `apiGet` 拦截 553649434→刷新→重试 1 次（覆盖 syllabus/getVideoInfo/getLiveResource，生产者消费者都受益）；`batch_redo_papers.js` 做题循环捕获失效码后改用本模块（同一卷最多刷新 2 次） |
| **边界** | 只在硬证据 553649434 时触发；刷新失败（日常 Chrome 未开/未登录）抛明确错误交调用方，不无限重试；JWT/Cookie 不入库 |
| **相关文档** | gaodun-exam-api.md §1.2 token 自愈、video-processing.md 故障码、ISSUES I-013 |

---

### `cdp/api_do_paper.js` — 通用纯接口做卷（单卷，推荐入口）

| 项目 | 说明 |
|------|------|
| **用途** | 从 syllabus 自动解析指定卷的 csItemId/paperId/resourceId，交 gaodun_paper_core 完成取题→交卷→（主观）AI 批改→回查；零 UI 点选 |
| **用法** | `node scripts/cdp/api_do_paper.js <paperId 或 标题关键字> [最小停留秒]`；加 `--no-ai` 只交卷不做主观 AI 批改。如 `node scripts/cdp/api_do_paper.js 82749` |
| **可靠性** | ✅ 客观卷 + 主观大题卷（含顶层独立 type6）；退出码：0=严格满分或平台最优（未配 AI / AI 判分上限不阻断）、4 已交卷但未达平台最优（可补批）、1/2 未交卷成功或异常；**仅限可重做基础卷，冲刺模考排除** |
| **相关文档** | gaodun-exam-api.md §3 |

---

### `cdp/batch_redo_papers.js` — 批量纯接口补做到 100%

- 只读枚举 `papers_inventory.json`+`papers_audit.json` 中「非满分且非冲刺」的卷，逐张交 gaodun_paper_core：record→(首次 create-paper)→redo(取标准答案，平铺 type5 子题与顶层 type6，按 cpaBotType 分流)→按实际题量停留→submit 全量→交卷后并发=3 AI 批改（cs=6 三级补全→best-of-N→aiCeiling）→exam-report 回查；硬排除冲刺模考；`10462203 时间太短` 自动延长 20s；单张失败不中断，结果落 `data/_workspace/<profile>/papers/batch_result_<日期>.json`；卷间停 4s。
- 用法：`node scripts/cdp/batch_redo_papers.js`（dry-run 预览）｜加 `--go` 实跑｜`--go 82174 82175 ...` 指定 paperId｜加 `--no-ai` 只交卷不做主观 AI 批改。
- 支持客观题（type 1/2）与主观题（type5 套 type6、顶层独立 type6，交卷后 AI 批改冲满分）；三态结果：✅严格满分 / 🟡平台最优（题库未配 AI 或 AI 判分上限，答案均已正确提交）/ ⏺已交卷未满分；交卷成功即 progress=1，未达平台最优单独标记可补批，不中断批量。

---

### `cdp/refresh_inventory.js` — 刷新作业基线（只读，不交卷）

| 项目 | 说明 |
|------|------|
| **用途** | 拉 syllabus 枚举全部 paper → 对每张基础卷只读 record 审计（满分/平台最优/非满分/未提交/未做）→ 已交卷但分低的用 `paper/analysis` 只读复核 `inspectSubmitted`：配了 AI 的题须判满、或 cs=6 且"我方答案归一化后≈标准答案"才计 AI 判分上限，未配 AI 不阻断，真答错仍判非满分 → 章节自然顺序写出 `papers_inventory.json`（全量）与 `papers_audit.json`（待做）；硬排除冲刺模考。批量开工前先跑它刷新基线，避免重复做已完成卷 |
| **用法** | `node scripts/cdp/refresh_inventory.js [--profile <key>]`（课程 ID/syllabus 读 profile，缺省税法；约 1–2 分钟，每张间隔 250ms 低频只读） |
| **可靠性** | ✅ 已实测；分类判据见 gaodun-exam-api.md §2.1/2.2/2.10 |
| **相关文档** | gaodun-exam-api.md §2.1、§2.2、§2.2.1、§2.10；判分上限方法论见 guides/flaky-ai-judging.md |

---

### `cdp/fetch_user_space_courses.js` — 拉用户空间全课程清单（开工前盘点，只读）

| 项目 | 说明 |
|------|------|
| **用途** | JWT 直连 `ep-course/.../space/vcourse/pc`，一次返回账号在各 project 下购买/开通的全部课程，提取 vcourseId/saasCourseId/subjectId/开课状态/到期等稳定字段。新开科目（如会计）开工前先跑它拿 saasCourseId（=做题链路 courseId），替代手工找 URL |
| **用法** | `node scripts/cdp/fetch_user_space_courses.js [--print]`；精简台账 `data/_workspace/_account/user-space/account_courses.json`（覆盖式、带 fetchedAt，不入库、不传网盘），当次原始响应留同目录 `user_space_vcourse_<ts>.json` |
| **可靠性** | ✅ 已实测（2026-09-07 拉到 CPA 8 门，会计 saasCourseId=42656）；JWT 过期需先在登录态抓一次带 authentication 的请求刷新 jsonl |
| **相关文档** | gaodun-exam-api.md §1.3、§2.11 |

---

### `cdp/load_profile.js` — 课程档案卡读取器（跨课复用基础件）

| 项目 | 说明 |
|------|------|
| **用途** | 读 `config/courses/<key>.json`，为所有 cdp 脚本提供 courseId(saas)/vcourseId/syllabusId/平台/章组/路径，替代脚本内硬编码；导出 `loadProfile()/primaryIds()/listProfiles()`；换课用参数或环境变量 `GAODUN_COURSE_PROFILE`，缺省回退税法 |
| **用法** | `const {loadProfile,primaryIds}=require('./load_profile')`；命令行自检 `node scripts/cdp/load_profile.js [key]` |
| **可靠性** | ✅ 已建并自检通过（税法/会计两卡、缺省回退、坏卡报错）；Python 版 `knowledge/course_profile.py`、shell 版 `course_config.sh` 同源 |
| **相关文档** | parallel-toolkit-design.md §3、config/courses/README.md |

---

### `cdp/collect_paper_sources.js` — papers 原料只读补采

| 项目 | 说明 |
|------|------|
| **用途** | 线 B 原料补采：把已交卷的 116 张基础卷的题面/选项/标准答案/官方解析/知识点标签/全站正确率，经只读接口 record→paper/analysis 逐张拉出并精简落盘，供末期知识库生成。**纯只读**：不 redo、不建实例、不交卷、不耗 AI 权益、无副作用 |
| **用法** | `node scripts/cdp/collect_paper_sources.js [--all] [paperId...]`（默认只补本地缺失卷，`--all` 强制重拉） |
| **可靠性** | ✅ 高（已采 116 套 / 1296 题）；产物 课程 `data/_workspace/<profile>/papers/<id>.json` + `data/_workspace/<profile>/manifest/paper_index.json`（不入库，物理集中、按讲视图见 papers_view.py） |
| **相关文档** | gaodun-exam-api.md、standards 2.2.4、SOP 步骤1 |

---

### `cdp/download_lecture_notes.js` — 正课(glive)讲义 PDF 批量下载（免认证 CDN 直链）

| 项目 | 说明 |
|------|------|
| **用途** | 读 profile 的 glive syllabus children，取 lecture_note 资源的免认证 CDN 直链批量下载讲义 PDF 到课程 `原始资源/notes`；断点续下、字节校验，不依赖做题链路 |
| **用法** | `node scripts/cdp/download_lecture_notes.js [--profile <key>] [--dry]` |
| **可靠性** | ✅ 会计 44/44 零失败（2026-09-08） |
| **相关文档** | WORKFLOW §3、tools/video-processing.md |

---

### `cdp/ep3_course_outline.js` — 名师课 ep3(saasType13) 梯度/章节树/讲义清单基线（只读）

| 项目 | 说明 |
|------|------|
| **用途** | 纯 GET 拉 `ep-course/.../gradation/handout` + `student-learning/analysis/chapter`，输出「26 考季 4 梯度→章/节树(csItem/视频/题计数)→扁平化讲义清单」manifest；ep3 比正课多「梯度×多老师」两层 |
| **用法** | `node scripts/cdp/ep3_course_outline.js <courseId> [--all-season]`；产物 `data/_workspace/_account/ep3/manifest/<cid>.outline.json`（不入库） |
| **可靠性** | ✅ 名师会计 17244 实测：4 梯度/视频330/题206/讲义34（16 PDF+18 ZIP） |
| **相关文档** | `data/_workspace/_account/ep3-platform-probe.md`、`ep3/tickets-index.md` |

---

### `cdp/ep3_download_handouts.js` — 名师课 ep3 讲义/课件下载（CDN 直链 + 签名兜底）

| 项目 | 说明 |
|------|------|
| **用途** | 按 outline manifest 下载讲义：`simg01` CDN 直链为主（免认证、字节==fileSize），失败时 g-study batch-download 换 enclosure 签名链兜底；幂等、可按格式/限量试点 |
| **用法** | `node scripts/cdp/ep3_download_handouts.js <cid> [--format=pdf\|all] [--limit=N] [--dry]`；试点落 `data/_workspace/_account/ep3/downloads/<cid>/梯度/分类/`（正式课程库落位待 L1 方案） |
| **可靠性** | ✅ 3 份 PDF 逐字节一致、均为真 PDF（姚远172页/陈蓓蓓161页/词典65页） |
| **相关文档** | 同 ep3_course_outline |

### `cdp/ep3_download_videos.js` — 名师课 ep3 视频采集薄编排（枚举→取流→取key→解密→FHD mp4 + VTT字幕）

| 项目 | 说明 |
|------|------|
| **用途** | ep3(saasType13) 讲次视频端到端采集。syllabus 递归枚举讲次叶子 → getVideoInfo 拿 videoId → glive2-vod live/resource 拿 FHD m3u8+**平台 VTT 字幕 URL** → 复用 `capture_video_key.js`(CDP 播放取 key，按 videoId:res 缓存) → 复用 `download_decrypt.js`(分片下载+AES解密) → ffmpeg -c copy 出 1080P mp4 → 下 VTT 原始稿 `subtitle.vtt` 并转 `transcript.md`（**平台自带字幕，ep3 不需 FunASR 转写**）。薄编排不重复实现取 key/解密 |
| **用法** | 枚举：`node scripts/cdp/ep3_download_videos.js --course 17244 --parent-grad 23408 --grad 76232 --syllabus 76456 --list`；单讲：`--learning-url "<ep3 learning URL>" --out <dir>`；批量：同枚举参数去掉 `--list`、加 `--out <dir> [--res FHD] [--limit N] [--dual-teacher]`。断点续跑（mp4/transcript 存在即跳过）、单讲失败记 `.ep3cache/fails.json` 不中断批量 |
| **产出** | 每讲 `<NN_讲名>/{video.mp4(1080P),subtitle.vtt,transcript.md,meta.json}`，临时 `_work` 用完即清；`--dual-teacher` 时文件加老师前缀（姚远_/陈蓓蓓_，目录不分老师） |
| **可靠性** | ✅ 25考季样本(1585s/167.8MB/1080P/30段)+26考季批量 limit1(2337s/205.2MB/41段)双重端到端验证；枚举 25考季412/26考季408 与接口 total 吻合、chapterId 零缺失 |
| **相关文档** | `data/_workspace/_account/ep3-platform-probe.md` 第四/五轮、`ep3/tickets-index.md` EP3-05、`docs/development/tools/video-processing.md`（ep3 小节） |

---

### `cdp/throttled_ep3_download.sh` — 名师课多科目「节流下载」总调度（白天防风控 + 给前台留资源）

| 项目 | 说明 |
|------|------|
| **用途** | 多科目 ep3 视频批量下载的唯一推荐入口。只起 1 个生产者（`round_robin_prefetch.sh` 串行预取 key、全进程唯一操作 Chrome）+ 最多 `MAX_PARALLEL`(默认3) 路纯 `--consumer` 消费者（只从 keycache 读 key 下载、不碰 Chrome），结束一路自动补一路；全部子进程 `nice -n 20 taskpolicy -c utility` 降后台优先级，避免下载占满网络/磁盘把豆包挤死。任务队列在脚本内 `TASKS`，科目/阶段由 `config/ep3_subjects.json` 驱动，断点续跑 |
| **用法** | `bash scripts/cdp/throttled_ep3_download.sh`；夜间提速 `MAX_PARALLEL=6 bash scripts/cdp/throttled_ep3_download.sh`。日志 `data/_workspace/_account/ep3/logs/throttled_download.log` + 各 `consumer_*.log` |
| **关键坑** | 并发计数只能用消费者 PID 数组 + `kill -0`，**不能用 `jobs -rp`**（会把生产者计入、误顶满上限卡死第三路；macOS bash 3.2 无 `wait -n`）；消费者偶发启动卡死（CPU=0/零日志）直接 `kill -9`，调度器自动补位。分片并发分时段（白天12/夜间64）在 `ep3_download_videos.js` 内 |
| **相关文档** | `docs/development/tools/video-processing.md`「多科目节流调度」小节、`cdp/round_robin_prefetch.sh` |

### `cdp/round_robin_prefetch.sh` — ep3 取 key 生产者（轮询多科目×阶段、per-stage 独立 keycache、按需滚动预取）

| 项目 | 说明 |
|------|------|
| **用途** | 串行轮询指定科目（参数=科目名，缺省全部）的全部阶段，**只给当前有活跃消费者（pgrep 识别 `--stage X --consumer`）的阶段、每轮滚动预取 prefetch_count 个 key**（顺带下无需 key 的 VTT 字幕），不下载视频；与纯消费者解耦，避免多进程同时操作 Chrome 抢播放页。无消费者阶段不预取（防 token 闲置过期）。科目/profile/阶段/老师/缓存路径全部读 `config/ep3_subjects.json`，加科目不改脚本。⚠️ 缓存必须按「profile×阶段」分文件，同一 profile 多阶段共用一个缓存会被先跑阶段的缓存总条数连带饿死后跑阶段（2026-09-10 修复） |
| **用法** | `bash scripts/cdp/round_robin_prefetch.sh accounting tax strategy econlaw`（一般由 throttled 调度器自动拉起，不单独跑）；per-stage 缓存 `data/_workspace/_account/ep3/keycache/<profile>__<阶段>.json` |

---

### `cdp/ep3_diff_online_local.js` — 名师课「在线真视频 vs 本地实物」只读核对器

| 项目 | 说明 |
|------|------|
| **用途** | 走浏览器桥（connect_browser 页面内 fetch，绕 Tengine 405）只读 GET syllabus，按叶子内嵌 `resource.discriminator/video_id` 判真视频（剔除章测等非视频叶子），与本地实物比对出缺口/残缺；不下载、不取 key、不写课程库、不碰做题风控 |
| **用法** | `node scripts/cdp/ep3_diff_online_local.js`（参数见脚本头） |
| **相关文档** | `cdp/ep3_course_outline.js`、工程记忆 `workflow-ep3-vod-decryption` |

---

### `cdp/do_sprint_paper.js` — 冲刺模考 6 卷统一纯接口做卷入口（3 试卷 + 3 机考）

| 项目 | 说明 |
|------|------|
| **用途** | 冲刺模考专用：record→create/redo→submit→AI 批改（correct-ai/cpa）→exam-report 全接口闭环；客观题用 questionAnswer.answer、主观用 core 的 `cleanSubjectiveAnswer`（算式为主体+点拨精简为「依据：」+多小问分点，交卷与首次 AI 批改同版），按真实记分判定满分（aiPoints），cs=2 不再虚报满分 |
| **用法** | `node scripts/cdp/do_sprint_paper.js s1|s2|s3|m1|m2|m3`（兼容旧参数 1/2/3）；机考自动带 `origin=https://mock-cpa.gaodun.com`；结果落 `data/_workspace/<profile>/papers/exam_result_<paperId>_<ts>.json` |
| **6 卷映射** | s1/s2/s3=86722/86723/86724（glivepro 试卷）；m1/m2/m3=86726/86727/86728（mock-cpa 机考，与试卷同题） |
| **可靠性** | ✅ 高；免费可达最优=客观全对+AI 题尽量满，未配 AI 题（cpaBotType=0）须人工批改、本流程不购买 |
| **相关文档** | gaodun-exam-api.md（冲刺模考侦查过程报告存 `data/_workspace/<course>/task-reports/`，不入库） |

### `cdp/run_redo_all.sh` — 冲刺 6 卷批量重做入口（顺序跑、独立日志、末尾汇总）

| 项目 | 说明 |
|------|------|
| **用途** | 修复答案生成逻辑后对 6 卷批量重做补全答案；顺序 s1→s2→s3→m1→m2→m3（避免并发风控），每卷调 `do_sprint_paper.js`，末尾汇总各卷最新 exam_result 分数与 answerGaps |
| **用法** | `bash scripts/cdp/run_redo_all.sh`，日志 `logs/sprint_redo_all_<ts>.log`，建议后台 `nohup bash scripts/cdp/run_redo_all.sh > /tmp/redo.log 2>&1 &` |
| **验收线** | 6 卷全部 `answerGaps=0`（答案完整性校验门无缺口）、`objectiveAllRight=true`、`wrong=[]`、`failed=0` |
| **相关** | do_sprint_paper.js、gaodun_paper_core.js（cleanSubjectiveAnswer/pruneBasis/splitAskedBlocks/countAskedSubs）、exam-workflow.md §4.3.1 |

---

## 十、飞书知识库同步（新空间 8 课模型，脚本位于 `scripts/knowledge/`）

> 现役权威链路（2026-09-19 重构，替代旧 `scripts/sync_wiki_new.sh`、`auto_sync_all.*`、`verify_sync_completeness.py`，旧件已移入 `.trash/`）。
> **树模型**：知识空间「CPA备考知识库」→ 根「课程库」→ **全称课程容器**（容器本身=课程首页）→ 章 / 全局篇 → 知识点。
> 一门课一张配置卡 `config/courses/<profile>.json`（`wiki.spaceId` / `rootParentNodeToken` / `courseNodeToken` / `courseObjToken`），全程 `--profile` 驱动，换课只换卡不改代码。完整 SOP 见 `docs/development/guides/wiki-sync-sop.md`。

### `knowledge/build_tree.py` — 建课程容器 + 树结构（只建结构、不写正文）

| 项目 | 说明 |
|------|------|
| **用途** | 按配置卡 `primaryCourse.name` 在「课程库」根下幂等确保全称课程容器（按标题复用），回写 `wiki.courseNodeToken/courseObjToken` 到配置卡，再在内容器建章（章目录名，写章 README 节点）+ 章下知识点 + 知识详解根目录全局篇；根 `README.md` 是课程首页、不建子节点。映射追加 `data/_workspace/<profile>/logs/wiki_node_map.tsv`（title/node/obj/parent），按 map 幂等可重跑 |
| **用法** | `python3 scripts/knowledge/build_tree.py <profile>`（推荐，全自动）；显式课程目录可加第 2 参；旧用法 `<profile> <parent_token> <course_dir>` 直接在指定父节点下建树、不建容器 |
| **前置坑** | 换空间重建前，先把旧空间遗留的 `data/_workspace/<profile>/logs/wiki_node_map.tsv` 归档改名（如 `.oldspace.tsv`），否则按标题幂等会复用老空间 token |
| **相关** | wiki-sync-sop.md、course_profile.py、lark-cli `wiki +node-list/+node-create` |

---

### `knowledge/resync_wiki_content.py` — 正文覆盖（含课程首页，只写内容不建节点）

| 项目 | 说明 |
|------|------|
| **用途** | 把本地知识详解 markdown 覆盖写入 map 对应飞书文档；**课程首页**（知识详解根 `README.md`）写入课程容器 obj（done 名 `__COURSE_HOMEPAGE__.done`）。写入前自动剥离顶部 OKF frontmatter，相对链接经 `wiki_link_resolve.py` 转 `<cite>`；每篇成功落 `logs/resync_done/<safe标题>.done` 断点续跑，`--dry-run` 预检、`--force` 全量重刷 |
| **用法** | `python3 scripts/knowledge/resync_wiki_content.py --profile <profile> [--dry-run] [--only 片段] [--no-homepage] [--course-obj <obj>]`；也支持 `--course-dir/--map` 显式指定（无合法卡时用） |
| **限流** | 检测到转发代理 `invalid_response` 立即失败交外层换新进程；`RESYNC_MAX_NEW` 控制单进程新写上限（实测每进程 20 篇 0 失败） |
| **相关** | run_resync_batches.sh、sync_with_restart.sh、wiki_link_resolve.py、feishu-api.md |

---

### `knowledge/run_resync_batches.sh` / `knowledge/sync_with_restart.sh` — 分批换新进程驱动（绕转发代理两层限流）

| 项目 | 说明 |
|------|------|
| **用途** | Worker Supervisor 模式：拉起 python worker（新代理会话），worker 写满 `RESYNC_MAX_NEW`（默认 20）篇主动退出后，Supervisor **立即拉起新 worker**（不长休眠）；连续 `RESYNC_FAIL_MAX`（默认 5）次无进展重启才短休 `RESYNC_COOLDOWN`（默认 30s）。总篇数自动 = map 行数 + 1（课程首页），done 数达标 Supervisor 自退。done 列表落 `logs/resync_done/*.done` 持久化，任意中断/重入不丢、不重复耗配额 |
| **用法** | `bash scripts/knowledge/run_resync_batches.sh <profile> [每轮新写=20]`；旋钮走环境变量 `RESYNC_FAIL_MAX=5 RESYNC_COOLDOWN=30`；`bash scripts/knowledge/sync_with_restart.sh <profile> [max_new] [interval] [batch_pause] [batch_rest]`（旧备用驱动） |
| **相关** | resync_wiki_content.py、feishu-api.md（限流根因与参数） |

---

### `knowledge/verify_wiki_tree.py` / `knowledge/verify_wiki_content.py` — 只读双验收（一门一验收）

| 项目 | 说明 |
|------|------|
| **用途** | 树核验：本地知识详解 / 飞书容器树 / map 三方标题集合、node、parent 完全一致，计数动态推导（不写死 169/32），无重复/错挂/顶层异常；正文回读：逐篇全新进程 `docs +fetch`，判级 OK/THIN(<300)/EMPTY(<100)/FETCH_FAIL，出 `logs/content_readback.tsv`，`--refill` 只补拉非 OK 篇 |
| **用法** | `python3 scripts/knowledge/verify_wiki_tree.py <profile>`；`python3 scripts/knowledge/verify_wiki_content.py <profile> [--refill]`（退出码非 0 即验收不通过） |
| **相关** | wiki-sync-sop.md（验收门）、lark-cli `wiki +node-list` / `docs +fetch` |

---

### `wiki_link_resolve.py` — 同步飞书前的内部链接解析过滤器（stdin→stdout）

| 项目 | 说明 |
|------|------|
| **用途** | 把本地同目录相对链接 `[标题](./标题.md)` 解析为飞书内部文档引用 `<cite type="doc" doc-id="obj_token"/>`（obj_token 强绑定、可校验坏链）；管道过滤器，由 resync 同步链路调用（须显式传 `WIKI_MAP`） |
| **用法** | `cat 正文.md | python3 scripts/wiki_link_resolve.py`（一般由 resync 自动调用） |
| **相关文档** | `docs/development/guides/wiki-link-verification-sop.md` |

---

## 十一、知识详解生成（8个，位于 `scripts/knowledge/`）

> 按官方知识点聚合生成知识详解 md 的核心生产脚本。流程：collect_point_questions（按知识点收题）→ render_point_qa（渲染题答解析）→ organize_user_notes（整理学员补充）→ assemble_point（组装成篇）。
> 用户笔记子链：`cdp/collect_user_notes.js`（按 questionId 拉公开笔记到 notes-raw/all_notes.jsonl）→ `knowledge/build_notes_mapping.py`（试卷标题解析知识点、映射到知识详解篇并剥身份字段）→ `knowledge/organize_user_notes.py`（四分类、Top5、写入「四、学员补充」）。

### `knowledge/course_profile.py` — 课程档案卡读取器（跨课复用基础件）

| 项目 | 说明 |
|------|------|
| **用途** | 读 `config/courses/<key>.json`，为 knowledge 脚本提供课程目录/章组名/科目信息，替代 `build_course_overview.py` 等脚本内硬编码；导出 `load_profile()/primary_ids()`；换课用参数或 `GAODUN_COURSE_PROFILE`，缺省回退税法 |
| **用法** | `from course_profile import load_profile`；命令行自检 `python3 scripts/knowledge/course_profile.py [key]` |
| **可靠性** | ✅ 已建并自检通过；Node 版 `cdp/load_profile.js`、shell 版 `course_config.sh` 同源 |
| **相关文档** | parallel-toolkit-design.md §3、config/courses/README.md |

---

### `knowledge/collect_point_questions.py` — 按知识点收集题目

| 项目 | 说明 |
|------|------|
| **用途** | 从 papers 原料中按官方知识点标签聚合题目，客观题取顶层、主观题下钻 subQuestionList 小问层 |
| **用法** | `python3 scripts/knowledge/collect_point_questions.py` |
| **可靠性** | ✅ 高（92 知识点全覆盖，含小问层知识点等价归一） |
| **相关文档** | ADR-012、knowledge-detail-build-sop.md |

---

### `knowledge/render_point_qa.py` — 题答解析渲染

| 项目 | 说明 |
|------|------|
| **用途** | 把收集到的题目渲染为「三、题答解析」节，客观题（答案+解析）与主观题（分点答案+点拨）两型；题量为 0 的分类整段不渲染（`if groups:` 保护） |
| **用法** | `python3 scripts/knowledge/render_point_qa.py` |
| **可靠性** | ✅ 高（已根治 0 空小节问题；与 assemble_point.py 的 if groups 逻辑对齐） |
| **相关文档** | ADR-012、KNOWLEDGE_BASE_TEMPLATE.md |

---

### `knowledge/build_notes_mapping.py` — 用户笔记→知识点篇 映射（通用，替代一次性过程件）

| 项目 | 说明 |
|------|------|
| **用途** | 衔接 collect_user_notes.js 与 organize_user_notes.py：扫真题面（跳过 batch_result 汇总），由试卷标题解析知识点、与知识详解现有篇名精确匹配，产出 organize 所需的 qid_to_kps / kp_to_file / notes_by_knowledge_point / unmatched_kps；映射层即剥除学员身份字段（白名单只留 noteContent/赞数/时间/papers）。聚合卷/近义名经 `notes-raw/alias.json`（过程件）别名到一篇或多篇，代码不写死任何课程 |
| **用法** | `python3 scripts/knowledge/build_notes_mapping.py --profile <key>`（缺省读 GAODUN_COURSE_PROFILE/税法；笔记取 `data/_workspace/<key>/notes-raw/`，可用 `USER_NOTES_RAW_DIR` 覆盖）。知识详解篇未生成的章节自然落 unmatched，篇章补齐后重跑即可，不丢原始笔记 |
| **可靠性** | ✅ 会计试跑：现有 66 篇中 60 篇挂上笔记（其余本无公开笔记），unmatched 全为未生成章/章级卷 |
| **相关文档** | ADR-013、knowledge-detail-build-sop.md、collect_user_notes.js、organize_user_notes.py |

---

### `knowledge/organize_user_notes.py` — 用户笔记整理（四分类+去元数据）

| 项目 | 说明 |
|------|------|
| **用途** | 把原始用户笔记（含学员名/点赞数/日期）按四分类（记忆口诀/易错点辨析/解题技巧/知识补充）整理，每类按赞 Top5 筛选，输出纯知识内容（**不输出学员名/点赞数/用户ID/日期**，元数据仅保留在原始资料中用于溯源） |
| **用法** | `python3 scripts/knowledge/organize_user_notes.py`（课程目录/笔记目录默认读 profile，缺省税法，笔记取 `data/_workspace/<profile>/notes-raw/`；可用 `GAODUN_COURSE_PROFILE` 或 `COURSE_LOCAL_ROOT`/`USER_NOTES_RAW_DIR` 覆盖） |
| **可靠性** | ✅ 高（744 条覆盖 92 篇；已彻底移除元数据输出） |
| **相关文档** | ADR-013、collect_user_notes.js |

---

### `knowledge/assemble_point.py` — 知识点篇组装（四节合一）

| 项目 | 说明 |
|------|------|
| **用途** | 把知识拆解/考试指导/题答解析/学员补充四节组装为一篇知识点 md，写入课程「知识详解/」对应章节目录；`if groups:` 保护空分类不渲染 |
| **用法** | `python3 scripts/knowledge/assemble_point.py` |
| **可靠性** | ✅ 高（92 篇+2 全局篇，已用于税法课全量生成） |
| **相关文档** | ADR-012、knowledge-detail-build-sop.md |

---

### `knowledge/ep3_build_manifest.py` — 名师课(ep3)知识详解 manifest 骨架构建器

| 项目 | 说明 |
|------|------|
| **用途** | ep3 题答受风控、没有 papers 官方标签，走确定性替代：章归属取讲次 meta 的 chapterPath 第一级、知识点由讲次目录名去 `NN_`/分P后缀聚合，产出与正课同构的 course-manifest 骨架 |
| **用法** | `python3 scripts/knowledge/ep3_build_manifest.py`（参数见脚本头） |
| **相关文档** | 知识生成 SOP §2.1（manifest 读取口径）、knowledge-detail-build-sop.md |

---

### `knowledge/batch_build_chapter.py` — 章节级知识详解批量构建器

| 项目 | 说明 |
|------|------|
| **用途** | 一次处理整章：`list`（列知识点与题量）/ `template`（生成带考点的头部模板）/ `assemble`（批量组装题答）/ `frontmatter`（批量加 OKF frontmatter） |
| **用法** | `python3 scripts/knowledge/batch_build_chapter.py <list\|template\|assemble\|frontmatter> ...` |
| **相关文档** | knowledge-detail-build-sop.md、知识生成 SOP §2.12 |

---

## 脚本使用原则

1. **先查本文档再用脚本**：执行任务前，先在本文档中找到对应脚本，了解用途、用法、可靠性
2. **优先用脚本，不手动写命令**：已有脚本的功能，必须用脚本，不要手动写JavaScript或curl
3. **做题必须用脚本**：`cdp/api_do_paper.js`（单卷）/ `cdp/batch_redo_papers.js`（批量）/ `cdp/do_sprint_paper.js`（冲刺模考），纯接口主链路，禁止手动 UI 点选
4. **批量任务在iTerm中运行**：`transcribe_all.sh`、`batch_ocr.sh`、`compress.sh`（批量模式）必须在iTerm中运行，不要后台运行
5. **新增脚本必须更新本文档**：新增脚本时，必须在本文档对应分类中添加说明（用途/用法/可靠性/相关文档）

---

## 维护规则

1. **新增脚本时**：在本文档对应分类中添加条目，说明用途、用法、可靠性、相关文档
2. **修改脚本时**：更新本文档中对应条目的用法和可靠性说明
3. **删除脚本时**：从本文档中移除条目，并检查是否有其他文档引用该脚本
4. **定期检查**：每次大阶段完成后，检查本文档与实际脚本是否一致（`ls scripts/` 对比）

---

*本文档是项目脚本的唯一权威索引，所有新增/修改/删除脚本时必须同步更新。*
