#!/usr/bin/env python3
"""pdf-grayscale-copy.py — PDF の頁を「複写機で写したもの」 相当の白黒の写しにする (raster・圧縮・紙専用の印を引き継ぐ)。

窓口が原本でなく**写し**を求める書類 (原本は本人の控え) を、 紙に刷らずにファイルで出すための形。
色の印影を重ねた PDF (overlay-seal-pdf.py の出力) をこの道具に通すと、 印影ごと白黒の画素に焼かれ、
出口の gate (check-seal-attachments.py --allow-monochrome-copy) が「白黒の写し」 として通す。

    pdf-grayscale-copy.py IN.pdf --out OUT.pdf [--pages 3] [--dpi 300]
    pdf-grayscale-copy.py --selftest

- 既定 300 dpi・頁ごとに PNG の stream + deflate で埋める = 1 頁で数百 KB。 ⚠️ pixmap をそのまま埋めると
  圧縮されず 600 dpi で 1 頁 35 MB になり、 メールの上限 (25 MB) を超えて配達されない (実測)。
- 入力の PDF Keywords の紙専用の印 (`paper-only:seal-image`) は出力へ引き継ぐ (印影の有無の記録を落とさない)。
- --pages は 1 始まり (例: 3 / 1-2,4)。 省略 = 全頁。
規約 = conventions/office-automation.md#seal-artifact-marker (例外 2)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))


def parse_pages(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, int(b)))
        elif part:
            out.append(int(part) - 1)
    bad = [p + 1 for p in out if not 0 <= p < n]
    if bad:
        raise ValueError(f"頁が範囲外: {bad} (全 {n} 頁)")
    return out


def make_copy(src_path: str, out_path: str, pages: str | None = None, dpi: int = 300) -> int:
    import fitz
    from seal_artifact import copy_marker
    src = fitz.open(src_path)
    out = fitz.open()
    for i in parse_pages(pages, len(src)):
        page = src[i]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        np_ = out.new_page(width=page.rect.width, height=page.rect.height)
        np_.insert_image(np_.rect, stream=pix.tobytes("png"))
    copy_marker(src, out)
    out.save(out_path, deflate=True, garbage=4)
    return os.path.getsize(out_path)


def _selftest() -> int:
    import tempfile
    import fitz
    from seal_artifact import has_marker, is_monochrome_copy, mark_doc
    d = tempfile.mkdtemp()
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {label}")
        ok = ok and bool(cond)

    src = os.path.join(d, "form.pdf")
    doc = fitz.open()
    for k in range(3):
        pg = doc.new_page()
        pg.insert_text((72, 72), f"page {k + 1}")
        pg.draw_circle((300, 300), 14, color=(0.8, 0.1, 0.1), fill=(0.85, 0.15, 0.1))
    mark_doc(doc)
    doc.save(src)
    out = os.path.join(d, "copy.pdf")
    size = make_copy(src, out, "3")
    res = fitz.open(out)
    check("指定した頁だけ (1 頁)", len(res) == 1)
    check("紙専用の印を引き継ぐ", has_marker(out))
    check("色のある画素が無い = 白黒の写し", is_monochrome_copy(out))
    check("圧縮されている (1 頁 1 MB 未満)", size < 1_000_000)
    check("元の PDF は色つき (白黒の写しではない)", not is_monochrome_copy(src))
    try:
        parse_pages("5", 3)
        check("範囲外の頁は止める", False)
    except ValueError:
        check("範囲外の頁は止める", True)
    print(f"pdf-grayscale-copy selftest: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.pdf or not a.out:
        ap.error("IN.pdf と --out が要る")
    if os.path.abspath(a.pdf) == os.path.abspath(a.out):
        ap.error("--out は入力と別の path にする")
    size = make_copy(a.pdf, a.out, a.pages, a.dpi)
    print(f"{a.out}: {size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
