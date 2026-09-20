#!/usr/bin/env python3
"""
把"半新半旧"格式的章节点转换为方案D格式：
- 本章概述中包含"本章核心考点"列表 → 拆出来作为独立的"重点内容"章节
- 概述只保留前面的段落（不含核心考点）
- 知识点列表表格保持不变
- 学习建议保持不变

适用场景：正课会计、名师课六科的章节点（本章概述含核心考点+知识点列表表格+学习建议）

用法：python3 extract_key_points_to_section.py <知识详解目录>
"""

import os
import sys
import re
import glob


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

    # 检查是否已经有独立的"重点内容"章节
    if re.search(r'^## 重点内容', body, re.MULTILINE):
        return False  # 已经有重点内容章节，无需转换

    # 找到"本章概述"章节，提取"本章核心考点"列表
    lines = body.split('\n')
    new_lines = []
    in_overview = False
    in_key_points = False
    key_points_lines = []
    overview_paragraphs = []
    found_key_points = False

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.strip() == '## 本章概述':
            in_overview = True
            new_lines.append(line)
            i += 1
            continue

        if in_overview:
            if line.startswith('## '):
                # 遇到下一个章节，结束概述
                in_overview = False
                # 如果找到了核心考点，先添加概述段落，再添加重点内容章节
                if found_key_points and key_points_lines:
                    # 概述段落已经添加了
                    new_lines.append('')  # 空行
                    new_lines.append('## 重点内容')
                    new_lines.append('')
                    # 把核心考点列表添加到重点内容章节
                    for kp_line in key_points_lines:
                        new_lines.append(kp_line)
                    new_lines.append('')  # 空行
                new_lines.append(line)
            elif re.match(r'^\*\*本章核心考点[：:]\*\*', line.strip()) or re.match(r'^本章核心考点[：:]', line.strip()):
                # 找到"本章核心考点"标题
                in_key_points = True
                found_key_points = True
                # 不添加这一行到概述中
            elif in_key_points:
                if line.strip() == '' or line.strip() == '---':
                    # 核心考点列表结束（遇到空行或分隔线）
                    in_key_points = False
                    # 不添加空行或分隔线到概述中
                elif re.match(r'^\d+\.\s', line.strip()) or re.match(r'^-\s', line.strip()):
                    # 核心考点列表项
                    key_points_lines.append(line)
                else:
                    # 其他内容，可能是列表项的延续
                    key_points_lines.append(line)
            else:
                # 概述的普通段落
                new_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    # 处理文件末尾的概述（如果文件在概述章节结束）
    if in_overview and found_key_points and key_points_lines:
        new_lines.append('')  # 空行
        new_lines.append('## 重点内容')
        new_lines.append('')
        for kp_line in key_points_lines:
            new_lines.append(kp_line)

    body = '\n'.join(new_lines)

    # 检查是否有变化
    if body == original_body or not found_key_points:
        return False

    # 保存文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body)

    return True


def main():
    if len(sys.argv) < 2:
        print('用法：python3 extract_key_points_to_section.py <知识详解目录>')
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
            print(f'  ⏭️  {chapter_name}（无变化或已有重点内容章节）')

    print(f'\n完成：转换 {converted}/{len(chapter_readmes)} 个章节点')


if __name__ == '__main__':
    main()
