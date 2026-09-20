# 飞书知识库链接验证 SOP

> **文档类型**：Task（操作指南）
> **更新频率**：流程变更时
> **维护者**：AI自动维护 + 用户审核
> **读者**：AI代理

## 目的

确保飞书知识库中所有内部链接①指向正确节点（无死链、错链、占位符坏链），②统一采用 `<cite>` 结构化内部引用（标题渲染、obj_token 强绑定、可自动校验）。同时固化"打开方式"的平台实测结论，避免再用 DOM 属性误判跳转行为。每次知识详解同步飞书后、或知识库结构调整后，必须执行本 SOP 验证。

## 核心约定一：内部链接一律用 `<cite>` 文档引用

选择 cite 而非完整 URL，**理由是结构化与可校验性，不是打开方式**（二者打开方式相同，见下节）：

| 写法 | 飞书渲染 | 是否采用 | 选择理由 |
|------|---------|---------|---------|
| `<cite type="doc" doc-id="obj_token"/>` | 文档标题（蓝色内部引用） | ✅ 唯一采用 | 渲染为目标标题、obj_token 强绑定、可回读自动校验 0 坏链 |
| 完整 URL `[文字](https://<域名>/wiki/<node>)` | 普通超链接 | ❌ 站内导航弃用 | URL 冗长、随节点变动易失效、无法结构化校验；仅外链使用 |
| `<cite type="citation">` 参考文献组件 | JS 弹层组件 | ❌ 不用于导航 | 弹层内链接仍新开 |

- cite 渲染文字固定为**目标文档标题**，因此本地相对链接的链接文字必须等于目标文件名（标题），税法课已全量核验 746 处一致；
- cite 的 `doc-id` 填 **obj_token（docx token，台账第 3 列）**，不是 node_token；
- 本地 Markdown 源文件保留 `./标题.md` 相对链接不动，仅在写入飞书的管道里由 `wiki_link_resolve.py` 转成 cite；Markdown 流中可直接内嵌该 XML 标签，飞书可识别。

## 核心约定二：打开方式的平台事实（2026-09-07 可信点击实测）

**飞书正文区跨文档跳转一律在新标签页打开，与写入格式无关；唯一"当前窗口切换文档"的入口是左侧知识库目录树。**

用真实 Chrome + CDP 可信鼠标点击（`Input.dispatchMouseEvent`，`isTrusted=true`，飞书无法拦截）逐种实测：

| 入口 | 标签页变化 | 当前页是否切换 | 结论 |
|------|-----------|--------------|------|
| `<cite>` 内部引用 | +1 | 否 | 新标签页 |
| `<button action="OpenLink">` | +1 | 否 | 新标签页 |
| `<bookmark>` 书签卡片 | +1 | 否 | 新标签页 |
| 普通 `<a>` 完整 URL | +1 | 否 | 新标签页 |
| 原生 `<sub-page-list/>` 子页面列表 | +1 | 否 | 新标签页 |
| **左侧知识库目录树节点** | **不变** | **是，URL 直接切换** | **当前窗口** |

佐证：lark-cli 官方仓库 issue #2399（2026-08-19）确认 API 写入的跨文档/锚点链接即新开，期望中的 `docsLink`（仅解决同一篇内滚动）至今未实现。

> ⚠️ **教训：禁止用 DOM 的 `target="_self"` 属性判定"本窗口打开"。** cite 渲染出的 `a.mention-doc` 虽带 `target="_self"`，但飞书 React 的 onclick 统一接管，真人左键点击仍新开标签。DOM 属性 ≠ 真实导航行为；判定打开方式只能靠 CDP 可信点击（合成 `dispatchEvent` 因 `isTrusted=false` 会被飞书拦截，同样不可信）。

**单窗口阅读方案（方案 B）**：正文 cite 全部保留（阅读中偶尔引用，新开可接受），在**导航型页面**（课程总览页、14 章 README）顶部加统一导航说明，引导读者用左侧目录树做单窗口连续阅读；92 篇知识点详解与 2 篇全局资料是纯内容页，不加，避免重复堆砌。

## 验证范围（三层）

| 层级 | 位置 | 链接数量（税法课参考值） | 形态 |
|------|------|--------------------------|------|
| 第一层 | 课程总览页（课程根节点） | 16 | 14 章入口 cite + 2 篇全局资料 cite |
| 第二层 | 14 章 README「知识点目录」 | 92 | 每章指向该章各知识点详解的 cite |
| 第三层 | 92 篇知识点详解「关联知识点」 | 654 | 知识点之间互相跳转的 cite |
| **合计** | | **762** | 全部为 cite、doc-id 全部在台账内 |

