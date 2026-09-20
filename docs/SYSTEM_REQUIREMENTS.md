# 系统要求与环境配置

> **文档类型**：Reference（参考资料）
> **更新频率**：环境配置变更时
> **维护者**：AI自动维护
> **读者**：AI代理+人类

本文档详细说明项目的系统要求、支持的平台、工具依赖、硬件要求、开发与测试环境，以及迁移到新电脑的步骤。

> README.md 中只保留摘要和链接，详细内容见本文档。

---

## 一、平台兼容性

> ⚠️ **项目主要在 macOS 下开发和运行**，部分工具依赖 macOS 原生功能。如需在其他平台运行，需替换对应工具。

### 1.1 支持的平台

| 平台 | 支持状态 | 说明 |
|------|---------|------|
| **macOS 12+** | ✅ 完全支持 | 主要开发和运行环境 |
| Linux | ⚠️ 部分支持 | 需替换 OCR 方案，终端工具不同 |
| Windows | ⚠️ 部分支持 | 需替换 OCR 方案，bash 脚本需 WSL |

### 1.2 Mac 专用工具（不可直接跨平台）

| 工具 | 用途 | 替代方案（其他平台） |
|------|------|---------------------|
| **macOS Vision 框架** | PDF/图片 OCR 文字提取 | Tesseract OCR / PaddleOCR |
| **iTerm2** | 批量任务前台运行（实时进度） | GNOME Terminal / Windows Terminal |
| **textutil** | DOC/DOCX 文字提取 | python-docx / pandoc |
| **AppleScript** | iTerm 窗口控制 | 无直接替代 |
| **bash 3.2** | 脚本运行环境（Mac自带） | 升级到 bash 4+ 或调整脚本 |

### 1.3 跨平台工具（可直接使用）

| 工具 | 用途 |
|------|------|
| ffmpeg | 视频下载、解密、压缩、验证 |
| Playwright CLI | 浏览器自动化 |
| Node.js | HLS 分片下载脚本 |
| Python 3.10+ | 转写、OCR批处理、网盘上传 |
| FunASR / faster-whisper | 音频转文字 |
| 百度网盘 PCS API | 文件上传 |

---

## 二、硬件要求

- **CPU**：建议 8 核以上（视频压缩和音频转写耗时较长）
- **内存**：建议 16GB 以上（转写模型加载需要）
- **磁盘**：建议 500GB 以上（原始视频 + 压缩视频 + 转写中间文件）
- **网络**：稳定的互联网连接（视频下载、网盘上传、飞书API）

---

## 三、开发与测试环境（当前配置）

> 项目目前主要在以下 Mac 环境下开发和测试，其他环境可能存在兼容性问题。

### 3.1 系统信息

- **操作系统**：macOS 15.7.8 (Sequoia)
- **BuildVersion**：24G824
- **Shell**：bash 3.2.57(1)-release（Mac自带版本）

### 3.2 硬件配置

- **机型**：Mac Pro
- **CPU**：13th Intel Core i5-13600KF @ 3.5 GHz（14核20线程）
- **内存**：128 GB
- **磁盘**：3.7TB NVMe（可用3.1TB）

### 3.3 已安装工具与版本

> 2026-09-01 真机命令核对；版本随环境升级，以 `工具 --version` 实测为准。

| 工具 | 版本 | 安装方式 |
|------|------|---------|
| ffmpeg | 8.1.2 | Homebrew |
| Node.js | v22.23.2 | Homebrew |
| npm | 10.9.8 | 随Node.js |
| Python | 3.14.7 | Homebrew |
| pip | 26.2.1 | 随Python |
| git | 2.45.2 | Xcode Command Line Tools |
| Homebrew | 6.0.20 | 官方安装脚本 |
| Google Chrome | 最新版 | 官方下载 |
| iTerm2 | 最新版 | 官方下载 |

### 3.4 Mac 特定设置

- **OCR**：使用 macOS Vision 框架（系统原生，无需额外安装）
- **终端**：批量任务必须在 iTerm2 前台运行，禁止后台运行
- **安全设置**：允许 Apple 事件中的 JavaScript（iTerm 控制需要）
- **Playwright**：使用 Extension 模式附加已运行的 Chrome，不使用 CDP 模式

### 3.5 注意事项

- 项目在 Intel Mac 上测试通过，Apple Silicon (M1/M2/M3) 可能需要额外配置（如 FunASR 环境）
- macOS 版本低于 12 可能不支持部分 Vision 框架功能
- bash 脚本基于 bash 3.2 编写，在 bash 4+ 上可能需要调整

---

## 四、环境检查命令

在开始任务前，运行以下命令检查环境：

```bash
# 检查系统版本
sw_vers

# 检查硬件配置
system_profiler SPHardwareDataType

# 检查关键工具版本
ffmpeg -version
node --version
python3 --version
git --version

# 检查磁盘空间
df -h /

# 检查项目目录结构
bash code/scripts/check_directory_structure.sh
```

---

## 五、迁移到新 Mac 的步骤

1. 克隆仓库：`git clone <repo-url>`
2. 安装依赖：`brew install ffmpeg node python@3.11`
3. 搭建转写环境：`bash code/scripts/setup_transcription_env.sh`
4. 放置数据目录：把课程数据放到项目内 `data/高顿/`（实体目录、整体 gitignore，可从百度网盘镜像拉回；2026-09-14 起不再用软链，见 ADR-021）
5. 解密凭证：`secrets json .secrets/baidu_credentials.enc access_token`（全局命令 `secrets`，新机器先执行一次 `secrets install`）
6. 验证：运行 `bash code/scripts/check_directory_structure.sh`

---

## 六、环境配置维护原则

1. **环境变更时更新本文档**：新增工具、升级版本、修改配置时，必须更新本文档
2. **新电脑复现环境**：按照"迁移到新 Mac 的步骤"操作，确保环境一致
3. **工具版本锁定**：关键工具（ffmpeg、Node.js、Python）的版本记录在本文档中
4. **平台兼容性说明**：新增功能时，必须说明是否依赖特定平台的工具
