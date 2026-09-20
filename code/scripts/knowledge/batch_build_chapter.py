#!/usr/bin/env python3
"""
章节级批量构建器：一次性处理整个章节的知识详解生成。

功能：
1. list      - 列出章节所有知识点及题目统计
2. template  - 为每个知识点生成头部模板（含从题目提取的考点）
3. assemble  - 批量组装题答（需要AI完善后的头部）
4. frontmatter - 批量加OKF frontmatter
5. verify    - 批量OKF校验
6. readme    - 生成章README
7. all       - 执行 assemble + frontmatter + verify + readme

用法：
  python3 scripts/knowledge/batch_build_chapter.py --profile cpa-accounting-2026 --chapter 16 --stage list
  python3 scripts/knowledge/batch_build_chapter.py --profile cpa-accounting-2026 --chapter 16 --stage template
  python3 scripts/knowledge/batch_build_chapter.py --profile cpa-accounting-2026 --chapter 16 --stage all --heads-dir /tmp/ch16_heads
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "knowledge"))

from course_profile import load_profile  # noqa: E402


def get_chapter_points(profile, chapter_code):
    """获取章节所有知识点的聚合JSON路径"""
    # workspace路径固定为 data/_workspace/<profile_key>
    profile_key = profile.get("key", "")
    ws = PROJECT_ROOT / "data" / "_workspace" / profile_key
    points_dir = ws / "tmp" / "point-questions"
    
    # 从profile structure获取章节信息（章节编号和名称）
    structure = profile.get("structure", {})
    groups = structure.get("groups", [])
    
    chapter = None
    for g in groups:
        if str(g.get("code", "")) == str(chapter_code):
            chapter = g
            break
    
    if not chapter:
        # 尝试按名称匹配
        for g in groups:
            if str(chapter_code) in g.get("name", "") or g.get("name", "").startswith(str(chapter_code)):
                chapter = g
                break
    
    if not chapter:
        print(f"错误：找不到章节 {chapter_code}")
        print("可用章节：")
        for g in groups:
            print(f"  {g.get('code')}: {g.get('name')}")
        sys.exit(1)
    
    # 从course-manifest.json获取知识点信息
    manifest_file = ws / "manifest" / "course-manifest.json"
    if not manifest_file.exists():
        print(f"错误：找不到 manifest 文件 {manifest_file}")
        sys.exit(1)
    
    with open(manifest_file) as f:
        manifest = json.load(f)
    
    knowledge = manifest.get("knowledge", {})
    manifest_groups = knowledge.get("groups", [])
    point_index = knowledge.get("pointIndex", {})
    
    # 找到对应的manifest group（按名称匹配）
    manifest_group = None
    for g in manifest_groups:
        if g.get("name") == chapter.get("name"):
            manifest_group = g
            break
    
    if not manifest_group:
        print(f"错误：在 manifest 中找不到章节 {chapter.get('name')}")
        sys.exit(1)
    
    group_code = manifest_group.get("code")
    point_ids = manifest_group.get("pointIds", [])
    
    # 查找该章节的聚合JSON
    point_files = []
    for point_id in point_ids:
        # 从pointIndex获取知识点名称（title字段）
        point_info = point_index.get(str(point_id), {})
        point_name = point_info.get("title", point_info.get("name", str(point_id)))
        # 查找匹配的JSON文件（格式：G{groupCode}_{pointId}_{name}.json）
        matches = list(points_dir.glob(f"G{group_code}_{point_id}_*.json"))
        if not matches:
            # 尝试不指定groupCode
            matches = list(points_dir.glob(f"*_{point_id}_*.json"))
        if matches:
            point_files.append({
                "id": point_id,
                "name": point_name,
                "file": matches[0],
                "chapter_code": chapter.get("code"),
                "chapter_name": chapter.get("name"),
                "group_code": group_code,
            })
        else:
            print(f"警告：找不到知识点 {point_id} {point_name} 的聚合JSON")
    
    return chapter, point_files


def stage_list(profile, chapter_code):
    """列出章节所有知识点及题目统计"""
    chapter, point_files = get_chapter_points(profile, chapter_code)
    
    print(f"\n=== 章节 {chapter.get('code')}: {chapter.get('name')} ===")
    print(f"知识点数: {len(point_files)}")
    print()
    
    total_questions = 0
    for pf in point_files:
        with open(pf["file"]) as f:
            data = json.load(f)
        count = data.get("count", len(data.get("questions", [])))
        type_dist = data.get("typeDist", {})
        total_questions += count
        
        type_str = ", ".join([f"{k}:{v}" for k, v in type_dist.items()]) if type_dist else ""
        print(f"  {pf['id']} {pf['name']}: {count}题 ({type_str})")
    
    print(f"\n合计: {len(point_files)}个知识点, {total_questions}题")
    return chapter, point_files


def stage_template(profile, chapter_code, output_dir):
    """为每个知识点生成头部模板"""
    chapter, point_files = stage_list(profile, chapter_code)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n=== 生成头部模板到 {output_path} ===")
    
    for pf in point_files:
        with open(pf["file"]) as f:
            data = json.load(f)
        
        questions = data.get("questions", [])
        count = data.get("count", len(questions))
        
        # 从题目中提取考点关键词
        keywords = set()
        for q in questions[:10]:  # 只看前10题
            stem = q.get("stem", "")
            # 提取关键术语（简单的中文名词提取）
            terms = re.findall(r'[\u4e00-\u9fa5]{2,6}', stem)
            for t in terms:
                if len(t) >= 2 and not any(skip in t for skip in ["下列", "关于", "正确", "错误", "说法", "是指", "属于", "包括"]):
                    keywords.add(t)
        
        # 按出现频率排序
        keyword_freq = {}
        for q in questions:
            stem = q.get("stem", "")
            for kw in keywords:
                if kw in stem:
                    keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
        
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:8]
        keyword_str = "、".join([k for k, v in top_keywords])
        
        # 题型分布
        type_dist = data.get("typeDist", {})
        type_str = "、".join([f"{k}({v}题)" for k, v in type_dist.items()])
        
        # 生成头部模板
        template = f"""---
