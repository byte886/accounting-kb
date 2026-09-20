# macOS 辅助功能自动化（AX）：控件捕捉与精准交互（含多显示器）

> **文档类型**：Task（操作指南 — macOS 原生 UI 自动化通用方法）
> **更新频率**：方法或工具链变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理（开发工程师）与用户

> 这是一份**跨项目通用**的 macOS 自动化方法：如何程序化读取/操作其他 App 的原生控件、可靠点击系统弹窗，并在**多显示器**环境下点得准。
> 本项目的直接应用是自动点掉 Chrome「要允许远程调试吗？」弹窗（脚本 `code/scripts/cdp/press_allow.applescript`，被 CDP 连接模块调用，见 [浏览器 CDP 连接手册](../tools/browser-cdp-connect-guide.md)），但方法适用于任何原生 App 自动化场景。

---

## 1. 两条技术路线：元素级（首选） vs 坐标级（兜底）

macOS 上让程序操作另一个 App 的界面，有本质不同的两条路：

| 维度 | 元素级：辅助功能 API（AX） | 坐标级：合成输入事件 |
|---|---|---|
| 动作对象 | **UI 元素对象**（按钮、输入框…） | 屏幕上的某个 (x, y) 点 |
| 典型手段 | 遍历 AX 树 → 找到元素 → `perform action "AXPress"` | System Events `click at`、`cliclick`、CGEvent 鼠标事件 |
| 是否要窗口在前台/聚焦 | **不需要**，动作由目标 App 内部处理 | 通常需要，且要移动/点击真实光标 |
| 与多屏/Retina/窗口位置关系 | **完全解耦**，不存在点偏 | 强依赖全局坐标换算，多屏易点偏 |
| 可靠性 | 高（原生控件直接响应动作） | 中：AppKit/多数 SwiftUI 可用，但 **Mac Catalyst 右栏控件、部分沙盒 App、某些安全弹窗会静默丢弃** |
| 适用 | 绝大多数原生控件、系统弹窗（首选） | 元素树读不到（自绘 Canvas/游戏/网页内部）时兜底 |

**核心结论：能用元素级 AXPress 就不要用坐标点击。** AXPress 是「对元素对象发动作」，由目标 App 内部执行，窗口不必成为关键窗口、光标都不用移过去，因此**天然不存在多显示器点不准的问题**；多屏痛点几乎全部来自坐标级方案。

---

## 2. 关键坑：控件文字不一定在 AXTitle

读一个按钮叫什么，不能只看 `title`（AXTitle）。原生控件的可见文本可能落在不同属性里，需要**拼接多个属性一起判断**：

| 属性 | 含义 | 本项目 Chrome 授权弹窗实测 |
|---|---|---|
| `AXTitle`（title） | 元素标题 | **为空** |
| `AXDescription`（description） | 无障碍描述 | **按钮文字在这里**：「在'设置'中关闭 / 取消 / 允许」 |
| `AXValue`（value） | 当前值 | 部分控件有值 |
| `AXHelp`（help） | 帮助提示 | 偶尔承载文本 |
| `AXRole`（role） | 角色，如 `AXButton` | 用来先筛按钮 |

教训：**只按 title 找按钮会找不到**；正确做法是 role 先筛 `AXButton`，再把 title/description/value/help 拼起来匹配文本。

另一个易混点：**「窗口/sheet 消失」不等于「动作生效」**。本项目实测坐标点击能让授权 sheet 视觉上关闭，但调试连接依旧卡住（并未真正授权）；只有对正确元素执行 AXPress，才同时满足「sheet 关闭 + 业务状态真正改变」。**验证动作要以业务状态为准，不能只看界面消失。**

---

## 3. 多显示器：为什么坐标点击会偏，AXPress 不会

### 3.1 为什么 AXPress 不受多屏影响

AXPress 的目标是元素引用（AXUIElement），不是坐标。无论元素出现在哪块屏、窗口被拖到哪里、是否被遮挡，只要能在 AX 树里枚举到它，动作就直达该元素——**没有任何坐标运算，自然与屏幕数量、排列、缩放无关**。

