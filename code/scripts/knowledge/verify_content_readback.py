#!/usr/bin/env python3
"""全量回读验收：从飞书逐篇拉正文，证明 169 子页 + 课程首页都非空、标题对得上。

只读，绝不写入。每篇用全新 lark-cli 进程（规避转发代理单进程累计限流）。
输出：
  logs/content_readback.tsv  每行 title<TAB>obj<TAB>kind<TAB>fetched_title<TAB>content_len<TAB>status
标准：content 去空白后 <100 判 EMPTY，<300 判 THIN，其余 OK；拉取失败判 FETCH_FAIL。
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

rows = []
with open(MAP, encoding="utf-8") as f:
    for line in f:
        c = line.rstrip("\n").split("\t")
        if len(c) >= 3 and c[0]:
            rows.append((c[0], c[2]))  # title, obj
# 首页放最后也无妨，这里插到最前
items = [(COURSE_TITLE, COURSE_OBJ, "homepage")]
for t, o in rows:
    items.append((t, o, "page"))

OUT.parent.mkdir(parents=True, exist_ok=True)
fh = open(OUT, "w", encoding="utf-8", newline="")
w = csv.writer(fh, delimiter="\t")
w.writerow(["title", "obj", "kind", "fetched_title", "content_len", "status"])

stats = {"OK": 0, "THIN": 0, "EMPTY": 0, "FETCH_FAIL": 0}
for i, (title, obj, kind) in enumerate(items, 1):
    content, ftitle, status, err = "", "", "FETCH_FAIL", ""
    for attempt in range(4):
        p = subprocess.run(
            ["lark-cli", "docs", "+fetch", "--doc", obj, "--doc-format", "markdown",
             "--scope", "full", "--detail", "simple", "--as", "user", "--format", "json"],
            capture_output=True, text=True, timeout=90, cwd=PROJ,
        )
        raw = p.stdout + p.stderr
        try:
            d = json.loads(p.stdout)
            if d.get("ok"):
                doc = d["data"]["document"]
                content = doc.get("content", "") or ""
                ftitle = doc.get("title", "") or ""
                n = len(content.strip())
                if n < 100:
                    status = "EMPTY"
                elif n < 300:
                    status = "THIN"
                else:
                    status = "OK"
                err = ""
                break
            err = str(d)[:200]
        except Exception:
            err = raw[:200]
        # 限流：换新进程前冷却
        time.sleep(30 if ("invalid_response" in raw or "temporary token" in raw) else 8)
    n = len(content.strip())
    stats[status] += 1
    w.writerow([title, obj, kind, ftitle, n, status])
    fh.flush()
    flag = {"OK": "✓", "THIN": "⚠薄", "EMPTY": "✗空", "FETCH_FAIL": "✗取"}[status]
    print(f"[{i}/{len(items)}] {flag} len={n:>6} {title[:42]}", flush=True)
    if status == "FETCH_FAIL":
        print(f"      err={err}", flush=True)
    time.sleep(1.2)

fh.close()
print("\n===== 回读汇总 =====")
for k in ("OK", "THIN", "EMPTY", "FETCH_FAIL"):
    print(f"{k}: {stats[k]}")
print("报告:", OUT)
