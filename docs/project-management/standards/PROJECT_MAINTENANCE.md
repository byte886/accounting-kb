# 项目维护规范（索引）

> **文档类型**：Reference（参考资料 — 文档索引）
> **更新频率**：维护规则变更时
> **维护者**：AI自动维护
> **读者**：AI代理+人类

> 本文档是项目维护规范的**索引文档**，详细内容已拆分为三个独立文档。

---

## 文档拆分说明

原 `PROJECT_MAINTENANCE.md`（552行）内容跨多个领域，按文档分解原则拆分为三个独立文档：

| 文档 | 内容 | 章节 |
|------|------|------|
| **[PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md)** | 项目结构维护规范 | 原第一至五章 |
| **[DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md)** | 文档写作指南 | 原第六至十一章 |
| **[DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md)** | 文档优化流程与变更驱动 | 原第十二至十三章 |

---

## 快速索引

### 项目结构维护

| 主题 | 文档 |
|------|------|
| 结构维护原则 | [PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md) |
| 文件归属原则 | [PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md) |
| 网盘上传内容筛选 | [PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md) |
| 测试闭环检查 | [PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md) |
| 状态查询协议触发 | [PROJECT_STRUCTURE_MAINTENANCE.md](PROJECT_STRUCTURE_MAINTENANCE.md) |

### 文档写作指南

| 主题 | 文档 |
|------|------|
| 文档组织原则（三层保障） | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |
| 文档分解原则 | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |
| 文档分类原则（Diátaxis框架） | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |
| Docs as Code 理念 | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |
| 文档定期梳理机制 | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |
| AI 友好写作原则 | [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) |

### 文档优化流程与变更驱动

| 主题 | 文档 |
|------|------|
| 文档优化的正确流程（强制） | [DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md) |
| 优化方法 / 变更联动的常见错误 | [DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md) |
| 文档变更驱动流程（强制） | [DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md) |
| 文档变更检查清单 | [DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md) |
| 与其他文档的联动关系 | [DOCUMENTATION_OPTIMIZATION.md](DOCUMENTATION_OPTIMIZATION.md) |

---

## 核心原则摘要（速览，权威以三个子文档为准，如有冲突以子文档为准）

### 项目结构维护
1. GitHub 仓库只放代码和文档，生成结果放本地和百度网盘
2. 脚本统一放 `code/scripts/`，文档按专业领域分类
3. 文件和目录有变化时必须检查 .gitignore
4. 网盘只上传面向使用者的内容，技术过程文档不上传

### 文档写作
1. 重要规则通过三层保障（README正文 / docs子文档 / 自动化机制）
2. 文档超过500行或内容跨领域时必须分解
3. 每个文档主要属于一种类型（Tutorial/How-to/Reference/Explanation）
4. 文档即代码，问题驱动更新
5. AI友好写作：答案在前、短段落、标题反映问题、可执行命令完整给出

### 文档优化与变更
1. 文档优化必须按四步流程：读最佳实践 → 一次性全面分析 → 一次性执行 → 主动验证
2. 禁止逐步优化，禁止等待用户指出问题
3. 文档变更自动触发驱动流程，不需要用户请求
4. 变更后必须按检查清单验证

---

> 本文档是项目维护规范的索引，详细内容见三个子文档。新增维护规则时，先判断属于哪个领域，添加到对应子文档中。
