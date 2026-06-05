#!/usr/bin/env python3
"""One-shot migration: office-automation.md positional §-numbers -> stable slug IDs.

Drives three deterministic operations from a single embedded slug map:
  build-index : parse office-automation.md, emit conventions/office-automation.index.yaml
  rewrite-doc : drop leading §-number from each heading + add <a id="slug">; rewrite
                intra-file §-refs -> [`slug`](#slug). Skips fenced code blocks and any
                §-number NOT in the map (= external refs to CLAUDE.md inline, left intact).
  rewrite-ref FILE : rewrite §<legacy> -> [`slug`](#slug) inside an inbound pointer file
                (active pointers only; historical/dated records are passed over by hand).

Content invariant: only heading lines and §-ref tokens change. Verify with
`git diff --word-diff`. Re-runnable: rewrite passes are idempotent (already-slugged refs
have no bare §-token left to match).
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "conventions" / "office-automation.md"
INDEX = REPO / "conventions" / "office-automation.index.yaml"

# legacy §-number -> stable slug.  Hand-authored, semantic, generic (no names/institutions).
SLUG = {
    "0": "form-dump-first",
    "0.5": "form-filename-convention",
    "1": "openpyxl-xlsx-fill",
    "1-1": "xlimage-size-silent-fail",
    "1-1b": "sheet-by-name-not-index",
    "1-2": "image-anchor-onecellanchor",
    "1-3": "column-width-units",
    "1-4": "wrap-text-needs-row-height",
    "1-5": "data-validation-not-enforced",
    "1-6": "xlsx-locked-by-excel",
    "1-7": "merged-cell-write-topleft",
    "1-8": "bool-cell-hash-overflow",
    "1-8b": "datetime-cell-hash-overflow",
    "1-9": "int-vs-str-by-spec",
    "1-10": "print-area-one-page",
    "1-11": "row-height-409pt-limit",
    "1-12": "topleftcell-scroll-persist",
    "1-13": "xlsx-rich-text-underline",
    "2": "xlsx-md-to-pdf",
    "2-1": "xlsx-to-pdf-script",
    "2-2": "md-to-pdf-chrome",
    "2-3": "pdf-snapshot-xlsx-submission",
    "2-4": "docx-to-pdf-pages",
    "2-4b": "docx-pdf-stale-cache",
    "2-5": "docx-fill-xml-edit",
    "2-5b": "docx-checkbox-content-control",
    "2-5c": "docx-guidance-deletion",
    "2-6": "erad-forbidden-chars",
    "2-7": "signature-not-stamp",
    "2-7b": "physical-seal-required",
    "2-8": "placeholder-trailing-underscore",
    "2-9": "docx-pdf-page-compress",
    "3": "tts-review",
    "4": "common-discipline",
    "4-1": "dump-cell-structure-first",
    "4-2": "char-limit-formula-check",
    "4-3": "visual-check-by-user",
    "5": "label-vs-input-antipattern",
    "5-1": "label-input-structure",
    "5-2": "label-overwrite-bug",
    "5-3": "diff-form-xlsx-detection",
    "5-4": "fill-prevention-workflow",
    "5-5": "embedded-instruction-in-label",
    "5-6": "label-detection-at-dump",
    "5-7": "choice-label-marking",
    "5-8": "multi-sheet-formula-propagation",
    "5-9": "clear-yellow-fill-marks",
    "6": "xlsx-visual-unobservable",
    "6-1": "claude-cannot-observe-render",
    "6-2": "wrap-text-row-height-prereq",
    "6-3": "explicit-newline-break",
    "6-4": "pdf-visual-confirm",
    "6-5": "image-budget-exhaustion",
    "7": "multi-sheet-form",
    "7-1": "all-sheet-sweep",
    "7-2": "cross-sheet-formula-chain",
    "7-3": "side-by-side-page-split",
    "7-4": "hidden-sheet-user-expectation",
    "7-5": "same-pattern-grep-sweep",
    "8": "print-area-pagebreak",
    "8-1": "print-area-tradeoff",
    "8-2": "fittopage-vs-scale",
    "8-3": "multiple-print-areas",
    "8-4": "row-col-breaks",
    "8-5": "print-setup-visual-confirm",
    "8-6": "print-dialog-whole-workbook",
    "9": "label-overwrite-detection-limit",
    "9-1": "detection-miss-example",
    "9-2": "manual-review-required",
    "9-3": "header-row-detection-helper",
    "10": "business-trip-proof-forward",
    "10-1": "forward-mail-template",
    "10-2": "forward-mail-components",
    "10-3": "forward-record-sync",
    "11": "external-vs-internal-form",
    "11-1": "external-internal-structure-diff",
    "11-2": "seal-field-verify-method",
    "11-3": "tpl-only-false-positive",
    "12": "seal-approval-sweep",
    "12-1": "seal-keyword-set",
    "12-2": "seal-diff-with-template",
    "12-3": "seal-question-reflex",
    "12-4": "seal-image-generation-embed",
    "13": "related-repos",
}

HEAD_RE = re.compile(r"^(#{2,3})\s+([0-9]+(?:\.[0-9]+)?(?:-[0-9]+[a-z]?)?)\.\s+(.*)$")
# §-ref token: longest legacy first so 1-8b beats 1-8, 0.5 beats 0.
REF_KEYS = sorted(SLUG, key=len, reverse=True)
REF_RE = re.compile("§(" + "|".join(re.escape(k) for k in REF_KEYS) + r")(?![0-9A-Za-z\-])")


def parse_sections(text):
    """-> list of dicts: legacy, level, title, body, start_line."""
    lines = text.split("\n")
    secs, cur = [], None
    in_fence = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
        m = HEAD_RE.match(ln) if not in_fence else None
        if m:
            if cur:
                secs.append(cur)
            cur = {"legacy": m.group(2), "level": len(m.group(1)),
                   "title": m.group(3).strip(), "body": [], "line": i}
        elif cur:
            cur["body"].append(ln)
    if cur:
        secs.append(cur)
    return secs


def body_refs(body_lines):
    """slugs referenced in a section body (skip fenced code), excluding unknown numbers."""
    out, in_fence = [], False
    for ln in body_lines:
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for num in REF_RE.findall(ln):
            s = SLUG[num]
            if s not in out:
                out.append(s)
    return out


def yaml_q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_index():
    text = DOC.read_text(encoding="utf-8")
    secs = parse_sections(text)
    seen = [s["legacy"] for s in secs]
    missing = [k for k in SLUG if k not in seen]
    extra = [s["legacy"] for s in secs if s["legacy"] not in SLUG]
    if missing or extra:
        print(f"WARN map/doc mismatch: missing_in_doc={missing} not_in_map={extra}", file=sys.stderr)

    out = ["# Stable slug index for office-automation.md (Phase 1 slug migration).",
           "# id = canonical identity (cross-refs use it). legacy = pre-migration §-number,",
           "# kept ONLY here so dated/historical inbound refs (§2-5b etc.) stay resolvable.",
           "# related = slugs this section cross-references. Validated by",
           "# scripts/check-office-automation-index.py (dangling=0 / orphan=0).",
           "sections:"]
    for s in secs:
        slug = SLUG.get(s["legacy"], "UNMAPPED")
        rel = [r for r in body_refs(s["body"]) if r != slug]
        org = ""
        for ln in s["body"]:
            mo = re.search(r"origin[:：].*?(20[0-9]{2})[-/.年]\s*([0-9]{1,2})", ln)
            if mo:
                org = f"{mo.group(1)}-{int(mo.group(2)):02d}"
                break
        out.append(f"  - id: {slug}")
        out.append(f"    legacy: {yaml_q(s['legacy'])}")
        out.append(f"    level: {s['level']}")
        out.append(f"    title: {yaml_q(s['title'])}")
        if org:
            out.append(f"    origin: {yaml_q(org)}")
        if rel:
            out.append(f"    related: [{', '.join(rel)}]")
    INDEX.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {INDEX.relative_to(REPO)}  ({len(secs)} sections)")


def rewrite_refs(text):
    """§<known> -> slug. In prose: markdown link [`slug`](#slug). Inside fenced code
    (comments): bare slug, since markdown link syntax would render literally there.
    External numbers (not in map) are never matched. Idempotent."""
    out, in_fence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(ln)
            continue
        if in_fence:
            out.append(REF_RE.sub(lambda m: SLUG[m.group(1)], ln))
        else:
            out.append(REF_RE.sub(lambda m: f"[`{SLUG[m.group(1)]}`](#{SLUG[m.group(1)]})", ln))
    return "\n".join(out)


def rewrite_doc():
    text = DOC.read_text(encoding="utf-8")
    # 1) refs (also rewrites the top banner's §6-4/§6-5/§2-4b mentions)
    text = rewrite_refs(text)
    # 2) headings: drop leading "<num>. " and prepend an invisible anchor
    out, in_fence = [], False
    for ln in text.split("\n"):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(ln)
            continue
        m = HEAD_RE.match(ln) if not in_fence else None
        if m and m.group(2) in SLUG:
            hashes, _, title = m.group(1), m.group(2), m.group(3)
            slug = SLUG[m.group(2)]
            out.append(f'{hashes} <a id="{slug}"></a>{title}')
        else:
            out.append(ln)
    DOC.write_text("\n".join(out), encoding="utf-8")
    print(f"rewrote {DOC.relative_to(REPO)}")


def rewrite_ref_file(path):
    p = Path(path)
    before = p.read_text(encoding="utf-8")
    after = rewrite_refs(before)
    if before == after:
        print(f"no change: {path}")
        return
    p.write_text(after, encoding="utf-8")
    n = sum(1 for _ in REF_RE.finditer(before))
    print(f"rewrote {n} ref(s): {path}")


# inbound: only §<legacy> ANCHORED to the office-automation.md filename, so a doc's own
# "本節 §1-5" is never mis-touched. Collapses "office-automation.md §5-3" -> ".md#slug".
INBOUND_RE = re.compile(r"office-automation\.md\s*§(" + "|".join(re.escape(k) for k in REF_KEYS)
                        + r")(?![0-9A-Za-z\-])")


def rewrite_inbound(path):
    p = Path(path)
    before = p.read_text(encoding="utf-8")
    hits = [m.group(1) for m in INBOUND_RE.finditer(before)]
    after = INBOUND_RE.sub(lambda m: f"office-automation.md#{SLUG[m.group(1)]}", before)
    if before == after:
        print(f"no anchored ref: {path}")
        return
    p.write_text(after, encoding="utf-8")
    print(f"rewrote {len(hits)} anchored ref(s) {['§'+h for h in hits]}: {path}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build-index"
    if cmd == "build-index":
        build_index()
    elif cmd == "rewrite-doc":
        rewrite_doc()
    elif cmd == "rewrite-ref":
        rewrite_ref_file(sys.argv[2])
    elif cmd == "rewrite-inbound":
        for f in sys.argv[2:]:
            rewrite_inbound(f)
    else:
        sys.exit(f"unknown cmd: {cmd}")
