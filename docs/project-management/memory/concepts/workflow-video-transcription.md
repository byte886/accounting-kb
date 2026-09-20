---
type: Workflow
title: 视频压缩与音频转写链路
description: 课程视频用 H.265/HEVC CRF30 preset fast 压缩（约 8:1，hvc1 保证 Apple 可播）；音频用本地 FunASR SenseVoiceSmall + fsmn-vad 转写（零成本、不上云）；产物归原始资源层。
tags: [video, ffmpeg, h265, transcription, funasr, workflow]
sources:
  - id: adr-002
    resource: ../../decisions/ADR-002-视频压缩标准.md
    title: ADR-002 选择 H.265 CRF30 作为视频压缩标准
  - id: adr-003
    resource: ../../decisions/ADR-003-音频转写方案.md
    title: ADR-003 选择 FunASR SenseVoiceSmall 作为音频转写方案
  - id: adr-018
    resource: ../../decisions/ADR-018-名师课ep3取流解密平台路由与平台字幕替代转写.md
    title: ADR-018 名师课 ep3 用平台 VTT 字幕替代本地转写
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 视频压缩与音频转写链路

## 一句话结论
原始课程视频（单个约 1.5–2.5GB）统一用 **H.265/HEVC CRF30 preset fast** 压缩到约 1/8（2.5h ≈ 200MB）再归档；需要文字稿时用**本地 FunASR SenseVoiceSmall + fsmn-vad** 转写，零 API 成本、音频不上云。两者产物都属于"原始资源层"（见 [三层解耦](architecture-knowledge-paradigm.md)）。

## 视频压缩（ADR-002，用户已验证质量）
```bash
ffmpeg -i input.mp4 \
  -c:v libx265 -crf 30 -preset fast \
  -c:a aac -b:a 96k \
  -tag:v hvc1 -movflags +faststart \
  output.mp4
```
- **为什么是它**：比 H.264 省 40–50% 体积；CRF30 在课件场景文字清晰、头像略糊但不影响学习；`-tag:v hvc1` 保证 iPhone/Mac 原生播放；AAC 96k 够人声。
- 20 核 CPU 上 preset fast 约 10 倍速，单个 2.5h 视频约 15 分钟。
- 选型对比：H.264 CRF28（约 4:1，兼容好但大）、H.265 CRF28（约 6:1，质量更好但大）、AV1（约 10:1 但极慢、兼容差）均未采用。

## 音频转写（ADR-003）
- **栈**：FunASR SenseVoiceSmall（中文识别）+ fsmn-vad（语音活动检测），跑在本地虚拟环境 `.venv-transcribe`（已 gitignore、不入库）。
- **为什么是它**：中文准确率高、约 5–10 倍速、完全本地免费、隐私不上云；代价是主要支持中文、标点分段需后处理、专业术语可能要自定义词典、换机需重建 venv。
- 备选：Whisper/faster-whisper（慢/需 GPU）、阿里云/讯飞（10–25 元/小时）、得到大脑（会员制）均未采用。

## 平台分流：本链路只用于正课 glive，名师课 ep3 不走 FunASR
本压缩/转写链路针对**正课 glive（saasCourseType=16）**。**名师课 ep3/epiphany（saasCourseType=13）平台自带 VTT 字幕**，直接下载 `result.subtitle` 即得文字稿、**不做 FunASR 转写**，且正式采集为 FHD-1080P、分片本就是 h264/aac 用 ffmpeg `-c copy` 不再重压；取 key 走 CDP Worker 截获，是另一条独立链路，见 [名师课 ep3 视频取流解密与平台字幕](workflow-ep3-vod-decryption.md) 与 [ADR-018](../../decisions/ADR-018-名师课ep3取流解密平台路由与平台字幕替代转写.md)。判断走哪条先看课程的 saasCourseType（见 [课程 profile 对照](reference-course-profiles.md)）。

## 归位与边界
- 压缩视频、音频、转写文稿都是**原始资源**，归本地大文件目录 + 百度网盘镜像，不进 Git、不直接同步飞书。
- 转写文本只是知识来源之一，进入知识详解前仍要走"按知识点聚合 + 元数据剥离"。
- 详细操作与脚本：`docs/development/tools/video-processing.md`、`docs/development/tools/transcription.md`；压缩 `code/scripts/compress.sh`，转写主管道 `code/scripts/transcribe_pipeline.py`（另有 transcribe_one/all/parallel 等 shell 包装；旧名 transcribe.py 已按 snake_case 更名）。

## 来源与下钻
- [ADR-002 视频压缩标准](../../decisions/ADR-002-视频压缩标准.md)
- [ADR-003 音频转写方案](../../decisions/ADR-003-音频转写方案.md)
- 产物归属见 [四地存储分工](architecture-storage-layout.md) 与 [三层解耦](architecture-knowledge-paradigm.md)。
