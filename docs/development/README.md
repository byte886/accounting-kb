# 开发文档索引

> **文档类型**：Reference（参考资料 — 文档索引）
> **更新频率**：文档结构变更时
> **维护者**：AI自动维护
> **读者**：AI代理

> 本文档是开发文档的快速索引。**完整的项目文档地图请参考 [DOCUMENTATION_MAP.md](../DOCUMENTATION_MAP.md)**。

---

## 目录结构

```
docs/development/
├── README.md                    # 本文档（索引）
├── api/                         # 接口与外部服务
│   ├── feishu-api.md            # 飞书API使用注意事项
│   ├── gaodun-exam-api.md       # 高顿做题接口档案（syllabus/redo-paper/submit-paper/exam-report）
│   ├── netdisk-setup.md         # 百度网盘集成：应用创建、API配置、上传脚本
│   └── encryption.md            # 加密凭证：Token加密存储与使用
├── guides/                      # 详细操作指南与规范
│   ├── agents-md-best-practices.md       # AGENTS.md写作最佳实践
│   ├── debugging-and-collaboration.md    # 问题排查方法论与人机协作
│   ├── exam-workflow.md                  # 做题/交卷任务执行指南（接口为主、UI兜底、检查清单）
│   ├── resource-collection-sop.md        # 阶段①资源采集SOP（视频/转写、讲义/OCR）
│   ├── paper-manifest-sop.md             # 阶段②做题交卷/试卷采集/manifest SOP
│   ├── knowledge-detail-build-sop.md     # 阶段③知识详解生成SOP（核心，一篇4节）
│   ├── finalize-sop.md                   # 阶段④收尾SOP（网盘/飞书统一同步/清理）
│   ├── feishu-knowledge-base-maintenance.md # 飞书知识库整理与维护SOP
│   ├── interaction-workflow.md           # 通用交互流程与优化规范（所有Web场景）
│   ├── macos-accessibility-automation.md # macOS原生控件/系统弹窗/多屏精准操作
│   ├── multi-role-collaboration.md       # 多角色协作分工（完整方法见飞书AI库）
│   └── git-workflow.md                   # GitHub工作流：SSH配置、代理设置、常见问题
├── tools/                       # 工具使用指南
│   ├── browser-cdp-connect-guide.md # 浏览器CDP连接手册（puppeteer-core连日常Chrome）
│   ├── playwright-cli-guide.md  # Playwright CLI使用指南
│   ├── video-processing.md      # 视频处理详细指南（下载/解密/压缩/验证）
│   ├── transcription.md         # 音频转文字：FunASR环境配置、性能数据
│   ├── ocr.md                   # OCR文字提取：macOS Vision框架、PDF转图片
│   └── document-download.md     # 文档下载：CDN直链获取、curl后台下载
├── knowledge/                   # 知识库管理
│   ├── knowledge-base-organization.md  # 三层架构/14组92点/一篇4节组织规范
│   └── knowledge-base-sources.md       # 知识库来源清单、优先级与冲突处理
└── templates/                   # 模板
    ├── KNOWLEDGE_BASE_TEMPLATE.md  # 知识点单篇4节/组父/课程全局模板
    ├── KNOWLEDGE_BASE_TEMPLATE.md  # 知识库内容模板（含知识点单篇、父节点、课程根等全部模板）
    ├── REPORT_TEMPLATE.md          # 任务报告模板
    └── VERIFICATION_TEMPLATE.md    # 通用验证模板（视频/转写专项质检按需）
```

---

## 技术栈

| 领域 | 技术/工具 |
|------|-----------|
| 视频下载 | Playwright + Node.js（HLS AES-128解密） |
| 视频压缩 | ffmpeg（H.265 CRF30） |
| 音频转文字 | FunASR SenseVoiceSmall（开源本地） |
| OCR | macOS Vision框架（系统原生）+ AI视觉补充 |
| 网盘 | 百度网盘开放平台API |
| 知识库 | 飞书知识库（Lark Wiki） |
| 浏览器自动化·主链路 | puppeteer-core 经 CDP 连接日常 Chrome（选型见 ADR-010） |
| 浏览器自动化·UI兜底 | Playwright CLI（Extension 模式附加到已登录 Chrome） |
| 自动做题·主链路 | 纯 HTTP 接口（syllabus/redo-paper/submit-paper/exam-report，JWT 鉴权；契约见 api/gaodun-exam-api.md） |
| 自动做题·兜底 | Playwright UI 点选（接口失败时降级，保证作业最终交得上） |

---

## 脚本位置

> 所有脚本统一放在 `code/scripts/` 目录，详细说明见 [code/scripts/README.md](../../code/scripts/README.md)

---

## 维护规则

1. **新增开发文档时**：按主题放入对应子目录（api/workflow/tools/knowledge），不要平铺在development/根目录
2. **新增子目录时**：必须在本文档中更新目录结构和文档列表
3. **文档移动/重命名时**：必须更新本文档和所有引用该文档的链接
4. **定期检查**：每次大阶段完成后，检查本文档与实际文件是否一致

---

**完整文档地图**：[DOCUMENTATION_MAP.md](../DOCUMENTATION_MAP.md)
