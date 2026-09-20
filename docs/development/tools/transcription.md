# 音频转文字

> **文档类型**：Task（操作指南）
> **更新频率**：工具变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档记录高顿课程视频的音频转文字方案，包括 FunASR 环境配置、性能数据、脚本使用和已知问题。

## 1. 方案选型

**方案：阿里 FunASR（SenseVoiceSmall），开源本地方案，0成本**

| 对比项 | FunASR SenseVoiceSmall | Whisper large-v3 | 阿里云录音文件识别 |
|--------|------------------------|-------------------|---------------------|
| 中文 CER | 8-10% | 22-31% | 5-8% |
| 成本 | 免费（本地） | 免费（本地） | 约1.2元/小时 |
| 速度（CPU） | ~15x 实时（VAD加速） | ~1x 实时 | 异步（5-10分钟） |
| 标点恢复 | 内置 | 内置 | 内置 |
| 说话人分离 | 需额外模型 | 需额外模型 | 支持 |

选择理由：
- 用户有讲义 PDF，不需要 OCR，只做音频转文字
- 开源本地，0成本，数据不上传
- 中文识别效果优于 Whisper
- VAD 加速后速度快（~15x 实时）

## 2. 环境配置

### 2.1 系统要求

- macOS x86_64（Apple Silicon 需额外配置）
- Python 3.12（Homebrew）
- ffmpeg（音频提取）

### 2.2 依赖版本

| 包 | 版本 | 说明 |
|----|------|------|
| torch | 2.2.2 | macOS x86_64 最高可用版本 |
| numpy | 1.26.4 | 不可升级到 2.x（funasr 兼容性） |
| funasr | 1.4.3 | 阿里语音识别框架 |
| modelscope | 最新 | 模型下载 |

### 2.3 虚拟环境

```bash
cd transcription
python3.12 -m venv venv
source venv/bin/activate
pip install torch==2.2.2 numpy==1.26.4 funasr==1.4.3 modelscope
```

### 2.4 模型缓存

- SenseVoiceSmall：`~/.cache/modelscope/models/iic--SenseVoiceSmall/`（936MB）
- VAD 模型：`iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- 首次运行自动下载，后续离线使用

## 3. 性能数据

**测试环境**：Mac Pro i5-13600KF / 128GB / 纯 CPU

| 模式 | 10分钟音频耗时 | 速度 | 2.5小时视频预估 |
|------|----------------|------|-----------------|
| 不用 VAD | 190秒 | 3.1x 实时 | ~48分钟 |
| 用 VAD（fsmn-vad, max_single_segment_time=30000） | 38.5秒 | 15.6x 实时 | ~10分钟 |
| 模型加载 | 3-4秒 | - | - |

**VAD 加速原理**：
- 先用 VAD 检测语音段，跳过静音段
- 每段最长 30 秒，避免长音频内存溢出
- 课件视频通常有大量停顿（老师思考、学生互动），VAD 加速效果显著

## 4. 转写脚本

### 4.1 单视频转写

```bash
cd transcription
source venv/bin/activate
python transcribe_pipeline.py <视频路径> <输出目录>
```

脚本流程：
1. 提取音频（ffmpeg 16kHz mono WAV）
2. VAD 分段（fsmn-vad）
3. 逐段转写（SenseVoiceSmall）
4. 后处理（去除特殊标记如 `<|zh|><|HAPPY|>`）
5. 输出 markdown + json

输出位置：`输出目录/video/transcript.md` 和 `transcript.json`

### 4.2 批量转写

```bash
bash code/scripts/transcribe_all.sh   # 按 GAODUN_COURSE_PROFILE 转写整门课，已存在 transcript 自动跳过
```

**重要**：批量脚本需在 iTerm 中运行，可开多个窗口并行处理不同视频。

脚本特性：
- 断点续传：已存在 transcript.md 且 >100 字节的视频自动跳过
- 实时进度显示：当前第几个/总共几个、已用时间、预计剩余时间
- 完成后输出汇总报告

### 4.3 已知 Bug（已修复）

**问题**：批量脚本复制路径错误，导致转写结果丢失。

**原因**：`transcribe_pipeline.py` 输出到 `输出目录/video/transcript.md`，但批量脚本检查的是 `输出目录/transcript.md`（少了 `video/` 层）。

**修复**：批量脚本中检查路径改为 `$TEMP_OUTPUT/video/transcript.md`。

## 5. 输出格式

### 5.1 Markdown 格式

```markdown
# video

> 自动转写 | 时长2.6小时 | 转写耗时10.6分钟 | 速度14.7x实时 | 约51769字

## 第1段

[转写文本...]

## 第2段

[转写文本...]
```

### 5.2 JSON 格式

包含原始转写结果、元信息、分段信息。

## 6. 已知问题

| 问题 | 影响 | 解决方案 |
|------|------|----------|
| 开头有特殊标记 `<\|zh\|><\|HAPPY\|><\|Speech\|>` | 文字稿开头有乱码 | 脚本已后处理去除 |
| 个别同音错误（如"概数"应为"概述"） | 专业术语可能识别错误 | 结合讲义 PDF 校对 |
| SenseVoice 不输出字级时间戳 | 无法精确定位到秒 | 知识库不需要精确时间轴，按语义分段即可 |
| 批量脚本复制路径错误 | 转写结果丢失 | 已修复，需重跑 |

## 7. 成本对比

| 方案 | 13个视频（约30小时）成本 | 说明 |
|------|---------------------------|------|
| FunASR 本地 | 0元 | 约2小时（15x实时），纯CPU |
| Whisper 本地 | 0元 | 约30小时（1x实时），太慢 |
| 阿里云录音文件识别 | ~36元 | 1.2元/小时，异步处理 |
| 得到大脑会员 | 35元/月 | 不限量，但需上传到第三方 |

**选择 FunASR 本地**：0成本，速度快，数据不上传，满足需求。

## 8. 参考资料

- [FunASR GitHub](https://github.com/modelscope/FunASR)
- [SenseVoiceSmall Model](https://www.modelscope.cn/models/iic/SenseVoiceSmall)
- [FunASR 中文语音识别教程](https://github.com/modelscope/FunASR/blob/main/docs/tutorial/README.md)
