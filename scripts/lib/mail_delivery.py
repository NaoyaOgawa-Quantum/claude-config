#!/usr/bin/env python3
"""mail_delivery.py — Gmail で送ったメールが「届かなかった」 ことを、 送る前と送った直後に機械で拾う部品。

- 送る前: Gmail はメール全体 (MIME を encode した後) が 25 MB を超えると配達しない。 それでも API の
  messages.send は messageId を返し、 送信済みにも残る = 送った側からは成功に見える。 ∴ 送る前に大きさを測る
  (`oversize`)。
- 送った直後: 配達できなかったとき Gmail は同じ thread に mailer-daemon の通知を入れる (理由が書かれないことが
  ある)。 送った後に少し待って thread を読み直し、 その通知があれば失敗として扱う (`bounces`)。
  上限超えだけでなく、 宛先の誤り・受け手の拒否も同じ形で返る。

送信 CLI は両方を呼ぶ: 大きさは dry-run でも止め、 配達の確認は送った後に 1 回 (待ち時間 = DEFAULT_WAIT_SEC)。
規約 = conventions/gmail-sending.md#oversize-silent-failure

    python3 mail_delivery.py --selftest
"""
from __future__ import annotations

import re
import sys

GMAIL_MAX_BYTES = 25 * 1024 * 1024   # Gmail の送信の上限 (encode 後のメール全体)
DEFAULT_WAIT_SEC = 8                 # 送った後に thread を読み直すまでの待ち (実測: 通知は同じ分に届く)
BOUNCE_FROM_RE = re.compile(r"mailer-daemon@|postmaster@", re.I)


def oversize(nbytes: int, limit: int = GMAIL_MAX_BYTES) -> str | None:
    """上限を超えていれば理由の 1 文、 超えていなければ None。 nbytes = encode 後のメール全体 (msg.as_bytes())。"""
    if nbytes <= limit:
        return None
    return (f"メールの大きさ {nbytes / 1048576:.1f} MB が Gmail の上限 {limit / 1048576:.0f} MB を超える。 "
            "添付を小さくする (例: raster の PDF は 300 dpi・圧縮で作る)")


def _header(msg: dict, name: str) -> str:
    for h in (msg.get("payload") or {}).get("headers") or []:
        if (h.get("name") or "").lower() == name.lower():
            return h.get("value") or ""
    return ""


def bounces(thread: dict, since_ms: int) -> list[dict]:
    """thread (users.threads.get の JSON、 From の header つき) から、 since_ms 以降の配達失敗の通知を返す。

    戻り値 = [{"id", "internalDate", "from", "snippet"}]。 since_ms = 送ったメールの internalDate (ms)。"""
    out = []
    for m in thread.get("messages") or []:
        try:
            t = int(m.get("internalDate") or 0)
        except (TypeError, ValueError):
            t = 0
        frm = _header(m, "From")
        if t >= since_ms and BOUNCE_FROM_RE.search(frm):
            out.append({"id": m.get("id"), "internalDate": t, "from": frm,
                        "snippet": (m.get("snippet") or "")[:160]})
    return out


def _selftest() -> int:
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  {'✅' if cond else '❌'} {label}")
        ok = ok and bool(cond)

    check("上限以下は None", oversize(GMAIL_MAX_BYTES) is None)
    check("上限超えは理由を返す", "上限" in (oversize(GMAIL_MAX_BYTES + 1) or ""))

    def msg(mid, t, frm):
        return {"id": mid, "internalDate": str(t), "snippet": "x",
                "payload": {"headers": [{"name": "From", "value": frm}]}}

    th = {"messages": [msg("a", 1000, "Office <office@example.org>"),
                       msg("b", 2000, "Me <me@example.org>"),
                       msg("c", 2001, "Mail Delivery Subsystem <mailer-daemon@example.net>"),
                       msg("d", 500, "Mail Delivery Subsystem <mailer-daemon@example.net>")]}
    got = bounces(th, 2000)
    check("送った後の mailer-daemon だけを拾う", [b["id"] for b in got] == ["c"])
    check("送る前の通知は拾わない", all(b["id"] != "d" for b in got))
    check("postmaster も拾う", bounces({"messages": [msg("e", 3000, "postmaster@example.net")]}, 0)[0]["id"] == "e")
    check("通知が無ければ空", bounces({"messages": [msg("f", 3000, "a@example.org")]}, 0) == [])
    print(f"mail_delivery selftest: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(_selftest())
    print(__doc__)
