#!/usr/bin/env python3
"""根据 local/cloud 两份快照生成双向对齐计划（只生成计划，不执行任何写操作）。

用法：
  python3 sync_plan.py <local.json> <cloud.json> <local_root> <cloud_root> [plan.json]

计划内容：
  mkdirs_cloud   云端缺失的目录（含空目录骨架）
  uploads        云端缺失/大小不一致的文件 [{rel, local, remote, size, reason}]
  mkdirs_local   本地缺失的目录（含空目录骨架）
  downloads      本地缺失/大小不一致的文件 [{rel, remote, local, size, reason}]
  extra_*        仅报告，删除一律另行人工确认，本工具不生成删除动作
"""

import argparse
import json
import sys


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("local_json")
    ap.add_argument("cloud_json")
    ap.add_argument("local_root")
    ap.add_argument("cloud_root")
    ap.add_argument("plan_out", nargs="?", default="")
    a = ap.parse_args()

    loc = load(a.local_json)
    net = load(a.cloud_json)

    mkdirs_cloud, uploads = [], []
    mkdirs_local, downloads = [], []
    all_paths = sorted(set(loc) | set(net))

    for path in all_paths:
        l = loc.get(path, {"dirs": [], "files": {}})
        n = net.get(path, {"dirs": [], "files": {}})
        prefix = "" if path == "" else path + "/"

        # 目录
        for d in sorted(set(l["dirs"]) - set(n["dirs"])):
            mkdirs_cloud.append(prefix + d)
        for d in sorted(set(n["dirs"]) - set(l["dirs"])):
            mkdirs_local.append(prefix + d)

        # 文件
        for f in sorted(set(l["files"]) - set(n["files"])):
            rel = prefix + f
            uploads.append({"rel": rel,
                            "local": f"{a.local_root}/{rel}",
                            "remote": f"{a.cloud_root}/{rel}",
                            "size": l["files"][f], "reason": "云端缺失"})
        for f in sorted(set(n["files"]) - set(l["files"])):
            rel = prefix + f
            downloads.append({"rel": rel,
                              "remote": f"{a.cloud_root}/{rel}",
                              "local": f"{a.local_root}/{rel}",
                              "size": n["files"][f], "reason": "本地缺失"})
        for f in sorted(set(l["files"]) & set(n["files"])):
            if l["files"][f] != n["files"][f]:
                rel = prefix + f
                uploads.append({"rel": rel,
                                "local": f"{a.local_root}/{rel}",
                                "remote": f"{a.cloud_root}/{rel}",
                                "size": l["files"][f],
                                "reason": f"大小不一致 本地{l['files'][f]}/云端{n['files'][f]}"})
                downloads.append({"rel": rel,
                                  "remote": f"{a.cloud_root}/{rel}",
                                  "local": f"{a.local_root}/{rel}",
                                  "size": n["files"][f],
                                  "reason": f"大小不一致 云端{n['files'][f]}/本地{l['files'][f]}（双向均列出，需人工裁定方向）"})

    def mb(items):
        return sum(i.get("size", 0) for i in items if i["size"] and i["size"] > 0) / 1024 / 1024

    plan = {
        "local_root": a.local_root,
        "cloud_root": a.cloud_root,
        "mkdirs_cloud": mkdirs_cloud,
        "uploads": uploads,
        "mkdirs_local": mkdirs_local,
        "downloads": downloads,
    }
    print(f"待建云端目录: {len(mkdirs_cloud)}")
    print(f"待上传文件  : {len(uploads)}（约 {mb(uploads):.1f} MB）")
    print(f"待建本地目录: {len(mkdirs_local)}")
    print(f"待下载文件  : {len(downloads)}（约 {mb(downloads):.1f} MB）")
    clash = [u for u in uploads if "大小不一致" in u["reason"]]
    if clash:
        print(f"⚠️ 大小不一致（双向冲突，需人工裁定）: {len(clash)}")

    if a.plan_out:
        with open(a.plan_out, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print(f"计划已写入 {a.plan_out}")


if __name__ == "__main__":
    main()
