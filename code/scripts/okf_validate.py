#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
okf_validate.py —— Open Knowledge Format (OKF) v0.2 一致性校验器（零第三方依赖）

【项目自包含说明】本文件 vendored（原样复制）自全局技能 okf-wiki v0.2 的
scripts/okf_validate.py，复制进本仓库是为了让工程不依赖任何全局技能 / 全局
AGENTS，切换到其它 Agent 或换机器、仅 clone 本仓库即可运行（见 ADR-017）。
请勿在本地分叉修改校验逻辑以免与上游脱节；上游升级时整体替换本文件。

设计依据：reference/OKF-SPEC-v0.2.md §11 Conformance（上游规范，未随本仓库分发）。
  硬错误 E（不合规，必须修）：
    E1 非保留 .md 缺少可识别的 YAML frontmatter
    E2 frontmatter 缺少非空 type
    E3 保留文件结构违规（子目录 index 带 frontmatter；log.md 带 frontmatter）
  软警告 W（规范建议，默认不致命，--strict 时视为不通过）：
    缺 title/description；status 非法；时间不是 ISO8601/未带时区偏移；
    actor 疑似把 human: 误写；stale_after 已过期；死链（规范要求容忍，仅提示）；
    孤儿页；正文脚注与 sources[].id 对不上；v0.1 遗留 timestamp / # Citations；
    log 日期格式/倒序。
  信息 I：信任等级现算结果等，仅供参考。

与上游关系：一致性思路参考 scaccogatto/okf-skills（MIT）的 okf_validate.py，
本实现为零依赖重写（不依赖 PyYAML），仅解析 OKF frontmatter 用到的 YAML 子集，
复杂/无法识别的 YAML 形态采取宽容跳过，不误报。

用法：
  python3 okf_validate.py <bundle目录> [--strict] [--max-warnings N] [--json] [--exclude GLOB ...]
退出码：存在 E 返回 1；--strict 下存在 W 也返回 1；--max-warnings N 下 W 条数超过 N 也返回 1；否则 0。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

RESERVED = {"index.md", "log.md"}
STATUS_VALUES = {"draft", "stable", "deprecated"}
CN_TZ = timezone(timedelta(hours=8))

# YYYY-MM-DD 或带时间（秒可选），末尾 Z 或 ±HH:MM
ISO_FULL = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ACTOR_BAD_HUMAN = re.compile(r"^\s*human[\\/\s]", re.I)  # human/xxx、Human xxx 等疑似误写
MD_LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s#]+)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\)")
FOOTNOTE_REF = re.compile(r"\[\^([^\]\s]+)\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]\s]+)\]\s*:")
CITATIONS_HEADING = re.compile(r"^#{1,6}[ \t]+Citations[ \t]*$", re.M)
LOG_DATE = re.compile(r"^##[ \t]+(\d{4}-\d{2}-\d{2})\s*$", re.M)


# --------------------------- 极简 frontmatter 解析 ---------------------------

def _strip_quotes(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    return v.strip()


def parse_inline_map(s: str) -> dict:
    """解析 `{ by: a, at: b }` 这种行内 map（值内不含逗号的常见形态）。"""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: dict[str, str] = {}
    # 顶层逗号切分（OKF 行内 map 值不含嵌套逗号）
    for part in re.split(r",(?![^{}]*\})", s):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = _strip_quotes(v)
    return out


def parse_frontmatter(fm: str) -> dict:
    """只提取校验所需字段，宽容解析 OKF 使用的 YAML 子集。"""
    data: dict = {"_scalars": {}, "_lists": {}, "_inline": {}}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        # 仅处理顶层（列 0）key
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest == "":
            # 块结构：list 或嵌套 map，收集到缩进回退为止
            block = []
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith((" ", "\t"))):
                block.append(lines[j])
                j += 1
            items = _parse_block_list(block)
            if items is not None:
                data["_lists"][key] = items
            i = j
            continue
        if rest.startswith("[") and rest.endswith("]"):  # 行内 list，如 tags: [a, b]
            data["_scalars"][key] = [_strip_quotes(x) for x in rest[1:-1].split(",") if x.strip()]
        elif rest.startswith("{") and rest.endswith("}"):  # 行内 map
            data["_inline"][key] = parse_inline_map(rest)
        else:
            data["_scalars"][key] = _strip_quotes(rest)
        i += 1
    return data


