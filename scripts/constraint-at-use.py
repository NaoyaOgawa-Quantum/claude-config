#!/usr/bin/env python3
"""constraint-at-use.py — 制約表 (markdown table) の行を、 その道具・file を使う瞬間の PreToolUse hook で session に 1 回だけ出す (auto-load 面から降ろした制約の point-of-use 配達)

層1 engine (2026-10-04)。 「触る前に効く制約」 の表 (1 列目 = 対象の道具・台帳の名、 2 列目 = 制約) を毎 session
auto-load される CLAUDE.md に置くと、 道具ごとに 1 行足す構造ゆえ際限なく育ち、 memory file の予算に張り付く
(RCA = 利用者の層の plan、 実測で 33 KB / 54 行)。 本 engine は表を auto-load されない file へ降ろす代わりに、
**道具を Bash で叩く瞬間・台帳 file を開く瞬間に、 該当する行だけを additionalContext で 1 回出す**。 読む側が
100 KB 手前の preamble から思い出すのでなく、 tool 結果の直前にその行が居る。

key の導出 (= 対応表を別に持たない、 convention-design-principles.md#detector-config-must-be-derived):
  1 列目の token のうち ① backtick の中 ② 5 字以上で `-` `_` `.` `/` のどれかを含む (= script / file 名の形) を key に
  する。 `<id>` 等の placeholder は「/ と空白以外の任意」、 `{a,b}` は選択肢に展開。 key は Bash の command と
  file 系 tool (Edit / Write / MultiEdit / Read / NotebookEdit) の path に対して substring (regex) で当てる。
  1 列目から key が導けない行 (「Remote Control の auth」 等) は、 表の file の HTML comment で足す:
      <!-- constraint-keys
      - <1 列目の頭 (prefix)> :: <regex>
      -->
  (= 同じ file の中、 描画されない、 規則の文は触らない)。 `--check` が key の無い行を列挙して exit 1 で止める
  (= 足した行が黙って「出ない行」 にならない)。

出し方: 1 回の tool call で最大 --max 行 (既定 2)、 同じ行は 1 session に 1 回 (state = <state-dir>/<session_id>、
machine-local)。
出力は PreToolUse の additionalContext (止めない。 deny は別の guard の仕事)。 全 error path で fail-open (無言 exit 0)。
自分 (engine 名) を含む command には出さない (表の file 名は除外しない = 表を開く瞬間に行の足し方の行が出るのは望む挙動)。

usage:
  constraint-at-use.py --table T.md [--table U.md]... [--state-dir DIR] [--max N]      # hook (stdin = PreToolUse JSON)
  constraint-at-use.py --table T.md --probe '<command or path>' [--tool Bash]           # どの行が出るか (state は書かない)
  constraint-at-use.py --table T.md --check                                            # 行と key の一覧、 key 無しの行があれば exit 1
  constraint-at-use.py --selftest

public-safe / stdlib only。 表の path・state の場所は呼び手 (利用者の shim) が渡す。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

FILE_TOOLS = ("Edit", "Write", "MultiEdit", "Read", "NotebookEdit")
TOK_RE = re.compile(r"`([^`]+)`|([A-Za-z][A-Za-z0-9_.\-/<>{},]*[A-Za-z0-9>}])")
KEY_BLOCK_RE = re.compile(r"<!--\s*constraint-keys\s*\n(.*?)-->", re.S)
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state", "constraint-at-use")
HEADER = "⚠️ 触る前に効く制約 (この session で初めて触る道具の行。 正本 = {table})"


def _expand_braces(tok: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", tok)
    if not m:
        return [tok]
    out = []
    for alt in m.group(1).split(","):
        out.extend(_expand_braces(tok[: m.start()] + alt.strip() + tok[m.end():]))
    return out


def token_to_regex(tok: str) -> str:
    parts = re.split(r"(<[^>]*>)", tok)
    return "".join(r"[^/\s]*" if p.startswith("<") else re.escape(p) for p in parts if p)


def derive_keys(head: str) -> list[str]:
    keys = []
    for m in TOK_RE.finditer(head):
        tok = (m.group(1) or m.group(2) or "").strip()
        if not tok:
            continue
        if m.group(2) and not (len(tok) >= 5 and re.search(r"[-_./]", tok)):
            continue
        for t in _expand_braces(tok):
            r = token_to_regex(t)
            if r and r not in keys:
                keys.append(r)
    return keys


def load_table(path: Path) -> list[dict]:
    """[{id, head, line, keys, table}] — 最初の markdown table の行 (header と区切りを除く)。 overlay の key を足す。"""
    text = path.read_text(encoding="utf-8")
    rows = []
    in_table = False
    for line in text.split("\n"):
        if line.startswith("|"):
            if re.match(r"^\|[-\s|:]+\|?\s*$", line):
                in_table = True  # 区切り行 = ここまでが header
                continue
            if not in_table:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if len(cells) < 2:
                continue
            head = cells[0]
            rows.append({"id": hashlib.sha1(head.encode("utf-8")).hexdigest()[:12], "head": head, "line": line,
                         "keys": derive_keys(head), "table": str(path)})
        elif in_table and rows and line.strip() == "":
            break  # 表の終わり
    for blk in KEY_BLOCK_RE.findall(text):
        for l in blk.split("\n"):
            l = l.strip()
            if not l.startswith("- ") or " :: " not in l:
                continue
            prefix, rx = l[2:].split(" :: ", 1)
            hits = [r for r in rows if r["head"].startswith(prefix.strip())]
            if len(hits) == 1 and rx.strip() and rx.strip() not in hits[0]["keys"]:
                hits[0]["keys"].append(rx.strip())
    return rows


def haystack(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "Bash":
        return str(tool_input.get("command", ""))
    if tool_name in FILE_TOOLS:
        return str(tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or "")
    return None


def match_rows(rows: list[dict], text: str) -> list[dict]:
    out = []
    for r in rows:
        for k in r["keys"]:
            try:
                if re.search(k, text):
                    out.append(r)
                    break
            except re.error:
                continue
    return out


def _state_path(state_dir: str, session_id: str) -> Path:
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "nosession")[:80]
    return Path(state_dir) / sid


def _seen(state_dir: str, session_id: str) -> set[str]:
    p = _state_path(state_dir, session_id)
    try:
        return set(p.read_text(encoding="utf-8").split())
    except OSError:
        return set()


def _mark(state_dir: str, session_id: str, ids: list[str]) -> None:
    p = _state_path(state_dir, session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("".join(i + "\n" for i in ids))


def self_mention(text: str, tables: list[Path]) -> bool:
    """engine 自身を叩く command (--probe / --check / selftest) には出さない。 表の file 名は除外しない
    (= 表を開く・grep する瞬間に「行の足し方」 の行が 1 回出るのは望む挙動)。"""
    return Path(__file__).name in text


def render(rows: list[dict], table_names: str) -> str:
    body = "\n".join(r["line"] for r in rows)
    return HEADER.format(table=table_names) + "\n" + body + "\n(同じ行は 1 session に 1 回だけ出る。 表の他の行は道具の名で grep)"


def hook_main(tables: list[Path], state_dir: str, max_rows: int) -> int:
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        if ev.get("hook_event_name", "PreToolUse") != "PreToolUse":
            return 0
        text = haystack(ev.get("tool_name", ""), ev.get("tool_input") or {})
        if not text or self_mention(text, tables):
            return 0
        rows = []
        for t in tables:
            if t.is_file():
                rows.extend(load_table(t))
        hits = match_rows(rows, text)
        if not hits:
            return 0
        sid = str(ev.get("session_id") or "")
        seen = _seen(state_dir, sid)
        fresh = [r for r in hits if r["id"] not in seen][:max_rows]
        if not fresh:
            return 0
        _mark(state_dir, sid, [r["id"] for r in fresh])
        names = " / ".join(sorted({Path(r["table"]).name for r in fresh}))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": render(fresh, names)}}, ensure_ascii=False))
        return 0
    except Exception:  # noqa: BLE001  fail-open: hook の故障で tool call を止めない
        return 0


def check_main(tables: list[Path]) -> int:
    bad = 0
    for t in tables:
        rows = load_table(t)
        print(f"{t}: {len(rows)} 行")
        for r in rows:
            mark = "∅" if not r["keys"] else " "
            bad += not r["keys"]
            print(f"  {mark} {r['head'][:48]!r:52} -> {r['keys'][:4]}{' …' if len(r['keys']) > 4 else ''}")
    if bad:
        print(f"key の無い行 = {bad} (出ない行 = 表の末尾の <!-- constraint-keys --> に「- <1 列目の頭> :: <regex>」 を足す)")
    return 1 if bad else 0


def selftest() -> int:
    import shutil
    import subprocess
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="cau-selftest-"))
    ok = True

    def check(cond, label):
        nonlocal ok
        print(("  ✅ " if cond else "  ❌ ") + label)
        ok = ok and cond

    try:
        tbl = tmp / "constraints.md"
        tbl.write_text("# t\n\n| 対象 | 制約 |\n|---|---|\n"
                       "| drive-xlsx-set-cells | **他人の file は OK 経由** |\n"
                       "| todo_ledger (台帳 = `todo/<id>.yaml`、 実体は `lib/{todo_ledger,recorded_ids}.py`) | **loader 経由で読む** |\n"
                       "| Remote Control の auth | **auth_error で断定しない** |\n"
                       "| calendar.sh / calendar-events.py | **add は dry-run** |\n"
                       "\n後文\n\n<!-- constraint-keys\n- Remote Control の auth :: claude auth status|remote-control\n-->\n",
                       encoding="utf-8")
        rows = load_table(tbl)
        check(len(rows) == 4, "table: header / 区切りを除く 4 行を読む")
        k = {r["head"][:12]: r["keys"] for r in rows}
        check(k["drive-xlsx-s"] == ["drive\\-xlsx\\-set\\-cells"], "key: script 名 (- を含む bare token)")
        check(any("todo/[^/\\s]*\\.yaml" == x for x in k["todo_ledger "]), "key: `<id>` placeholder → [^/\\s]*")
        check("lib/todo_ledger\\.py" in k["todo_ledger "] and "lib/recorded_ids\\.py" in k["todo_ledger "], "key: {a,b} を展開")
        check(k["Remote Contr"] == ["claude auth status|remote-control"], "key: 導けない行は overlay から")
        check(k["calendar.sh "] == ["calendar\\.sh", "calendar\\-events\\.py"], "key: `.sh` / `.py` の 2 つ")
        hits = match_rows(rows, "python3 scripts/drive-xlsx-set-cells.py --inspect x.xlsx")
        check([r["head"][:5] for r in hits] == ["drive"], "match: Bash command に script 名")
        hits = match_rows(rows, "repo/todo/2026-10-01-foo.yaml")
        check(len(hits) == 1 and hits[0]["head"].startswith("todo_ledger"), "match: Edit の path に todo/<id>.yaml")
        check(match_rows(rows, "claude auth status") and not match_rows(rows, "git status"), "match: overlay の regex、 無関係な command は 0")
        # hook: 新しい process で stdin JSON → additionalContext JSON、 2 回目は無言 (state)
        st = tmp / "state"
        ev = {"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "Bash",
              "tool_input": {"command": "python3 scripts/drive-xlsx-set-cells.py --inspect x.xlsx"}}

        def run(e, *extra):
            return subprocess.run([sys.executable, __file__, "--table", str(tbl), "--state-dir", str(st), *extra],
                                  input=json.dumps(e), capture_output=True, text=True)

        r = run(ev)
        check(r.returncode == 0 and '"additionalContext"' in r.stdout and "他人の file は OK 経由" in r.stdout
              and "PreToolUse" in r.stdout, "hook: 初回は additionalContext に行を出す")
        r = run(ev)
        check(r.returncode == 0 and r.stdout.strip() == "", "hook: 同じ session の 2 回目は無言")
        r = run(dict(ev, session_id="s2"))
        check('"additionalContext"' in r.stdout, "hook: 別の session では再び出る")
        r = run({"hook_event_name": "PreToolUse", "session_id": "s3", "tool_name": "Edit",
                 "tool_input": {"file_path": "repo/todo/2026-10-01-foo.yaml"}})
        check("loader 経由で読む" in r.stdout, "hook: Edit の file_path でも出る")
        r = run({"hook_event_name": "PreToolUse", "session_id": "s4", "tool_name": "Bash",
                 "tool_input": {"command": "python3 constraint-at-use.py --table x.md --probe 'calendar.sh add'"}})
        check(r.stdout.strip() == "", "hook: engine 自身を叩く command (--probe 等) には出さない")
        r = run({"hook_event_name": "PreToolUse", "session_id": "s5", "tool_name": "Bash",
                 "tool_input": {"command": "python3 x/calendar.sh add && python3 drive-xlsx-set-cells.py && vi todo/a.yaml"}},
                "--max", "2")
        check(r.stdout.count("\n| ") + r.stdout.count("\\n| ") <= 2 and '"additionalContext"' in r.stdout, "hook: 1 回の call は --max 行まで")
        r = run({"hook_event_name": "PostToolUse", "session_id": "s6", "tool_name": "Bash",
                 "tool_input": {"command": "calendar.sh"}})
        check(r.stdout.strip() == "", "hook: PreToolUse 以外の event は無言")
        r = subprocess.run([sys.executable, __file__, "--table", str(tbl), "--state-dir", str(st)], input="not json",
                           capture_output=True, text=True)
        check(r.returncode == 0 and r.stdout.strip() == "", "hook: 壊れた stdin は fail-open (無言 exit 0)")
        r = subprocess.run([sys.executable, __file__, "--table", str(tmp / "missing.md"), "--state-dir", str(st)],
                           input=json.dumps(ev), capture_output=True, text=True)
        check(r.returncode == 0 and r.stdout.strip() == "", "hook: 表が無ければ fail-open")
        # --probe / --check
        r = subprocess.run([sys.executable, __file__, "--table", str(tbl), "--probe", "calendar.sh add"], capture_output=True, text=True)
        check(r.returncode == 0 and "calendar.sh" in r.stdout, "--probe: 出る行を表示")
        r = subprocess.run([sys.executable, __file__, "--table", str(tbl), "--check"], capture_output=True, text=True)
        check(r.returncode == 0 and "4 行" in r.stdout, "--check: 全行に key があれば rc 0")
        tbl.write_text(tbl.read_text(encoding="utf-8").replace("| Remote Control の auth |", "| 承認の CLI |"), encoding="utf-8")
        r = subprocess.run([sys.executable, __file__, "--table", str(tbl), "--check"], capture_output=True, text=True)
        check(r.returncode == 1 and "key の無い行 = 1" in r.stdout, "--check: key の無い行があれば rc 1 + 行を列挙")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("selftest:", "ALL PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if args == ["--selftest"]:
        return selftest()
    tables, state_dir, max_rows, probe, tool, check = [], DEFAULT_STATE_DIR, 2, None, "Bash", False
    it = iter(args)
    for tok in it:
        if tok == "--table":
            tables.append(Path(next(it, "")))
        elif tok == "--state-dir":
            state_dir = next(it, state_dir)
        elif tok == "--max":
            max_rows = int(next(it, "2"))
        elif tok == "--probe":
            probe = next(it, "")
        elif tok == "--tool":
            tool = next(it, "Bash")
        elif tok == "--check":
            check = True
        else:
            print(__doc__.split("usage:", 1)[-1])
            return 64
    if not tables:
        print("--table が要る")
        return 64
    if check:
        return check_main([t for t in tables if t.is_file()])
    if probe is not None:
        rows = []
        for t in tables:
            if t.is_file():
                rows.extend(load_table(t))
        hits = match_rows(rows, probe)
        print(f"{len(hits)} 行が出る (tool = {tool}):")
        for r in hits:
            print("  " + r["head"][:70])
        return 0
    return hook_main(tables, state_dir, max_rows)


if __name__ == "__main__":
    sys.exit(main())
