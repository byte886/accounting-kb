#!/usr/bin/env python3
"""只读核验飞书课程树 vs 本地知识详解 vs map（新 8 课模型，配置驱动，绝不写入）。

校验：课程容器下顶层 = 章 + 全局篇；章下 = 知识点；本地 / 飞书 / map 三方标题集合一致，
map 的 node_token / parent 与飞书实际一致，无重复标题、无错挂、无顶层异常节点。
计数全部动态推导（不写死 169/32），八门课通用。

用法：
  python3 scripts/knowledge/verify_wiki_tree.py <profile>
退出码：0=结构完全一致；1=存在差异；2=前置缺失（未建容器 / map 不存在等）。
"""
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_raw(profile):
    fp = REPO / "config" / "courses" / f"{profile}.json"
    if not fp.exists():
        raise FileNotFoundError(fp)
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def lark(args, retries=4):
    for i in range(retries):
        p = subprocess.run(["lark-cli"] + args + ["--as", "user", "--format", "json"],
                           capture_output=True, text=True, cwd=str(REPO))
        try:
            j = json.loads(p.stdout)
            if j.get("ok"):
                return j
            err = json.dumps(j.get("error", {}), ensure_ascii=False)
        except Exception:  # noqa: BLE001
            err = (p.stdout or "")[:160] + (p.stderr or "")[:160]
        if "invalid_response" in err or "invalid character" in err or "temporary token" in err:
            time.sleep(8 * (i + 1))
            continue
        print("  [lark错误]", err[:200])
        time.sleep(3)
    return None


def children(space, parent):
    items, token = [], None
    while True:
        args = ["wiki", "+node-list", "--space-id", space, "--parent-node-token", parent]
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


def local_titles(knowledge):
    globals_, chapters, points = {}, {}, {}
    k = str(knowledge)
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
    if len(sys.argv) != 2:
        print("用法: python3 verify_wiki_tree.py <profile>")
        sys.exit(2)
    profile = sys.argv[1]
    cfg = load_raw(profile)
    key = cfg.get("key", profile)
    wiki = cfg.get("wiki") or {}
    space = wiki.get("spaceId")
    container = wiki.get("courseNodeToken")
    if not space or not container:
        print(f"[前置缺失] {profile} 配置卡缺 wiki.spaceId/courseNodeToken，请先跑 build_tree.py")
        sys.exit(2)
    knowledge = REPO / cfg["paths"]["localRoot"] / "知识详解"
    map_file = REPO / f"data/_workspace/{key}/logs/wiki_node_map.tsv"
    if not knowledge.exists():
        print(f"[前置缺失] 本地知识详解目录不存在: {knowledge}")
        sys.exit(2)
    if not map_file.exists():
        print(f"[前置缺失] map 不存在: {map_file}，请先跑 build_tree.py")
        sys.exit(2)

    globals_, chapters, points = local_titles(knowledge)
    local_all = list(globals_) + list(chapters) + list(points)
    print(f"[{profile}] 本地：全局篇={len(globals_)} 章={len(chapters)} 知识点={len(points)} 合计子页={len(local_all)}")

    map_rows, dup_t, seen_n = {}, [], {}
    for line in map_file.read_text(encoding="utf-8").splitlines():
        c = line.split("\t")
        if len(c) >= 3 and c[0]:
            if c[0] in map_rows:
                dup_t.append(c[0])
            map_rows[c[0]] = {"node": c[1], "obj": c[2], "parent": c[3] if len(c) > 3 else ""}
            seen_n.setdefault(c[1], []).append(c[0])
    dup_n = {n: t for n, t in seen_n.items() if len(t) > 1}
    print(f"[map] 行={len(map_rows)} 重复标题={dup_t or '无'} 重复node={dup_n or '无'}")

    top = children(space, container)
    actual = {}
    chap_nodes = [n for n in top if n["title"] in chapters]
    glob_nodes = [n for n in top if n["title"] in globals_]
    other = [n for n in top if n["title"] not in chapters and n["title"] not in globals_]
    print(f"[飞书] 容器下顶层={len(top)}（章={len(chap_nodes)} 全局篇={len(glob_nodes)} 其它={len(other)}）")
    for n in other:
        print("  [顶层异常]", n["title"])
    for n in top:
        actual[n["title"]] = (n["node_token"], container)
    point_total = 0
    for cn in chap_nodes:
        kids = children(space, cn["node_token"])
        point_total += len(kids)
        for kid in kids:
            if kid["title"] in actual:
                print("  [飞书重复标题]", kid["title"])
            actual[kid["title"]] = (kid["node_token"], cn["node_token"])
        time.sleep(0.3)
    print(f"[飞书] 章下知识点={point_total}；子页面总数={len(actual)}（顶层{len(top)}+知识点{point_total}）")

    local_set, actual_set, map_set = set(local_all), set(actual), set(map_rows)
    diffs = []
    for label, a, b in (("本地有/飞书缺", local_set, actual_set),
                        ("飞书有/本地无", actual_set, local_set),
                        ("本地有/map缺", local_set, map_set),
                        ("map有/本地无", map_set, local_set)):
        d = sorted(a - b)
        if d:
            diffs.append(f"{label}: {d}")
    bad, map_missing = [], []
    for t, info in map_rows.items():
        if t not in actual:
            map_missing.append(t)
        elif actual[t][0] != info["node"]:
            bad.append((t, "node不一致", info["node"], actual[t][0]))
        elif info["parent"] and info["parent"] != actual[t][1]:
            bad.append((t, "parent不一致", info["parent"], actual[t][1]))
    if map_missing:
        diffs.append(f"map节点不在飞书: {sorted(map_missing)}")
    if bad:
        diffs.append(f"map父子/node不一致: {bad}")
    if dup_t or dup_n:
        diffs.append("map 存在重复标题/node")

    print("\n=== 结论 ===")
    if not diffs and len(local_all) == len(actual) == len(map_rows):
        print(f"结构完全一致（{len(local_all)} 子页，顶层 {len(top)}，无重复/无错挂） ✅")
        sys.exit(0)
    for d in diffs:
        print(" -", d)
    print("结构存在差异 ❌")
    sys.exit(1)


if __name__ == "__main__":
    main()