# {pf['name']}

> **Context Block**
> - **章节**：{chapter.get('code')} {chapter.get('name')}
> - **知识点**：{pf['id']} {pf['name']}
> - **题量**：{count}题（{type_str}）
> - **高频考点**：{keyword_str}
> - **来源**：讲义OCR + 题目paperId（见题答解析）

## 一、知识拆解

### 核心概念
（AI补充：本知识点的核心定义、关键术语）

### 关键规则
（AI补充：重要会计处理规则、确认条件、计量方法）

### 易混点辨析
（AI补充：容易混淆的概念对比、常见错误）

## 二、考试指导

### 考频分析
本知识点在考试中出现{count}题，高频考点包括：{keyword_str}。

### 命题规律
（AI补充：常见命题角度、题型分布、难度分析）

### 答题技巧
（AI补充：解题思路、关键步骤、注意事项）

## 三、题答解析

（以下由 assemble_point.py 自动组装）
"""
        
        out_file = output_path / f"{pf['id']}_{pf['name']}.md"
        with open(out_file, "w") as f:
            f.write(template)
        
        print(f"  ✓ {pf['id']} {pf['name']}: {count}题, 关键词{len(top_keywords)}个")
    
    print(f"\n模板已生成到 {output_path}")
    print("下一步：AI审核和完善知识拆解、考试指导内容")
    return chapter, point_files


def stage_assemble(profile, chapter_code, heads_dir):
    """批量组装题答"""
    chapter, point_files = get_chapter_points(profile, chapter_code)
    heads_path = Path(heads_dir)
    
    print(f"\n=== 批量组装题答 ===")
    print(f"头部目录: {heads_path}")
    
    local_root = Path(profile["paths"]["localRoot"])
    course_root = local_root / "知识详解"
    chapter_code = str(chapter.get('code')).zfill(2)
    chapter_dir_name = f"{chapter_code}_{chapter.get('name')}"
    chapter_dir = course_root / chapter_dir_name
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    success = 0
    failed = []
    
    for pf in point_files:
        head_file = heads_path / f"{pf['id']}_{pf['name']}.md"
        if not head_file.exists():
            print(f"  ✗ {pf['id']} {pf['name']}: 找不到头部文件 {head_file}")
            failed.append(pf)
            continue
        
        # 调用assemble_point.py
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "knowledge" / "assemble_point.py"),
            "--src", str(pf["file"]),
            "--head", str(head_file),
            "--course-root", str(local_root),
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✓ {pf['id']} {pf['name']}")
            success += 1
        else:
            print(f"  ✗ {pf['id']} {pf['name']}: {result.stderr[:100]}")
            failed.append(pf)
    
    print(f"\n组装完成: {success}/{len(point_files)} 成功")
    if failed:
        print(f"失败: {len(failed)} 个")
    return chapter, point_files, failed


def stage_frontmatter(profile, chapter_code):
    """批量加OKF frontmatter"""
    chapter, point_files = get_chapter_points(profile, chapter_code)
    
    local_root = Path(profile["paths"]["localRoot"])
    course_root = local_root / "知识详解"
    ch_code = str(chapter.get('code')).zfill(2)
    chapter_dir_name = f"{ch_code}_{chapter.get('name')}"
    chapter_dir = course_root / chapter_dir_name
    
    print(f"\n=== 批量加frontmatter ===")
    print(f"章节目录: {chapter_dir}")
    
    # 查找现有的frontmatter脚本或使用内联方式
    # 这里简化处理，直接为每个文件添加frontmatter
    # 实际项目中应该有专门的frontmatter工具
    
    md_files = list(chapter_dir.glob("*.md"))
    print(f"找到 {len(md_files)} 个md文件")
    
    for md_file in md_files:
        with open(md_file) as f:
            content = f.read()
        
        # 检查是否已有frontmatter
        if content.startswith("---"):
            print(f"  - {md_file.name}: 已有frontmatter，跳过")
            continue
        
        # 从文件名提取信息
        name = md_file.stem
        is_index = md_file.name == "README.md"  # 章目录页=ChapterIndex，其余=KnowledgePoint

        # frontmatter 标准档壳：字段范式见 docs/development/templates/KNOWLEDGE_BASE_TEMPLATE.md
        # 与 AGENTS.md §3.12；这里只补壳，sources 必须由知识生成环节按「lecture 指讲目录 /
        # transcript / paperId」口径填齐、内容定稿后 status 再由 draft 改 stable，不得留空交付。
        pk = profile.get("key", "")
        subject_slug = pk.replace("cpa-", "", 1)
        if subject_slug.endswith("-2026"):
            subject_slug = subject_slug[:-5]
        subject_slug = subject_slug or "cpa"
        now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
        ch_name = chapter.get('name')
        if is_index:
            frontmatter = f"""---
