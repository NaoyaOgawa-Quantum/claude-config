#!/usr/bin/env python3
"""currentdate-anchor.py — temporal frame anchor for Claude

正本: claude-config/hooks/currentdate-anchor.py
setup.sh が ~/.claude/hooks/ に symlink を作成 (Step 2 の Installing Claude
Code hooks、 *.sh + *.py glob)

対象: UserPromptSubmit (user prompt に時刻 deictic 表現が含まれる場合) +
      SessionStart (無条件)

動作:
  - hook input (stdin JSON) を parse
  - UserPromptSubmit: `prompt` field に時刻 deictic 表現 (= 「今日 / 明日 /
    昨日 / 今夜 / 明朝 / 明後日 / 先日 / 翌日 / 今週 / 来週 / 先週 / today
    / tomorrow / yesterday / tonight / last week / next week / in N days /
    N days ago」 等) が含まれていたら currentDate anchor を inject
  - SessionStart: 無条件で currentDate を inject

Why this exists (= 2026-05-19→20 RCA):

  Claude (= 私) は session 開始時の `# currentDate` context を持っているが、
  multi-turn / multi-day session で user 発話の「明日 / 今日 / 今夜」 等を
  会話の流れで暗黙に旧 frame (= 「前ターンの仮想 today」) で解釈する reflex
  failure を起こす。

  具体的失敗事例 (= odakin 2026-05-19→20 session):
    - session 開始時 currentDate = 2026-05-20 (= 既に「明日」 を意図した日
      が今日)
    - user 発話 (5/19 夜の reflex で書いたつもり) 「今日はもう帰る、 明日
      メール書く」 を私は 5/19 frame で受け取り、 「明日 = 5/20」 「明日朝
      の draft 着手で十分」 等と発話
    - 真実は currentDate = 5/20 だったので「今日 = 5/20、 明日 = 5/21」、
      私の発言は時刻 frame が 1 日ずれていた
    - user 指摘「もうその明日や」 で発覚、 古川さん経緯説明メールの〆切は
      5/20 (= 今日) と判明

  この失敗は odakin-prefs/CLAUDE.md inline §16「context 構築での単一情報源
  null 結論飛躍」 の時刻 domain への現れ。 conv-tion (time-context.md) に
  wording で書いても reflex で skip される (= §15 axis 2 aspirational
  instruction risk)、 機械的 enforcement layer が必要。

Behavior 詳細:
  - 時刻 deictic 表現が prompt に含まれる場合のみ inject (= 無関係な prompt
    では silent、 dashboard / chat を散らかさない)
  - SessionStart は無条件 (= session 起点で常に anchor refresh、 multi-day
    session の day change を early notice)
  - inject format:
      🕐 Time anchor: Today is YYYY-MM-DD (曜日)
      • 今日 / today     → YYYY-MM-DD (曜日)
      • 明日 / tomorrow  → YYYY-MM-DD+1 (曜日)
      • 昨日 / yesterday → YYYY-MM-DD-1 (曜日)
      • 明後日           → YYYY-MM-DD+2 (曜日)
      ...
  - false positive 許容 (= 「明日香」 等の地名で hit しても害は「Claude が
    currentDate を 1 回多く見る」 だけ、 false negative = 時刻 frame ずれ の
    コストの方が高い)

依存: Python 3.6+ (= 標準ライブラリのみ、 jq 不要)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta

# 時刻 deictic 表現 (= 日本語 + 英語、 false positive 許容で広めに pattern 化)
TIME_DEICTIC_PATTERNS = [
    # 日本語: 単語単位 (= 「明日」 等)
    r"今日", r"今夜", r"今晩", r"明日", r"明朝", r"明晩", r"明後日",
    r"昨日", r"昨夜", r"一昨日", r"一昨夜",
    r"先日", r"翌日", r"翌朝", r"翌晩", r"翌週", r"翌月", r"翌年",
    r"今週", r"来週", r"先週", r"再来週",
    r"今月", r"来月", r"先月", r"再来月",
    r"今年", r"来年", r"去年", r"昨年", r"再来年",
    # 数値 + 単位 (= 「あと3日」 「5日後」 「2日前」 等)
    r"あと\s*\d+\s*[日週月年]",
    r"\d+\s*[日週月年]後",
    r"\d+\s*[日週月年]前",
    # 英語: \b で word boundary
    r"\btoday\b", r"\btonight\b", r"\btomorrow\b", r"\byesterday\b",
    r"\blast\s+(night|week|month|year)\b",
    r"\bnext\s+(week|month|year)\b",
    r"\bthis\s+(week|month|year)\b",
    r"\bin\s+\d+\s+(day|week|month|year)s?\b",
    r"\b\d+\s+(day|week|month|year)s?\s+ago\b",
]
_DEICTIC_RE = re.compile("|".join(TIME_DEICTIC_PATTERNS), re.IGNORECASE)

# 曜日 (= date.weekday() 0=Mon)
_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]
_WEEKDAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def fmt_date(d: date) -> str:
    """YYYY-MM-DD (曜日) format。"""
    wd = _WEEKDAY_JA[d.weekday()]
    return f"{d.strftime('%Y-%m-%d')} ({wd})"


def fmt_date_en(d: date) -> str:
    """YYYY-MM-DD (weekday) format、 英語曜日。"""
    return f"{d.strftime('%Y-%m-%d')} ({_WEEKDAY_EN[d.weekday()]})"


def main() -> int:
    # Hook input parse (= fail-open: parse 失敗時は silent exit、 Claude を止めない)
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
    prompt = str(data.get("prompt", "")) if event == "UserPromptSubmit" else ""

    # Event 別 trigger 判定
    if event == "UserPromptSubmit":
        # 時刻 deictic が含まれている場合のみ inject
        if not _DEICTIC_RE.search(prompt):
            return 0  # no deictic, silent
    elif event == "SessionStart":
        pass  # unconditional inject
    else:
        # 想定外 event は silent (= 別 event に hook 配線された場合の fail-safe)
        return 0

    # currentDate + relative dates
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    dayafter = today + timedelta(days=2)

    if event == "SessionStart":
        msg = f"""<system-reminder>
🕐 Session start: **Today is {fmt_date(today)}**.

session 内 multi-turn / multi-day で日付が進んだ場合、 reflex で旧 frame を
使わず、 常に currentDate を anchor として時刻表現を解釈すること。 次回
user prompt に「今日 / 明日 / 昨日」 等の時刻 deictic 表現が含まれた場合は
自動的に anchor reminder が再注入される (UserPromptSubmit hook)。

[claude-config/hooks/currentdate-anchor.py、 conventions/time-context.md]
</system-reminder>"""
    else:  # UserPromptSubmit + deictic hit
        msg = f"""<system-reminder>
🕐 Time anchor: **Today is {fmt_date(today)}** (currentDate).

User の発話に時刻 deictic 表現を検出。 以下の anchor で再翻訳すること:
  • 今日 / today        → {fmt_date(today)}
  • 明日 / tomorrow     → {fmt_date(tomorrow)}
  • 昨日 / yesterday    → {fmt_date(yesterday)}
  • 明後日              → {fmt_date(dayafter)}

reflex で「会話の流れから推測した frame」 を使わない (= 「前ターンの仮想
today」 「session 開始時の仮想 today」 で解釈しない)。 currentDate が真の
anchor、 user 発話の時刻表現は常にこの起算で再翻訳。

[claude-config/conventions/time-context.md 参照]
</system-reminder>"""

    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