> 总览页不设"知识拆解 / 考试指导"两列：每章只保留一个章入口 cite，章内"知识点目录"即知识拆解、"重点内容"即该章考试指导；跨章横向汇总由全局两篇 cite 承担。

## 前置条件

1. **节点台账**：`logs/wiki_node_map.tsv` 存在、**已去重**（每标题唯一一行），格式 `标题\tnode_token\tobj_token\tparent_node_token`；
2. **lark-cli 可用**：已登录，`--as user` 身份可访问目标知识空间；
3. **本地链接预检通过**：本地 md 相对链接全部能匹配台账标题，且链接文字等于目标文件名。

## 验证步骤

### 第一步：本地链接预检（同步飞书前）

```bash
# 1) 相对链接目标必须都能在台账标题列找到；预期 0 未匹配
# 2) 链接文字必须等于目标文件名（决定 cite 渲染文字是否与原文一致）
python3 - << 'PY'
import glob, os, re
TITLE_COL = set(l.split('\t')[0] for l in open('logs/wiki_node_map.tsv', encoding='utf-8'))
bad_target, bad_label = [], []
for md in glob.glob('data/**/知识详解/**/*.md', recursive=True):
    for m in re.finditer(r'\[([^\]]+)\]\(\./([^)]+?)\.md\)', open(md, encoding='utf-8').read()):
        label, target = m.group(1), m.group(2)
        if target not in TITLE_COL: bad_target.append((os.path.basename(md), target))
        if label != target: bad_label.append((os.path.basename(md), label, target))
print('目标无映射:', len(bad_target), bad_target[:5])
print('文字≠标题:', len(bad_label), bad_label[:5])
PY
```

任一非 0 都需先修复本地文件，再同步。

### 第二步：转换管道本地验证（不写飞书）

```bash
# 任意一篇经 wiki_link_resolve.py 转换后，应只剩 cite、无残留相对链接
cat "data/.../知识详解/01_税法总论/README.md" | python3 code/scripts/check/wiki_link_resolve.py
# 预期：[标题](./标题.md) 全部变为 <cite type="doc" doc-id="obj_token"/>
# stderr 不应出现"未找到节点映射"
```

### 第三步：飞书回读验证（同步后，正确性主验证）

cite 回读形态为 `<cite doc-id="obj_token" file-type="docx" title="标题" type="doc"></cite>`，按 **doc-id 与台账 obj_token 比对**。

```bash
# 回读一篇（以课程根总览页为例）
lark-cli docs +fetch --doc <obj_token> --doc-format xml --as user --format json > /tmp/doc.json

python3 - << 'PY'
import json, re
x = json.load(open('/tmp/doc.json'))['data']['document']['content']
cites = re.findall(r'<cite doc-id="([^"]+)"[^>]*title="([^"]*)"', x)
obj_col = set(l.split('\t')[2] for l in open('logs/wiki_node_map.tsv', encoding='utf-8'))
bad = [(t, o) for o, t in cites if o not in obj_col]
# 站内导航不应残留完整 feishu URL（外链除外）
plain = re.findall(r'<a href="https://[^"]*feishu[^"]*"', x)
print(f'cite 数: {len(cites)}, 指向台账外: {len(bad)}, 残留完整URL链接: {len(plain)}')
PY
```

批量回读可复用 `code/scripts/knowledge/resync_wiki_content.py` 的对应遍历逻辑，对 108 篇逐篇统计 cite 数与坏链。

### 第四步：导航说明存在性检查（方案 B）

导航型页面顶部必须有引导左侧树单窗口阅读的说明块，纯内容页不加：

```bash
# 总览页 + 14 章 README 各应有 1 处"导航说明/导航："；知识点篇应为 0
python3 - << 'PY'
import glob, subprocess, json
# 飞书侧：fetch 后统计 "左侧知识库目录树" 出现次数；总览=1、每章 README=1
# 本地侧快速核对：
for rd in sorted(glob.glob('data/**/知识详解/[0-9]*/README.md', recursive=True)):
    s = open(rd, encoding='utf-8').read()
    assert '左侧知识库目录树' in s, rd
print('14 章 README 导航说明齐全')
PY
```

### 第五步（可选）：打开方式可信点击复核

