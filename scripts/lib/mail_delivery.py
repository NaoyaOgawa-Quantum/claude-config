#!/usr/bin/env python3
"""mail_delivery.py — Gmail で送ったメールが「届かなかった」 ことを、 送る前と送った直後に機械で拾う部品。

- 送る前: Gmail はメール全体 (MIME を encode した後) が 25 MB を超えると配達しない。 それでも API の
  messages.send は messageId を返し、 送信済みにも残る = 送った側からは成功に見える。 ∴ 送る前に大きさを測る
  (`oversize`)。
- 送った直後: 配達できなかったとき Gmail は同じ thread に mailer-daemon の通知を入れる (理由が書かれないことが
  ある)。 送った後に少し待って thread を読み直し、 その通知があれば失敗として扱う (`bounces`)。
  上限超えだけでなく、 宛先の誤り・受け手の拒否も同じ形で返る。

送信 CLI は両方を呼ぶ: 大きさは dry-run でも止め、 配達の確認は送った後に 1 回 (待ち時間 = `wait_sec`)。
MIME を自分で組まない経路 (MCP server が組んで送る send など) は、 添付の file の大きさから
`estimate_encoded_bytes` で見積もって `oversize` に渡す。
規約 = conventions/gmail-sending.md#oversize-silent-failure

    python3 mail_delivery.py --selftest
"""
from __future__ import annotations

import os
import re
import sys

GMAIL_MAX_BYTES = 25 * 1024 * 1024   # Gmail の送信の上限 (encode 後のメール全体)
DEFAULT_WAIT_SEC = 8                 # 送った後に thread を読み直すまでの待ち (実測: 通知は同じ分に届く)
WAIT_ENV = "CLAUDE_MAIL_DELIVERY_WAIT"  # 待ちの秒数を上書きする env (0 = 確認しない)
BOUNCE_FROM_RE = re.compile(r"mailer-daemon@|postmaster@", re.I)
B64_LINE = 76                        # MIME の base64 の 1 行の文字数 (この後に CRLF)
PART_OVERHEAD = 1024                 # 添付 1 つあたりの part の header と boundary の余裕
HEADER_MARGIN = 16 * 1024            # メール全体の header・宛先・multipart の枠の余裕


def oversize(nbytes: int, limit: int = GMAIL_MAX_BYTES) -> str | None:
    """上限を超えていれば理由の 1 文、 超えていなければ None。 nbytes = encode 後のメール全体 (msg.as_bytes())。"""
    if nbytes <= limit:
        return None
    return (f"メールの大きさ {nbytes / 1048576:.1f} MB が Gmail の上限 {limit / 1048576:.0f} MB を超える。 "
            "添付を小さくする (例: raster の PDF は 300 dpi・圧縮で作る)")


def _b64_wrapped(n: int) -> int:
    enc = 4 * ((n + 2) // 3)
    return enc + 2 * ((enc + B64_LINE - 1) // B64_LINE)


def estimate_encoded_bytes(attachment_sizes, text_bytes: int = 0) -> int:
    """MIME を組む前に、 encode 後のメール全体の大きさを見積もる (過大側に寄せる)。

    attachment_sizes = 添付 file の byte 数の並び、 text_bytes = 本文 (text と html の合計、 UTF-8) の byte 数。
    添付は base64 (76 文字ごとに CRLF)、 本文は quoted-printable の最悪 (1 byte → 3 文字 + 行末の soft break) で数え、
    header と枠の余裕を足す。 実際に組める経路は `len(msg.as_bytes())` を測る方が正確。"""
    total = HEADER_MARGIN
    for n in attachment_sizes:
        total += _b64_wrapped(int(n)) + PART_OVERHEAD
    qp = 3 * int(text_bytes)
    total += qp + 3 * ((qp + 72) // 73)
    return total


def wait_sec() -> float:
    """送った後に thread を読み直すまでの秒数。 env CLAUDE_MAIL_DELIVERY_WAIT (0 = 確認しない)、 無ければ DEFAULT_WAIT_SEC。"""
    v = os.environ.get(WAIT_ENV)
    if v is not None:
        try:
            return max(0.0, float(v))
        except ValueError:
            pass
    return float(DEFAULT_WAIT_SEC)


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
    check("見積もり: 添付 18 MB は上限以下", oversize(estimate_encoded_bytes([18 * 1048576], 4000)) is None)
    check("見積もり: 添付 19 MB は base64 で上限を超える", oversize(estimate_encoded_bytes([19 * 1048576])) is not None)
    check("見積もり: 添付の合計で数える",
          oversize(estimate_encoded_bytes([10 * 1048576, 10 * 1048576])) is not None)
    check("見積もり: base64 の 4/3 + 改行より小さくならない",
          estimate_encoded_bytes([3_000_000]) >= 4_000_000 * 78 // 76)
    saved = os.environ.get(WAIT_ENV)
    os.environ[WAIT_ENV] = "0"
    check("wait_sec: env 0 は確認しない", wait_sec() == 0.0)
    os.environ[WAIT_ENV] = "x"
    check("wait_sec: 読めない値は既定", wait_sec() == float(DEFAULT_WAIT_SEC))
    if saved is None:
        os.environ.pop(WAIT_ENV, None)
    else:
        os.environ[WAIT_ENV] = saved

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
