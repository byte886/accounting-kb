#!/usr/bin/env python3
"""ocr_pdf_rapid.py — RapidOCR (PP-OCRv6) 批量 PDF → Markdown

替换原 macOS Vision 方案。优势：跨平台、pip 一条命令装、中文/数字混排更准。

用法:
  .venv-ocr/bin/python scripts/ocr/ocr_pdf_rapid.py <pdf路径> [--out <md路径>] [--dpi 200]

输出格式与旧 batch_ocr.sh 一致：
  # <书名>（OCR文字稿）
  > 自动OCR识别 | 共N页 | 使用 RapidOCR PP-OCRv6
  ---
  ## 第1页
  <文本>
  ---
  ## 第2页
  ...

断点续跑：同目录 <pdf名>.pages/<N>.txt 存在且非空则跳过。
"""
import argparse, sys, time, re
from pathlib import Path
import pymupdf
from rapidocr import RapidOCR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", help="输出md路径，默认同目录 <pdf名>_OCR.md")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-pages", type=int, default=0, help="0=全部")
    args = ap.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        sys.exit(f"PDF不存在: {pdf_path}")

    out_md = Path(args.out).resolve() if args.out else pdf_path.with_name(pdf_path.stem + "_OCR.md")
    cache_dir = pdf_path.parent / (pdf_path.stem + ".pages")
    cache_dir.mkdir(exist_ok=True)

    doc = pymupdf.open(str(pdf_path))
    total = doc.page_count
    if args.max_pages > 0:
        total = min(total, args.max_pages)

    print(f"[rapidocr] PDF: {pdf_path.name}  总页: {total}  输出: {out_md}", flush=True)

    # 懒加载模型（首次约2-3s）
    t0 = time.time()
    ocr = RapidOCR()
    print(f"[rapidocr] 模型加载: {time.time()-t0:.1f}s", flush=True)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# {pdf_path.stem}（OCR文字稿）\n\n")
        f.write(f"> 自动OCR识别 | 共{total}页 | 使用 RapidOCR PP-OCRv6 | DPI {args.dpi}\n\n")

        success = skipped = failed = 0
        t_start = time.time()
        for i in range(total):
            page_no = i + 1
            cache = cache_dir / f"{page_no:04d}.txt"

            if cache.exists() and cache.stat().st_size > 0:
                text = cache.read_text(encoding="utf-8")
                skipped += 1
            else:
                # PDF → 图片 → OCR
                page = doc[i]
                mat = pymupdf.Matrix(args.dpi / 72, args.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")

                t1 = time.time()
                result = ocr(img_bytes)
                dt = time.time() - t1
                lines = list(result.txts) if result.txts else []
                text = "\n".join(lines) if lines else "（本页无文字或为纯图片）"
                cache.write_text(text, encoding="utf-8")
                success += 1
                if page_no % 10 == 0 or page_no == total:
                    elapsed = time.time() - t_start
                    eta = (elapsed / success) * (total - success - skipped)
                    print(f"  [{page_no}/{total}] 成功{success} 跳过{skipped} 失败{failed} "
                          f"本页{dt:.1f}s 已用{elapsed:.0f}s ETA{eta:.0f}s", flush=True)

            f.write("---\n")
            f.write(f"## 第{page_no}页\n\n")
            f.write(text + "\n\n")

    doc.close()

    # 后处理：常见错字
    text_all = out_md.read_text(encoding="utf-8")
    text_all = text_all.replace("高顿教意", "高顿教育").replace("高顿教肓", "高顿教育")
    out_md.write_text(text_all, encoding="utf-8")

    dur = time.time() - t_start
    print(f"[rapidocr] 完成: 成功{success} 跳过{skipped} 失败{failed} 总耗时{dur:.0f}s "
          f"输出{out_md.stat().st_size//1024}KB", flush=True)


if __name__ == "__main__":
    main()
