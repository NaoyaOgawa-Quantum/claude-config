#!/usr/bin/env python3
"""currentdate-anchor.py — session start temporal anchor

正本: claude-config/hooks/currentdate-anchor.py
setup.sh が ~/.claude/hooks/ に symlink を作成 (Step 2 の Installing Claude
Code hooks、 *.sh + *.py glob)

対象: SessionStart hook のみ (= session 起動時 1 回 fire)

動作:
  - hook input (stdin JSON) を parse
  - hook_event_name = "SessionStart" の場合のみ currentDate + 曜日 を system
    reminder で inject
  - 他 event は silent (= fail-safe、 想定外配線への防御)

Why this exists (= 2026-05-19→20 RCA、 SessionStart のみ復活 2026-05-20):

  Claude は session 開始時の `# currentDate` context を持っているが、 user
  発話の「今日 / 明日」 等を会話の流れで暗黙に旧 frame で解釈する reflex
  failure を起こすことがある (= odakin-prefs/CLAUDE.md inline §16 trait
  family の時刻 domain への現れ)。

  初回試行 (3c0e6f6、 2026-05-20) では UserPromptSubmit + SessionStart の
  両 hook で機械的 enforcement layer を実装したが、 UserPromptSubmit が
  user prompt の度に user chat UI を汚染する problem で同日中に退役。

  user 判断 (= 2026-05-20 後刻): SessionStart hook **のみ**復活。 SessionStart
  は session 起動時 1 回のみ fire するため:
    - user UI 汚染 = 1 回 (= 状況確認 phase の期待情報、 汚染感低い)
    - 「狼少年」 効果なし
    - false positive 概念なし (= trigger 不問)

  SessionStart hook で救えないケース: multi-day session (= autocompact / 翌
  日に session 継続) の day change。 これは規律 §3 (= user 発話読時に
  currentDate を明示的再参照する reflex) で対処。

Behavior 詳細:
  - 出力 format: 簡潔な 2 行 (= 「Today is YYYY-MM-DD (曜日)」 + 補足の
    relative dates 「明日 = ... 昨日 = ...」)
  - fail-open: JSON parse 失敗 / 例外時は silent exit (= Claude を止めない)

依存: Python 3.6+ (= 標準ライブラリのみ、 jq 不要)
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta

# 曜日 (= date.weekday() 0=Mon)
_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def fmt_date(d: date) -> str:
    """YYYY-MM-DD (曜日) format。"""
    wd = _WEEKDAY_JA[d.weekday()]
    return f"{d.strftime('%Y-%m-%d')} ({wd})"


def main() -> int:
    # Hook input parse (= fail-open)
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0

    event = str(data.get("hook_event_name", ""))
    # SessionStart 以外は silent (= 想定外配線への fail-safe)
    if event != "SessionStart":
        return 0

    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    msg = f"""<system-reminder>
🕐 Today is **{fmt_date(today)}** — 明日={fmt_date(tomorrow)} / 昨日={fmt_date(yesterday)}

multi-day session で日付が進んだ場合、 reflex で旧 frame を使わず、 user 発話
の時刻 deictic 表現 (= 今日 / 明日 / 今夜 等) を上記 currentDate 起算で再翻訳。

[claude-config/conventions/time-context.md]
</system-reminder>"""

    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
