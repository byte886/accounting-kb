# 飞书知识库同步 SOP（新空间 8 课模型）

> **文档类型**：Task（操作指南，现役权威）
> **更新频率**：流程/脚本变更时
> **维护者**：AI 自动维护 + 用户审核
> **读者**：AI 代理
> **最近重构**：2026-09-19（旧"四棵树/课程根→组→点"模型与 `sync_wiki_new.sh`、`auto_sync_all.*`、`verify_sync_completeness.py` 已退役入 `.trash/`，统一为本模型）

## 目的

规范课程知识详解从**本地唯一源头**同步到飞书新知识库的完整流程：建树 → 正文同步 → 全量回读验收，做到配置驱动、可断点续跑、可重复执行、一门课一验收。

**铁律**：
1. **本地是唯一源头**：所有成品先在课程目录 `知识详解/` 完成并过校验，再同步飞书；**禁止直接在飞书手工改成品**。
2. **一门课一验收、同一时刻只有一个写进程**：严禁多窗口/多脚本并发写同一空间（会抢转发代理写窗口、产生重复/错挂节点）。开跑前先 `ps` 清残留。
3. **只信脚本与回读，不信"写入 ok"**：节点结构看 `verify_wiki_tree.py`，正文非空/标题对得上看 `verify_wiki_content.py`。

**与其他 SOP 的分工**：
- 本文档：建树、正文同步、限流、错误恢复、双验收编排
- [wiki-link-verification-sop.md](./wiki-link-verification-sop.md)：同步后内部链接（`<cite>`、坏链）验证
- [wiki-content-verification-sop.md](./wiki-content-verification-sop.md)：章节点五要素、知识点四节结构等内容质量验证
- 限流根因与 lark-cli 细节：[../api/feishu-api.md](../api/feishu-api.md)

---

## 0. 固定坐标与 8 门课清单

- 知识空间「CPA备考知识库」`space_id = 7686897234545249236`
- 空间根节点「课程库」`rootParentNodeToken = K4IcwWg6HidyY6k6Z8hcdmGFnth`
- 层级：**课程库 → 全称课程容器（容器本身=课程首页）→ 章 / 全局篇 → 知识点**
- 老空间 `7678261729456852192` 仅剩 CPA 级《通用做题思路解析》，**新课一律建新空间，勿写老空间**。

| profile | 科目/老师 | 课程容器标题（=配置卡 primaryCourse.name） | 规模（参考，以本地/map 实测为准） |
|---|---|---|---|
| `cpa-accounting-2026` | 会计·罗翔（正课） | 【26考季】VIPCPA系列-会计（罗翔老师） | 30 章 / 137 点 / 2 全局 = 169 + 首页 ✅已建已验收 |
| `cpa-tax-2026` | 税法·蔡俊峻（正课） | 【26考季】VIPCPA系列-税法（蔡俊峻老师） | 14 章 / 92 点 / 2 全局 = 108 |
| `ep3-accounting-2026` | 名师·会计 | 【VIPCPA专享】名师专业课-会计 | 约 176 篇 |
| `ep3-audit-2026` | 名师·审计 | 【VIPCPA专享】名师专业课-审计 | 约 132 篇 |
| `ep3-finance-2026` | 名师·财管 | 【VIPCPA专享】名师专业课-财管 | 约 144 篇 |
| `ep3-strategy-2026` | 名师·战略 | 【VIPCPA专享】名师专业课-战略 | 约 77 篇 |
| `ep3-tax-2026` | 名师·税法 | 【VIPCPA专享】名师专业课-税法 | 约 107 篇 |
| `ep3-econlaw-2026` | 名师·经济法 | 【VIPCPA专享】名师专业课-经济法 | 约 80 篇 |

> 容器标题、space、root 都从配置卡 `config/courses/<profile>.json` 的 `primaryCourse.name` 与 `wiki` 块读取，**不要在命令里手填标题**。建树后脚本自动回写 `wiki.courseNodeToken / courseObjToken`。

---

## 1. 同步前检查（必做）

1. **本地成品过校验门**：
   - `python3 scripts/okf_validate.py "<课程知识详解目录>"` 硬错误 E=0；
   - 章 README 五要素、知识点篇四节结构齐全（模板见 [../templates/KNOWLEDGE_BASE_TEMPLATE.md](../templates/KNOWLEDGE_BASE_TEMPLATE.md)）。
