---
type: Workflow
title: 飞书同步与单窗口导航
description: 知识详解本地成稿后单向同步飞书；站内链接用 cite 结构化（为可校验，非为当前窗口）；正文跨文档必新开是飞书平台事实，唯一本窗口是左侧目录树；同步后按 SOP 回读校验。
tags: [feishu, 同步, wiki链接, 单窗口, cite, workflow]
sources:
  - id: adr-015
    resource: ../../decisions/ADR-015-飞书内部链接打开方式与单窗口导航方案.md
    title: ADR-015 飞书内部链接打开方式与单窗口导航方案
  - id: link-sop
    resource: ../../../development/guides/wiki-link-verification-sop.md
    title: wiki-link-verification-sop 飞书链接三层验证 SOP
  - id: wiki-sync-sop
    resource: ../../../development/guides/wiki-sync-sop.md
    title: wiki-sync-sop 飞书知识库同步 SOP（新空间 8 课模型）
generated: { by: "doubao/okf-wiki", at: "2026-09-07T20:30:00+08:00" }
status: stable
---

# 飞书同步与单窗口导航

## 一句话结论
**本地是唯一源头**：知识详解先在本地 `知识详解/` 成稿并过校验，再单向同步飞书，**禁止直接改飞书**。站内链接统一用 `<cite type="doc">` 是为了"结构化、可自动校验 0 坏链"，**不是**因为它能当前窗口打开——飞书正文跨文档链接无论怎么写都新开标签，唯一单窗口入口是左侧知识库目录树，靠导航页引导。

## 同步方向与形态
- 单向：本地 → 飞书；本地与飞书结构同构（章父节点 / 知识点子页面）。
- 父节点（章 README/总览）必须含子节点链接 + 一句摘要；子页面更新后同步刷新父节点概览/题量。
- 本地 md 的 YAML frontmatter 是给机器的，**同步飞书时由同步环节渲染成人读信息块或剥离，外部读者看不到裸 YAML**。
- 过程留痕（验证/同步记录）默认并入任务报告，不单独传飞书。

## 链接写法与"新开标签"平台事实（ADR-015，CDP 可信点击实测）
| 正文写法 | 结果 |
|---|---|
| `<cite type="doc">` / OpenLink 按钮 / bookmark 书签 / 普通 `<a href>` 完整 URL / 原生 sub-page-list | **全部新开标签** |
| **左侧知识库目录树节点** | **唯一本窗口：标签数不变、当前页 URL 直接切换** |

- 因此：站内互链用 cite（渲染成目标标题、obj_token 强绑定、可回读校验）；**完整 URL 只用于站外链接**。今后不得再以"cite 能当前窗口打开/target=_self"作为选型或验收理由。
- **方案 B（采纳）**：cite 全保留，只在**导航型页面**（课程总览 1 处 + 各章 README）顶部加一段单窗口引导（"正文引用点击新开，想连续阅读用左侧目录树"）；**纯内容页（92 篇知识点 + 2 全局）不加**，避免堆砌。方案 A（去链接化全交左侧树）已否决。
- 若未来 lark-cli 落地 `docsLink` 或飞书改前端行为，先用 CDP 可信点击复测再评估，不凭文档猜测。

## 同步后校验（两层，权威手段不同）
1. **链接正确性**（指向对不对、有无坏链）：`docs +fetch` 回读，按 doc-id 与台账 obj_token 逐行比对、统计残留完整 URL（流程见 wiki-link-verification-sop）。
2. **打开方式**（点了怎么开）：仅在怀疑前端变化时，用真实 Chrome + puppeteer-core 的 `page.mouse.click()`（isTrusted=true）抽检；**禁止**用 DOM target 属性或合成事件下结论。
3. 导航页校验"引导块存在"，内容页校验其"不存在"。

## 新空间 8 课模型与配置驱动链路（2026-09-19 起现役）

- **固定坐标**：新空间「CPA备考知识库」space `7686897234545249236`，根「课程库」node `K4IcwWg6HidyY6k6Z8hcdmGFnth`；层级＝**课程库 → 全称课程容器（容器本身=课程首页）→ 章/全局篇 → 知识点**。老空间 `7678261729456852192` 仅留 CPA 级《通用做题思路解析》，新课勿写。容器标题/space/root 全部读配置卡 `config/courses/<profile>.json`（`primaryCourse.name` + `wiki` 块），不在命令里手填。
- **链路（一门课一闭环、一门一验收）**：`build_tree.py <profile>`（幂等建全称容器并回写 `courseNodeToken/courseObjToken`，再在内容器建章→点→全局篇；根 README 不建子节点）→ `resync_wiki_content.py --profile` 分批写正文（**根 README 写入容器=课程首页**，done 名 `__COURSE_HOMEPAGE__.done`；frontmatter 自动剥离）→ 只读双验收 `verify_wiki_tree.py`（本地/map/飞书容器树三方一致，动态计数）+ `verify_wiki_content.py`（逐篇 docs +fetch，EMPTY<100/THIN<300/FETCH_FAIL，`--refill` 补非 OK）。数量口径：map 行数+1（首页）= done 数 = 回读篇数。
- **换空间重建先归档旧 map**：老空间遗留 `wiki_node_map.tsv` 不改名，build_tree 会按标题幂等命中老 token、新容器为空；先改名 `.oldspace.tsv` 再建。
- **标题以本地目录名/frontmatter title 为准**：会计第 17 章本地目录曾被截断成 `17_收入`（飞书/frontmatter 为全称），修法是改本地目录名+跨章相对链接+map 标题键（token 不变），不迁就错误短名。
- **限流是豆包转发代理按"单进程累计请求"计，不是飞书账号/token/内容问题**：`invalid_response`/`parse temporary token`/rc=5 → 换新 python 进程即恢复；`run_resync_batches.sh` 已是 Worker Supervisor 模式——worker 写满 20 篇主动退出后立即拉起新 worker（不长休眠），连续 5 次无进展才短休 30s，done 列表落文件持久化；回读 FETCH_FAIL 冷却约 8 分钟 `--refill`。旧"简单逐个脚本最可靠、复杂批量不行"结论已证伪（真因即代理累计限流）。
- **同一空间同一时刻只允许一个写进程**；豆包"工作任务"是服务端异步、OS kill/重启都停不掉，停止须在该任务对话内，开长任务前先确认无同目标 run。
- 已退役（入 `.trash/*.20260919`）：`sync_wiki_new.sh`（老"课程根→组→点"建树器）、`auto_sync_all.py/.sh`（硬编码老空间）、`verify_sync_completeness.py`（老六科硬编码）。权威步骤见 wiki-sync-sop。

## 来源与下钻
- [ADR-015 飞书内部链接打开方式与单窗口导航方案](../../decisions/ADR-015-飞书内部链接打开方式与单窗口导航方案.md)（五种写法实测表、方案取舍、教训）
- [wiki-link-verification-sop](../../../development/guides/wiki-link-verification-sop.md)（三层链接验证流程）
- [wiki-sync-sop 新空间 8 课模型](../../../development/guides/wiki-sync-sop.md)（建树/分批正文/双验收完整步骤、8 课坐标、限流处置）
- 可信点击能力见 [浏览器自动化连接通道](workflow-browser-cdp.md)；本地源头与成品结构见 [三层解耦](architecture-knowledge-paradigm.md)。
