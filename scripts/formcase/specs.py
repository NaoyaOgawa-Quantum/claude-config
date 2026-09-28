"""お手本 spec (``<spec_dir>/*.yaml``) の読み込み。 spec の書式の正本は各 yaml と記入内容 gate。

spec の dir・雛形の base は instance 設定 (``config.py``) が持つ = engine は「どの様式か」 を知らない。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from . import config as CF

def _yaml_safe_load(stream):  # yaml.safe_load と同じ結果を C 版 (libyaml) で返す = 約 10 倍速 (2026-09-23)
    import yaml
    return yaml.load(stream, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))



@lru_cache(maxsize=None)
def _load_all(spec_dir: str) -> dict:
    out = {}
    for p in sorted(Path(spec_dir).glob("*.yaml")):
        raw = p.read_bytes()
        if raw.startswith(b"\x00GITCRYPT"):
            continue
        d = _yaml_safe_load(raw.decode("utf-8")) or {}
        sid = (d.get("meta") or {}).get("id")
        if sid:
            d["_path"] = p
            out[str(sid)] = d
    return out


def invalidate() -> None:
    """設定が差し替わったら読み直す (config.configure / reset が呼ぶ)。"""
    _load_all.cache_clear()


def all_specs(spec_dir: Path | None = None) -> dict:
    return _load_all(str(spec_dir or CF.spec_dir()))


def get(form_id, spec_dir: Path | None = None):
    return all_specs(spec_dir).get(str(form_id)) if form_id is not None else None


def spec_ids() -> list:
    return sorted(all_specs())


def group_def(spec: dict, group_id: str) -> dict:
    g = (spec.get("groups") or {}).get(group_id)
    if g is None:
        raise KeyError(f"spec {spec['meta'].get('id')!r} に group {group_id!r} が無い")
    return g


def group_sheets(spec: dict, group_id: str, with_depends: bool = True) -> list:
    g = group_def(spec, group_id)
    out = list(g.get("sheets") or [])
    if with_depends:
        out += [s for s in (g.get("depends") or []) if s not in out]
    return out


def template_path(spec: dict) -> Path:
    return (CF.template_root() / spec["meta"]["template"]).resolve()


def _on_off(raw, what: str) -> str:
    st = {True: "on", False: "off"}.get(raw, str(raw).lower())     # YAML 1.1 は裸の on / off を bool に読む = 両方受ける
    if st not in ("on", "off"):
        raise ValueError(f"{what}: state は on / off ({raw!r})")
    return st


def case_controls(spec: dict, doc: dict | None) -> dict:
    """案件の document (submission.yaml の documents.<doc>) の ``controls:`` = 箱の案件ごとの上書き (2026-09-28) を正規化する:
    {control id: {"state": on|off, "why": str}}。 書き方は ``{id: "on"}`` か ``{id: {state: "on", why: …}}``。
    上書きできるのは spec の entry が ``per_case: true`` の箱だけ (= どの箱が案件で変わるかは spec が決める。 それ以外の箱の state は
    様式の規則で、 案件の宣言で変えない)。 spec に無い id / per_case でない箱 / on・off 以外 = ValueError。 上書きが無ければ {}。"""
    raw = (doc or {}).get("controls")
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"document の controls: は {{箱の id: on / off}} の mapping ({type(raw).__name__})")
    known = {str(e.get("id")): e for e in (spec or {}).get("controls") or []}
    out = {}
    for cid, v in raw.items():
        cid = str(cid)
        e = known.get(cid)
        if e is None:
            raise ValueError(f"document の controls: {cid!r} は spec {(spec or {}).get('meta', {}).get('id')!r} の controls に無い"
                             f" (在るのは {sorted(known)})")
        if not e.get("per_case"):
            raise ValueError(f"document の controls: {cid!r} は spec で per_case: true でない = 案件ごとに変えない箱"
                             " (変えるなら spec の規則を直す)")
        body = v if isinstance(v, dict) else {"state": v}
        out[cid] = {"state": _on_off(body.get("state", ""), f"document の controls: {cid!r}"),
                    "why": str(body.get("why") or "").strip()}
    return out


def controls(spec: dict, doc: dict | None = None) -> list:
    """spec の ``controls:`` (form control の箱 = checkbox、 D9 2026-09-25) を正規化する:
    [{id, sheet, anchor, index, state, label, rule, group, why, …}]。 anchor = 箱が載る cell (雛形の controlPr の from、 A1 形式)、
    index = 同じ cell に載る箱の並び (既定 0)、 state = on (選んだ側 = 印を入れる) / off (入れない)。 sheet の既定 = meta.sheet。
    doc = 案件の document (submission.yaml の documents.<doc>) を渡すと、 その ``controls:`` の上書き (``case_controls``) を
    state に当てた「この案件の state」 を返す (上書きした entry は ``override = {"state", "why", "default"}`` を持つ)。
    fill・gate・build の期待数・凍結の記録はどれもこの関数で state を引く = 同じ上書きを見る (form-case-pipeline.md の
    「form control の箱」 の案件ごとの上書き)。 上書きの不正は ValueError (case_controls)。"""
    out = []
    main = (spec.get("meta") or {}).get("sheet")
    ov = case_controls(spec, doc) if doc is not None else {}
    for e in spec.get("controls") or []:
        st = _on_off(e.get("state", ""), f"controls {e.get('id')!r}")
        if not e.get("anchor"):
            raise ValueError(f"controls {e.get('id')!r}: anchor (箱が載る cell) が無い")
        ent = dict(e, sheet=str(e.get("sheet") or main), anchor=str(e["anchor"]).upper().replace("$", ""),
                   index=int(e.get("index") or 0), state=st)
        o = ov.get(str(e.get("id")))
        if o is not None:
            ent.update(state=o["state"], override={"state": o["state"], "why": o["why"], "default": st})
        out.append(ent)
    return out


def control_group(spec: dict, entry: dict) -> str | None:
    """箱の entry が属する group (``group:`` が無ければ spec の最初の group)。"""
    groups = list((spec or {}).get("groups") or {})
    return entry.get("group") or (groups[0] if groups else None)


def case_controls_for_group(spec: dict, doc: dict | None, group: str) -> dict:
    """その group の箱への上書きだけ = {id: on|off} (凍結の記録と、 凍結後に上書きが変わったかの照合が使う)。"""
    ov = case_controls(spec, doc)
    if not ov:
        return {}
    return {str(e.get("id")): ov[str(e.get("id"))]["state"] for e in (spec or {}).get("controls") or []
            if str(e.get("id")) in ov and control_group(spec, e) == group}


def history_homes() -> set:
    """規則の理由・経緯の home = spec の ``meta.history_home`` (spec file からの相対 path) の実在するもの。"""
    out = set()
    for spec in all_specs().values():
        hh = (spec.get("meta") or {}).get("history_home") or []
        for rel in ([hh] if isinstance(hh, str) else hh):
            cand = (spec["_path"].parent / rel).resolve()
            if cand.exists():
                out.add(cand)
    return out


# ---------------------------------------------------------------------------
# 頁の役割 (page_roles) — どの頁が窓口に出す頁か。 判定の実体 = scripts/lib/print_pages.py
# (役割の語・矛盾の検査・頁の目印の照合。 本 module は spec の形を渡す adapter だけ)
# ---------------------------------------------------------------------------
def _pp():
    import sys

    lib = str(Path(__file__).resolve().parent.parent / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import print_pages

    return print_pages


def page_roles(spec: dict) -> dict:
    """{package の頁番号 (1 始まり): {"role", "anchor", "label", "why"}}。 spec に無ければ {}。"""
    out = {}
    for k, v in (spec.get("page_roles") or {}).items():
        out[int(k)] = v if isinstance(v, dict) else {"role": v}
    return out


def page_role_problems(spec: dict) -> list:
    """spec の頁の役割の矛盾 (空 = 問題なし)。 検査の中身 = print_pages.role_map_problems:
    役割の語 / submit の anchor / group (= まとまり) は submit だけ / submit はどれかの group に。
    docx 様式 (package = Word の文書まるごと) は meta.pages の全頁に役割が要る (= 様式に付いてくる説明書き・記載例を
    黙って刷らない)。 Excel 様式は group の sheets と印刷範囲 (= 刷る sheet の whitelist) だけを刷るので無くてよい。"""
    meta = spec.get("meta") or {}
    n = int(meta.get("pages") or 1) if str(meta.get("kind") or "") == "docx" else None
    groups = {gid: (g or {}).get("pages") or [] for gid, g in (spec.get("groups") or {}).items()}
    return _pp().role_map_problems(page_roles(spec), groups, n_pages=n, name=str(meta.get("id")))
