# ADR-006：用Playwright操作百度网盘替代API

> **文档类型**：Active（过程记录 — 架构决策记录）
> **日期**：2026-08-29
> **状态**：已采纳
> **决策者**：用户 + AI

## 背景

百度网盘开放平台的API权限有限，list API（列出文件）权限不足，只能上传文件，无法浏览和管理目录结构。项目需要检查网盘文件完整性、管理目录结构，需要一个替代方案。

## 决策

采用 **Playwright操作百度网盘网页版** 作为API的替代方案，用于浏览目录结构、检查文件完整性、管理文件。

**技术方案**：
- 使用Playwright CLI的 `attach --extension=chrome` 模式连接用户已有的Chrome
- 复用用户Chrome的百度网盘登录态
- 通过双击导航进入文件夹
- 通过 `document.body.innerText` 解析文件列表

## 备选方案

| 方案 | 优点 | 缺点 | 可行性 |
|------|------|------|--------|
| 申请开放平台更高权限 | 官方API，稳定高效 | 需要审核，可能不通过 | ⭐⭐⭐ |
| BaiduPCS-Go第三方工具 | 命令行操作，速度快 | 第三方工具，安全风险，可能被封号 | ⭐⭐⭐⭐ |
| **Playwright操作网页版** | **不需要额外权限，可视化，可管理文件** | **比API慢，需要维护，依赖网页结构** | ⭐⭐⭐⭐ |
| 手动操作 | 简单 | 效率低，无法自动化 | ⭐⭐ |

## 决策理由

1. **无需申请权限**：直接使用用户已有的登录态，不需要等待API审核
2. **功能完整**：可以浏览目录、检查文件、新建文件夹、移动删除文件
3. **可视化**：操作过程可见，便于调试和验证
4. **可自动化**：可以脚本化，作为批量任务的一部分
5. **用户要求**：用户明确要求用Playwright操作，而不是申请API权限

## 技术实现

### 连接方式
```bash
# 自动化刷新token并连接
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach --extension=chrome
```

### 导航方式
- 百度网盘是单页应用，URL导航不生效
- 需要用双击（dblclick）进入文件夹
- 通过JavaScript触发双击事件：
```javascript
const event = new MouseEvent('dblclick', {bubbles: true, cancelable: true});
element.dispatchEvent(event);
```

### 文件列表解析
```javascript
const allText = document.body.innerText;
const lines = allText.split('\n').map(l => l.trim()).filter(l => l);
const fileIndex = lines.findIndex(l => l.includes('文件名'));
const fileLines = fileIndex >= 0 ? lines.slice(fileIndex + 1) : lines.slice(-30);
```

## 已验证的目录结构
```
/apps/CPA课程归档/高顿/CPA/
├── 课程库/ ✅
└── 待整理/ ✅
```

## 后果

### 正面
- 解决了API权限不足的问题
- 可以检查文件完整性和目录结构
- 可以管理文件（新建、移动、删除）

### 负面
- 比API慢（需要加载网页）
- 依赖百度网盘网页结构，结构变更可能导致脚本失效
- 需要保持Chrome登录态
- token可能过期，需要自动化刷新流程

## 自动化token刷新

为了解决token过期问题，建立了自动化刷新流程：
1. 用AppleScript打开扩展状态页面
2. 自动点击刷新按钮
3. 获取新token
4. 重新连接

详细流程见 `docs/development/tools/playwright-cli-guide.md` 第4节。

## 验证

- 2026-08-29：成功用Playwright操作百度网盘，浏览到 `/apps/CPA课程归档/高顿/CPA/` 目录
- 验证了目录结构与规划一致（课程库/待整理）
- 自动化token刷新流程测试通过

## 相关文档

- `docs/development/tools/playwright-cli-guide.md` — Playwright使用指南
- `docs/development/api/netdisk-setup.md` — 百度网盘API设置
- `project-management/ISSUES.md` — 问题跟踪（I-002已解决）
