# OCR 文字提取

> **文档类型**：Task（操作指南）
> **更新频率**：工具变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档记录高顿课程 PDF 讲义的 OCR 文字提取方案。2026-09-20 起，默认引擎从 macOS Vision 切换为 **RapidOCR（PP-OCRv6，ONNX Runtime）**，跨平台、pip 一条命令装、中文/数字混排更准。

## 1. 背景

高顿课件 PDF 多为**图片型 PDF**（PPT 导出为图片），无法直接提取文字，需 OCR。

## 2. 现行方案：RapidOCR PP-OCRv6

### 2.1 工具链

- **OCR 引擎**：[RapidOCR](https://github.com/RapidAI/RapidOCR)（PP-OCRv6 的 ONNX Runtime 封装，CPU 跑，免费开源）
- **PDF 转图片**：PyMuPDF（200 DPI）
- **主脚本**：`scripts/ocr/ocr_pdf_rapid.py`
- **批量入口**：`scripts/batch_ocr.sh`（单本 PDF）、`scripts/ocr/run_ocr_all.sh`（整门课）
- **Python 环境**：项目根 `.venv-ocr/`（Python 3.12）

### 2.2 环境搭建（一次性）

```bash
cd <项目根>
/usr/local/bin/python3.12 -m venv .venv-ocr
.venv-ocr/bin/pip install rapidocr onnxruntime pymupdf
```

模型首次运行自动下载到 `.venv-ocr/lib/python3.12/site-packages/rapidocr/models/`（PP-OCRv6 det+rec+cls，约 15MB），无需手动配。

> 为什么用 3.12 而不是系统 3.14：onnxruntime 暂不支持 Python 3.14。

### 2.3 用法

单本 PDF：
```bash
bash scripts/batch_ocr.sh "<讲义.pdf>" [输出目录]
# 等价于：
.venv-ocr/bin/python scripts/ocr/ocr_pdf_rapid.py "<讲义.pdf>" --out "<讲义>_OCR.md"
```

整门课批量：
```bash
COURSE_PROFILE=ep3-econlaw-2026 bash scripts/ocr/run_ocr_all.sh [--dry]
```

### 2.4 性能（实测，2026-09-20）

| 指标 | RapidOCR PP-OCRv6 |
|------|-------------------|
| 速度 | ~1.5 秒/页（M 系列 CPU，200 DPI） |
| 模型加载 | 首次 ~2s，后续进程内 0.2s |
| 中文/数字混排 | 优于 macOS Vision |
| 跨平台 | macOS / Linux / Windows 均可 |
| 断点续跑 | `<pdf名>.pages/<N>.txt`（PDF 同目录，跨 PDF 不串） |

### 2.5 输出格式

与旧版一致：
```markdown
# <讲义名>（OCR文字稿）

> 自动OCR识别 | 共N页 | 使用 RapidOCR PP-OCRv6 | DPI 200

---
## 第1页

<识别文本>

---
## 第2页
...
```

后处理："高顿教意/教肓"→"高顿教育"。

## 3. 与旧方案对比

| 维度 | macOS Vision（旧，2026-09 前） | RapidOCR PP-OCRv6（现行） |
|---|---|---|
| 安装 | 系统自带，需 swiftc 编译 | pip 一条命令 |
| 速度 | ~1s/页 | ~1.5s/页 |
| 中文 | 好 | 更好（数字/混排） |
| 跨平台 | 仅 macOS | 全平台 |
| 脚本 | `ocr_vision.swift`（已退役保留） | `ocr_pdf_rapid.py` |

旧 `scripts/ocr/ocr_vision.swift` 保留备查，不再默认调用。

## 4. 表格/公式/图表

RapidOCR 默认只出文字，不保留表格结构。遇到复杂表格/公式/图表：
- 用全局技能 `work-doc-extract` 的 PP-StructureV3 或 PaddleOCR-VL 兜底
- 或直接用 AI 视觉模型描述该页

## 5. 其他格式

| 格式 | 工具 |
|---|---|
| PPTX | python-pptx |
| DOCX | python-docx |
| XLSX | openpyxl |

## 6. 已知坑

- **Python 版本**：必须用 3.12 venv，系统 3.14 装不上 onnxruntime
- **后台跑**：长任务用 `nohup ... &` + `tail -f`，Python 进程比 swift 二进制稳
- **断点缓存**：`<pdf名>.pages/` 目录在 PDF 同目录，会被 git 忽略（见 .gitignore）
