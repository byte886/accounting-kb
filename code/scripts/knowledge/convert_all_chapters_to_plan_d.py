#!/usr/bin/env python3
"""
全面章节点格式转换脚本 — 统一为方案D格式
方案D标准：本章概述 → 知识点列表（表格） → 重点内容 → 学习建议

支持的输入格式：
- 格式A：本章概述(含编号核心考点) + 知识点列表 + 学习建议 → 拆出重点内容
- 格式B：本章考情 + 教材结构 + 新教材变化 + 知识点列表 + 知识点摘要 + 本章小结 → 重组
- 格式C：知识点清单 + 本章重点 → 补概述和学习建议
- 格式D：知识点清单 + 本章框架 + 考试指导 → 重组
- 格式E：章节概览 + 知识点列表 + 核心考点 + 考试地位 → 重组
- 格式F：其他变体 → 尽量转换

用法：python3 convert_all_chapters_to_plan_d.py <知识详解目录>
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
    """分离 frontmatter 和正文"""
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            fm = content[:end+3]
            body = content[end+3:]
            return fm, body
    return '', content


def extract_section(body, title_pattern):
    """提取指定标题的章节内容，返回 (内容, 起始位置, 结束位置)
    支持带序号的标题，如"一、本章考情"
    """
    # 自动添加序号前缀匹配
    if not title_pattern.startswith('(?:'):
        pattern = rf'^## (?:[一二三四五六七八九十]+、)?{title_pattern}\s*$'
    else:
        pattern = rf'^## {title_pattern}\s*$'
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return None, -1, -1
    start = match.start()
    # 找到下一个 ## 标题
    next_match = re.search(r'^## ', body[match.end():], re.MULTILINE)
    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(body)
    section = body[start:end]
    return section, start, end


def extract_numbered_points(text):
    """从文本中提取编号的要点（1. 2. 3. 或 - ）"""
    points = []
    # 匹配 1. xxx 或 1、xxx 或 (1) xxx
    pattern = r'^\s*(?:\d+[.、\)]|\(\d+\)|[-*])\s+(.+?)(?=\n\s*(?:\d+[.、\)]|\(\d+\)|[-*])\s|\n## |\Z)'
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    for m in matches:
        m = m.strip()
        if m and len(m) > 5:
            points.append(m)
    return points


def convert_format_a(body):
    """格式A：概述含编号核心考点 + 知识点列表 + 学习建议"""
    # 提取概述
    overview_sec, _, overview_end = extract_section(body, r'本章概述')
    if not overview_sec:
        return None
    
    # 提取概述中的编号要点
    overview_text = overview_sec.replace('## 本章概述\n', '')
    points = extract_numbered_points(overview_text)
    
    if len(points) < 2:
        return None  # 没有足够的核心考点
    
    # 提取概述的纯文本部分（第一段，不含编号要点）
    first_para_match = re.match(r'^(.*?)(?=\n\s*\d+[.、\)]|\n---|\Z)', overview_text, re.DOTALL)
    overview_para = first_para_match.group(1).strip() if first_para_match else overview_text.strip()
    
    # 提取知识点列表
    kp_sec, kp_start, kp_end = extract_section(body, r'知识点列表')
    kp_content = kp_sec if kp_sec else ''
    
    # 提取学习建议
    advice_sec, _, _ = extract_section(body, r'学习建议')
    advice_content = advice_sec if advice_sec else '## 学习建议\n\n- 结合资产生命周期理解各环节处理\n- 重点掌握折旧计算和后续支出资本化判断\n- 注意与所得税、租赁等章节的关联\n'
    
    # 构建新内容
    key_points_text = '\n'.join([f'{i+1}. **{p.split("：")[0] if "：" in p else p[:20]}**：{p}' for i, p in enumerate(points)])
    
    new_body = f"""## 本章概述

{overview_para}

## 知识点列表

{kp_content.replace('## 知识点列表\n', '').strip() if kp_content else ''}

## 重点内容

{key_points_text}

