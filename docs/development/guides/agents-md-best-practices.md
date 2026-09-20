# AGENTS.md 写作最佳实践

> **文档类型**：Task（操作指南）
> **更新频率**：AGENTS.md 优化时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档基于 2026 年软件工程领域的最佳实践研究，指导如何写好给 AI 看的 AGENTS.md 文档。

> **来源**：综合 Anthropic Claude Code 官方指南、OpenAI Codex Prompting Guide、Google Gemini CLI 指南，以及 2026 年同行评审研究（McMillan 2026, Lulla et al. 2026）。

---

## 一、核心原则

### 1.1 非可推断测试（最重要）

对于每条规则，问自己：**"如果删除它，AI会犯错吗？"**

- 如果不会 → 删除
- 如果会 → 保留

这个原则应用后，可以消除 70-80% 人们本能想写下来的内容。

### 1.2 四个高价值类别

AGENTS.md 应该只包含以下四类内容：

| 类别 | 说明 | 示例 |
|------|------|------|
| **精确的工具和版本** | AI 无法可靠猜测的具体命令和版本号 | "Python 3.12, not 3.11"、"pnpm, not npm" |
| **逐字可执行命令** | 安装、测试、构建、部署的精确 CLI 字符串 | "Run `pnpm install --frozen-lockfile`" |
| **反直觉的约定** | 项目偏离默认值的地方 | 非标准目录布局、自定义错误处理模式 |
| **权限边界** | AI 可以做什么、需要确认什么、永远不能做什么 | "Never push to main directly" |

### 1.3 不应该包含的内容

| 内容类型 | 原因 | 处理方式 |
|----------|------|----------|
| README 中已有的内容 | 冗余会降低任务成功率约3%，增加推理成本20%+ | 链接或引用，不要重复 |
| 长篇架构解释 | 对人有用，对 AI 在始终加载的上下文中适得其反 | 移到 references/ 目录，按需读取 |
| 详细的 API 文档 | AI 可以在需要时获取 | 链接到实际文档 |
| 标准语言/框架约定 | 已经在模型的训练数据中 | 不要写（如"遵循 PEP 8"） |
| 不言而喻的建议 | 不约束行为，只消耗上下文窗口 | 删除（如"写干净的代码"） |
| 频繁变化的信息 | 应该在工作记忆或会话提示中 | 不要写（如当前冲刺任务列表） |
| 营销语言和项目历史 | 对 AI 无用，还会引导输出营销语气 | 删除（如"我们的平台赋能用户..."） |

---

## 二、结构建议

### 2.1 根文件保持简短

- **理想长度**：50-200 行
- **超过 200 行**：边际指令正在与上面的所有内容竞争注意力
- **实践建议**：将根文件视为高密度摘要，而不是手册

### 2.2 渐进式披露（Progressive Disclosure）

2026 年所有主要平台（Anthropic、OpenAI、Google）共享的架构模式：

```
/AGENTS.md              # 短根文件：工具、命令、权限、约定
/skills/                # 领域特定技能，按需加载
  pdf-extraction/
    SKILL.md
  schema-migration/
    SKILL.md
/references/            # 长篇参考资料，仅在需要时读取
  data-model.md
  deployment.md
/code/scripts/               # 确定性验证脚本
  run-tests.sh
```

### 2.3 嵌套指令文件

对于大型仓库：
- 根 `AGENTS.md`：组织范围的标准
- 子包/微服务特定的 `AGENTS.md`：最接近活动代码的文件优先

### 2.4 章节标题

供应商示例通常使用简短的 Markdown 标题：
- `## Setup`
- `## Code style`
- `## Testing`
- `## Permissions`

**注意**：2026 年的研究表明，特定的标题方案与更好的 AI 行为没有因果关系。标题的作用是帮助人类找到和编辑内容，可能帮助模型定位相关部分。不要过度设计分类法。

---

