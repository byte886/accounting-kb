#!/usr/bin/env python3
"""
章节点质量修复脚本
修复两类问题：
1. 概述模板化：从知识点列表提取核心内容，生成具体概述
2. 重点内容是知识点摘要：从摘要提取核心考点，重新组织为简洁重点内容

用法：python3 fix_chapter_quality.py <知识详解目录>
"""

import os
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


def extract_section(body, title_pattern):
    pattern = rf'^## (?:[一二三四五六七八九十]+、)?{title_pattern}\s*$'
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return None, -1, -1
    start = match.start()
    next_match = re.search(r'^## ', body[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(body)
    return body[start:end], start, end


def extract_kp_from_table(kp_content):
    """从知识点列表表格中提取知识点名称和核心内容"""
    kps = []
    # 匹配表格行：| 序号 | 知识点 | ... | 核心内容 |
    lines = kp_content.split('\n')
    for line in lines:
        if line.startswith('|') and not line.startswith('|---') and not line.startswith('| 序号') and not line.startswith('|编号'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 3:
                # 提取知识点名称（去掉markdown链接）
                name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cells[1])
                # 提取核心内容（最后一列）
                core = cells[-1] if len(cells) > 2 else ''
                if name and len(name) > 2:
                    kps.append((name, core[:80]))
    return kps


def fix_template_overview(body, chapter_name):
    """修复模板化概述：从知识点列表生成具体概述"""
    kp_sec, _, _ = extract_section(body, r'知识点列表.*')
    if not kp_sec:
        return None
    kp_content = re.sub(r'^## .*\n', '', kp_sec).strip()
    kps = extract_kp_from_table(kp_content)
    
    if not kps:
        return None
    
    # 生成具体概述
    kp_names = [k[0] for k in kps[:5]]
    kp_list_str = '、'.join(kp_names)
    if len(kps) > 5:
        kp_list_str += f'等{len(kps)}个知识点'
    
    # 根据科目类型生成不同的概述模板
    overview = f"本章围绕{chapter_name}展开，共包含{len(kps)}个核心知识点，主要涵盖{kp_list_str}。本章知识点体系完整，既有理论框架又有实务应用，在CPA考试中具有重要地位。"
    
    return overview


def fix_key_points_from_summary(body):
    """修复重点内容是知识点摘要的问题：从摘要提取核心考点"""
    key_sec, key_start, key_end = extract_section(body, r'重点内容')
    if not key_sec:
        return None
    
    key_text = re.sub(r'^## .*\n', '', key_sec).strip()
    
    # 检查是否是知识点摘要格式（以数字+知识点ID开头）
    if not re.search(r'^\d+\.\s+\*\*\d{4}', key_text, re.MULTILINE):
        return None
    
    # 提取每个知识点的核心要点
    points = []
    blocks = re.split(r'^\d+\.\s+\*\*', key_text, flags=re.MULTILINE)
    for block in blocks[1:]:
        # 提取知识点名称
        title_match = re.match(r'([^*]+)\*\*[：:]\s*(.+)', block, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            content = title_match.group(2).strip()
            # 提取第一句话作为核心要点
            first_sentence = re.split(r'[；;。\n]', content)[0].strip()
            if len(first_sentence) > 10:
                # 清理粗体标记
                first_sentence = re.sub(r'\*\*(.+?)\*\*', r'\1', first_sentence)
                points.append(f"**{title}**：{first_sentence[:80]}")
    
    if len(points) < 3:
        return None
    
    # 重新组织重点内容
    new_key_text = '\n'.join([f'{i+1}. {p}' for i, p in enumerate(points[:7])])
    return new_key_text


def fix_chapter(readme_path, chapter_dir_name=None):
    """修复单个章节点的质量问题"""
    content = read_file(readme_path)
    fm, body = split_frontmatter_and_body(content)
    
    issues = []
    new_body = body
    
    # 提取章节名：优先从目录名提取，其次从frontmatter，最后从正文标题
    chapter_name = None
    if chapter_dir_name:
        # 目录名格式：19_审计报告
        match = re.match(r'^\d+_(.+)$', chapter_dir_name)
        if match:
            chapter_name = match.group(1)
    
    if not chapter_name:
        # 从frontmatter提取
        fm_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        if fm_match:
            chapter_name = fm_match.group(1)
            chapter_name = re.sub(r'^第\d+章\s*', '', chapter_name)
    
    if not chapter_name:
        # 从正文标题提取
        title_match = re.search(r'^# (.+)$', body, re.MULTILINE)
        if title_match:
            chapter_name = title_match.group(1).strip()
            chapter_name = re.sub(r'^第\d+章\s*', '', chapter_name)
    
    if not chapter_name:
        chapter_name = '本章'
    
    # 检查并修复模板化概述
    overview_sec, _, _ = extract_section(new_body, r'本章概述')
    if overview_sec and '本章是CPA考试的重要章节' in overview_sec:
        new_overview = fix_template_overview(new_body, chapter_name)
        if new_overview:
            # 用正则替换整个概述section
            pattern = r'(## 本章概述\s*\n).*?(?=\n## 知识点列表|\Z)'
            replacement = r'\1' + new_overview + '\n\n'
            new_body2 = re.sub(pattern, replacement, new_body, flags=re.DOTALL)
            if new_body2 != new_body:
                new_body = new_body2
                issues.append('概述已修复')
    
    # 检查并修复重点内容是知识点摘要
    new_key = fix_key_points_from_summary(new_body)
    if new_key:
        # 用正则替换整个重点内容section
        pattern = r'(## 重点内容\s*\n).*?(?=\n## 学习建议|\Z)'
        replacement = r'\1' + new_key + '\n\n'
        new_body2 = re.sub(pattern, replacement, new_body, flags=re.DOTALL)
        if new_body2 != new_body:
            new_body = new_body2
            issues.append('重点内容已修复')
    
    if issues:
        write_file(readme_path, fm + '\n' + new_body + '\n')
        return issues
    
    return None


def main():
    if len(sys.argv) < 2:
        print("用法：python3 fix_chapter_quality.py <知识详解目录>")
        sys.exit(1)
    
    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"目录不存在：{base_dir}")
        sys.exit(1)
    
    fixed = 0
    total = 0
    
    for chapter_dir in sorted(base_dir.iterdir()):
        if not chapter_dir.is_dir():
            continue
        if not re.match(r'^\d+_', chapter_dir.name):
            continue
        readme = chapter_dir / 'README.md'
        if not readme.exists():
            continue
        
        total += 1
        issues = fix_chapter(readme, chapter_dir.name)
        if issues:
            fixed += 1
            print(f"  ✅ {chapter_dir.name}: {', '.join(issues)}")
    
    print(f"\n统计：共检查{total}个章节点，修复{fixed}个")


if __name__ == '__main__':
    main()
