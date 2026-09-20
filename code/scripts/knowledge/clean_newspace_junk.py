#!/usr/bin/env python3
"""清空指定父节点下的全部子节点（wiki +node-delete 默认级联 include-children，会连同孙节点删除）。
过程件，不入库。
用法：python3 run/clean_newspace_junk.py [parent_node_token] [--execute]
  - 不带 parent 默认清空间根「课程库」K4；清课程容器内容则传课程节点 Z8Aj。
  - 不带 --execute 仅演练列出；带 --execute 才真删。
"""
import json
import subprocess
import sys
import time

SPACE = "7686897234545249236"
DEFAULT_ROOT = "K4IcwWg6HidyY6k6Z8hcdmGFnth"  # 空间唯一根节点「课程库」
_pos = [a for a in sys.argv[1:] if a != "--execute"]
ROOT = _pos[0] if _pos else DEFAULT_ROOT
EXECUTE = "--execute" in sys.argv


def lark(args, timeout=120):
    p = subprocess.run(
        ["lark-cli"] + args + ["--as", "user", "--format", "json"],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "error": (p.stdout[:300] + p.stderr[:300])}


def list_children(parent):
    out, token = [], None
    while True:
        args = ["wiki", "+node-list", "--space-id", SPACE, "--parent-node-token", parent]
        if token:
            args += ["--page-token", token]
        r = lark(args)
        d = r.get("data", {}) if r.get("ok") else {}
        out += d.get("nodes", [])
        if d.get("has_more"):
            token = d.get("page_token")
            time.sleep(0.5)
        else:
            break
    return out


def main():
    nodes = list_children(ROOT)
    print(f"[演练] 课程库根下现有顶层节点 {len(nodes)} 个：", flush=True)
    for n in nodes:
        print(f"  - {n['title']}  node={n['node_token']}  has_child={n['has_child']}", flush=True)
    if not EXECUTE:
        print("\n[演练] 未加 --execute，不删除。", flush=True)
        return

    ok, fail = 0, []
    for i, n in enumerate(nodes, 1):
        tok, title = n["node_token"], n["title"]
        r = lark(["wiki", "+node-delete", "--node-token", tok, "--obj-type", "wiki",
                  "--space-id", SPACE, "--yes"], timeout=180)
        if r.get("ok"):
            ok += 1
            print(f"[{i}/{len(nodes)}] 已删除 {title}", flush=True)
        else:
            fail.append((title, str(r.get("error"))[:200]))
            print(f"[{i}/{len(nodes)}] 删除失败 {title}: {str(r.get('error'))[:200]}", flush=True)
        time.sleep(1.5)

    time.sleep(3)
    remain = list_children(ROOT)
    print(f"\n[汇总] 删除指令成功 {ok}，失败 {len(fail)}；复核课程库根下剩余顶层 {len(remain)} 个", flush=True)
    for n in remain:
        print(f"  剩余: {n['title']} node={n['node_token']}", flush=True)
    for t, e in fail:
        print(f"  [失败] {t}: {e}", flush=True)


if __name__ == "__main__":
    main()