type: ChapterIndex
title: {ch_code}_{ch_name}
description: "{ch_code}_{ch_name} 章目录页（知识点清单 + 考试指导入口）"
tags: [cpa, {subject_slug}, 26-season, chapter-{ch_code}]
sources: []
generated: {{ by: process:knowledge-build, at: "{now_iso}" }}
status: draft
stale_after: 2027-03-31T23:59:59+08:00
chapter: "{ch_code}_{ch_name}"
exam_season: "2026"
---

"""
        else:
            frontmatter = f"""---
type: KnowledgePoint
title: "{name}"
description: "{ch_code}_{ch_name}知识点：{name}"
tags: [cpa, {subject_slug}, 26-season, chapter-{ch_code}]
sources: []
generated: {{ by: process:knowledge-build, at: "{now_iso}" }}
status: draft
stale_after: 2027-03-31T23:59:59+08:00
chapter: "{ch_code}_{ch_name}"
exam_season: "2026"
question_count: 0
---

"""
        
        with open(md_file, "w") as f:
            f.write(frontmatter + content)
        
        print(f"  ✓ {md_file.name}")
    
    print(f"\nfrontmatter添加完成")
    return chapter, point_files


def stage_verify(profile, chapter_code):
    """批量OKF校验"""
    chapter, point_files = get_chapter_points(profile, chapter_code)
    
    local_root = Path(profile["paths"]["localRoot"])
    course_root = local_root / "知识详解"
    ch_code = str(chapter.get('code')).zfill(2)
    chapter_dir_name = f"{ch_code}_{chapter.get('name')}"
    chapter_dir = course_root / chapter_dir_name
    
    print(f"\n=== 批量OKF校验 ===")
    print(f"章节目录: {chapter_dir}")
    
    okf_validate = PROJECT_ROOT / "scripts" / "okf_validate.py"
    if okf_validate.exists():
        cmd = [sys.executable, str(okf_validate), str(chapter_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    else:
        print("警告：找不到 okf_validate.py，跳过校验")
    
    return chapter, point_files


def stage_readme(profile, chapter_code):
    """生成章README"""
    chapter, point_files = get_chapter_points(profile, chapter_code)
    
    local_root = Path(profile["paths"]["localRoot"])
    course_root = local_root / "知识详解"
    ch_code = str(chapter.get('code')).zfill(2)
    chapter_dir_name = f"{ch_code}_{chapter.get('name')}"
    chapter_dir = course_root / chapter_dir_name
    
    print(f"\n=== 生成章README ===")
    
    total_questions = 0
    point_list = []
    for pf in point_files:
        with open(pf["file"]) as f:
            data = json.load(f)
        count = data.get("count", len(data.get("questions", [])))
        total_questions += count
        point_list.append({
            "id": pf["id"],
            "name": pf["name"],
            "count": count,
            "file": f"{pf['id']}_{pf['name']}.md",
        })
    
    # 生成README
    readme = f"""---
