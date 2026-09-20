#!/usr/bin/env python3
"""
专门修复之前错误修复的20个章节
1. 概述包含"本章围绕本章展开"的，重新生成正确概述
2. 重点内容是知识点摘要格式的，重新生成简洁重点内容
"""

import re
import sys
from pathlib import Path


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def split_frontmatter_and_body(content):
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            return content[:end+3], content[end+3:]
    return '', content


def extract_kp_names(body):
    """从知识点列表提取知识点名称"""
    # 找到知识点列表section
    match = re.search(r'## 知识点列表.*?\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if not match:
        return []
    table_text = match.group(1)
    names = []
    for line in table_text.split('\n'):
        if line.startswith('|') and not line.startswith('|---') and not line.startswith('| 序号') and not line.startswith('|编号'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 2:
                name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cells[1])
                if name and len(name) > 2 and name != '知识点':
                    names.append(name)
    return names


def fix_overview(body, chapter_name):
    """修复错误概述"""
    kp_names = extract_kp_names(body)
    if not kp_names:
        return None
    
    kp_list_str = '、'.join(kp_names[:4])
    if len(kp_names) > 4:
        kp_list_str += f'等{len(kp_names)}个知识点'
    
    overview = f"本章围绕{chapter_name}展开，共包含{len(kp_names)}个核心知识点，主要涵盖{kp_list_str}。本章知识点体系完整，既有理论框架又有实务应用，在CPA考试中具有重要地位。"
    
    # 替换概述section（用函数避免replacement中的特殊字符被解释）
    pattern = r'(## 本章概述\s*\n).*?(?=\n## 知识点列表|\Z)'
    def replace_overview(m):
        return m.group(1) + overview + '\n\n'
    new_body = re.sub(pattern, replace_overview, body, flags=re.DOTALL)
    return new_body if new_body != body else None


def fix_key_points(body):
    """修复知识点摘要格式的重点内容"""
    # 找到重点内容section
    match = re.search(r'## 重点内容\s*\n(.*?)(?=\n## 学习建议|\Z)', body, re.DOTALL)
    if not match:
        return None
    key_text = match.group(1)
    
    # 检查是否是知识点摘要格式
    if not re.search(r'^\d+\.\s+\*\*\d{4}', key_text, re.MULTILINE):
        return None
    
    # 提取每个知识点的核心要点
    points = []
    blocks = re.split(r'^\d+\.\s+\*\*', key_text, flags=re.MULTILINE)
    for block in blocks[1:]:
        title_match = re.match(r'([^*]+)\*\*[：:]\s*(.+)', block, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            content = title_match.group(2).strip()
            # 提取第一句话
            first_sentence = re.split(r'[；;。\n]', content)[0].strip()
            if len(first_sentence) > 10:
                first_sentence = re.sub(r'\*\*(.+?)\*\*', r'\1', first_sentence)
                points.append(f"**{title}**：{first_sentence[:80]}")
    
    if len(points) < 3:
        return None
    
    new_key_text = '\n'.join([f'{i+1}. {p}' for i, p in enumerate(points[:7])])
    
    # 替换重点内容section（用split和join的方式，更可靠）
    parts = re.split(r'(## 重点内容\s*\n)', body, maxsplit=1)
    if len(parts) < 2:
        return None
    after = parts[2]
    # 找到学习建议section
    advice_match = re.search(r'(\n## 学习建议\s*\n)', after)
    if advice_match:
        after = advice_match.group(1) + after[advice_match.end():]
    else:
        after = '\n\n## 学习建议\n\n' + after
    new_body = parts[0] + parts[1] + new_key_text + '\n\n' + after
    return new_body if new_body != body else None


def main():
    if len(sys.argv) < 2:
        print("用法：python3 fix_broken_chapters.py <知识详解目录>")
        sys.exit(1)
    
    base_dir = Path(sys.argv[1])
    fixed = 0
    
    for chapter_dir in sorted(base_dir.iterdir()):
        if not chapter_dir.is_dir() or not re.match(r'^\d+_', chapter_dir.name):
            continue
        readme = chapter_dir / 'README.md'
        if not readme.exists():
            continue
        
        content = read_file(readme)
        fm, body = split_frontmatter_and_body(content)
        new_body = body
        issues = []
        
        # 提取章节名
        match = re.match(r'^\d+_(.+)$', chapter_dir.name)
        chapter_name = match.group(1) if match else '本章'
        
        # 检查概述是否错误
        if '本章围绕本章展开' in body or '主要涵盖知识点、' in body:
            result = fix_overview(new_body, chapter_name)
            if result:
                new_body = result
                issues.append('概述已修复')
        
        # 检查重点内容是否是知识点摘要（直接检查内容格式）
        key_match = re.search(r'## 重点内容\s*\n(.*?)(?=\n## 学习建议|\Z)', new_body, re.DOTALL)
        if key_match and re.search(r'^\d+\.\s+\*\*\d{4}', key_match.group(1), re.MULTILINE):
            result = fix_key_points(new_body)
            if result:
                new_body = result
                issues.append('重点内容已修复')
        
        if issues:
            write_file(readme, fm + '\n' + new_body + '\n')
            fixed += 1
            print(f"  ✅ {chapter_dir.name}: {', '.join(issues)}")
    
    print(f"\n共修复{fixed}个章节")


if __name__ == '__main__':
    main()
