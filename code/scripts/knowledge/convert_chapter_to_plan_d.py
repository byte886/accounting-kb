#!/usr/bin/env python3
"""
把章节点从旧格式转换为方案D格式：
- "本组主线" → "本章概述"
- "知识点目录（列表）" → "知识点列表（表格）"
- 学习建议无序列表 → 有序列表
- 导航说明中的"知识点目录" → "知识点列表"

用法：python3 convert_chapter_to_plan_d.py <知识详解目录>
"""

import os
import sys
import re
import glob


def convert_list_to_table(lines):
    """把知识点目录的列表形式转换成表格形式"""
    table_lines = []
    table_lines.append('| 序号 | 知识点 | 核心内容 |')
    table_lines.append('|------|--------|----------|')

    idx = 1
    for line in lines:
        # 匹配 "- [标题](链接) — 摘要" 格式
        m = re.match(r'^-\s+\[(.+?)\]\((.+?)\)\s+[—-]\s+(.+)$', line.strip())
        if m:
            title, link, summary = m.groups()
            table_lines.append(f'| {idx} | [{title}]({link}) | {summary} |')
            idx += 1
        else:
            # 无法解析的行，原样保留
            table_lines.append(line)

    return table_lines


def convert_file(filepath):
    """转换单个章节点文件"""
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # 分离frontmatter和正文
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            frontmatter = content[:end+3]
            body = content[end+3:]
        else:
            frontmatter = ''
            body = content
    else:
        frontmatter = ''
        body = content

    original_body = body

    # 1. 替换标题："## 本组主线" → "## 本章概述"
    body = body.replace('## 本组主线', '## 本章概述')

    # 2. 替换导航说明中的"知识点目录" → "知识点列表"
    body = body.replace('「知识点目录」', '「知识点列表」')

    # 3. 找到"知识点目录"章节，转换成表格
    lines = body.split('\n')
    new_lines = []
    in_knowledge_section = False
    knowledge_list_lines = []
    section_started = False

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.strip() == '## 知识点目录':
            # 替换标题
            new_lines.append('## 知识点列表')
            in_knowledge_section = True
            knowledge_list_lines = []
            section_started = False
            i += 1
            continue

        if in_knowledge_section:
            if line.startswith('## ') and line.strip() != '## 知识点列表':
                # 遇到下一个章节，结束知识点列表转换
                in_knowledge_section = False
                if knowledge_list_lines:
                    table = convert_list_to_table(knowledge_list_lines)
                    new_lines.extend(table)
                    new_lines.append('')  # 空行
                new_lines.append(line)
            elif line.strip().startswith('- ['):
                # 列表项
                knowledge_list_lines.append(line)
                section_started = True
            elif section_started and line.strip() == '':
                # 列表后的空行，先收集，等遇到下一个章节再处理
                knowledge_list_lines.append(line)
            elif not section_started:
                # 列表开始前的注释或空行
                new_lines.append(line)
            else:
                # 其他内容
                knowledge_list_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    # 处理文件末尾的知识点列表
    if in_knowledge_section and knowledge_list_lines:
        table = convert_list_to_table(knowledge_list_lines)
        new_lines.extend(table)

    body = '\n'.join(new_lines)

    # 4. 学习建议无序列表 → 有序列表
    # 找到"学习建议"章节
    lines = body.split('\n')
    new_lines = []
    in_study_section = False
    idx = 1

    for line in lines:
        if line.strip() == '## 学习建议':
            in_study_section = True
            idx = 1
            new_lines.append(line)
            continue

        if in_study_section:
            if line.startswith('## '):
                in_study_section = False
                new_lines.append(line)
            elif line.strip().startswith('- '):
                # 无序列表 → 有序列表
                content = line.strip()[2:]
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + f'{idx}. {content}')
                idx += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    body = '\n'.join(new_lines)

    # 检查是否有变化
    if body == original_body:
        return False

    # 保存文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body)

    return True


def main():
    if len(sys.argv) < 2:
        print('用法：python3 convert_chapter_to_plan_d.py <知识详解目录>')
        sys.exit(1)

    knowledge_dir = sys.argv[1]

    # 查找所有章节点的README.md
    chapter_readmes = glob.glob(os.path.join(knowledge_dir, '*', 'README.md'))
    # 只处理以数字开头的章节点
    chapter_readmes = [f for f in chapter_readmes if re.match(r'^\d+_', os.path.basename(os.path.dirname(f)))]

    print(f'找到 {len(chapter_readmes)} 个章节点')

    converted = 0
    for readme in sorted(chapter_readmes):
        chapter_name = os.path.basename(os.path.dirname(readme))
        if convert_file(readme):
            print(f'  ✅ {chapter_name}')
            converted += 1
        else:
            print(f'  ⏭️  {chapter_name}（无变化）')

    print(f'\n完成：转换 {converted}/{len(chapter_readmes)} 个章节点')


if __name__ == '__main__':
    main()
