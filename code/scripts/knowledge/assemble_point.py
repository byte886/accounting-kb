#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble_point.py — 单知识点成篇组装器（阶段③批量流水线最后一步）

把 AI 写好的"头部"（Context Block + 一、知识拆解 + 二、考试指导 + `## 三、题答解析` 标题）
与脚本确定性渲染的题答、自动生成的同组关联链接拼成最终知识点 .md。

- 题答数字全部来自 collect 聚合 JSON，AI 不转抄（复用 render_point_qa）；
- 同组兄弟篇关联链接由 manifest 自动生成，AI 不用手写；
- 输出即带客观/大题/小问三项对账数，供质量门核对。

用法：
  python3 assemble_point.py --src <G02_112470_xxx.json> --head <head.md> [--course-root <课程目录>]
聚合 JSON 位于 data/_workspace/<profile>/tmp/point-questions/；课程成品根默认从 profile 定位，可用 --course-root 覆盖。
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_point_qa as R  # noqa: E402
from course_profile import load_profile  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="collect 聚合 JSON")
    ap.add_argument("--head", required=True, help="AI 写的头部 md（到 ## 三、题答解析 标题）")
    ap.add_argument("--course-root", help="课程目录，默认从 src 推断")
    a = ap.parse_args()

    src = Path(a.src)
    # 新架构（ADR-016）：聚合 JSON 与 manifest 都在 data/_workspace/<profile>/；成品课程根从 profile 定位
    _prof = load_profile()
    workspace = ROOT / "data" / "_workspace" / _prof["key"]
    course = Path(a.course_root) if a.course_root else (ROOT / _prof["paths"]["localRoot"])
    d = json.load(open(src, encoding="utf-8"))
    pid, title, gc, gname = d["pointId"], d["title"], d["groupCode"], d["groupName"]
    qs = d["questions"]
    obj = [q for q in qs if q["type"] in (1, 2, 3)]
    sub = [q for q in qs if q["type"] == 6]

    # 题答渲染（复用 render_point_qa）
    lines = [f"### （一）客观题（{len(obj)} 道）", ""]
    for i, q in enumerate(obj, 1):
        lines += R.render_obj(q, i)
    groups, idx = [], {}
    for q in sub:
        key = (q.get("bigStem", ""), q.get("paperId"))
        if key not in idx:
            idx[key] = len(groups)
            groups.append([q.get("bigStem", ""), q.get("paperTitle", ""), q.get("paperId"), []])
        groups[idx[key]][3].append(q)
    n_sub = sum(len(g[3]) for g in groups)
    if groups:
        lines += [f"### （二）计算 / 综合大题（{len(groups)} 道大题、{n_sub} 个小问）", ""]
        lines += R.render_subj(groups)
    rendered = "\n".join(lines).rstrip()

    # 同组关联（来自 manifest，排除自己）
    mani = json.load(open(workspace / "manifest/course-manifest.json", encoding="utf-8"))
    k = mani["knowledge"]
    grp = next(g for g in k["groups"] if g["code"] == gc)
    pi = {int(x): y for x, y in k["pointIndex"].items()}
    rel = [f"- [{pi[i]['title']}](./{pi[i]['title']}.md)" for i in grp["pointIds"] if i != pid]
    related = "---\n\n## 关联知识点\n\n" + "\n".join(rel) + "\n"

    head = Path(a.head).read_text(encoding="utf-8").rstrip()
    final = f"{head}\n\n{rendered}\n\n{related}"

    # 输出目录用 profile code（01-32 连续），不用题库 groupCode（G24/G29 不连续），与01章试点一致
    prof_code = None
    for g in _prof.get("structure", {}).get("groups", []):
        if g.get("name") == gname:
            prof_code = g.get("code")
            break
    if prof_code is None:
        prof_code = f"{gc:02d}"
    dirname = f"{prof_code}_{gname}"
    outdir = course / "知识详解" / dirname
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{title}.md"
    out.write_text(final, encoding="utf-8")
    print(f"成篇：{dirname}/{title}.md | 客观{len(obj)} 大题{len(groups)} 小问{n_sub} | {len(final)}字符 -> {out}")


if __name__ == "__main__":
    main()
