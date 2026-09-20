#!/usr/bin/env python3
"""
organize_user_notes.py — 整理用户笔记，生成知识详解「四、学员补充」节内容

流程：
  1. 读取按知识点分组的笔记
  2. 去重（相同内容保留赞数最高的）
  3. 过滤无意义内容（太短、纯吐槽）
  4. 分类（口诀/易错点/解题技巧/知识补充）
  5. 按赞数排序，每个知识点保留 Top N
  6. 生成 Markdown 内容
  7. 写入知识详解文件的「四、学员补充」节（替换或新增）
"""
import json, os, re, sys
from collections import defaultdict

# 课程定位优先级：环境变量 COURSE_LOCAL_ROOT > 课程 profile（GAODUN_COURSE_PROFILE，缺省税法）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from course_profile import load_profile  # noqa: E402  同目录读取器
_profile = load_profile()
DEFAULT_DA = os.path.join(ROOT, _profile["paths"]["localRoot"])
DA = os.environ.get("COURSE_LOCAL_ROOT", DEFAULT_DA)
if not os.path.isabs(DA):
    DA = os.path.join(ROOT, DA)
KD = os.path.join(DA, "知识详解")
# 笔记原件：env USER_NOTES_RAW_DIR > data/_workspace/<profile.key>/notes-raw（与 collect_user_notes.js 对齐）
RAW_DIR = os.environ.get(
    "USER_NOTES_RAW_DIR", os.path.join(ROOT, "data", "_workspace", _profile["key"], "notes-raw"))

# 分类关键词
CATEGORIES = {
    "记忆口诀": ["速记", "口诀", "记住", "记忆", "谐音", "联想", "顺口溜", "记法", "背", "巧记"],
    "易错点辨析": ["易错", "注意", "容易", "混淆", "区别", "不要", "别忘", "提醒", "坑", "陷阱", "常错", "搞错"],
    "解题技巧": ["解题", "技巧", "方法", "步骤", "思路", "公式", "算法", "计算", "答题", "套路"],
    "知识补充": [],  # 默认分类
}

def categorize(text):
    """根据内容分类"""
    for cat, keywords in CATEGORIES.items():
        if cat == "知识补充":
            continue
        for kw in keywords:
            if kw in text:
                return cat
    return "知识补充"

def is_meaningful(text):
    """过滤无意义内容"""
    if len(text) < 8:
        return False
    # 纯吐槽/无实质内容
    meaningless = ["硬记", "背吧", "记住吧", "无语", "醉了", "服了", "难", "烦", "累", "加油", "冲", "过", "必过", "好运"]
    for m in meaningless:
        if text.strip() == m or text.strip().startswith(m) and len(text) < 15:
            return False
    return True

def normalize_text(text):
    """标准化文本用于去重"""
    t = re.sub(r'\s+', '', text)
    t = re.sub(r'[，,。.！!？?；;：:、]', '', t)
    return t

def organize_notes(kp_notes, kp_to_file):
    """整理所有笔记，返回文件路径 -> 学员补充内容的映射"""
    file_notes = defaultdict(list)  # file_path -> [(kp, note_dict)]

    for kp, notes in kp_notes.items():
        fp = kp_to_file.get(kp)
        if not fp:
            continue
        for n in notes:
            file_notes[fp].append((kp, n))

    result = {}
    for fp, notes in file_notes.items():
        # 去重
        seen = {}
        for kp, n in notes:
            text = n.get("noteContent", "").strip()
            if not text or not is_meaningful(text):
                continue
            norm = normalize_text(text)
            if norm in seen:
                # 保留赞数更高的
                if n.get("fabulousNum", 0) > seen[norm][1].get("fabulousNum", 0):
                    seen[norm] = (kp, n)
            else:
                seen[norm] = (kp, n)

        unique_notes = list(seen.values())

        # 分类
        categorized = defaultdict(list)
        for kp, n in unique_notes:
            cat = categorize(n.get("noteContent", ""))
            categorized[cat].append((kp, n))

        # 每类按赞数排序
        for cat in categorized:
            categorized[cat].sort(key=lambda x: x[1].get("fabulousNum", 0), reverse=True)

        # 生成 Markdown
        md_lines = []
        total_count = 0
        for cat in ["记忆口诀", "易错点辨析", "解题技巧", "知识补充"]:
            notes_in_cat = categorized.get(cat, [])
            if not notes_in_cat:
                continue
            # 每类最多保留 5 条
            top_notes = notes_in_cat[:5]
            md_lines.append(f"### {cat}")
            md_lines.append("")
            for kp, n in top_notes:
                text = n.get("noteContent", "").strip()
                # 清理文本中的换行
                text = re.sub(r'\n+', '；', text)
                # 学员名、点赞数等元数据仅用于排序筛选，一律不写入最终知识产物，只保留知识内容本身
                md_lines.append(f"- {text}")
                total_count += 1
            md_lines.append("")

        if total_count == 0:
            result[fp] = None
        else:
            result[fp] = "\n".join(md_lines).rstrip() + "\n"

    return result

def update_kd_file(fp, new_content):
    """更新知识详解文件的「四、学员补充」节"""
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否已有「四、学员补充」节
    pattern = r'## 四、学员补充\n.*?(?=\n## |\Z)'
    if re.search(pattern, content, re.DOTALL):
        # 替换现有节
        new_section = f"## 四、学员补充\n\n{new_content}"
        content = re.sub(pattern, new_section, content, flags=re.DOTALL)
    else:
        # 在文件末尾新增
        if not content.endswith('\n'):
            content += '\n'
        content += f"\n## 四、学员补充\n\n{new_content}\n"

    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    # 读取数据
    with open(os.path.join(RAW_DIR, "notes_by_knowledge_point.json")) as f:
        kp_notes = json.load(f)
    with open(os.path.join(RAW_DIR, "kp_to_file.json")) as f:
        kp_to_file = json.load(f)

    # 知识点→文件映射、按知识点分组均由 build_notes_mapping.py 生成；
    # "聚合卷/近义名 → 知识详解篇"的个别别名在 build 阶段经 notes-raw/alias.json 处理，本脚本不写死任何课程。

    print(f"知识点数: {len(kp_notes)}, 映射数: {len(kp_to_file)}")

    # 整理笔记
    file_contents = organize_notes(kp_notes, kp_to_file)

    print(f"\n有学员补充内容的文件数: {len([v for v in file_contents.values() if v])}")
    print(f"无内容的文件数: {len([v for v in file_contents.values() if not v])}")

    # 统计
    total_notes = 0
    for fp, content in file_contents.items():
        if content:
            total_notes += content.count('\n- ')
    print(f"整理后总笔记条数: {total_notes}")

    # 保存整理后的内容（供检查）
    output = {}
    for fp, content in file_contents.items():
        if content:
            output[fp] = content
    with open(os.path.join(RAW_DIR, "organized_notes.json"), 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n已保存整理结果: {RAW_DIR}/organized_notes.json")

    # 写入知识详解文件
    updated = 0
    for fp, content in file_contents.items():
        if content and os.path.exists(fp):
            update_kd_file(fp, content)
            updated += 1
    print(f"已更新知识详解文件: {updated} 篇")

if __name__ == "__main__":
    main()
