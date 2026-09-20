#!/usr/bin/env python3
"""递归遍历飞书课程知识库节点，生成 data/_workspace/cpa-tax-2026/logs/wiki_node_map.tsv（标题\tnode_token\tobj_token\tparent）。"""
import json, subprocess, sys, os

SPACE_ID = sys.argv[1] if len(sys.argv) > 1 else "7686897234545249236"
ROOT = sys.argv[2] if len(sys.argv) > 2 else "K4IcwWg6HidyY6k6Z8hcdmGFnth"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "_workspace", "cpa-tax-2026", "logs", "wiki_node_map.tsv")

def list_nodes(parent):
    cmd = ["lark-cli", "wiki", "+node-list", "--space-id", SPACE_ID,
           "--parent-node-token", parent, "--as", "user", "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"[FAIL] list {parent}: {r.stderr[:200]}", file=sys.stderr)
        return []
    try:
        d = json.loads(r.stdout)
        return d.get("data", {}).get("nodes", [])
    except Exception as e:
        print(f"[FAIL] parse {parent}: {e}", file=sys.stderr)
        return []

def walk(parent, results, depth=0):
    nodes = list_nodes(parent)
    for n in nodes:
        title = n.get("title", "")
        nt = n.get("node_token", "")
        ot = n.get("obj_token", "")
        has_child = n.get("has_child", False)
        results.append((title, nt, ot, parent))
        print(f"{'  '*depth}{title}  node={nt[:12]}...  obj={ot[:12]}...  child={has_child}")
        if has_child:
            walk(nt, results, depth+1)

def main():
    results = []
    print("=== 遍历飞书课程知识库 ===")
    walk(ROOT, results)
    print(f"\n共收集 {len(results)} 个节点")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for title, nt, ot, parent in results:
            f.write(f"{title}\t{nt}\t{ot}\t{parent}\n")
    print(f"已写入 {OUT}")
    # 校验：标题去重
    titles = [r[0] for r in results]
    dupes = [t for t in set(titles) if titles.count(t) > 1]
    if dupes:
        print(f"[WARN] 重复标题: {dupes}", file=sys.stderr)
    else:
        print("标题全局唯一，无重复")

if __name__ == "__main__":
    main()
