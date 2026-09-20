#!/usr/bin/env python3
"""全量回读验收（新 8 课模型，配置驱动，只读绝不写飞书）：逐篇用全新 lark-cli 进程拉正文，
证明 map 全部子页 + 课程首页都非空、长度达标。每篇独立进程，规避转发代理单进程累计限流。

输出：data/_workspace/<profile>/logs/content_readback.tsv
  列 title<TAB>obj<TAB>kind<TAB>fetched_title<TAB>content_len<TAB>status
判级：去空白后 <100=EMPTY，<300=THIN，其余 OK；拉取失败=FETCH_FAIL。

用法：
  python3 scripts/knowledge/verify_wiki_content.py <profile>            # 全量回读
  python3 scripts/knowledge/verify_wiki_content.py <profile> --refill   # 只补拉现有 TSV 中非 OK 的篇
退出码：0=无 EMPTY/FETCH_FAIL（THIN 仅告警）；1=存在空页/拉取失败；2=前置缺失。
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_raw(profile):
    fp = REPO / f"config/courses/{profile}.json"
    if not fp.exists():
        raise FileNotFoundError(fp)
    with open(fp, encoding="utf-8") as f:
        return json.load(f)


def fetch(obj, retries=4):
    content, ftitle, err = "", "", ""
    for attempt in range(retries):
        p = subprocess.run(
            ["lark-cli", "docs", "+fetch", "--doc", obj, "--doc-format", "markdown",
             "--scope", "full", "--detail", "simple", "--as", "user", "--format", "json"],
            capture_output=True, text=True, timeout=90, cwd=str(REPO),
        )
        raw = p.stdout + p.stderr
        try:
            d = json.loads(p.stdout)
            if d.get("ok"):
                doc = d["data"]["document"]
                return doc.get("content", "") or "", doc.get("title", "") or "", ""
            err = str(d)[:200]
        except Exception:  # noqa: BLE001
            err = raw[:200]
        time.sleep(30 if ("invalid_response" in raw or "temporary token" in raw) else 8)
    return "", "", err


def classify(n):
    return "EMPTY" if n < 100 else ("THIN" if n < 300 else "OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--refill", action="store_true", help="只补拉现有 TSV 中非 OK 的篇")
    args = ap.parse_args()

    cfg = load_raw(args.profile)
    key = cfg.get("key", args.profile)
    wiki = cfg.get("wiki") or {}
    course_obj = wiki.get("courseObjToken")
    course_title = (cfg.get("primaryCourse") or {}).get("name", "")
    map_file = REPO / f"data/_workspace/{key}/logs/wiki_node_map.tsv"
    out = REPO / f"data/_workspace/{key}/logs/content_readback.tsv"
    if not map_file.exists():
        print(f"[前置缺失] map 不存在: {map_file}")
        sys.exit(2)
    if not course_obj:
        print(f"[前置缺失] 配置卡缺 wiki.courseObjToken，请先跑 build_tree.py")
        sys.exit(2)

    # 规范清单：首页 + map 子页
    canon = [(course_title, course_obj, "homepage")]
    for line in map_file.read_text(encoding="utf-8").splitlines():
        c = line.rstrip("\n").split("\t")
        if len(c) >= 3 and c[0]:
            canon.append((c[0], c[2], "page"))

    prior = {}
    if args.refill and out.exists():
        with open(out, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                prior[(r["title"], r["obj"])] = r
    todo = canon
    if args.refill:
        todo = [(t, o, k) for (t, o, k) in canon
                if (t, o) not in prior or prior[(t, o)]["status"] != "OK"]
        print(f"[refill] 规范 {len(canon)} 篇，待补拉非 OK {len(todo)} 篇")

    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.refill else "w"
    fh = open(out, mode, encoding="utf-8", newline="")
    w = csv.writer(fh, delimiter="\t")
    if not args.refill:
        w.writerow(["title", "obj", "kind", "fetched_title", "content_len", "status"])

    stats = {"OK": 0, "THIN": 0, "EMPTY": 0, "FETCH_FAIL": 0}
    for i, (title, obj, kind) in enumerate(todo, 1):
        content, ftitle, err = fetch(obj)
        n = len(content.strip())
        status = classify(n) if not err and (content or n) else "FETCH_FAIL"
        if status == "FETCH_FAIL":
            n = 0
        stats[status] += 1
        w.writerow([title, obj, kind, ftitle, n, status])
        fh.flush()
        flag = {"OK": "✓", "THIN": "⚠薄", "EMPTY": "✗空", "FETCH_FAIL": "✗取"}[status]
        print(f"[{i}/{len(todo)}] {flag} len={n:>6} {title[:42]}", flush=True)
        if status == "FETCH_FAIL":
            print(f"      err={err}", flush=True)
        time.sleep(1.2)
    fh.close()

    # refill 模式下按规范清单汇总最终 TSV（重写为规范顺序，保留最新状态）
    if args.refill:
        merged = {}
        with open(out, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                merged[(r["title"], r["obj"])] = r
        with open(out, "w", encoding="utf-8", newline="") as f:
            ww = csv.writer(f, delimiter="\t")
            ww.writerow(["title", "obj", "kind", "fetched_title", "content_len", "status"])
            for (t, o, k) in canon:
                r = merged.get((t, o))
                if r:
                    ww.writerow([r["title"], r["obj"], r["kind"], r["fetched_title"],
                                 r["content_len"], r["status"]])

    # 全量口径汇总（refill 时读最终 TSV）
    if args.refill:
        stats = {"OK": 0, "THIN": 0, "EMPTY": 0, "FETCH_FAIL": 0}
        with open(out, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                stats[r["status"]] = stats.get(r["status"], 0) + 1
    print("\n===== 回读汇总 =====")
    for k in ("OK", "THIN", "EMPTY", "FETCH_FAIL"):
        print(f"{k}: {stats.get(k, 0)}")
    print("报告:", out)
    sys.exit(1 if (stats.get("EMPTY") or stats.get("FETCH_FAIL")) else 0)


if __name__ == "__main__":
    main()