{advice_content}
"""
    return new_body.strip()


def convert_format_c(body):
    """格式C：知识点清单 + 本章重点"""
    # 提取知识点清单
    kp_sec, _, _ = extract_section(body, r'知识点清单')
    if not kp_sec:
        return None
    kp_table = kp_sec.replace('## 知识点清单\n', '').strip()
    
    # 提取本章重点
    key_sec, _, _ = extract_section(body, r'本章重点')
    key_content = key_sec.replace('## 本章重点\n', '').strip() if key_sec else ''
    
    # 提取标题中的章节名
    title_match = re.search(r'^# (.+)$', body, re.MULTILINE)
    chapter_name = title_match.group(1) if title_match else '本章'
    
    # 生成概述和学习建议
    overview = f"本章是CPA考试的重要章节，围绕{chapter_name}的核心概念、处理流程和关键判断展开，知识点之间逻辑关联紧密，客观题与主观题均可能涉及。"
    
    advice = f"""## 学习建议

- 先掌握整体框架，再深入各知识点细节
- 重点关注易混淆概念的辨析
- 结合历年真题理解出题思路
- 注意与前后章节的关联知识点
"""
    
    new_body = f"""## 本章概述

{overview}

## 知识点列表

{kp_table}

## 重点内容

{key_content}

{advice}
"""
    return new_body.strip()


def convert_format_e(body):
    """格式E：章节概览 + 知识点列表 + 核心考点 + 考试地位"""
    # 提取章节概览
    overview_sec, _, _ = extract_section(body, r'章节概览')
    overview_text = overview_sec.replace('## 章节概览\n', '').strip() if overview_sec else ''
    
    # 提取考试地位
    status_sec, _, _ = extract_section(body, r'考试地位')
    status_text = status_sec.replace('## 考试地位\n', '').strip() if status_sec else ''
    
    # 合并概述
    full_overview = overview_text
    if status_text:
        full_overview += f"\n\n**考试地位**：{status_text}"
    
    # 提取知识点列表
    kp_sec, _, _ = extract_section(body, r'知识点列表.*')
    kp_content = kp_sec if kp_sec else ''
    if kp_content:
        # 去掉标题行
        kp_content = re.sub(r'^## 知识点列表.*\n', '', kp_content).strip()
    
    # 提取核心考点
    key_sec, _, _ = extract_section(body, r'核心考点')
    key_content = key_sec.replace('## 核心考点\n', '').strip() if key_sec else ''
    
    # 学习建议
    advice = """## 学习建议

- 先理解章节整体框架，再逐个突破知识点
- 重点掌握核心考点中的计算和判断
- 注意与其他章节的关联
- 多做真题巩固
"""
    
    new_body = f"""## 本章概述

{full_overview}

## 知识点列表

{kp_content}

## 重点内容

{key_content}

{advice}
"""
    return new_body.strip()


def convert_format_tax(body):
    """税法格式：章节概览 + 知识点子页面/索引 + 考试重点 + 本章总结/说明"""
    # 提取章节概览
    gailan_sec, _, _ = extract_section(body, r'章节概览')
    if not gailan_sec:
        return None
    gailan_text = gailan_sec.replace('## 章节概览\n', '').strip()
    
    # 提取概述段落（第一段，到教材结构或新教材变化之前）
    first_para_match = re.match(r'^(.*?)(?=\n\*\*教材结构\*\*|\n\*\*2026|\n---|\Z)', gailan_text, re.DOTALL)
    overview_para = first_para_match.group(1).strip() if first_para_match else gailan_text
    
    # 提取知识点子页面/索引
    kp_sec, _, _ = extract_section(body, r'知识点子页面|知识点索引|知识点列表.*')
    kp_content = ''
    if kp_sec:
        # 去掉标题行
        kp_content = re.sub(r'^## .*\n', '', kp_sec).strip()
    
    # 提取考试重点
    zhongdian_sec, _, _ = extract_section(body, r'考试重点')
    zhongdian_text = zhongdian_sec.replace('## 考试重点\n', '').strip() if zhongdian_sec else ''
    
    # 提取本章总结/说明
    zongjie_sec, _, _ = extract_section(body, r'本章总结|本章小结|说明')
    zongjie_text = ''
    if zongjie_sec:
        zongjie_text = re.sub(r'^## .*\n', '', zongjie_sec).strip()
        zongjie_text = re.sub(r'\n+', '\n', zongjie_text)[:150]
    
    # 学习建议
    advice_items = []
    if zongjie_text:
        # 从总结中提取要点
        points = extract_numbered_points(zongjie_text)
        for p in points[:2]:
            p_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', p)
            advice_items.append(f"- {p_clean}")
    advice_items.extend([
        "- 重点掌握税目、税率和征税环节的判定",
        "- 熟练掌握组价计算和已纳税款扣除",
        "- 注意与增值税的关联和区别",
        "- 多做计算题，提高解题速度",
    ])
    advice_text = '\n'.join(advice_items[:5])
    
    new_body = f"""## 本章概述

