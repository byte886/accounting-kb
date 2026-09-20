#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量给知识详解 108 篇加 OKF v0.2 标准档 frontmatter。

- 遍历知识详解目录：2 全局篇（根目录）+ 14 章 README + 92 知识点篇
- 解析每篇顶部 > Context Block，提取所属组/来源/题量/更新
- 按 type 词表生成 frontmatter：KnowledgePoint / ChapterIndex / Reference
- 已有 frontmatter（文件以 --- 开头）的跳过（试点 4 篇）
- 写入文件顶部，正文不动
"""
import os, re, sys
from pathlib import Path

KD = sys.argv[1] if len(sys.argv) > 1 else "data/高顿/CPA/课程库/【26考季】VIPCPA系列-税法（蔡俊峻老师）/知识详解"
STALE_AFTER = "2027-03-31T23:59:59+08:00"
GENERATED_AT = "2026-09-08T00:00:00+08:00"


def yaml_str(s):
    """YAML 字符串值：加双引号，转义内部双引号和反斜杠。"""
    if s is None:
        return '""'
    s = str(s).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'


def parse_context_block(text):
    """解析文件顶部的 > 引用块，返回 {字段名: 值}。"""
    fields = {}
    for line in text.split('\n'):
        if line.startswith('> '):
            content = line[2:].strip()
            m = re.match(r'^([^：:]+)[：:]\s*(.*)$', content)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                fields[key] = val
        elif line.startswith('#') or line.strip() == '---':
            if fields:
                break
        elif line.strip() and not line.startswith('>'):
            if fields:
                break
    return fields


def extract_question_count(text, fields):
    """提取题量：知识点篇'题 N 道'，章 README'题量[：:] N 题次'（冒号可选，兼容两种格式）。"""
    # 章 README：从全文匹配，兼容"题量：348 题次"和"题量 183 题次"
    m = re.search(r'题量[：:]?\s*(\d+)\s*题次', text)
    if m:
        return int(m.group(1))
    # 知识点篇：从来源字段匹配"题 N 道"
    src = fields.get('来源', '')
    m = re.search(r'题\s*(\d+)\s*道', src)
    if m:
        return int(m.group(1))
    return None


def extract_point_count(text, fields):
    """章 README：从全文匹配'覆盖知识点 N 个'或'本组覆盖知识点 N 个'。"""
    m = re.search(r'(?:本组)?覆盖知识点\s*(\d+)\s*个', text)
    if m:
        return int(m.group(1))
    return None


def extract_chapter(fields, filepath):
    """从所属组或路径提取章名（如 01_税法总论）。"""
    if '所属组' in fields:
        return fields['所属组'].strip()
    parts = Path(filepath).parts
    for p in parts:
        if re.match(r'^\d{2}_', p):
            return p
    return None


def extract_paper_ids(text):
    """从正文提取所有 paperId，去重排序。"""
    return sorted(set(re.findall(r'paperId\s+(\d+)', text)))


def extract_lecture_title(fields):
    """从来源字段提取讲义标题。"""
    src = fields.get('来源', '')
    m = re.search(r'讲义[《<](.+?)[》>]', src)
    if m:
        name = m.group(1)
        m2 = re.search(r'第([一二三四五六七八九十百千\d]+[节章节篇部课]+(?:[、,，和与及至到\-—][一二三四五六七八九十百千\d]+[节章节篇部课]+)*)', src)
        if m2:
            return f'讲义《{name}》{m2.group(0)}'
        return f'讲义《{name}》'
    # 章 README 格式："讲义 1 份（精讲XX-YY，覆盖全部 Z 节）"
    m = re.search(r'讲义\s*\d+\s*份[（(]([^)）]+)[)）]', src)
    if m:
        return f'讲义 {m.group(1)}'
    if src:
        return src[:80]
    return None


def determine_type(filepath):
    """判断文件类型。"""
    basename = os.path.basename(filepath)
    parent = os.path.basename(os.path.dirname(filepath))
    if basename == 'README.md':
        return 'ChapterIndex'
    if parent == '知识详解':
        return 'Reference'
    return 'KnowledgePoint'


def build_frontmatter(filepath, title, text, fields):
    """生成 frontmatter YAML 字符串。"""
    ftype = determine_type(filepath)
    chapter = extract_chapter(fields, filepath)
    qcount = extract_question_count(text, fields)
    pcount = extract_point_count(text, fields)
    paper_ids = extract_paper_ids(text)
    lecture_title = extract_lecture_title(fields)

    # description
    if ftype == 'ChapterIndex':
        parts = [title]
        if pcount:
            parts.append(f'{pcount}个知识点')
        if qcount:
            parts.append(f'{qcount}题次')
        description = '，'.join(parts)
    elif ftype == 'Reference':
        description = fields.get('定位', fields.get('说明', title))
        if len(description) > 120:
            description = description[:117] + '...'
    else:  # KnowledgePoint
        desc = f'{chapter}知识点：{title}' if chapter else title
        if qcount:
            desc += f'（{qcount}题）'
        description = desc

    # tags
    tags = ['cpa', 'tax-law', '26-season']
    if chapter:
        m = re.match(r'^(\d{2})', chapter)
        if m:
            tags.append(f'chapter-{m.group(1)}')
    if ftype == 'Reference':
        tags.append('global-reference')

    # sources
    sources = []
    if lecture_title:
        sources.append({'id': 'lecture', 'resource': '原始资源/notes/', 'title': lecture_title})
    elif ftype == 'Reference' and '来源' in fields:
        sources.append({'id': 'source-all', 'resource': '综合来源', 'title': fields['来源'][:80]})
    for pid in paper_ids:
        sources.append({'id': f'paper-{pid}', 'resource': f'paperId {pid}'})

    # 构建 YAML
    lines = ['---']
    lines.append(f'type: {ftype}')
    lines.append(f'title: {yaml_str(title)}')
    lines.append(f'description: {yaml_str(description)}')
    lines.append(f'tags: [{", ".join(tags)}]')

    if sources:
        lines.append('sources:')
        for s in sources:
            lines.append(f'  - id: {s["id"]}')
            lines.append(f'    resource: {yaml_str(s["resource"])}')
            if 'title' in s:
                lines.append(f'    title: {yaml_str(s["title"])}')

    lines.append(f'generated: {{ by: process:knowledge-build, at: {GENERATED_AT} }}')
    lines.append('status: stable')
    lines.append(f'stale_after: {STALE_AFTER}')

    if chapter and ftype != 'Reference':
        lines.append(f'chapter: {chapter}')
    lines.append('exam_season: 2026')
    if qcount is not None:
        lines.append(f'question_count: {qcount}')
    if pcount is not None:
        lines.append(f'point_count: {pcount}')
    if ftype == 'Reference':
        lines.append('scope: global')

    lines.append('---')
    return '\n'.join(lines)


def process_file(filepath):
    """处理单个文件，返回 (status, detail)。"""
    with open(filepath, encoding='utf-8') as f:
        text = f.read()

    if text.startswith('---'):
        return ('skipped', '已有 frontmatter')

    m = re.match(r'^#\s+(.+)$', text, re.M)
    title = m.group(1).strip() if m else os.path.basename(filepath)[:-3]

    fields = parse_context_block(text)
    fm = build_frontmatter(filepath, title, text, fields)

    new_text = fm + '\n\n' + text
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_text)

    ftype = determine_type(filepath)
    return ('ok', f'{ftype} q={extract_question_count(text, fields)} papers={len(extract_paper_ids(text))}')


def main():
    kd = Path(KD)
    if not kd.exists():
        print(f'[FAIL] 知识详解目录不存在: {kd}', file=sys.stderr)
        sys.exit(1)

    files = []
    files.extend(sorted(kd.glob('*.md')))  # 全局篇
    for group in sorted(kd.iterdir()):
        if group.is_dir():
            files.extend(sorted(group.glob('*.md')))

    print(f'共 {len(files)} 篇文件')
    stats = {'ok': 0, 'skipped': 0, 'failed': 0}
    type_count = {}
    failures = []

    for i, fp in enumerate(files, 1):
        try:
            status, detail = process_file(str(fp))
            stats[status] += 1
            if status == 'ok':
                ftype = detail.split()[0]
                type_count[ftype] = type_count.get(ftype, 0) + 1
            print(f'[{i:3d}/{len(files)}] {status:7s} {detail:40s} {fp.name}')
        except Exception as e:
            stats['failed'] += 1
            failures.append((str(fp), str(e)))
            print(f'[{i:3d}/{len(files)}] FAIL    {fp.name}: {e}')

    print(f'\n===== 汇总 =====')
    print(f'ok={stats["ok"]}  skipped={stats["skipped"]}  failed={stats["failed"]}')
    print(f'类型分布: {type_count}')
    if failures:
        print('失败列表:')
        for f, e in failures:
            print(f'  {f}: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
