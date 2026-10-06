#!/usr/bin/env python3
"""guard-cli-form-guard.py — PreToolUse(Bash): 規則保護の guard の承認 CLI を、 宣言済みの allow に当たらない形 (繋いだ形・相対 path) で打つ command を止める (tool-call-robustness.md#classifier-blocks-guard-approval-cli)

なぜ:
  auto mode で guard の承認 CLI (agent-rule-guard.py / manuscript-claim-guard.py) を classifier の判定から外すには、
  settings の allow `Bash(python3 <engine の絶対 path> *)` に当たる形で打つ必要がある。 cd・変数の代入・&& ; | と
  繋いだ形や、 engine を相対 path で書いた形は allow に当たらず classifier に回り、 Self-Modification で止められる
  (実測: allow が入った機械で、 繋いだ形・相対 path の記録が止められ、 単独・絶対 path の形は classifier を通らずに通った)。
  classifier に止められた後に自分で形を直して打ち直すのは「形を変えて試す」 に当たり、 本人の承認が要る。
  ∴ classifier に届く前に、 この hook が形を直させる (hook の停止は classifier の判定より前に起きる)。

止めるもの (python の interpreter の直後に engine が来る呼び出し、 または engine の直接実行に限る):
  1. command に shell の制御演算子 (&& || ; | & 改行) がある (引用の中は見ない)
  2. 先頭の語が `python3` でない (変数の代入・cd・別の interpreter・直接実行)
  3. engine の path が正本の絶対 path (この hook がある repo の scripts/) と一致しない
通すもの:
  - engine を読むだけの command (grep / sed / cat …。 interpreter に渡していない)
  - engine に触れない command
  - 解析できない command (引用が閉じていない等) = fail-open

無効化: CLAUDE_GUARD_CLI_FORM_GUARD=0
試験: bash hooks/guard-cli-form-guard.test.sh
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

ENGINES = ("agent-rule-guard.py", "manuscript-claim-guard.py")
INTERPRETER_RE = re.compile(r"^python(\d+(\.\d+)?)?$")
CONTROL = {"&&", "||", ";", "|", "&", ";;", "|&", "\n"}
DOC = "claude-config/conventions/tool-call-robustness.md#classifier-blocks-guard-approval-cli"


def tokens(command: str) -> list[str] | None:
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace = " \t\r"
    try:
        return list(lex)
    except ValueError:
        return None


def is_control(tok: str) -> bool:
    return tok in CONTROL or (tok != "" and set(tok) <= set("&|;"))


def invoked_engine(toks: list[str]) -> str | None:
    """engine を実行している呼び出しなら、 その engine の名前を返す (読むだけなら None)。"""
    for i, tok in enumerate(toks):
        name = os.path.basename(tok)
        if name not in ENGINES:
            continue
        prev = toks[i - 1] if i > 0 else None
        if prev is None or is_control(prev):
            return name  # 直接実行
        if INTERPRETER_RE.match(os.path.basename(prev)):
            return name
    return None


def canonical_engine(name: str) -> str:
    repo = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(repo, "scripts", name)


def problems(toks: list[str], canonical: str) -> list[str]:
    out = []
    if any(is_control(t) for t in toks):
        out.append("他の command と繋いでいる (&& ; | や改行)")
    if not toks or toks[0] != "python3":
        out.append(f"先頭が `python3` でない (先頭 = `{toks[0] if toks else ''}`: 変数の代入・cd・別の interpreter・直接実行)")
    elif len(toks) < 2 or toks[1] != canonical:
        out.append(f"engine が正本の絶対 path でない (`{toks[1] if len(toks) > 1 else ''}`)")
    return out


def main() -> int:
    if os.environ.get("CLAUDE_GUARD_CLI_FORM_GUARD", "1") == "0":
        return 0
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    command = ((data or {}).get("tool_input") or {}).get("command") or ""
    if not any(e in command for e in ENGINES):
        return 0
    toks = tokens(command)
    if not toks:
        return 0
    name = invoked_engine(toks)
    if name is None:
        return 0
    canonical = canonical_engine(name)
    found = problems(toks, canonical)
    if not found:
        return 0
    lines = [
        "[guard-cli-form-guard] 規則保護の guard の承認 CLI は、 単独の 1 command・絶対 path で打つ:",
        f"  python3 {canonical} <引数…>",
        "  (cd・変数の代入・&& ; | と繋がない。 --file / --candidate も絶対 path で書く)",
        "この command の形:",
        *[f"  - {p}" for p in found],
        "繋いだ形・相対 path は宣言済みの allow に当たらず classifier に回り、 Self-Modification で止められる。",
        "この停止は classifier の判定より前なので、 上の形に直して打ち直す。",
        f"正本 = {DOC}",
    ]
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
