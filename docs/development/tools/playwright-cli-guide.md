# Playwright CLI 使用指南

> **文档类型**：Task（操作指南）
> **更新频率**：工具变更时
> **维护者**：AI自动维护
> **读者**：AI代理

> 本文档记录 Playwright CLI 的正确用法、常见错误和最佳实践。
> 每次遇到新的问题或错误时，应及时更新本文档。

## 一、基本概念

### 1.1 连接方式

Playwright CLI 支持两种连接浏览器的方式：

1. **open 命令**：启动一个新的浏览器实例
   - 不支持 `--extension` 选项
   - 支持 `--browser`、`--headed`、`--persistent` 等选项
   - 适用于需要启动新浏览器的场景

2. **attach 命令**：连接到已运行的浏览器
   - 支持 `--extension` 选项（连接浏览器扩展）
   - 支持 `--cdp` 选项（连接 CDP 端点）
   - 支持 `--endpoint` 选项（连接 Playwright 服务器端点）
   - 适用于需要连接已运行浏览器的场景（如高顿教育网站已登录）

### 1.2 会话管理

- 使用 `-s=<session_name>` 指定会话名称
- 高顿教育项目使用会话名 `ga`
- 连接后，所有命令都需要指定会话名：`playwright-cli -s=ga <command>`

## 二、正确的命令用法

### 2.1 连接浏览器（高顿教育项目）

**正确用法**：
```bash
# 使用 attach 命令连接 Chrome 浏览器扩展
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach --extension=chrome
```

**常见错误**：
```bash
# ❌ 错误：open 命令不支持 --extension 选项
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga open --extension=chrome

# ❌ 错误：缺少 --extension 选项
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach
```

### 2.2 导航到 URL

**正确用法**：
```bash
# 使用 goto 命令导航到 URL
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga goto "https://glivepro.gaodun.com/course/42660/class-schedule"
```

**常见错误**：
```bash
# ❌ 错误：没有 navigate 命令，应该用 goto
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga navigate "https://..."

# ❌ 错误：URL 没有加引号（包含特殊字符时会出错）
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga goto https://glivepro.gaodun.com/course/42660/class-schedule
```

### 2.3 标签页管理

**正确用法**：
```bash
# 列出所有标签页
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga tab-list

# 创建新标签页
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga tab-new "https://..."

# 选择标签页（索引从 0 开始）
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga tab-select 1

# 关闭标签页
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga tab-close 2
```

**最佳实践**：
- 操作前先执行 `tab-list` 查看所有标签页
- 从后往前关闭多余页面（避免索引变化导致关错）
- 只保留当前工作页，如需参考文档可额外保留 1 个飞书文档页

### 2.4 页面操作

**正确用法**：
```bash
# 获取页面快照（获取元素 ref）
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga snapshot --depth=8

# 点击元素
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga click e123

# 截图
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga screenshot --filename=/tmp/page.png

# 执行 JavaScript
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga eval "window.location.href"

# 重新加载页面
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga reload
```

### 2.5 断开连接

**正确用法**：
```bash
# 断开连接（不关闭浏览器）
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga detach

# 关闭浏览器
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga close
```

## 三、常见错误与解决方案

### 3.1 错误：open 命令不支持 --extension 选项

**错误信息**：
```
Unknown option: --extension
```

**原因**：`open` 命令用于启动新浏览器，不支持 `--extension` 选项。`--extension` 选项只在 `attach` 命令中可用。

**解决方案**：使用 `attach` 命令代替 `open` 命令：
```bash
# ✅ 正确
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach --extension=chrome
```

### 3.2 错误：没有 navigate 命令

**错误信息**：
```
Unknown command: navigate
```

**原因**：Playwright CLI 没有 `navigate` 命令，导航 URL 应该使用 `goto` 命令。

**解决方案**：使用 `goto` 命令：
```bash
# ✅ 正确
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga goto "https://..."
```

### 3.3 错误：浏览器会话未打开

**错误信息**：
```
The browser 'ga' is not open, please run open first
```

**原因**：会话 `ga` 未连接到浏览器，需要先执行 `attach` 命令。

**解决方案**：先连接浏览器，再执行其他命令：
```bash
# 1. 连接浏览器
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga attach --extension=chrome

# 2. 等待 2 秒
sleep 2

# 3. 执行其他命令
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga tab-list
```

### 3.4 错误：元素 ref 失效

**错误信息**：
```
Element not found
```

**原因**：页面变化后，之前获取的元素 ref 可能失效，需要重新获取快照。

**解决方案**：每次页面变化后，重新执行 `snapshot` 获取最新的元素 ref。

### 3.5 错误：CDP 不可用

**错误信息**：
```
Not allowed
```

**原因**：Extension 模式下 CDP 不可用，只能用 Playwright CLI 命令。

**解决方案**：使用 Playwright CLI 命令，不要尝试使用 CDP。

### 3.6 错误：Failed to connect to MCP relay: WebSocket error

**错误信息**：
```
Failed to connect to MCP relay: WebSocket error
```

**原因**：Playwright Extension 的 token 过期或连接异常，需要刷新 token。

**解决方案**：按下面的"Token 自动刷新流程"刷新 token 并重新连接。

