#!/usr/bin/env python3
"""百度网盘 ↔ 本地目录 · 日常增量检查与台账（对齐完成后使用）。

原理：百度沙箱不开放 listall/search，全量递归列目录较慢（4千+目录约数十分钟）。
但逐目录 list 返回每个条目的 server_mtime，且实测父目录 mtime 随子内容上传而更新。
因此增量扫描时：目录 mtime 与台账一致 → 整棵子树剪枝跳过；只深入变化/新增分支。

子命令：
  init   <ledger.json>                 全量扫描云端+本地，建立台账（对齐完成后跑一次）
  check  <ledger.json> [--full]        增量（或 --full 全量）重扫，输出自上次以来的
                                       变化清单 + 当前双向差异，并刷新 current 快照
  report <ledger.json> <cur.json>      只打印两份状态之间的变化

台账/状态 schema：
  {"ts","cloud_root","local_root",
   "cloud": {rel: {"dirs":{name:mtime},"files":{name:{size,mtime,fs_id}}}},
   "local": {rel: {"dirs":[names],"files":{name:{size,mtime}}}}}

安全约定：云端删除/移动只报告，不自动产生删除动作；空目录计入状态。
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from baidu_upload import get_token  # noqa: E402
from pan_inventory import strict_list, is_junk  # noqa: E402


# ---------------- 云端扫描 ----------------

def cloud_full(root, token, workers=3, retries=5):
    """全量云端扫描，返回富记录（含 mtime/fs_id）。"""
    data = {}
    queue = [root]
    queued = {root}

    def job(path):
        for attempt in range(1, retries + 1):
            try:
                return path, strict_list(path, token), None
            except Exception as e:  # noqa: BLE001
                err = str(e)
                time.sleep(min(2 * attempt, 10))
        return path, None, err

    in_flight = set()
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue or in_flight:
            while queue and len(in_flight) < workers:
                p = queue.pop(0)
                in_flight.add(pool.submit(job, p))
            done = set()
            for fut in as_completed(list(in_flight)):
                path, items, err = fut.result()
                done.add(fut)
                rel = "" if path == root else path[len(root) + 1:]
                if err:
                    failed.append((path, err))
                    continue
                dirs, files = {}, {}
                for it in items:
                    name = it["server_filename"]
                    if it["isdir"]:
                        if not name.startswith("."):
                            dirs[name] = it.get("server_mtime", 0)
                    elif not is_junk(name):
                        files[name] = {"size": it.get("size", 0),
                                       "mtime": it.get("server_mtime", 0),
                                       "fs_id": it.get("fs_id")}
                data[rel] = {"dirs": dirs, "files": files}
                for d in dirs:
                    child = path + "/" + d
                    if child not in queued:
                        queued.add(child)
                        queue.append(child)
            in_flight -= done
    if failed:
        print("云端扫描失败目录：", file=sys.stderr)
        for p, e in failed[:20]:
            print(f"  {p}: {e}", file=sys.stderr)
        sys.exit(2)
    return data


def cloud_incremental(root, token, ledger):
    """按目录 mtime 剪枝的增量扫描，返回 (当前全量视图, 变化的相对路径集合)。"""
    cur = {}
    changed_branches = set()

    def scan(path, rel):
        try:
            items = strict_list(path, token)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] list 失败 {path}: {e}，按台账保留", file=sys.stderr)
            if rel in ledger["cloud"]:
                cur[rel] = ledger["cloud"][rel]
            return
        old = ledger["cloud"].get(rel)
        dirs, files = {}, {}
        for it in items:
            name = it["server_filename"]
            if it["isdir"]:
                if not name.startswith("."):
                    dirs[name] = it.get("server_mtime", 0)
            elif not is_junk(name):
                files[name] = {"size": it.get("size", 0),
                               "mtime": it.get("server_mtime", 0),
                               "fs_id": it.get("fs_id")}
        cur[rel] = {"dirs": dirs, "files": files}

        old_dirs = old["dirs"] if old else {}
        old_files = old["files"] if old else {}
        branch_changed = (old is None
                          or set(old_dirs) != set(dirs)
                          or set(old_files) != set(files)
                          or any(old_files.get(n, {}).get("mtime") != f["mtime"]
                                 or old_files.get(n, {}).get("size") != f["size"]
                                 for n, f in files.items()))
        if branch_changed:
            changed_branches.add(rel)
        for d, mt in dirs.items():
            child_rel = d if rel == "" else rel + "/" + d
            # 新目录或 mtime 变化才深入；否则整棵剪枝并从台账拷贝
            if d not in old_dirs or old_dirs[d] != mt:
                scan(path + "/" + d, child_rel)
            else:
                _copy_pruned(ledger, child_rel, cur)

    def _copy_pruned(led, prefix, dst):
        for k, v in led["cloud"].items():
            if k == prefix or k.startswith(prefix + "/"):
                dst[k] = v

    scan(root, "")
    return cur, changed_branches


# ---------------- 本地扫描 ----------------

def local_full(root):
    data = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        if rel == ".":
            rel = ""
        files = {}
        for name in filenames:
            if is_junk(name):
                continue
            fp = os.path.join(dirpath, name)
            try:
                st = os.stat(fp)
                files[name] = {"size": st.st_size, "mtime": int(st.st_mtime)}
            except OSError:
                files[name] = {"size": -1, "mtime": 0}
        data[rel] = {"dirs": dirnames, "files": files}
    return data


# ---------------- 变化对比 ----------------

def side_changes(old, new, side):
    """对比某一侧台账→当前，返回分类变化。"""
    out = {"added_files": [], "removed_files": [], "modified_files": [],
           "added_dirs": [], "removed_dirs": []}
    for path in sorted(set(old) | set(new)):
        o = old.get(path, {"dirs": {}, "files": {}})
        n = new.get(path, {"dirs": {}, "files": {}})
        od = set(o["dirs"])
        nd = set(n["dirs"])
        of = set(o["files"])
        nf = set(n["files"])
        pre = "" if path == "" else path + "/"
        for d in sorted(nd - od):
            out["added_dirs"].append(pre + d)
        for d in sorted(od - nd):
            out["removed_dirs"].append(pre + d)
        for f in sorted(nf - of):
            out["added_files"].append(pre + f)
        for f in sorted(of - nf):
            out["removed_files"].append(pre + f)
        for f in sorted(of & nf):
            if o["files"][f].get("size") != n["files"][f].get("size"):
                out["modified_files"].append(
                    f"{pre}{f}（{o['files'][f].get('size')}→{n['files'][f].get('size')}B）")
    return out


def cross_plan(local, cloud):
    """当前本地 vs 当前云端 → 待执行动作（不产生删除）。"""
    plan = {"mkdirs_local": [], "downloads": [], "mkdirs_cloud": [], "uploads": [],
            "size_conflicts": []}
    for path in sorted(set(local) | set(cloud)):
        l = local.get(path, {"dirs": [], "files": {}})
        c = cloud.get(path, {"dirs": {}, "files": {}})
        ld = set(l["dirs"])
        cd = set(c["dirs"])
        lf = set(l["files"])
        cf = set(c["files"])
        pre = "" if path == "" else path + "/"
        for d in sorted(cd - ld):
            plan["mkdirs_local"].append(pre + d)
        for d in sorted(ld - cd):
            plan["mkdirs_cloud"].append(pre + d)
        for f in sorted(cf - lf):
            plan["downloads"].append(pre + f)
        for f in sorted(lf - cf):
            plan["uploads"].append(pre + f)
        for f in sorted(lf & cf):
            if l["files"][f]["size"] != c["files"][f]["size"]:
                plan["size_conflicts"].append(
                    f"{pre}{f}（本地{l['files'][f]['size']}/云端{c['files'][f]['size']}B）")
    return plan


def print_changes(title, ch, limit=40):
    print(f"\n== {title} ==")
    for key, label in [("added_files", "新增文件"), ("modified_files", "修改文件"),
                       ("removed_files", "删除文件（仅报告）"),
                       ("added_dirs", "新增目录"), ("removed_dirs", "删除目录（仅报告）")]:
        items = ch[key]
        if not items:
            continue
        print(f"  {label}: {len(items)}")
        for it in items[:limit]:
            print(f"    {it}")
        if len(items) > limit:
            print(f"    …另有 {len(items) - limit} 项")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("ledger")
    p.add_argument("--local-root", default=os.environ.get("NETDISK_LOCAL_ROOT"))
    p.add_argument("--cloud-root", default=os.environ.get("NETDISK_CLOUD_ROOT"))
    p = sub.add_parser("check")
    p.add_argument("ledger")
    p.add_argument("--full", action="store_true", help="全量扫描（定期审计）")
    p.add_argument("--current-out", default="")
    p = sub.add_parser("report")
    p.add_argument("ledger")
    p.add_argument("current")
    a = ap.parse_args()

    if a.cmd == "init":
        if not a.local_root or not a.cloud_root:
            ap.error("init 需要 --local-root/--cloud-root，或先 export "
                     "NETDISK_LOCAL_ROOT / NETDISK_CLOUD_ROOT")
        token = get_token()
        print("全量扫描云端（约数十分钟）...")
        cloud = cloud_full(a.cloud_root, token)
        print(f"  云端 {len(cloud)} 目录节点")
        local = local_full(a.local_root)
        print(f"  本地 {len(local)} 目录节点")
        led = {"ts": int(time.time()), "cloud_root": a.cloud_root,
               "local_root": a.local_root, "cloud": cloud, "local": local}
        json.dump(led, open(a.ledger, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"台账已建立：{a.ledger}")
        return

    led = json.load(open(a.ledger, encoding="utf-8"))
    if a.cmd == "report":
        cur = json.load(open(a.current, encoding="utf-8"))
        print_changes("云端变化（评估师操作等）", side_changes(led["cloud"], cur["cloud"], "cloud"))
        print_changes("本地变化", side_changes(led["local"], cur["local"], "local"))
        return

    token = get_token()
    print("增量扫描云端...")
    if a.full:
        cloud = cloud_full(led["cloud_root"], token)
    else:
        cloud, branches = cloud_incremental(led["cloud_root"], token, led)
        print(f"  深入变化分支 {len(branches)} 个：{sorted(branches)[:10]}")
    local = local_full(led["local_root"])
    cur = {"ts": int(time.time()), "cloud_root": led["cloud_root"],
           "local_root": led["local_root"], "cloud": cloud, "local": local}
    out = a.current_out or a.ledger.replace(".json", "_current.json")
    json.dump(cur, open(out, "w", encoding="utf-8"), ensure_ascii=False)

    print_changes("云端变化（自上次台账）", side_changes(led["cloud"], cloud, "cloud"))
    print_changes("本地变化（自上次台账）", side_changes(led["local"], local, "local"))
    plan = cross_plan(local, cloud)
    print("\n== 待同步动作 ==")
    print(f"  待下载文件: {len(plan['downloads'])}，待建本地目录: {len(plan['mkdirs_local'])}")
    print(f"  待上传文件: {len(plan['uploads'])}，待建云端目录: {len(plan['mkdirs_cloud'])}")
    print(f"  大小冲突（需人工裁定）: {len(plan['size_conflicts'])}")
    for it in plan["size_conflicts"][:20]:
        print(f"    {it}")
    print(f"\n当前状态已存：{out}（确认同步完成后用它替换台账即完成 commit）")


if __name__ == "__main__":
    main()
