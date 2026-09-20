#!/usr/bin/env python3
"""补拉验收（只读，绝不写入飞书）：只重新拉 content_readback.tsv 里缺失或非 OK 的行。

背景：全量回读尾部撞转发代理限流（invalid_response），这些页 len=0 是"没拉到"而非"飞书上为空"。
做法：
- 以 wiki_node_map.tsv(169) + 课程首页 为准；
- 已在 TSV 且 status=OK 的直接保留；其余（缺失 / FETCH_FAIL / THIN / EMPTY）逐篇用全新
  lark-cli 进程重拉，限流时更长冷却、最多 6 次；
- 合并后按规范顺序重写 content_readback.tsv。
判级同全量脚本：去空白 <100 EMPTY，<300 THIN，其余 OK。
"""
import csv
import json
import subprocess
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parents[4]
WS = PROJ / "data/_workspace/cpa-accounting-2026"
MAP = WS / "logs/wiki_node_map.tsv"
OUT = WS / "logs/content_readback.tsv"
COURSE_OBJ = "SvfadwfgWokuB4xws99cwE03nev"
COURSE_TITLE = "【26考季】VIPCPA系列-会计（罗翔老师）"

# 规范顺序：首页 + map 顺序
canon = [(COURSE_TITLE, COURSE_OBJ, "homepage")]
with open(MAP, encoding="utf-8") as f:
    for line in f:
        c = line.rstrip("\n").split("\t")
        if len(c) >= 3 and c[0]:
            canon.append((c[0], c[2], "page"))

# 读已有结果（按 obj）
have = {}
if OUT.exists():
    with open(OUT, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            have[r["obj"].strip()] = r

def grade(n):
    if n < 100:
        return "EMPTY"
    if n < 300:
        return "THIN"
    return "OK"

def fetch(obj):
    content, ftitle, status, err = "", "", "FETCH_FAIL", ""
    for attempt in range(6):
        try:
            p = subprocess.run(
                ["lark-cli", "docs", "+fetch", "--doc", obj, "--doc-format", "markdown",
                 "--scope", "full", "--detail", "simple", "--as", "user", "--format", "json"],
                capture_output=True, text=True, timeout=90, cwd=PROJ,
            )
        except Exception as e:  # noqa: BLE001
            err = f"exc {e}"
            time.sleep(20)
            continue
        raw = p.stdout + p.stderr
        try:
            d = json.loads(p.stdout)
            if d.get("ok"):
                doc = d["data"]["document"]
                content = doc.get("content", "") or ""
                ftitle = doc.get("title", "") or ""
                return ftitle, len(content.strip()), grade(len(content.strip())), ""
            err = str(d)[:160]
        except Exception:  # noqa: BLE001
            err = raw[:160]
        limited = ("invalid_response" in raw or "temporary token" in raw
                   or "invalid char" in raw)
        time.sleep(45 if limited else 10)
    return ftitle, 0, "FETCH_FAIL", err

results = []
todo = []
for title, obj, kind in canon:
    r = have.get(obj)
    if r and r.get("status", "").strip() == "OK":
        results.append([title, obj, kind, r.get("fetched_title", ""),
                        int(r.get("content_len", 0)), "OK"])
    else:
        todo.append((title, obj, kind))

print(f"规范总数 {len(canon)}，已 OK {len(results)}，待补拉 {len(todo)}", flush=True)
for i, (title, obj, kind) in enumerate(todo, 1):
    ftitle, n, status, err = fetch(obj)
    results.append([title, obj, kind, ftitle, n, status])
    flag = {"OK": "✓", "THIN": "⚠薄", "EMPTY": "✗空", "FETCH_FAIL": "✗取"}[status]
    print(f"[补 {i}/{len(todo)}] {flag} len={n:>6} {title[:42]}", flush=True)
    if status != "OK":
        print(f"      err={err}", flush=True)
    time.sleep(5)  # 篇间冷却，规避限流

# 按规范顺序输出
order = {obj: i for i, (_, obj, _) in enumerate(canon)}
results.sort(key=lambda x: order.get(x[1], 9999))
with open(OUT, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh, delimiter="\t")
    w.writerow(["title", "obj", "kind", "fetched_title", "content_len", "status"])
    w.writerows(results)

from collections import Counter
cnt = Counter(r[5] for r in results)
print("\n===== 合并后汇总 =====")
for k in ("OK", "THIN", "EMPTY", "FETCH_FAIL"):
    print(f"{k}: {cnt.get(k, 0)}")
print("总数:", len(results), "报告:", OUT)
