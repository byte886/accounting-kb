# 飞书 API 使用注意事项

> **文档类型**：Reference（参考资料）
> **更新频率**：API变更时
> **维护者**：AI自动维护
> **读者**：AI代理

本文档记录使用 `lark-cli` 操作飞书 API 时遇到的技术问题、解决方案和最佳实践。

---

## 一、Wiki 节点操作

### 1.1 删除节点：必须用 URL 方式，不能用 raw token

**问题**：使用 `lark-cli wiki +node-delete` 删除节点时，如果用 raw token + `--space-id` + `--obj-type docx`，会报 `node not found`（错误码 131005）。

**错误示例**：
```bash
# ❌ 会报 node not found (code 131005)
lark-cli wiki +node-delete \
  --space-id 7678261729456852192 \
  --node-token J9g6wQ14wilTqHktEH1c5TkUn2f \
  --obj-type docx \
  --yes
```

**正确示例**：
```bash
# ✅ 用 URL 方式，自动解析 space_id 和 obj_type
lark-cli wiki +node-delete \
  --node-token "https://zcnjheoajxng.feishu.cn/wiki/J9g6wQ14wilTqHktEH1c5TkUn2f" \
  --yes
```

**原因**：URL 方式会自动调用 `get_node` 解析正确的 `space_id` 和 `obj_type`，而 raw token 方式可能因为参数不匹配导致找不到节点。

**最佳实践**：所有 wiki 节点操作（删除、获取信息等）优先使用 URL 方式传入 `--node-token`。

---

### 1.2 node-list 参数名

**正确参数名**：
- `--space-id`（不是 `--space`）
- `--parent-node-token`（不是 `--parent-node`）

**示例**：
```bash
lark-cli wiki +node-list \
  --space-id 7678261729456852192 \
  --parent-node-token UM6bwW23tiYkCVk3nXtc3TpBnGe
```

---

### 1.3 node-get 的 obj-type 不接受 "wiki"

**问题**：`lark-cli wiki +node-get --obj-type wiki` 会报错，因为 `--obj-type` 只接受 `doc, docx, sheet, bitable, mindnote, slides, file`。

**正确方式**：用 URL 方式，自动推断 obj_type：
```bash
lark-cli wiki +node-get \
  --node-token "https://zcnjheoajxng.feishu.cn/wiki/J9g6wQ14wilTqHktEH1c5TkUn2f"
```

---

### 1.4 移动节点用 wiki +move 的 node 模式（同步、整棵子树随动）

整理知识库结构时，用 node 模式移动**已有 wiki 节点**（不要用 docs-to-wiki 模式）：

```bash
# 把某节点移到新父节点下；同步返回，node_token 与正文不变，其整棵子树随父移动
lark-cli wiki +move \
  --node-token <被移动节点 wiki node token> \
  --target-parent-token <目标父节点 wiki node token> --as user
```

- 移动到空间根目录用 `--target-space-id <space_id>`（与 `--target-parent-token` 二选一）。
- 移动是高风险写操作，先出移动清单经确认；先建好目标父节点、拿到 token 再移。

### 1.5 删除节点默认级联删子树，删前必须核验为空

`wiki +node-delete` **默认 `--include-children=true`，会把整棵子树一起删掉**。因此：

```bash
# 1) 先列直接子节点，确认数量为 0
lark-cli wiki +node-list --space-id <sid> --parent-node-token <待删节点> --as user
# 2) 确认为空壳后再删（raw node token 配 --obj-type wiki，高风险需 --yes）
lark-cli wiki +node-delete --node-token <token> --obj-type wiki \
  --space-id <sid> --yes --as user
```

只删"内容已全部迁出、确认废弃"的空分组；非空或用户未明确同意的节点一律保留。错误码 `131011` 表示该空间开启了删除审批，CLI 无法绕过，需到 Web 界面处理。

---

## 二、文档内容操作

### 2.1 docs +update 的 --content 不接受绝对路径

**问题**：`lark-cli docs +update --content /tmp/file.md` 会报错，因为 `--content` 只接受相对路径（当前目录内）或 stdin。

**错误示例**：
```bash
# ❌ 报错：invalid file path, must be a relative path within the current directory
lark-cli docs +update --doc <token> --command overwrite --content @/tmp/file.md
```

**正确方式1**：用相对路径
```bash
# ✅ 文件放在当前目录下
lark-cli docs +update --doc <token> --command overwrite --content @./file.md
```

**正确方式2**：用 stdin（适合短内容；长内容/批量的注意事项见 2.3）
```bash
# ✅ 通过管道传递内容
cat << 'EOF' | lark-cli docs +update --doc <token> --command overwrite --doc-format markdown --content -
# 文档标题
内容...
EOF
```

