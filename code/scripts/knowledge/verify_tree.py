#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读核验飞书课程树 vs 本地源 vs map（不做任何写操作）。"""
import glob
import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SPACE = "7686897234545249236"
COURSE_NODE = "Z8AjwYUwvi11kJkO07tc4r36nib"
PROFILE = "cpa-accounting-2026"
LOGS = REPO / "data" / "_workspace" / PROFILE / "logs"
MAP_FILE = LOGS / "wiki_node_map.tsv"
KNOWLEDGE = (REPO / "data" / "高顿" / "CPA"
             / "【26考季】VIPCPA系列-会计（罗翔老师）" / "知识详解")


def lark(args, retries=4):
    for i in range(retries):
        p = subprocess.run(["lark-cli"] + args + ["--as", "user", "--format", "json"],
                           capture_output=True, text=True, cwd=str(REPO))
        try:
            j = json.loads(p.stdout)
            if j.get("ok"):
                return j
            err = json.dumps(j.get("error", {}), ensure_ascii=False)
        except Exception:
            err = (p.stdout or "")[:160] + (p.stderr or "")[:160]
        if "invalid_response" in err or "invalid character" in err:
            time.sleep(8 * (i + 1))
            continue
        print("  [lark错误]", err[:200])
        time.sleep(3)
    return None


def children(parent):
    items, token = [], None
    while True:
        args = ["wiki", "+node-list", "--space-id", SPACE, "--parent-node-token", parent]
        if token:
            args += ["--page-token", token]
        j = lark(args)
        if not j:
            break
        d = j.get("data", {})
        items += d.get("nodes", []) or d.get("items", []) or []
        token = d.get("page_token") or d.get("next_page_token")
        if not d.get("has_more") or not token:
            break
        time.sleep(0.4)
    return items


def local_titles():
    globals_, chapters, points = {}, {}, {}
    k = str(KNOWLEDGE)
    for p in glob.glob(os.path.join(k, "*.md")):
        if os.path.basename(p) != "README.md":
            globals_[os.path.basename(p)[:-3]] = p
    for g in sorted(glob.glob(os.path.join(k, "[0-9]*", ""))):
        gn = os.path.basename(os.path.normpath(g))
        if os.path.isfile(os.path.join(g, "README.md")):
            chapters[gn] = os.path.join(g, "README.md")
        for p in glob.glob(os.path.join(g, "*.md")):
            if os.path.basename(p) != "README.md":
                points[os.path.basename(p)[:-3]] = p
    return globals_, chapters, points


def main():
    globals_, chapters, points = local_titles()
    local_all = list(globals_) + list(chapters) + list(points)
    print("[本地] 全局篇=%d 章README=%d 知识点=%d 合计=%d"
          % (len(globals_), len(chapters), len(points), len(local_all)))

    map_rows, dup_t, seen_n = {}, [], {}
    if MAP_FILE.exists():
        for line in MAP_FILE.read_text(encoding="utf-8").splitlines():
            c = line.split("\t")
            if len(c) >= 3 and c[0]:
                if c[0] in map_rows:
                    dup_t.append(c[0])
                map_rows[c[0]] = {"node": c[1], "obj": c[2],
                                  "parent": c[3] if len(c) > 3 else ""}
                seen_n.setdefault(c[1], []).append(c[0])
    dup_n = {n: t for n, t in seen_n.items() if len(t) > 1}
    print("[map] 行=%d 重复标题键=%s 重复node=%s"
          % (len(map_rows), dup_t or "无", dup_n or "无"))

    top = children(COURSE_NODE)
    actual = {}
    chap_nodes = [n for n in top if n["title"] in chapters]
    glob_nodes = [n for n in top if n["title"] in globals_]
    other = [n for n in top if n["title"] not in chapters and n["title"] not in globals_]
    print("[飞书] 课程下顶层=%d（章=%d 全局篇=%d 其它=%d）"
          % (len(top), len(chap_nodes), len(glob_nodes), len(other)))
    for n in other:
        print("  [顶层异常]", n["title"])
    for n in top:
        actual[n["title"]] = (n["node_token"], COURSE_NODE)
    point_total = 0
    for cn in chap_nodes:
        kids = children(cn["node_token"])
        point_total += len(kids)
        for kid in kids:
            if kid["title"] in actual:
                print("  [飞书重复标题]", kid["title"])
            actual[kid["title"]] = (kid["node_token"], cn["node_token"])
        time.sleep(0.3)
    print("[飞书] 章下知识点合计=%d；子页面总数=%d（顶层%d+知识点%d）"
          % (point_total, len(actual), len(top), point_total))

    local_set, actual_set, map_set = set(local_all), set(actual), set(map_rows)
    print("\n=== 差异 ===")
    print("本地有/飞书缺:", sorted(local_set - actual_set) or "无")
    print("飞书有/本地无:", sorted(actual_set - local_set) or "无")
    print("本地有/map缺:", sorted(local_set - map_set) or "无")
    print("map有/本地无:", sorted(map_set - local_set) or "无")
    bad, map_missing = [], []
    for t, info in map_rows.items():
        if t not in actual:
            map_missing.append(t)
        elif actual[t][0] != info["node"]:
            bad.append((t, "node不一致", info["node"], actual[t][0]))
        elif info["parent"] and info["parent"] != actual[t][1]:
            bad.append((t, "parent不一致", info["parent"], actual[t][1]))
    print("map节点不在飞书:", map_missing or "无")
    print("map父子/node不一致:", bad or "无")
    ok = (len(local_all) == 169 and len(actual) == 169 and len(map_rows) == 169
          and not (local_set ^ actual_set) and not (local_set ^ map_set)
          and not bad and not map_missing and len(top) == 32
          and not dup_t and not dup_n)
    print("\n=== 结论 ===")
    print("结构完全一致(169, 顶层32, 无重复/无错挂):", "是 ✅" if ok else "否 ❌（见上）")


if __name__ == "__main__":
    main()
