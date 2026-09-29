#!/usr/bin/env python3
"""transcript-tool-result.py — Claude Code の会話記録 (jsonl) から tool の戻り値を file に取り出す

用途: browser の `javascript_tool` などが返した大きな値 (画素の probe 結果、 表の dump) を Python 側で
検査したいとき、 戻り値を読んで file に書き写すと数値の写し間違い (= 生成) が混じる。 戻り値は
transcript に残っているので、 目印の文字列で探して機械的に取り出す。
手順 = conventions/preview.md#tool-result-to-file

使い方:
  transcript-tool-result.py <transcript.jsonl | session id の先頭> --contains 語 --list
  transcript-tool-result.py <…> --contains 語 [--nth N] [--json-string] [--json] --out FILE
    --contains     戻り値の本文に含まれる目印 (必須)。 一致が複数あれば --nth で選ぶまで書かない
    --nth          一致の何番目か (0 始まり、 -1 = 最後)
    --json-string  本文の先頭の JSON 文字列 literal を 1 段 decode する (javascript_tool は値を JSON で返す)
    --json         (decode 後の) 本文を JSON として読めることを確かめ、 整形せずに書く
  transcript-tool-result.py --selftest
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile


def find_transcript(arg: str) -> str | None:
    if os.path.isfile(arg):
        return arg
    hits = sorted(glob.glob(os.path.expanduser(f"~/.claude/projects/*/{arg}*.jsonl")))
    return hits[0] if len(hits) == 1 else None


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def collect(path: str) -> list[dict]:
    """tool の戻り値を順に。 [{line, tool, text}] (tool = 呼び出した tool の名前、 分からなければ "")"""
    names: dict[str, str] = {}
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not isinstance(e, dict):
                continue
            content = (e.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if not isinstance(b, dict):
                    continue
                if e.get("type") == "assistant" and b.get("type") == "tool_use":
                    names[b.get("id", "")] = b.get("name", "")
                elif e.get("type") == "user" and b.get("type") == "tool_result":
                    out.append({"line": i, "tool": names.get(b.get("tool_use_id", ""), ""),
                                "text": _text_of(b.get("content"))})
    return out


def decode_json_string(text: str) -> str:
    """先頭の JSON 文字列 literal を decode (後ろに付く tab context などの文は捨てる)。"""
    value, _ = json.JSONDecoder().raw_decode(text.lstrip())
    if not isinstance(value, str):
        raise ValueError("先頭が JSON の文字列 literal ではない")
    return value


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("transcript", nargs="?")
    ap.add_argument("--contains")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--nth", type=int)
    ap.add_argument("--json-string", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.transcript or not a.contains:
        ap.error("transcript と --contains が要る")
    path = find_transcript(a.transcript)
    if path is None:
        print(f"transcript が 1 つに決まらない: {a.transcript}", file=sys.stderr)
        return 2
    hits = [r for r in collect(path) if a.contains in r["text"]]
    if a.list or (a.nth is None and len(hits) != 1):
        for k, r in enumerate(hits):
            print(f"[{k}] line {r['line']} {r['tool'] or '?'} {len(r['text'])} 字: {r['text'][:80]!r}")
        if not a.list:
            print(f"一致が {len(hits)} 件 = --nth で選ぶ (書いていない)", file=sys.stderr)
            return 2
        return 0
    try:
        text = hits[a.nth if a.nth is not None else 0]["text"]
    except IndexError:
        print(f"--nth {a.nth} は範囲外 (一致 {len(hits)} 件)", file=sys.stderr)
        return 2
    if a.json_string:
        text = decode_json_string(text)
    if a.json:
        json.loads(text)                       # 読めなければ例外 = 書かない
    if not a.out:
        ap.error("--out が要る (--list 以外)")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {a.out} ({len(text)} 字, line {hits[a.nth or 0]['line']})")
    return 0


def selftest() -> int:
    fails = []

    def check(label: str, ok: bool) -> None:
        print(("  ok: " if ok else "  NG: ") + label)
        if not ok:
            fails.append(label)

    payload = json.dumps([{"w": 4, "s": [[0, 1, 2.5]]}])
    rows = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "javascript_tool", "input": {"text": "x"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": [{"type": "text", "text": json.dumps(payload) + "\n\nTab Context: ..."}]}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "echo MARK"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t2", "content": "MARK other"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t9", "content": "MARK third"}]}},
        [1, 2, 3],
    ]
    with tempfile.TemporaryDirectory() as d:
        tr = os.path.join(d, "s.jsonl")
        with open(tr, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write("{broken\n")
        got = collect(tr)
        check("tool_result を順に集め、 壊れた行と配列だけの行を飛ばす", len(got) == 3)
        check("呼び出した tool の名前を引く", got[0]["tool"] == "javascript_tool" and got[2]["tool"] == "")
        out = os.path.join(d, "o.json")
        rc = main([tr, "--contains", '\\"w\\": 4', "--json-string", "--json", "--out", out])
        check("JSON 文字列を 1 段 decode して書く", rc == 0 and json.loads(open(out).read())[0]["w"] == 4)
        rc = main([tr, "--contains", "MARK", "--out", out])
        check("一致が複数なら --nth まで書かない", rc == 2)
        rc = main([tr, "--contains", "MARK", "--nth", "-1", "--out", out])
        check("--nth -1 で最後の一致", rc == 0 and open(out).read() == "MARK third")
        rc = main([tr, "--contains", "absent", "--out", out])
        check("一致 0 件でも書かない", rc == 2)
        try:
            decode_json_string("[1, 2]")
            check("先頭が文字列でなければ拒む", False)
        except ValueError:
            check("先頭が文字列でなければ拒む", True)
    print("selftest:", "ALL PASS" if not fails else f"{len(fails)} FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
