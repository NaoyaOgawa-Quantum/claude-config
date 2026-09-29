#!/usr/bin/env python3
"""latex-split-deps.py — 原稿の一部 (節・\\input の file) を別の文書へ移す前に、 移すと切れる参照・引用と、 移した文の中で旧い入れ物を指す語を列挙する (読むだけ)。

用途:
  - 付録や補足を別論文 (companion paper) へ移す、 あるいは Supplemental Material へ移す前の計画。
    移す範囲を決めた時点で、 次の 4 つを一度に出す:
      A. 残る側 → 移す側の label への参照 (移した後に引用か別の式へ付け替える必要がある箇所)
      B. 移す側 → 残る側の label への参照 (移した先で xr の接頭辞と「of Ref. [..]」 が要る箇所)
      C. 移す側だけが使う引用 key (文献が一緒に移る)
      D. 移す側の文で、 旧い入れ物を指す語 ("the main text" / "this appendix" / "Supplemental Material" ほか)
    B と D は移した後の付け替えの一覧、 A は残る側の付け替えの一覧になる (latex.md#companion-paper-split)。
  - 移した後の検査は build の未定義参照と verify-verbatim-move.py が持つ。 この script は移す前の地図だけを出す。

usage:
    python3 latex-split-deps.py main.tex --move-section "Title of a section" [--move-section ...] [--move-file part.tex ...] [--json]
    python3 latex-split-deps.py --selftest

- main.tex から \\input / \\include を辿り、 見つかった file をすべて読む (見つからない input は警告して飛ばす)。
- --move-section は \\section{...} の見出しの文字列 (大文字小文字・前後の空白は無視) で、 その見出しから次の \\section・\\appendix・\\bibliography・\\end{document} の手前までを移す側とする。
- --move-file は file 全体を移す側とする (\\input で入る付録など)。
- 参照の命令 = \\ref \\eqref \\cref \\Cref \\autoref \\pageref \\labelcref と、 preamble で `\\newcommand{\\X}{\\eqref}` のように参照の命令の別名にした macro (自動で拾う。 拾えないものは --ref-macro X)。
- comment (% 以降) は読まない。 exit は常に 0 (計画の道具)。 見出しが見つからなければ exit 2。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

REF_CMDS = ["ref", "eqref", "cref", "Cref", "autoref", "pageref", "labelcref"]
CONTAINER_WORDS = re.compile(
    r"\b(?:main text|this appendix|these appendices|the present appendix|supplemental material|this supplement)\b", re.I)


def strip_comments(text: str) -> str:
    out = []
    for line in text.split("\n"):
        m = re.search(r"(?<!\\)%", line)
        out.append(line[:m.start()] if m else line)
    return "\n".join(out)


def ref_aliases(text: str) -> list[str]:
    pat = r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?\\([A-Za-z]+)\}?\s*\{\\(%s)\}" % "|".join(REF_CMDS)
    names = [m.group(1) for m in re.finditer(pat, text)]
    names += [m.group(1) for m in re.finditer(r"\\def\\([A-Za-z]+)\{\\(?:%s)\}" % "|".join(REF_CMDS), text)]
    return names


def load_tree(root: Path) -> list[tuple[Path, str]]:
    """root から \\input / \\include を辿った file の (path, 本文) の列。"""
    seen, order = set(), []

    def visit(p: Path):
        if p in seen:
            return
        seen.add(p)
        text = p.read_text(encoding="utf-8")
        order.append((p, text))
        for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}", strip_comments(text)):
            name = m.group(1).strip()
            cand = [p.parent / name, p.parent / (name + ".tex")]
            hit = next((c for c in cand if c.is_file()), None)
            if hit is None:
                print(f"warning: input not found: {name} (from {p.name})", file=sys.stderr)
                continue
            visit(hit.resolve())

    visit(root.resolve())
    return order


def section_spans(text: str) -> list[tuple[str, int, int]]:
    """(見出し, 開始, 終了) の列。 終了 = 次の \\section・\\appendix・\\bibliography・\\end{document}。"""
    stops = [m.start() for m in re.finditer(r"\\section\*?\{|\\appendix\b|\\bibliography\{|\\end\{document\}", text)]
    spans = []
    for m in re.finditer(r"\\section\*?\{", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        title = re.sub(r"\s+", " ", text[m.end():i - 1]).strip()
        end = next((s for s in stops if s > m.start()), len(text))
        spans.append((title, m.start(), end))
    return spans


def analyse(root: Path, move_sections: list[str], move_files: list[str], extra_ref: list[str]) -> dict:
    files = load_tree(root)
    alltext = "\n".join(strip_comments(t) for _, t in files)
    cmds = REF_CMDS + ref_aliases(alltext) + extra_ref
    ref_re = re.compile(r"\\(%s)\*?\{([^}]+)\}" % "|".join(sorted(set(cmds), key=len, reverse=True)))
    want = {s.strip().lower() for s in move_sections}
    mfiles = {(root.parent / f).resolve() for f in move_files} | {(root.parent / (f + ".tex")).resolve() for f in move_files}
    stripped = {p: strip_comments(raw) for p, raw in files}   # comment を消しても行数は変わらない
    moved, stay = [], []          # (path, offset, text) の断片。 offset は stripped の中の位置
    found = set()
    for p, _ in files:
        t = stripped[p]
        if p in mfiles:
            moved.append((p, 0, t))
            continue
        cuts = []
        for title, a, b in section_spans(t):
            if title.lower() in want:
                found.add(title.lower())
                cuts.append((a, b))
        pos = 0
        for a, b in cuts:
            stay.append((p, pos, t[pos:a])); moved.append((p, a, t[a:b])); pos = b
        stay.append((p, pos, t[pos:]))
    missing = sorted(want - found)
    if missing:
        return {"error": "section not found: " + "; ".join(missing)}

    def where(p: Path, base: int, frag: str, i: int) -> str:
        line = stripped[p][:base + i].count("\n") + 1
        return f"{p.name}:{line}"

    def labels(parts):
        return {m.group(1) for _, _, t in parts for m in re.finditer(r"\\label\{([^}]+)\}", t)}

    def refs(parts):
        for p, base, t in parts:
            for m in ref_re.finditer(t):
                for key in m.group(2).split(","):
                    ctx = re.sub(r"\s+", " ", t[max(0, m.start() - 60):m.end() + 20])
                    yield key.strip(), where(p, base, t, m.start()), ctx

    def cites(parts):
        return {k.strip() for _, _, t in parts for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^]]*\])*\{([^}]+)\}", t) for k in m.group(1).split(",")}

    lm, ls = labels(moved), labels(stay)
    a = [dict(label=k, at=w, context=c) for k, w, c in refs(stay) if k in lm]
    b = [dict(label=k, at=w, context=c) for k, w, c in refs(moved) if k in ls]
    words = []
    for p, base, t in moved:
        for m in CONTAINER_WORDS.finditer(t):
            words.append(dict(word=m.group(0), at=where(p, base, t, m.start()),
                              context=re.sub(r"\s+", " ", t[max(0, m.start() - 50):m.end() + 30])))
    return {"files": [p.name for p, _ in files], "moved_labels": len(lm), "staying_labels": len(ls),
            "A_stay_to_moved": a, "B_moved_to_stay": b,
            "C_cites_only_moved": sorted(cites(moved) - cites(stay)),
            "D_container_words": words, "labels_in_both": sorted(lm & ls)}


def report(r: dict) -> str:
    out = [f"files read: {', '.join(r['files'])}", f"labels: moved {r['moved_labels']}, staying {r['staying_labels']}"]
    for key, head in [("A_stay_to_moved", "A. staying text -> moved labels (repoint in the source document)"),
                      ("B_moved_to_stay", "B. moved text -> staying labels (xr prefix + citation in the new document)")]:
        out.append(f"\n{head}: {len(r[key])}")
        out += [f"  {x['at']}  {x['label']}  | {x['context']}" for x in r[key]]
    out.append(f"\nC. citations used only in the moved part: {len(r['C_cites_only_moved'])}")
    out += ["  " + k for k in r["C_cites_only_moved"]]
    out.append(f"\nD. words naming the old container in the moved part: {len(r['D_container_words'])}")
    out += [f"  {x['at']}  \"{x['word']}\"  | {x['context']}" for x in r["D_container_words"]]
    if r["labels_in_both"]:
        out.append("\nlabels defined on both sides (fix before moving): " + ", ".join(r["labels_in_both"]))
    return "\n".join(out)


def selftest() -> int:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "main.tex").write_text(
            "\\newcommand{\\er}{\\eqref}\n\\begin{document}\n"
            "\\section{Intro}\\label{sec:intro}\nSee Appendix~\\ref{app:x} and \\er{eq:x}. % \\ref{app:y}\n"
            "Also \\cite{common}.\n\\begin{equation}a\\label{eq:a}\\end{equation}\n"
            "\\appendix\n\\section{Extra part}\n\\label{app:x}\nThis appendix uses \\er{eq:a} of Sec.~\\ref{sec:intro} and \\cite{only,common}.\n"
            "\\begin{equation}b\\label{eq:x}\\end{equation}\n"
            "\\input{part}\n\\section{Kept}\\label{app:k}\nKept \\cref{eq:y,eq:a}.\n\\bibliography{refs}\n\\end{document}\n",
            encoding="utf-8")
        (d / "part.tex").write_text("\\section{Other}\\label{app:y}\nIn the main text \\ref{sec:intro}.\n"
                                    "\\begin{equation}c\\label{eq:y}\\end{equation}\n", encoding="utf-8")
        r = analyse(d / "main.tex", ["extra part"], ["part.tex"], [])
        ok = True

        def expect(cond, msg):
            nonlocal ok
            print(("PASS " if cond else "FAIL ") + msg)
            ok &= bool(cond)
        expect(sorted(x["label"] for x in r["A_stay_to_moved"]) == ["app:x", "eq:x", "eq:y"],
               "A lists staying refs into moved labels, through the \\er alias and a \\cref list, not the comment")
        expect(sorted(x["label"] for x in r["B_moved_to_stay"]) == ["eq:a", "sec:intro", "sec:intro"],
               "B lists moved refs into staying labels, from the section and the moved file")
        expect(r["C_cites_only_moved"] == ["only"], "C lists citations only in the moved part")
        expect(sorted(x["word"].lower() for x in r["D_container_words"]) == ["main text", "this appendix"], "D lists container words, case-insensitive")
        expect(all(x["at"].startswith(("main.tex:", "part.tex:")) for x in r["A_stay_to_moved"] + r["B_moved_to_stay"]), "locations carry file:line")
        expect(analyse(d / "main.tex", ["no such"], [], []).get("error", "").startswith("section not found"), "unknown section is an error")
        a_lines = {x["at"] for x in r["A_stay_to_moved"]}
        expect(a_lines == {"main.tex:4", "main.tex:14"}, "line numbers count from the file start")
    print("ALL PASS" if ok else "SOME FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?")
    ap.add_argument("--move-section", action="append", default=[])
    ap.add_argument("--move-file", action="append", default=[])
    ap.add_argument("--ref-macro", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.root or not (a.move_section or a.move_file):
        ap.error("root .tex and at least one --move-section or --move-file are required")
    r = analyse(Path(a.root), a.move_section, a.move_file, a.ref_macro)
    if "error" in r:
        print(r["error"], file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