仅当怀疑飞书前端行为变化时做。**必须用真实 Chrome + puppeteer-core CDP**（连接方式见 `docs/development/tools/browser-cdp-connect-guide.md`），用 `page.mouse.click()`（底层 `Input.dispatchMouseEvent`，`isTrusted=true`）点击，监听 `browser.on('targetcreated')` 与当前页 `page.url()`：

- 点正文 cite：标签数 +1、当前页 url 不变 = 新标签页（符合平台事实）；
- 点左侧目录树节点：标签数不变、当前页 url 切换 = 当前窗口。

禁止用 `bu.dispatchEvent` / `element.click()`（`isTrusted=false`，会被飞书拦截，结论失真），也禁止只看 `target` 属性下结论。

### 第六步：汇总报告

```
=== 飞书链接验证报告 ===
第一层 总览页:    16 cite, 0 坏链, 0 残留完整URL, 导航说明 1
第二层 章README:  92 cite, 0 坏链, 0 残留完整URL, 导航说明 14/14
第三层 知识点:   654 cite, 0 坏链, 0 残留完整URL（纯内容页无导航说明）
合计:            762 cite, 0 错误
打开方式:        正文 cite 统一新开标签（平台固定）；单窗口走左侧目录树（已在导航页说明）
结论: 全部通过
```

## 常见问题与修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 回读出现完整 URL `<a href=.../wiki/...>` | 旧版同步产物，或误用 markdown 链接 | 用 `resync_wiki_content.py` 以新版 `wiki_link_resolve.py`（输出 cite）重同步 |
| cite 整块变空 | doc-id 误填 node_token，或拼了不存在的 obj_token | 改用台账第 3 列 obj_token；`wiki +node-get` 可反查 |
| 转换时 stderr 报"未找到节点映射" | 本地链接目标与台账标题不一致，或台账缺该节点 | 先补/修台账或本地文件名，禁止臆造 token |
| cite 渲染文字与原文链接文字不符 | 链接文字≠目标文档标题 | 修改本地链接文字等于文件名（标题）后重同步 |
| 误以为"cite 带 target=_self 就本窗口打开" | 把 DOM 属性当成真实导航行为 | 见"核心约定二"：以 CDP 可信点击为准，正文 cite 一律新开 |
| 总览页多行指向同一篇全局手册 | 误把"考试指导"列统一指向全局速查 | 每章入口 cite 必须指向该章 README 的 obj_token，全局手册只在"全局资料"出现一次 |
| 台账出现同标题多行 | 历史同步重复追加（节点未必重复） | 先按整行去重；若同标题对应不同 obj_token，才说明飞书有重复节点需人工核对删除 |

## 验收标准

- 三层合计 0 坏链、0 台账外 doc-id、0 残留完整 URL 站内链接；
- cite 渲染标题均为有意义的文档名（无 `[链接]`、`[点击查看]` 等占位符）；
- 导航型页面（总览页 1 + 14 章 README）顶部各有 1 处左侧树单窗口导航说明，纯内容页不加；
- 课程总览页章入口行数与章数一致（税法课 14 行 + 全局 2 篇）；
- **不**再以 `target="_self"` 作为"本窗口打开"的验收项（DOM 属性不代表真实行为）。

## 参考

- 节点台账：`logs/wiki_node_map.tsv`（标题 / node / obj / parent，已去重）
- 链接解析：`code/scripts/check/wiki_link_resolve.py`（相对链接 → cite，stdin/stdout 过滤器）
- 总览页生成：`code/scripts/knowledge/build_course_overview.py`（`--format xml` 飞书 / `--format markdown` 本地源）
- 内容重同步：`code/scripts/knowledge/resync_wiki_content.py`（只覆盖内容、不建节点，`--dry-run` 预检；写入前自动剥离知识详解顶部 OKF frontmatter，飞书不显示 YAML）
- 首次建树（课程容器→章/全局篇→知识点）：`code/scripts/knowledge/build_tree.py <profile>`（配置驱动，新 8 课模型，见 [wiki-sync-sop.md](wiki-sync-sop.md)）
- 飞书 API：`lark-cli docs +fetch`（回读）、`lark-cli docs +update --command overwrite`（覆盖）
- 打开方式佐证：lark-cli issue #2399（docsLink 同文档跳转尚未实现）
- 相关 ADR：[ADR-012](../../project-management/decisions/ADR-012-三层解耦与按知识点聚合.md)（飞书与本地同构）
