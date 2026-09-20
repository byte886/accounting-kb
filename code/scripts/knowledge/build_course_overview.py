#!/usr/bin/env python3
"""生成课程总览页：飞书 XML（--format xml，默认）与本地 Markdown 源文件（--format markdown）。

设计要点（2026-09-07 修订）：
- 飞书侧章节入口统一用 <cite type="doc" doc-id="obj_token"/> 内部文档引用：渲染为目标文档
  标题、obj_token 强绑定、可自动校验坏链，比完整 URL 规范可靠。
  打开方式经真实 Chrome CDP 可信点击实测：cite 与完整 URL 一样都在【新标签页】打开，飞书正文
  跨文档跳转统一新开，写入格式无法改成当前窗口，唯一当前窗口切换是左侧知识库目录树（详见
  wiki-link-verification-sop.md）。故页首用 NAV_HINT 如实说明并引导左侧树单窗口阅读。
- 每章只保留一个入口（章 README）：章内"知识点目录"即知识拆解入口，"重点内容"即该章考试指导，
  不再让 14 行"考试指导"都指向同一个全局速查手册；全局横向汇总以 cite 单列于表格下方。
- 本地 Markdown 源文件用相对链接，供 git/网盘归档，与飞书 XML 同源生成，避免两处不一致。

数据来源：
- data/_workspace/cpa-tax-2026/logs/wiki_node_map.tsv（标题 node_token obj_token parent，取 14 章与 2 篇全局资料的 obj_token）
- 本地知识详解目录（统计每章知识点 .md 篇数）
"""
import argparse
import glob
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "knowledge"))
from course_profile import load_profile  # noqa: E402


def _pick_profile_key():
    if "--profile" in sys.argv:
        i = sys.argv.index("--profile")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    for a in sys.argv[1:]:
        if a.startswith("--profile="):
            return a.split("=", 1)[1]
    return None


# 结构/章名/标题/总览内容全部来自课程档案卡（缺省税法），换课只换 profile
PROFILE = load_profile(_pick_profile_key())
MAP_FILE = os.path.join(REPO, "logs", "wiki_node_map.tsv")  # TODO 跨课时按 key 分（随飞书同步链路一起）
COURSE_DIR = os.path.join(REPO, PROFILE["paths"]["localRoot"], "知识详解")
COURSE_TITLE = PROFILE["primaryCourse"]["name"]
# 官方章组显示名 {序号: 名}（不带 NN_ 前缀），来自 profile.structure.groups
CHAPTER_DISPLAY = {g["code"]: g["name"] for g in (PROFILE.get("structure", {}).get("groups") or [])}
# 总览教学内容为可选段：会计等新课未生产前缺省为空，对应小节省略，不串入税法内容
_OV = PROFILE.get("overview", {}) or {}
COURSE_INFO = [tuple(x) for x in (_OV.get("courseInfo") or [])]
GLOBAL_DOCS = [tuple(x) for x in (_OV.get("globalDocs") or [])]
IMPORTANCE_LEVELS = [tuple(x) for x in (_OV.get("importanceLevels") or [])]
STUDY_METHODS = list(_OV.get("studyMethods") or [])
SUMMARY_TEXT = _OV.get("summary", "")

NAV_HINT = (
    "导航说明：本页章节名与全局资料均为飞书内部文档引用，点击会在新标签页打开"
    "（飞书正文跨文档链接的固定行为）。若希望在同一窗口连续阅读、避免标签过多迷失，"
    "请使用左侧知识库目录树：点节点即在当前窗口切换，展开章节可见其全部知识点。"
)

LIST_NOTE = (
    "每章只设一个入口（章 README）：章内“知识点目录”是知识拆解入口，“重点内容”是该章考试指导；"
    "每篇知识点详解统一含“知识拆解 / 考试指导 / 题答解析 / 学员补充”四节。"
    "跨章横向汇总与通用做题方法见表格下方两篇全局资料。"
)


