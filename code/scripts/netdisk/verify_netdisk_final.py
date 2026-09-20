#!/usr/bin/env python3
"""
网盘终态验证脚本：递归对比本地课程目录与网盘课程目录的结构、文件数、文件名集合、文件大小。

用法：
    BAIDU_ENC_PASS=xxx python3 scripts/verify_netdisk_final.py <本地课程根> <网盘课程根>

示例（路径由 course_config.sh 的 $COURSE_LOCAL_ROOT / $COURSE_REMOTE_ROOT 提供）：
    source scripts/course_config.sh
    BAIDU_ENC_PASS=<主密码> python3 scripts/verify_netdisk_final.py \
        "$COURSE_LOCAL_ROOT" "$COURSE_REMOTE_ROOT"

退出码：0=通过，1=有差异，2=参数/环境错误

比对口径：默认排除点开头隐藏/缓存目录（.ep3cache/.DS_Store 等——非学习资产，同步脚本从不上传）；
其他“本阶段不比对”的目录用 -x/--exclude 显式指定（可重复、任意层级）。名师课原始资源滚动备份阶段，
知识详解尚在生成、走飞书，不应拿半成品卡视频备份的完成判定，用 `-x 知识详解`；待课程完整 finalize、
知识详解定稿并按 finalize-sop 步骤1 传云后，再跑一次不带 -x 的两层（原始资源+知识详解）全量核验。
"""

import os
import sys
import argparse
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from baidu_upload import get_token, list_files


def scan_local(local_root, excludes=frozenset()):
    """递归扫描本地目录，返回 {相对路径: {'dirs': set, 'files': {name: size}}}。
    excludes: 调用方显式不比对的目录名（任意层级），如原始资源阶段传 {'知识详解'}。"""
    result = {}
    for dirpath, dirnames, filenames in os.walk(local_root):
        # 剪枝：点开头隐藏/缓存（.ep3cache 下载密钥缓存等）默认排除，excludes 显式排除。必须“原地”
        # 改写 dirnames[:] 才能让 os.walk 真正不递归；只在结果集过滤仍会走进 .ep3cache、把
        # keycache.json 误报为网盘缺失（2026-09-18 经济法核验唯一假差异即此）。
        dirnames[:] = [d for d in dirnames
                       if not d.startswith('.') and d not in excludes]
        rel = os.path.relpath(dirpath, local_root)
        if rel == '.':
            rel = ''
        dirs = set(dirnames)
        files = {}
        for f in filenames:
            if f.startswith('.'):
                continue
            fpath = os.path.join(dirpath, f)
            try:
                files[f] = os.path.getsize(fpath)
            except OSError:
                files[f] = -1
        result[rel] = {'dirs': dirs, 'files': files}
    return result


def scan_netdisk(netdisk_root, token, excludes=frozenset()):
    """递归扫描网盘目录，返回 {相对路径: {'dirs': set, 'files': {name: size}}}。
    excludes 与 scan_local 对称，命中的网盘目录既不收录也不递归。"""
    result = {}

    def _scan(rel_path):
        full_path = netdisk_root + '/' + rel_path if rel_path else netdisk_root
        # 抑制 list_files 的 print 输出
        with contextlib.redirect_stdout(open(os.devnull, 'w')):
            items = list_files(full_path, token)
        dirs = set()
        files = {}
        for item in items:
            name = item['server_filename']
            if item['isdir']:
                dirs.add(name)
            else:
                files[name] = item.get('size', 0)
        dirs = {d for d in dirs if d not in excludes}
        result[rel_path] = {'dirs': dirs, 'files': files}
        for d in sorted(dirs):
            next_rel = rel_path + '/' + d if rel_path else d
            _scan(next_rel)

    _scan('')
    return result


