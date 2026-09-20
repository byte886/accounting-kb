#!/usr/bin/env python3
"""课程档案卡(profile)读取器（Python 侧）。

knowledge/*.py 不再硬编码课程目录 / 章名 / 课程信息，统一从
config/courses/<key>.json 读取。换课只换 --profile 或环境变量
GAODUN_COURSE_PROFILE，不改代码。设计见
docs/development/guides/parallel-toolkit-design.md 三。

用法：
    from course_profile import load_profile, primary_ids
    p = load_profile()                       # 默认 cpa-tax-2026（可用环境变量覆盖）
    p = load_profile("cpa-accounting-2026")  # 指定 key
    ids = primary_ids(p)                     # courseId/syllabusId/...

命令行自检：
    python3 scripts/knowledge/course_profile.py cpa-tax-2026
"""
import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE_DIR = REPO / "config" / "courses"
DEFAULT_KEY = "cpa-tax-2026"


def list_profiles():
    if not PROFILE_DIR.exists():
        return []
    return sorted(f.stem for f in PROFILE_DIR.glob("*.json"))


def load_profile(key=None):
    """读取并做最小必填校验，返回 profile dict。"""
    key = key or os.environ.get("GAODUN_COURSE_PROFILE") or DEFAULT_KEY
    fp = Path(key)
    if str(key).endswith(".json") and fp.exists():
        file = fp.resolve()
    else:
        file = PROFILE_DIR / f"{key}.json"
    if not file.exists():
        avail = ", ".join(list_profiles()) or "无"
        raise FileNotFoundError(f"课程 profile 不存在: {file}（可用：{avail}）")
    with open(file, encoding="utf-8") as f:
        p = json.load(f)

    errs = []
    if not p.get("key"):
        errs.append("缺 key")
    pc = p.get("primaryCourse") or {}
    if not pc.get("saasCourseId"):
        errs.append("缺 primaryCourse.saasCourseId")
    if (p.get("subject") or {}).get("id") is None:
        errs.append("缺 subject.id")
    if not (p.get("paths") or {}).get("localRoot"):
        errs.append("缺 paths.localRoot")
    if errs:
        raise ValueError(f"profile 校验失败({file.name}): {'; '.join(errs)}")
    p["_file"] = str(file)
    return p


def primary_ids(p):
    """取主采集源做题/内容接口参数（等价旧脚本散落的常量）。"""
    c = p["primaryCourse"]
    return {
        "courseId": c.get("saasCourseId"),
        "vcourseId": c.get("vcourseId"),
        "syllabusId": c.get("syllabusId"),
        "gradationId": c.get("gradationId"),
        "platform": c.get("platform"),
        "subjectId": p["subject"]["id"],
    }


def _main():
    ap = argparse.ArgumentParser(description="课程 profile 自检")
    ap.add_argument("key", nargs="?", help="profile key，默认环境变量或 cpa-tax-2026")
    args = ap.parse_args()
    p = load_profile(args.key)
    ids = primary_ids(p)
    print(f"profile   : {p['key']}  ({os.path.relpath(p['_file'], REPO)})")
    print(f"科目      : {p['subject']['name']}({p['subject']['id']})  老师={p.get('teacher','-')}  考季={p.get('season','-')}")
    print(f"主采集源  : {p['primaryCourse']['name']}")
    print(f"IDs       : courseId(saas)={ids['courseId']} vcourse={ids['vcourseId']} "
          f"syllabus={ids['syllabusId']} platform={ids['platform']} 状态={p['primaryCourse'].get('learnStatusDesc')}")
    st = p.get("structure") or {}
    groups = st.get("groups") or []
    print(f"章组结构  : {st.get('officialGroupCount')} 组 / {st.get('pointCount')} 知识点，已列 {len(groups)} 组名")
    print(f"本地路径  : {p['paths']['localRoot']}")
    for c in p.get("companionCourses", []):
        print(f"配套课    : [{c.get('platform')}] {c.get('name')} collect={c.get('collect', True)} 状态={c.get('learnStatusDesc','-')}")


if __name__ == "__main__":
    try:
        _main()
    except (FileNotFoundError, ValueError) as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
