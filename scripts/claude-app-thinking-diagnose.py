#!/usr/bin/env python3
"""Claude for Mac (Code タブ) で思考 (thinking) の要約が画面に出ない原因を read-only で診断する (conventions/macos-claude-app-thinking-display.md)。

見るもの (同 doc #diagnose):
  1. app と埋込 engine の版 (挙動は版で変わる)
  2. 動いている engine process の起動引数 --thinking-display (omitted = 思考の要約を受け取らない)
  3. app の log の切替記録 "[CCD] thinking display → summarized (view_open)" / "→ omitted (view_close_debounce)"
  4. transcript (jsonl) の thinking block のうち本文があるものの数 (本文が空で署名だけ = 受け取っていない)
  5. ~/.claude/settings.json の showThinkingSummaries (desktop では起動引数が優先されて効かない)

何も書き換えない (ps / file read のみ)。

Usage:
  python3 scripts/claude-app-thinking-diagnose.py                  # 全部 (transcript は最近更新された 5 本)
  python3 scripts/claude-app-thinking-diagnose.py --session 1a2b3c4d   # transcript を session id の先頭で指定
  python3 scripts/claude-app-thinking-diagnose.py --transcript <path.jsonl>
  python3 scripts/claude-app-thinking-diagnose.py --selftest
"""
from __future__ import annotations

import argparse
import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path

APP_PLIST = Path("/Applications/Claude.app/Contents/Info.plist")
ENGINE_ROOT = Path.home() / "Library/Application Support/Claude/claude-code"
LOG_DIR = Path.home() / "Library/Logs/Claude"
PROJECTS = Path.home() / ".claude/projects"
USER_SETTINGS = Path.home() / ".claude/settings.json"

FLIP_RE = re.compile(r"^(\S+ \S+) .*\[CCD\] thinking display → (\w+) \((\w+)\)")
UI_PATH = "セッションのタイトル横の「⌄」 →「トランスクリプト表示」 →「思考」 (常にするなら同じ submenu の「思考をデフォルトにする」)"


def parse_engine_args(cmd: str) -> dict | None:
    """desktop が起動した engine process の command line から model / effort / thinking-display を取る。"""
    if "/claude-code/" not in cmd or "--output-format stream-json" not in cmd:
        return None
    if "disclaimer" in cmd.split(" --", 1)[0]:
        return None  # 起動用の wrapper process (同じ引数を持つので二重に数えない)

    def opt(name: str) -> str | None:
        m = re.search(rf"--{name}[ =](\S+)", cmd)
        return m.group(1) if m else None

    ver = re.search(r"/claude-code/([\d.]+)/", cmd)
    return {"engine": ver.group(1) if ver else "?", "model": opt("model"),
            "effort": opt("effort"), "thinking_display": opt("thinking-display")}


def count_thinking(lines) -> dict:
    """jsonl の行から thinking block を数える。 本文が空で署名だけのものは「受け取っていない」 印。"""
    total = with_text = 0
    for line in lines:
        if '"thinking"' not in line:
            continue
        try:
            content = (json.loads(line).get("message") or {}).get("content")
        except (ValueError, AttributeError):
            continue
        if not isinstance(content, list):
            continue
        for b in content:
            if isinstance(b, dict) and b.get("type") == "thinking":
                total += 1
                with_text += bool((b.get("thinking") or "").strip())
    return {"total": total, "with_text": with_text}