def compare(local_data, netdisk_data):
    """对比本地和网盘，返回差异列表"""
    diffs = []
    all_paths = set(local_data.keys()) | set(netdisk_data.keys())

    for path in sorted(all_paths):
        label = path if path else '(根目录)'
        l = local_data.get(path, {'dirs': set(), 'files': {}})
        n = netdisk_data.get(path, {'dirs': set(), 'files': {}})

        # 目录差异
        only_local_dirs = l['dirs'] - n['dirs']
        only_netdisk_dirs = n['dirs'] - l['dirs']
        if only_local_dirs:
            diffs.append(f"[目录缺失-网盘] {label}: 本地有但网盘无: {sorted(only_local_dirs)}")
        if only_netdisk_dirs:
            diffs.append(f"[目录多余-网盘] {label}: 网盘有但本地无: {sorted(only_netdisk_dirs)}")

        # 文件差异
        only_local_files = set(l['files'].keys()) - set(n['files'].keys())
        only_netdisk_files = set(n['files'].keys()) - set(l['files'].keys())
        if only_local_files:
            diffs.append(f"[文件缺失-网盘] {label}: 本地有但网盘无: {sorted(only_local_files)}")
        if only_netdisk_files:
            diffs.append(f"[文件多余-网盘] {label}: 网盘有但本地无: {sorted(only_netdisk_files)}")

        # 文件大小差异（共同文件）
        common_files = set(l['files'].keys()) & set(n['files'].keys())
        size_mismatch = []
        for f in sorted(common_files):
            if l['files'][f] != n['files'][f]:
                size_mismatch.append(f"{f}(本地{l['files'][f]}B vs 网盘{n['files'][f]}B)")
        if size_mismatch:
            diffs.append(f"[大小不一致] {label}: {size_mismatch}")

    return diffs


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('local_root', help='本地课程根（或要比对的子目录，如 原始资源/videos）')
    ap.add_argument('netdisk_root', help='网盘对应课程根（或子目录）')
    ap.add_argument('-x', '--exclude', action='append', default=[], metavar='DIR',
                    help='额外排除的目录名，可重复、任意层级（如原始资源阶段传 -x 知识详解）')
    a = ap.parse_args()

    local_root = a.local_root
    netdisk_root = a.netdisk_root.rstrip('/')
    excludes = frozenset(a.exclude)

    if not os.path.isdir(local_root):
        print(f"错误：本地目录不存在: {local_root}")
        sys.exit(2)

    print(f"本地课程根: {local_root}")
    print(f"网盘课程根: {netdisk_root}")
    print()

    # 获取 token
    token = get_token()
    if not token:
        print("错误：无法获取百度网盘 access_token（检查 BAIDU_ENC_PASS 环境变量）")
        sys.exit(2)
    print("Token 获取成功")
    print()

    # 扫描本地
    print("扫描本地目录...")
    local_data = scan_local(local_root, excludes)
    local_dirs = len(local_data)
    local_files = sum(len(v['files']) for v in local_data.values())
    print(f"  本地: {local_dirs} 个目录, {local_files} 个文件（已排除点开头隐藏/缓存{('、' + '、'.join(sorted(excludes))) if excludes else ''}）")
    print()

    # 扫描网盘
    print("扫描网盘目录（递归，每个目录一次 API 调用，约需 1-2 分钟）...")
    netdisk_data = scan_netdisk(netdisk_root, token, excludes)
    netdisk_dirs = len(netdisk_data)
    netdisk_files = sum(len(v['files']) for v in netdisk_data.values())
    print(f"  网盘: {netdisk_dirs} 个目录, {netdisk_files} 个文件")
    print()

    # 对比
    print("对比中...")
    diffs = compare(local_data, netdisk_data)

    # 输出结果
    print()
    print("=" * 60)
    if not diffs:
        print("✅ 验证通过：本地与网盘完全一致")
        print(f"  目录数: {local_dirs} (本地) = {netdisk_dirs} (网盘)")
        print(f"  文件数: {local_files} (本地) = {netdisk_files} (网盘)")
        sys.exit(0)
    else:
        print(f"❌ 验证失败：发现 {len(diffs)} 处差异")
        print()
        for i, d in enumerate(diffs, 1):
            print(f"  {i}. {d}")
        print()
        print("修复建议：")
        print("  - 文件缺失/多余：检查同步脚本，重新同步对应目录")
        print("  - 大小不一致：可能是上传不完整，重新覆盖上传对应文件")
        print("  - 目录差异：检查目录结构约定，确认是否为预期差异")
        sys.exit(1)


if __name__ == '__main__':
    main()