type: ChapterIndex
title: "{ch_code} {chapter.get('name')}"
description: "会计{chapter.get('name')}章节知识点详解，共{len(point_files)}个知识点，{total_questions}道题"
tags: ["CPA", "会计", "{chapter.get('name')}", "章节索引"]
generated:
  process: knowledge-build
  at: "{datetime.now().isoformat()}"
status: stable
stale_after: "2027-03-31T23:59:59+08:00"
chapter: "{ch_code}_{chapter.get('name')}"
exam_season: "2026"
point_count: {len(point_files)}
question_count: {total_questions}
---

# {ch_code} {chapter.get('name')}

> 本组覆盖知识点 {len(point_files)} 个 · 题量 {total_questions} 题次

## 知识点列表

"""
    
    for i, p in enumerate(point_list, 1):
        readme += f"{i}. [{p['name']}]({p['file']})（{p['count']}题）\n"
    
    readme += f"""
## 章节概述

（AI补充：本章在CPA会计考试中的地位、重点内容、学习建议）

## 考情分析

- 知识点数：{len(point_files)}
- 题目数：{total_questions}
- 高频考点：（AI补充）

## 学习建议

（AI补充：本章学习方法、重点难点、与其他章节的联系）
"""
    
    readme_file = chapter_dir / "README.md"
    with open(readme_file, "w") as f:
        f.write(readme)
    
    print(f"  ✓ README.md 已生成: {len(point_files)}知识点, {total_questions}题")
    return chapter, point_files


def main():
    parser = argparse.ArgumentParser(description="章节级批量构建器")
    parser.add_argument("--profile", required=True, help="课程profile名称")
    parser.add_argument("--chapter", required=True, help="章节编号（如16）")
    parser.add_argument("--stage", required=True, 
                       choices=["list", "template", "assemble", "frontmatter", "verify", "readme", "all"],
                       help="执行阶段")
    parser.add_argument("--heads-dir", help="头部文件目录（assemble阶段需要）")
    parser.add_argument("--output-dir", help="模板输出目录（template阶段，默认/tmp/ch{chapter}_heads）")
    
    args = parser.parse_args()
    
    # 加载profile
    os.environ["GAODUN_COURSE_PROFILE"] = args.profile
    profile = load_profile()
    
    if args.stage == "list":
        stage_list(profile, args.chapter)
    elif args.stage == "template":
        output_dir = args.output_dir or f"/tmp/ch{args.chapter}_heads"
        stage_template(profile, args.chapter, output_dir)
    elif args.stage == "assemble":
        if not args.heads_dir:
            print("错误：assemble阶段需要 --heads-dir")
            sys.exit(1)
        stage_assemble(profile, args.chapter, args.heads_dir)
    elif args.stage == "frontmatter":
        stage_frontmatter(profile, args.chapter)
    elif args.stage == "verify":
        stage_verify(profile, args.chapter)
    elif args.stage == "readme":
        stage_readme(profile, args.chapter)
    elif args.stage == "all":
        if not args.heads_dir:
            print("错误：all阶段需要 --heads-dir")
            sys.exit(1)
        stage_assemble(profile, args.chapter, args.heads_dir)
        stage_frontmatter(profile, args.chapter)
        stage_verify(profile, args.chapter)
        stage_readme(profile, args.chapter)


if __name__ == "__main__":
    main()
