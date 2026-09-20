# 编码规范

> **文档类型**：Governance（治理规范）
> **更新频率**：编码规范变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档记录项目的编码规范，从 AGENTS.md 中移除以保持 AGENTS.md 简洁。

---

## 一、脚本规范

- **Shell脚本**：bash 3.2 兼容（Mac自带版本），set -euo pipefail
- **Python脚本**：类型注解，函数式优先，避免全局状态
- **文件名**：`.py/.sh/.js` 一律全小写 `snake_case`（下划线分词，禁止连字符与大写），如 `baidu_upload.py`、`check_directory_structure.sh`；唯一例外是 Git 固定名 `pre-commit`。详见 `docs/project-management/standards/NAMING_CONVENTION.md` 第九章 9.4（依据 PEP 8）
- **所有脚本放 `code/scripts/` 目录**，禁止散落在各子目录
- **产出落点受控**：脚本只把成品写到正式目录；运行数据写 `data/`、日志/完成哨兵写 `logs/`、临时中转写 `/tmp` 或模块内 `.tmp_*/`，不得在业务目录散落点开头的缓存文件（落点分类见 PROJECT_STRUCTURE_MAINTENANCE.md 2.1）
- **临时目录自清**：批处理脚本建的临时中转目录必须 `cleanup()+trap cleanup EXIT` 兜底删除，保证正常/报错/Ctrl-C 都不留残（断点续跑凭证例外，不得删）；每新增一类运行产物，必须同步 `.gitignore` 与 `code/scripts/pre-commit` 的 `ARTIFACT_RE`

## 二、文档规范

- **Markdown格式**，标题层级清晰（# → ## → ###）
- **命令用代码块**，路径用反引号
- **每个文档开头标注类型**：`> 文档类型：Task / Concept / Reference / Governance / Active / Knowledge / Template`（7 类封闭词表，以 DOCUMENTATION_GUIDE.md 3.1 为准，不得自造类型词）
- **WORKFLOW.md只放流程概览和链接**，详细内容放专项文档

## 三、命名规范

- 课程目录：两层 `原始资源/`、`知识详解/`；运行时过程件统一在独立的 `data/_workspace/`（账号级 `_account` + 课程级 `<profile>`，详见 DIRECTORY_STRUCTURE）
- 视频：`原始资源/videos/NN_讲题/{video.mp4,transcript.md}`（统一命名，不留原始长文件名）
- 讲义：`原始资源/notes/NN_模块/{讲义_*.pdf,讲义_*_OCR.md}`
- 知识库成品：`知识详解/NN_模块组/{官方知识点}.md`（一篇 4 节）+ 课程全局篇
- **仓库工程文件命名**：以 `NAMING_CONVENTION.md` 第九章为唯一事实源（脚本 snake_case、方法文档小写 kebab-case、规范/模板/台账 UPPER_SNAKE、中文过程产物与标题对应），本节不再重复规则