## 三、最小工作模板（约50行）

```markdown
# AGENTS.md

## Tooling and versions
- Python 3.12 (not 3.11)
- Node 20.x via pnpm (not npm or yarn)
- Postgres 16 for local development

## Commands
- Install: `pnpm install --frozen-lockfile`
- Test: `pnpm test --watchAll=false`
- Lint: `pnpm lint --max-warnings 0`
- Build: `pnpm build`

## Conventions
- All React components use the `*Widget.tsx` suffix
- Database migrations are immutable after merge
- API errors use the `AppError` class in `src/lib/errors.ts`

## Permissions
- YOU MUST run the full test suite before reporting a task complete
- Never push directly to main; open a PR
- Ask for confirmation before deleting any file outside src/ or tests/

## References
- Architecture overview: @references/architecture.md
- Deployment: @references/deployment.md
```

### 这个模板刻意做的事情：

1. **没有项目使命陈述** — AI 不需要
2. **没有语言约定** — PEP 8 和标准 React 约定已经在模型中
3. **带标志的逐字命令** — 不是"用 pnpm 运行测试"，而是精确字符串
4. **权限表述为正面命令** — 选择性强调不可覆盖的规则
5. **信任边界明确** — 不假设
6. **参考资料通过 @ 语法导入** — 而不是内联

---

## 四、部署前检查清单

1. 一个新的 AI，没有其他上下文，仅使用此文件加上代码库，能完成典型任务吗？
2. 每一行都通过了非可推断测试吗——删除它会导致真正的错误吗？
3. 精确的版本、精确的命令、精确的权限都说明了吗？
4. 可信和不可信输入之间的信任边界明确吗？
5. "完成"标准是确定性和可检查的（脚本、模式、测试套件），而不是期望性的吗？
6. 文件在 ~200 行以内，还是额外内容已模块化到 skills 和 references 中？
7. 文件在版本控制下，有真正的审查流程吗？
8. 文件中没有秘密、凭证或通过 obscurity 的安全措施吗？
9. 你实际上用 AI 在代表性任务上测试过它吗？
10. 有运行时监控或跟踪审查系统来捕获文件遗漏的内容吗？

---

## 五、本项目的应用

基于以上最佳实践，本项目的 AGENTS.md 应该：

### 5.1 应该保留的内容

- **精确的工具和版本**：Python 3.13、Node.js v20、ffmpeg 8.1.2
- **逐字可执行命令**：视频压缩、转写、做题、上传的精确命令
- **反直觉的约定**：
  - 批量任务必须在 iTerm 前台运行，禁止后台运行
  - OCR 使用 macOS Vision 框架（系统原生，无需安装额外工具）
  - 生成结果（视频/PDF/文字稿）禁止提交到 GitHub
  - 做题必须先查询知识库
- **权限边界**：
  - 不要用 Chrome 手动下载文件
  - 不要自行关闭用户打开的 Chrome 窗口
  - 不要不查阅文档就直接执行

### 5.2 应该移走的内容

- **Project Overview** → 移到 README.md（给人看的）
- **Code Style** → 移到 `docs/project-management/standards/CODE_STYLE.md`
- **Testing Instructions** → 分散移到对应专项文档
- **Architecture Notes 中的目录结构** → 链接到 `docs/DIRECTORY_STRUCTURE.md`
- **Tech Stack 中的详细版本** → 链接到 `docs/SYSTEM_REQUIREMENTS.md`

### 5.3 优化后的结构（预计10章，约150行）

```
1. 文档边界
2. 执行前必读文档（强制顺序）
3. 核心规则（强制，必须遵守）
4. Things to Avoid（明确禁止事项）
5. 工具与版本（精确版本）
6. 常用命令（逐字可执行）
7. 浏览器操作检查清单
8. 存储分工（硬约束）
9. 异常处理流程
10. 文档快速入口
11. 状态查询协议
12. Definition of Done
```
