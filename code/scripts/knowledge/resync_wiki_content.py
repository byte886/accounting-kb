#!/usr/bin/env python3
"""把本地知识详解 Markdown 重新覆盖写入对应飞书文档（只更新内容，绝不创建/删除节点）。

适用：链接格式、正文清理等"内容层"批量修订后的重同步（如相对链接改为 <cite> 内部引用）。
- 标题→obj_token 取自 data/_workspace/cpa-tax-2026/logs/wiki_node_map.tsv（已去重，108 个标题全局唯一）；
- 本地相对链接经 scripts/wiki_link_resolve.py 转为 <cite> 内部文档引用（渲染为目标文档标题、
  obj_token 强绑定可校验坏链；注意飞书正文跨文档点击统一新开标签，单窗口导航走左侧知识库目录树）；
- 章 README 以"章目录名"为标题，知识点篇以文件名（去 .md）为标题，全局篇在知识详解根目录；
- 找不到 obj、或 docs +update 失败均计入失败清单；重试按错误类型分级：
  代理会话错（ext err / parse temporary token / invalid_response）原地只重试 1 次(2s+抖动)、
  再败立即 exit 2 交外层换新进程；HTTP 429 按 Retry-After 等；其他网络错最多 3 次指数退避(1/2/4/8/16s 封顶30s ±20%抖动)；
- 单进程新写满 RESYNC_MAX_NEW(默认20) 篇即 exit 0，外层 run_resync_batches.sh 拉起新进程续跑（done 断点跳过）；
- 不写 done_flag、不追加 map，避免映射表重复膨胀。

用法：
  python3 scripts/knowledge/resync_wiki_content.py                  # 全量重同步（默认用 profile.paths.localRoot）
  python3 scripts/knowledge/resync_wiki_content.py --only 01        # 只重跑路径含 01 的文件（dry 过滤）
  python3 scripts/knowledge/resync_wiki_content.py --dry-run         # 只列出将同步的文件，不写飞书
  python3 scripts/knowledge/resync_wiki_content.py --course-dir <dir> --map <tsv>  # 显式指定目录和映射（一卡一课，不靠手改 json）
"""
import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "knowledge"))
from course_profile import load_profile  # noqa: E402

HOMEPAGE_KEY = "__COURSE_HOMEPAGE__"  # 课程首页 done 标记名（对应课程容器本身，非 map 子页面）


def _load_default_profile():
    """默认 profile 加载容错：显式传 --course-dir/--map 时允许最小卡/无卡运行。"""
    try:
        return load_profile()
    except Exception:  # noqa: BLE001
        return None


_profile = _load_default_profile()
if _profile:
    _key = _profile["key"]
    _local_root = _profile["paths"]["localRoot"]
else:
    _key = os.environ.get("GAODUN_COURSE_PROFILE", "")
    _local_root = ""
# 标题→obj_token 映射随 profile 走（建树脚本 build_tree.py 产出），可用 WIKI_MAP/--map 覆盖
MAP_FILE = os.environ.get("WIKI_MAP") or (
    os.path.join(REPO, "data", "_workspace", _key, "logs", "wiki_node_map.tsv") if _key else "")
RESOLVER = os.path.join(REPO, "scripts", "wiki_link_resolve.py")
COURSE_DIR = os.path.join(REPO, _local_root, "知识详解") if _local_root else ""
# 断点续跑：每篇成功落 done，重跑时零 API 跳过（与建树 wiki_done 同范式），
# 多轮保守批次只补未成功篇、不重复消耗账号写配额；--force 可全量重刷
DONE_DIR = os.path.join(os.path.dirname(MAP_FILE), "resync_done") if MAP_FILE else ""


def load_raw_config(key):
    """只读原始配置卡（不做必填校验），用于取 wiki.courseObjToken 等。"""
    import json
    fp = os.path.join(REPO, "config", "courses", f"{key}.json")
    if key and os.path.isfile(fp):
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    return {}


def safe_name(title):
    return title.replace("/", "_").replace(" ", "_")


def strip_frontmatter(text):
    """剥离文件顶部的 YAML frontmatter（连续 ---...---），无则原样返回。

    仅当文件以 --- 开头时才剥离；正文中间的 --- 分隔线（前面有标题/blockquote）不会被误判。
    剥离后去掉前导空行，保证正文从 # 标题开始。
    """
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[i + 1:]).lstrip("\n")
    return text  # 无闭合 ---，原样返回（不破坏文件）


def load_title2obj():
    m = {}
    with open(MAP_FILE, encoding="utf-8") as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 3 and c[0]:
                m[c[0]] = c[2]
    return m


