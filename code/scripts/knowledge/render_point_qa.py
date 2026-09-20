#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_point_qa.py — 把 collect_point_questions.py 的单知识点聚合 JSON
确定性渲染成「三、题答解析」Markdown 片段。

设计目的（阶段③步骤3）：
- 题面 / 选项 / 答案 / 官方解析 / 大题算式一律从 papers JSON 机械渲染，
  AI 不手抄数字，避免算式 / 答案抄错；
- 客观题(type1/2/3) 与主观大题(type5 容器→type6 小问) 分两段；
- 主观题按大题题干 bigStem 分组、保序，呈现「大题业务情境 →(1)(n)小问算式」层级；
- 渲染结果只作初稿，AI 负责校核，不新增 / 不删改题目本身。

用法：
  python3 render_point_qa.py <point_questions.json> [--out out.md]
不写 --out 则打印到 stdout。
"""
import argparse, collections, html, json, sys

LABELS = "ABCDEFGHIJ"


def clean(s):
    if s is None:
        return ""
    s = str(s)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&times;", "×"), ("&divide;", "÷")]:
        s = s.replace(a, b)
    s = html.unescape(s)
    return " ".join(s.split())


def render_obj(q, idx):
    out = [f"**{idx}.【{q['typeName']}｜来源：{clean(q.get('paperTitle'))}（paperId {q.get('paperId')}）】{clean(q['stem'])}**", ""]
    for i, op in enumerate(q.get("options", [])):
        out.append(f"- {LABELS[i]}. {clean(op)}")
    out.append("")
    out.append(f"**答案：{clean(q['answer'])}**　解析：{clean(q['analysis'])}")
    out.append("")
    return out


def render_subj(groups):
    """groups: list of (bigStem, paperTitle, paperId, [sub questions])"""
    out = []
    for n, (big, title, pid, subs) in enumerate(groups, 1):
        out.append(f"#### 大题{n}（{n}/{len(groups)}）｜来源：{clean(title)}（paperId {pid}）")
        out.append("")
        out.append("> " + clean(big).replace("\n", "  \n> "))
        out.append("")
        for q in subs:
            ana = clean(q["analysis"])
            out.append(f"**{clean(q['stem'])}**")
            out.append("")
            out.append(f"{ana}")
            out.append("")
        out.append("---")
        out.append("")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = json.load(open(a.src, encoding="utf-8"))
    qs = d["questions"]
    obj = [q for q in qs if q["type"] in (1, 2, 3)]
    sub = [q for q in qs if q["type"] == 6]

    lines = [f"### （一）客观题（{len(obj)} 道）", ""]
    for i, q in enumerate(obj, 1):
        lines += render_obj(q, i)

    # 主观题按 bigStem + paperId 分组保序
    groups = []
    idx = {}
    for q in sub:
        key = (q.get("bigStem", ""), q.get("paperId"))
        if key not in idx:
            idx[key] = len(groups)
            groups.append([q.get("bigStem", ""), q.get("paperTitle", ""), q.get("paperId"), []])
        groups[idx[key]][3].append(q)
    n_sub = sum(len(g[3]) for g in groups)
    # 无大题/小问时不渲染该分类标题（避免出现“（0 道大题、0 个小问）”空小节），与 assemble_point.py 对齐
    if groups:
        lines += [f"### （二）计算 / 综合大题（{len(groups)} 道大题、{n_sub} 个小问）", ""]
        lines += render_subj(groups)

    text = "\n".join(lines).rstrip() + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"渲染完成：客观{len(obj)} 大题{len(groups)} 小问{n_sub} -> {a.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
