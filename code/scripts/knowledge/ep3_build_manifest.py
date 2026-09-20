#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ep3_build_manifest.py — 名师课(ep3)知识详解 manifest 骨架构建器

正课（glive）的 course-manifest.json 由 papers.knowledgePointList 官方标签生成；
名师课（ep3）题答受风控、没有 papers 标签，改走确定性替代路径：
  - 章归属：讲次 meta.json 的 chapterPath 第一级（实测与 outline 全面精讲章树 1:1）
  - 知识点：讲次目录名去 NN_ 前缀、去分P后缀（1）（2）后聚合
  - 导读/导学/总结讲次不单独成知识点篇（内容供组概述使用）
输出与正课同构的 knowledge.groups / pointIndex，供 batch_build_chapter 复用。

用法：
  python3 scripts/knowledge/ep3_build_manifest.py --profile ep3-accounting-2026            # 预览
  python3 scripts/knowledge/ep3_build_manifest.py --profile ep3-accounting-2026 --write     # 落盘 manifest + 回写 profile.structure
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 分P后缀：（1）（2）(3) 等结尾
RE_PART = re.compile(r"[（(]\d+[）)]$")
# 不单独成篇的讲次（导读/导学/总结）
RE_GUIDE = re.compile(r"^本章(导读|导学|总结)")


def strip_lesson_name(name: str) -> str:
    n = re.sub(r"^\d+_", "", name)
    n = RE_PART.sub("", n)
    return n.strip()


def load_json(p: Path):
    return json.load(open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="ep3 profile key，如 ep3-accounting-2026")
    ap.add_argument("--stage", default="全面精讲", help="主干阶段，默认全面精讲")
    ap.add_argument("--write", action="store_true", help="落盘 manifest 并回写 profile.structure")
    a = ap.parse_args()

    prof = load_json(ROOT / "config" / "courses" / f"{a.profile}.json")
    course_id = prof["primaryCourse"]["saasCourseId"]
    outline = load_json(ROOT / "data/_workspace/_account/ep3/manifest" / f"{course_id}.outline.json")

    # outline 该阶段的官方章顺序
    stages = [s for s in outline["gradations"] if a.stage in s["name"]]
    if not stages:
        raise SystemExit(f"outline 中找不到阶段 {a.stage}")
    chapter_order = [c["name"] for c in stages[0]["chapterTree"]]

    # 章 code：优先对齐对应正课 profile（同科目教材章 code 一致），缺则按 outline 顺序编号
    subject = a.profile.replace("ep3-", "").replace("-2026", "")
    zheng = ROOT / "config" / "courses" / f"cpa-{subject}-2026.json"
    code_map = {}
    if zheng.exists():
        for g in load_json(zheng).get("structure", {}).get("groups", []):
            code_map[g["name"]] = int(g["code"])

    # 遍历讲次目录
    vbase = ROOT / prof["paths"]["localRoot"] / "原始资源" / "videos" / a.stage
    chapters: dict = {}
    for lesson in sorted(x for x in vbase.iterdir() if x.is_dir() and not x.name.startswith(".")):
        metas = sorted(lesson.glob("*_meta.json"))
        if not metas:
            continue
        m0 = load_json(metas[0])
        cp = m0.get("chapterPath", "")
        ch = cp.split("/")[0].strip() if cp else None
        if not ch:
            print(f"  [warn] 无 chapterPath：{lesson.name}")
            continue
        point_name = strip_lesson_name(lesson.name)
        if RE_GUIDE.match(point_name):
            continue  # 导读/导学/总结不单独成篇
        teachers = sorted({load_json(x).get("teacher", "?") for x in metas})
        chapters.setdefault(ch, {})
        chapters[ch].setdefault(point_name, {"lessonDirs": [], "teachers": set()})
        chapters[ch][point_name]["lessonDirs"].append(lesson.name)
        chapters[ch][point_name]["teachers"].update(teachers)

    # 按 outline 顺序生成 groups / pointIndex（pointId = 章code*1000 + 章内序，稳定可读）
    groups, point_index = [], {}
    missing_in_outline = [c for c in chapters if c not in chapter_order]
    for ci, ch in enumerate(chapter_order):
        if ch not in chapters:
            print(f"  [warn] outline 有章但本地无讲次：{ch}")
            continue
        code = code_map.get(ch, ci + 1)
        point_ids = []
        for pname, info in chapters[ch].items():
            pid = code * 1000 + len(point_ids) + 1
            point_ids.append(pid)
            point_index[str(pid)] = {
                "title": pname,
                "lessonDirs": sorted(info["lessonDirs"]),
                "teachers": sorted(info["teachers"]),
                "stage": a.stage,
                "chapter": ch,
            }
        groups.append({"code": code, "name": ch, "pointIds": point_ids})

    total_points = len(point_index)
    total_lessons = sum(len(v["lessonDirs"]) for v in point_index.values())

    # 预览输出
    print(f"课程：{prof['primaryCourse']['name']}（{a.stage}）")
    print(f"章 {len(groups)} / 知识点篇 {total_points} / 覆盖讲次 {total_lessons}")
    if missing_in_outline:
        print(f"[warn] 本地有但 outline 章树无：{missing_in_outline}")
    for g in groups:
        print(f"  {g['code']:02d} {g['name']}（{len(g['pointIds'])} 篇）")

    if not a.write:
        print("\n[dry-run] 加 --write 落盘 manifest 并回写 profile.structure")
        return

    # 落盘 course-manifest.json
    ws = ROOT / "data" / "_workspace" / a.profile / "manifest"
    ws.mkdir(parents=True, exist_ok=True)
    manifest = {
        "_meta": {
            "builder": "ep3_build_manifest.py",
            "source": "meta.chapterPath + 讲次目录聚合（无 papers，风控期替代路径）",
            "mainStage": a.stage,
            "courseId": course_id,
        },
        "knowledge": {
            "groups": groups,
            "pointIndex": point_index,
            "genericPoint": None,
            "aliasPoints": [],
        },
    }
    out = ws / "course-manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写 manifest：{out.relative_to(ROOT)}")

    # 回写 profile.structure（不覆盖已有非 groups 字段）
    prof.setdefault("structure", {})
    prof["structure"].update({
        "officialGroupCount": len(groups),
        "pointCount": total_points,
        "mainStage": a.stage,
        "groups": [{"code": f"{g['code']:02d}", "name": g["name"]} for g in groups],
        "historyHint": (
            "名师课(ep3)风控期无 papers.knowledgePointList，章取 outline 全面精讲章树、"
            "知识点由讲次目录去分P聚合（ep3_build_manifest.py）；"
            "章 code 对齐同科目正课 profile。重点强化跨章专题/考前冲刺不单独建组，跨讲聚合融入对应章/全局篇。"
        ),
    })
    prof_path = ROOT / "config" / "courses" / f"{a.profile}.json"
    prof_path.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已回写 profile.structure：{prof_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