def load_obj_tokens():
    """从 node_map 取每个章目录名（NN_xxx）与全局资料的 obj_token。"""
    chapter_obj, global_obj = {}, {}
    with open(MAP_FILE, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3:
                continue
            title, _node, obj = cols[0], cols[1], cols[2]
            if len(title) >= 3 and title[:2].isdigit() and title[2] == "_":
                chapter_obj[title[:2]] = obj  # 同名章只此一条，后写覆盖无妨
            if title in ("考试指导速查手册", "课程做题思路解析"):
                global_obj[title] = obj
    return chapter_obj, global_obj


def count_points():
    """统计每章知识点 .md 篇数（排除 README），并返回 {序号: (篇数, 章目录名)}。"""
    counts, dirname = {}, {}
    for path in sorted(glob.glob(os.path.join(COURSE_DIR, "[0-9]*/"))):
        name = os.path.basename(path.rstrip(os.sep))
        num = name[:2]
        n = len([
            p for p in glob.glob(os.path.join(path, "*.md"))
            if os.path.basename(p) != "README.md"
        ])
        counts[num] = n
        dirname[num] = name
    return counts, dirname


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_rows(chapter_obj, counts, dirname):
    rows = []
    for num in sorted(CHAPTER_DISPLAY):
        obj = chapter_obj.get(num)
        if not obj:
            sys.exit(f"[ERROR] wiki_node_map.tsv 缺少 {num} 章 obj_token")
        rows.append((num, obj, counts.get(num, 0), dirname.get(num, "")))
    return rows


# ---------- 飞书 XML ----------

def build_xml(chapter_obj, global_obj, counts, dirname):
    rows = build_rows(chapter_obj, counts, dirname)
    total = sum(r[2] for r in rows)
    p = []
    p.append(f"<title>{esc(COURSE_TITLE)}</title>")
    # 导航说明（如实告知正文引用新开标签、单窗口走左侧目录树）
    p.append(f"<blockquote><p>{esc(NAV_HINT)}</p></blockquote>")
    # 课程信息
    if COURSE_INFO:
        p.append("<h2>课程信息</h2>")
        p.append("<ul>" + "".join(f"<li>{esc(k)}：{esc(v)}</li>" for k, v in COURSE_INFO) + "</ul>")
    # 章节列表
    p.append("<h2>章节列表</h2>")
    p.append(f"<blockquote><p>{esc(LIST_NOTE)}</p></blockquote>")
    head = "".join(
        f'<th background-color="light-gray"><p>{h}</p></th>'
        for h in ("序号", "章节", "知识点", "状态")
    )
    body = []
    for num, obj, n, _dn in rows:
        body.append(
            "<tr>"
            f"<td><p>{num}</p></td>"
            f'<td><p><cite type="doc" doc-id="{obj}"/></p></td>'
            f"<td><p>{n} 篇</p></td>"
            f"<td><p>✅ 已完成</p></td>"
            "</tr>"
        )
    p.append(
        "<table><colgroup><col width=\"60\"/><col width=\"320\"/>"
        "<col width=\"90\"/><col width=\"110\"/></colgroup>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )
    p.append(f"<p>合计 {len(rows)} 章、{total} 篇知识点详解。</p>")
    # 全局资料
    if GLOBAL_DOCS:
        p.append("<h3>全局资料</h3>")
        p.append("<ul>")
        for title, desc in GLOBAL_DOCS:
            obj = global_obj.get(title)
            if not obj:
                sys.exit(f"[ERROR] wiki_node_map.tsv 缺少全局资料 {title} obj_token")
            p.append(f"<li><cite type=\"doc\" doc-id=\"{obj}\"/> — {esc(desc)}</li>")
        p.append("</ul>")
    # 课程概述（教学内容为可选段，缺省省略）
    if SUMMARY_TEXT or IMPORTANCE_LEVELS or STUDY_METHODS:
        p.append("<h2>课程概述</h2>")
        if SUMMARY_TEXT:
            p.append(f"<p>{esc(SUMMARY_TEXT)}</p>")
        if IMPORTANCE_LEVELS:
            p.append("<h3>各章节重要性层级</h3>")
            p.append("<ul>" + "".join(f"<li><b>{esc(lv)}</b>：{esc(txt)}</li>" for lv, txt in IMPORTANCE_LEVELS) + "</ul>")
        if STUDY_METHODS:
            p.append("<h3>学习方法</h3>")
            p.append("<ol>" + "".join(f"<li>{esc(m)}</li>" for m in STUDY_METHODS) + "</ol>")
    return "".join(p)


# ---------- 本地 Markdown ----------

def build_markdown(chapter_obj, counts, dirname):
    rows = build_rows(chapter_obj, counts, dirname)
    total = sum(r[2] for r in rows)
    L = []
    L.append(f"# {COURSE_TITLE}\n")
    L.append("> 本文件为飞书课程根节点（总览页）的本地源文件，与飞书版本同源生成。")
    L.append("> 导航说明：飞书侧章节为内部文档引用，点击在新标签页打开（飞书正文跨文档链接固定行为），"
             "单窗口连续阅读请用飞书左侧知识库目录树；本地源文件用相对路径链接。\n")
    if COURSE_INFO:
        L.append("## 课程信息\n")
        for k, v in COURSE_INFO:
            L.append(f"- {k}：{v}")
        L.append("")
    L.append("## 章节列表\n")
    L.append(f"> {LIST_NOTE}\n")
    L.append("| 序号 | 章节 | 知识点 | 状态 |")
    L.append("|-|-|-|-|")
    for num, _obj, n, dn in rows:
        L.append(f"| {num} | [{CHAPTER_DISPLAY[num]}](./知识详解/{dn}/README.md) | {n} 篇 | ✅ 已完成 |")
    L.append(f"\n合计 {len(rows)} 章、{total} 篇知识点详解。\n")
    if GLOBAL_DOCS:
        L.append("### 全局资料\n")
        for title, desc in GLOBAL_DOCS:
            L.append(f"- **[{title}](./知识详解/{title}.md)** — {desc}")
        L.append("")
    if SUMMARY_TEXT or IMPORTANCE_LEVELS or STUDY_METHODS:
        L.append("## 课程概述\n")
        if SUMMARY_TEXT:
            L.append(SUMMARY_TEXT + "\n")
        if IMPORTANCE_LEVELS:
            L.append("### 各章节重要性层级\n")
            for lv, txt in IMPORTANCE_LEVELS:
                L.append(f"- **{lv}**：{txt}")
            L.append("")
        if STUDY_METHODS:
            L.append("### 学习方法\n")
            for i, m in enumerate(STUDY_METHODS, 1):
                L.append(f"{i}. {m}")
            L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["xml", "markdown"], default="xml")
    args = ap.parse_args()
    chapter_obj, global_obj = load_obj_tokens()
    counts, dirname = count_points()
    if args.format == "xml":
        sys.stdout.write(build_xml(chapter_obj, global_obj, counts, dirname))
    else:
        sys.stdout.write(build_markdown(chapter_obj, counts, dirname))


if __name__ == "__main__":
    main()
