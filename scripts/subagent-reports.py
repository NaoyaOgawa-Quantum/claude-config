#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subagent-reports.py — ある session が使った agent (subagent) の最終報告を、 会話記録から読み出す。--selftest 内蔵。

用途: agent の最終報告は呼び出した側の context にだけ渡り、 user には見えない。 文脈圧縮のあとや
session の締めの整理 (知見を正本へ移す) で、 委ねた先で分かったことを取りこぼさないために、
記録から報告を引き直す。

読む記録:
  <projects-dir>/<project>/<session id>/subagents/agent-*.jsonl  (Claude Code)
  同じ名前の agent-*.meta.json があれば description / agentType を添える。
  報告 = その jsonl の最後の assistant 発言の text (tool 呼び出しだけの発言は飛ばす)。

projects-dir の既定 (先に見つかった方から全部):
  - --projects-dir の指定
  - 環境変数 CLAUDE_CONFIG_DIR が指す dir の projects/ (Claude Code の設定 dir を切り替えている場合)
  - ~/.claude/projects
  ⚠️ 0 件 = 「その session は agent を使っていない」 か「別の設定 dir の記録」。 どちらかは見た dir を出すので読み分ける。

使い方:
  subagent-reports.py <session id か先頭の数文字>       # 既定は環境変数 CLAUDE_CODE_SESSION_ID
  subagent-reports.py bbb02153 --max-chars 2000
  subagent-reports.py bbb02153 --json

OS: macOS / Linux / Windows (Git Bash・PowerShell) で同じに動く (標準 library だけ、 Python 3.8+、 path は pathlib、
出力は UTF-8 に固定 = Windows の cp932 console で絵文字が UnicodeEncodeError にならない)。
"""
import argparse
import json
import os
import sys
from pathlib import Path


def _utf8_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def candidate_projects_dirs(explicit=None):
    if explicit:
        return [Path(explicit).expanduser()]
    dirs = []
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        dirs.append(Path(env).expanduser() / "projects")
    dirs.append(Path.home() / ".claude" / "projects")
    seen, out = set(), []
    for d in dirs:
        key = str(d.resolve()) if d.exists() else str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def find_agent_files(projects_dirs, session):
    found = []
    for pdir in projects_dirs:
        if not pdir.is_dir():
            continue
        for proj in sorted(pdir.iterdir()):
            if not proj.is_dir():
                continue
            for sdir in sorted(proj.glob(session + "*")):
                sub = sdir / "subagents"
                if sub.is_dir():
                    found.extend(sorted(sub.glob("agent-*.jsonl")))
    return found


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content
                 if isinstance(c, dict) and c.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def read_report(path):
    """(meta, last assistant text, last timestamp)。 壊れた行は飛ばす。"""
    meta = {}
    mpath = path.with_name(path.name[:-len(".jsonl")] + ".meta.json")
    if mpath.is_file():
        try:
            meta = json.loads(mpath.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            meta = {}
    last_text, last_ts = "", ""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            text = _text_of((rec.get("message") or {}).get("content"))
            if text.strip():
                last_text, last_ts = text, rec.get("timestamp", "")
    return meta, last_text, last_ts


def main(argv=None):
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="session が使った agent の最終報告を読み出す")
    ap.add_argument("session", nargs="?", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
                    help="session id か先頭の数文字 (既定 = $CLAUDE_CODE_SESSION_ID)")
    ap.add_argument("--projects-dir", default="")
    ap.add_argument("--max-chars", type=int, default=4000, help="1 報告の表示上限 (0 = 全文)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.session:
        ap.error("session id を渡す (または CLAUDE_CODE_SESSION_ID を設定)")
    pdirs = candidate_projects_dirs(args.projects_dir or None)
    files = find_agent_files(pdirs, args.session)
    rows = []
    for f in files:
        meta, text, ts = read_report(f)
        rows.append({"file": str(f), "agentType": meta.get("agentType", ""),
                     "description": meta.get("description", ""), "timestamp": ts, "report": text})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print("見た dir: " + ", ".join(str(d) for d in pdirs))
    print("agent の記録: {} 件 (session {})".format(len(rows), args.session))
    for i, r in enumerate(rows, 1):
        body = r["report"] or "(text の報告なし)"
        if args.max_chars and len(body) > args.max_chars:
            body = body[:args.max_chars] + "\n… (以下略、 --max-chars 0 で全文)"
        print("\n--- [{}] {} {} {}".format(i, r["agentType"], r["description"], r["timestamp"]).rstrip())
        print("    " + r["file"])
        print(body)
    return 0


def selftest():
    import io
    import tempfile
    from contextlib import redirect_stdout
    failures = []

    def check(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)
            if detail:
                print("     " + detail[:800])

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "projects"
        sub = root / "-proj" / "abcd1234-0000" / "subagents"
        sub.mkdir(parents=True)
        recs = [
            {"type": "user", "message": {"content": "do it"}},
            {"type": "assistant", "timestamp": "t1", "message": {"content": [{"type": "text", "text": "途中経過"}]}},
            {"type": "assistant", "timestamp": "t2", "message": {"content": [{"type": "text", "text": "最終報告 ✅"}]}},
            {"type": "assistant", "timestamp": "t3", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
        ]
        (sub / "agent-x1.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n{broken\n", encoding="utf-8")
        (sub / "agent-x1.meta.json").write_text(json.dumps({"agentType": "opus55", "description": "調べる"}),
                                                encoding="utf-8")
        other = root / "-proj" / "ffff0000" / "subagents"
        other.mkdir(parents=True)
        (other / "agent-y.jsonl").write_text(json.dumps(recs[2]) + "\n", encoding="utf-8")

        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["abcd", "--projects-dir", str(root), "--json"])
        rows = json.loads(out.getvalue())
        check("prefix で該当 session だけを拾う", rc == 0 and len(rows) == 1, out.getvalue())
        check("最後の text 発言を報告にする (tool だけの発言・壊れた行は飛ばす)",
              rows and rows[0]["report"] == "最終報告 ✅" and rows[0]["timestamp"] == "t2", out.getvalue())
        check("meta の description を添える", rows and rows[0]["description"] == "調べる", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            main(["zzzz", "--projects-dir", str(root)])
        check("0 件は 0 件と見た dir を出す", "0 件" in out.getvalue() and str(root) in out.getvalue(),
              out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            main(["abcd", "--projects-dir", str(root), "--max-chars", "3"])
        check("--max-chars で切る", "最終報\n… (以下略" in out.getvalue(), out.getvalue())
    print("\n{}: {} failure(s)".format("FAIL" if failures else "OK", len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
