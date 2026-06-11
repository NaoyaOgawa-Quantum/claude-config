#!/usr/bin/env python3
"""雛形 PDF への直接印字エンジン (= office-automation.md #pdf-prefill-direct の汎用実装)。

行政・学術様式の「標題・押印マーク等が drawing の xlsx」 を openpyxl で編集すると drawing が
全消失する (#openpyxl-destroys-drawings)。 紙提出だけが必要な場合の最速安全経路 =
雛形 xlsx を Excel で PDF 化 (drawing は render 済) → その PDF に本エンジンで値を印字。

組み込み済みの安全装置 (= 2026-06-11 の印刷事故 3 連 RCA を全て機械化):
  - 座標は label 語の bbox から導出 (hardcode しない、 雛形改訂に頑健)
  - 文字照合は全て NFKC (= CJK 互換字形の false negative 回避, #pdf-text-match-nfkc)
  - `=TODAY()` 由来の `#+` overflow は redact で除去 (矩形 shrink で隣接巻き添え防止)
  - フォントは実 file 埋め込み + subset (組み込み "japan" は glyph 不描画 renderer あり)
  - 検証内蔵 (全挿入値の存在 + `##` 残存 + ページ数)
  - 印刷用に 600dpi ラスタ版も生成 (= subset font の printer RIP 化け対策, #print-raster-pdf)

使い方 (library): 様式ごとの driver script が import して使う。
    from pdf_form_fill import build_document
    build_document(template_pdf="form.pdf",
                   page_contains=["銀行振込口座"], page_not_contains=[],
                   items=[{"anchor": "所属:", "occurrence": 0, "dx": 8, "text": "〇〇学科"},
                          {"anchor": "殿", "align": "right", "dx": -4, "text": "山田 太郎"}],
                   out_base="out/dir/書類名")
  → 書類名_filled.pdf (確認用) + 書類名_raster.pdf (印刷用) を生成、 検証 fail は例外。

item の仕様:
  anchor      : ページ上の label 語 (NFKC 一致、 get_text("words") の 1 語)
  occurrence  : 同語が複数あるとき何番目か (y→x 順、 default 0)
  dx, dy      : anchor の右端 (align=left) / 左端 (align=right) からの offset (pt)
  align       : "left" (= anchor の右に置く、 default) / "right" (= text 右端を anchor 左端に合わせる)
  text        : 印字する文字列。 "\n" 区切りで複数行 (行送りは fontsize*1.45)
  size        : fontsize (default 9)
  verify      : False にすると検証対象から外す (= "✓" 等、 重複しうる短い記号用)
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path

import fitz

FONT_CANDIDATES = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]
XLSX_TO_PDF = Path(__file__).resolve().parent / "xlsx-to-pdf.sh"


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def pick_font() -> str:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    raise FileNotFoundError(f"日本語フォントが見つからない: {FONT_CANDIDATES}")


def ensure_template_pdf(template_xlsx: Path) -> Path:
    """xlsx → PDF (Excel 経由、 drawing render 済)。 PDF が新しければ再生成しない。"""
    pdf = template_xlsx.with_suffix(".pdf")
    if not pdf.exists() or pdf.stat().st_mtime < template_xlsx.stat().st_mtime:
        subprocess.run(["zsh", str(XLSX_TO_PDF), str(template_xlsx)],
                       check=True, capture_output=True)
    if not pdf.exists():
        raise RuntimeError(f"雛形 PDF 生成失敗: {template_xlsx} (Excel が必要)")
    return pdf


def find_page(doc: "fitz.Document", contains: list, not_contains: list = ()) -> int:
    """内容特徴語でページを特定 (= ページ番号 hardcode 禁止)。"""
    for i, page in enumerate(doc):
        t = nfkc(page.get_text())
        if all(c in t for c in contains) and not any(c in t for c in not_contains):
            return i
    raise LookupError(f"該当ページなし: contains={contains}")


def word_rect(page, label: str, occurrence: int = 0) -> "fitz.Rect":
    hits = [fitz.Rect(w[:4]) for w in page.get_text("words") if nfkc(w[4]) == nfkc(label)]
    hits.sort(key=lambda r: (round(r.y0), r.x0))
    if len(hits) <= occurrence:
        raise LookupError(f"anchor 語「{label}」(#{occurrence}) が見つからない (雛形改訂?)")
    return hits[occurrence]


def redact_hash_runs(page) -> int:
    """`####` 等 (= =TODAY() の列幅 overflow、 個数は出力時の列幅依存) を除去。"""
    rects = [fitz.Rect(w[:4]) for w in page.get_text("words") if re.fullmatch(r"#+", w[4])]
    for r in rects:
        page.add_redact_annot(fitz.Rect(r.x0 + 2, r.y0 + 1, r.x1, r.y1 - 1))
    if rects:
        page.apply_redactions()
    return len(rects)


def redact_words(page, words: list) -> int:
    """数式由来の不要表示 (= 例: 空参照の "0") を語単位で除去。 矩形は shrink。"""
    rects = [fitz.Rect(w[:4]) for w in page.get_text("words") if w[4] in words]
    for r in rects:
        page.add_redact_annot(fitz.Rect(r.x0 + 0.5, r.y0 + 0.5, r.x1 - 0.5, r.y1 - 0.5))
    if rects:
        page.apply_redactions()
    return len(rects)


def build_document(template_pdf, page_contains, items, out_base,
                   page_not_contains=(), drop_words=(), dpi=600) -> dict:
    """1 書類 (= 1 ページ) を生成。 return = {"filled": path, "raster": path}。"""
    font = pick_font()
    src = fitz.open(str(template_pdf))
    pno = find_page(src, list(page_contains), list(page_not_contains))
    doc = fitz.open()
    doc.insert_pdf(src, from_page=pno, to_page=pno)
    page = doc[0]

    redact_hash_runs(page)
    if drop_words:
        redact_words(page, list(drop_words))

    for it in items:
        r = word_rect(page, it["anchor"], it.get("occurrence", 0))
        size = it.get("size", 9)
        F = dict(fontname="JPF", fontfile=font, fontsize=size)
        lines = str(it["text"]).split("\n")
        if it.get("align", "left") == "right":
            width = max(fitz.get_text_length(ln, fontfile=font, fontsize=size) for ln in lines)
            x = r.x0 - width + it.get("dx", -4)
        else:
            x = r.x1 + it.get("dx", 6)
        y = r.y1 + it.get("dy", 0)
        for ln in lines:
            page.insert_text((x, y), ln, **F)
            y += size * 1.45

    doc.subset_fonts()
    out_filled = Path(f"{out_base}_filled.pdf")
    out_filled.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_filled, garbage=3, deflate=True)

    # --- 検証 (機械層): 全値の存在 (NFKC) + ## 残存 + ページ数 ---
    t = nfkc(fitz.open(out_filled)[0].get_text())
    expected = [str(it["text"]).replace("\n", "") for it in items if it.get("verify", True)]
    missing = [e for e in expected if nfkc(e).replace(" ", "") not in t.replace(" ", "").replace("\n", "")]
    if missing or "##" in t or fitz.open(out_filled).page_count != 1:
        raise AssertionError(f"検証 FAIL ({out_base}): missing={missing} hash={'##' in t}")

    # --- 印刷用ラスタ (WYSIWYG 保証) ---
    pg = fitz.open(out_filled)[0]
    png = out_filled.with_suffix(".tmp.png")
    pg.get_pixmap(dpi=dpi).save(png)
    rast = fitz.open()
    np_ = rast.new_page(width=pg.rect.width, height=pg.rect.height)
    np_.insert_image(np_.rect, filename=str(png))
    out_raster = Path(f"{out_base}_raster.pdf")
    rast.save(out_raster, deflate=True)
    png.unlink()
    return {"filled": out_filled, "raster": out_raster}
