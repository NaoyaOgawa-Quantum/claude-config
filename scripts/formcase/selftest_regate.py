"""regate.py (今ある出力を今の関門に通し直す / 刷る直前の受け入れ) の fixture test。 ``formcase.py --selftest`` から呼ばれる。

合成の instance (selftest.py の spec ``fx``) の雛形に図形の字を 1 つ足し、 その字の在る出力・無い出力・raster を作って、
判定・窓口より手前かどうかの分類・cache の無効化・案件の探し方・受け入れの終了値を確かめる。 Office は使わない。
判定の cache は tmp に向ける (XDG_CACHE_HOME) = 手元の cache を汚さない。
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from . import config as CF
from . import lifecycle as L
from . import manifest as M
from . import regate as RG
from . import specs as S

SHAPE_TEXT = "区分の枠の字"
LABELS = ("申請者の氏名", "所属の名称", "用務の内容")      # 合成の雛形の 1 頁目に足す見出し (頁を見つける手掛かり)


G2_LABELS = ("上段", "内訳", "label")                             # 合成の雛形の g2 の sheet に元から在る見出し


def _pdf(path: Path, with_shape: bool, extra: str = "", labels=LABELS) -> Path:
    import fitz

    d = fitz.open()
    pg = d.new_page()
    y = 60
    for t in tuple(labels) + ((SHAPE_TEXT,) if with_shape else ()) + ((extra,) if extra else ()):
        pg.insert_text((50, y), t, fontname="japan", fontsize=10)
        y += 18
    d.save(str(path))
    d.close()
    return path


def _raster(src: Path, dst: Path) -> Path:
    import fitz

    s = fitz.open(str(src))
    o = fitz.open()
    for pg in s:
        np_ = o.new_page(width=pg.rect.width, height=pg.rect.height)
        np_.insert_image(np_.rect, pixmap=pg.get_pixmap(dpi=36))
    o.save(str(dst))
    return dst


def run_regate_tests(tmp: Path, inst: Path, expect) -> None:
    from .selftest import MAIN, _inject_drawing, _mark_mac, _sheet_part

    lib = str(Path(__file__).resolve().parent.parent / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import fitz
    import print_pages as PP

    spec = S.get("fx")
    tpl = S.template_path(spec)
    tpl_bytes = tpl.read_bytes()
    spec_path = Path(spec["_path"])
    spec_bytes = spec_path.read_bytes()
    saved_cache = os.environ.get("XDG_CACHE_HOME")
    os.environ["XDG_CACHE_HOME"] = str(tmp / "cache")
    try:
        import warnings

        import openpyxl

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wbt = openpyxl.load_workbook(tpl)
            for i, t in enumerate(LABELS):
                wbt[MAIN][f"B{3 + i}"] = t
            wbt.save(tpl)
        _inject_drawing(tpl, _sheet_part(tpl, MAIN), SHAPE_TEXT)
        case = tmp / "repo-a" / "docs" / "2026-05-05-regate"
        case.mkdir(parents=True)
        shutil.copy2(tmp / "repo-a" / "docs" / "2026-01-01-case-a" / "book.xlsx", case / "book.xlsx")
        _mark_mac(case / "book.xlsx")
        _pdf(case / "g1.pdf", with_shape=False)            # 図形の字が無い出力 = 関門が入る前の世代
        _pdf(case / "g2.pdf", with_shape=False, labels=G2_LABELS)      # g2 の sheet に図形は無い = 通る出力
        data = {"schema": M.SCHEMA, "case": case.name,
                "documents": {"d1": {"form": "fx", "workbook": "book.xlsx",
                                     "groups": {"g1": {"current": {"state": "draft", "outputs": {"print": "g1.pdf"}}},
                                                "g2": {"current": {"state": "draft", "outputs": {"print": "g2.pdf"}}}}}}}
        (case / M.MANIFEST_NAME).write_text(M.dump_text(data), encoding="utf-8")
        m = M.load(case)

        # --- 1 つの出力の判定 --------------------------------------------------------
        bad = RG.evaluate(m, "d1", "g1", case / "g1.pdf")
        good = RG.evaluate(m, "d1", "g1", _pdf(tmp / "good.pdf", with_shape=True))
        expect("regate: 雛形の図形の字が無い出力 = fail (理由に図形の字)、 在る出力 = pass (素刷りなし = partial)",
               bad["verdict"] == RG.FAIL and "図形の字" in bad["reason"] and good["verdict"] == RG.PASS and good["partial"],
               (bad, good))
        ras = RG.evaluate(m, "d1", "g1", _raster(case / "g1.pdf", tmp / "ras.pdf"))
        expect("regate: text 層の無い PDF (raster) と無い file は na (照合できない、 pass と言わない)",
               ras["verdict"] == RG.NA and "raster" in ras["reason"]
               and RG.evaluate(m, "d1", "g1", case / "nope.pdf")["verdict"] == RG.NA, ras)

        # --- cache: 同じ出力は 2 回目は cache、 関門の入力 (spec) が変われば通し直す ---------------
        again = RG.evaluate(m, "d1", "g1", case / "g1.pdf")
        spec_path.write_bytes(spec_bytes + b"\n# selftest: spec changed\n")
        CF._invalidate()
        after = RG.evaluate(M.load(case), "d1", "g1", case / "g1.pdf")
        spec_path.write_bytes(spec_bytes)
        CF._invalidate()
        expect("regate: 同じ出力の 2 回目は cache / spec が変わると指紋が変わり通し直す (判定を持ち越さない)",
               again["cached"] and again["verdict"] == RG.FAIL and not after["cached"] and after["verdict"] == RG.FAIL,
               (again["cached"], after["cached"]))
        m = M.load(case)

        # --- 窓口より手前か / 提出済みか -----------------------------------------------
        f_draft = RG.findings(m)
        expect("regate: draft の出力が在って今の関門に落ちる = 🔴 (窓口より手前)。 通る出力の group は何も言わない",
               [x[0] for x in f_draft] == [M.FAIL] and f_draft[0][1] == "d1/g1" and "窓口より手前" in f_draft[0][2], f_draft)
        L.freeze(m, "d1", "g1", "sent", date="2026-05-05", paper="unverified", paper_diff="相手が刷る")
        m.save()
        m = M.load(case)
        f_sent = RG.findings(m)
        expect("regate: sent (送っただけ = 窓口に届いていない) の凍結 issue も 🔴 のまま (凍結は今の関門の免除ではない)",
               [x[0] for x in f_sent] == [M.FAIL] and "sent 2026-05-05" in f_sent[0][2], f_sent)
        L.annotate(m, "d1", "g1", gate_waiver="本人「このまま出してよい」")
        m.save()
        m = M.load(case)
        f_waived = RG.findings(m)
        cur = m.group("d1", "g1")["current"]
        expect("regate: gate_waiver (そのまま出すと決めた人の言葉) を書いた issue は 📄 (件数に入れない)、 日付つきで残る",
               [x[0] for x in f_waived] == [M.PAPER] and "このまま出してよい" in f_waived[0][2]
               and str(cur.get("gate_waiver", "")).startswith("20"), (f_waived, cur.get("gate_waiver")))
        adm_w = RG.admit(case / "g1.pdf")
        expect("admit: waiver のある issue の出力は通す (📄 の行つき)", adm_w["status"] == RG.OK and adm_w["lines"][0].startswith("📄"), adm_w)
        L.annotate(m, "d1", "g1", gate_waiver="")
        m.save()
        m = M.load(case)
        expect("regate: gate_waiver を空文字で消すと 🔴 に戻る",
               "gate_waiver" not in m.group("d1", "g1")["current"] and [x[0] for x in RG.findings(m)] == [M.FAIL])
        L.freeze(m, "d1", "g1", "submitted", date="2026-05-06", paper="unverified", paper_diff="相手が出した")
        m.save()
        m = M.load(case)
        sub = RG.submitted_failures(m)
        expect("regate: submitted (窓口に届いた) は 🔴 にしない = 落ちる出力の一覧だけ (出し直すかは人が決める)",
               not RG.findings(m) and [r["file"] for r in sub] == ["g1.pdf"] and sub[0]["stage"] == "submitted", (RG.findings(m), sub))

        # --- 受け入れ (admit): 今の issue / 前の issue / 派生物 / 写し / 無関係の PDF -------------
        adm_bad = RG.admit(case / "g1.pdf")
        adm_ok = RG.admit(case / "g2.pdf")
        expect("admit: 今の issue の出力は判定どおり (落ちる = block + 直し方 / 通る = ok)",
               adm_bad["status"] == RG.BLOCK and any("reopen" in x for x in adm_bad["lines"]) and adm_ok["status"] == RG.OK,
               (adm_bad, adm_ok))
        L.reopen(m, "d1", "g1", "関門に落ちる世代を作り直す", date="2026-05-07")
        m.save()
        m = M.load(case)
        new_rel = m.group("d1", "g1")["current"]["outputs"]["print"]
        _pdf(case / new_rel, with_shape=True)
        adm_prev = RG.admit(case / "g1.pdf")
        adm_new = RG.admit(case / new_rel)
        expect("admit: reopen で置き換えた前の issue の出力は止め、 今の版の名前を言う / 新しい issue の出力は通す",
               adm_prev["status"] == RG.BLOCK and "前の issue" in adm_prev["lines"][0] and new_rel in adm_prev["lines"][0]
               and adm_new["status"] == RG.OK, (adm_prev, adm_new))
        expect("regate: 作り直して通る出力になれば findings は空 (前の issue の出力は findings に数えない)", not RG.findings(m), RG.findings(m))
        rows_all = RG.sweep(m, "all")
        expect("regate --scope all: 前の issue の出力も行に出る (stage = superseded、 fail)",
               any(r["stage"] == "superseded" and r["verdict"] == RG.FAIL and r["file"] == "g1.pdf" for r in rows_all), rows_all)

        outside = tmp / "scratch"
        outside.mkdir()
        # 派生物 (raster): 宣言の origin から元の出力を辿る
        der = _raster(case / new_rel, outside / "der.pdf")
        d = fitz.open(str(der))
        PP.write_record(d, [{"role": "submit", "label": "x"}], f"pdf-print-preflight --pages 1 ({new_rel})",
                        origin=PP.file_origin(str(case / new_rel)))
        d.save(str(outside / "der_decl.pdf"))
        adm_der = RG.admit(outside / "der_decl.pdf")
        expect("admit: 案件 dir の外の派生物 (raster) は宣言の origin から元の出力を辿り、 元の判定に従う",
               adm_der["status"] == RG.OK and "派生物" in adm_der["lines"][0], adm_der)
        old_der = fitz.open(str(_raster(case / "g1.pdf", outside / "old_der.pdf")))
        PP.write_record(old_der, [{"role": "submit", "label": "x"}], "pdf-print-preflight --pages 1 (g1.pdf)",
                        origin=PP.file_origin(str(case / "g1.pdf")))
        old_der.save(str(outside / "old_der_decl.pdf"))
        adm_old_der = RG.admit(outside / "old_der_decl.pdf")
        expect("admit: 前の issue の出力から作った派生物も止める", adm_old_der["status"] == RG.BLOCK and "前の issue" in adm_old_der["lines"][0],
               adm_old_der)
        _pdf(case / new_rel, with_shape=True, extra="作り直した版")     # 派生の後に元を作り直す (draft の出力は書き換わる)
        adm_stale = RG.admit(outside / "der_decl.pdf")
        expect("admit: 派生物を作った後に元の出力が作り直されていれば止める (古い版の raster を刷らせない)",
               adm_stale["status"] == RG.BLOCK and "作り直されている" in adm_stale["lines"][0], adm_stale)
        # origin の無い旧い派生物: src の「(元.pdf)」 の名前で全案件から探す
        legacy = fitz.open(str(_raster(case / "g1.pdf", outside / "legacy.pdf")))
        PP.write_record(legacy, [{"role": "submit", "label": "x"}], "pdf-print-preflight --pages 1 (g1.pdf)")
        legacy.save(str(outside / "legacy_decl.pdf"))
        adm_legacy = RG.admit(outside / "legacy_decl.pdf")
        expect("admit: origin を持たない旧い派生物は、 宣言の src の file 名で案件を探して同じ判定 (前の issue = 止める)",
               adm_legacy["status"] == RG.BLOCK, adm_legacy)
        # 出力と同じ bytes の写しは案件に結ぶ / 同じ名前でも中身の違う宣言なしの PDF は無関係
        shutil.copy2(case / "g2.pdf", outside / "g2.pdf")
        other = outside / "x"
        other.mkdir()
        _pdf(other / "g2.pdf", with_shape=False, extra="別の文書", labels=G2_LABELS)
        adm_copy = RG.admit(outside / "g2.pdf")
        adm_other = RG.admit(other / "g2.pdf")
        adm_none = RG.admit(_pdf(outside / "memo.pdf", with_shape=False))
        expect("admit: 出力と同じ bytes の写しは案件の出力として判定 / 同じ名前で中身の違う PDF・無関係の PDF には何も言わない",
               adm_copy["status"] == RG.OK and adm_other["status"] == RG.NOT_FORMCASE and adm_none["status"] == RG.NOT_FORMCASE
               and not adm_none["lines"], (adm_copy, adm_other, adm_none))
        # formcase の宣言を持つのに、 どの案件の出力でもない file = unknown (止めるかは呼び元 = 刷る直前の gate が世代を見て決める)
        orphan = fitz.open(str(_raster(case / "g1.pdf", outside / "orphan_src.pdf")))
        PP.write_record(orphan, [{"role": "submit", "label": "x"}], "formcase fx/g1")
        orphan.save(str(outside / "orphan.pdf"))
        expect("admit: formcase の宣言を持つが案件に辿れない file は unknown (ok とも not-formcase とも言わない)",
               RG.admit(outside / "orphan.pdf")["status"] == RG.UNKNOWN)

        # --- 押印を紙に実物で押す運用 (seal_mode: physical) で、 印影の画像入りの出力 = 前の運用の世代 ----------
        import seal_artifact as SA

        sealed = fitz.open(str(_pdf(tmp / "sealed_src.pdf", with_shape=False, labels=G2_LABELS)))
        sealed[0].draw_circle((300, 300), 20, color=(1, 0, 0), fill=(1, 0, 0))
        SA.mark_doc(sealed)
        sealed.save(str(tmp / "sealed.pdf"))
        cfg = CF.cfg()
        prev_mode = cfg.get("seal_mode")
        try:
            cfg["seal_mode"] = "physical"
            ev_seal = RG.evaluate(m, "d1", "g2", tmp / "sealed.pdf", use_cache=False)
            cfg["seal_mode"] = "image"
            ev_image = RG.evaluate(m, "d1", "g2", tmp / "sealed.pdf", use_cache=False)
        finally:
            cfg["seal_mode"] = prev_mode
        expect("regate: seal_mode physical では印影の画像入りの印を持つ出力は fail (前の運用の世代)、 image の運用なら pass",
               ev_seal["verdict"] == RG.FAIL and "印影" in ev_seal["reason"] and ev_image["verdict"] == RG.PASS, (ev_seal, ev_image))

        # --- CLI の終了値 ---------------------------------------------------------------
        sp = importlib.util.spec_from_file_location("formcase_cli_regate", Path(__file__).resolve().parents[1] / "formcase.py")
        cli = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(cli)
        import contextlib
        import io

        def run_cli(argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = cli.main(argv)
            return rc, buf.getvalue()
        rc_ok, _ = run_cli(["admit", str(case / "g2.pdf")])
        rc_blk, out_blk = run_cli(["admit", str(case / "g1.pdf")])
        rc_unk, _ = run_cli(["admit", str(outside / "orphan.pdf")])
        rc_nf, out_nf = run_cli(["admit", str(outside / "memo.pdf")])
        expect("CLI admit: 通す = 0 / 止める = 1 (理由つき) / 照合できない = 3 / formcase の出力でない = 0 で無言",
               (rc_ok, rc_blk, rc_unk, rc_nf) == (0, 1, 3, 0) and "🔴" in out_blk and not out_nf.strip(),
               (rc_ok, rc_blk, rc_unk, rc_nf, out_nf))
        rc_clean, out_clean = run_cli(["regate", str(case)])
        m2 = M.load(case)
        m2.group("d1", "g1")["current"]["outputs"]["print"] = "g1.pdf"     # 落ちる出力を今の draft の出力に戻す
        m2.group("d1", "g1")["previous"] = []
        m2.save()
        rc_bad, out_bad = run_cli(["regate", str(case)])
        expect("CLI regate: 窓口より手前の出力が全部通れば exit 0 / 落ちる出力が在れば exit 1 + 🔴 の行と直し方",
               rc_clean == 0 and rc_bad == 1 and "🔴" in out_bad and "reopen → build" in out_bad, (rc_clean, rc_bad, out_bad[-300:]))

        # --- 記入内容 gate: 窓口より手前の凍結 issue は、 今の spec の gate を免除しない (提出済みは裁かない) ------------
        cfg = CF.cfg()
        prev_gates, prev_default = cfg.get("gates"), cfg.get("default_gates")
        gate = inst / "gate_t.py"
        try:
            cfg["gates"] = [{"id": "t", "script": "gate_t.py", "label": "合成の記入内容 gate"}]
            cfg["default_gates"] = ["t"]
            gate.write_text("import sys\nprint('✅ 合成 gate: 通る')\nsys.exit(0)\n", encoding="utf-8")
            case2 = tmp / "repo-a" / "docs" / "2026-06-06-regate-content"
            case2.mkdir(parents=True)
            shutil.copy2(case / "book.xlsx", case2 / "book.xlsx")
            _pdf(case2 / "g2.pdf", with_shape=False, labels=G2_LABELS)
            (case2 / M.MANIFEST_NAME).write_text(M.dump_text({
                "schema": M.SCHEMA, "case": case2.name,
                "documents": {"d1": {"form": "fx", "workbook": "book.xlsx",
                                     "groups": {"g2": {"current": {"state": "draft", "outputs": {"print": "g2.pdf"}}}}}}}),
                encoding="utf-8")
            mc = M.load(case2)
            L.freeze(mc, "d1", "g2", "printed", date="2026-06-06", paper="same")
            mc.save()
            mc = M.load(case2)
            rows_ok = RG.sweep(mc, "pre")
            expect("記入内容 gate: 窓口より手前の issue には今の spec の gate の行が付く (通れば ✅、 findings は空)",
                   any(r["role"] == RG.CONTENT_ROLE and r["verdict"] == RG.PASS for r in rows_ok) and not RG.findings(mc),
                   (rows_ok, RG.findings(mc)))
            # 凍結の後に規則 (gate) が変わった = 指紋が変わり、 刷っただけの issue は 🔴 になる
            gate.write_text("import sys\nprint('🔴 合成 gate: 規則が変わり、 この記入は通らない')\nsys.exit(1)\n", encoding="utf-8")
            f_rule = RG.findings(mc)
            adm_rule = RG.admit(case2 / "g2.pdf")
            expect("記入内容 gate: 凍結の後に規則が変われば、 刷っただけ (printed) の issue は 🔴 + 刷る前の受け入れも止める",
                   [x[0] for x in f_rule] == [M.FAIL] and "記入内容" in f_rule[0][2]
                   and adm_rule["status"] == RG.BLOCK and any("規則が変わり" in x for x in adm_rule["lines"]), (f_rule, adm_rule))
            gate.unlink()
            f_gone = RG.findings(mc)
            rows_gone = [r for r in RG.sweep(mc, "pre") if r["role"] == RG.CONTENT_ROLE]
            expect("記入内容 gate: gate が走らない (script が無い) のは na = 違反と言わない",
                   not [x for x in f_gone if x[0] == M.FAIL] and rows_gone and rows_gone[0]["verdict"] == RG.NA, (f_gone, rows_gone))
            gate.write_text("import sys\nprint('🔴 合成 gate: 規則が変わり、 この記入は通らない')\nsys.exit(1)\n", encoding="utf-8")
            L.freeze(mc, "d1", "g2", "submitted", date="2026-06-07", paper="same")
            mc.save()
            mc = M.load(case2)
            expect("記入内容 gate: 提出済み (submitted) の issue は今の規則で裁かない (🔴 にも一覧にも出さない)",
                   not RG.findings(mc) and not [r for r in RG.sweep(mc, "current") if r["role"] == RG.CONTENT_ROLE],
                   (RG.findings(mc), RG.sweep(mc, "current")))
        finally:
            cfg["gates"], cfg["default_gates"] = prev_gates, prev_default
            if gate.exists():
                gate.unlink()
    finally:
        tpl.write_bytes(tpl_bytes)
        spec_path.write_bytes(spec_bytes)
        CF._invalidate()
        if saved_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = saved_cache