---

### 2.2 Markdown 格式更新

使用 `--doc-format markdown` 可以用 Markdown 格式更新文档，支持标准 Markdown 语法：
- 标题：`#`, `##`, `###`
- 链接：`[文本](URL)`
- 引用：`> 引用内容`
- 列表：`- 项目` 或 `1. 项目`
- 表格：标准 Markdown 表格
- 分割线：`---`

**示例**：
```bash
cat << 'EOF' | lark-cli docs +update \
  --doc EV7vdI57wopS2ixYUbFcQPKmnwQ \
  --command overwrite \
  --doc-format markdown \
  --content -
> 课程：2026 CPA 税法-全面精讲 | 主讲：蔡俊峻老师

## 本章内容

### 知识本身
[第一章 税法总论](https://...)
EOF
```

---

### 2.3 长内容/批量优先 @file：stdin 在命令转后台时可能静默未写入

**问题（实测）**：用 heredoc 经 stdin（`--content -`）传较长内容时，若命令超过前台等待被自动转入后台，stdin 可能与终端断连，导致**命令看似跑完、正文却没写进去**（fetch 回读发现仍是旧内容），且不一定报错。

**最佳实践**：
- 短内容可直接 stdin；**多行/长内容、一次写多篇时，优先把内容落成 cwd 内文件，用 `@./file.md` 传参**，最稳。
- **任何写操作后必须 `docs +fetch` 回读验证**（长度、链接数、关键字），不能只看返回 `success`。

### 2.4 站内导航用 `<cite>` 内部引用；不要用变量/占位符

带引号的 heredoc（`<<'EOF'`）**不会展开 shell 变量**。若正文里写 `%BASE%/xxx`、`$W/xxx` 这类占位符，会原样写入形成坏链。

- **指向知识库内其他文档**：一律写 `<cite type="doc" doc-id="obj_token"/>`（`doc-id` 用 obj_token）。飞书渲染为目标文档标题（蓝色内部引用），由 obj_token 强绑定、可回读自动校验坏链；Markdown 流中可直接内嵌该标签，由 `wiki_link_resolve.py` 从本地相对链接自动转换。
- **打开方式（2026-09-07 真实 Chrome CDP 可信点击实测）**：cite 与完整 URL 一样，点击都在**新标签页**打开——飞书正文跨文档跳转统一新开，任何写入格式（cite/按钮/书签/普通链接/子页面列表）都无法改成当前窗口，唯一当前窗口切换是左侧知识库目录树。选 cite 而非完整 URL，是因为它结构化、显示标题、obj 强绑定可校验，**不是**因为打开方式不同；完整 URL 仅用于站外链接。详见 `guides/wiki-link-verification-sop.md`。
- 写完用正则回查：不应残留 `%`、`$` 类占位符；站内导航不应残留 `href="https://.../wiki/..."` 普通链接。

### 2.5 docs +fetch / +update 可直接吃 wiki node token

`--doc` 既能传 obj_token（docx token）/文档 URL，也能直接传 **wiki node token**，CLI 会自动解析，无需先 `node-get` 换 obj_token。注意区分：命令入参传 node/obj token 或 URL 均可；但**正文里的站内导航链接**用 `<cite type="doc" doc-id="obj_token"/>`（结构化内部引用，点击新开标签、单窗口连续阅读走左侧知识库目录树），不用 `/wiki/<node_token>` 完整 URL（冗长、易随节点变动失效）。

---

## 三、权限设置

### 3.1 文档对外分享：API 可能受组织策略限制

**问题**：使用 `lark-cli drive permission.public patch` 设置文档为"互联网获得链接的人可阅读"时，可能报 `Permission denied`（错误码 1063002）。

**原因**：组织管理员设置了安全策略，禁止通过 API 将文档分享到组织外。

**解决方案**：通过飞书网页界面手动设置分享权限（界面操作不受 API 权限限制）。

**界面操作流程**：
1. 打开文档
2. 点击右上角「Share」按钮
3. 点击「组织名称」下拉菜单
4. 选择「Anyone with the link」
5. 选择「Current page and sub-pages」（应用到子页面）
6. 点击「Confirm」确认法律责任提示

---

## 四、通用最佳实践

### 4.1 优先使用 URL 方式传入 token

所有需要 token 的操作（wiki 节点、文档等），优先使用完整 URL 传入，让 CLI 自动解析 token 类型和相关参数：

