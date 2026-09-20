#!/usr/bin/env python3
"""飞书知识库建树脚本（新空间「课程库 → 全称课程容器 → 章/全局篇 → 知识点」8 课模型）。

职责（只建结构，不写正文；正文由 resync_wiki_content.py 负责）：
1. 从 config/courses/<profile>.json 读 wiki.spaceId / wiki.rootParentNodeToken /
   primaryCourse.name（课程容器全称）；
2. 在「课程库」根节点下幂等确保存在一个全称课程容器（按标题复用，不重复建），
   并把 wiki.courseNodeToken / wiki.courseObjToken 回写到配置卡；
3. 在课程容器下建 30 章（章目录名）+ 章下知识点 + 2 全局篇（知识详解根目录 *.md，
   根 README.md 是课程首页、对应容器本身，不建子节点）；
4. 映射逐行追加到 data/_workspace/<profile>/logs/wiki_node_map.tsv
   （title<TAB>node_token<TAB>obj_token<TAB>parent_node_token），幂等可重跑。

用法：
  # 推荐（新 8 课模型，全部从配置卡读）：
  python3 scripts/knowledge/build_tree.py cpa-accounting-2026
  # 指定课程目录（默认取配置卡 paths.localRoot）：
  python3 scripts/knowledge/build_tree.py cpa-accounting-2026 /path/to/course
  # 兼容旧用法（直接在给定 parent 下建树、不建课程容器）：
  python3 scripts/knowledge/build_tree.py <profile> <parent_token> <course_dir>

可选环境变量：GAODUN_WIKI_SPACE_ID 覆盖 spaceId。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)

SPACE_ID = os.environ.get("GAODUN_WIKI_SPACE_ID", "")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_config(profile):
    """直接读配置卡 JSON（不做最小必填校验，建树只依赖 wiki/primaryCourse/paths）。"""
    cfg_path = PROJECT_DIR / "config" / "courses" / f"{profile}.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置卡不存在: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_path"] = str(cfg_path)
    return cfg


def writeback_config(cfg, course_node, course_obj):
    """把课程容器 token 回写配置卡 wiki.courseNodeToken/courseObjToken。"""
    cfg_path = Path(cfg["_path"])
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    wiki = data.setdefault("wiki", {})
    changed = (wiki.get("courseNodeToken") != course_node
               or wiki.get("courseObjToken") != course_obj)
    wiki["courseNodeToken"] = course_node
    wiki["courseObjToken"] = course_obj
    wiki.pop("_note", None)  # 回写后移除占位说明
    if changed:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        log(f"  [回写配置] wiki.courseNodeToken={course_node} -> {cfg_path.name}")


def run_lark(args):
    """运行 lark-cli，返回解析后的 JSON。"""
    cmd = ["lark-cli"] + args + ["--as", "user", "--format", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return json.loads(result.stdout)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e}"}


def get_children(parent_token):
    """获取父节点下所有子节点（标题→节点 dict），自动翻页。"""
    items, page_token = [], None
    while True:
        args = ["wiki", "+node-list", "--space-id", SPACE_ID,
                "--parent-node-token", parent_token]
        if page_token:
            args += ["--page-token", page_token]
        result = run_lark(args)
        if not result.get("ok"):
            break
        d = result.get("data", {})
        items += d.get("nodes", []) or d.get("items", []) or []
        page_token = d.get("page_token") or d.get("next_page_token")
        if not d.get("has_more") or not page_token:
            break
        time.sleep(0.3)
    return {n["title"]: n for n in items}


def create_node(parent_token, title):
    """在 parent 下幂等建节点，返回 (node_token, obj_token)。"""
    if title in get_children(parent_token):
        log(f"  [复用] {title}")
        n = get_children(parent_token)[title]
        return n["node_token"], n["obj_token"]
    for attempt in range(3):
        result = run_lark([
            "wiki", "+node-create", "--parent-node-token", parent_token,
            "--title", title, "--space-id", SPACE_ID,
        ])
        if result.get("ok"):
            d = result.get("data", {})
            log(f"  [创建] {title}")
            time.sleep(0.5)
            return d.get("node_token"), d.get("obj_token")
        log(f"  [重试{attempt + 1}] {title}: {str(result.get('error'))[:120]}")
        time.sleep((attempt + 1) * 4)
    log(f"  [失败] {title}")
    return None, None


def ensure_course_container(cfg):
    """在课程库根下确保全称课程容器存在，返回 (node_token, obj_token)。"""
    wiki = cfg.get("wiki") or {}
    root = wiki.get("rootParentNodeToken")
    title = (cfg.get("primaryCourse") or {}).get("name")
    if not root or not title:
        raise ValueError("配置卡缺 wiki.rootParentNodeToken 或 primaryCourse.name，无法建课程容器")
    log(f"--- 确保课程容器：{title}（在课程库 {root} 下）---")
    existing = get_children(root)
    node = existing.get(title)
    if node:
        log(f"  [复用容器] {title}")
        course_node, course_obj = node["node_token"], node["obj_token"]
    elif wiki.get("courseNodeToken"):
        # 配置卡声称有容器但根列表没按标题找到：信任配置卡（极端分页/改名场景），不另建
        log(f"  [采用配置卡容器] {wiki['courseNodeToken']}")
        course_node, course_obj = wiki["courseNodeToken"], wiki.get("courseObjToken")
    else:
        course_node, course_obj = create_node(root, title)
    if not course_node:
        raise RuntimeError(f"课程容器创建失败: {title}")
    writeback_config(cfg, course_node, course_obj)
    return course_node, course_obj


def build_inside(profile, parent_token, knowledge_dir, map_file):
    """在 parent_token（课程容器）下建 章→知识点 + 全局篇，映射落 map_file。"""
    existing_map = {}
    if map_file.exists():
        with open(map_file, encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) >= 3:
                    existing_map[p[0]] = (p[1], p[2])

    def save_map(title, node_token, obj_token, parent):
        existing_map[title] = (node_token, obj_token)
        with open(map_file, "a", encoding="utf-8") as f:
            f.write(f"{title}\t{node_token}\t{obj_token}\t{parent}\n")

    # 1. 章 + 知识点
    log("--- 章节点与知识点 ---")
    for group_dir in sorted(knowledge_dir.iterdir()):
        if not group_dir.is_dir():
            continue
        group_name = group_dir.name
        if group_name in existing_map:
            group_node = existing_map[group_name]
            log(f"  [跳过章] {group_name}")
        else:
            group_node = create_node(parent_token, group_name)
            if group_node[0]:
                save_map(group_name, group_node[0], group_node[1], parent_token)
            else:
                log(f"  [错误] 无法建章: {group_name}")
                continue
        for md in sorted(group_dir.glob("*.md")):
            if md.name == "README.md":
                continue
            t = md.stem
            if t in existing_map:
                continue
            n = create_node(group_node[0], t)
            if n[0]:
                save_map(t, n[0], n[1], group_node[0])

    # 2. 全局篇（知识详解根目录 *.md；根 README 是课程首页、不建子节点）
    log("--- 全局篇（置于章之后）---")
    for md in sorted(knowledge_dir.glob("*.md")):
        if md.name == "README.md":
            continue
        t = md.stem
        if t in existing_map:
            continue
        n = create_node(parent_token, t)
        if n[0]:
            save_map(t, n[0], n[1], parent_token)

    log(f"========== 建树完成: {profile}，map 共 {len(existing_map)} 个子页面 ==========")
    return True


def main():
    global SPACE_ID
    profile = sys.argv[1] if len(sys.argv) > 1 else None
    p2 = sys.argv[2] if len(sys.argv) > 2 else None
    p3 = sys.argv[3] if len(sys.argv) > 3 else None
    if not profile:
        print("用法:\n"
              "  python3 build_tree.py <profile>                 # 新8课模型：自动建课程容器\n"
              "  python3 build_tree.py <profile> <course_dir>    # 指定课程目录\n"
              "  python3 build_tree.py <profile> <parent_token> <course_dir>  # 旧用法，不建容器")
        sys.exit(1)

    cfg = load_config(profile)
    if not SPACE_ID:
        SPACE_ID = (cfg.get("wiki") or {}).get("spaceId", "")
    if not SPACE_ID:
        log(f"[错误] 配置卡缺 wiki.spaceId: {cfg['_path']}")
        sys.exit(2)

    local_root = cfg.get("paths", {}).get("localRoot", "")
    if p3:
        # 旧用法：p2=parent_token, p3=course_dir，直接在 parent 下建树（不建容器）
        parent_token, course_dir = p2, Path(p3)
        log(f"========== 旧用法建树: {profile}，直接挂 {parent_token} ==========")
    else:
        # 新 8 课模型：确保课程容器
        course_dir = Path(p2) if p2 else (PROJECT_DIR / local_root)
        parent_token, _ = ensure_course_container(cfg)

    knowledge_dir = course_dir / "知识详解"
    if not knowledge_dir.exists():
        log(f"[错误] 知识详解目录不存在: {knowledge_dir}")
        sys.exit(3)

    map_file = PROJECT_DIR / f"data/_workspace/{cfg.get('key', profile)}/logs/wiki_node_map.tsv"
    map_file.parent.mkdir(parents=True, exist_ok=True)
    log(f"space={SPACE_ID} 容器/父节点={parent_token} 目录={knowledge_dir}")
    build_inside(cfg.get("key", profile), parent_token, knowledge_dir, map_file)


if __name__ == "__main__":
    main()