def collect_files():
    """返回 [(标题, 本地路径)]，覆盖 2 全局篇 + 14 章 README + 92 知识点篇。"""
    items = []
    for path in sorted(glob.glob(os.path.join(COURSE_DIR, "*.md"))):  # 全局篇
        # 根目录下的 README.md 是课程首页，直接对应根节点本身，不作为子节点同步
        if os.path.basename(path) == "README.md":
            continue
        items.append((os.path.basename(path)[:-3], path))
    for group in sorted(glob.glob(os.path.join(COURSE_DIR, "[0-9]*/"))):
        gname = os.path.basename(group.rstrip(os.sep))
        readme = os.path.join(group, "README.md")
        if os.path.isfile(readme):
            items.append((gname, readme))
        for p in sorted(glob.glob(os.path.join(group, "*.md"))):
            if os.path.basename(p) == "README.md":
                continue
            items.append((os.path.basename(p)[:-3], p))
    return items


# ---- 重试/错误分类（2026-09-20 重构）----
# lark-cli 走豆包沙箱 forward proxy（DOUBAO_OFFICE_FORWARD_PROXY）：
#   "ext err: parse temporary token from Authorization fail" 是代理层 token 会话问题，
#   不是飞书官方 429。换新 shell=新进程拿新代理会话即恢复，故代理错误只在原地短重试一次，
#   再败立即非零退出(exit 2)交外层 run_resync_batches.sh 拉起全新进程续跑。
PROXY_ERR_MARKERS = ("invalid_response", "parse temporary token", "ext err")
PROXY_RETRY_MAX = 1          # 代理会话错误：原地最多重试 1 次（2s + 抖动），再败即退出换进程
NET_RETRY_MAX = 3           # 其他网络/5xx 错误：原地最多重试 3 次，指数退避
BACKOFF_BASE = [1.0, 2.0, 4.0, 8.0, 16.0]  # 指数退避序列（1→2→4→8→16），封顶 30s


def _jitter(base):
    """±20% 随机抖动。"""
    return base * (1.0 + random.uniform(-0.2, 0.2))


def _classify_error(raw):
    """把一次 lark-cli 失败返回归类。

    返回 (kind, retry_after)：
      'proxy'   代理会话问题（ext err / parse temporary token / invalid_response / 非JSON返回）
      'http429' 标准 HTTP 429，retry_after 为从 Retry-After 解析出的等待秒数（可能 None）
      'network' 其他网络/瞬时/5xx 错误，走指数退避
      'fatal'   业务/参数错误，不在原地盲目重试
    """
    # 代理会话问题往往不是合法 JSON，先于 JSON 解析识别
    if any(m in raw for m in PROXY_ERR_MARKERS):
        return "proxy", None
    try:
        d = json.loads(raw)
    except Exception:  # noqa: BLE001
        # 非 JSON 且未命中代理标记：按瞬时网络错处理
        return "network", None
    if isinstance(d, dict) and d.get("ok"):
        return "fatal", None
    err = d.get("error") if isinstance(d, dict) else None
    code = err.get("code") or err.get("status") if isinstance(err, dict) else None
    cnum = None
    if code is not None:
        try:
            cnum = int(code)
        except (TypeError, ValueError):
            cnum = None
    # 标准 HTTP 429：读 Retry-After（飞书业务错误码是大数字，不可按 >=500 误判为网络错）
    if cnum == 429 or '"code":429' in raw.replace(" ", ""):
        ra = None
        if isinstance(err, dict):
            ra = err.get("retry_after") or err.get("retryAfter") or err.get("Retry-After")
        if ra is None:
            m = re.search(r'"retry[-_ ]?after"\s*:\s*"?(\d+)', raw, re.I)
            if m:
                ra = m.group(1)
        try:
            return "http429", float(ra) if ra is not None else None
        except (TypeError, ValueError):
            return "http429", None
    # 其余 JSON 错误为业务/参数错误（含大数字错误码），不在原地盲目重试
    return "fatal", None