### 3.2 坐标级方案必须处理的三个坐标问题（仅当不得不坐标点击时）

1. **两套坐标系原点不同**
   - Core Graphics（CGEvent、`CGDisplayBounds`）用**全局显示空间，原点在主显示器左上角，y 向下**；
   - AppKit（`NSScreen.frame`）原点在**左下角，y 向上**。
   - 混用必然点偏，换算时先统一到一套。
2. **「主屏」是菜单栏所在屏**：全局坐标原点随「主显示器」设置变化；显示器重排后所有全局坐标都会变。多屏要用 `CGGetActiveDisplayList`/`CGDisplayBounds` 动态取各屏 bounds，不能写死。
3. **点（point）与像素（pixel）、Retina @2x**：逻辑分辨率和物理像素差一个 `backingScaleFactor`；截图是像素、鼠标事件用点，**禁止从截图像素直接估坐标**（还要叠加窗口/视口原点偏移）。需要坐标时，应**从 AX 元素动态读 `AXPosition`/`AXSize` 算其中心点**，而不是看图估。

> 经验法则：多屏场景下，要么用 AXPress（推荐）；要么「AX 读元素位置 → 算中心 → 坐标点击」，把坐标来源锚定在元素上，仍不硬编码、不看截图估点。

---

## 4. 标准操作流程（SOP）

1. **授权**：系统设置 → 隐私与安全性 → **辅助功能**，勾选运行脚本的终端 / 宿主 App（父进程链上的 App 都可能需要）。
2. **先读树、后动手**：枚举目标进程的窗口/sheet/控件，打印 role 与多属性文本，确认真正的目标元素；不要看截图估坐标。
3. **优先元素动作**：按钮用 `AXPress`，输入框用 `setValue`，滚动条/步进用 `AXIncrement`/`AXDecrement`。
4. **必须坐标时**：从元素的 `AXPosition`+`AXSize` 动态算中心，用全局坐标，多屏先取各屏 bounds。
5. **以业务状态验证**：动作后同时确认「界面变化 + 底层状态变化」；两者不一致说明动作被静默丢弃，换元素级路线。
6. **缩小遍历范围、设深度上限、加 try 容错**：先按 role/层级把范围缩到最小子树（如只看 sheet），避开网页 `AXWebArea` 这类节点海量的区域（AX 耗时与访问节点数近似线性，见 §5.1）；个别属性读取可能抛错，设深度上限并对每次取值兜底。
7. **轮询自动化要串行、勿并发轰炸**：同一时刻只发一个 AppleScript，上一次返回或超时再发下一个，停止时清理在途子进程（见 §5.2）。

---

## 5. 本项目落地：自动点 Chrome 远程调试授权

`code/scripts/cdp/press_allow.applescript`（系统自带 `osascript`，零安装）。最终实现是踩过三个坑后定下的，这三个坑都是**可迁移到任何原生 App 自动化的通用规律**。

### 5.1 只遍历「弹窗 sheet」，绝不递归整窗 / 网页区（性能命门）

最初递归扫描整个 window 的 UI 元素（深度 25）。Chrome 窗口里挂着整张网页，网页 `AXWebArea` 有成千上万节点，**每个节点都是一次跨进程 AppleEvent 往返**，系统繁忙时整树遍历实测要 **9.3 秒**（进程 user CPU 仅 0.26s，其余全在跨进程等待）。而授权弹窗只是 window 上的一个模态 `sheet`，里面只有几个按钮。改为：入口只取 `sheets of windows` → 先直接取 `buttons of sheet`（最快路径）→ 兜底也只在 sheet 内部有限深度递归，且遇到 `AXWebArea` 立即跳过、深度封顶 12。**同一次点按耗时从 9.3s 降到 0.31s（约 30 倍）。**

