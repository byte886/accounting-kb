#!/usr/bin/env python3
"""同步飞书前的内部链接解析过滤器（stdin markdown → stdout markdown，内嵌 XML cite）。

把本地同目录相对链接 [标题](./标题.md) 解析为飞书内部文档引用
<cite type="doc" doc-id="obj_token"/>：飞书渲染为目标文档标题（蓝色内部引用），
由 obj_token 强绑定目标、可自动校验坏链，比手写完整 URL 更规范可靠。

打开方式（2026-09-07 真实 Chrome CDP 可信点击实测，lark-cli issue #2399 佐证）：
cite 与完整 URL 一样，点击后都在【新标签页】打开——飞书正文区跨文档跳转统一新开标签，
是前端固定行为，任何写入格式（cite/按钮/书签/普通链接/原生子页面列表）都无法改成当前窗口；
唯一当前窗口切换文档的入口是左侧知识库目录树。因此改用 cite 的理由不是"它能本窗口打开"
（两者都新开），而是：cite 渲染为文档标题、obj_token 强绑定、可自动校验 0 坏链；完整 URL
冗长且会随节点变动失效。"单窗口连续阅读"的引导统一放在导航型页面（总览页、章 README）顶部。

历史：早期版本输出完整 wiki URL（https://<域名>/wiki/<node_token>），2026-09-07 起改为 cite。
- 本地源文件保留 ./ 相对链接不动，仅在写入飞书的管道里做转换；
- cite 渲染文字固定为目标文档标题，故要求链接文字等于目标文件名（已全量核验一致）；
- 找不到映射的同目录链接降级为纯文本 label（不在飞书留残缺 .md 坏链）并向 stderr 告警，绝不臆造 token；
  本地源文件保持不动，将来补建目标篇后重跑 resync 即自动恢复成 cite；
- obj_token 取自 WIKI_MAP 环境变量指向的 wiki_node_map.tsv 第 3 列（该表已去重，标题唯一）。
  ⚠️ 调用方（如 resync_wiki_content.py）必须显式 export WIKI_MAP=data/_workspace/<profile>/logs/wiki_node_map.tsv；
  未设时仅回退仓库根 logs/（通常不存在），映射为空会让所有链接静默保留原样——这是严重隐患。
"""
import os
import re
import sys

MAP_FILE = os.environ.get(
    "WIKI_MAP",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "wiki_node_map.tsv"),
)

# 标题 -> obj_token（第 3 列）
title2obj = {}
if os.path.isfile(MAP_FILE):
    for line in open(MAP_FILE, encoding="utf-8"):
        cols = line.rstrip("\n").split("\t")
        if len(cols) >= 3 and cols[0]:
            title2obj[cols[0]] = cols[2]
if not title2obj:
    print(
        f"[wiki_link_resolve][严重] 映射表为空或不存在: {MAP_FILE}；"
        f"所有相对链接都无法转成 cite。请显式 export WIKI_MAP=data/_workspace/<profile>/logs/wiki_node_map.tsv",
        file=sys.stderr, flush=True,
    )

text = sys.stdin.read()
_missing = set()
_link_pat = re.compile(r"\[([^\]]+)\]\(\./([^)]+?)\.md\)")


def _resolve(m):
    label, target = m.group(1).strip(), m.group(2).strip()
    obj = title2obj.get(target)
    if obj:
        return f'<cite type="doc" doc-id="{obj}"/>'
    # 目标节点在本课程不存在（如未单独成篇、无知识来源不凭空造）：飞书端保留相对 .md 只会是
    # 残缺坏链，故降级为纯文本 label；本地源文件不动，将来补建该篇后重跑 resync 会自动恢复成 cite。
    _missing.add(target)
    return label


# 仅替换同目录相对链接 ./xxx.md（跨组 ../ 与外链不动）
out = _link_pat.sub(_resolve, text)

for t in sorted(_missing):
    print(f"[wiki_link_resolve] 未找到节点映射，降级为纯文本（无此节点）: {t}", file=sys.stderr)

sys.stdout.write(out)
