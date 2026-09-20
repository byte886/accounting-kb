#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_ep3_videos.py — 名师课(ep3)视频批量 H.265 重压驱动（断点续跑 / 全局单实例）

背景：名师课视频由 ep3 链路 ffmpeg -c copy 原样封装为 H.264 1080P（未重压，单讲常达数百 MB~1GB）。
本脚本把仍是 H.264 的 *_video.mp4 用与正课 scripts/compress.sh 完全一致的参数重压为 H.265
（libx265 / CRF30 / preset fast / AAC 96k / hvc1 / faststart），目标"课件文字清晰、体积大幅下降"。

设计要点：
  - 幂等：压前 ffprobe 读 v:0 编码，已是 hevc 直接 skip；只有 h264（及其它非 hevc）才压。可任意重跑。
  - 安全替换：先压到同目录临时文件 .compress_tmp__<名>.mp4，验证（可解析/hevc/分辨率不变/时长容差）
    通过后才 os.replace 同名覆盖原文件（保持 <老师>_video.mp4 命名，meta/vtt/transcript/网盘判重不受影响）；
    验证失败删临时文件、保留原文件、记 failed，不中断后续。
  - 全局单实例：fcntl.flock 占用 data/_workspace/_account/ep3/compress.lock，防误开第二个互相抢核。
  - 断点续跑：每个文件结果追加 compress_state.jsonl；重跑时 hevc 即跳过，天然续跑。
  - 单实例吃满逻辑核（x265 内部多线程）；不开第二个 ffmpeg（SOP：x265 全局单实例）。
  - 与正课口径一致：COMPRESS_NONINTERACTIVE=1，时长容差 max(3s, 0.1%)。

用法：
  python3 scripts/compress_ep3_videos.py --dry-run                 # 只扫描列出待压/已压，不编码
  python3 scripts/compress_ep3_videos.py --limit 3                 # 只压前 3 个（试跑）
  python3 scripts/compress_ep3_videos.py                           # 全量（应配 nohup 后台）
  python3 scripts/compress_ep3_videos.py --course 战略 --crf 28    # 指定课/调质量
  python3 scripts/compress_ep3_videos.py --report                  # 只看进度报告