> **通用规律**：AX 操作耗时与「实际访问到的节点数」近似线性正相关（每个属性都是一次跨进程往返）。操作原生弹窗/控件时，先用 role/层级把范围缩到最小的那棵子树（sheet / 指定 window / 指定 group），**永远不要无脑递归包含网页内容的整窗**。

### 5.2 轮询点按必须「串行」，并发 AppleScript 会拥塞堆积

调用方（Node）最初用 `setInterval` 每 0.6~0.9s 派生一个 osascript、且不等上一个结束。实测多个 AppleScript **并发**访问同一个 System Events 目标时会串行排队、互相死等，子进程全部卡在 S 状态、越积越多，没有一个走到点按动作——表现为「弹窗一直点不掉、时好时坏」（系统闲时第一个就点中，忙时永久卡死）。改为**串行点击循环**：同一时刻最多一个 osascript，上一次结束（或硬超时）后再排下一次；停止时主动 kill 在途子进程。修复后连续 8 次连接 osascript 残留恒为 0、全部成功。

> **通用规律**：不要并发发起多个操作同一目标的 AppleScript / System Events 调用；自动化轮询用「串行循环 + 单次硬超时 + 在途清理」，不要用不等返回的 `setInterval` 并发轰炸。

### 5.3 点中即停 + 全程容错，避免访问失效子树

点中「允许」后 sheet 会**立即关闭**，若递归仍在继续，就会访问已失效元素而抛错——事办成了、脚本却以非 0 退出，被上层误判为失败。对策：全局 `gPressed` 标志，点中后各层立即停止递归；`perform action` 单独包 try；整块遍历 `on error` 兜底；进程未就绪 / 无弹窗都安静返回 `pressed=false` 且退出码 0。

### 5.4 最终行为与调用

- role 先筛 `AXButton`，拼接 title/description/value/help 匹配「允许」（文字在 AXDescription，见 §2），对其 `AXPress`；
- 无弹窗返回 `pressed=false`、退出码 0，可被安全重复调用；
- 由连接模块的**串行点击循环**在连接/重试期间调用，吸收「连接↔弹窗」竞态。

调用（Node 内，单次硬超时 2500ms）：
```js
const { execFile } = require('child_process');
execFile('osascript', ['code/scripts/cdp/press_allow.applescript'], { timeout: 2500 }, (e, out) => { /* ... */ });
```
手工调试：
```bash
osascript code/scripts/cdp/press_allow.applescript     # 有弹窗 pressed=true 并点掉；无弹窗 pressed=false、退出码 0
```

---

## 6. 工具链选型

| 工具 | 语言/形态 | 适用 | 备注 |
|---|---|---|---|
| **osascript + System Events（本项目）** | 系统自带 AppleScript | 零安装、快速搞定原生控件与系统弹窗 | 复杂逻辑略啰嗦；文件形式比 `osascript -e` 多行更稳（避免 -1708 等转义问题） |
| `synthemesc/ax` | 现代 CLI（`ax ls/click/action/...`） | 命令行列显示器/App/窗口/元素树、执行 action | 比 AppleScript 更适合交互式探查 |
| `steipete/AXorcist` | Swift 链式封装 | 在 Swift 程序里模糊查询/读取/点击 | 仅 macOS |
| `namuan/swift-wright` | Swift，选择器语法 | 用 `button#id`、`[title~=x]` 这类选择器定位 | 适合结构化定位 |
| AXUIElement C API / AppKit NSAccessibility | C/ObjC/Swift | 需要极致控制或做成产品 | 底层能力，上述工具都基于它 |
| cliclick / CGEvent | 坐标点击 | 仅在元素树读不到时兜底 | 多屏需自行换算坐标 |

探查阶段建议先用 `ax ls` 之类把元素树打印出来定位，再决定用 AppleScript 还是代码实现。

---

## 7. 排障对策