def _parse_block_list(block: list[str]):
    """解析 `- ...` 列表；每项可能是行内 map 或多行 key: val。非 list 返回 None。"""
    meaningful = [b for b in block if b.strip()]
    if not meaningful or not any(re.match(r"^\s*-\s+", b) for b in meaningful):
        return None
    items, cur = [], None
    for b in block:
        if not b.strip():
            continue
        m_dash = re.match(r"^\s*-\s+(.*)$", b)
        if m_dash:
            if cur is not None:
                items.append(cur)
            payload = m_dash.group(1).strip()
            if payload.startswith("{"):
                cur = parse_inline_map(payload)
            else:
                cur = {}
                if ":" in payload:
                    k, v = payload.split(":", 1)
                    cur[k.strip()] = _strip_quotes(v)
        else:
            mm = re.match(r"^\s+([\w]+):\s*(.*)$", b)
            if mm and isinstance(cur, dict):
                cur[mm.group(1)] = _strip_quotes(mm.group(2))
    if cur is not None:
        items.append(cur)
    return items


def split_frontmatter(text: str):
    """返回 (fm_text|None, body)。文件必须以 --- 开头。"""
    if not text.startswith("---"):
        return None, text
    lines = text.splitlines(keepends=True)
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            fm = "".join(lines[1:idx])
            body = "".join(lines[idx + 1:])
            return fm, body
    return None, text


# ------------------------------- 时间工具 -------------------------------

def parse_dt(s: str):
    try:
        t = s.strip().replace("Z", "+00:00")
        if "T" not in t and " " not in t:
            t += "T00:00:00+08:00"
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CN_TZ)
        return dt
    except Exception:
        return None


# ------------------------------- 单文件检查 -------------------------------

@dataclass
class Finding:
    level: str  # E/W/I
    code: str
    msg: str


@dataclass
class FileReport:
    rel: str
    findings: list[Finding] = field(default_factory=list)

    def add(self, level, code, msg):
        self.findings.append(Finding(level, code, msg))

    @property
    def errors(self): return [f for f in self.findings if f.level == "E"]
    @property
    def warnings(self): return [f for f in self.findings if f.level == "W"]
    @property
    def infos(self): return [f for f in self.findings if f.level == "I"]