"""
import argparse, fcntl, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPA = ROOT / "data" / "高顿" / "CPA"
ACCT = ROOT / "data" / "_workspace" / "_account" / "ep3"
STATE_DIR = ACCT
LOG_DIR = ACCT / "logs"
LOCK = STATE_DIR / "compress.lock"
STATE_JSONL = STATE_DIR / "compress_state.jsonl"
LOG = LOG_DIR / "compress_ep3.log"

# 默认按体量从小到大：最快产出第一门完整成果（顺序不影响知识详解线）
DEFAULT_COURSES = ["战略", "审计", "经济法", "财管", "税法", "会计"]
TMP_PREFIX = ".compress_tmp__"


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)


def probe(path: Path):
    """返回 (vcodec,width,height,duration_sec)。"""
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1", str(path)])
    codec = w = h = None
    dur = 0.0
    for ln in r.stdout.splitlines():
        if ln.startswith("codec_name="):
            codec = ln.split("=", 1)[1]
        elif ln.startswith("width="):
            w = int(ln.split("=", 1)[1])
        elif ln.startswith("height="):
            h = int(ln.split("=", 1)[1])
        elif ln.startswith("duration="):
            try:
                dur = float(ln.split("=", 1)[1])
            except ValueError:
                pass
    return codec, w, h, dur


def find_course_dir(keyword: str):
    for d in CPA.iterdir():
        if "名师专业课" in d.name and keyword in d.name:
            return d
    return None


def collect(courses):
    """返回 [(course_kw, mp4_path)]，只收名师课 *_video.mp4。"""
    out = []
    for kw in courses:
        cdir = find_course_dir(kw)
        if not cdir:
            log(f"⚠️ 未找到课程目录：{kw}")
            continue
        vdir = cdir / "原始资源" / "videos"
        files = sorted(p for p in vdir.rglob("*_video.mp4")
                       if not p.name.startswith(TMP_PREFIX))
        out.extend((kw, p) for p in files)
    return out


def encode_one(src: Path, crf: int, preset: str, cores: int):
    tmp = src.with_name(TMP_PREFIX + src.name)
    if tmp.exists():
        tmp.unlink()
    cmd = ["ffmpeg", "-y", "-i", str(src),
           "-map", "0:v:0", "-map", "0:a:0?",
           "-c:v", "libx265", "-crf", str(crf), "-preset", preset,
           "-x265-params", f"pools={cores}:frame-threads=4:wpp=1",
           "-c:a", "aac", "-b:a", "96k",
           "-tag:v", "hvc1", "-movflags", "+faststart", str(tmp)]
    env = dict(os.environ, COMPRESS_NONINTERACTIVE="1")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, env=env)
    if r.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        return False, "ffmpeg失败: " + r.stderr[-400:]
    # 验证
    ic, iw, ih, idur = probe(src)
    oc, ow, oh, odur = probe(tmp)
    if oc != "hevc":
        tmp.unlink()
        return False, f"输出非hevc({oc})"
    if (iw, ih) != (ow, oh):
        tmp.unlink()
        return False, f"分辨率变化 {iw}x{ih}->{ow}x{oh}"
    tol = max(3.0, idur * 0.001)
    if abs(idur - odur) > tol:
        tmp.unlink()
        return False, f"时长偏差 {idur:.1f}->{odur:.1f} (tol {tol:.1f})"
    if not tmp.exists() or tmp.stat().st_size < 100_000:
        tmp.unlink()
        return False, "输出过小/缺失"
    os.replace(tmp, src)  # 同名覆盖
    return True, {"in_codec": ic, "dur": round(idur, 1),
                  "out_dur": round(odur, 1), "wh": f"{ow}x{oh}"}


def append_state(rec: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def report(files):
    n_hevc = n_h264 = n_other = 0
    sum_in = 0
    for kw, p in files:
        c, _, _, _ = probe(p)
        sz = p.stat().st_size
        if c == "hevc":
            n_hevc += 1
        elif c == "h264":
            n_h264 += 1
            sum_in += sz
        else:
            n_other += 1
    log(f"扫描 {len(files)}：已压hevc {n_hevc}，待压h264 {n_h264}（{sum_in/1e9:.1f}GB），其它 {n_other}")
    return n_h264


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--course", action="append", help="只压指定课（关键词，可多次）；默认六科")
    ap.add_argument("--crf", type=int, default=30)
    ap.add_argument("--preset", default="fast")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--min-free-gb", type=float, default=50)
    ap.add_argument("--reverse", action="store_true", help="按路径倒序压（从后往前）")
    ap.add_argument("--jobs", type=int, default=0, help="x265 pools 线程数，0=全部逻辑核（本机穿插低负载时调小）")
    args = ap.parse_args()

    courses = args.course or DEFAULT_COURSES
    files = collect(courses)
    if args.reverse:
        files.reverse()
    log(f"课程顺序 {courses}{'（倒序）' if args.reverse else ''}；扫描到 *_video.mp4 共 {len(files)}")

    if args.report or args.dry_run:
        report(files)
        return

    # 全局单实例锁
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lf = open(LOCK, "w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("❌ 已有一个压缩实例在跑（compress.lock 被占），退出。")
        sys.exit(2)

    cores = args.jobs if args.jobs and args.jobs > 0 else (os.cpu_count() or 8)
    log(f"x265 pools={cores}（逻辑核 {os.cpu_count()}）")
    done = fail = skip = 0
    t0 = time.time()
    processed = 0
    for kw, p in files:
        c, w, h, dur = probe(p)
        if c == "hevc":
            skip += 1
            continue
        # 磁盘安全阈
        free_gb = __import__("shutil").disk_usage(str(p)).free / 1e9
        if free_gb < args.min_free_gb:
            log(f"⛔ 剩余磁盘 {free_gb:.0f}GB < {args.min_free_gb}GB，暂停（已处理{processed}）")
            break
        in_sz = p.stat().st_size
        log(f"▶ 压缩 [{kw}] {p.parent.name}/{p.name} {c} {w}x{h} {in_sz/1e6:.0f}MB {dur/60:.1f}min")
        ts = time.time()
        ok, info = encode_one(p, args.crf, args.preset, cores)
        cost = time.time() - ts
        if ok:
            out_sz = p.stat().st_size
            ratio = out_sz / in_sz if in_sz else 0
            done += 1
            processed += 1
            log(f"✅ 完成 {out_sz/1e6:.0f}MB (原{in_sz/1e6:.0f}MB, {ratio*100:.0f}%) 用时{cost/60:.1f}min")
            append_state({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "course": kw,
                          "file": str(p.relative_to(ROOT)), "status": "done",
                          "in_mb": round(in_sz / 1e6, 1), "out_mb": round(out_sz / 1e6, 1),
                          "ratio": round(ratio, 3), "sec": round(cost, 1), **(info if isinstance(info, dict) else {})})
        else:
            fail += 1
            log(f"❌ 失败 {p}: {info}")
            append_state({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "course": kw,
                          "file": str(p.relative_to(ROOT)), "status": "fail", "err": str(info)})
        if args.limit and (done + fail) >= args.limit:
            log(f"达到 --limit {args.limit}，停止试跑。")
            break

    log(f"=== 本轮结束：新压{done} 跳过(已hevc){skip} 失败{fail} 总用时{(time.time()-t0)/60:.1f}min ===")
    if fail:
        log(f"⚠️ 有 {fail} 个失败，见 {STATE_JSONL} status=fail；重跑本脚本会自动重试（仍是h264）。")
        sys.exit(1)


if __name__ == "__main__":
    main()
