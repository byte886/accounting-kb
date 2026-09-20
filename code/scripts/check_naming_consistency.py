#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_naming_consistency.py — 仓库命名一致性巡检 / 重命名影响面 / 整改回归

依据（唯一事实源）：docs/project-management/standards/NAMING_CONVENTION.md 第九章
流程依据：docs/project-management/standards/PROJECT_STRUCTURE_MAINTENANCE.md 第六章 SOP

用法：
  python3 scripts/check_naming_consistency.py                 # 巡检：类型↔命名自洽 + 类型复核候选
  python3 scripts/check_naming_consistency.py --impact NAME   # 影响面：列出全仓引用 NAME 的位置（改名前先跑）
  python3 scripts/check_naming_consistency.py --regression    # 回归：自洽计数 + 相对链接死链（整改后跑）
  python3 scripts/check_naming_consistency.py --help

退出码：巡检/回归发现硬性不自洽或真实死链时返回 1（仅提示类 warning 不影响）；全部通过返回 0。
判型以正文实质为准、头部「文档类型」仅作声明；拿不准的只给 WARN，由人确认，不臆断。
"""
import subprocess
import os
import re
import sys
import argparse

# 默认排除：数据目录、隐藏配置/密钥目录（不纳入仓库命名治理）
DEFAULT_EXCLUDE = ("data/", ".github/", ".secrets/")
# L0 平台/社区固定名，不参与风格判定
FIXED_NAMES = {
    "README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "AGENTS.md",
    ".gitignore", "pre-commit", "requirements.txt",
}
# docs 根 5 个顶层骨架：虽标 Task/Concept/Reference，仍固定大写
TOP_SKELETON = {
    "WORKFLOW.md", "REQUIREMENTS.md", "SYSTEM_REQUIREMENTS.md",
    "DOCUMENTATION_MAP.md", "DIRECTORY_STRUCTURE.md",
}
# development 下的工具/方法类 Reference 用小写；其余位置 Reference 用大写
LOWER_REF_PREFIX = ("docs/development/api/", "docs/development/tools/",
                    "docs/development/guides/", "docs/development/knowledge/")
# 元规则词：H1 标题命中这些词、却标 Task/Concept 时，列为“类型复核候选”
# （只客观列出，交 SOP 第2步通读，不预设结论、不数强制词——操作流程也会大量使用“必须/禁止”）
META_TITLE_WORDS = ("规范", "标准", "约定", "规约", "词表")
CN_RE = re.compile(r"[一-鿿]")
TYPE_RE = re.compile(r"文档类型\**[：:]\s*([A-Za-z]+)")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# 中文过程产物 / 知识库内容目录：文件名段间用下划线 _（ISO 日期里的连字符除外，ADR 另按 9.8）
CN_UNDERSCORE_DIRS = ("task-reports/", "test-plans/", "verification-reports/", "knowledge-base/")


def git_files():
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"],
                         capture_output=True, text=True).stdout
    return [f for f in out.splitlines()
            if not f.startswith(DEFAULT_EXCLUDE)]


def read_head(path, limit=4000):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(limit)
    except Exception:
        return ""


def doc_type(path):
    m = TYPE_RE.search(read_head(path, 800))
    return m.group(1) if m else ""


def is_upper_snake(stem):
    return bool(re.fullmatch(r"[A-Z0-9_]+", stem))


def is_lower_kebab(stem):
    return not re.search(r"[A-Z]", stem)


def cn_separator_warn(path, stem):
    """中文过程产物/内容文件名：去掉 ISO 日期后仍含半角连字符，则提示应改用下划线（警告级、不阻断）。"""
    if path.startswith("docs/project-management/decisions/"):  # ADR 规定 ADR-NNN-中文，豁免
        return None
    if not any(d in path for d in CN_UNDERSCORE_DIRS):
        return None
    if "-" in ISO_DATE_RE.sub("", stem):
        return f"中文过程/内容文件名段间应用下划线 _（ISO 日期除外），疑似连字符混用：{path}"
    return None


def classify(path):
    """返回 (问题描述 or None, 提示 or None)。只对能判定的文件给结论。"""
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    if base in FIXED_NAMES:
        return None, None
    # 脚本：全小写 snake_case
    if re.match(r"scripts/.*\.(sh|py|js)$", path):
        if re.search(r"[A-Z-]", stem):
            return f"脚本应为全小写 snake_case：{path}", None
        return None, None
    # ADR、非 md、中文名：豁免风格判定
    if path.startswith("docs/project-management/decisions/"):
        return None, None
    if not path.endswith(".md"):
        return None, None
    if CN_RE.search(stem):
        # 中文文件不做大小写判定；仅对过程产物/知识库内容目录提示"段间下划线"（日期里的 - 除外）
        return None, cn_separator_warn(path, stem)
    # docs 根顶层骨架固定大写
    if path.startswith("docs/") and path.count("/") == 1 and base in TOP_SKELETON:
        return None, None

    t = doc_type(path)
    upper, lower = is_upper_snake(stem), is_lower_kebab(stem)
    issue = None
    if t in ("Governance", "Template", "Active") and not upper:
        issue = f"[{t}] 应 UPPER_SNAKE 大写：{path}"
    elif t in ("Task", "Concept") and not lower:
        issue = f"[{t}] 应小写 kebab-case：{path}"
    elif t == "Reference":
        if path.startswith(LOWER_REF_PREFIX) and not lower:
            issue = f"[Reference 工具类] 应小写：{path}"
        elif not path.startswith(LOWER_REF_PREFIX) and not upper:
            issue = f"[Reference 全局类] 应大写：{path}"

    # 类型复核候选：H1 自我描述是“规范/标准/约定”，头部却标 Task/Concept（客观列出，通读后可维持原判）
    warn = None
    if t in ("Task", "Concept"):
        head_lines = read_head(path, 400).splitlines()
        h1 = next((ln for ln in head_lines if ln.startswith("#")), "")
        hit = next((w for w in META_TITLE_WORDS if w in h1), None)
        if hit:
            warn = f"标题含「{hit}」但头部标 {t}，请通读确认实质类型（候选，可维持原判）：{path}"
    return issue, warn


def cmd_check(show_clean=False):
    files = git_files()
    issues, warns = [], []
    for f in files:
        issue, warn = classify(f)
        if issue:
            issues.append(issue)
        if warn:
            warns.append(warn)
    print(f"扫描 {len(files)} 个文件（已排除 {', '.join(DEFAULT_EXCLUDE)}）")
    if warns:
        print(f"\n⚠️ 提示/候选 {len(warns)} 条（仅提示、不阻断；请按 SOP 通读确认，可维持原判）：")
        for w in warns:
            print("  " + w)
    if issues:
        print(f"\n❌ 类型↔命名不自洽 {len(issues)} 个：")
        for i in issues:
            print("  " + i)
    elif show_clean or not warns:
        print("\n✅ 类型↔命名 0 不自洽")
    return 1 if issues else 0


def cmd_impact(name):
    files = git_files()
    hits = 0
    pat = re.compile(re.escape(name))
    for f in files:
        if not (f.endswith(".md") or f.endswith((".sh", ".py", ".js", ".gitignore"))):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                for no, line in enumerate(fh, 1):
                    if pat.search(line):
                        print(f"{f}:{no}: {line.strip()[:160]}")
                        hits += 1
        except Exception:
            continue
    print(f"\n共 {hits} 处引用「{name}」（改名/删除前据此逐项级联销项）")
    return 0


def cmd_regression():
    rc = cmd_check(show_clean=True)
    # 相对链接死链
    dead = []
    for f in git_files():
        if not f.endswith(".md"):
            continue
        base = os.path.dirname(f)
        for m in LINK_RE.finditer(read_head(f, 200000)):
            url = m.group(1).split("#")[0]
            if not url or re.match(r"https?://|mailto:|data:", url):
                continue
            target = os.path.normpath(os.path.join(base, url))
            if not os.path.exists(target):
                dead.append((f, m.group(1)))
    print()
    if dead:
        print(f"❌ 相对链接断链 {len(dead)} 个（请确认是否为模板教学占位）：")
        for f, u in dead:
            print(f"  {f} -> {u}")
        rc = 1
    else:
        print("✅ 相对链接 0 断链")
    return rc


def main():
    ap = argparse.ArgumentParser(description="仓库命名一致性巡检/影响面/回归")
    ap.add_argument("--impact", metavar="NAME", help="列出全仓引用 NAME 的位置（影响面）")
    ap.add_argument("--regression", action="store_true", help="整改后回归：自洽 + 断链")
    args = ap.parse_args()
    if args.impact:
        sys.exit(cmd_impact(args.impact))
    if args.regression:
        sys.exit(cmd_regression())
    sys.exit(cmd_check())


if __name__ == "__main__":
    main()
