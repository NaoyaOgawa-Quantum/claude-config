"""今ある出力を「今の関門」 に通し直す (regate) と、 外へ出す直前の受け入れ (admit)。 規約 = conventions/form-case-pipeline.md#regate。

なぜ要るか:
  関門 (雛形との照合 = fidelity.py) は build の時に 1 回だけ走る。 build の後に関門が足された・強くなった出力は、 その関門を
  一度も通っていないのに「作った時は通った」 まま案件 dir に残り、 刷る・送る・提出する操作にそのまま使える。 凍結 (freeze) は
  記録を守る仕組みで、 欠陥の分かった世代の出力を止める仕組みではない (凍結 issue は記入内容 gate も再生成も対象外)。
  刷る直前の照合を「出力が自分で持つ宣言」 から引くと、 宣言より前に作られた出力ほど検査が薄くなる (= 止めたい世代だけが素通りする)。
  ∴ 判定を成果物に付けて持ち越さず、 **見る時点の engine・spec・雛形で見直す**。
  一般形 = docs/convention-design-principles.md#verdict-expires-with-the-gate。

この module が持つもの:
  evaluate   1 つの出力 PDF を build と同じ関数 (fidelity.check_group → report_lines) に通す → pass / fail / na (照合できない)。
             押印を紙に実物で押す運用 (設定 seal_mode: physical) では、 印影の画像入りの出力 (前の運用の世代) も fail
  content_gate  窓口より手前の今の issue の workbook を、 今の spec の記入内容 gate (build が最初に回す gate と同じ) に通す。
             凍結 issue は build では裁かない (提出した記録を今の規則で FAIL にしない) が、 刷った・送っただけの issue は
             まだ窓口に届いていない = 規則が変わったら作り直しが効くので、 ここでは免除しない
  sweep      案件の出力を並べて evaluate。 scope = pre (窓口より手前 = draft / printed / sent / unknown の今の issue) / all (前の issue も)
  findings   check / audit 用: 窓口より手前の出力が落ちる = 🔴 (刷る・渡す・出す前に reopen → build)。 issue に ``gate_waiver``
             (そのまま出すと決めた人の言葉) があれば 📄。 提出済みが落ちるのは件数だけ (出し直すかは人が決める)
  locate     file (と、 その宣言の origin / src が指す元の file) を出力に持つ案件を探す
  admit      刷る・添付する直前の 1 file の受け入れ: ① 前の issue の出力 (reopen で置き換え済み) = 止める ② 今の issue の出力 =
             evaluate の判定 ③ 派生物 (raster・頁の抜き出し) = 元の出力を辿って同じ判定。 formcase の出力でない PDF には何も言わない

判定の cache: ``~/.cache/formcase/regate/<出力の sha256>.json`` に、 判定と「関門の指紋」 (engine・検出器・spec・雛形・bind・workbook・
箱の上書き・素刷りの有無の hash) を置く。 指紋が今と違う記録は使わない = engine や spec が変われば次に見た時に通し直す
(「検出器を変えたら在庫を通す」 を人が覚えていなくてよい)。 cache は機械ごと・消してよい。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from . import config as CF
from . import manifest as M
from . import specs as S

PASS, FAIL, NA = "pass", "fail", "na"
# 窓口より手前 = まだ作り直しが効く state (submitted だけが「窓口に届いた」)
PRE_WINDOW_STATES = ("draft", "printed", "sent", "unknown")
OK, BLOCK, UNKNOWN, NOT_FORMCASE = "ok", "block", "unknown", "not-formcase"

_PKG = Path(__file__).resolve().parent
_CC = _PKG.parent
# 関門の実体 = この file 群が変われば判定をやり直す
_GATE_FILES = (_PKG / "fidelity.py", _PKG / "regate.py", _PKG / "layout.py", _PKG / "specs.py", _PKG / "docx_form.py",
               _CC / "check-form-static-text.py", _CC / "lib" / "office_census.py", _CC / "lib" / "seal_artifact.py")
_SRC_FILE = re.compile(r"\(([^()]+\.pdf)\)\s*$", re.I)      # 宣言の src の末尾「(元の file.pdf)」


def cache_root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "formcase" / "regate"


# ---------------------------------------------------------------------------
# 案件の発見 (CLI の discover と同じ規則 = 設定の case_roots の下の manifest)
# ---------------------------------------------------------------------------
def discover(roots=None) -> list:
    """設定の case_roots の下の案件 dir (= submission.yaml のある dir)。 root 直下の case_root_skip は見ない。"""
    out = []
    skip = CF.case_root_skip()
    for r in roots if roots is not None else CF.case_roots():
        r = Path(r)
        if not r.is_dir():
            continue
        for p in sorted(r.glob("**/" + M.MANIFEST_NAME)):
            if p.relative_to(r).parts[:1] and p.relative_to(r).parts[0] in skip:
                continue
            out.append(p.parent)
    return out


# ---------------------------------------------------------------------------
# 1 つの出力の判定
# ---------------------------------------------------------------------------
def has_text_layer(pdf) -> bool:
    import fitz

    try:
        with fitz.open(str(pdf)) as d:
            return any(pg.get_text().strip() for pg in d)
    except Exception:  # noqa: BLE001  読めない PDF = text 層があるとは言えない
        return False


def _blank_parts(spec: dict, group: str):
    """group の素刷りの cache の file (対象の範囲ごと)。 1 つでも無ければ None (Excel は起こさない)。"""
    from . import fidelity as FD

    parts = []
    for sh, rng in FD._group_targets(spec, group):
        p = FD.blank_dir(spec) / f"{FD._safe(sh)}__{FD._safe(rng or 'print_area')}.pdf"
        if not (p.exists() and p.stat().st_size > 0):
            return None
        parts.append(p)
    return parts or None


def _cached_blank(spec: dict, group: str, tmp):
    """group の素刷り (cache に在る分だけを 1 本に並べる)。 1 つでも無ければ None。"""
    import fitz

    from . import fidelity as FD

    parts = _blank_parts(spec, group)
    if not parts:
        return None
    o = fitz.open()
    for p in parts:
        with fitz.open(str(p)) as b:
            o.insert_pdf(b)
    out = Path(tmp) / f"blank_{FD._safe(group)}.pdf"
    o.save(str(out))
    o.close()
    return out


def gate_fingerprint(spec: dict, wb, doc: dict, group: str, has_blank: bool) -> str:
    """今の関門の指紋 = この値が同じなら同じ出力に同じ判定が出る、 と言える範囲の入力の hash。"""
    from . import fidelity as FD

    h = hashlib.sha256()
    for p in _GATE_FILES:
        h.update(p.name.encode())
        h.update(p.read_bytes() if p.exists() else b"-")
    sp = Path(spec.get("_path")) if spec.get("_path") else None
    h.update(sp.read_bytes() if sp is not None and sp.exists() else b"-")
    try:
        tpl = S.template_path(spec)
        h.update(FD.sha256(tpl).encode() if tpl.exists() else b"no-template")
        bf = FD.bind_file(spec)
        h.update(bf.read_bytes() if bf.exists() else b"no-bind")
    except (KeyError, TypeError):
        h.update(b"no-template")
    h.update(M.file_sha256(wb).encode() if wb is not None and Path(wb).exists() else b"no-workbook")
    try:
        ov = S.case_controls_for_group(spec, doc, group)
    except ValueError as e:
        ov = {"error": str(e)}
    h.update(json.dumps(ov, sort_keys=True, ensure_ascii=False).encode())
    h.update(b"blank" if has_blank else b"noblank")
    h.update(CF.seal_mode().encode())
    return h.hexdigest()[:32]


def _cache_get(key: str, fp: str):
    p = cache_root() / key[:2] / f"{key}.json"
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if rec.get("fp") == fp and rec.get("verdict") in (PASS, FAIL, NA) else None


def _cache_put(key: str, fp: str, res: dict) -> None:
    p = cache_root() / key[:2] / f"{key}.json"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"fp": fp, "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
               **{k: res[k] for k in ("verdict", "reason", "lines", "partial")}}
        p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass                                    # cache が書けなくても判定は返す


def _res(verdict, reason="", lines=None, partial=False, cached=False) -> dict:
    return {"verdict": verdict, "reason": reason, "lines": list(lines or []), "partial": partial, "cached": cached}


def seal_stop(pdf) -> str | None:
    """押印を紙に実物で押す運用 (seal_mode: physical) なのに、 印影の画像入りの印 (紙専用の marker) を持つ出力 = 前の運用の世代。
    白黒の写し (色のある画素が無い) は写しとして出す物なので対象外。"""
    if CF.seal_mode() != "physical":
        return None
    import sys

    lib = str(_CC / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    try:
        import seal_artifact as SA

        if SA.has_marker(str(pdf)) and not SA.is_monochrome_copy(str(pdf)):
            return ("印影の画像入りの出力 (押印を紙に実物で押す運用 = seal_mode: physical より前の世代)。 "
                    "押印欄を空けた版を作り直して刷り、 紙に押す")
    except Exception:  # noqa: BLE001  印の検査が走らない = この理由では止めない (雛形との照合は別に走る)
        return None
    return None


def evaluate(m: M.Manifest, doc_id: str, group_id: str, pdf, excel: bool = False, use_cache: bool = True) -> dict:
    """出力 PDF 1 本を今の関門に通す → {verdict: pass|fail|na, reason, lines, partial, cached}。
    partial = 素刷り (cache) が無く、 画像・箱の照合を見ていない pass (図形の字と見出しは見た)。
    excel=True = 素刷りの cache が無ければ Excel で作る (既定は cache だけ = app を起こさない)。"""
    from . import docx_form as DF
    from . import fidelity as FD

    doc = m.doc(doc_id)
    spec = S.get(doc.get("form"))
    pdf = Path(pdf)
    if not pdf.exists():
        return _res(NA, "file が無い")
    if spec is None:
        return _res(NA, f"spec が無い (form = {doc.get('form')}) = この engine の関門の対象外")
    if not ((spec.get("meta") or {}).get("template")):
        return _res(NA, "spec に雛形が無い = 照合する参照が無い")
    if not has_text_layer(pdf):
        return _res(NA, "text 層が無い (raster) = 元の出力で照合する")
    wb = m.workbook(doc_id)
    docx = DF.is_docx(spec)
    try:
        have_blank = (not docx) and bool(_blank_parts(spec, group_id))
    except Exception:  # noqa: BLE001  雛形が読めない等 = 素刷りなしとして進む (照合の側が理由を言う)
        have_blank = False
    key = M.file_sha256(pdf)
    if use_cache and (have_blank or docx or not excel):
        hit = _cache_get(key, gate_fingerprint(spec, wb, doc, group_id, have_blank))
        if hit:
            return _res(hit["verdict"], hit.get("reason", ""), hit.get("lines"), bool(hit.get("partial")), cached=True)
    with tempfile.TemporaryDirectory(prefix="formcase-regate-") as td:
        if docx:
            blank = None
        elif have_blank:
            blank = _cached_blank(spec, group_id, td)
        else:
            blank = FD.group_blank(spec, group_id, Path(td)) if excel else None
        fp = gate_fingerprint(spec, wb, doc, group_id, bool(blank))
        filled = wb if (wb is not None and wb.exists()) else None
        rep = FD.check_group(spec, group_id, pdf, filled=filled, blank=blank, doc=doc)
        lines, stop = FD.report_lines(rep, spec)
    if "error" in rep:
        return _res(NA, f"雛形との照合が走らなかった: {rep['error'][:160]}", lines)       # 故障は cache しない
    targets = rep.get("targets") or []
    if not targets or all(t.get("page") is None for t in targets):
        res = _res(NA, "雛形のどの範囲の頁もこの PDF に見つからない (別の書類か、 字が画像になっている)", lines)
    else:
        stop = stop or seal_stop(pdf)
        partial = blank is None and not DF.is_docx(spec)
        if partial and not stop:
            lines = lines + ["⚪ 素刷りの cache が無い = 画像・箱の数と位置は見ていない (formcase.py bind <form> で作る / regate --excel)"]
        res = _res(FAIL if stop else PASS, stop or "", lines, partial=partial and not stop)
    _cache_put(key, fp, res)
    return res


CONTENT_ROLE = "記入内容"


def _content_fingerprint(m: M.Manifest, doc_id: str, group_id: str, spec: dict, wb) -> str:
    from . import docx_form as DF
    from . import fidelity as FD
    from . import gates as GT

    doc = m.doc(doc_id)
    h = hashlib.sha256()
    for p in (_PKG / "gates.py", _PKG / "regate.py", _PKG / "specs.py", _PKG / "docx_form.py"):
        h.update(p.read_bytes() if p.exists() else b"-")
    sp = Path(spec.get("_path")) if spec.get("_path") else None
    h.update(sp.read_bytes() if sp is not None and sp.exists() else b"-")
    h.update(M.file_sha256(wb).encode())
    if DF.is_docx(spec):
        tpl = S.template_path(spec)
        h.update(FD.sha256(tpl).encode() if tpl.exists() else b"no-template")
    else:
        for g in CF.gates_for(doc.get("form"), spec):
            h.update(g["id"].encode())
            h.update(g["script"].read_bytes() if g["script"].exists() else b"-")
            h.update(json.dumps(g["args"]).encode())
        h.update(json.dumps(GT.scope_sheets(m, doc_id, [group_id]), ensure_ascii=False).encode())
        try:
            ov = S.case_controls(spec, doc)
        except ValueError as e:
            ov = {"error": str(e)}
        h.update(json.dumps(ov, sort_keys=True, ensure_ascii=False, default=str).encode())
    return "c:" + group_id + ":" + h.hexdigest()[:32]


def content_gate(m: M.Manifest, doc_id: str, group_id: str, use_cache: bool = True) -> dict:
    """今の issue の workbook を、 今の spec の記入内容 gate に通す (その group を「作る対象」 として = 凍結の免除なし)。
    → {verdict, reason, lines, partial, cached}。 spec・workbook・gate が無い = na。 gate の故障 (script が無い等) も na。"""
    import contextlib
    import io

    from . import gates as GT

    doc = m.doc(doc_id)
    spec = S.get(doc.get("form"))
    wb = m.workbook(doc_id)
    if spec is None:
        return _res(NA, f"spec が無い (form = {doc.get('form')})")
    if wb is None or not wb.exists():
        return _res(NA, "workbook が無い")
    try:
        fp = _content_fingerprint(m, doc_id, group_id, spec, wb)
    except Exception as e:  # noqa: BLE001
        return _res(NA, f"記入内容 gate の指紋を作れない: {type(e).__name__}: {e}")
    key = hashlib.sha256((str(wb.resolve()) + "|" + group_id).encode()).hexdigest()
    if use_cache:
        hit = _cache_get(key, fp)
        if hit:
            return _res(hit["verdict"], hit.get("reason", ""), hit.get("lines"), cached=True)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            ok = GT.run_scoped(m, doc_id, [group_id], raise_on_fail=False)
    except Exception as e:  # noqa: BLE001  gate が走らない = 違反と言わない (故障は cache しない)
        return _res(NA, f"記入内容 gate が走らなかった: {type(e).__name__}: {_clip(str(e), 160)}")
    lines = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]
    if ok:
        res = _res(PASS, "", [])
    else:
        bad = [x for x in lines if "🔴" in x or "FAIL" in x or "✗" in x][:8]
        res = _res(FAIL, "今の spec の記入内容 gate に落ちる (凍結の後に規則が変わった・workbook が変わった)", bad or lines[-8:])
    _cache_put(key, fp, res)
    return res


# ---------------------------------------------------------------------------
# 案件の出力を並べる
# ---------------------------------------------------------------------------
def _issues(g: dict):
    yield "current", g.get("current") or {}
    for i, it in enumerate(g.get("previous") or []):
        yield i, it


def stage(state) -> str:
    return "pre" if state in PRE_WINDOW_STATES else "submitted"


def issue_label(ref) -> str:
    return "current" if ref == "current" else f"previous[{ref}]"


def outputs(m: M.Manifest, scope: str = "pre"):
    """(doc_id, group_id, issue ref, issue, role, path) を並べる。 scope: pre = 窓口より手前の今の issue (file が在るもの) /
    current = 今の issue 全部 / all = 前の issue も。"""
    for doc_id, _d, gid, g in m.iter_groups():
        for ref, it in _issues(g):
            if scope != "all" and ref != "current":
                continue
            if scope == "pre" and stage(it.get("state")) != "pre":
                continue
            for role, rel in (it.get("outputs") or {}).items():
                if not str(rel).lower().endswith(".pdf"):
                    continue
                p = m.case_dir / rel
                if scope == "pre" and not p.exists():
                    continue                    # まだ作っていない draft の出力
                yield doc_id, gid, ref, it, role, p


def sweep(m: M.Manifest, scope: str = "pre", excel: bool = False, use_cache: bool = True) -> list:
    """案件の出力を今の関門に通した行の list。 行 = {doc, group, issue, state, date, stage, role, file, waiver, verdict, reason, lines, …}。"""
    rows = []
    pre_groups = {}
    for doc_id, gid, ref, it, role, p in outputs(m, scope):
        ev = evaluate(m, doc_id, gid, p, excel=excel, use_cache=use_cache)
        rows.append({"doc": doc_id, "group": gid, "issue": issue_label(ref), "state": it.get("state"),
                     "date": str(it.get("date") or ""), "stage": stage(it.get("state")) if ref == "current" else "superseded",
                     "role": role, "file": p.name, "waiver": it.get("gate_waiver") or "", **ev})
        if ref == "current" and stage(it.get("state")) == "pre" and p.exists():
            pre_groups[(doc_id, gid)] = it
    # 窓口より手前で出力の在る今の issue = 今の spec の記入内容 gate も当てる (提出済み・前の issue は裁かない)
    for (doc_id, gid), it in pre_groups.items():
        ev = content_gate(m, doc_id, gid, use_cache=use_cache)
        if ev["verdict"] == NA and S.get(m.doc(doc_id).get("form")) is None:
            continue                            # spec の無い書類は出力の行が既に na と言っている
        wb = m.workbook(doc_id)
        rows.append({"doc": doc_id, "group": gid, "issue": "current", "state": it.get("state"),
                     "date": str(it.get("date") or ""), "stage": "pre", "role": CONTENT_ROLE,
                     "file": wb.name if wb is not None else "", "waiver": it.get("gate_waiver") or "", **ev})
    return rows


def _short(reason: str, n: int = 70) -> str:
    """止めた理由の頭 (何が無いか) だけを 1 行に。 直し方の案内 (「 = 」 の後) は落とす。"""
    return _clip(str(reason).split(" = ")[0], n)


def _clip(text: str, n: int = 90) -> str:
    r = " ".join(str(text).split())
    return r if len(r) <= n else r[: n - 1] + "…"


def findings(m: M.Manifest, excel: bool = False, use_cache: bool = True) -> list:
    """check / audit 用の findings [(level, where, msg)]。 窓口より手前の出力が今の関門に落ちる = 🔴 (waiver があれば 📄)。
    spec の在る issue で、 どの出力も照合できなかったものは 🟡 (= 見ていないことを黙らない)。"""
    f = []
    by_issue: dict = {}
    for r in sweep(m, "pre", excel=excel, use_cache=use_cache):
        by_issue.setdefault((r["doc"], r["group"]), []).append(r)
    for (doc_id, gid), rs in by_issue.items():
        where = f"{doc_id}/{gid}"
        bad = [r for r in rs if r["verdict"] == FAIL]
        label = f"{rs[0]['state']} {rs[0]['date']}".strip()
        if bad:
            files = ", ".join(r["file"] + (" (記入内容)" if r["role"] == CONTENT_ROLE else "") for r in bad)
            if rs[0]["waiver"]:
                f.append((M.PAPER, where, f"今の関門に落ちる出力 ({label}: {files}) をそのまま出すと決めた記録: {rs[0]['waiver']}"))
            else:
                f.append((M.FAIL, where,
                          f"窓口より手前 ({label}) の出力が今の関門に落ちる: {files} — {_short(bad[0]['reason'])} = 刷る・渡す・出す前に "
                          "formcase.py reopen → build で作り直す (送った相手が刷る書類なら差し替えを送るかを人が決める。 "
                          "そのまま出すと決めたら formcase.py annotate --gate-waiver に決めた人の言葉)"))
        elif all(r["verdict"] == NA for r in rs if r["role"] != CONTENT_ROLE):
            spec = S.get(m.doc(doc_id).get("form"))
            if spec is not None and (spec.get("meta") or {}).get("template"):
                f.append((M.WARN, where, f"窓口より手前 ({label}) の出力を今の関門で照合できない: {_clip(rs[0]['reason'])}"))
    return f


def submitted_failures(m: M.Manifest, use_cache: bool = True) -> list:
    """提出済みの今の issue で今の関門に落ちる行 (出し直すかは人が決める = 件数に数えない一覧用)。"""
    return [r for r in sweep(m, "current", use_cache=use_cache) if r["stage"] == "submitted" and r["verdict"] == FAIL]


# ---------------------------------------------------------------------------
# file → 案件 (受け入れ)
# ---------------------------------------------------------------------------
def _read_record(pdf):
    import sys

    lib = str(_CC / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import fitz
    import print_pages as PP

    try:
        with fitz.open(str(pdf)) as d:
            return PP.read_record(d)
    except Exception:  # noqa: BLE001
        return None


def _match(m: M.Manifest, path: Path):
    """manifest の出力に path が在れば (doc, group, issue ref, role, 今の issue の出力でもあるか)。 今の issue を先に見る。"""
    want = str(Path(path).resolve())
    hit = None
    for doc_id, _d, gid, g in m.iter_groups():
        for ref, it in _issues(g):
            for role, rel in (it.get("outputs") or {}).items():
                if str((m.case_dir / rel).resolve()) == want:
                    if ref == "current":
                        return doc_id, gid, ref, role
                    hit = hit or (doc_id, gid, ref, role)
    return hit


def _manifest_above(path: Path, levels: int = 4):
    for d in [path.parent, *path.parent.parents][:levels]:
        if (d / M.MANIFEST_NAME).exists():
            try:
                return M.load(d)
            except M.ManifestError:
                return None
    return None


def origin_chain(pdf, hops: int = 3) -> tuple:
    """(pdf と、 その宣言が指す元の file を辿った list, 宣言の src に出てきた元の file 名)。 元の file = 宣言の origin.path、
    無ければ src の末尾の「(元.pdf)」 を同じ dir で探す。"""
    chain = [Path(pdf).resolve()]
    names = []
    cur = chain[0]
    for _ in range(hops):
        rec = _read_record(cur) or {}
        nxt = None
        org = rec.get("origin") or {}
        if org.get("path") and Path(org["path"]).exists():
            nxt = Path(org["path"]).resolve()
        mm = _SRC_FILE.search(str(rec.get("src") or ""))
        if mm:
            names.append(mm.group(1))
            if nxt is None and (cur.parent / mm.group(1)).exists():
                nxt = (cur.parent / mm.group(1)).resolve()
        if nxt is None or nxt in chain:
            break
        chain.append(nxt)
        cur = nxt
    return chain, names


def locate(pdf, search_roots: bool = True) -> dict | None:
    """pdf (または元の file) を出力に持つ案件 → {m, doc, group, issue, role, origin, derived}。 見つからなければ None。
    同じ名前の出力が複数の案件に在って決められない時は {"ambiguous": [案件 dir …]}。"""
    chain, names = origin_chain(pdf)
    first = chain[0]
    for c in chain:
        m = _manifest_above(c)
        if m is None:
            continue
        hit = _match(m, c)
        if hit:
            return {"m": m, "doc": hit[0], "group": hit[1], "issue": hit[2], "role": hit[3], "origin": c, "derived": c != first}
    if not search_roots:
        return None
    # 案件 dir の外に置かれた派生物 (scratch の raster など): 名前で全案件を探す。 宣言が formcase の出力・派生物だと言っている file は
    # 名前だけで、 宣言の無い file は出力と同じ bytes の写しの時だけ結ぶ (= たまたま同じ名前の別の PDF を案件の出力と読まない)
    rec = _read_record(first) or {}
    declared = str(rec.get("src") or "").startswith("formcase") or bool(names) or bool(rec.get("origin"))
    first_sha = None if declared else M.file_sha256(first)
    wanted = {first.name, *names}
    stem = re.sub(r"_raster$", "", first.stem)
    wanted.add(stem + ".pdf")
    hits = []
    for case in discover():
        try:
            m = M.load(case)
        except M.ManifestError:
            continue
        for doc_id, _d, gid, g in m.iter_groups():
            for ref, it in _issues(g):
                for role, rel in (it.get("outputs") or {}).items():
                    if Path(rel).name in wanted and (m.case_dir / rel).exists():
                        if first_sha is not None and M.file_sha256(m.case_dir / rel) != first_sha:
                            continue
                        hits.append({"m": m, "doc": doc_id, "group": gid, "issue": ref, "role": role,
                                     "origin": (m.case_dir / rel).resolve(), "derived": True})
    if not hits:
        return None
    cur = [h for h in hits if h["issue"] == "current"] or hits
    if len({str(h["origin"]) for h in cur}) == 1:
        return cur[0]
    return {"ambiguous": sorted({str(h["m"].case_dir) for h in cur})}


def _current_rels(m: M.Manifest, doc_id: str, group_id: str) -> list:
    cur = m.group(doc_id, group_id).get("current") or {}
    return [str(v) for v in (cur.get("outputs") or {}).values()]


def admit(pdf, excel: bool = False, use_cache: bool = True) -> dict:
    """刷る・添付する直前の受け入れ → {status: ok|block|unknown|not-formcase, lines: [...]}。
    block = 前の issue の出力 / 今の関門に落ちる (waiver なし)。 unknown = formcase の出力らしいが照合できない (止めるかは呼び元)。"""
    pdf = Path(pdf)
    if not pdf.exists():
        return {"status": UNKNOWN, "lines": [f"⚪ file が無い: {pdf}"]}
    loc = locate(pdf)
    rec = _read_record(pdf) or {}
    by_formcase = str(rec.get("src") or "").startswith("formcase")
    if loc is None:
        if by_formcase:
            return {"status": UNKNOWN,
                    "lines": [f"⚪ 宣言は formcase の出力 ({rec.get('src')}) だが、 どの案件の出力か辿れない = 今の関門に通せない"]}
        return {"status": NOT_FORMCASE, "lines": []}
    if "ambiguous" in loc:
        return {"status": UNKNOWN, "lines": ["⚪ 同じ名前の出力が複数の案件に在り、 どれの派生物か決められない: "
                                             + ", ".join(Path(c).name for c in loc["ambiguous"])
                                             + " (案件 dir の中の元の file を渡す)"]}
    m, doc_id, gid, ref = loc["m"], loc["doc"], loc["group"], loc["issue"]
    where = f"{m.case_dir.name} {doc_id}/{gid}"
    src_note = f" (派生物、 元 = {loc['origin'].name})" if loc["derived"] else ""
    org = rec.get("origin") or {}
    if (loc["derived"] and org.get("sha256") and org.get("path")
            and Path(org["path"]).resolve() == loc["origin"] and M.file_sha256(loc["origin"]) != org["sha256"]):
        return {"status": BLOCK, "where": where,
                "lines": [f"🔴 {where}{src_note}: この派生物 (raster・頁の抜き出し) を作った後に、 元の出力が作り直されている = 古い版。 "
                          f"今の {loc['origin'].name} から派生物を作り直す"]}
    if ref != "current":
        now = ", ".join(_current_rels(m, doc_id, gid)) or "(今の issue に出力なし)"
        return {"status": BLOCK, "where": where,
                "lines": [f"🔴 {where}: 前の issue の出力{src_note} = reopen で置き換え済みの旧版。 今の版 = {now}"]}
    it = m.group(doc_id, gid).get("current") or {}
    ev = evaluate(m, doc_id, gid, loc["origin"], excel=excel, use_cache=use_cache)
    if ev["verdict"] == NA:
        # raster の出力など: 同じ issue の、 text 層のある出力で照合する
        for role, rel in (it.get("outputs") or {}).items():
            p = m.case_dir / rel
            if p.resolve() != loc["origin"] and str(rel).lower().endswith(".pdf") and p.exists() and has_text_layer(p):
                ev2 = evaluate(m, doc_id, gid, p, excel=excel, use_cache=use_cache)
                if ev2["verdict"] != NA:
                    ev, src_note = ev2, src_note + f" (text 層のある同じ issue の {Path(rel).name} で照合)"
                    break
    label = f"{it.get('state')} {it.get('date', '')}".strip()
    if ev["verdict"] == PASS and stage(it.get("state")) == "pre":
        cg = content_gate(m, doc_id, gid, use_cache=use_cache)
        if cg["verdict"] == FAIL:
            ev = cg
    if ev["verdict"] == FAIL:
        if it.get("gate_waiver"):
            return {"status": OK, "where": where,
                    "lines": [f"📄 {where} ({label}){src_note}: 今の関門に落ちるが、 そのまま出すと決めた記録あり: {it['gate_waiver']}"]}
        fix = ("formcase.py reopen → build で作り直す" if it.get("state") in M.FROZEN_STATES else "formcase.py build で作り直す")
        return {"status": BLOCK, "where": where,
                "lines": [f"🔴 {where} ({label}){src_note}: 今の関門に落ちる — {_short(ev['reason'], 140)}",
                          *[f"   {x}" for x in ev["lines"] if "🔴" in x][:6],
                          f"   → {fix} (作った時は通った検査でも、 今の検査には通っていない)"]}
    if ev["verdict"] == NA:
        return {"status": UNKNOWN, "where": where, "lines": [f"⚪ {where} ({label}){src_note}: 今の関門で照合できない — {ev['reason']}"]}
    tail = " (素刷りなし = 画像・箱は見ていない)" if ev.get("partial") else ""
    return {"status": OK, "where": where, "lines": [f"✅ {where} ({label}){src_note}: 今の関門を通る{tail}"]}
