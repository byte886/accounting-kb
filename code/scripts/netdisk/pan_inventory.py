#!/usr/bin/env python3
"""百度网盘 ↔ 本地目录 对齐盘点工具（通用：根目录由参数指定）

子命令：
  cloud-snapshot <网盘根> <out.json>     递归列云端，落 JSON 快照（并发+重试+断点缓存）
  local-snapshot <本地根> <out.json>     走本地目录，落 JSON 快照（含空目录，排除点开头文件）
  diff <local.json> <cloud.json>         结构/文件/大小对账，分类输出；rc 0=一致 1=有差异
  tree <snapshot.json> [前缀]            打印快照目录树与计数

快照 schema（与 verify_netdisk_final.py 兼容）：
  {"root": "...", "data": {"<相对路径，根为''>": {"dirs": [...], "files": {名: 字节}}}}

约定：点开头的文件/目录（.DS_Store/.Trashes 等）两边都不收录；
同步临时件（.part/.tmp/.crdownload/*.baiduyun.p.downloading 等）两边都不收录；
空目录显式收录（空目录骨架本身就是要同步的项目管理信息）。
"""

JUNK_SUFFIXES = (".part", ".tmp", ".crdownload", ".baiduyun.p.downloading",
                 ".baiduyun.p.uploading", ".downloading")


def is_junk(name):
    return name.startswith(".") or name.endswith(JUNK_SUFFIXES)

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from baidu_upload import get_token  # noqa: E402


def strict_list(remote_dir, token):
    """直接调 xpan list，errno != 0 一律抛错（list_files 会把错误吞成空列表，
    会把限流/瞬时错误伪装成空目录，盘点绝不能接受）。"""
    import subprocess
    import urllib.parse
    url = ("https://pan.baidu.com/rest/2.0/xpan/file?method=list"
           f"&access_token={token}&dir={urllib.parse.quote(remote_dir)}&web=web")
    out = subprocess.run(["curl", "-s", "--connect-timeout", "10", url],
                         capture_output=True, text=True, timeout=30).stdout
    resp = json.loads(out)
    if resp.get("errno") != 0:
        raise RuntimeError(f"list errno={resp.get('errno')} {str(resp)[:120]}")
    return resp.get("list", [])


def cloud_snapshot(root, out_path, workers=3, retries=5, fresh=False):
    token = get_token()
    root = root.rstrip("/")
    cache_path = out_path + ".part"
    data = {}
    if os.path.isfile(cache_path) and not fresh:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f).get("data", {})
        print(f"[续跑] 已缓存 {len(data)} 个目录")

    # BFS 发现 + 线程池列目录
    queue = [root]
    queued = {root}
    failed = []

    def job(path):
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                items = strict_list(path, token)
                return path, items, None
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(min(2 * attempt, 10))
        return path, None, str(last_err)

    in_flight = set()
    total = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue or in_flight:
            while queue and len(in_flight) < workers:
                p = queue.pop(0)
                rel = "" if p == root else p[len(root) + 1:]
                if rel in data:
                    continue
                in_flight.add(pool.submit(job, p))
                total += 1
            done = set()
            for fut in as_completed(list(in_flight), timeout=None):
                path, items, err = fut.result()
                done.add(fut)
                rel = "" if path == root else path[len(root) + 1:]
                if err:
                    failed.append((path, err))
                    continue
                dirs, files = [], {}
                for it in items:
                    name = it["server_filename"]
                    if it["isdir"]:
                        if not name.startswith("."):
                            dirs.append(name)
                    elif not is_junk(name):
                        files[name] = it.get("size", 0)
                data[rel] = {"dirs": sorted(dirs), "files": files}
                for d in dirs:
                    child = path + "/" + d
                    child_rel = d if rel == "" else rel + "/" + d
                    if child not in queued and child_rel not in data:
                        queued.add(child)
                        queue.append(child)
                if total % 10 == 0:
                    print(f"  已列 {total} 个目录，待列 {len(queue)}...", flush=True)
            in_flight -= done
            # 每批落盘，支持断点
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"root": root, "data": data}, f, ensure_ascii=False)

    if failed:
        print("以下目录列出失败：", file=sys.stderr)
        for p, e in failed:
            print(f"  {p}: {e}", file=sys.stderr)
        print("重跑本命令可断点续列", file=sys.stderr)
        sys.exit(2)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"root": root, "data": data}, f, ensure_ascii=False, indent=1)
    os.remove(cache_path)
    nfiles = sum(len(v["files"]) for v in data.values())
    print(f"云端快照完成：{len(data)} 个目录，{nfiles} 个文件 -> {out_path}")