2. **配置卡合法且指向新空间**：
   - `python3 scripts/knowledge/course_profile.py <profile>` 能正常打印（校验 key / primaryCourse.saasCourseId / subject.id / paths.localRoot）；
   - `wiki.spaceId=7686897234545249236`、`wiki.rootParentNodeToken=K4Icw…nth`；已建过的课有 `courseNodeToken/courseObjToken`，未建的课这两项留空（建树自动回写）；
   - `paths.localRoot` 与 `primaryCourse.name` 自洽，**一卡一课**，禁止改 cpa 卡 localRoot 借指名师课。
3. **⚠️ 换空间重建先归档旧 map（最易踩）**：若该 profile 的 `data/_workspace/<profile>/logs/wiki_node_map.tsv` 是**老空间**遗留，先改名归档（如 `wiki_node_map.oldspace.tsv`），否则建树按标题幂等会命中老 token、不在新容器建树。会计 map 已是新空间，**禁止重置**。
4. **lark-cli 可用**：`lark-cli auth status` 已登录；只读冒烟：
   `lark-cli wiki +node-list --space-id 7686897234545249236 --parent-node-token K4IcwWg6HidyY6k6Z8hcdmGFnth --as user --format json`
5. **清残留写进程**：`ps aux | grep -E "build_tree|resync_wiki|run_resync|sync_with_restart" | grep -v grep`，确认没有别的同步在跑（含其他豆包窗口/异步任务；豆包"工作任务"是服务端异步，停止入口在该任务对话内，OS 层 kill 不住）。

---

## 2. 第一步：建树（课程容器 + 章/点/全局，只建结构不写正文）

```bash
python3 scripts/knowledge/build_tree.py <profile>
```

脚本行为（幂等，可反复续跑）：
1. 读配置卡 `wiki.spaceId / rootParentNodeToken / primaryCourse.name`；
2. 在「课程库」根下按标题确保**全称课程容器**存在（已存在则复用），并把 `courseNodeToken / courseObjToken` 回写配置卡；
3. 在内容器建：章（章目录名，对应章 README）→ 章下知识点（md 文件名去 `.md`）→ 知识详解根目录全局篇；
4. **根 `知识详解/README.md` 是课程首页、对应容器本身，不建子节点**（正文由第二步写入容器）；
5. 映射逐行追加 `data/_workspace/<profile>/logs/wiki_node_map.tsv`（title / node / obj / parent），已在 map 的标题零网络跳过。

兼容旧用法（不建容器、直接挂某父节点）：`build_tree.py <profile> <parent_token> <course_dir>`。

> 章/点标题以**本地目录名/文件名**为准，并须与文件 frontmatter `title`、根 README 课程首页表格一致。会计课曾出现本地目录被截断成 `17_收入`（frontmatter 与飞书都是全称 `17_收入、费用和利润`）的不一致，建树/验收前先核对本地目录名是否为官方全称；若本地目录名截断，先改本地目录名 + 相对链接 + map 标题键（token 不变），不要反过来迁就错误短名。

---

## 3. 第二步：正文同步（分批换新进程，绕转发代理限流）

先预检（不写飞书），确认条目数与映射齐全：

```bash
python3 scripts/knowledge/resync_wiki_content.py --profile <profile> --dry-run
```

应输出 `待处理文件 N 个（map 共 M 个标题）`，其中 **N = M + 1**（多 1 个课程首页 `__COURSE_HOMEPAGE__`），且无"无 obj 映射"。

正式批量同步（推荐驱动，自动换新进程）：

```bash
# Supervisor 模式：worker 写满 20 篇即退出，Supervisor 立即拉起新 worker（不长休眠）；总篇数自动=map行数+首页；连续 5 次无进展才短休 30s，done 数达标自退
nohup bash scripts/knowledge/run_resync_batches.sh <profile> 20 75 > /tmp/resync_<profile>.out 2>&1 &
tail -f data/_workspace/<profile>/logs/resync_wiki.log
```

- 每篇成功落 `data/_workspace/<profile>/logs/resync_done/<safe标题>.done`，课程首页落 `__COURSE_HOMEPAGE__.done`；断点续跑、任意中断可重入，`--force` 才全量重刷。
- 正文写入前自动剥离顶部 OKF frontmatter（飞书读者看不到 YAML），相对链接经 `scripts/wiki_link_resolve.py` 转 `<cite>`（resync 已显式传 `WIKI_MAP`，勿绕过）。
- 备用驱动 `scripts/knowledge/sync_with_restart.sh <profile> [max_new] [interval] [batch_pause] [batch_rest]`（前台 tee 日志，参数含义见脚本头）。

