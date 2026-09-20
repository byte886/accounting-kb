#!/usr/bin/env python3
"""解析 verify_netdisk_final.py 的日志，按 notes/videos/垃圾/噪声 分类汇总待传项。
用法: python3 scripts/netdisk_verify_summary.py logs/netdisk_verify_<course>.log [...]
"""
import sys, re, ast, collections

def categorize(path):
    if ('知识详解' in path) or ('.ep3cache' in path) or ('.DS_Store' in path):
        return 'noise'
    if '_work' in path or '.dec.ts' in path:
        return 'junk'
    if '/notes' in path or path.startswith('原始资源/notes'):
        return 'notes'
    if '/videos' in path:
        return 'videos'
    return 'other'

def is_video(name):
    return name.endswith('_video.mp4') or name == 'video.mp4' or name.endswith('.mp4')

line_re = re.compile(r'^\s*\d+\.\s*\[(.*?)\]\s*(.*?):\s*(.*)$')
sz_re = re.compile(r'^(.*?)\(本地(\d+)B vs 网盘(\d+)B\)$')

def parse(path):
    s = collections.Counter()
    miss_videos = set(); mismatch_video = 0; mismatch_video_older = 0
    miss_lecture_dirs = 0; miss_companion = 0; notes_miss = 0; notes_mis = 0
    junk_files = 0
    cur = None
    for raw in open(path, encoding='utf-8'):
        m = line_re.match(raw.rstrip('\n'))
        if not m:
            continue
        kind, rel, payload = m.group(1), m.group(2), m.group(3)
        # 剥掉 "本地有但网盘无: " / "网盘有但本地无: " 等中文前缀，定位到列表起始 '['
        bi = payload.find('[')
        if bi >= 0:
            payload = payload[bi:]
        cat = categorize(rel)
        if kind == '目录缺失-网盘':
            if cat == 'videos':
                try:
                    miss_lecture_dirs += len(ast.literal_eval(payload))
                except Exception:
                    pass
            continue
        if kind in ('文件多余-网盘', '目录多余-网盘'):
            if cat == 'junk':
                try:
                    items = ast.literal_eval(payload)
                    junk_files += len(items)
                except Exception:
                    junk_files += 1
            continue
        if kind == '文件缺失-网盘':
            try:
                items = ast.literal_eval(payload)
            except Exception:
                continue
            for f in items:
                c = categorize(rel + '/' + f)
                if c == 'notes':
                    notes_miss += 1
                elif c == 'videos':
                    if is_video(f):
                        miss_videos.add(rel + '/' + f)
                    else:
                        miss_companion += 1
            continue
        if kind == '大小不一致':
            # payload 是 Python 风格列表字符串
            try:
                items = ast.literal_eval(payload)
            except Exception:
                items = [payload]
            for it in items:
                mm = sz_re.match(it.strip())
                if not mm:
                    continue
                name, loc, net = mm.group(1), int(mm.group(2)), int(mm.group(3))
                c = categorize(rel + '/' + name)
                if c == 'notes':
                    notes_mis += 1
                elif c == 'videos' and is_video(name):
                    mismatch_video += 1
                    if net > loc:
                        mismatch_video_older += 1
    return dict(notes_miss=notes_miss, notes_mismatch=notes_mis,
                miss_video_files=len(miss_videos), mismatch_video=mismatch_video,
                mismatch_older=mismatch_video_older, miss_lecture_dirs=miss_lecture_dirs,
                miss_companion=miss_companion, junk_files=junk_files)

if __name__ == '__main__':
    hdr = ['课程', '讲义缺', '讲义不一致', '视频缺(文件)', '视频大小不一致', '其中网盘是旧大版', '缺讲目录', '缺配套(vtt等)', '网盘垃圾分片']
    print('\t'.join(hdr))
    tot = collections.Counter()
    for p in sys.argv[1:]:
        r = parse(p)
        name = p.split('netdisk_verify_')[-1].replace('.log', '')
        print('\t'.join(map(str, [name, r['notes_miss'], r['notes_mismatch'], r['miss_video_files'],
                                  r['mismatch_video'], r['mismatch_older'], r['miss_lecture_dirs'],
                                  r['miss_companion'], r['junk_files']])))
        for k, v in r.items():
            tot[k] += v
    print('合计\t' + '\t'.join(str(tot[k]) for k in
          ['notes_miss', 'notes_mismatch', 'miss_video_files', 'mismatch_video', 'mismatch_older',
           'miss_lecture_dirs', 'miss_companion', 'junk_files']))