def app_versions() -> tuple[str, list[str]]:
    app = "?"
    try:
        app = plistlib.loads(APP_PLIST.read_bytes()).get("CFBundleShortVersionString", "?")
    except OSError:
        pass
    engines = sorted((p.name for p in ENGINE_ROOT.glob("*") if p.is_dir()),
                     key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")])
    return app, engines


def running_engines() -> list[dict]:
    out = subprocess.run(["ps", "-axo", "pid=,etime=,command="], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        info = parse_engine_args(parts[2])
        if info:
            rows.append({"pid": parts[0], "elapsed": parts[1], **info})
    return rows


def recent_flips(limit: int) -> list[tuple[str, str, str]]:
    flips = []
    for f in sorted(LOG_DIR.glob("main*.log")):
        try:
            for line in f.read_text(errors="replace").splitlines():
                m = FLIP_RE.match(line)
                if m:
                    flips.append(m.groups())
        except OSError:
            continue
    return sorted(flips)[-limit:]


def pick_transcripts(args) -> list[Path]:
    if args.transcript:
        return [Path(args.transcript).expanduser()]
    if args.session:
        return sorted(PROJECTS.glob(f"*/{args.session}*.jsonl"))
    files = sorted(PROJECTS.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:args.recent]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--session", help="transcript を session id の先頭で指定")
    ap.add_argument("--transcript", help="transcript (jsonl) の path")
    ap.add_argument("--recent", type=int, default=5, help="指定が無いとき見る transcript の本数")
    ap.add_argument("--flips", type=int, default=5, help="log の切替記録を何行出すか")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    app, engines = app_versions()
    print(f"# 版: app {app} / engine {', '.join(engines[-2:]) or '?'}")

    print("\n# 動いている engine の起動引数 (--thinking-display)")
    procs = running_engines()
    for p in procs:
        print(f"  pid {p['pid']:>6} {p['elapsed']:>11}  {p['model'] or '-':<20} effort={p['effort'] or '-':<7}"
              f" thinking-display={p['thinking_display'] or '(指定なし)'}")
    if not procs:
        print("  (desktop が起動した engine は見当たらない)")
    omitted = [p for p in procs if p["thinking_display"] == "omitted"]

    print(f"\n# app の log の切替記録 (古い順、 末尾 {args.flips} 件)")
    flips = recent_flips(args.flips)
    for ts, to, why in flips:
        print(f"  {ts}  → {to} ({why})")
    if not flips:
        print("  (記録なし = この期間に「思考」 表示へ切り替えたセッションが無い)")

    print("\n# transcript の thinking block (本文あり / 全体)")
    for f in pick_transcripts(args):
        try:
            c = count_thinking(f.open(errors="replace"))
        except OSError as e:
            print(f"  {f.name[:8]}  読めない: {e}")
            continue
        print(f"  {f.name[:8]}  {c['with_text']:>5} / {c['total']:<5}")

    try:
        sts = json.loads(USER_SETTINGS.read_text()).get("showThinkingSummaries")
    except (OSError, ValueError):
        sts = None
    print(f"\n# ~/.claude/settings.json showThinkingSummaries = {sts!r}"
          + (" (desktop では起動引数 --thinking-display が優先され、 効かない)" if sts is not None else ""))

    print("\n# 読み方")
    if omitted:
        print(f"  - {len(omitted)} 本が omitted で起動 = 画面が「思考」 表示でない間は思考の要約を受け取らない。"
              " 起動引数は起動時の値のままなので、 後で「思考」 に切り替えたセッションも omitted と出る (効いたかは log と transcript で見る)。")
    print(f"  - 表示の切替 = {UI_PATH}")
    print("  - 切り替えは次の応答から効く。 切り替える前のターンの思考は署名だけで、 後から出せない。")
    print("  - 画面で切り替えても log に view_open が出ないなら、 画面と app 本体が噛み合っていない = ウィンドウを再読み込み (doc #stale-renderer)。")
    print("  - 思考は出るがツールのまとまりの中に畳まれて 1 行しか見えない = 新しいレイアウト。 全部開くのは「詳細」 表示、"
          " 既定は 設定 → 外観 →「デフォルトのトランスクリプト表示」 (doc #grouped-layout-collapsed)。")
    return 0


def selftest() -> int:
    ok = True

    def check(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print(f"FAIL {name}: {got!r} != {want!r}")

    cmd = ("/opt/fixture/Claude/claude-code/2.1.281/claude.app/Contents/MacOS/claude "
           "--output-format stream-json --verbose --input-format stream-json --effort xhigh "
           "--model claude-opus-5-5 --thinking-display omitted --allowedTools a,b")
    check("parse", parse_engine_args(cmd), {"engine": "2.1.281", "model": "claude-opus-5-5",
                                           "effort": "xhigh", "thinking_display": "omitted"})
    check("wrapper skipped", parse_engine_args("/Applications/Claude.app/Contents/Helpers/disclaimer --pgroup -- " + cmd), None)
    check("cli not desktop", parse_engine_args("/usr/local/bin/claude --model x"), None)
    lines = [
        json.dumps({"message": {"content": [{"type": "thinking", "thinking": "", "signature": "s"}]}}),
        json.dumps({"message": {"content": [{"type": "thinking", "thinking": "reasoning", "signature": "s"},
                                            {"type": "text", "text": "hi"}]}}),
        json.dumps({"message": {"content": "plain"}}),
        "not json \"thinking\"",
    ]
    check("count", count_thinking(lines), {"total": 2, "with_text": 1})
    m = FLIP_RE.match("2026-01-02 03:04:05 [info] [CCD] thinking display → summarized (view_open) for local_x")
    check("flip", m.groups() if m else None, ("2026-01-02 03:04:05", "summarized", "view_open"))
    print("selftest ok" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