### 重新建树后（删旧节点重建）

map 会更新，但旧 `resync_done/` 标记仍在；为防"只同步了章 README、知识点遗漏"，重建后应清空 done 全量重跑：

```bash
rm -rf data/_workspace/<profile>/logs/resync_done/
nohup bash scripts/knowledge/run_resync_batches.sh <profile> 20 75 > /tmp/resync_<profile>.out 2>&1 &
```

### 限流处置（转发代理，非飞书账号/token/内容问题）

- 现象：`invalid_response`、`parse temporary token`、`invalid character 'e'`、非 JSON 以 `e` 开头、rc=5。
- 根因两层：①单 lark-cli/python 进程累计请求到阈值→**换新进程**即恢复；②`run_resync_batches.sh` 已是 Worker Supervisor 模式——worker 写满 `RESYNC_MAX_NEW=20` 篇主动干净退出后，Supervisor **立即拉起新 worker**（不长休眠）；连续 `RESYNC_FAIL_MAX=5`（默认）次无进展重启才短休 `RESYNC_COOLDOWN=30s`（默认）；done 列表落 `logs/resync_done/*.done` 持久化，重启不丢；跑到全部 done 才自退。
- 进程内重试（2026-09-20 固化进 `resync_wiki_content.py`）：错误分类——`ext err` / `parse temporary token` / `invalid_response`（非 JSON 返回）属代理会话问题，原地只重试 1 次（2s±20% 抖动）再败即 `exit 2` 交外层换新进程；标准 HTTP 429 读 `Retry-After` 头等待；其他网络错最多重试 3 次（1→2→4→8→16s 封顶 30s，每次 ±20% 抖动）。
- 判别口诀：先停脚本，用**全新 shell 手动单发同一篇**，立即成功即代理累计限流；不要误判登录失效、不要让用户重新登录、不要一味加长静默。
- 深限流（整晚密集写）彻底静默约 15 分钟；窗口内继续请求会"续命"。详见 [../api/feishu-api.md](../api/feishu-api.md)。
- 实测可靠节奏：单进程新写 20 篇 0 失败；撞限流快速退出换新进程，篇间 1.5–5s。

---

## 4. 第三步：全量只读双验收（一门一验收，必做）

```bash
# 4.1 结构验收：本地 / 飞书容器树 / map 三方一致（计数动态，不写死）
python3 scripts/knowledge/verify_wiki_tree.py <profile>
# 期望退出码 0："结构完全一致（N 子页，顶层 T，无重复/无错挂） ✅"

# 4.2 正文回读：逐篇全新进程 docs +fetch，证明首页+子页都非空、标题对得上
python3 scripts/knowledge/verify_wiki_content.py <profile>
# 出 data/_workspace/<profile>/logs/content_readback.tsv
# 判级：去空白 <100=EMPTY，<300=THIN，其余 OK；拉取失败=FETCH_FAIL
# 期望：EMPTY=0、FETCH_FAIL=0（THIN 逐个确认是否本就该短），退出码 0
```

- 回读撞限流出现少量 `FETCH_FAIL` 时，冷却后只补拉非 OK 篇：
  `python3 scripts/knowledge/verify_wiki_content.py <profile> --refill`（会计课实测冷却约 8 分钟后 12 篇 56 秒补齐）。
- 数量口径自检：`map 行数 + 1（首页）= resync_done 数 = 回读总篇数`；本地 `知识详解` 下 md 总数 = map 行数 + 1（根 README）。
- 链接形态（cite/坏链）另按 [wiki-link-verification-sop.md](./wiki-link-verification-sop.md) 抽验；内容结构按 [wiki-content-verification-sop.md](./wiki-content-verification-sop.md)。
- 任一项不过：先修本地源，再重跑 resync（结构问题用 build_tree 补建），**不得手工改飞书后谎报完成**。

---

## 5. 收尾

1. 更新 `project-management/TASK_STATUS.md`（该课指针级状态：容器 token、子页数、验收结论）；单课批次明细留 `data/_workspace/<profile>/`（过程件不入库）。
2. 按 `docs/project-management/standards/DOC_SYNC_CHECKLIST.md` 同步相关文档；稳定结论沉淀 OKF 工程记忆。
3. 一门课完整闭环（建树→同步→双验收 0 问题）后再开下一门；8 门课全部完成后再更新课程首页/CPA 层导航（如需要）。
4. 生成结果（视频/PDF/文字稿）与 `data/_workspace/` 不入库；脚本与文档变更按 git 规范提交。

