#!/usr/bin/env python3
"""
将正课会计旧格式章节点README转换为方案D格式。
旧格式：# 标题、> 本组覆盖、## 知识点列表（有序列表）、## 章节概述、## 考情分析、## 学习建议
方案D：## 本章概述、## 知识点列表（表格）、## 重点内容、## 学习建议
"""
import re
import sys
from pathlib import Path


def convert_chapter(readme_path: Path) -> bool:
    """转换单个章节点README为方案D格式"""
    content = readme_path.read_text(encoding='utf-8')
    
    # 分离frontmatter和正文
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter = '---' + parts[1] + '---'
            body = parts[2]
        else:
            return False
    else:
        frontmatter = ''
        body = content
    
    # 提取章节概述
    overview_match = re.search(r'## 章节概述\s*\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    overview = overview_match.group(1).strip() if overview_match else ''
    
    # 提取知识点列表（有序列表）
    points_match = re.search(r'## 知识点列表\s*\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    points_text = points_match.group(1).strip() if points_match else ''
    
    # 解析知识点列表项
    point_items = []
    for line in points_text.split('\n'):
        line = line.strip()
        # 匹配：1. [标题](链接)（X题）
        m = re.match(r'\d+\.\s*\[([^\]]+)\]\(([^)]+)\)\s*（(\d+)题）', line)
        if m:
            point_items.append({
                'title': m.group(1),
                'link': m.group(2),
                'questions': m.group(3)
            })
            continue
        # 匹配：1. [标题](链接)
        m = re.match(r'\d+\.\s*\[([^\]]+)\]\(([^)]+)\)', line)
        if m:
            point_items.append({
                'title': m.group(1),
                'link': m.group(2),
                'questions': ''
            })
    
    # 提取考情分析中的高频考点作为重点内容
    key_points = []
    kp_match = re.search(r'## 考情分析\s*\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    if kp_match:
        kp_text = kp_match.group(1)
        # 提取高频考点列表
        hf_match = re.search(r'高频考点[：:]\s*\n(.*?)(?=\n-|\n## |\Z)', kp_text, re.DOTALL)
        if hf_match:
            hf_text = hf_match.group(1)
            for line in hf_text.split('\n'):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    # 去掉序号
                    kp = re.sub(r'^\d+\.\s*', '', line)
                    if kp:
                        key_points.append(kp)
    
    # 如果没有提取到高频考点，从考情分析中提取其他内容
    if not key_points and kp_match:
        kp_text = kp_match.group(1)
        for line in kp_text.split('\n'):
            line = line.strip()
            if line.startswith('- ') and '知识点数' not in line and '题目数' not in line:
                kp = line[2:].strip()
                if kp:
                    key_points.append(kp)
    
    # 提取学习建议
    advice_match = re.search(r'## 学习建议\s*\n(.*?)(?=\n## |\Z)', body, re.DOTALL)
    advice = advice_match.group(1).strip() if advice_match else ''
    
    # 从知识点文件中提取核心内容（description）
    chapter_dir = readme_path.parent
    point_cores = {}
    for item in point_items:
        point_file = chapter_dir / item['link']
        if point_file.exists():
            point_content = point_file.read_text(encoding='utf-8')
            desc_match = re.search(r'description:\s*["\']?([^"\'\n]+)', point_content)
            if desc_match:
                point_cores[item['title']] = desc_match.group(1).strip()
            else:
                # 从知识拆解中提取第一句话
                kd_match = re.search(r'## 一、知识拆解\s*\n(.*?)(?=\n## |\Z)', point_content, re.DOTALL)
                if kd_match:
                    first_line = kd_match.group(1).strip().split('\n')[0]
                    first_line = re.sub(r'^[#>\-\*\s]+', '', first_line)
                    if first_line:
                        point_cores[item['title']] = first_line[:80]
    
    # 构建新的正文
    new_body = '\n\n'
    
    # 本章概述
    new_body += '## 本章概述\n\n'
    new_body += overview + '\n\n'
    
    # 知识点列表（表格）
    new_body += '## 知识点列表\n\n'
    new_body += '| 序号 | 知识点 | 核心内容 |\n'
    new_body += '|------|--------|----------|\n'
    for i, item in enumerate(point_items, 1):
        core = point_cores.get(item['title'], '')
        if len(core) > 100:
            core = core[:100] + '...'
        new_body += f'| {i} | [{item["title"]}](./{item["link"]}) | {core} |\n'
    new_body += '\n---\n\n'
    
    # 重点内容
    new_body += '## 重点内容\n\n'
    if key_points:
        for i, kp in enumerate(key_points[:7], 1):
            new_body += f'{i}. {kp}\n'
    else:
        # 如果没有提取到高频考点，从知识点中生成
        for i, item in enumerate(point_items[:5], 1):
            core = point_cores.get(item['title'], item['title'])
            if len(core) > 80:
                core = core[:80] + '...'
            new_body += f'{i}. **{item["title"]}**：{core}\n'
    new_body += '\n'
    
    # 学习建议
    new_body += '## 学习建议\n\n'
    new_body += advice + '\n'
    
    # 组合frontmatter和新正文
    new_content = frontmatter + new_body
    
    # 写入文件
    readme_path.write_text(new_content, encoding='utf-8')
    return True


def main():
    if len(sys.argv) < 2:
        print("用法：python3 convert_old_format_to_plan_d.py <章节目录或README文件>")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    if path.is_dir():
        # 转换目录下所有章节点
        count = 0
        for chapter_dir in sorted(path.iterdir()):
            if not chapter_dir.is_dir() or not re.match(r'^\d+_', chapter_dir.name):
                continue
            readme = chapter_dir / 'README.md'
            if readme.exists():
                if convert_chapter(readme):
                    print(f'  ✅ {chapter_dir.name}')
                    count += 1
        print(f'\n共转换 {count} 个章节')
    else:
        # 转换单个文件
        if convert_chapter(path):
            print(f'  ✅ {path.name}')
        else:
            print(f'  ❌ {path.name} 转换失败')


if __name__ == '__main__':
    main()