{overview_para}

## 知识点列表

{kp_content}

## 重点内容

{zhongdian_text}

## 学习建议

{advice_text}
"""
    return new_body.strip()


def convert_format_d(body):
    """格式D：知识点清单 + 本章框架 + 考试指导"""
    # 提取知识点清单
    kp_sec, _, _ = extract_section(body, r'知识点清单')
    if not kp_sec:
        return None
    kp_table = kp_sec.replace('## 知识点清单\n', '').strip()
    
    # 提取本章框架
    kuangjia_sec, _, _ = extract_section(body, r'本章框架')
    kuangjia_text = kuangjia_sec.replace('## 本章框架\n', '').strip() if kuangjia_sec else ''
    
    # 提取考试指导
    zhidao_sec, _, _ = extract_section(body, r'考试指导')
    zhidao_text = zhidao_sec.replace('## 考试指导\n', '').strip() if zhidao_sec else ''
    
    # 提取章节名
    title_match = re.search(r'^# (.+)$', body, re.MULTILINE)
    chapter_name = title_match.group(1) if title_match else '本章'
    
    # 生成概述
    overview = f"本章围绕{chapter_name}展开，是CPA财管科目的重要组成部分。本章知识点体系完整，既有理论框架又有计算应用，在考试中客观题和主观题均可能涉及。"
    
    # 从本章框架提取重点内容
    key_points = []
    if kuangjia_text:
        # 提取编号要点
        points = extract_numbered_points(kuangjia_text)
        for p in points[:7]:
            # 清理粗体标记
            p_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', p)
            key_points.append(p_clean)
    
    # 如果框架中没有要点，从知识点清单提取核心内容
    if len(key_points) < 3:
        kp_points = re.findall(r'\|\s*\d+\s*\|\s*\[?([^\]|]+)\]?[^\|]*\|([^|]+)\|', kp_table)
        for name, content in kp_points[:5]:
            name = name.strip()
            content = content.strip()[:50]
            if name and content:
                key_points.append(f"**{name}**：{content}")
    
    key_points_text = '\n'.join([f'{i+1}. {p}' for i, p in enumerate(key_points[:7])])
    
    # 学习建议
    advice_items = []
    if zhidao_text:
        advice_points = extract_numbered_points(zhidao_text)
        for p in advice_points[:3]:
            p_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', p)
            advice_items.append(f"- {p_clean}")
    advice_items.extend([
        "- 先掌握整体框架，再深入各知识点计算",
        "- 重点关注公式的理解和应用，不要死记硬背",
        "- 多做计算题，提高解题速度和准确率",
        "- 注意与其他章节的关联知识点",
    ])
    advice_text = '\n'.join(advice_items[:5])
    
    new_body = f"""## 本章概述

{overview}

## 知识点列表

{kp_table}

## 重点内容

{key_points_text}

## 学习建议

