"""Shared report contract text for vendor-specific delegation adapters.

# agent-authority:file

The common semantic requirement is multi-session-coordination.md#worker-record-clause.
This module contains no tool policy or vendor configuration.
"""
MARKER = "記録の約束"
CLAUSE = (
    "\n\n## " + MARKER + " (委ねた側が自動で足した段 / appended by the delegating side)\n"
    "あなたの「考え中」 の中身は会話記録に残らず、 後から誰も引けない。 作業の最後に、 次を報告 (返す本文) か成果物の file に"
    "書く (file に書いたら報告にその path を書く。 該当が無ければ「なし」 と 1 行):\n"
    "1. 捨てた案とその理由\n"
    "2. 途中で気づいたこと (壊れ方・想定外・周辺の問題)\n"
    "3. 確かめていないこと・推定のままのこと\n"
    "(Your thinking is not recorded. In your final report or a deliverable file, list: discarded options and why, "
    "things you noticed along the way, and what remains unverified.)"
)
