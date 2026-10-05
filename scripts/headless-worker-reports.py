#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""headless-worker-reports.py — ある session が Bash から headless で起動した worker (`claude -p` / `codex exec`) を会話記録から数え上げ、 worker の作業 dir に残った成果物 (HANDOFF・結果・教訓候補・script) を読み出す。--selftest 内蔵。

用途: Agent tool の subagent は subagent-reports.py、 掲示板と token の子は各々の道具で引けるが、
Bash から直接起動した headless の worker (封じた sandbox の盲検 reviewer など) はどの口にも現れない。
worker の報告は端末の log と作業 dir にしか残らず、 起動した側が拾わないと session の終わりに消える。
締めの整理 (知見を正本へ移す) で取りこぼさないために、 起動の事実を記録から機械で引く。

出すもの (起動ごと):
  - 起動時刻、 作業 dir (command の `cd <dir>`、 無ければ記録の cwd)、 model / effort、 config dir
  - 記録の約束の根拠: 起動文の約束の段 (MARKER)、 自動注入 runner の指定、 作業 dir の HANDOFF 要件を区別する。
    根拠が無ければ「受領を確認できない」 と ⚠️。 hook の updatedInput が元の tool 記録に反映されるか、
    起動先で注入が成功したかはこの記録だけでは確定しない。 worker の報告・成果物で受領を確認する。
  - 作業 dir の成果物: HANDOFF.md / REVIEW-RESULTS.md / STAGE*-RESULTS.md / ledger.yaml / DONE /
    scratch/hoist-candidates.md と、 worker が書いた script (checks/・scratch/ の *.py) の一覧
  - HANDOFF.md と hoist-candidates.md の本文 (--max-chars、 0 = 全部)
  - worker 自身の会話記録の場所 (<config dir>/projects/<作業 dir の slug>/*.jsonl)

作業 dir が sandbox なら、 進み具合と受領検査は ai-collaboration scripts/inspect-review-sandbox.py。

usage:
  headless-worker-reports.py <session id の先頭> [--max-chars N] [--projects-dir DIR ...]
  headless-worker-reports.py --selftest
0 件のときは、 見た記録 file を出して終わる (= 使っていない、 と区別できる)。 標準 library だけ。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

LAUNCH_RE = re.compile(r"(?:^|[\s;&|(])(claude\b[^\n;&|]*?\s(?:-p|--print)\b|codex\s+exec\b)")
MARKER = "記録の約束"
TOP = ("HANDOFF.md", "REVIEW-RESULTS.md", "ledger.yaml", "DONE")
TEXTS = ("HANDOFF.md", "scratch/hoist-candidates.md")


def projects_dirs(explicit=None) -> list[Path]:
    if explicit:
        return [Path(p).expanduser() for p in explicit]
    out = []
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        out.append(Path(env).expanduser() / "projects")
    home = Path.home()
    out.append(home / ".claude" / "projects")
    out.extend(sorted(p / "projects" for p in home.glob(".claude-*") if p.is_dir()))
    return [p for p in dict.fromkeys(out) if p.is_dir()]


def session_files(dirs: list[Path], session: str) -> list[Path]:
    found = []
    for d in dirs:
        found.extend(sorted(d.glob(f"*/{session}*.jsonl")))
    return found


def expand(path: str) -> Path:
    path = path.strip("'\"").replace("$HOME", str(Path.home())).replace("${HOME}", str(Path.home()))
    return Path(path).expanduser()


def launches(transcript: Path) -> list[dict]:
    out = []
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"Bash"' not in line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            content = (obj.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict) or b.get("type") != "tool_use" or b.get("name") != "Bash":
                    continue
                cmd = str((b.get("input") or {}).get("command", ""))
                m = LAUNCH_RE.search(cmd)
                if not m:
                    continue
                cds = re.findall(r"(?:^|[\s;&|(])cd\s+((?:\"[^\"]+\"|'[^']+'|[^\s;&|]+))", cmd[:m.start() + 1])
                cwd = expand(cds[-1]) if cds else (Path(obj["cwd"]) if obj.get("cwd") else None)
                cfg = re.search(r"CLAUDE_CONFIG_DIR=(\S+)", cmd)
                model = re.search(r"--model[ =](\S+)", cmd)
                effort = re.search(r"--effort[ =](\S+)", cmd)
                out.append({
                    "ts": obj.get("timestamp"), "cwd": cwd, "kind": "codex" if "codex" in m.group(1) else "claude",
                    "config": expand(cfg.group(1)) if cfg else None,
                    "model": model.group(1) if model else None, "effort": effort.group(1) if effort else None,
                    "marker": MARKER in cmd,
                    "runner": bool(re.search(r"headless-record-clause-nudge\.py['\"]?\s+--run\b", cmd)),
                })
    return out


def promise(launch: dict) -> str:
    if launch["marker"]:
        return "起動文に約束の段あり"
    if launch.get("runner"):
        return "起動文に自動注入 runner の指定あり (受領は worker の報告・成果物で確認)"
    cwd = launch["cwd"]
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = cwd / name if cwd else None
        if p and p.is_file() and "HANDOFF" in p.read_text(encoding="utf-8", errors="replace"):
            return f"作業 dir の {name} が HANDOFF を求めている"
    return "⚠️ 記録から約束の受領を確認できない (hook の有効性・起動形式と、worker の報告・成果物を確認する)"


def worker_transcripts(launch: dict) -> list[Path]:
    cwd = launch["cwd"]
    if not cwd:
        return []
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    roots = [launch["config"] / "projects"] if launch["config"] else projects_dirs()
    found = []
    for r in roots:
        d = r / slug
        if d.is_dir():
            found.extend(sorted(d.glob("*.jsonl")))
    return found


def report(launch: dict, n: int, max_chars: int) -> None:
    cwd = launch["cwd"]
    print(f"== 起動 {n}: {launch['ts']}  {launch['kind']}  model={launch['model'] or '既定'}  effort={launch['effort'] or '既定'}")
    print(f"   作業 dir: {cwd if cwd else '不明 (command に cd が無く、 記録に cwd も無い)'}")
    print(f"   記録の約束: {promise(launch)}")
    if not cwd or not cwd.is_dir():
        print("   作業 dir が今は無い")
        return
    have = [n_ for n_ in TOP if (cwd / n_).exists()] + [p.name for p in sorted(cwd.glob("STAGE*-RESULTS.md"))]
    if (cwd / "scratch" / "hoist-candidates.md").exists():
        have.append("scratch/hoist-candidates.md")
    print("   成果物: " + (", ".join(have) or "なし"))
    scripts = [str(p.relative_to(cwd)) for sub in ("checks", "scratch") for p in sorted((cwd / sub).glob("*.py"))]
    print(f"   worker が書いた script ({len(scripts)}): " + (", ".join(scripts) or "なし"))
    ts = worker_transcripts(launch)
    print(f"   worker の会話記録 ({len(ts)}): " + (", ".join(str(t) for t in ts) or "見つからない"))
    for name in TEXTS:
        p = cwd / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            cut = text if max_chars == 0 else text[:max_chars]
            print(f"   ---- {name} ({len(text)} 字{'' if cut == text else f'、 先頭 {max_chars} 字'})")
            print(cut.rstrip())


def run(session: str, dirs: list[Path], max_chars: int) -> int:
    files = session_files(dirs, session)
    if not files:
        print(f"session {session} の記録が見つからない (見た dir: {', '.join(map(str, dirs))})")
        return 1
    all_l = []
    for f in files:
        all_l.extend(launches(f))
    seen, uniq = set(), []
    for l in all_l:                                     # 同じ dir への再起動は別の起動として残す (時刻で区別)
        key = (str(l["cwd"]), l["ts"])
        if key not in seen:
            seen.add(key)
            uniq.append(l)
    print(f"見た記録: {', '.join(str(f) for f in files)}")
    print(f"headless の起動: {len(uniq)} 件 (session {session})")
    for i, l in enumerate(uniq, 1):
        report(l, i, max_chars)
    return 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        box = tmp / "box"
        (box / "scratch").mkdir(parents=True)
        (box / "checks").mkdir()
        (box / "CLAUDE.md").write_text("rule 7: write HANDOFF.md\n")
        (box / "HANDOFF.md").write_text("# handoff\nlesson\n")
        (box / "scratch" / "hoist-candidates.md").write_text("cand\n")
        (box / "checks" / "a.py").write_text("print(1)\n")
        bare = tmp / "bare"
        bare.mkdir()
        proj = tmp / "cfg" / "projects" / "p"
        proj.mkdir(parents=True)

        def bash(ts, cmd, cwd=None):
            o = {"type": "assistant", "timestamp": ts, "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}
            if cwd:
                o["cwd"] = cwd
            return json.dumps(o, ensure_ascii=False) + "\n"

        (proj / "abcd1234-x.jsonl").write_text(
            bash("T1", f"cd {box} && CLAUDE_CONFIG_DIR={tmp}/wcfg claude -p \"do it\" --model m1 --effort high < /dev/null > run.log")
            + bash("T2", "ls -la && echo claude -pretend")
            + bash("T3", "claude --print 'x'", cwd=str(bare))
            + bash("T4", f"cd '{bare}' ; codex exec \"y {MARKER}\"")
            + bash("T5", "git commit -m 'mention claude -p in text'")
            + bash("T6", "python3 '/opt/sample/headless-record-clause-nudge.py' --run claude -p task", cwd=str(bare)))
        ls = launches(proj / "abcd1234-x.jsonl")
        assert [l["ts"] for l in ls] == ["T1", "T3", "T4", "T5", "T6"], [l["ts"] for l in ls]   # T5: 文中の言及も拾う (過剰側に倒す)
        assert ls[0]["cwd"] == box and ls[0]["model"] == "m1" and ls[0]["effort"] == "high" and ls[0]["config"] == tmp / "wcfg"
        assert ls[1]["cwd"] == bare and ls[2]["kind"] == "codex" and ls[2]["marker"]
        assert "HANDOFF を求めている" in promise(ls[0]) and promise(ls[1]).startswith("⚠️") and "約束の段あり" in promise(ls[2])
        assert "受領を確認できない" in promise(ls[1]) and "渡っていない" not in promise(ls[1])
        assert "自動注入 runner" in promise(ls[4]) and "受領は worker" in promise(ls[4])
        wslug = re.sub(r"[^A-Za-z0-9]", "-", str(box))
        (tmp / "wcfg" / "projects" / wslug).mkdir(parents=True)
        (tmp / "wcfg" / "projects" / wslug / "w.jsonl").write_text("{}\n")
        assert len(worker_transcripts(ls[0])) == 1
        assert run("abcd1234", [tmp / "cfg" / "projects"], 0) == 0
        assert run("zzzz", [tmp / "cfg" / "projects"], 0) == 1
    print("selftest OK")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session")
    ap.add_argument("--max-chars", type=int, default=2000)
    ap.add_argument("--projects-dir", action="append")
    a = ap.parse_args(argv)
    return run(a.session, projects_dirs(a.projects_dir), a.max_chars)


if __name__ == "__main__":
    sys.exit(main())