| 症状 | 原因 | 对策 |
|---|---|---|
| 脚本报辅助功能/权限错误（-1719 等） | 终端/宿主未被授予辅助功能权限 | 系统设置里勾选；换了运行宿主（如 IDE/终端）要重新授权 |
| 按 title 找不到按钮 | 文本在 description/value/help | 拼接多属性匹配（见 §2） |
| 坐标点击后弹窗消失但功能没生效 | 安全 sheet 丢弃合成坐标点击 | 改用元素级 AXPress，并以业务状态复验 |
| 多屏时点到另一块屏/点空 | 用了写死坐标、混淆两套坐标系 | 用 AXPress；或动态读元素 position/size 算中心（§3） |
| 遍历 AX 树中途报错中断 | 个别属性/元素读取抛异常 | 每次取值包 try、设递归深度上限 |
| `osascript -e` 多行脚本报 -1708 | 命令行转义/换行问题 | 写成 `.applescript` 文件再执行 |
| 遍历/点按有时灵有时不灵、甚至永久卡住 | ①递归进了网页 AXWebArea，单次遍历长达数秒被上层超时杀掉；②多个 osascript 并发访问 System Events 拥塞堆积 | 只遍历 sheet/最小子树并跳过 AXWebArea；改串行点击循环 + 单次硬超时 + 在途清理（§5.1/5.2） |
| 点中后脚本报错、退出码非 0（事办成却判失败） | 点中后 sheet 立即关闭，递归继续访问已失效元素 | 点中即停标志 + perform/遍历全程 try 容错（§5.3） |
| 读不到弹窗里的按钮 | 整体读 contents 被隔离 | 递归逐元素扫描，但范围限定在 sheet 内（§5） |

---

## 8. 官方与权威资料（链接可能过时，附关键词）

> 核对日期 2026-09-01；链接失效用关键词检索官方/权威源。

| 主题 | 链接 | 备用检索关键词 |
|---|---|---|
| AXUIElement C API（元素、属性、perform action） | https://developer.apple.com/documentation/applicationservices/axuielement_h | `AXUIElementCopyAttributeValue AXUIElementPerformAction macOS` |
| AppKit 无障碍协议（属性与坐标转换） | https://developer.apple.com/documentation/appkit/nsaccessibilityprotocol | `NSAccessibility protocol accessibilityFrame accessibilityPointInScreen` |
| 无障碍坐标空间说明 | https://developer.apple.com/documentation/Accessibility/integrating-accessibility-into-your-app | `NSAccessibilityPointInView screen coordinate space` |
| 元素动作无需聚焦/移动鼠标的机制 | https://bridge.surf/blog/macos-can-support-two-cursors-at-the-same-time | `macOS AXPress native control no focus cursor computer use` |
| 合成坐标点击被部分控件丢弃、勿凭截图估点 | https://macos-use.dev/t/drive-native-macos-apps-ax-tree-mcp | `macOS synthetic CGEvent dropped Catalyst accessibility tree ground truth` |
| 多屏全局坐标 | https://developer.apple.com/documentation/coregraphics/cgdisplay | `CGDisplayBounds CGGetActiveDisplayList global display coordinate NSScreen` |
| Chrome 调试授权自动点（社区参考实现） | https://github.com/ochen1/chrome-devtools-mcp-auto-allow-macos | `chrome devtools auto allow remote debugging macos hammerspoon AXPress` |
| 现代 AX CLI / Swift 库 | https://github.com/synthemesc/ax 、https://github.com/steipete/AXorcist | `macOS accessibility CLI ax ls AXUIElement swift` |

---

**文档维护记录**

| 日期 | 变更内容 | 维护者 |
|------|---------|--------|
| 2026-09-01 | 初始版本：元素级 vs 坐标级、多属性定位、多屏坐标、SOP、工具链、排障与检索入口 | AI自动维护 |
| 2026-09-01 | 二次迭代（实测修正）：补三条通用规律——只遍历 sheet 勿入网页 AXWebArea（9.3s→0.31s）、AppleScript 串行勿并发堆积、点中即停+容错；同步更新 SOP 与排障表 | AI自动维护 |
