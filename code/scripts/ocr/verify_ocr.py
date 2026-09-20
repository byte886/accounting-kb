#!/usr/bin/env python3
"""verify_ocr.py — 复核讲义 OCR 完整性：每份 docs/*.pdf 的实际页数，
应与 docs_text/<名>_OCR.md 中 `## 第N页` 分节数一致（允许相等；少于即残缺）。
用法: code/venvs/transcription/bin/python scripts/ocr/verify_ocr.py
输出: 逐份 OK/残缺清单 + 汇总，残缺时退出码 1。
"""
import re, sys, pathlib, os
import pymupdf  # PyMuPDF 1.28

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "scripts", "knowledge"))
from course_profile import load_profile  # noqa: E402
# 课程目录：env COURSE_LOCAL_ROOT 优先，否则读 profile（data/高顿 为项目内实体目录，ADR-021）
_rel = os.environ.get("COURSE_LOCAL_ROOT", load_profile()["paths"]["localRoot"])
COURSE = pathlib.Path(_rel) if os.path.isabs(_rel) else pathlib.Path(_REPO) / _rel
SEC = re.compile(r"^## 第\d+页", re.M)

def main():
    ok, bad, missing, dup = 0, [], [], 0
    pdfs = sorted(COURSE.glob("[0-9][0-9]_*/docs/*.pdf"))
    for pdf in pdfs:
        lec = pdf.parent.parent
        md = lec / "docs_text" / (pdf.stem + "_OCR.md")
        try:
            pages = pymupdf.open(str(pdf)).page_count
        except Exception as e:
            bad.append((pdf.name, f"PDF无法读取:{e}")); continue
        if not md.exists():
            # run_ocr_all 统一跳过「课件_」旧命名件：若同目录另有其它 PDF（即新版同源件），判为重复豁免
            siblings = [x for x in pdf.parent.glob("*.pdf") if x.name != pdf.name]
            if pdf.stem.startswith("课件_") and siblings:
                dup += 1; continue
            missing.append((lec.name, pdf.name, pages)); continue
        secs = len(SEC.findall(md.read_text(encoding="utf-8", errors="ignore")))
        if secs >= pages:
            ok += 1
        else:
            bad.append((f"{lec.name}/{pdf.name}", f"页数{pages} 分节{secs} 缺{pages-secs}"))
    print(f"PDF总数 {len(pdfs)} | 完整 {ok} | 重复旧件豁免 {dup} | 缺OCR文件 {len(missing)} | 残缺 {len(bad)}")
    for lec, name, p in missing:
        print(f"  [缺文件] {lec}/{name} ({p}页)")
    for name, why in bad:
        print(f"  [残缺] {name} -> {why}")
    sys.exit(1 if (bad or missing) else 0)

if __name__ == "__main__":
    main()
