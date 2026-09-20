#!/usr/bin/env python3
"""SOP 首推的「简单逐个处理」内容同步驱动（过程件，不入库）：
每一篇都起一个全新 lark-cli 进程写正文，成功落 done，失败只记录不纠缠，
篇间固定间隔（默认10秒）；可反复重跑（按 done 断点续传，只补未成功篇）。

写入顺序：① 课程首页（根 README → 课程容器节点，需 env COURSE_OBJ；其章链接依赖完整 map）
          ② 2 全局篇 + 30 章 README + 137 知识点 = 169 子页面。
用法：
  COURSE_OBJ=<课程obj> python3 run/sync_content_perfile.py             # 续跑（含首页）
  RESYNC_FORCE=1 COURSE_OBJ=<obj> python3 run/sync_content_perfile.py   # 忽略done全量重写
"""
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROFILE = "cpa-accounting-2026"
LOGS = REPO / "data/_workspace" / PROFILE / "logs"
MAP_FILE = LOGS / "wiki_node_map.tsv"
DONE_DIR = LOGS / "resync_done"
KNOWLEDGE = REPO / "data/高顿/CPA/【26考季】VIPCPA系列-会计（罗翔老师）/知识详解"
RESOLVER = REPO / "scripts/wiki_link_resolve.py"
INTERVAL = float(os.environ.get("PERFILE_INTERVAL", "10"))
FORCE = os.environ.get("RESYNC_FORCE") == "1"
COURSE_OBJ = os.environ.get("COURSE_OBJ", "").strip()
HOMEPAGE_KEY = "__COURSE_HOMEPAGE__"


def safe_name(t):
    return t.replace("/", "_").replace(" ", "_")


def strip_frontmatter(text):
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[i + 1:]).lstrip("\n")
    return text


def load_title2obj():
    m = {}
    for line in MAP_FILE.read_text(encoding="utf-8").splitlines():
        c = line.split("\t")
        if len(c) >= 3 and c[0]:
            m[c[0]] = c[2]
    return m


def collect_children():
    """2 全局篇 + 30 章 README + 137 知识点 = 169。返回 (标题, 路径)。"""
    items = []
    for p in sorted(glob.glob(str(KNOWLEDGE / "*.md"))):
        if os.path.basename(p) == "README.md":
            continue
        items.append((os.path.basename(p)[:-3], p))
    for group in sorted(glob.glob(str(KNOWLEDGE / "[0-9]*/"))):
        gname = os.path.basename(group.rstrip(os.sep))
        readme = os.path.join(group, "README.md")
        if os.path.isfile(readme):
            items.append((gname, readme))
        for p in sorted(glob.glob(os.path.join(group, "*.md"))):
            if os.path.basename(p) == "README.md":
                continue
            items.append((os.path.basename(p)[:-3], p))
    return items


def write_one(path, obj):
    raw = open(path, encoding="utf-8").read()
    raw = strip_frontmatter(raw)
    resolved = subprocess.run(
        ["python3", str(RESOLVER)], input=raw, capture_output=True, text=True,
        cwd=str(REPO), env={**os.environ, "WIKI_MAP": str(MAP_FILE)},
    ).stdout
    if not resolved.strip():
        return False, "resolver 输出为空"
    if "](" + "./" in resolved:
        print("    [警告] 仍残留 ./ 相对链接（cite 未生效，检查 WIKI_MAP）", flush=True)
    proc = subprocess.run(
        ["lark-cli", "docs", "+update", "--doc", obj, "--command", "overwrite",
         "--doc-format", "markdown", "--content", "-", "--as", "user", "--format", "json"],
        input=resolved, capture_output=True, text=True, cwd=str(REPO),
    )
    out = proc.stdout + proc.stderr
    compact = out.replace(" ", "")
    if '"ok":true' in compact or '"ok":true' in out:
        return True, ""
    tag = "invalid_response/代理限流" if ("invalid_response" in out or "parse temporary token" in out) else out[:200]
    return False, tag


def main():
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    t2o = load_title2obj()

    # (done_key, 日志标题, 路径, obj)
    tasks = []
    if COURSE_OBJ:
        tasks.append((HOMEPAGE_KEY, "课程首页", str(KNOWLEDGE / "README.md"), COURSE_OBJ))
    missing = []
    for title, path in collect_children():
        obj = t2o.get(title)
        if not obj:
            missing.append(title)
            continue
        tasks.append((title, title, path, obj))

    n_child = len(tasks) - (1 if COURSE_OBJ else 0)
    print(f"[配置] map 标题 {len(t2o)} 个；任务 {len(tasks)} 篇（首页={'有' if COURSE_OBJ else '无'} + 子页面{n_child}）", flush=True)
    print(f"[配置] interval={INTERVAL}s force={FORCE}；无obj映射 {len(missing)} 篇", flush=True)
    ok = skip = 0
    failed = []
    for i, (key, label, path, obj) in enumerate(tasks, 1):
        flag = DONE_DIR / (safe_name(key) + ".done")
        if flag.exists() and not FORCE:
            skip += 1
            continue
        success, err = write_one(path, obj)
        if success:
            flag.write_text(label + "\n", encoding="utf-8")
            ok += 1
            print(f"[{i}/{len(tasks)}] ✓ {label}", flush=True)
        else:
            failed.append((label, err))
            print(f"[{i}/{len(tasks)}] ✗ {label} :: {err}", flush=True)
            if "代理限流" in str(err):
                time.sleep(30)
        time.sleep(INTERVAL)

    print("\n========== 汇总 ==========", flush=True)
    print(f"新写成功 {ok}，done跳过 {skip}，无映射 {len(missing)}，失败 {len(failed)}", flush=True)
    for t in missing:
        print(f"  [无映射] {t}", flush=True)
    for t, e in failed:
        print(f"  [失败] {t} :: {e}", flush=True)
    sys.exit(1 if (missing or failed) else 0)


if __name__ == "__main__":
    main()
