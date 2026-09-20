# 文档下载指南

> **文档类型**：Task（操作指南 — 文档下载）
> **更新频率**：每次下载流程变更时
> **维护者**：AI自动维护
> **读者**：AI代理（执行文档下载任务时）

本文档记录从高顿教育网站下载讲义/课件文档的完整流程，包括获取CDN直链、curl后台下载、完整性校验。

---

## ⚠️ 强制规则

**禁止用Chrome点击下载按钮！必须用curl后台下载！**

- 点击"下载"按钮会触发Chrome下载对话框，影响自动化流程
- 如果出现Chrome下载对话框，立即取消（按Esc或点击取消），删除已下载文件，用curl重新下载
- 违反后果：必须立即取消，删除已下载的文件，用正确的curl方式重新下载

---

## 1. 获取下载链接

### 1.1 下载入口

课程表页（`https://glivepro.gaodun.com/course/42660/class-schedule`）每个直播场次下展开"讲义"/"课件"条目，点击"下载"按钮会触发fetch到CDN直链。

### 1.2 CDN直链特征

- CDN域名：`simg01.gaodunwangxiao.com/newoss/resources/...`
- PDF可直接curl下载，无需认证
- 链接可能包含token或签名参数，会过期

### 1.3 正确获取CDN直链的方法（必须遵守）

**方法：用Playwright的`run-code`监听网络请求，点击下载按钮时捕获CDN直链**

```bash
# 步骤1：用Playwright拦截网络请求获取CDN直链
npx playwright cli -s=ga run-code --filename /tmp/get_download_url.js

# /tmp/get_download_url.js 内容示例：
# 监听网络请求，点击下载按钮，捕获CDN直链并返回
```

**替代方法：用浏览器开发者工具的Network面板**
1. 打开开发者工具（F12），切换到Network面板
2. 点击"下载"按钮
3. 在Network面板中找到CDN请求（域名包含`gaodunwangxiao.com`）
4. 复制请求URL

---

## 2. 用curl下载（后台，无对话框）

### 2.1 基本命令

```bash
curl -L -o docs/课件.pdf -e "https://glivepro.gaodun.com/" "<CDN直链>"
```

**参数说明：**
- `-L`：跟随重定向
- `-o <文件>`：输出文件名
- `-e <URL>`：设置Referer，模拟从高顿网站发起的请求

### 2.2 批量下载

如果有多个文档，可以写一个简单的循环：

```bash
# 下载链接列表文件，每行一个URL
urls.txt:
https://simg01.gaodunwangxiao.com/.../讲义1.pdf
https://simg01.gaodunwangxiao.com/.../课件1.pdf

# 批量下载
while read url; do
  filename=$(basename "$url" | cut -d'?' -f1)
  curl -L -o "docs/$filename" -e "https://glivepro.gaodun.com/" "$url"
done < urls.txt
```

### 2.3 下载位置

- 下载到课程目录的 `原始资源/notes/NN_模块/`
- 路径：`高顿/CPA/<课程名>/原始资源/notes/NN_模块/讲义_名称.pdf`
- 讲目录命名（`NN=idx-1`、开班 00、只清非法字符、忠实平台标题）与视频讲目录完全一致，规则见 [video-processing.md](./video-processing.md)「讲目录命名」，不在此重复。
- 不要下载到项目根目录或其他临时位置

---

## 3. 文档格式确认

### 3.1 可能的格式

- PDF（最常见）
- PPT/PPTX
- DOC/DOCX

### 3.2 确认方法

```bash
# 用file命令确认格式
file docs/课件.pdf
# 输出示例：PDF document, version 1.7

# 检查文件大小
ls -lh docs/
```

---

## 4. 完整性校验

### 4.1 对照课程清单

- 对照课程清单（`data/_workspace/<profile>/manifest/course_catalog.json` 或课程表页面）核对每个讲次应有的讲义数量
- 检查是否有遗漏的讲义或课件

### 4.2 文件大小检查

- 检查文件大小是否与页面显示一致
- PDF文件通常几MB到几十MB，过小（<100KB）可能下载不完整

### 4.3 PDF页数检查

```bash
# 用pdfinfo检查页数（需要安装poppler）
pdfinfo docs/讲义.pdf | grep Pages
```

### 4.4 打开验证

- 用PDF阅读器打开文件，确认内容完整、无乱码、无空白页
- 重点检查开头和结尾几页

---

## 5. 下一步：文档文字提取（OCR）

### 5.1 重要提醒

- 高顿课件PDF多为**图片型PDF**（PPT导出为图片），无法直接提取文字，**必须使用OCR**
- **OCR方案**：macOS Vision框架（系统原生免费，中文识别效果好），**不是tesseract**
- **工具**：Swift编译的`/tmp/ocr_vision` + PyMuPDF（200 DPI）
- **性能**：116页约2分钟，每页约1秒
- **批量脚本**：`code/scripts/ocr/batch_ocr.sh`
- **详细文档**：[ocr.md](./ocr.md)

### 5.2 执行前检查清单

- [ ] 检查`/tmp/ocr_vision`二进制是否存在，不存在则先编译
- [ ] 检查PDF是否有文本层（有文本层可直接提取，无需OCR）
- [ ] 图片型PDF必须使用macOS Vision框架OCR，**不要安装tesseract**

---

## 6. 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Chrome弹出下载对话框 | 用了Chrome点击下载按钮 | 立即取消，用curl后台下载 |
| 下载的文件打不开 | CDN链接过期或下载不完整 | 重新获取CDN直链，重新下载 |
| 文件大小过小 | 下载不完整或链接错误 | 检查文件大小，重新下载 |
| PDF无法提取文字 | 图片型PDF | 使用OCR（macOS Vision框架） |
| curl下载403错误 | 缺少Referer或链接过期 | 添加`-e "https://glivepro.gaodun.com/"`，重新获取链接 |

---

## 7. 相关脚本和文档

| 类型 | 名称 | 位置 |
|------|------|------|
| 脚本 | 批量OCR | `code/scripts/ocr/batch_ocr.sh` |
| 文档 | OCR指南 | [ocr.md](./ocr.md) |
| 文档 | 命名规范 | [../../project-management/standards/NAMING_CONVENTION.md](../../project-management/standards/NAMING_CONVENTION.md) |
| 文档 | 主工作流 | [../../WORKFLOW.md](../../WORKFLOW.md) 第3节 |

---

*本文档是文档下载的专项指南，详细操作步骤以本文档为准。主工作流WORKFLOW.md只保留摘要和链接。*