## 四、Token 自动刷新流程

当出现 `Failed to connect to MCP relay: WebSocket error` 或 token 过期时，需要刷新 token。

### 4.1 Extension 状态页面

- **URL**：`chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html`
- **刷新按钮**：class 为 `.auth-token-refresh`
- **token 显示**：class 为 `.auth-token-code`

### 4.2 自动刷新流程（使用 AppleScript）

```bash
# 步骤1：打开Extension状态页面并点击刷新按钮
osascript << 'EOF'
tell application "Google Chrome"
    open location "chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html"
    delay 2
    set currentTab to active tab of front window
    execute currentTab javascript "document.querySelector('.auth-token-refresh').click();"
    delay 1
end tell
EOF

# 步骤2：获取新token
NEW_TOKEN=$(osascript << 'EOF'
tell application "Google Chrome"
    set currentTab to active tab of front window
    set tokenText to execute currentTab javascript "document.querySelector('.auth-token-code').textContent"
    return tokenText
end tell
EOF
)

# 步骤3：提取纯token值（去掉 PLAYWRIGHT_MCP_EXTENSION_TOKEN= 前缀）
PURE_TOKEN=$(echo "$NEW_TOKEN" | sed 's/PLAYWRIGHT_MCP_EXTENSION_TOKEN=//')

# 步骤4：设置环境变量并重新连接
export PLAYWRIGHT_MCP_EXTENSION_TOKEN="$PURE_TOKEN"
npx playwright cli -s=ga attach --extension=chrome
```

### 4.3 注意事项

- 点击刷新按钮后，旧的连接会立即断开（这是正常的）
- 必须用 AppleScript 获取新 token，因为 Playwright 连接已断开
- 获取新 token 后，需要重新设置环境变量并重新连接
- 新 token 格式：`PLAYWRIGHT_MCP_EXTENSION_TOKEN=xxxxx`，需要去掉前缀只保留 `xxxxx`

### 4.4 已验证的 token 刷新记录

| 刷新时间 | 旧 token | 新 token | 刷新原因 |
|----------|----------|----------|----------|
| 2026-08-28 | JK0HlLRvp68DTxJKai2ZT6UHw3u6hnUwFugi8NkQc6g | ABG0ojdWZTmQzZ1nnntl9yQYJPin7nDzTdI-UCzs4xw | 测试自动刷新流程 |

### 4.5 常用话术

用户可以直接复制以下话术触发 Token 刷新流程：

> `刷新Playwright token`

或

> `Playwright连接失败，帮我刷新token`

AI 收到后，应自动执行 4.2 中的步骤1（用 AppleScript 打开扩展状态页面并点击刷新按钮），然后自动获取新 token 并重新连接。

## 五、最佳实践

### 4.1 命令执行前检查

每次执行 Playwright CLI 命令前，先检查：
1. 浏览器会话是否已连接（`tab-list`）
2. 当前标签页是否正确（`tab-list`）
3. 命令名称是否正确（`goto` 不是 `navigate`，`attach` 不是 `open --extension`）

### 4.2 页面加载等待

导航到新页面后，等待页面加载完成：
```bash
# 导航到 URL
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga goto "https://..."

# 等待 3 秒页面加载
sleep 3

# 检查当前 URL
PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token> npx playwright cli -s=ga eval "window.location.href"
```

### 4.3 环境变量设置

为了避免每次都输入 token，可以设置环境变量：
```bash
# 设置环境变量（仅当前会话有效）
export PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token>

# 之后可以直接使用
npx playwright cli -s=ga attach --extension=chrome
```

### 4.4 命令封装

对于常用的命令组合，可以封装成脚本：
```bash
#!/bin/bash
# code/scripts/playwright-connect.sh
# 连接到高顿教育浏览器会话

export PLAYWRIGHT_MCP_EXTENSION_TOKEN=<token>

# 连接浏览器
npx playwright cli -s=ga attach --extension=chrome

# 等待连接
sleep 2

# 列出标签页
npx playwright cli -s=ga tab-list
```

## 六、命令速查表

| 操作 | 正确命令 | 常见错误 |
|------|----------|----------|
| 连接浏览器扩展 | `attach --extension=chrome` | `open --extension=chrome` ❌ |
| 导航到 URL | `goto <url>` | `navigate <url>` ❌ |
| 列出标签页 | `tab-list` | - |
| 创建新标签页 | `tab-new <url>` | - |
| 选择标签页 | `tab-select <index>` | - |
| 关闭标签页 | `tab-close <index>` | - |
| 获取页面快照 | `snapshot --depth=8` | - |
| 点击元素 | `click <ref>` | - |
| 截图 | `screenshot --filename=<path>` | - |
| 执行 JS | `eval <expression>` | - |
| 重新加载 | `reload` | - |
| 断开连接 | `detach` | - |
| 关闭浏览器 | `close` | - |

## 七、相关文档

- [video-processing.md](./video-processing.md) — 视频处理详细指南（包含 Playwright 捕获密钥的步骤）
- [exam-workflow.md](../guides/exam-workflow.md) — 做题/交卷任务执行指南（接口为主、UI 兜底）；通用页面/标签管理原则见 interaction-workflow.md
- [WORKFLOW.md](../../WORKFLOW.md) — 总体工作流
