#!/usr/bin/env python3
"""按 sync_plan.py 生成的计划执行同步（写操作，执行前请先核对计划）。

用法：
  python3 sync_apply.py up   <plan.json> [--dry-run] [--limit N] [--workers 3]
  python3 sync_apply.py down <plan.json> [--dry-run] [--limit N] [--workers 3]
  python3 sync_apply.py mkdirs <plan.json> up|down   # 只建空目录骨架

特性：并发 2–3、失败收集不中断、结束打印失败清单（可据清单重跑计划）；
上传走 baidu_upload.upload_file（rtype=3 覆盖），下载走 dlink（同大小跳过）。
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from baidu_upload import get_token, mkdir_p, upload_file, get_dlink  # noqa: E402
from pan_inventory import strict_list  # noqa: E402
import subprocess
import urllib.parse


def apply_mkdirs_cloud(plan, token, dry=False):
    todo = plan["mkdirs_cloud"]
    print(f"[云端建目录] {len(todo)} 个")
    root = plan["cloud_root"]
    for rel in todo:
        remote = f"{root}/{rel}"
        print(f"  mkdir {remote}")
        if not dry:
            mkdir_p(remote, token)


def apply_mkdirs_local(plan, dry=False):
    todo = plan["mkdirs_local"]
    print(f"[本地建目录] {len(todo)} 个")
    root = plan["local_root"]
    for rel in todo:
        local = f"{root}/{rel}"
        print(f"  mkdir {local}")
        if not dry:
            os.makedirs(local, exist_ok=True)


def apply_up(plan, token, workers, limit, dry=False):
    apply_mkdirs_cloud(plan, token, dry)
    todo = plan["uploads"][:limit] if limit else plan["uploads"]
    print(f"[上传] {len(todo)} / {len(plan['uploads'])} 个文件，并发 {workers}")
    failed = []

    def one(item):
        try:
            if dry:
                return item, None
            upload_file(item["local"], item["remote"], token)
            return item, None
        except BaseException as e:  # noqa: BLE001  upload_file 内部 sys.exit
            return item, str(e)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, it) for it in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            item, err = fut.result()
            tag = "OK " if not err else "ERR"
            print(f"[{i}/{len(todo)}] {tag} {item['rel']}" + (f" -> {err}" if err else ""))
            if err:
                failed.append({"rel": item["rel"], "err": err})
    return failed


def _download_one(item, token, fs_cache):
    remote = item["remote"]
    local = item["local"]
    parent, name = remote.rsplit("/", 1)
    if os.path.isfile(local) and os.path.getsize(local) == item["size"]:
        return "skip"
    if parent not in fs_cache:
        fs_cache[parent] = {x["server_filename"]: x for x in strict_list(parent, token)}
    entry = fs_cache[parent].get(name)
    if not entry:
        raise RuntimeError("云端未找到（快照可能过期，重跑 cloud-snapshot）")
    os.makedirs(os.path.dirname(local), exist_ok=True)
    dlink = get_dlink(entry["fs_id"], token)
    url = dlink + "&access_token=" + urllib.parse.quote(token, safe="")
    tmp = local + ".part"
    cmd = ["curl", "-sL", "--connect-timeout", "10", "-H",
           "User-Agent: pan.baidu.com", "-o", tmp]
    rate = os.environ.get("BAIDU_DOWNLOAD_RATE", "").strip()
    if rate:
        cmd += ["--limit-rate", rate]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    if os.path.getsize(tmp) != item["size"]:
        raise RuntimeError(f"大小不符 期望{item['size']} 实得{os.path.getsize(tmp)}")
    os.replace(tmp, local)
    return "ok"


def apply_down(plan, token, workers, limit, dry=False):
    apply_mkdirs_local(plan, dry)
    todo = plan["downloads"][:limit] if limit else plan["downloads"]
    print(f"[下载] {len(todo)} / {len(plan['downloads'])} 个文件，并发 {workers}")
    failed, fs_cache = [], {}

    def one(item):
        for attempt in range(1, 4):
            try:
                if dry:
                    return item, "dry", None
                return item, _download_one(item, token, fs_cache), None
            except BaseException as e:  # noqa: BLE001
                if attempt == 3:
                    return item, None, str(e)
                time.sleep(2 * attempt)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, it) for it in todo]
        for i, fut in enumerate(as_completed(futs), 1):
            item, status, err = fut.result()
            if err:
                print(f"[{i}/{len(todo)}] ERR {item['rel']} -> {err}")
                failed.append({"rel": item["rel"], "err": err})
            elif status == "skip":
                print(f"[{i}/{len(todo)}] SKIP {item['rel']}")
            else:
                print(f"[{i}/{len(todo)}] OK {item['rel']}")
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("direction", choices=["up", "down", "mkdirs"])
    ap.add_argument("plan")
    ap.add_argument("mkdir_dir", nargs="?", choices=["up", "down"], default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()

    plan = json.load(open(a.plan, encoding="utf-8"))
    token = get_token()

    if a.direction == "mkdirs":
        if a.mkdir_dir == "up":
            apply_mkdirs_cloud(plan, token, a.dry_run)
        elif a.mkdir_dir == "down":
            apply_mkdirs_local(plan, a.dry_run)
        else:
            ap.error("mkdirs 需要指定 up 或 down")
        return

    failed = apply_up(plan, token, a.workers, a.limit, a.dry_run) if a.direction == "up" \
        else apply_down(plan, token, a.workers, a.limit, a.dry_run)
    print("=" * 60)
    if failed:
        print(f"❌ {len(failed)} 个失败：")
        for f in failed[:50]:
            print(f"  {f['rel']}: {f['err']}")
        sys.exit(1)
    print("✅ 本方向计划全部完成")


if __name__ == "__main__":
    main()