def check_concept(rel: str, text: str, now: datetime) -> FileReport:
    r = FileReport(rel)
    fm, body = split_frontmatter(text)
    if fm is None:
        r.add("E", "E1", "缺少可识别的 YAML frontmatter（文件需以 --- 开头、并以 --- 结束）")
        return r  # 无法继续
    data = parse_frontmatter(fm)
    scal, lists, inl = data["_scalars"], data["_lists"], data["_inline"]

    # E2 type
    t = scal.get("type", "")
    if not t:
        r.add("E", "E2", "frontmatter 缺少非空 type（唯一始终必填字段）")

    # W 推荐字段
    if not scal.get("title"):
        r.add("W", "W10", "缺 title（标准档建议；最小档可忽略）")
    if not scal.get("description"):
        r.add("W", "W11", "缺 description（index 与搜索片段会用到）")

    # W v0.1 遗留
    if "timestamp" in scal:
        r.add("W", "W20", "v0.1 遗留字段 timestamp，应迁移为 generated.at（§13.1）")
    if CITATIONS_HEADING.search(body):
        r.add("W", "W21", "正文存在 v0.1 的 # Citations 列表，应迁移为 frontmatter sources（§13.1）")

    # W status
    st = scal.get("status")
    if st is not None and st not in STATUS_VALUES:
        r.add("W", "W30", f"status={st!r} 不在 draft/stable/deprecated（缺省视为 stable）")

    # generated / verified
    gen = inl.get("generated", {})
    if gen.get("at"):
        _check_time(r, gen["at"], "generated.at")
    if gen.get("by") and ACTOR_BAD_HUMAN.match(gen["by"]):
        r.add("W", "W40", f"generated.by={gen['by']!r} 疑似误写：人工须用 human:<id> 前缀")
    ver_items = lists.get("verified") or ([inl["verified"]] if "verified" in inl else [])
    human_reviewed = False
    for v in ver_items:
        if isinstance(v, dict):
            if v.get("at"):
                _check_time(r, v["at"], "verified.at")
            by = v.get("by", "")
            if by.startswith("human:"):
                human_reviewed = True
            elif ACTOR_BAD_HUMAN.match(by):
                r.add("W", "W40", f"verified.by={by!r} 疑似把 human: 误写，会被当成机器、降低信任等级")
    # 信任等级现算（信息）
    if not ver_items:
        r.add("I", "I10", "信任等级=unverified（无 verified；仍可用，补 verified: human:xxx 可升为 human-reviewed）")
    elif human_reviewed:
        r.add("I", "I10", "信任等级=human-reviewed")
    else:
        r.add("I", "I10", "信任等级=machine-confirmed（核验者均非 human:）")

    # sources 时间 + 收集 id
    src_ids = set()
    for s in lists.get("sources", []):
        if isinstance(s, dict):
            if s.get("id"):
                src_ids.add(s["id"])
            if not s.get("resource"):
                r.add("W", "W50", f"sources 条目 {s.get('id') or '?'} 缺 resource（条目内必填）")
            if s.get("last_modified"):
                _check_time(r, s["last_modified"], "sources.last_modified")

    # stale_after
    sa = scal.get("stale_after")
    if sa:
        dt = parse_dt(sa)
        if dt is None or not (ISO_FULL.match(sa) or ISO_DATE.match(sa)):
            r.add("W", "W31", f"stale_after={sa!r} 不是 ISO8601 时刻（建议如 2026-12-31T23:59:59+08:00）")
        elif now >= dt:
            r.add("W", "W32", f"stale_after={sa} 已到期，内容需复审")

    # 正文脚注 ↔ sources id
    refs = set(FOOTNOTE_REF.findall(body))
    defs = set(FOOTNOTE_DEF.findall(body))
    used = refs  # 引用出现即视为使用
    orphan_foot = [x for x in (refs | defs) if src_ids and x not in src_ids and not x.startswith(("fn", "note"))]
    # 只有当文档确实声明了 sources 时才对账，避免对纯说明性脚注误报
    if src_ids:
        for x in sorted(used | defs):
            if x not in src_ids:
                r.add("W", "W60", f"正文脚注 [^{x}] 在 sources 中找不到同 id 条目")
        for x in sorted(src_ids):
            if x not in (refs | defs):
                r.add("I", "I11", f"sources 条目 {x} 未被正文脚注引用（确认是否需要逐句溯源）")
    return r


def _check_time(r: FileReport, val: str, field_name: str):
    if ISO_FULL.match(val):
        return
    if ISO_DATE.match(val):
        r.add("I", "I12", f"{field_name}={val} 只有日期、缺时间与偏移（精度较低，可接受）")
    else:
        r.add("W", "W31", f"{field_name}={val!r} 不是 ISO8601 时间（建议带 UTC 偏移，如 ...+08:00 / Z）")


def check_index(rel: str, text: str, is_root: bool) -> FileReport:
    r = FileReport(rel)
    fm, _ = split_frontmatter(text)
    if fm is not None and not is_root:
        r.add("E", "E3", "非根 index.md 不允许带 frontmatter（仅 bundle 根 index 可有 okf_version）")
    if is_root and fm is not None and "okf_version" not in fm:
        r.add("I", "I13", "根 index 可声明 okf_version: \"0.2\"")
    # 条目形态提示
    if "* [" not in text and "- [" not in text:
        r.add("W", "W70", "index 未见 `* [标题](链接) - 描述` 条目（§8）")
    return r


def check_log(rel: str, text: str) -> FileReport:
    r = FileReport(rel)
    fm, _ = split_frontmatter(text)
    if fm is not None:
        r.add("E", "E3", "log.md 不允许带 frontmatter（§9）")
    dates = LOG_DATE.findall(text)
    if not dates:
        r.add("W", "W71", "log 未见 `## YYYY-MM-DD` 分组（§9）")
    else:
        parsed = [parse_dt(d) for d in dates]
        if any(p is None for p in parsed):
            r.add("W", "W71", "log 存在非 YYYY-MM-DD 的日期标题")
        ordered = [p for p in parsed if p]
        if ordered != sorted(ordered, reverse=True):
            r.add("W", "W72", "log 日期应倒序（最新在最上面）")
    return r


# ------------------------------- 整包检查 -------------------------------