def local_snapshot(root, out_path):
    root = root.rstrip("/")
    data = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        if rel == ".":
            rel = ""
        files = {}
        for name in sorted(filenames):
            if is_junk(name):
                continue
            fp = os.path.join(dirpath, name)
            try:
                files[name] = os.path.getsize(fp)
            except OSError:
                files[name] = -1
        data[rel] = {"dirs": dirnames, "files": files}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"root": root, "data": data}, f, ensure_ascii=False, indent=1)
    nfiles = sum(len(v["files"]) for v in data.values())
    print(f"本地快照完成：{len(data)} 个目录，{nfiles} 个文件 -> {out_path}")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def diff_snaps(local_p, cloud_p):
    loc = load(local_p)["data"]
    net = load(cloud_p)["data"]
    diffs = []
    for path in sorted(set(loc) | set(net)):
        label = path if path else "(根目录)"
        l = loc.get(path, {"dirs": [], "files": {}})
        n = net.get(path, {"dirs": [], "files": {}})
        ld, nd = set(l["dirs"]), set(n["dirs"])
        lf, nf = set(l["files"]), set(n["files"])
        if ld - nd:
            diffs.append(("目录缺失-云端", label, sorted(ld - nd)))
        if nd - ld:
            diffs.append(("目录多余-云端", label, sorted(nd - ld)))
        if lf - nf:
            diffs.append(("文件缺失-云端", label, sorted(lf - nf)))
        if nf - lf:
            diffs.append(("文件多余-云端", label, sorted(nf - lf)))
        mm = [f"{f}(本地{l['files'][f]}B/云端{n['files'][f]}B)"
              for f in sorted(lf & nf) if l["files"][f] != n["files"][f]]
        if mm:
            diffs.append(("大小不一致", label, mm))
    ld_total = sum(len(v["dirs"]) for v in loc.values())
    nd_total = sum(len(v["dirs"]) for v in net.values())
    lf_total = sum(len(v["files"]) for v in loc.values())
    nf_total = sum(len(v["files"]) for v in net.values())
    print("=" * 64)
    print(f"本地：{len(loc)} 个目录节点 / {lf_total} 个文件")
    print(f"云端：{len(net)} 个目录节点 / {nf_total} 个文件")
    print("=" * 64)
    if not diffs:
        print("✅ 完全一致（结构、文件集合、大小；空目录已计入）")
        return 0
    buckets = {}
    for kind, label, items in diffs:
        buckets.setdefault(kind, []).append((label, items))
    for kind, rows in buckets.items():
        n = sum(len(i) for _, i in rows)
        print(f"\n【{kind}】共 {n} 项，{len(rows)} 个目录：")
        for label, items in rows:
            show = items if len(items) <= 8 else items[:8] + [f"...等 {len(items)} 项"]
            for it in show:
                print(f"  {label}/{it}")
    print(f"\n❌ {sum(len(i) for _, _, i in diffs)} 处差异")
    return 1


def tree(snap_p, prefix=""):
    snap = load(snap_p)
    root = snap["root"]
    data = snap["data"]
    print(f"根: {root}")
    keys = sorted(k for k in data if k.startswith(prefix))
    for k in keys:
        v = data[k]
        depth = 0 if k == "" else k.count("/") + 1
        name = root if k == "" else k.rsplit("/", 1)[-1]
        print("  " * depth + f"{name}/  ({len(v['dirs'])} 子目录, {len(v['files'])} 文件)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cloud-snapshot")
    p.add_argument("root")
    p.add_argument("out")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--fresh", action="store_true", help="忽略 .part 缓存全量重扫")
    p = sub.add_parser("local-snapshot")
    p.add_argument("root")
    p.add_argument("out")
    p = sub.add_parser("diff")
    p.add_argument("local_json")
    p.add_argument("cloud_json")
    p = sub.add_parser("tree")
    p.add_argument("snapshot")
    p.add_argument("prefix", nargs="?", default="")
    a = ap.parse_args()

    if a.cmd == "cloud-snapshot":
        cloud_snapshot(a.root, a.out, workers=a.workers, fresh=a.fresh)
    elif a.cmd == "local-snapshot":
        local_snapshot(a.root, a.out)
    elif a.cmd == "diff":
        sys.exit(diff_snaps(a.local_json, a.cloud_json))
    elif a.cmd == "tree":
        tree(a.snapshot, a.prefix)


if __name__ == "__main__":
    main()
