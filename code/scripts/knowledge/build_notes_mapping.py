#!/usr/bin/env python3
"""build_notes_mapping.py — 把采集到的用户笔记（all_notes.jsonl）映射到知识详解知识点篇。

补齐 collect_user_notes.js（只按 questionId 拉原始笔记）与
organize_user_notes.py（消费"按知识点分组"的笔记）之间缺失的通用一环。
税法一期靠一次性过程件生成下列中间件、未固化，本脚本把它做成换课可复用的正式环节。

流程（数据驱动，不在代码里写死任何课程的章名/别名）：
  1. 扫 profile 的 原始资源/papers/，只认真题面（dict 且含 moduleList；跳过 batch_result_*.json 之类汇总）
  2. 试卷标题去【前缀】、去科目段后取末段作为候选知识点名，与 知识详解/ 现有篇名精确匹配
     - 卷型段（知识点练习 / 分章真题测 / 课后练习 等）本就在知识点段之前，取末段天然兼容三种标题
     - 可选别名表 notes-raw/alias.json：{卷上知识点名: 篇名 或 [篇名...]}，处理"聚合卷 vs 拆细篇/近义名"
  3. questionId -> [知识点名]；all_notes.jsonl 沿此挂到各知识点
  4. 产出（与 organize_user_notes.py 输入对齐，均落 notes-raw，过程件不入库）：
       qid_to_kps.json              {questionId(str): [知识点名]}
       kp_to_file.json              {知识点名: 相对仓库根的知识详解篇路径}
       notes_by_knowledge_point.json {知识点名: [笔记白名单字段...]}
       unmatched_kps.json           [匹配不到现有篇的知识点名]（章级卷/未生成章/待别名，供人工核对）

用法：python3 scripts/knowledge/build_notes_mapping.py [--profile cpa-accounting-2026]
身份字段（studentName/studentId/头像/isSelf 等）在本层即剥离，只留知识内容与排序用的赞数/时间。
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from course_profile import load_profile  # noqa: E402

# 笔记向下游传递时的白名单：身份信息一律不带（学员名等元数据绝不进知识产物）
NOTE_KEEP = ("questionId", "noteContent", "fabulousNum", "createdAt", "papers")
# 标题里非知识点的"卷型/前缀"段（取末段后仍兜底剔除用）
SECTION_JUNK = {"知识点练习", "分章真题测", "课后练习", "课前练习", "章节练习"}


def candidate_kps(title, subject_name):
    """从试卷标题解析候选知识点名。

    去【前缀】、去科目段；去科目后第一段要么是卷型标记（知识点练习/分章真题测），
    要么是章/专题名（课后练习），都不是知识点，剔除；其余段用 "-" 拼回，
    以保留知识点名内部的连字符（如"关于特定交易的会计处理（1-3类）"）。
    只剩一段时即章级卷（如"总论"），原样返回、交由 unmatched 人工判断。
    """
    t = re.sub(r"^【[^】]*】", "", (title or "").strip())
    parts = [x.strip() for x in re.split(r"[-—–]", t) if x.strip()]
    if parts and parts[0] == subject_name:
        parts = parts[1:]
    if len(parts) >= 2:
        parts = parts[1:]  # 剔除卷型段或章名段
    parts = [x for x in parts if x not in SECTION_JUNK]
    return "-".join(parts) if parts else None


def iter_real_papers(papers_dir: Path):
    """只产出真题面（dict 且含 moduleList），跳过批次汇总等非题面 JSON。"""
    for fp in sorted(papers_dir.glob("*.json")):
        try:
            j = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(j, dict) and isinstance(j.get("moduleList"), list):
            yield fp, j


def paper_question_ids(paper):
    ids = []
    for mod in paper.get("moduleList", []):
        for q in mod.get("questionList", []) or []:
            if q.get("questionId") is not None:
                ids.append(q["questionId"])
            for sub in q.get("subQuestionList", []) or []:
                if sub.get("questionId") is not None:
                    ids.append(sub["questionId"])
    return ids


def main():
    ap = argparse.ArgumentParser(description="用户笔记→知识详解知识点 映射构建")
    ap.add_argument("--profile", help="课程 key，默认环境变量或 cpa-tax-2026")
    args = ap.parse_args()
    p = load_profile(args.profile)
    da = Path(REPO / p["paths"]["localRoot"]).resolve()
    kd_dir = da / "知识详解"
    papers_dir = da / "原始资源" / "papers"
    raw_dir = Path(os.environ.get("USER_NOTES_RAW_DIR",
                                  REPO / "data" / "_workspace" / p["key"] / "notes-raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    subject_name = (p.get("subject") or {}).get("name", "")

    # 现有知识详解篇：篇名 -> 相对仓库根路径
    kp_to_file = {}
    for f in kd_dir.rglob("*.md"):
        if "README" in f.name:
            continue
        try:
            kp_to_file[f.stem] = str(f.relative_to(REPO))
        except ValueError:
            kp_to_file[f.stem] = str(f)

    alias_path = raw_dir / "alias.json"
    alias = json.load(open(alias_path, encoding="utf-8")) if alias_path.exists() else {}

    # questionId -> [kp]；同时收集未匹配候选
    qid_to_kps = defaultdict(list)
    unmatched = []
    seen_unmatched = set()

    def resolve(cand):
        """候选知识点名 -> [现有篇名]；返回 None 表示未匹配。"""
        if not cand:
            return None
        if cand in kp_to_file:
            return [cand]
        if cand in alias:
            v = alias[cand]
            return v if isinstance(v, list) else [v]
        return None

    n_papers = 0
    for _, paper in iter_real_papers(papers_dir):
        n_papers += 1
        cand = candidate_kps(paper.get("title", ""), subject_name)
        kps = resolve(cand)
        if not kps:
            if cand and cand not in seen_unmatched:
                seen_unmatched.add(cand)
                unmatched.append(cand)
            continue
        for qid in paper_question_ids(paper):
            for k in kps:
                if k not in qid_to_kps[qid]:
                    qid_to_kps[qid].append(k)

    # all_notes.jsonl 沿 qid->kp 挂载，剥身份字段
    notes_by_kp = defaultdict(list)
    n_notes = n_dropped = 0
    notes_file = raw_dir / "all_notes.jsonl"
    if notes_file.exists():
        for line in open(notes_file, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            n = json.loads(line)
            qid = str(n.get("questionId"))
            kps = qid_to_kps.get(qid) or qid_to_kps.get(n.get("questionId"))
            if not kps:
                n_dropped += 1
                continue
            clean = {k: n[k] for k in NOTE_KEEP if k in n}
            for k in kps:
                notes_by_kp[k].append(clean)
            n_notes += 1

    # 只保留确有现有篇的映射写入 kp_to_file
    kp_to_file_matched = {k: v for k, v in kp_to_file.items()
                          if any(k in kps for kps in qid_to_kps.values()) or notes_by_kp.get(k)}

    json.dump({str(k): v for k, v in qid_to_kps.items()},
              open(raw_dir / "qid_to_kps.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(kp_to_file_matched, open(raw_dir / "kp_to_file.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(dict(notes_by_kp), open(raw_dir / "notes_by_knowledge_point.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(sorted(unmatched), open(raw_dir / "unmatched_kps.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    n_with_notes = sum(1 for v in notes_by_kp.values() if v)
    print(f"课程: {p['key']}（{subject_name}）  真题面 {n_papers} 张  现有知识点篇 {len(kp_to_file)}")
    print(f"questionId→知识点 映射 {sum(len(v) for v in qid_to_kps.values())} 条（{len(qid_to_kps)} 题）")
    print(f"笔记挂载 {n_notes} 条到 {len(notes_by_kp)} 个知识点（其中 {n_with_notes} 个有笔记）；无映射丢弃 {n_dropped} 条")
    print(f"未匹配候选知识点 {len(unmatched)} 个 -> unmatched_kps.json（章级卷/未生成章/需 alias 别名）")
    if unmatched:
        for u in unmatched[:20]:
            print("   -", u)
        if len(unmatched) > 20:
            print(f"   …其余 {len(unmatched) - 20} 个见文件")


if __name__ == "__main__":
    main()