def validate(root: Path, excludes: list[str]):
    now = datetime.now(CN_TZ)
    md_files = sorted(p for p in root.rglob("*.md")
                      if not any(part in (".git", "node_modules") for part in p.parts))
    reports: list[FileReport] = []
    path_to_report: dict[str, FileReport] = {}
    edges: list[tuple[str, str, str]] = []  # (源文件 rel, 原始目标, 归一化目标)

    for p in md_files:
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        name = p.name
        if name == "index.md":
            rep = check_index(rel, text, rel == "index.md")
        elif name == "log.md":
            rep = check_log(rel, text)
        else:
            rep = check_concept(rel, text, now)
        # 收集 bundle 内链接（用于死链/孤儿）
        for tgt in MD_LINK.findall(text):
            if re.match(r"^[a-z]+://", tgt) or tgt.startswith("mailto:"):
                continue
            edges.append((rel, tgt, _resolve_link(rel, tgt, root)))
        reports.append(rep)
        path_to_report[rel] = rep

    # 死链：精确挂到链出方；命中的目标计入 linked
    rel_set = {r.rel for r in reports}
    linked: set[str] = set()
    for src, raw, target in edges:
        if not target:
            continue
        if target in rel_set or (root / target).exists():
            linked.add(target)
        else:  # 规范要求容忍死链，仅作 W，可能是"尚未写"的前向链接
            path_to_report[src].add(
                "W", "W80",
                f"链接目标在包内不存在：{raw}（归一为 {target}；可能是待写的前向链接）")

    # 孤儿：保留文件(index/log，含子目录)豁免，其余 concept 须被某条链接命中
    for rel in sorted(rel_set):
        if Path(rel).name in RESERVED:
            continue
        if rel not in linked:
            path_to_report[rel].add("W", "W81", "孤儿页：未被任何 index/概念链接到，建议在 index 登记")
    return reports


def _resolve_link(rel_source: str, target: str, root: Path) -> str:
    if target.startswith("/"):
        cand = target.lstrip("/")
    else:
        cand = (Path(rel_source).parent / target).as_posix()
    cand = cand.replace("//", "/")
    if cand.endswith("/"):
        cand += "index.md"
    elif not cand.endswith(".md"):
        # 链接到无扩展名路径时，按目录或 .md 两种可能归一（这里补 .md 以便匹配）
        pass
    return cand


def main():
    ap = argparse.ArgumentParser(description="OKF v0.2 一致性校验器（零依赖）")
    ap.add_argument("root", help="bundle 根目录")
    ap.add_argument("--strict", action="store_true", help="警告 W 也视为不通过")
    ap.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    ap.add_argument("--exclude", nargs="*", default=[], help="排除的相对路径 glob，可多次")
    ap.add_argument("--max-warnings", type=int, default=None, metavar="N",
                    help="警告数超过 N 也判不通过（介于默认宽松与 --strict 之间，便于遗留 W 分批清零）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"[致命] 不是目录：{root}", file=sys.stderr)
        return 2

    reports = validate(root, args.exclude)
    n_e = sum(len(r.errors) for r in reports)
    n_w = sum(len(r.warnings) for r in reports)
    n_i = sum(len(r.infos) for r in reports)
    over_max = args.max_warnings is not None and n_w > args.max_warnings

    if args.as_json:
        out = {
            "root": str(root),
            "files": len(reports),
            "errors": n_e, "warnings": n_w, "infos": n_i,
            "items": [
                {"path": r.rel,
                 "errors": [f.__dict__ for f in r.errors],
                 "warnings": [f.__dict__ for f in r.warnings],
                 "infos": [f.__dict__ for f in r.infos]}
                for r in reports if r.findings
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"== OKF 校验：{root} ｜ 文件 {len(reports)} 个 ｜ E {n_e} · W {n_w} · I {n_i} ==")
        for r in reports:
            if not r.findings:
                continue
            print(f"\n· {r.rel}")
            for f in r.findings:
                mark = {"E": "✗ E", "W": "△ W", "I": "· I"}[f.level]
                print(f"  [{mark}{f.code[1:]}] {f.msg}")
        note = ""
        if n_w:
            if args.strict:
                note = "（--strict 下视为不通过）"
            elif over_max:
                note = f"（超过 --max-warnings={args.max_warnings}）"
        print("\n" + ("通过：无硬错误。" if n_e == 0 else "存在硬错误，必须修复。")
              + ((f" 警告 {n_w} 条" + note) if n_w else ""))

    if n_e > 0 or (args.strict and n_w > 0) or over_max:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