def update_one(title, path, obj):
    """覆盖写一篇。返回 (success, err, abort)。
    abort=True 表示代理会话已坏，主循环应立即非零退出、交外层换新进程。"""
    raw = open(path, encoding="utf-8").read()
    raw = strip_frontmatter(raw)
    # 必须显式把本 profile 的 map 传给 resolver：resolver 默认回退到仓库根 logs/（不存在），
    # 不传 WIKI_MAP 会导致其映射表为空、所有相对链接都转不成 cite（2026-09-12 会计课踩过，
    # 第二遍 169 篇内链全部退化成纯文本，不得不第三遍重刷）
    resolved = subprocess.run(
        ["python3", RESOLVER], input=raw, capture_output=True, text=True, cwd=REPO,
        env={**os.environ, "WIKI_MAP": MAP_FILE},
    ).stdout
    # 守卫：resolver 输出空时不发空写请求（否则 lark-cli 报 requires --content，
    # 属 validation 错误、重试纯浪费），直接返回真因
    if not resolved.strip():
        return False, "wiki_link_resolve 输出为空（resolver 异常），未发写请求", False
    # fail-loud：同目录 ./xxx.md 链接本应全部转成 cite，残留说明 WIKI_MAP 没生效
    if "](" + "./" in resolved:
        print(f"    [警告] {title} resolver 后仍残留 ./ 相对链接（cite 未生效，检查 WIKI_MAP 是否传对）", flush=True)

    proxy_tried = 0   # 代理会话错误已原地重试次数
    net_tried = 0     # 网络/429 错误已原地重试次数
    attempt = 0
    last = ""
    while True:
        attempt += 1
        proc = subprocess.run(
            ["lark-cli", "docs", "+update", "--doc", obj, "--command", "overwrite",
             "--doc-format", "markdown", "--content", "-", "--as", "user", "--format", "json"],
            input=resolved, capture_output=True, text=True, cwd=REPO,
        )
        last = proc.stdout + proc.stderr
        if '"ok":true' in last.replace(" ", "") or '"ok": true' in last:
            return True, "", False
        kind, ra = _classify_error(last)
        print(f"    [attempt {attempt} rc={proc.returncode} kind={kind}] {last[:240]!r}", flush=True)

        # 代理会话问题：原地最多重试 1 次（2s+抖动），再败立即退出换进程
        if kind == "proxy":
            if proxy_tried < PROXY_RETRY_MAX:
                proxy_tried += 1
                wait = _jitter(2.0)
                print(f"    ⚠️ 代理会话问题(ext err/token)，原地第{proxy_tried}次重试，等 {wait:.1f}s", flush=True)
                time.sleep(wait)
                continue
            print("    ✗ 代理会话连续失败，立即非零退出，交外层换新进程", flush=True)
            return False, last[:300], True

        # HTTP 429 / 其他网络错误：最多重试 NET_RETRY_MAX 次
        if kind in ("http429", "network"):
            if net_tried >= NET_RETRY_MAX:
                return False, last[:300], False
            net_tried += 1
            if kind == "http429" and ra:
                wait = float(ra)
                tag = f"HTTP 429 按 Retry-After"
            else:
                wait = _jitter(min(30.0, BACKOFF_BASE[min(net_tried - 1, len(BACKOFF_BASE) - 1)]))
                tag = f"{kind} 第{net_tried}/{NET_RETRY_MAX}"
            print(f"    ⏳ {tag}，等 {wait:.1f}s", flush=True)
            time.sleep(wait)
            continue

        # fatal：业务/参数错误，不重试
        return False, last[:300], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只同步路径中包含该片段的文件")
    ap.add_argument("--dry-run", action="store_true", help="只列文件，不写飞书")
    ap.add_argument("--force", action="store_true", help="忽略 done 标记全量重刷")
    ap.add_argument("--profile", help="课程 profile key（默认环境变量或 cpa-tax）；决定 map/目录/课程容器")
    ap.add_argument("--course-dir", help="显式指定知识详解目录（默认回退 profile.paths.localRoot/知识详解）")
    ap.add_argument("--map", dest="map_file", help="显式指定 wiki_node_map.tsv 路径（默认回退 data/_workspace/<profile>/logs/wiki_node_map.tsv）")
    ap.add_argument("--course-obj", dest="course_obj", help="课程容器 obj_token（课程首页写入目标，默认读配置卡 wiki.courseObjToken）")
    ap.add_argument("--no-homepage", action="store_true", help="不同步课程首页（知识详解根 README.md → 课程容器）")
    args = ap.parse_args()

    # 一卡一课：显式参数覆盖 profile 默认值，从此不靠手改 json 切换正课/名师课
    global MAP_FILE, COURSE_DIR, DONE_DIR
    if args.profile:
        p = load_profile(args.profile)  # 合法卡；缺字段直接抛清晰错误
        MAP_FILE = os.path.join(REPO, "data", "_workspace", p["key"], "logs", "wiki_node_map.tsv")
        COURSE_DIR = os.path.join(REPO, p["paths"]["localRoot"], "知识详解")
    if args.map_file:
        MAP_FILE = args.map_file if os.path.isabs(args.map_file) else os.path.join(REPO, args.map_file)
    if args.course_dir:
        COURSE_DIR = args.course_dir if os.path.isabs(args.course_dir) else os.path.join(REPO, args.course_dir)
    if not MAP_FILE or not COURSE_DIR:
        ap.error("无法确定 map/course-dir：请用 --profile 指定合法配置卡，或同时显式传 --map 与 --course-dir")
    DONE_DIR = os.path.join(os.path.dirname(MAP_FILE), "resync_done")

    print(f"[配置] course_dir={COURSE_DIR}")
    print(f"[配置] map_file={MAP_FILE}")
    title2obj = load_title2obj()
    items = [(t, path, None) for t, path in collect_files()]

    # 课程首页：知识详解根 README.md 写入课程容器本身（不是 map 里的子页面）
    cfg = load_raw_config(args.profile or _key)
    course_obj = args.course_obj or (cfg.get("wiki") or {}).get("courseObjToken")
    homepage = os.path.join(COURSE_DIR, "README.md")
    if not args.no_homepage and course_obj and os.path.isfile(homepage):
        items.append((HOMEPAGE_KEY, homepage, course_obj))
        print(f"[配置] 课程首页 {os.path.basename(homepage)} -> 容器 {course_obj}")
    elif not args.no_homepage and not course_obj:
        print("[提示] 未取到 wiki.courseObjToken，跳过课程首页（先跑 build_tree.py 建容器并回写配置卡）")

    if args.only:
        items = [it for it in items if args.only in it[1]]

    missing, failed, ok = [], [], 0
    new_written = 0  # 本轮真实新写成功数（不含 done 跳过）
    # 单进程新写上限：lark-cli 经豆包转发代理访问飞书，单进程累计请求到阈值后代理层
    # 会话失效（ext err / parse temporary token / invalid_response）；全新进程=新代理会话即恢复。
    # 故每进程新写满 MAX_NEW 篇即主动干净退出(exit 0)，由外层 shell 拉起新进程续跑。
    # 默认 20（实测健康窗口）；RESYNC_MAX_NEW=0 表示不限制。
    max_new = int(os.environ.get("RESYNC_MAX_NEW", "20"))
    print(f"待处理文件 {len(items)} 个（map 共 {len(title2obj)} 个标题；单进程新写上限={max_new or '不限'}）")
    for i, (title, path, obj_override) in enumerate(items, 1):
        obj = obj_override or title2obj.get(title)
        rel = os.path.relpath(path, REPO)
        if not obj:
            missing.append((title, rel))
            print(f"[{i}/{len(items)}] ✗ 无obj映射: {title}")
            continue
        done_flag = os.path.join(DONE_DIR, safe_name(title) + ".done")
        if not args.force and os.path.exists(done_flag):
            ok += 1
            print(f"[{i}/{len(items)}] · 已同步跳过: {title}")
            continue
        if args.dry_run:
            print(f"[{i}/{len(items)}] (dry) {title} -> {obj[:10]}")
            continue
        success, err, abort = update_one(title, path, obj)
        if success:
            ok += 1
            os.makedirs(DONE_DIR, exist_ok=True)
            with open(done_flag, "w", encoding="utf-8") as fh:
                fh.write(title + "\n")
            print(f"[{i}/{len(items)}] ✓ {title}")
            new_written += 1
            if max_new and new_written >= max_new:
                print(f"  === 本轮新写 {new_written} 篇达单进程上限，主动退出(exit 0)供外层换新进程 ===")
                break
        else:
            failed.append((title, rel, err))
            print(f"[{i}/{len(items)}] ✗ 写入失败: {title}")
            # 代理会话已坏：立即非零退出(exit 2)，外层 shell 拉起全新进程续跑（不在原进程死等）
            if abort:
                print("  === 代理会话连续失败，立即非零退出(exit 2)，交外层换新进程 ===", flush=True)
                sys.exit(2)
        # 串行篇间间隔（保持不并发）
        time.sleep(float(os.environ.get("RESYNC_INTERVAL", "1.5")))

    print("\n========== 汇总 ==========")
    print(f"成功 {ok}，无映射 {len(missing)}，失败 {len(failed)}")
    for t, p in missing:
        print(f"  [无映射] {t} ({p})")
    for t, p, e in failed:
        print(f"  [失败] {t} ({p}): {e}")
    sys.exit(1 if (missing or failed) else 0)


if __name__ == "__main__":
    main()
