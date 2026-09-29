#!/usr/bin/env python3
"""git-rewrite-follow.py — 書き換えられた (force-push された) 履歴に手元の clone を中身で揃える / 古い世代の commit・blob の push を止める / 揃える機構が各マシンに届いたかを状態で答える (engine = scripts/lib/git_rewrite_follow.py、 追従の判定は書き換えられない層 = 本 repo に置く)

書き換えた repo の追従を、 書き換えられる repo の中の script に頼らないための入口 (実測 2026-09-29: 追従 script が
書き換えられる側の repo に在り、 その repo 自身を書き換えると古い履歴の Mac は script を pull できない。 毎時の
無人 job は `pull --rebase` で古い commit を積み直しうる)。 判定・不変条件・manifest の形 = lib の docstring。

usage:
  git-rewrite-follow.py follow --repo PATH [--no-fetch] [--map GLOB]... [--max N] [--dry-run] [--tsv]
      diverged な clone を、 対応表 / tree の一致 で新しい履歴に揃える (reset --keep)。 1 行で結果。
      exit 0 = 揃えた / 揃っている / 触らない (upstream 無し等)、 1 = 止まった (手元にしか無い中身、 dirty の重なり、 通信、
      書き換えの痕跡の無い通常の分岐 = 追従の対象外)。
      --tsv = repo-sync-sweep.sh 向け (F<TAB>行 = 揃えた / S<TAB>行 = 止まった / 無音 = 何もしない)
  git-rewrite-follow.py sweep --root DIR [--fetch] [--map GLOB]... [--max N] [--dry-run] [--no-prepush]
      DIR/*/ の repo を順に follow (既定は fetch しない = 直前の sync が fetch した ref を読む) + manifest のある repo に
      pre-push stub を置く。 exit 0 (何かで止まった repo があれば 1)。
  git-rewrite-follow.py guard --repo PATH --hook [remote url]      (git pre-push の stdin を読む。 stub が呼ぶ)
  git-rewrite-follow.py guard --repo PATH --range LOCAL..REMOTE     (手で確かめる)
      push 範囲に対応表の旧 sha か forbidden-blobs の blob が在れば exit 1 + 理由。
  git-rewrite-follow.py ensure-prepush (--repo PATH | --root DIR) [--force]
      manifest (`<upstream>:.rewrite-follow/`) のある repo に pre-push stub を置く (既存の別の pre-push は触らない)。
  git-rewrite-follow.py status --repo PATH [--json]
      upstream / manifest の有無 / stub の有無 / forced-update の痕跡 / HEAD と upstream の関係。 heartbeat と gate が読む。
  git-rewrite-follow.py --selftest

対応表の外部供給: --map GLOB (repeatable) / ~/.claude/rewrite-follow-maps.txt (1 行 1 glob、 env GIT_REWRITE_FOLLOW_MAPS_FILE で
場所を変える) / env GIT_REWRITE_FOLLOW_MAPS (`:` 区切り glob)。 `<map>.forbidden-blobs` が隣に在れば guard が読む。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import git_rewrite_follow as RF  # noqa: E402


def _print_result(r, tsv):
    if r.state == "followed":
        if tsv:
            print("F\t" + r.line)
            for x in r.extra:
                print("F\t" + x.strip())
        else:
            print(r.line)
            for x in r.extra:
                print(x)
    elif r.state == "stopped":
        if tsv:
            print("S\t" + r.line)
        else:
            print(r.line, file=sys.stderr)
    elif r.state == "diverged" and not tsv:   # 通常の分岐 = tsv (sweep) では無音 → 呼び元が従来の A 行を出す
        print(r.line, file=sys.stderr)


def cmd_follow(a):
    try:
        r = RF.follow_repo(a.repo, a.map, fetch=not a.no_fetch, max_count=a.max, dry_run=a.dry_run)
    except Exception as exc:  # 判定の失敗は 1 行で止まる (呼び元は次回再試行)
        r = RF.Result("stopped", f"{Path(a.repo).name}: 追従の判定で失敗 ({type(exc).__name__}: {str(exc)[:160]})", exit_code=1)
    _print_result(r, a.tsv)
    return r.exit_code


def cmd_sweep(a):
    rc = 0
    for r, pl in RF.sweep(a.root, a.map, fetch=a.fetch, max_count=a.max, dry_run=a.dry_run, prepush=not a.no_prepush):
        _print_result(r, a.tsv)
        if pl:
            print(("P\t" if a.tsv else "") + pl)
        rc = max(rc, r.exit_code)
    return rc


def cmd_guard(a):
    if a.range:
        local, _, remote = a.range.partition("..")
        lines = [f"refs/heads/x {RF.rev(a.repo, local)} refs/heads/x {RF.rev(a.repo, remote) if remote else RF.ZERO}"]
    else:
        lines = sys.stdin.read().splitlines()
    try:
        ok, msgs = RF.guard_stdin(a.repo, lines, a.map)
    except Exception as exc:  # 検査の失敗は通す (fail-open) が、 通したことは言う
        print(f"rewrite-follow guard: 検査できなかったので通す ({type(exc).__name__}: {str(exc)[:120]})", file=sys.stderr)
        return 0
    for m in msgs:
        print(m, file=sys.stderr)
    return 0 if ok else 1


def cmd_ensure_prepush(a):
    repos = [a.repo] if a.repo else sorted(str(Path(g).parent) for g in Path(a.root).glob("*/.git"))
    for r in repos:
        try:
            line = RF.ensure_prepush(r, only_with_manifest=not a.force)
        except Exception as exc:
            line = f"{Path(r).name}: pre-push stub を置けなかった ({type(exc).__name__}: {str(exc)[:120]})"
        if line:
            print(line)
    return 0


def cmd_status(a):
    st = RF.status(a.repo, a.map)
    if a.json:
        print(json.dumps(st, ensure_ascii=False, indent=1))
    else:
        for k, v in st.items():
            print(f"{k}: {v}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--map", action="append", default=[], metavar="GLOB", help="対応表 (old new) の glob、 repeatable")

    p = sub.add_parser("follow")
    p.add_argument("--repo", required=True)
    p.add_argument("--no-fetch", action="store_true")
    p.add_argument("--max", type=int, default=RF.DEFAULT_MAX)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--tsv", action="store_true")
    common(p)
    p = sub.add_parser("sweep")
    p.add_argument("--root", default=os.path.join(os.path.expanduser("~"), "Claude"))
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--max", type=int, default=RF.DEFAULT_MAX)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-prepush", action="store_true")
    p.add_argument("--tsv", action="store_true")
    common(p)
    p = sub.add_parser("guard")
    p.add_argument("--repo", required=True)
    p.add_argument("--hook", action="store_true", help="git pre-push として stdin を読む")
    p.add_argument("--range", help="LOCAL..REMOTE (手で確かめる)")
    p.add_argument("rest", nargs="*", help="(pre-push が渡す remote 名と URL、 使わない)")
    common(p)
    p = sub.add_parser("ensure-prepush")
    p.add_argument("--repo")
    p.add_argument("--root")
    p.add_argument("--force", action="store_true", help="manifest が無くても置く")
    p = sub.add_parser("status")
    p.add_argument("--repo", required=True)
    p.add_argument("--json", action="store_true")
    common(p)
    a = ap.parse_args(argv)
    if a.selftest:
        return RF._selftest()
    if a.cmd == "follow":
        return cmd_follow(a)
    if a.cmd == "sweep":
        return cmd_sweep(a)
    if a.cmd == "guard":
        return cmd_guard(a)
    if a.cmd == "ensure-prepush":
        if not (a.repo or a.root):
            ap.error("ensure-prepush needs --repo or --root")
        return cmd_ensure_prepush(a)
    if a.cmd == "status":
        return cmd_status(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
