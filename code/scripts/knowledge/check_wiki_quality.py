#!/usr/bin/env python3
"""
飞书知识库章节点质量批量检查脚本。
检查项：
1. 四个标准章节是否齐全（本章概述/知识点列表/重点内容/学习建议）
2. 重点内容条数（3-7条）
3. 内容非空
4. frontmatter已剥离（不显示---...---）
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LARK_CLI = "/Users/wenjiechen/Library/Application Support/Doubao/Profile 2/sandbox_envs_dir/envs/9cbd27d1-c9f2-42e9-95ab-39d1071b7981/override_dlcs/bin/lark-cli"
REPO = str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent)

# 六科配置
COURSES = [
    {"name": "会计", "profile": "cpa-accounting-2026", "chapters": ["03_总论", "14_金融工具", "29_合并财务报表"]},
    {"name": "审计", "profile": "ep3-audit-2026", "chapters": ["01_审计概述", "19_审计报告", "24_企业可持续信息鉴证"]},
    {"name": "财管", "profile": "ep3-finance-2026", "chapters": ["01_财务管理概述", "08_资本结构", "20_业绩评价"]},
    {"name": "税法", "profile": "cpa-tax-2026", "chapters": ["02_增值税法", "10_房产税·契税·土地增值税", "14_税务行政法制"]},
    {"name": "经济法", "profile": "ep3-econlaw-2026", "chapters": ["01_法律基本原理", "06_企业破产法律制度", "12_涉外经济法律制度"]},
    {"name": "战略", "profile": "ep3-strategy-2026", "chapters": ["01_战略与战略管理", "02_战略分析", "08_企业面对的主要风险与应对"]},
]


def fetch_doc(obj_token: str) -> str:
    """从飞书获取文档内容"""
    proc = subprocess.run(
        [LARK_CLI, "docs", "+fetch", "--doc", obj_token, "--as", "user", "--format", "json"],
        capture_output=True, text=True, cwd=REPO, timeout=30,
    )
    try:
        data = json.loads(proc.stdout)
        return data.get("data", {}).get("document", {}).get("content", "")
    except Exception:
        return ""


def check_chapter(course_name: str, profile: str, chapter: str) -> dict:
    """检查单个章节点的质量"""
    result = {
        "course": course_name,
        "chapter": chapter,
        "has_overview": False,
        "has_points_list": False,
        "has_key_points": False,
        "has_advice": False,
        "key_points_count": 0,
        "content_length": 0,
        "has_frontmatter": False,
        "errors": [],
    }

    # 从wiki_node_map.tsv获取obj_token
    map_file = Path(REPO) / "data/_workspace" / profile / "logs" / "wiki_node_map.tsv"
    if not map_file.exists():
        result["errors"].append(f"wiki_node_map.tsv不存在: {map_file}")
        return result

    obj_token = None
    for line in map_file.read_text(encoding="utf-8").split("\n"):
        cols = line.split("\t")
        if len(cols) >= 3 and cols[0] == chapter:
            obj_token = cols[2]
            break

    if not obj_token:
        result["errors"].append(f"未在wiki_node_map.tsv中找到章节: {chapter}")
        return result

    # 获取飞书端内容
    content = fetch_doc(obj_token)
    if not content:
        result["errors"].append("飞书端内容为空或获取失败")
        return result

    result["content_length"] = len(content)

    # 检查四个标准章节（HTML格式<h2>）
    result["has_overview"] = "<h2>本章概述</h2>" in content
    result["has_points_list"] = "<h2>知识点列表</h2>" in content
    result["has_key_points"] = "<h2>重点内容</h2>" in content
    result["has_advice"] = "<h2>学习建议</h2>" in content

    # 检查frontmatter是否已剥离（飞书端不应显示---...---）
    result["has_frontmatter"] = "---" in content[:200] and "type:" in content[:200]

    # 检查重点内容条数
    if result["has_key_points"]:
        match = re.search(r"<h2>重点内容</h2>(.*?)(?=<h2>|$)", content, re.DOTALL)
        if match:
            kp_html = match.group(1)
            # 统计<li>标签数量
            result["key_points_count"] = len(re.findall(r"<li", kp_html))
            # 如果没有<li>，统计数字开头的条目
            if result["key_points_count"] == 0:
                text = re.sub(r"<[^>]+>", "", kp_html)
                result["key_points_count"] = len(re.findall(r"^\d+\.", text, re.MULTILINE))

    return result


def main():
    print("=" * 80)
    print("飞书知识库章节点质量检查")
    print("=" * 80)
    print()

    all_results = []
    total = 0
    passed = 0

    for course in COURSES:
        print(f"【{course['name']}】")
        for chapter in course["chapters"]:
            print(f"  检查: {chapter}...", end=" ", flush=True)
            result = check_chapter(course["name"], course["profile"], chapter)
            all_results.append(result)
            total += 1

            # 判断是否通过
            is_pass = (
                result["has_overview"]
                and result["has_points_list"]
                and result["has_key_points"]
                and result["has_advice"]
                and result["content_length"] > 100
                and not result["has_frontmatter"]
                and not result["errors"]
            )
            if is_pass:
                passed += 1
                print("✅ 通过")
            else:
                print("❌ 未通过")
                for err in result["errors"]:
                    print(f"      - {err}")
                if not result["has_overview"]:
                    print("      - 缺少本章概述")
                if not result["has_points_list"]:
                    print("      - 缺少知识点列表")
                if not result["has_key_points"]:
                    print("      - 缺少重点内容")
                if not result["has_advice"]:
                    print("      - 缺少学习建议")
                if result["has_frontmatter"]:
                    print("      - frontmatter未剥离")
                if result["key_points_count"] > 0 and (result["key_points_count"] < 3 or result["key_points_count"] > 7):
                    print(f"      - 重点内容条数异常: {result['key_points_count']}条（应为3-7条）")

            # 避免API限流
            time.sleep(1)
        print()

    print("=" * 80)
    print(f"检查结果: {passed}/{total} 通过")
    print("=" * 80)
    print()

    # 详细统计
    print("详细统计:")
    print(f"  本章概述齐全: {sum(1 for r in all_results if r['has_overview'])}/{total}")
    print(f"  知识点列表齐全: {sum(1 for r in all_results if r['has_points_list'])}/{total}")
    print(f"  重点内容齐全: {sum(1 for r in all_results if r['has_key_points'])}/{total}")
    print(f"  学习建议齐全: {sum(1 for r in all_results if r['has_advice'])}/{total}")
    print(f"  frontmatter已剥离: {sum(1 for r in all_results if not r['has_frontmatter'])}/{total}")
    print(f"  内容非空(>100字): {sum(1 for r in all_results if r['content_length'] > 100)}/{total}")
    kp_counts = [r["key_points_count"] for r in all_results if r["has_key_points"]]
    if kp_counts:
        print(f"  重点内容条数: 最小{min(kp_counts)}, 最大{max(kp_counts)}, 平均{sum(kp_counts)/len(kp_counts):.1f}")


if __name__ == "__main__":
    main()