```bash
# ✅ 推荐：URL 方式，自动解析
lark-cli wiki +node-get --node-token "https://zcnjheoajxng.feishu.cn/wiki/<token>"
lark-cli docs +fetch --doc "https://zcnjheoajxng.feishu.cn/docx/<token>"
```

### 4.2 高风险操作需要 --yes

删除节点、删除文档等高风险写操作需要加 `--yes` 确认：
```bash
lark-cli wiki +node-delete --node-token "<URL>" --yes
```

### 4.3 输出可能被保存到文件

某些命令的输出（特别是 JSON 响应）可能被自动保存到 `download.txt` 文件，而不是直接输出到 stdout。需要读取该文件获取响应内容。

### 4.4 批量写操作的账号级滑动窗口限流（建树/批量同步必看）

**问题**：批量建 wiki 节点或批量 `docs +update` 时，跑一段后开始大面积失败：`+node-list` 持续返回空（脚本判"疑似限流"），`+node-create` 返回 `ok:false` 且 token 为空。会计课 169 节点建树实测出两个相互独立的账号级配额窗口：

- **查询窗口**：`node-list` 累计约 70 次调用（或连续新建 20-24 个节点期间的查重调用）后进入持续拒绝；
- **写窗口**：`node-create` / `docs +update` 累计约 36-40 次写后进入持续拒绝。

**原因与识别（别误判）**：这是飞书账号级滑动窗口频控，不是 token 失效、不是权限 scope、不是内容问题（响应里没有 `Authorization failed` / 登录超时类错误，且窗口前的同类调用绝大多数成功）。固定步进 sleep、25 秒级短休眠都不足以恢复，需要 60-90 秒级冷却。排查先怀疑调用节奏，不要一失败就判定登录失效让用户重新登录。

**最佳实践（建树四件套，已固化进 `code/scripts/knowledge/build_tree.py`，会计课从零多轮收敛到 169/169）**：

1. **组级缓存砍查询量**：进一个父节点只 `node-list` 一次、把全部直接子节点拉成本地 TSV，之后查重走本地（awk）不调网络；node-list 调用量从"每节点一次"（=节点数）降到"每组一次"（=组数，169 降到约 31）。
2. **写操作指数退避重试**：`node-create` / `docs +update` 失败不立即放弃，按 4s/8s/12s 退避重试 3 次扛瞬时抖动；只对限流类现象重试，`invalid_parameters`/`not_found` 不用同参重复。
3. **小批次长冷却**：每处理 8 个真实成功的写节点（FAIL 不计数）主动休眠 90 秒，把单窗口写次数压到阈值以下。参数：建树 `WIKI_BATCH=8 WIKI_BATCH_SLEEP=90`，正文覆盖 `RESYNC_BATCH_SIZE=8 RESYNC_BATCH_PAUSE=90`；节点间另留 1.5s 间隔。
4. **断点续跑 + 整组零网络跳过**：每个成功节点落一个 `done_flag`（`logs/wiki_done/<safe标题>.done`），重跑时已完成节点零 API 跳过；一个组（章）的组节点与其下知识点若全部有 done_flag，整组不 prefetch、不查重、直接 continue，续跑空跑穿过大量已建章不耗任何配额、直达未完成区，多轮收敛、重复跑安全。

**操作要点**：续跑前先 `ps` 确认无同类脚本残留（严防双开抢同一写窗口）；每轮跑完看进程是否自然退出（日志"同步完成"），再用"本地成品标题 vs done_flag"的正确口径列缺失（组节点按章目录名、知识点按 md 文件名去 .md，别用 README 当标题），冷却 60-90s 后只对缺失组续跑。

**纯 `docs +update` 正文批量覆盖（resync）的实测补充（2026-09-11 晚会计课 169 篇第二遍覆盖）**：