{advice_text}
"""
    return new_body.strip()


def convert_format_b(body):
    """格式B：考情格式（本章考情+教材结构+新教材变化+知识点列表+知识点摘要+本章小结）"""
    # 提取本章考情
    kaoqing_sec, _, _ = extract_section(body, r'本章考情')
    if not kaoqing_sec:
        return None
    kaoqing_text = kaoqing_sec.replace('## 本章考情\n', '').strip()
    
    # 提取概述段落（第一段）
    first_para_match = re.match(r'^(.*?)(?=\n-|\n## |\Z)', kaoqing_text, re.DOTALL)
    overview_para = first_para_match.group(1).strip() if first_para_match else kaoqing_text
    
    # 提取学习策略
    strategy_match = re.search(r'\*\*学习策略\*\*[：:]\s*(.+?)(?=\n-|\n## |\Z)', kaoqing_text, re.DOTALL)
    strategy = strategy_match.group(1).strip() if strategy_match else ''
    
    # 提取知识点列表
    kp_sec, _, _ = extract_section(body, r'知识点列表.*')
    kp_content = kp_sec if kp_sec else ''
    if kp_content:
        kp_content = re.sub(r'^## 知识点列表.*\n', '', kp_content).strip()
    
    # 提取知识点摘要，生成重点内容
    zhaiyao_sec, _, _ = extract_section(body, r'知识点摘要')
    key_points = []
    if zhaiyao_sec:
        zhaiyao_text = zhaiyao_sec.replace('## 知识点摘要\n', '')
        # 提取每个 ### 知识点的要点
        kp_blocks = re.split(r'^### ', zhaiyao_text, flags=re.MULTILINE)
        for block in kp_blocks[1:6]:  # 最多取前5个知识点
            lines = block.strip().split('\n')
            title = lines[0].strip()
            # 提取前2-3个要点
            points = []
            for line in lines[1:]:
                point_match = re.match(r'^-\s+(.+)$', line)
                if point_match:
                    p = point_match.group(1).strip()
                    if len(p) > 10:
                        # 截取前50字
                        points.append(p[:60] + '...' if len(p) > 60 else p)
                if len(points) >= 2:
                    break
            if points:
                key_points.append(f"**{title}**：{'；'.join(points)}")
    
    # 如果知识点摘要不够，从教材变化中提取
    if len(key_points) < 3:
        bianhua_sec, _, _ = extract_section(body, r'.*教材变化.*')
        if bianhua_sec:
            bianhua_text = bianhua_sec
            changes = re.findall(r'^\d+\.\s+\*\*(.+?)\*\*[：:]\s*(.+?)(?=\n\d+\.|\n## |\Z)', bianhua_text, re.MULTILINE | re.DOTALL)
            for title, content in changes[:3]:
                key_points.append(f"**{title}**：{content.strip()[:60]}")
    
    key_points_text = '\n'.join([f'{i+1}. {p}' for i, p in enumerate(key_points[:7])])
    
    # 提取本章小结作为学习建议补充
    xiaojie_sec, _, _ = extract_section(body, r'本章小结')
    xiaojie_text = ''
    if xiaojie_sec:
        xiaojie_text = xiaojie_sec.replace('## 本章小结\n', '').strip()
        xiaojie_text = re.sub(r'\n+', '\n', xiaojie_text)[:200]
    
    # 学习建议
    advice_items = []
    if strategy:
        advice_items.append(f"- {strategy}")
    advice_items.extend([
        "- 先掌握基础概念，再深入具体处理",
        "- 重点关注易混淆知识点的辨析",
        "- 结合历年真题理解出题思路",
        "- 注意与前后章节的关联",
    ])
    advice_text = '\n'.join(advice_items[:5])
    
    new_body = f"""## 本章概述

{overview_para}

## 知识点列表

{kp_content}

## 重点内容

{key_points_text}

## 学习建议