## 6. 常见问题与修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 建树复用了老空间节点、新容器是空的 | 旧 `wiki_node_map.tsv` 未归档 | 停脚本，把旧 map 改名为 `.oldspace.tsv`，在新容器内重跑 build_tree 生成新 map |
| 课程容器被建成短名/错名（如"会计罗翔"） | 手工/GUI 误建或配置卡 name 不对 | 以配置卡 `primaryCourse.name` 全称为准；错节点用 `wiki +node-delete`（**默认级联、会删整棵子树，--yes 前再三确认**）删除后重跑，不得留同名双容器 |
| 飞书节点标题与本地目录名不一致 | 本地目录名被截断/改名 | 以 frontmatter `title`/官方全称改本地目录名，同步改相对链接与 map 标题键（token 不变），再验收（会计 17 章先例） |
| 正文写入 ok 但飞书是空文档 | resolver 输出空 / WIKI_MAP 没传 / 写到错 obj | resync 有空输出守卫与 `](./` 残留 fail-loud；必须回读确认；检查 `--profile` 与 map 是否同课 |
| 大量 `invalid_response`/rc=5 | 转发代理累计限流 | 换新进程批次法 + 单进程写满20篇自动换进程（第 3 节），不要重新登录 |
| 回读 `FETCH_FAIL`（len=0） | 拉取时限流，"没拉到"不是"飞书为空" | 冷却后 `--refill` 只补失败篇，勿据此判空 |
| 两个窗口/异步任务同时在写 | 服务端异步任务未停 | 在该任务对话内停止；OS 层 kill 无效；开跑前务必确认唯一写进程 |
| 本地批量改了知识点文件名 | 节点标题不会随内容更新 | 先改本地名 + 章 README 链接 + map 标题键（保留 token），再 resync；节点树标题以 map/本地为准，必要时按 feishu-api 的节点改名接口处理 |

## 7. lark-cli 常用命令（统一追加 `--as user --format json`）

```bash
# 列子节点（自动翻页由脚本处理）
lark-cli wiki +node-list --space-id <space> --parent-node-token <parent>
# 建节点（返回 data.node_token / data.obj_token）
lark-cli wiki +node-create --space-id <space> --parent-node-token <parent> --title <标题>
# 删节点（默认级联删子树，危险，先确认）
lark-cli wiki +node-delete --space-id <space> --node-token <node> --yes
# 读正文（回读）
lark-cli docs +fetch --doc <obj> --doc-format markdown --scope full --detail simple
# 覆盖写正文（markdown 走 stdin，脚本已封装；自动剥离 frontmatter）
lark-cli docs +update --doc <obj> --command overwrite --doc-format markdown --content -
```

## 8. 产物与路径速查

| 产物 | 路径 |
|------|------|
| 配置卡（space/root/容器 token/本地路径） | `config/courses/<profile>.json` |
| 节点台账 map | `data/_workspace/<profile>/logs/wiki_node_map.tsv` |
| 正文 done 断点 | `data/_workspace/<profile>/logs/resync_done/*.done`（含 `__COURSE_HOMEPAGE__.done`） |
| 正文回读报告 | `data/_workspace/<profile>/logs/content_readback.tsv` |
| 建树脚本 | `scripts/knowledge/build_tree.py` |
| 正文同步 | `scripts/knowledge/resync_wiki_content.py` |
| 分批驱动 | `scripts/knowledge/run_resync_batches.sh`、`scripts/knowledge/sync_with_restart.sh` |
| 双验收 | `scripts/knowledge/verify_wiki_tree.py`、`scripts/knowledge/verify_wiki_content.py` |
| 链接解析 | `scripts/wiki_link_resolve.py` |

## 参考

- 限流根因/参数：[../api/feishu-api.md](../api/feishu-api.md)
- 链接验证：[wiki-link-verification-sop.md](./wiki-link-verification-sop.md)
- 内容验证：[wiki-content-verification-sop.md](./wiki-content-verification-sop.md)
- 章节点模板：[../templates/KNOWLEDGE_BASE_TEMPLATE.md](../templates/KNOWLEDGE_BASE_TEMPLATE.md)
- 知识生成 SOP：[../knowledge/knowledge-base-organization.md](../knowledge/knowledge-base-organization.md)
