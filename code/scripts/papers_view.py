#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
papers_view.py — papers 题源的「按讲索引视图」（只读，不落盘、不复制任何文件）

遵循 standards 2.2.4「物理集中存、逻辑按讲视图」：
  - 物理：data/_workspace/<profile>/papers/<paperId>.json + manifest/paper_index.json（按 paperId 集中存，不按讲复制）
  - 视图：本脚本由 paper_index.json 的 chapter 字段 group by 现场派生「每讲几套卷、多少题」

用法：
  python3 scripts/papers_view.py                  # 全讲概览：讲次 → 卷数/题数/paperId
  python3 scripts/papers_view.py --lecture 01     # 只看标题含 "01" 的讲，列每套卷明细
  python3 scripts/papers_view.py --lecture 增值税 # 关键词模糊匹配
  python3 scripts/papers_view.py --json           # 输出结构化 JSON（供其它脚本消费）

注意：chapter 字段前导空格需 strip；这是只读视图，绝不写回、绝不生成第二份物理副本。
"""
import argparse
import collections
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts', 'knowledge'))
from course_profile import load_profile  # noqa: E402
_profile = load_profile()  # 支持 env GAODUN_COURSE_PROFILE，缺省税法
DEFAULT_INDEX = os.path.join(
    PROJECT_ROOT, 'data', '_workspace', _profile['key'], 'manifest', 'paper_index.json')
LECTURE_NUM_RE = re.compile(r'精讲(\d+)')


def load_index(path):
    with open(path, encoding='utf-8') as f:
        rows = json.load(f)
    for r in rows:
        r['chapter'] = (r.get('chapter') or '').strip()
    return rows


def lecture_sort_key(chapter):
    m = LECTURE_NUM_RE.search(chapter)
    # 有精讲编号按编号；强化冲刺等无编号排最后
    return (0, int(m.group(1))) if m else (1, chapter)


def group_by_lecture(rows):
    g = collections.OrderedDict()
    for ch in sorted({r['chapter'] for r in rows if r['chapter']}, key=lecture_sort_key):
        items = [r for r in rows if r['chapter'] == ch]
        g[ch] = {
            'papers': len(items),
            'questions': sum(int(r.get('qCount', 0)) for r in items),
            'paperIds': [r['paperId'] for r in items],
            'items': sorted(items, key=lambda r: str(r['paperId'])),
        }
    return g


def main():
    ap = argparse.ArgumentParser(description='papers 按讲索引只读视图')
    ap.add_argument('--index', default=DEFAULT_INDEX, help='paper_index.json 路径')
    ap.add_argument('--lecture', help='只看标题含该关键词/讲号的讲（如 01、增值税）')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    args = ap.parse_args()

    if not os.path.exists(args.index):
        sys.exit(f'✗ 找不到 {args.index}')
    rows = load_index(args.index)
    grouped = group_by_lecture(rows)

    if args.lecture:
        kw = args.lecture
        grouped = {ch: v for ch, v in grouped.items() if kw in ch}
        if not grouped:
            sys.exit(f'✗ 没有标题含 "{kw}" 的讲')

    if args.json:
        out = {ch: {'papers': v['papers'], 'questions': v['questions'],
                    'paperIds': v['paperIds']} for ch, v in grouped.items()}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    detail = bool(args.lecture)
    total_p, total_q = 0, 0
    for ch, v in grouped.items():
        total_p += v['papers']; total_q += v['questions']
        print(f"\n■ {ch}  —  {v['papers']}套 / {v['questions']}题")
        if detail:
            for r in v['items']:
                print(f"    {r['paperId']:>6}  {r.get('cls',''):<6} {r.get('qCount',0):>3}题  {r.get('title','')}")
        else:
            print(f"    paperIds: {v['paperIds']}")
    print(f"\n合计：{len(grouped)} 讲，{total_p} 套卷，{total_q} 题")


if __name__ == '__main__':
    main()
