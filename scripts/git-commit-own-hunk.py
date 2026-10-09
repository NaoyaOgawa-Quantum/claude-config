#!/usr/bin/env python3
"""git-commit-own-hunk.py — 同じ file に別の session の未 commit の変更が居る時に、 自分の変更だけを commit する (一時 index。 作業 tree の相手の変更は触らない)。

## なぜ要るのか

並列の session が同じ file を触っていると、 `git commit -- <path>` は相手の未 commit の変更ごと commit する
(守れるのは file の単位まで)。 自分の分だけを commit する手順 (HEAD の版に自分の変更だけを当てた版を作り、
一時 index から commit する) は [`conventions/multi-session-coordination.md#temp-index-commit`](../conventions/multi-session-coordination.md#temp-index-commit)
に在るが、 手で踏むと次の穴に落ちる。 本 script はその穴を塞いだ形で 1 command にする。

1. **HEAD が動いた後の commit は、 相手の commit の中身を黙って戻す**。 版を作った時の HEAD (P) から一時 index を作り、
   その間に相手が commit して HEAD が X に進んでいると、 `git commit` は親 = X・tree = 「P + 自分の変更」 の commit を作る
   = X の変更が消える。 error は出ない (git が止めるのは commit の最中に HEAD が動いた時だけ)。
   → 親を最初に 1 回だけ決め、 commit の直前に HEAD がその親のままかを見て、 commit の直後に親を照合する。
   違えば ref を元に戻して (旧値つき) 版を作り直す。
2. **temp file を `git hash-object -w` に渡すと、 その path の clean filter が掛からない**。 暗号化 (git-crypt 等) の path なら
   平文の blob が commit に入る。 → `--path <path>` を付けて blob を作る。 親の版も filter を通して読む
   (`git cat-file --filters`)。
3. **実行 file の mode を 100644 と決め打ちすると実行権限が落ちる**。 → 親の tree の mode を引き継ぐ。
4. **commit の後に実 index を揃えないと、 自分の commit を取り消す変更が stage 済みになる**。 → commit の後に
   `git reset -q -- <path>` (作業 tree は不変)。
5. **commit 時の関門に止められた時に、 作業 tree に当てた自分の変更が残る**。 → 作業 tree への書き込みは commit が
   通った後にだけ行う (止められたら作業 tree は 1 byte も変わらない)。

commit は `git commit` で作る (pre-commit / prepare-commit-msg / commit-msg / post-commit がそのまま走る)。

## 似た道具との使い分け

- **本 script** = 手元の HEAD の上に commit する。 worktree を作らないので速く、 暗号化の repo でも checkout が要らない。
  hook は手元の作業 tree で走る。 push は別に行う。
- [`commit-from-origin-worktree.py`](commit-from-origin-worktree.py) = `origin/<branch>` から切った使い捨ての worktree で commit して push まで行う。
  手元の index・作業 tree・未 push の commit に一切触れない。 手元に他の session の未 push の commit が居て、 それを巻き込んで
  push したくない時はこちら (同じ file に相手の変更が混ざる時は、 その `--apply` に (old, new) の pair を渡す)。

## 使い方

    # 置換で指定 (親の版と作業 tree の両方に、 同じ置換を当てる)。 OLD / NEW は file で渡す (shell の引用の事故を避ける)
    git-commit-own-hunk.py -F msg.txt --replace <path> old.txt new.txt [--replace …]
    git-commit-own-hunk.py -F msg.txt --replace-str <path> 'old' 'new'

    # 版で指定 (「親の版 + 自分の変更」 の全文を自分で作った時)。 作った時の HEAD を --base に書く
    git-commit-own-hunk.py -F msg.txt --base <sha> --version <path> mine.txt
    #   ⚠️ --version は作業 tree に書かない (全文は相手の変更の混ざった作業 tree に当てられない)。 commit の後、
    #   作業 tree が親の版のままだと自分の commit を取り消す差分に見える = 作業 tree が親の版と一致するなら
    #   `git checkout HEAD -- <path>`、 相手の変更が在るなら自分の変更を作業 tree にも当てる (= --replace を使う方が楽)

    --dry-run   commit せずに、 何が commit されるかを出す
    --no-worktree  置換を作業 tree に当てない (もう自分で当ててある時)
    --repo DIR  (既定 = cwd の repo)

置換は親の版の中で**ちょうど 1 回**一致しなければ止まる (0 回 = もう入っているか文面が違う / 2 回以上 = どれか決まらない)。
commit の後は push と、 相手の session への 1 行 (相手の `git diff` から自分の分が消えて見える) を忘れない。

## 終了値

    0 = commit した (dry-run なら何もしていない)
    1 = commit 時の関門 (hook) が止めた。 HEAD も作業 tree も変わっていない
    2 = 使い方・前提の誤り (置換が 1 回一致でない、 変更が無い、 対象が通常の file でない)
    3 = commit は入ったが、 作業 tree に同じ置換を当てられなかった (相手の変更が同じ場所に在る)。 作業 tree を手で直す
    4 = HEAD が動き続けて版を作り直せなかった / --base が今の HEAD と違う。 何も commit していない

## 限界

- HEAD を見てから `git commit` が HEAD を読むまでの間 (process の起動 1 回ぶん) に相手の commit が入ると、 誤った commit が
  一瞬 HEAD になる。 直後の照合で ref を戻して作り直すが、 その間に push する post-commit hook が在る repo では、
  誤った commit が外へ出うる (そういう hook を持つ repo では使わない)。
- hook は作業 tree を読むことがある。 hook が見る作業 tree には相手の変更も在る (index は自分の分だけ)。
- rename と symlink は扱わない。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RC_OK, RC_GATE, RC_USAGE, RC_WORKTREE, RC_MOVED = 0, 1, 2, 3, 4
TEST_HOOK_ENV = "GIT_COMMIT_OWN_HUNK_TEST_HOOK"   # selftest 専用: 最初の commit の直前に 1 回だけ shell で実行する (窓を決定的に開ける)
RETRIES = 3


class Stop(Exception):
    def __init__(self, rc: int, msg: str):
        super().__init__(msg)
        self.rc = rc


def run(top, *args, inp: bytes | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(top), *args], input=inp, capture_output=True, env=env)


def out(top, *args, inp: bytes | None = None, env: dict | None = None) -> bytes:
    r = run(top, *args, inp=inp, env=env)
    if r.returncode != 0:
        raise Stop(RC_USAGE, f"git {' '.join(args[:3])} が失敗: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout


def repo_top(start: Path) -> Path:
    r = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True)
    if r.returncode != 0:
        raise Stop(RC_USAGE, f"git の repo ではない: {start}")
    return Path(r.stdout.decode().strip())


def rel_path(top: Path, p: str, cwd: Path) -> str:
    q = Path(p)
    q = q if q.is_absolute() else cwd / q
    try:
        return q.resolve().relative_to(top.resolve()).as_posix()
    except ValueError:
        raise Stop(RC_USAGE, f"repo の外の path: {p}")


def parent_version(top: Path, parent: str, path: str) -> bytes | None:
    """親の版 (smudge filter を通した中身)。 親に無ければ None。"""
    r = run(top, "cat-file", "--filters", f"{parent}:{path}")
    return r.stdout if r.returncode == 0 else None


def tree_mode(top: Path, parent: str, path: str) -> str:
    line = out(top, "ls-tree", parent, "--", path).decode().strip()
    if not line:
        return "100644"
    mode = line.split()[0]
    if mode not in ("100644", "100755"):
        raise Stop(RC_USAGE, f"通常の file でない (mode {mode}): {path}")
    return mode


def apply_replaces(data: bytes, reps: list, where: str) -> bytes:
    for old, new in reps:
        n = data.count(old)
        if n != 1:
            hint = "もう入っているか、 文面が違う" if n == 0 else "どれを置き換えるか決まらない"
            raise Stop(RC_USAGE, f"{where}: 置換の old が {n} 回一致 (ちょうど 1 回でなければ止める = {hint}): "
                                 f"{old[:60].decode('utf-8', 'replace')!r}")
        data = data.replace(old, new)
    return data


def build_versions(top: Path, parent: str, specs: dict) -> dict:
    """{path: (mode, mine bytes)}。 specs[path] = {"reps": [(old, new)…]} か {"version": bytes}。"""
    built = {}
    for path, sp in specs.items():
        old = parent_version(top, parent, path)
        if "version" in sp:
            mine = sp["version"]
        else:
            if old is None:
                raise Stop(RC_USAGE, f"{path}: 親の版に無い file は置換で指定できない (--version で全文を渡す)")
            mine = apply_replaces(old, sp["reps"], f"{path} (親の版)")
        if old is not None and mine == old:
            raise Stop(RC_USAGE, f"{path}: 親の版と同じ = commit する変更が無い (もう入っている)")
        built[path] = (tree_mode(top, parent, path), mine)
    return built


def commit_once(top: Path, parent: str, built: dict, msg_file: Path, first: bool) -> tuple:
    """(状態, 値)。 状態 = ok (値 = commit) / gate (値 = git の出力) / moved (値 = 説明)。"""
    tmp = Path(tempfile.mkdtemp(prefix="own-hunk-"))
    try:
        env = dict(os.environ, GIT_INDEX_FILE=str(tmp / "index"))
        out(top, "read-tree", parent, env=env)
        for path, (mode, mine) in built.items():
            blob = out(top, "hash-object", "-w", "--path", path, "--stdin", inp=mine).decode().strip()
            out(top, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}", env=env)
        if out(top, "rev-parse", "HEAD").decode().strip() != parent:
            return "moved", "版を作っている間に HEAD が動いた"
        hook = os.environ.get(TEST_HOOK_ENV)
        if hook and first:
            subprocess.run(hook, shell=True, cwd=str(top), capture_output=True)
        r = run(top, "commit", "-q", "-F", str(msg_file), env=env)
        if r.returncode != 0:
            return "gate", (r.stdout + r.stderr).decode("utf-8", "replace").strip()
        new = out(top, "rev-parse", "HEAD").decode().strip()
        parents = out(top, "rev-list", "--parents", "-n", "1", new).decode().split()[1:]
        touched = set(out(top, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", new).decode().split("\0")) - {""}
        if parents[:1] != [parent] or not touched <= set(built):
            # 親が違う = 相手の commit の上に、 古い tree の commit を作った (相手の変更を戻している)。 ref を元に戻す (旧値つき)
            back = parents[0] if parents else parent
            rb = run(top, "update-ref", "HEAD", back, new)
            state = "戻した" if rb.returncode == 0 else "戻せなかった (HEAD がさらに動いた = git log を見て手で直す)"
            return "moved", f"commit の直前に HEAD が動いた。 誤った commit {new[:9]} を HEAD から外して {state}"
        return "ok", new
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def dry_run(top: Path, parent: str, built: dict) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="own-hunk-"))
    try:
        env = dict(os.environ, GIT_INDEX_FILE=str(tmp / "index"))
        out(top, "read-tree", parent, env=env)
        for path, (mode, mine) in built.items():
            blob = out(top, "hash-object", "-w", "--path", path, "--stdin", inp=mine).decode().strip()
            out(top, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}", env=env)
        sys.stdout.write(out(top, "diff", "--cached", "--stat", parent, env=env).decode("utf-8", "replace"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply_worktree(top: Path, specs: dict) -> list:
    """置換を作業 tree に当てる。 当てられなかった path の説明の list を返す (空 = 全部当たった / もう当たっていた)。"""
    problems = []
    for path, sp in specs.items():
        if "reps" not in sp:
            continue
        f = top / path
        try:
            data = f.read_bytes()
        except OSError as e:
            problems.append(f"{path}: 作業 tree の file を読めない ({e})")
            continue
        new_data, bad = data, None
        for old, new in sp["reps"]:
            n = new_data.count(old)
            if n == 1:
                new_data = new_data.replace(old, new)
            elif n == 0 and new and new in new_data:
                continue                      # もう当ててある
            else:
                bad = f"{path}: 作業 tree で old が {n} 回一致 = 相手の変更が同じ場所に在る。 手で直す"
                break
        if bad:
            problems.append(bad)
        elif new_data != data:
            f.write_bytes(new_data)
    return problems


def do_commit(top: Path, specs: dict, msg_file: Path, base: str | None, dry: bool, worktree: bool) -> int:
    has_version = any("version" in sp for sp in specs.values())
    for attempt in range(1, RETRIES + 1):
        parent = out(top, "rev-parse", "HEAD").decode().strip()
        if base is not None:
            want = out(top, "rev-parse", base).decode().strip()
            if want != parent:
                raise Stop(RC_MOVED, f"--base {base[:9]} は今の HEAD ({parent[:9]}) と違う = 渡された版は古い親から作ってある。 "
                                     "今の HEAD から版を作り直す")
        built = build_versions(top, parent, specs)
        if dry:
            print(f"dry-run: 親 = {parent[:9]}。 commit されるのは次だけ (相手の未 commit の変更は入らない):")
            dry_run(top, parent, built)
            return RC_OK
        state, val = commit_once(top, parent, built, msg_file, first=(attempt == 1))
        if state == "gate":
            print("🛑 commit 時の関門が止めた。 HEAD も作業 tree も変わっていない。 git の出力:", file=sys.stderr)
            print(val, file=sys.stderr)
            return RC_GATE
        if state == "moved":
            print(f"⚠️ {val}", file=sys.stderr)
            if has_version:
                raise Stop(RC_MOVED, "版 (--version) は古い親から作ってある。 今の HEAD から作り直して呼び直す")
            continue
        out(top, "reset", "-q", "--", *built)
        problems = apply_worktree(top, specs) if worktree else []
        stat = out(top, "show", "--stat", "--format=%h %s", val).decode("utf-8", "replace").strip()
        print(f"✅ commit した (自分の分だけ。 親 = {parent[:9]}、 試行 {attempt} 回目):")
        print(stat)
        print("次: push する。 相手の session に 1 行知らせる (相手の git diff から自分の分が消えて見える)。")
        if problems:
            print("🟠 commit は入ったが、 作業 tree に同じ置換を当てられなかった:", file=sys.stderr)
            for x in problems:
                print("  " + x, file=sys.stderr)
            return RC_WORKTREE
        return RC_OK
    raise Stop(RC_MOVED, f"HEAD が {RETRIES} 回続けて動いた。 何も commit していない (少し待って呼び直す)")


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------
def selftest() -> int:
    fails = 0
    base_env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                    GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    base_env.pop(TEST_HOOK_ENV, None)
    saved = dict(os.environ)

    def g(top, *args, inp=None):
        return subprocess.run(["git", "-C", str(top), *args], input=inp, capture_output=True, env=dict(os.environ))

    def new_repo(root: Path, name: str) -> Path:
        top = root / name
        top.mkdir()
        g(top, "init", "-q", "-b", "main")
        (top / "f.txt").write_text("a\nb\nc\nd\ne\n")
        (top / "g.txt").write_text("g0\n")
        g(top, "add", "f.txt", "g.txt")
        g(top, "commit", "-q", "-m", "P")
        return top

    def call(top: Path, argv: list) -> int:
        try:
            return main(["--repo", str(top), *argv])
        except SystemExit as e:
            return int(e.code or 0)

    def ok(label: str, cond: bool, extra: str = "") -> None:
        nonlocal fails
        fails += not cond
        print(f"{'PASS' if cond else 'FAIL'} {label}{(': ' + extra) if extra and not cond else ''}")

    def head_file(top, path):
        return g(top, "cat-file", "-p", f"HEAD:{path}").stdout.decode()

    root = Path(tempfile.mkdtemp(prefix="own-hunk-selftest-"))
    try:
        os.environ.clear()
        os.environ.update(base_env)
        msg = root / "msg.txt"
        msg.write_text("mine\n")

        # 1. 相手の未 commit の変更が同じ file に居る → 自分の分だけ commit、 作業 tree は両方、 index は揃う
        top = new_repo(root, "r1")
        (top / "f.txt").write_text("a-other\nb\nc\nd\ne\n")          # 相手の未 commit の変更
        rc = call(top, ["-F", str(msg), "--replace-str", "f.txt", "e\n", "e-mine\n"])
        ok("自分の分だけが commit に入る (相手の未 commit の変更は入らない)",
           rc == 0 and head_file(top, "f.txt") == "a\nb\nc\nd\ne-mine\n", f"rc={rc} head={head_file(top, 'f.txt')!r}")
        ok("作業 tree は相手の変更 + 自分の変更", (top / "f.txt").read_text() == "a-other\nb\nc\nd\ne-mine\n")
        ok("実 index は新しい HEAD に揃う (status が ' M' = 自分の commit を取り消す変更が stage されていない)",
           g(top, "status", "--porcelain", "--", "f.txt").stdout.decode().startswith(" M"))

        # 2. commit 時の関門が止める → HEAD も作業 tree も変わらない
        top = new_repo(root, "r2")
        hook = top / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho blocked >&2\nexit 1\n")
        hook.chmod(0o755)
        (top / "f.txt").write_text("a-other\nb\nc\nd\ne\n")
        before_head = g(top, "rev-parse", "HEAD").stdout
        rc = call(top, ["-F", str(msg), "--replace-str", "f.txt", "e\n", "e-mine\n"])
        ok("関門が止めたら終了値 1、 HEAD は動かない", rc == RC_GATE and g(top, "rev-parse", "HEAD").stdout == before_head, f"rc={rc}")
        ok("関門が止めたら作業 tree は 1 byte も変わらない (自分の変更は当たっていない)",
           (top / "f.txt").read_text() == "a-other\nb\nc\nd\ne\n")

        # 3. commit の直前に相手が commit して HEAD が動く → 相手の commit の中身を戻さず、 作り直して commit
        top = new_repo(root, "r3")
        os.environ[TEST_HOOK_ENV] = "printf 'g1\\n' >> g.txt && git add g.txt && git commit -q -m other"
        rc = call(top, ["-F", str(msg), "--replace-str", "f.txt", "e\n", "e-mine\n"])
        os.environ.pop(TEST_HOOK_ENV, None)
        log = g(top, "log", "--format=%s").stdout.decode().split()
        ok("HEAD が動いても相手の commit の中身が残る (g.txt が戻されていない)",
           rc == 0 and head_file(top, "g.txt") == "g0\ng1\n", f"rc={rc} g={head_file(top, 'g.txt')!r}")
        ok("履歴は 相手の commit → 自分の commit (誤った commit は HEAD に残らない)", log[:3] == ["mine", "other", "P"], str(log))
        ok("自分の変更も入っている", head_file(top, "f.txt").endswith("e-mine\n"))

        # 4. 実行 file の mode を引き継ぐ
        top = new_repo(root, "r4")
        (top / "x.sh").write_text("#!/bin/sh\necho 1\n")
        (top / "x.sh").chmod(0o755)
        g(top, "add", "x.sh")
        g(top, "commit", "-q", "-m", "x")
        rc = call(top, ["-F", str(msg), "--replace-str", "x.sh", "echo 1\n", "echo 2\n"])
        ok("実行 file の mode (100755) が落ちない", rc == 0 and g(top, "ls-tree", "HEAD", "--", "x.sh").stdout.decode().startswith("100755"))

        # 5. clean filter が掛かる (暗号化の path に平文の blob を入れない)
        top = new_repo(root, "r5")
        g(top, "config", "filter.up.clean", "tr a-z A-Z")
        g(top, "config", "filter.up.smudge", "tr A-Z a-z")
        (top / ".gitattributes").write_text("s.txt filter=up\n")
        (top / "s.txt").write_text("secret one\n")
        g(top, "add", ".gitattributes", "s.txt")
        g(top, "commit", "-q", "-m", "s")
        rc = call(top, ["-F", str(msg), "--replace-str", "s.txt", "secret one\n", "secret two\n"])
        ok("blob は path の clean filter を通る (保存された中身は filter の後の形)",
           rc == 0 and head_file(top, "s.txt") == "SECRET TWO\n", f"rc={rc} raw={head_file(top, 's.txt')!r}")

        # 6. 置換が 1 回一致でない → 止まる
        top = new_repo(root, "r6")
        (top / "f.txt").write_text("a\nb\nc\nd\ne\n")
        before_head = g(top, "rev-parse", "HEAD").stdout
        rc0 = call(top, ["-F", str(msg), "--replace-str", "f.txt", "zzz\n", "y\n"])
        (top / "h.txt").write_text("k\nk\n")
        g(top, "add", "h.txt")
        g(top, "commit", "-q", "-m", "h")
        before_head = g(top, "rev-parse", "HEAD").stdout
        rc2 = call(top, ["-F", str(msg), "--replace-str", "h.txt", "k\n", "y\n"])
        ok("old が 0 回・2 回なら終了値 2、 何も commit しない",
           rc0 == RC_USAGE and rc2 == RC_USAGE and g(top, "rev-parse", "HEAD").stdout == before_head, f"rc0={rc0} rc2={rc2}")

        # 7. --version: 新しい file / 古い --base は止まる
        top = new_repo(root, "r7")
        mine = root / "n.mine"
        mine.write_text("new file\n")
        base = g(top, "rev-parse", "HEAD").stdout.decode().strip()
        rc = call(top, ["-F", str(msg), "--base", base, "--version", "n.txt", str(mine)])
        ok("--version で新しい file を足せる (mode 100644)",
           rc == 0 and g(top, "ls-tree", "HEAD", "--", "n.txt").stdout.decode().startswith("100644") and head_file(top, "n.txt") == "new file\n")
        mine.write_text("new file v2\n")
        rc = call(top, ["-F", str(msg), "--base", base, "--version", "n.txt", str(mine)])
        ok("--base が今の HEAD と違えば終了値 4、 何も commit しない", rc == RC_MOVED and head_file(top, "n.txt") == "new file\n", f"rc={rc}")

        # 8. dry-run は commit しない / 相手が実 index に stage した file は自分の commit に入らない
        top = new_repo(root, "r8")
        (top / "o.txt").write_text("other staged\n")
        g(top, "add", "o.txt")                                        # 相手が実 index に stage
        before_head = g(top, "rev-parse", "HEAD").stdout
        rc = call(top, ["-F", str(msg), "--dry-run", "--replace-str", "f.txt", "e\n", "e-mine\n"])
        ok("dry-run は commit しない", rc == 0 and g(top, "rev-parse", "HEAD").stdout == before_head)
        rc = call(top, ["-F", str(msg), "--replace-str", "f.txt", "e\n", "e-mine\n"])
        names = g(top, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.decode().split()
        ok("相手が実 index に stage した file は自分の commit に入らず、 stage されたまま残る",
           rc == 0 and names == ["f.txt"] and g(top, "status", "--porcelain", "--", "o.txt").stdout.decode().startswith("A "), str(names))

        # 9. 作業 tree の同じ場所に相手の変更が在る → commit は入り、 終了値 3 で知らせる
        top = new_repo(root, "r9")
        (top / "f.txt").write_text("a\nb\nc\nd\ne-other\n")
        rc = call(top, ["-F", str(msg), "--replace-str", "f.txt", "e\n", "e-mine\n"])
        ok("作業 tree に当てられない時は終了値 3 (commit は入り、 作業 tree の相手の変更はそのまま)",
           rc == RC_WORKTREE and head_file(top, "f.txt").endswith("e-mine\n") and (top / "f.txt").read_text().endswith("e-other\n"), f"rc={rc}")
    finally:
        os.environ.clear()
        os.environ.update(saved)
        shutil.rmtree(root, ignore_errors=True)
    print("ALL PASS" if not fails else f"{fails} FAIL")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", help="repo の中の dir (既定 = cwd)")
    ap.add_argument("-F", "--message-file", help="commit message の file")
    ap.add_argument("--replace", nargs=3, action="append", metavar=("PATH", "OLDFILE", "NEWFILE"), default=[],
                    help="親の版と作業 tree の PATH で、 OLDFILE の中身を NEWFILE の中身に置き換える (ちょうど 1 回一致)")
    ap.add_argument("--replace-str", nargs=3, action="append", metavar=("PATH", "OLD", "NEW"), default=[],
                    help="同上、 文字列で渡す")
    ap.add_argument("--version", nargs=2, action="append", metavar=("PATH", "FILE"), default=[],
                    help="PATH の全文 (親の版 + 自分の変更) を FILE で渡す。 --base が要る")
    ap.add_argument("--base", help="--version の版を作った時の HEAD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-worktree", action="store_true", help="置換を作業 tree に当てない")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        cwd = Path(args.repo).resolve() if args.repo else Path.cwd()
        top = repo_top(cwd)
        if not args.message_file and not args.dry_run:
            raise Stop(RC_USAGE, "-F <commit message の file> が要る")
        if args.version and not args.base:
            raise Stop(RC_USAGE, "--version には --base <版を作った時の HEAD> が要る")
        specs: dict = {}
        for p, of, nf in args.replace:
            specs.setdefault(rel_path(top, p, cwd), {}).setdefault("reps", []).append((Path(of).read_bytes(), Path(nf).read_bytes()))
        for p, o, n in args.replace_str:
            specs.setdefault(rel_path(top, p, cwd), {}).setdefault("reps", []).append((o.encode(), n.encode()))
        for p, f in args.version:
            rp = rel_path(top, p, cwd)
            if rp in specs:
                raise Stop(RC_USAGE, f"{rp}: --replace と --version を同じ path に混ぜない")
            specs[rp] = {"version": Path(f).read_bytes()}
        if not specs:
            raise Stop(RC_USAGE, "--replace / --replace-str / --version のどれかが要る")
        msg = Path(args.message_file).resolve() if args.message_file else Path(os.devnull)
        return do_commit(top, specs, msg, args.base, args.dry_run, not args.no_worktree)
    except Stop as e:
        print(f"git-commit-own-hunk: {e}", file=sys.stderr)
        return e.rc


if __name__ == "__main__":
    sys.exit(main())
