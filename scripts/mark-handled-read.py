#!/usr/bin/env python3
"""mark-handled-read.py — 見張っている Gmail ラベルの未読のうち、 「対応済み」 と記録で言えるものだけを既読にする engine。

対応済み = 次のどちらか。 どちらでもない未読は触らず、 仕分けの対象として一覧に出す:
  (a) messageId か threadId が記録の台帳に在る (harvester = lib/recorded_ids.py = 他の網と同じ関数)
  (b) 「見て対応不要と決めた」 ack の台帳 (YAML、 `ack: [{id, reason}]`) に在る。 reason は「YYYY-MM-DD 理由」 の形だけが効く
      (= 見て決めた記録。 理由の無い行は無視)

外すのは UNREAD だけ (ほかのラベル・削除・移動はしない)。 既定は dry-run、 書くのは --apply。
一般則 = conventions/email-surface-pattern.md#record-bound-mark-read。 個人の構成 (ラベル・台帳の場所) は呼び出し側が渡す。

使い方:
  mark-handled-read.py --label lab:SomeLabel [--label ...] --ledger-glob '~/repo/inbox/*.yaml' [...] \
      [--ack ack.yaml] [--gmail-dir ~/.gmail-mcp] [--apply | --ack-snippet]
  mark-handled-read.py --selftest

  --label ACCOUNT:NAME   見るラベル (account = gmail_read.service_for の alias)。 repeat 可
  --ledger-glob G        記録の台帳 (YAML) の glob。 repeat 可。 ~ を展開する
  --ack FILE             ack の台帳 (無ければ (b) は空)
  --ack-snippet          未対応の thread を ack に足す形で出す (件名を見て判断してから reason を書く = 見ずに貼らない)

設計 (実測から):
  - 未読を鍵にした見張りの段は、 記録を付けても UNREAD が残るので対応済みの mail で膨らみ、 本物が埋もれる。
  - auto mode では、 その場で書いた一括の既読化は外部への書き込みとして止められる → 判定を記録に束縛した狭い道具にし、
    道具の path だけを allow に宣言する。
  - ack の台帳は「既読にしてよい」 の許可そのもの。 止められた操作を通すために agent が自分で ack を書くと
    自己承認として止められる → ack を書くのは本人の OK の後。
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REASON_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \S")


def acked_ids(text: str | None) -> set[str]:
    """ack の台帳 text から、 reason が「YYYY-MM-DD 理由」 の形の id だけを返す。"""
    import yaml
    if not text:
        return set()
    data = yaml.safe_load(text) or {}
    out = set()
    for row in data.get("ack", []) or []:
        if not isinstance(row, dict):
            continue
        rid, reason = str(row.get("id", "")).strip(), str(row.get("reason", "")).strip()
        if rid and REASON_RE.match(reason):
            out.add(rid)
    return out


def handled(msg: dict, known: set[str]) -> bool:
    return msg.get("id") in known or msg.get("threadId") in known


def recorded_ids(ledger_globs: list[str]) -> set[str]:
    sys.path.insert(0, str(HERE / "lib"))
    import recorded_ids as ri
    paths: list[str] = []
    for g in ledger_globs:
        paths += glob.glob(os.path.expanduser(g))
    ids = set(ri.harvest_yaml_files(paths))
    text = "".join(Path(p).read_text(encoding="utf-8", errors="ignore") for p in paths)
    return ids | ri.harvest_thread_ids(text)


def parse_labels(items: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for it in items:
        acct, sep, name = it.partition(":")
        if not sep or not acct or not name:
            raise SystemExit(f"--label は ACCOUNT:NAME の形: {it!r}")
        out.setdefault(acct, []).append(name)
    return out


def selftest() -> int:
    known = {"aaa", "ttt"}
    assert handled({"id": "aaa", "threadId": "x"}, known)
    assert handled({"id": "b", "threadId": "ttt"}, known)
    assert not handled({"id": "b", "threadId": "y"}, known)
    txt = "ack:\n  - id: \"t1\"\n    reason: \"2030-01-01 見た\"\n  - id: \"t2\"\n    reason: \"理由なし\"\n  - id: \"t3\"\n  - \"bare\"\n"
    assert acked_ids(txt) == {"t1"}, acked_ids(txt)
    assert acked_ids("") == set()
    assert parse_labels(["a:X", "a:Y Z", "b:W"]) == {"a": ["X", "Y Z"], "b": ["W"]}
    try:
        parse_labels(["nocolon"])
        raise AssertionError("ACCOUNT:NAME でない --label は止まる")
    except SystemExit:
        pass
    print("selftest ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--ledger-glob", action="append", default=[])
    ap.add_argument("--ack")
    ap.add_argument("--gmail-dir", default="~/.gmail-mcp")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ack-snippet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    labels = parse_labels(a.label)
    if not labels or not a.ledger_glob:
        raise SystemExit("--label と --ledger-glob が要る (個人の構成は呼び出し側が渡す)")
    sys.path.insert(0, str(HERE / "lib"))
    import gmail_read as gr

    ack_text = Path(os.path.expanduser(a.ack)).read_text(encoding="utf-8") if a.ack and Path(os.path.expanduser(a.ack)).is_file() else None
    known = recorded_ids(a.ledger_glob) | acked_ids(ack_text)
    total = 0
    snippet: list[str] = []
    for acct, names in labels.items():
        svc = gr.service_for(Path(os.path.expanduser(a.gmail_dir)), acct, label="mark-handled-read")
        if svc is None:
            print(f"⚪ {acct}: 認証が無い = 未チェック")
            continue
        lab_ids = {x["name"]: x["id"] for x in svc.users().labels().list(userId="me").execute().get("labels", [])}
        for name in names:
            lid = lab_ids.get(name)
            if not lid:
                print(f"⚪ {acct} / {name}: ラベルが無い")
                continue
            msgs, tok = [], None
            while True:
                r = svc.users().messages().list(userId="me", labelIds=[lid, "UNREAD"], maxResults=100, pageToken=tok).execute()
                msgs += r.get("messages", []) or []
                tok = r.get("nextPageToken")
                if not tok:
                    break
            done = [m for m in msgs if handled(m, known)]
            rest = [m for m in msgs if not handled(m, known)]
            print(f"== {acct} / {name}: 未読 {len(msgs)} = 対応済み {len(done)} + 未対応 {len(rest)}")
            seen: set[str] = set()
            for m in rest:
                md = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                metadataHeaders=["From", "Subject", "Date"]).execute()
                h = {x["name"]: x["value"] for x in md["payload"]["headers"]}
                print(f"   ? thr={m['threadId']} {h.get('Date', '')[:16]} | {h.get('From', '')[:26]} | {h.get('Subject', '')[:64]}")
                if m["threadId"] not in seen:
                    seen.add(m["threadId"])
                    subj = h.get("Subject", "").replace('"', "'")[:60]
                    snippet.append(f"  - id: \"{m['threadId']}\"   # {acct} / {name} / {subj}\n    reason: \"YYYY-MM-DD <見て決めた理由>\"")
            if a.apply and done:
                ids = [m["id"] for m in done]
                for i in range(0, len(ids), 500):
                    svc.users().messages().batchModify(userId="me", body={"ids": ids[i:i + 500], "removeLabelIds": ["UNREAD"]}).execute()
                total += len(ids)
                print(f"   ✓ 対応済み {len(ids)} 件を既読にした")
    if a.ack_snippet and snippet:
        print("\n# --- ack の台帳に足す候補 (件名を見て判断してから reason を書く) ---")
        print("\n".join(snippet))
    print(f"\n合計 {total} 件を既読にした" if a.apply else "\n(dry-run。 既読にするなら --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