{advice_text}
"""
    return new_body.strip()


def detect_format(body):
    """检测章节点的格式类型"""
    has_overview = bool(re.search(r'^## 本章概述', body, re.MULTILINE))
    has_kp_list = bool(re.search(r'^## 知识点列表', body, re.MULTILINE))
    has_advice = bool(re.search(r'^## 学习建议', body, re.MULTILINE))
    has_key_points = bool(re.search(r'^## 重点内容', body, re.MULTILINE))
    has_kaoqing = bool(re.search(r'^## (?:[一二三四五六七八九十]+、)?本章考情', body, re.MULTILINE))
    has_kp_qingdan = bool(re.search(r'^## 知识点清单', body, re.MULTILINE))
    has_benzhang_zhongdian = bool(re.search(r'^## 本章重点', body, re.MULTILINE))
    has_zhangjie_gailan = bool(re.search(r'^## 章节概览', body, re.MULTILINE))
    has_hexin_kaodian = bool(re.search(r'^## 核心考点', body, re.MULTILINE))
    has_kaoshi_diwei = bool(re.search(r'^## 考试地位', body, re.MULTILINE))
    has_benzhang_kuangjia = bool(re.search(r'^## 本章框架', body, re.MULTILINE))
    has_kaoshi_zhidao = bool(re.search(r'^## 考试指导', body, re.MULTILINE))
    has_kaoshi_zhongdian = bool(re.search(r'^## 考试重点', body, re.MULTILINE))
    has_zhishidian_zhaiyao = bool(re.search(r'^## (?:[一二三四五六七八九十]+、)?知识点摘要', body, re.MULTILINE))
    has_benzhang_xiaojie = bool(re.search(r'^## (?:[一二三四五六七八九十]+、)?本章小结', body, re.MULTILINE))
    
    # 方案D标准格式
    if has_overview and has_kp_list and has_key_points and has_advice:
        # 检查顺序
        sections = re.findall(r'^## (.+)$', body, re.MULTILINE)
        expected = ['本章概述', '知识点列表', '重点内容', '学习建议']
        actual = [s for s in sections if s in expected]
        if actual == expected:
            return 'standard'  # 已经是标准格式
        return 'wrong_order'  # 格式对但顺序错
    
    # 格式A：概述+知识点列表+学习建议（缺重点内容）
    if has_overview and has_kp_list and has_advice and not has_key_points:
        return 'format_a'
    
    # 格式C：知识点清单+本章重点
    if has_kp_qingdan and has_benzhang_zhongdian:
        return 'format_c'
    
    # 格式D：知识点清单+本章框架+考试指导
    if has_kp_qingdan and has_benzhang_kuangjia:
        return 'format_d'
    
    # 格式E：章节概览+知识点列表+核心考点+考试地位
    if has_zhangjie_gailan and has_hexin_kaodian:
        return 'format_e'
    
    # 税法格式：章节概览 + 考试重点 + 知识点子页面/索引
    if has_zhangjie_gailan and has_kaoshi_zhongdian:
        return 'format_tax'
    
    # 格式B：考情格式
    if has_kaoqing:
        return 'format_b'
    
    return 'unknown'


def fix_order(body):
    """修正章节顺序为：概述→知识点列表→重点内容→学习建议"""
    sections = {}
    for title in ['本章概述', '知识点列表', '重点内容', '学习建议']:
        sec, _, _ = extract_section(body, title)
        if sec:
            sections[title] = sec
    
    if len(sections) < 4:
        return None
    
    new_body = '\n\n'.join([sections[t].strip() for t in ['本章概述', '知识点列表', '重点内容', '学习建议']])
    return new_body


def convert_chapter(readme_path):
    """转换单个章节点"""
    content = read_file(readme_path)
    fm, body = split_frontmatter_and_body(content)
    
    fmt = detect_format(body)
    
    if fmt == 'standard':
        return 'already_standard', fmt
    
    if fmt == 'wrong_order':
        new_body = fix_order(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'fixed_order', fmt
        return 'failed', fmt
    
    if fmt == 'format_a':
        new_body = convert_format_a(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'skipped', fmt
    
    if fmt == 'format_c':
        new_body = convert_format_c(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'failed', fmt
    
    if fmt == 'format_e':
        new_body = convert_format_e(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'failed', fmt
    
    if fmt == 'format_b':
        new_body = convert_format_b(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'failed', fmt
    
    if fmt == 'format_d':
        new_body = convert_format_d(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'failed', fmt
    
    if fmt == 'format_tax':
        new_body = convert_format_tax(body)
        if new_body:
            write_file(readme_path, fm + '\n' + new_body + '\n')
            return 'converted', fmt
        return 'failed', fmt
    
    # unknown 暂不自动转换，标记为待处理
    return 'pending', fmt


def main():
    if len(sys.argv) < 2:
        print("用法：python3 convert_all_chapters_to_plan_d.py <知识详解目录>")
        sys.exit(1)
    
    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"目录不存在：{base_dir}")
        sys.exit(1)
    
    results = {
        'already_standard': [],
        'fixed_order': [],
        'converted': [],
        'skipped': [],
        'pending': [],
        'failed': [],
    }
    
    # 遍历所有章节目录
    for chapter_dir in sorted(base_dir.iterdir()):
        if not chapter_dir.is_dir():
            continue
        if not re.match(r'^\d+_', chapter_dir.name):
            continue
        readme = chapter_dir / 'README.md'
        if not readme.exists():
            continue
        
        status, fmt = convert_chapter(readme)
        results[status].append((chapter_dir.name, fmt))
        
        symbol = {
            'already_standard': '✅',
            'fixed_order': '🔄',
            'converted': '✅',
            'skipped': '⏭️',
            'pending': '⚠️',
            'failed': '❌',
        }.get(status, '?')
        print(f"  {symbol} {chapter_dir.name} [{fmt}] -> {status}")
    
    print("\n" + "="*60)
    print(f"统计：")
    for status, items in results.items():
        if items:
            print(f"  {status}: {len(items)}")
    total = sum(len(v) for v in results.values())
    converted = len(results['converted']) + len(results['fixed_order'])
    print(f"\n总计：{total} 个章节点，已转换/修正：{converted}，待处理：{len(results['pending'])}")


if __name__ == '__main__':
    main()
