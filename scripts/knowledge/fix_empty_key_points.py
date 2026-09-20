#!/usr/bin/env python3
"""
自动修复重点内容为空的章节。
从知识点description中提取核心要点，生成重点内容。
"""
import os
import re
import sys
from pathlib import Path

REPO = "/Users/wenjiechen/Desktop/gaodun-course-knowledge-base"

# 需要修复的章节列表
CHAPTERS_TO_FIX = [
    # 会计
    ("会计", "30_每股收益"),
    ("会计", "31_公允价值计量"),
    ("会计", "32_政府及民间非营利组织会计"),
    # 经济法
    ("经济法", "01_法律基本原理"),
    ("经济法", "02_基本民事法律制度"),
    ("经济法", "03_物权法律制度"),
    ("经济法", "04_合同法律制度"),
    ("经济法", "05_合伙企业法律制度"),
    ("经济法", "06_公司法律制度"),
    ("经济法", "07_证券法律制度"),
    ("经济法", "08_企业破产法律制度"),
    ("经济法", "09_票据与支付结算法律制度"),
    ("经济法", "10_企业国有资产法律制度"),
    # 税法
    ("税法", "13_税收征收管理法"),
    ("税法", "14_税务行政法制"),
]


def extract_key_points_from_description(description: str) -> list:
    """从description中提取核心要点"""
    # 查找"核心要点："后面的内容
    match = re.search(r"核心要点[：:](.+?)(?:。|$)", description)
    if not match:
        return []

    points_text = match.group(1)
    # 按顿号、逗号、分号分割
    points = re.split(r"[、，,；;]", points_text)
    # 过滤空字符串和太短的
    points = [p.strip() for p in points if len(p.strip()) > 2]
    return points[:7]  # 最多7条


def generate_key_points(chapter_dir: Path) -> str:
    """生成重点内容"""
    # 读取所有知识点文件的description
    all_points = []
    knowledge_files = sorted([f for f in chapter_dir.glob("*.md") if f.name != "README.md"])

    for kf in knowledge_files:
        with open(kf, 'r', encoding='utf-8') as f:
            content = f.read()
        # 提取description
        desc_match = re.search(r'^description:\s*(.+)$', content, re.MULTILINE)
        if desc_match:
            points = extract_key_points_from_description(desc_match.group(1))
            all_points.extend(points)

    # 去重
    seen = set()
    unique_points = []
    for p in all_points:
        if p not in seen:
            seen.add(p)
            unique_points.append(p)

    # 取前5-7条
    selected = unique_points[:6]

    # 生成重点内容
    result = "## 重点内容\n\n"
    for i, point in enumerate(selected, 1):
        # 尝试给每条要点加一个粗体标题（取前10个字）
        title = point[:15] + "..." if len(point) > 15 else point
        result += f"{i}. **{title}**：{point}\n"

    return result + "\n"


def fix_chapter(course: str, chapter: str):
    """修复单个章节"""
    chapter_dir = Path(REPO) / f"data/高顿/CPA/【VIPCPA专享】名师专业课-{course}/知识详解/{chapter}"
    readme_path = chapter_dir / "README.md"

    if not readme_path.exists():
        print(f"  ⚠️ README不存在: {readme_path}")
        return False

    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查重点内容是否为空
    if "## 重点内容" not in content:
        print(f"  ⚠️ 没有重点内容章节: {chapter}")
        return False

    # 提取重点内容部分
    kp_match = re.search(r"(## 重点内容\s*\n)(.*?)(\n## 学习建议)", content, re.DOTALL)
    if not kp_match:
        print(f"  ⚠️ 无法匹配重点内容: {chapter}")
        return False

    kp_content = kp_match.group(2).strip()
    if kp_content:
        print(f"  ℹ️ 重点内容非空，跳过: {chapter}")
        return False

    # 生成新的重点内容
    new_kp = generate_key_points(chapter_dir)

    # 替换
    new_content = content[:kp_match.start(2)] + "\n" + new_kp.split("\n", 1)[1] + content[kp_match.end(2):]

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✅ 已修复: {chapter}")
    return True


def main():
    print("=" * 60)
    print("自动修复重点内容为空的章节")
    print("=" * 60)
    print()

    fixed_count = 0
    for course, chapter in CHAPTERS_TO_FIX:
        print(f"【{course}】{chapter}")
        if fix_chapter(course, chapter):
            fixed_count += 1

    print()
    print("=" * 60)
    print(f"修复完成: {fixed_count}/{len(CHAPTERS_TO_FIX)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