- **阈值更低**：纯写（无查询间隔）连续约 **15 篇**即触发，比建树 node-create 混合查询的 36-40 次更早（纯写密度高）。净写速率必须压到窗口恢复速率以下，稳态参数 `RESYNC_BATCH_SIZE=4 RESYNC_BATCH_PAUSE=120 RESYNC_INTERVAL=5`（每 4 篇休 120s、篇间 5s）。
- **失败真实形态**：`{"ok":false,"error":{"type":"internal","subtype":"invalid_response","message":"API returned an invalid JSON response: response parse error: invalid character 'e' looking for beginning of value"}}`，进程 rc=5——飞书网关在窗口内返回**非 JSON 文本**（以字母 e 开头）。仍不是 token/权限/内容问题，不要让用户重新登录。
- **恢复时长随累计深度递增**：浅窗口停写约 5 分钟；整晚密集写叠加失败重试会累积成深窗口，需**彻底静默约 15 分钟**。窗口内继续发请求会给窗口"续命"，固定短冷却反复试探反而恢复更慢。
- **标准解法（已固化进 `code/scripts/knowledge/resync_wiki_content.py`）**：①每篇成功落 `logs/resync_done/<safe标题>.done`，重跑零 API 跳过、多轮只补未成功、不重复消耗写配额（`--force` 全量重刷）；②worker 内按错误类型分流——`ext err`/`parse temporary token`/`invalid_response`（非 JSON）原地只重试 1 次（2s±20% 抖动）再败 `exit 2` 交外层换新进程；HTTP 429 读 `Retry-After`；其他网络错最多 3 次（1→2→4→8→16s 封顶 30s，±20% 抖动）；③单进程写满 `RESYNC_MAX_NEW=20` 篇主动退出；④每次失败打印 rc 与原始返回。收敛判据：`ls logs/resync_done | wc -l` = 总数、进程自然退出。

> **根因更正与最终方案（2026-09-12 凌晨会计 169 篇收尾时终查，以此为准）**：上面对"飞书账号写窗口、停写静默即恢复"的判断**不准确**。
>
> - **真正根因**：沙箱里 `lark-cli` 并非直连飞书，而是经豆包转发代理 `DOUBAO_OFFICE_FORWARD_PROXY`（`www.doubao.com/alice/office/sandbox/lark_cli/proxy`）访问。**代理层对"单个进程/会话的累计请求数"有限流**，累计到阈值后对后续请求返回非 JSON 纯文本错误（以字母 e 开头），lark-cli 解析失败即报 `invalid_response ... invalid character 'e'`、rc=5。这不是飞书账号限流、不是 token、不是权限、不是内容、不是 locale/stdin 管道/nohup 环境。
> - **决定性判别证据**：长期后台脚本连续跑到失败时，①停掉后用**全新 shell 手动单发同一篇立即成功**；②前台一次性 Python subprocess 连续 10 篇全成功、nohup 单篇也成功，唯独**长期单进程累计十几篇后必失败**；③彻底静默 30 分钟后，旧进程第一发仍失败，而换新进程立即成功——所以**决定因素是"新进程=新代理会话"，不是静默时长**。
> - **最终方案：Worker Supervisor 模式**（`code/scripts/knowledge/run_resync_batches.sh`，财管 145 篇实测收敛）：worker（`resync_wiki_content.py`）退出后 Supervisor **立即拉起新 worker**，不做长休眠；连续 `RESYNC_FAIL_MAX=5` 次无进展重启（`rc≠0` 或本轮新增=0）才短休 `RESYNC_COOLDOWN=30s`；done 数达标（=map行数+1）Supervisor 自退；done 列表落 `logs/resync_done/*.done` 持久化，任意中断/重入不丢。
> - **排查口诀**：再遇到 `invalid_response` / rc=5 / 非 JSON（e 开头），**先停脚本用全新 shell 手动单发同一篇对照**——新进程成功即代理层累计限流，直接走批次法；不要误判飞书账号、不要让用户重新登录、不要只靠一味加长静默。
> - **第二层根因与 Supervisor 固化（2026-09-20 财管 145 篇 + 经济法 81 篇后定版，以此为准）**：外层 shell 凭证老化问题由 Supervisor 自动拉起新 worker 解决，无需人工手动换 shell——worker 写满 `RESYNC_MAX_NEW=20` 篇即 `exit 0`，Supervisor 立即起新 python 进程；连续 5 次无进展才短休 30s；done 列表持久化。进程内错误分类与指数退避+抖动（见上条）保留。财管/经济法实测收敛良好。
> - **同场另一个严重 bug（resolver 漏传 WIKI_MAP）**：`resync_wiki_content.py` 用 subprocess 调 `wiki_link_resolve.py` 时一度没传 `WIKI_MAP`，resolver 回退到不存在的仓库根 `logs/`、映射为空，导致 169 篇的 `./相对链接` **全部没转成 `<cite>`、飞书端退化成不可点纯文本**（写入却 ok，极隐蔽）。教训：①跨脚本 subprocess 必须显式传齐它依赖的环境变量/路径，不能假设默认值在当前 profile 成立；②resolver 映射为空、resync 处理后仍残留 `](./` 链接都已加 fail-loud 告警；③批量写入后必须 `docs +fetch` **回读飞书端**确认内链真的是 `<cite doc-id=...>`，不能只看写入 ok。

---

> 本文档记录飞书 API 使用中的技术问题和解决方案。遇到新问题时，按"问题→错误示例→正确示例→原因→最佳实践"的格式补充到本文档。
