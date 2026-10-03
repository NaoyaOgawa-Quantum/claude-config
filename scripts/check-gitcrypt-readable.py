#!/usr/bin/env python3
"""check-gitcrypt-readable.py — 暗号化 file が「このマシンで実際に読めるか」 と「commit に入った版が暗号文か」 を必ず可視に報告する。

## なぜ要るか

git-crypt でロックされたマシンでは、暗号化 file を開くと **暗号文がそのまま読める**。
JSON/YAML として parse すれば当然失敗するが、 呼び出し側が fail-open で書かれていると
**黙って 0 件を返す**。 「予定が 1 件も無い」 と「読めていない」 が区別できなくなる —
守られていないのに守られているつもりになる、 という最悪の壊れ方をする。

なので、 暗号化を入れるなら必ずこの検査とセットにする。 沈黙という状態を作らず、
READABLE / LOCKED / SKIP の 3 状態のどれかを毎回 1 行出す。

## 判定

  .gitattributes の `filter=git-crypt` が付いた path を対象に、 working tree の
  先頭 9 byte が git-crypt の magic (\\x00GITCRYPT) かどうかを見る。

    鍵が無い (= CI 等)                       → SKIP (= 検査していないと申告して exit 0)
    鍵はあるのに暗号文のまま                 → LOCKED (exit 1。 unlock が要る)
    平文で読める                             → READABLE (exit 0)

  「鍵が無い」 を FAIL にしない理由: CI の runner は clone するだけで鍵を持たない。
  このリポの既存契約 (= 各 test が自分で SKIP を宣言して exit 0) に合わせる。

## 逆向きの穴: commit に入った版が平文

  上は「読めるはずが読めない」 を見る。 逆に「暗号文のはずが平文で commit に入った」 も、 error 無しに起きる:
    - filter の設定前 (unlock・init の前) に、 暗号化の path へ新しい file を add した
    - repo の外に置いた file を `git hash-object -w` に `--path` なしで渡し、 その blob を index に入れた
      (path の clean filter が掛からない。 conventions/multi-session-coordination.md#temp-index-commit)
    - 平文の diff を index に直接当てた
  どれも作業 tree では普通に読めるので、 上の検査は READABLE と言う。 平文は push されて remote に残る。
  → HEAD の tree で、 `filter=git-crypt` の属性が付いた path の blob の先頭が magic かを見る (鍵は要らない)。

    対象の blob が全部暗号文                 → 「commit 済みの版: N blob すべて暗号文」 (exit 0)
    平文の blob が在る                       → PLAINTEXT-COMMITTED (exit 1。 dir の名前だけ出す)

  空の file は git-crypt が暗号化しないので数えない。 見るのは HEAD の tree だけ (過去の commit に残った平文は見ない)。

使い方: check-gitcrypt-readable.py [--selftest]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAGIC = b"\x00GITCRYPT"
PERSONAL_KEY = Path.home() / ".secrets" / "git-crypt.key"


def encrypted_patterns(root: Path):
    """`.gitattributes` で git-crypt 対象に指定された pattern を返す。"""
    ga = root / ".gitattributes"
    if not ga.is_file():
        return []
    out = []
    for line in ga.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "filter=git-crypt" not in line:
            continue
        out.append(line.split()[0])
    return out


def targets(root: Path, patterns):
    """pattern に当たる追跡 file を返す (= git 自身に解決させる)。"""
    if not patterns:
        return []
    # -z は必須: 既定の ls-files は **非 ASCII の path を引用符 + 8 進エスケープで返す**
    # ("docs/\346\227\245..." の形)。 そのまま Path にすると存在しない path になり、
    # 「読めない = LOCKED」 と誤検知する。 2026-09-12 に日本語 file 名を持つ 6 repo が
    # 一斉に LOCKED と報告され、 実際は全て健全だった。
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *patterns],
                       capture_output=True)
    names = r.stdout.split(b"\x00")
    return [root / n.decode("utf-8", "surrogateescape") for n in names if n]


def locked(path: Path):
    """working tree の中身が暗号文のままか。 読めなければ None。"""
    try:
        with path.open("rb") as fh:
            return fh.read(len(MAGIC)) == MAGIC
    except OSError:
        return None


def committed_plaintext(root: Path):
    """HEAD の tree で、 `filter=git-crypt` の属性が付いた path の blob のうち、 平文のまま入っているもの。

    (対象の blob の数, [平文の path…])。 HEAD が無い (commit がまだ無い) なら (0, [])。 空の blob は数えない
    (git-crypt は空の file を暗号化しない)。 属性は git 自身に解決させる (下の階層の .gitattributes と打ち消しも効く)。
    """
    ls = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD"], capture_output=True)
    if ls.returncode != 0:
        return 0, []
    entries = []
    for rec in ls.stdout.split(b"\x00"):
        if not rec or b"\t" not in rec:
            continue
        meta, path = rec.split(b"\t", 1)
        parts = meta.split()
        if len(parts) == 3 and parts[1] == b"blob":
            entries.append((parts[2].decode(), path))
    if not entries:
        return 0, []
    at = subprocess.run(["git", "-C", str(root), "check-attr", "-z", "--stdin", "filter"],
                        input=b"\x00".join(p for _, p in entries) + b"\x00", capture_output=True).stdout.split(b"\x00")
    crypt = {at[i] for i in range(0, len(at) - 2, 3) if at[i + 2] == b"git-crypt"}
    todo = [(sha, p) for sha, p in entries if p in crypt]
    if not todo:
        return 0, []
    proc = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    n, plain = 0, []
    try:
        for sha, path in todo:
            proc.stdin.write(sha.encode() + b"\n")
            proc.stdin.flush()
            head = proc.stdout.readline().split()
            if len(head) < 3:
                continue
            size = int(head[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            if size == 0:
                continue
            n += 1
            if not data.startswith(MAGIC):
                plain.append(path.decode("utf-8", "surrogateescape"))
    finally:
        proc.stdin.close()
        proc.wait()
    return n, plain


def report_committed(root: Path) -> int:
    """commit に入った版が暗号文かを 1 行で言う (鍵は要らない)。 平文が在れば 1。"""
    n, plain = committed_plaintext(root)
    if not plain:
        print(f"   commit 済みの版: {n} blob すべて暗号文" if n else "   commit 済みの版: 対象の blob が無い")
        return 0
    dirs = sorted({str(Path(p).parent) for p in plain})
    print(f"   🔴 PLAINTEXT-COMMITTED: {len(plain)}/{n} blob が平文のまま commit に入っている (暗号化の filter を通っていない)")
    print("        dir: " + ", ".join(dirs[:6]) + (" …" if len(dirs) > 6 else ""))
    print("   ※ 作業 tree では普通に読めるので気づかない。 push 済みなら平文が remote に残っている。")
    print("      直し方: filter が効く状態 (unlock 済み) で `git add --renormalize <path>` → commit。")
    print("      履歴に残った平文を消すのは別の作業 (docs/sensitive-repo-patterns.ja.md)。 原因の型 = 本 script の冒頭")
    return 1


def check(root: Path, key: Path = PERSONAL_KEY):
    pats = encrypted_patterns(root)
    print("── git-crypt で暗号化した file がこのマシンで読めるか")
    if not pats:
        print("   対象外: このリポに git-crypt 対象の宣言が無い")
        return 0
    rc_commit = report_committed(root)
    files = targets(root, pats)
    if not files:
        print(f"   対象外: 宣言はあるが該当する追跡 file が無い ({', '.join(pats)})")
        return rc_commit
    if not key.is_file():
        print(f"   SKIP: 鍵が無いマシン ({key}) — {len(files)} file は検査していない")
        print("         (= CI の runner 等。 検査しなかったと申告するだけで、 緑ではない)")
        return rc_commit
    bad = [f for f in files if locked(f) is not False]
    if bad:
        print(f"   🔒 LOCKED: {len(bad)}/{len(files)} file が暗号文のまま読めない")
        for f in bad[:5]:
            print(f"        {f.relative_to(root)}")
        print("   ※ この状態で private/ を読む script は fail-open で **黙って 0 件**を返す。")
        print("      復旧: cd " + str(root) + " && git-crypt unlock " + str(key))
        return 1
    print(f"   READABLE: {len(files)} file すべて平文で読める ({', '.join(pats)})")
    return rc_commit


def selftest():
    import tempfile

    fails = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], capture_output=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], capture_output=True)

        # (1) 宣言が無ければ対象外
        if check(root, key=root / "nokey") != 0:
            fails.append("宣言が無いのに 0 を返さない")

        (root / ".gitattributes").write_text("secret.json filter=git-crypt diff=git-crypt\n",
                                             encoding="utf-8")
        (root / "secret.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True)

        # (2) 鍵が無ければ SKIP (= FAIL にしない)
        if check(root, key=root / "nokey") != 0:
            fails.append("鍵が無いマシンで FAIL にしてしまう (= CI が落ちる)")

        # (3) 鍵はあるのに暗号文 → LOCKED
        key = root / "key"; key.write_bytes(b"x")
        (root / "secret.json").write_bytes(MAGIC + b"\x00rest")
        if check(root, key=key) != 1:
            fails.append("暗号文のままなのに LOCKED を報告しない")

        # (4) 平文なら READABLE
        (root / "secret.json").write_text("{}\n", encoding="utf-8")
        if check(root, key=key) != 0:
            fails.append("平文なのに READABLE を報告しない")

        # (5) 日本語 file 名を LOCKED と誤判定しない (= ls-files の引用に壊されない。
        #     2026-09-12 に 6 repo が一斉に誤 LOCKED になった回帰 test)
        (root / ".gitattributes").write_text("*.json filter=git-crypt diff=git-crypt\n",
                                             encoding="utf-8")
        (root / "日本語の名前.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True)
        if check(root, key=key) != 0:
            fails.append("日本語 file 名を LOCKED と誤検知する")

    # ---- 逆向き: commit に入った版が平文 (鍵は要らない)。 1 件ずつ [PASS] / [FAIL] を出す (foil の歯の spec が label で照合する)
    def step(label, ok):
        print(("[PASS] " if ok else "[FAIL] ") + label)
        if not ok:
            fails.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        git = ["git", "-C", str(root), "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], capture_output=True)
        nokey = root / "nokey"
        (root / ".gitattributes").write_text("*.json filter=git-crypt diff=git-crypt\nsub/keep.json !filter\n",
                                             encoding="utf-8")
        (root / "sub").mkdir()
        # filter を設定していない repo で add すると、 暗号化の path に平文の blob が入る (= 見つけたい状態)
        (root / "plain.json").write_text('{"secret": 1}\n', encoding="utf-8")
        (root / "enc.json").write_bytes(MAGIC + b"\x00ciphertext")          # 暗号文の形をした blob
        (root / "empty.json").write_bytes(b"")                              # 空は暗号化されない = 数えない
        (root / "sub" / "keep.json").write_text("{}\n", encoding="utf-8")   # 属性を打ち消した path = 対象外
        (root / "note.txt").write_text("plain is fine here\n", encoding="utf-8")
        subprocess.run(git + ["add", "-A"], capture_output=True)
        step("commit がまだ無い repo は平文の判定をしない (HEAD が無い)", committed_plaintext(root) == (0, []))
        subprocess.run(git + ["commit", "-q", "-m", "c1"], capture_output=True)
        n, plain = committed_plaintext(root)
        step("暗号化の path に平文の blob が commit されていれば拾う", plain == ["plain.json"])
        step("暗号文の blob・空の blob・属性を打ち消した path・属性の無い path は拾わない", n == 2 and "enc.json" not in plain)
        step("平文が commit に在れば、 鍵が無いマシンでも終了値 1 (readable の SKIP に隠れない)", check(root, key=nokey) == 1)
        (root / "日本語.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(git + ["rm", "-q", "--cached", "plain.json"], capture_output=True)
        subprocess.run(git + ["add", "日本語.json"], capture_output=True)
        subprocess.run(git + ["commit", "-q", "-m", "c2"], capture_output=True)
        step("非 ASCII の path も拾う", committed_plaintext(root)[1] == ["日本語.json"])
        subprocess.run(git + ["rm", "-q", "--cached", "日本語.json"], capture_output=True)
        subprocess.run(git + ["commit", "-q", "-m", "c3"], capture_output=True)
        step("平文が無くなれば終了値 0 (commit 済みの版 = すべて暗号文)", check(root, key=nokey) == 0)

    if fails:
        print("SELFTEST FAIL:", file=sys.stderr)
        for f in fails:
            print("  -", f, file=sys.stderr)
        return 1
    print("SELFTEST PASS (11 checks)")
    return 0


def check_fleet(base: Path = None, key: Path = PERSONAL_KEY):
    """~/Claude 配下の **git-crypt 宣言がある全 repo** を見る。

    1 repo だけ見ると、 暗号化の本体が別 repo にある場合に取りこぼす
    (2026-09-12: 1 つの repo だけ見て、 実際に読まれている別 repo 側の cache を見落としかけた)。 宣言のある repo を git 自身に数えさせる。
    """
    base = base or (Path.home() / "Claude")
    repos = [d for d in sorted(base.iterdir())
             if (d / ".git").exists() and encrypted_patterns(d)]
    if not repos:
        print("── git-crypt で暗号化した file がこのマシンで読めるか")
        print("   対象外: git-crypt 宣言のある repo が無い")
        return 0
    rc = 0
    for d in repos:
        print(f"  [{d.name}]", end=" ")
        rc |= check(d, key)
    return rc


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--fleet" in sys.argv:
        sys.exit(check_fleet())
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, encoding="utf-8", errors="replace")
    sys.exit(check(Path(r.stdout.strip() or ".")))
