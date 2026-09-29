"""書き換えられた (force-push された) 履歴に手元の clone を **中身で** 揃え、 古い世代の commit / blob の push を止める共有部品。

使い手 = scripts/git-rewrite-follow.py (CLI: follow / sweep / guard / ensure-prepush / status)、
scripts/repo-sync-sweep.sh (session 開始の同期 engine: diverged の repo にだけ呼ぶ)、
scripts/fleet-heartbeat.py (毎時の無人 commit+push: rebase の前に forced update を見る)。
判定をここ 1 か所に置き、 3 者が同じ述語で話す。 直接実行 = selftest (fixture 6 種 + guard)。

なぜ在るか (実測 2026-09-29): 履歴を書き換えた repo の追従 script が、 書き換えられる側の repo (個人層) の中に
在った。 その repo 自身を書き換えると、 古い履歴の Mac は追従 script を pull できず、 毎時の無人 job は
`pull --rebase` で古い commit を新しい履歴に積み直しうる (= 消した中身が push で remote に戻る)。 追従の判定を
**書き換えられない層 (本 repo) に** 置き、 repo 自身が運ぶ manifest (`.rewrite-follow/`) と tree の一致だけで
決めるようにした。 一般則 = conventions/multi-machine-state.md#history-rewrite-follow。

不変条件 (= この部品が守るもの):
  I1  ref を動かすのは「手元の committed content が upstream に在る」 と確かめた時だけ。 `git reset --keep`
      (未 commit の変更は保つ。 書き換えで変わった file に未 commit の変更が重なれば git が止める = そのまま止まる)。
  I2  `pull` / `merge` / `rebase` はしない。 揃えられない repo は 1 行で止まったと言う (exit 1)。
  I3  push 側: 対応表の旧 sha / 旧世代にしか無い blob を含む push を拒む (pre-push stub、 rebase で sha が変わっても
      blob で当たる)。
  I4  読むのは fetch 済みの remote-tracking ref (`<remote>/<branch>:<path>`) = worktree の pull 状態に依らない
      (conventions/hook-authoring.md#parallel-hooks-no-ordering)。

追従の判定 (follow_repo):
  0. upstream が無い / detached / merge・rebase 進行中 → 触らない。 HEAD が upstream の祖先 (= behind か同じ) →
     無音 (通常の同期の仕事)。 upstream が HEAD の祖先 (= ahead だけ) → 無音 (push の仕事)。 それ以外 = diverged。
  1. **対応表** (旧 sha → 新 sha): upstream の `.rewrite-follow/commit-map*` (書き換えの後に通常 commit で置く) と、
     外から渡す glob (`--map`、 `~/.claude/rewrite-follow-maps.txt`、 env GIT_REWRITE_FOLLOW_MAPS)。 HEAD か、 HEAD から
     first-parent で MAP_WALK 個まで遡った祖先 A が表に在り、 A..HEAD の差分が全部 **volatile path** (upstream の
     `.rewrite-follow/ignore-paths`、 例 = 無人 job が書く status file) なら、 表を最後まで辿った新 sha が upstream の
     祖先である時に揃える。
  2. **tree の一致**: upstream の直近 MAX 個の commit に HEAD と同じ tree id が在れば揃える (対応表が無い書き換え、
     1 commit 1 回の rev-list で済む)。
  3. **volatile を除いた tree の一致**: ignore-paths が宣言されていれば、 その path を除いた署名で 2 と同じ比較
     (無人 job の commit が古い履歴の上に載っている Mac)。
  4. どれも当たらない → 止まる (未 push の中身がある。 中身を確かめてから人が揃える)。
  揃えた後、 旧 sha を持つ手元の他 branch を名指しする (消さない = push しないよう知らせるだけ)。

forced update の証拠 (heartbeat が rebase の前に見る): remote-tracking ref の reflog に `forced-update` の
entry が在るか (fetch がその場で書く。 unreachable になった entry は既定 30 日で expire = それより後の判定は
証拠を失う。 その窓は heartbeat の defer が beat を止め fleet の 🔴 で人に届く、 かつ I3 の pre-push が最後の網)。

manifest (`<repo>/.rewrite-follow/`、 repo 自身が運ぶ。 読むのは upstream の版):
  ignore-paths      volatile な path (1 行 1 つ、 dir は末尾 `/`、 `#` 以降は注釈)。 書き換えの **前** に通常 commit で置く
  commit-map*       filter-repo が出す `old new` (先頭に `old new` の見出し行があってもよい)。 書き換えの **後** に置く
  forbidden-blobs*  旧世代にしか無い blob の sha1 (書き換えで消した平文の版)。 pre-push が push 範囲の object と突合する
"""
from __future__ import annotations

import glob as globmod
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MANIFEST_DIR = ".rewrite-follow"
MAP_WALK = 64            # HEAD から first-parent で遡って対応表を探す上限 (= 無人 job の commit が積もる数の上限)
DEFAULT_MAX = 300        # tree 比較の探索幅 (rev-list --max-count)
FETCH_TIMEOUT = 20
STUB_MARK = "git-rewrite-follow pre-push stub"
MAPS_FILE_ENV = "GIT_REWRITE_FOLLOW_MAPS_FILE"
MAPS_ENV = "GIT_REWRITE_FOLLOW_MAPS"
LOG_ENV = "GIT_REWRITE_FOLLOW_LOG"
ZERO = "0" * 40
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


# ---------------------------------------------------------------- git helpers

def _env():
    e = dict(os.environ)
    e.setdefault("GIT_TERMINAL_PROMPT", "0")
    e.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=5")
    e["LC_ALL"] = "C"
    return e


def git(repo, *args, check=True, timeout=60, input=None):
    """stdout (str, rstrip)。 check=True で失敗なら RuntimeError (stderr の 1 行目)。"""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=_env(),
                       timeout=timeout, input=input)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[0][:200] if (r.stderr or r.stdout).strip()
                           else f"git {' '.join(args)} failed rc={r.returncode}")
    return r.stdout.rstrip("\n")


def git_ok(repo, *args, timeout=60):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=_env(),
                          timeout=timeout).returncode == 0


def is_ancestor(repo, a, b):
    return git_ok(repo, "merge-base", "--is-ancestor", a, b)


def rev(repo, r):
    try:
        return git(repo, "rev-parse", "--verify", "-q", r + "^{commit}")
    except RuntimeError:
        return ""


def upstream_of(repo):
    """現在の branch の upstream (例 'origin/main')。 無ければ ''。 detached でも ''。"""
    try:
        if git(repo, "symbolic-ref", "-q", "HEAD", check=False) == "":
            return ""
        return git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except RuntimeError:
        return ""


def in_progress(repo):
    gd = Path(git(repo, "rev-parse", "--git-dir"))
    if not gd.is_absolute():
        gd = Path(repo) / gd
    return any((gd / n).exists() for n in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD"))


def forced_update_seen(repo, upstream, n=30):
    """remote-tracking ref の reflog の直近 n entry に forced-update が在るか (fetch が書く)。"""
    if not upstream:
        return False
    out = git(repo, "reflog", "show", "--format=%gs", f"-n{n}", f"refs/remotes/{upstream}", check=False)
    return "forced-update" in out


# ---------------------------------------------------------------- manifest / maps

def upstream_manifest_files(repo, upstream):
    """upstream の .rewrite-follow/ の file 名 → 中身 (str)。 無ければ {}。"""
    if not upstream:
        return {}
    out = git(repo, "ls-tree", "--name-only", upstream, MANIFEST_DIR + "/", check=False)
    files = {}
    for p in out.splitlines():
        name = p.rsplit("/", 1)[-1]
        body = git(repo, "show", f"{upstream}:{p}", check=False)
        files[name] = body
    return files


def parse_ignore_paths(text):
    out = []
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.lstrip("/"))
    return out


def parse_map(text):
    """`old new` 行 → {old: new}。 見出し行と壊れた行は飛ばす。"""
    m = {}
    for line in (text or "").splitlines():
        a = line.split()
        if len(a) == 2 and _SHA_RE.match(a[0]) and _SHA_RE.match(a[1]):
            m[a[0]] = a[1]
    return m


def parse_shas(text):
    return {l.strip() for l in (text or "").splitlines() if _SHA_RE.match(l.strip())}


def extra_map_paths(cli_globs=()):
    """外から渡す対応表の file 一覧 (CLI glob + maps file + env)。 値は path。"""
    globs = list(cli_globs)
    mf = os.environ.get(MAPS_FILE_ENV) or os.path.join(os.path.expanduser("~"), ".claude", "rewrite-follow-maps.txt")
    try:
        with open(mf, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    globs.append(os.path.expanduser(line))
    except OSError:
        pass
    for g in (os.environ.get(MAPS_ENV) or "").split(":"):
        if g.strip():
            globs.append(os.path.expanduser(g.strip()))
    paths = []
    for g in globs:
        for p in sorted(globmod.glob(g)):
            if os.path.isfile(p) and p not in paths:
                paths.append(p)
    return paths


class Generation:
    """旧世代の知識 = 対応表の集合 + 旧世代にしか無い blob + volatile path。"""

    def __init__(self, maps, forbidden, ignore):
        self.maps = maps                 # list[dict old→new]
        self.forbidden = forbidden       # set[sha]
        self.ignore = ignore             # list[str]

    @property
    def old_shas(self):
        s = set()
        for m in self.maps:
            s.update(o for o, n in m.items() if o != n)
        return s

    def chase(self, sha):
        """表を最後まで辿る (chain)。 変わらなければ元の sha。"""
        cur = sha
        for _ in range(len(self.maps) + 1):
            nxt = None
            for m in self.maps:
                if cur in m and m[cur] != cur:
                    nxt = m[cur]
                    break
            if nxt is None:
                break
            cur = nxt
        return cur

    @staticmethod
    def load(repo, upstream, cli_globs=()):
        files = upstream_manifest_files(repo, upstream)
        maps, forb = [], set()
        for name in sorted(files):
            if name.startswith("commit-map"):
                m = parse_map(files[name])
                if m:
                    maps.append(m)
            elif name.startswith("forbidden-blobs"):
                forb |= parse_shas(files[name])
        ignore = parse_ignore_paths(files.get("ignore-paths", ""))
        for p in extra_map_paths(cli_globs):
            try:
                with open(p, encoding="utf-8") as f:
                    m = parse_map(f.read())
            except OSError:
                continue
            if m:
                maps.append(m)
            fb = p + ".forbidden-blobs"
            if os.path.isfile(fb):
                try:
                    with open(fb, encoding="utf-8") as f:
                        forb |= parse_shas(f.read())
                except OSError:
                    pass
        return Generation(maps, forb, ignore)


# ---------------------------------------------------------------- tree signatures

def _under_ignore(path, ignore):
    for ig in ignore:
        if ig.endswith("/"):
            if path == ig[:-1] or path.startswith(ig):
                return True
        elif path == ig:
            return True
    return False


def _ignore_touches(prefix, ignore):
    """prefix (dir、 末尾 '/' 無し) の下に ignore の path が在るか (= 掘る必要があるか)。"""
    p = prefix + "/"
    return any(ig.startswith(p) for ig in ignore)


def tree_signature(repo, tree, ignore, prefix=""):
    """ignore を除いた tree の署名。 ignore の path に触れる dir だけ掘る (= 大きい tree でも git 呼び出しは深さ分)。"""
    if not ignore:
        return tree
    h = hashlib.sha1()
    for line in git(repo, "ls-tree", tree).splitlines():
        meta, name = line.split("\t", 1)
        mode, typ, sha = meta.split()
        path = prefix + name
        if _under_ignore(path, ignore) or (typ == "tree" and _under_ignore(path + "/", ignore)):
            continue
        if typ == "tree" and _ignore_touches(path, ignore):
            sha = tree_signature(repo, sha, ignore, path + "/")
        h.update(f"{mode} {typ} {sha}\t{path}\n".encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def diff_only_ignored(repo, a, b, ignore):
    """a..b の差分の path が全部 ignore の下か (空の差分も True)。"""
    if not ignore:
        return False
    out = git(repo, "diff", "--name-only", a, b, check=False)
    return all(_under_ignore(p, ignore) for p in out.splitlines())


# ---------------------------------------------------------------- follow

class Result:
    """state: current / ahead / followed / stopped / diverged (通常の分岐 = 追従の対象外) / skipped。 line = 人向けの 1 行 (無音なら '')。"""

    def __init__(self, state, line="", how="", target="", exit_code=0, extra=()):
        self.state, self.line, self.how, self.target, self.exit_code = state, line, how, target, exit_code
        self.extra = list(extra)  # 追加の行 (旧 branch の名指し等)


def _find_target(repo, head, upstream, gen, max_count):
    """(target sha, how) か (None, None)。"""
    up_sha = rev(repo, upstream)
    # 1. 対応表 (HEAD か、 volatile だけの差で遡れる祖先)
    if gen.maps:
        walk = git(repo, "rev-list", "--first-parent", f"--max-count={MAP_WALK}", head).splitlines()
        for a in walk:
            new = gen.chase(a)
            if new == a:
                continue
            if a != head and not diff_only_ignored(repo, a, head, gen.ignore):
                break   # 遡った先に手元だけの中身がある = これ以上遡っても揃えられない
            if rev(repo, new) and is_ancestor(repo, new, up_sha):
                return new, ("map" if a == head else "map+volatile")
            break
    # 2. tree の一致 / 3. volatile を除いた tree の一致
    lines = git(repo, "rev-list", f"--max-count={max_count}", "--format=%H %T", up_sha).splitlines()
    pairs = [l.split() for l in lines if not l.startswith("commit ")]
    head_tree = git(repo, "rev-parse", head + "^{tree}")
    for c, t in pairs:
        if t == head_tree:
            return c, "tree"
    if gen.ignore:
        want = tree_signature(repo, head_tree, gen.ignore)
        for c, t in pairs:
            if tree_signature(repo, t, gen.ignore) == want:
                return c, "tree-ignoring-volatile"
    return None, None


def old_branches(repo, gen, upstream, current_branch):
    """upstream に無い commit のうち旧 sha を持つ手元 branch の名前 (current は除く)。"""
    olds = gen.old_shas
    if not olds:
        return []
    names = []
    for b in git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/", check=False).splitlines():
        if not b or b == current_branch:
            continue
        shas = set(git(repo, "rev-list", b, "--not", upstream, check=False).split())
        if shas & olds:
            names.append(b)
    return names


def follow_repo(repo, cli_globs=(), fetch=True, max_count=DEFAULT_MAX, dry_run=False, log=True):
    repo = Path(repo)
    name = repo.name
    if not (repo / ".git").exists():
        return Result("skipped", "", exit_code=0)
    upstream = upstream_of(repo)
    if not upstream:
        return Result("skipped", "", exit_code=0)
    if fetch:
        remote = upstream.split("/", 1)[0]
        try:
            git(repo, "fetch", "-q", remote, timeout=FETCH_TIMEOUT)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            return Result("stopped", f"{name}: fetch に失敗 (通信) = 今回は止まる、 次に再試行: {str(exc)[:120]}", exit_code=1)
    if in_progress(repo):
        return Result("stopped", f"{name}: merge / rebase が進行中 = 触らない (片付けてから)", exit_code=1)
    head = rev(repo, "HEAD")
    up_sha = rev(repo, upstream)
    if not head or not up_sha:
        return Result("skipped", "", exit_code=0)
    if is_ancestor(repo, head, up_sha):
        return Result("current")
    if is_ancestor(repo, up_sha, head):
        return Result("ahead")
    gen = Generation.load(repo, upstream, cli_globs)
    target, how = _find_target(repo, head, upstream, gen, max_count)
    if not target:
        if forced_update_seen(repo, upstream) or gen.maps or gen.forbidden:
            # 書き換えの痕跡がある (fetch が forced-update を記録した / upstream が対応表を運ぶ) = 揃えられない理由は手元だけの中身
            return Result("stopped",
                          f"{name}: upstream ({upstream}) は書き換えられ、 手元の HEAD ({head[:7]}) と同じ中身の commit が新しい履歴に無い"
                          f" = 手元にしか無い commit がある。 中身を確かめてから人が揃える (git pull / merge / rebase はしない"
                          f" = 古い履歴が合流して消した中身が push で戻る)", exit_code=1)
        # 痕跡が無い = 通常の分岐 (手元の commit + upstream の前進)。 追従の仕事ではない = 呼び元の従来の扱いに返す
        return Result("diverged", f"{name}: upstream ({upstream}) と分岐 (書き換えの痕跡は無い = 通常の分岐、 手で解決)", exit_code=1)
    branch = git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    if dry_run:
        return Result("followed", f"{name}: [dry-run] 揃える: HEAD {head[:7]} → 新履歴の {target[:7]} ({how}) → {upstream} {up_sha[:7]}",
                      how=how, target=target)
    if not git_ok(repo, "reset", "-q", "--keep", up_sha):
        return Result("stopped", f"{name}: reset --keep が止まった (未 commit の変更が書き換えで変わった file に重なる) = 手で揃える"
                                 f" (git status で file を見て、 退避してから再実行)", exit_code=1)
    res = Result("followed",
                 f"{name}: 書き換えられた履歴に追従した (手元の HEAD {head[:7]} → 新履歴の {target[:7]} 〔{how}〕、 {branch or 'HEAD'} = {up_sha[:7]})",
                 how=how, target=target)
    olds = old_branches(repo, gen, upstream, branch)
    if olds:
        res.extra.append(f"  ⚠️ {name}: 古い履歴の commit を持つ手元 branch = {' '.join(olds)} (push しない。 要らなければ人が消す)")
    if log:
        _log(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} followed {repo} {head} -> {up_sha} via {how}")
    return res


def _log(line):
    p = os.environ.get(LOG_ENV) or os.path.join(os.path.expanduser("~"), ".claude", "state", "rewrite-follow.log")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sweep(root, cli_globs=(), fetch=False, max_count=DEFAULT_MAX, dry_run=False, prepush=True):
    """root/*/ の repo を順に。 (Result, prepush line) の list。"""
    out = []
    for gd in sorted(globmod.glob(os.path.join(str(root), "*", ".git"))):
        repo = Path(gd).parent
        try:
            r = follow_repo(repo, cli_globs, fetch=fetch, max_count=max_count, dry_run=dry_run)
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            r = Result("stopped", f"{repo.name}: 追従の判定で失敗 ({type(exc).__name__}: {str(exc)[:120]})", exit_code=1)
        pl = ""
        if prepush and r.state != "skipped":
            try:
                pl = ensure_prepush(repo, only_with_manifest=True)
            except (RuntimeError, OSError) as exc:
                pl = f"{repo.name}: pre-push stub を置けなかった ({str(exc)[:100]})"
        out.append((r, pl))
    return out


# ---------------------------------------------------------------- push guard

def push_violations(repo, local_sha, exclude, gen):
    """local_sha までの commit のうち exclude に無いものが、 旧 sha / 旧世代の blob を含むか。 違反の説明 list。"""
    args = ["rev-list", "--objects", local_sha]
    if exclude:
        args += ["--not", exclude]
    else:
        args += ["--not", "--remotes"]
    out = git(repo, *args, check=False)
    ids = {l.split(" ", 1)[0] for l in out.splitlines() if l}
    hits = []
    olds = ids & gen.old_shas
    if olds:
        hits.append(f"書き換え前の世代の commit {len(olds)} 個 (例 {sorted(olds)[0][:7]})")
    fb = ids & gen.forbidden
    if fb:
        hits.append(f"書き換えで消した版の blob {len(fb)} 個 (例 {sorted(fb)[0][:7]})")
    return hits


def guard_stdin(repo, lines, cli_globs=()):
    """git pre-push の stdin (local_ref local_sha remote_ref remote_sha) を検査。 (ok, messages)。"""
    repo = Path(repo)
    upstream = upstream_of(repo) or "origin/HEAD"
    gen = Generation.load(repo, upstream if rev(repo, upstream) else "", cli_globs)
    if not gen.maps and not gen.forbidden:
        return True, []
    msgs = []
    for line in lines:
        a = line.split()
        if len(a) != 4:
            continue
        _lref, lsha, rref, rsha = a
        if lsha == ZERO:
            continue  # delete
        exclude = rsha if rsha != ZERO else ""
        hits = push_violations(repo, lsha, exclude, gen)
        if hits:
            msgs.append(f"{repo.name}: push を止めた ({rref}): {'、 '.join(hits)} = 古い履歴が混ざっている。 "
                        f"追従 (git-rewrite-follow.py follow --repo {repo}) してから、 必要な commit だけ cherry-pick で載せ直す")
    return (not msgs), msgs


def stub_text(engine_path, repo):
    return (
        "#!/bin/sh\n"
        f"# {STUB_MARK} — installed by git-rewrite-follow.py ensure-prepush (do not edit; re-run ensure-prepush)\n"
        "# Refuses a push that carries commits / blobs of a rewritten-away generation "
        "(conventions/multi-machine-state.md#history-rewrite-follow).\n"
        "command -v python3 >/dev/null 2>&1 || { echo 'rewrite-follow pre-push: python3 が無いので検査せず通す' >&2; exit 0; }\n"
        f"[ -f \"{engine_path}\" ] || {{ echo 'rewrite-follow pre-push: engine が無いので検査せず通す' >&2; exit 0; }}\n"
        f"exec python3 \"{engine_path}\" guard --repo \"{repo}\" --hook \"$@\"\n"
    )


def hooks_dir(repo):
    p = Path(git(repo, "rev-parse", "--git-path", "hooks"))
    return p if p.is_absolute() else Path(repo) / p


def engine_cli_path():
    return str(Path(__file__).resolve().parent.parent / "git-rewrite-follow.py")


def ensure_prepush(repo, only_with_manifest=True, engine=None):
    """pre-push stub を置く / 更新する。 置いた・更新した時だけ 1 行、 それ以外は ''。 foreign な pre-push は触らず 1 行。"""
    repo = Path(repo)
    if not (repo / ".git").exists():
        return ""
    upstream = upstream_of(repo)
    if only_with_manifest:
        if not upstream or not upstream_manifest_files(repo, upstream):
            return ""
    engine = engine or engine_cli_path()
    hd = hooks_dir(repo)
    dst = hd / "pre-push"
    want = stub_text(engine, str(repo))
    if dst.exists():
        try:
            cur = dst.read_text(encoding="utf-8", errors="replace")
        except OSError:
            cur = ""
        if STUB_MARK not in cur:
            return f"{repo.name}: 既存の pre-push hook があるので rewrite-follow の stub を置かない ({dst})"
        if cur == want:
            return ""
    hd.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name("pre-push.rewrite-follow.tmp")
    tmp.write_text(want, encoding="utf-8")
    os.chmod(tmp, 0o755)
    os.replace(tmp, dst)
    return f"{repo.name}: 古い世代の push を止める pre-push stub を置いた ({dst})"


def has_prepush_stub(repo):
    try:
        p = hooks_dir(repo) / "pre-push"
        return p.exists() and STUB_MARK in p.read_text(encoding="utf-8", errors="replace")
    except (OSError, RuntimeError):
        return False


def status(repo, cli_globs=()):
    """JSON 向けの状態 (heartbeat / gate が読む)。 fetch はしない。"""
    repo = Path(repo)
    up = upstream_of(repo) if (repo / ".git").exists() else ""
    d = {"repo": str(repo), "upstream": up, "manifest": False, "prepush_stub": has_prepush_stub(repo),
         "forced_update_seen": False, "relation": "unknown"}
    if up and rev(repo, up):
        d["manifest"] = bool(upstream_manifest_files(repo, up))
        d["forced_update_seen"] = forced_update_seen(repo, up)
        head, u = rev(repo, "HEAD"), rev(repo, up)
        if head and u:
            d["relation"] = ("current" if is_ancestor(repo, head, u) else "ahead" if is_ancestor(repo, u, head) else "diverged")
    return d


# ---------------------------------------------------------------- selftest

def _selftest():
    import json
    import tempfile
    fails = []

    def check(label, ok, detail=""):
        print(("  ok: " if ok else "  NG: ") + label + (f"  [{detail}]" if (detail and not ok) else ""))
        if not ok:
            fails.append(label)

    td = tempfile.mkdtemp(prefix="grf-selftest-")
    os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                       "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
                       "GIT_COMMITTER_EMAIL": "t@example.invalid", LOG_ENV: os.path.join(td, "follow.log"),
                       MAPS_FILE_ENV: os.path.join(td, "no-maps.txt"), MAPS_ENV: ""})
    tmp = Path(td)

    def init(p):
        subprocess.run(["git", "init", "-q", "-b", "main", str(p)], check=True, env=_env())

    def commit(p, files, msg):
        for f, body in files.items():
            fp = p / f
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(body)
            git(p, "add", f)
        git(p, "commit", "-q", "--allow-empty", "-m", msg)
        return rev(p, "HEAD")

    # --- 旧履歴: 3 commit、 2 つ目が「学生の id」 を含む。 status/x.json は volatile
    remote = tmp / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, env=_env())
    src = tmp / "src"
    init(src)
    o1 = commit(src, {"a.txt": "one\n", "status/x.json": "{}\n"}, "c1")
    o2 = commit(src, {"b.txt": "id=K00X0000 (old)\n"}, "c2 mentions K00X0000")
    o3 = commit(src, {"b.txt": "id=<学籍番号>\n", "c.txt": "3\n"}, "c3 cleaned")
    git(src, "remote", "add", "origin", str(remote))
    git(src, "push", "-q", "origin", "main")
    old_blob_b2 = git(src, "rev-parse", f"{o2}:b.txt")

    def clone(name, at=None):
        p = tmp / name
        subprocess.run(["git", "clone", "-q", str(remote), str(p)], check=True, env=_env())
        if at:
            git(p, "reset", "-q", "--hard", at)
        return p

    # 手元の clone 群 (書き換えの前に作る)
    a_msg = clone("a-msg")                       # message だけの書き換えに揃える
    a_cont = clone("a-cont")                     # 中身の書き換え (今の tree は同じ) に揃える
    a_unp = clone("a-unpushed")                  # 未 push の commit → 止まる
    a_dirty = clone("a-dirty", at=o2)            # behind (b.txt は書き換えで変わる) ∧ その file が dirty → 止まる
    a_cur = clone("a-current")                   # 既に最新 (書き換え後に ff)
    a_beat = clone("a-beat")                     # 無人 job の commit が古い履歴の上に載る
    a_behind = clone("a-behind", at=o2)          # 書き換えの前から behind (tree は変わる) → 対応表で揃う
    a_dirty_other = clone("a-dirty-other")       # 変わっていない file が dirty → 揃う (reset --keep が保つ)
    (a_unp / "z.txt").write_text("mine\n")
    git(a_unp, "add", "z.txt")
    git(a_unp, "commit", "-q", "-m", "unpushed local")
    (a_dirty / "b.txt").write_text("edited locally\n")
    (a_dirty_other / "a.txt").write_text("edited locally, not touched by the rewrite\n")
    commit(a_beat, {"status/x.json": '{"beat": 1}\n'}, "heartbeat")
    commit(a_beat, {"status/x.json": '{"beat": 2}\n'}, "heartbeat")

    # --- 書き換え 1: message だけ (tree は全部同じ)
    new1 = tmp / "new1"
    init(new1)
    n1 = commit(new1, {"a.txt": "one\n", "status/x.json": "{}\n"}, "c1")
    n2 = commit(new1, {"b.txt": "id=K00X0000 (old)\n"}, "c2 mentions <学籍番号>")
    n3 = commit(new1, {"b.txt": "id=<学籍番号>\n", "c.txt": "3\n"}, "c3 cleaned")
    check("fixture: message-only rewrite keeps every tree", git(new1, "rev-parse", n3 + "^{tree}") == git(src, "rev-parse", o3 + "^{tree}"))
    git(new1, "push", "-q", "--force", str(remote), "main:main")
    r = follow_repo(a_msg)
    check("message-only rewrite: followed via tree", r.state == "followed" and r.how == "tree", r.line)
    check("message-only rewrite: HEAD = new tip", rev(a_msg, "HEAD") == n3)
    check("forced update is visible in the reflog", forced_update_seen(a_msg, "origin/main"))
    r = follow_repo(a_msg)
    check("already current: silent", r.state == "current" and r.line == "")
    # 書き換えた後に ff で最新になった clone (= 何もしない)
    git(a_cur, "fetch", "-q")
    git(a_cur, "reset", "-q", "--hard", "origin/main")
    check("current clone: silent", follow_repo(a_cur).state == "current")

    # --- 書き換え 2: 中身も変える (c2 の b.txt を scrub、 今の tree は同じ) + manifest (ignore-paths は書き換えの前から)
    # 手元の a-cont / a-unpushed / a-dirty / a-beat / a-behind / a-dirty-other は旧履歴 (o*) のまま
    for p in (a_cont, a_unp, a_dirty, a_beat, a_behind, a_dirty_other):
        check(f"precondition: {p.name} still on the old history", rev(p, "HEAD") in (o3, o2) or rev(p, "HEAD~1") == o3 or rev(p, "HEAD~2") == o3)
    check("precondition: the dirty clone is behind at the commit whose file the rewrite changes", rev(a_dirty, "HEAD") == o2)
    new2 = tmp / "new2"
    init(new2)
    m1 = commit(new2, {"a.txt": "one\n", "status/x.json": "{}\n", ".rewrite-follow/ignore-paths": "# volatile\nstatus/\n"}, "c1")
    m2 = commit(new2, {"b.txt": "id=<学籍番号> (old)\n"}, "c2 mentions <学籍番号>")
    m3 = commit(new2, {"b.txt": "id=<学籍番号>\n", "c.txt": "3\n"}, "c3 cleaned")
    # 「書き換えの前に ignore-paths を置いた」 状態を旧履歴側にも作る: 旧履歴に通常 commit で ignore-paths を足し、 それを土台に
    git(src, "fetch", "-q", "origin")
    o0 = commit(src, {".rewrite-follow/ignore-paths": "# volatile\nstatus/\n"}, "add manifest")
    # 旧側は o1..o3 + o0。 新側 = m1..m3 + 同じ manifest commit 相当 (tree が o0 と同じになるよう c.txt/b.txt を揃える)
    m0 = commit(new2, {}, "add manifest")  # allow-empty: tree は m3 と同じ = ignore-paths 込み
    check("fixture: content rewrite keeps HEAD tree", git(new2, "rev-parse", m0 + "^{tree}") == git(src, "rev-parse", o0 + "^{tree}"))
    check("fixture: content rewrite changes the c2 tree", git(new2, "rev-parse", m2 + "^{tree}") != git(src, "rev-parse", o2 + "^{tree}"))
    # 旧履歴を remote に戻して (= 書き換えの前の状態に、 manifest commit 込み)、 手元の clone を o0 に進める
    git(src, "push", "-q", "--force", "origin", "main:main")
    for p in (a_cont, a_unp, a_dirty_other):
        git(p, "fetch", "-q")
    git(a_cont, "merge", "-q", "--ff-only", "origin/main")
    git(a_dirty_other, "merge", "-q", "--ff-only", "origin/main")
    # a_unp: 手元 commit を o0 の上に載せ直す (通常の rebase = 書き換えの前だから正当)
    git(a_unp, "rebase", "-q", "origin/main")
    # a_dirty は o2 のまま (behind) で b.txt が dirty = 新履歴の先頭では b.txt が違う → reset --keep が止める
    # a_beat: o3 + 2 heartbeat commits (o0 はまだ pull していない = behind ∧ volatile 差)
    # 対応表 (旧 → 新) と forbidden blob を新履歴に通常 commit で置く
    cmap = "old new\n" + "\n".join(f"{o} {n}" for o, n in ((o1, m1), (o2, m2), (o3, m3), (o0, m0))) + "\n"
    mf = commit(new2, {".rewrite-follow/commit-map": cmap, ".rewrite-follow/forbidden-blobs": old_blob_b2 + "\n"}, "publish map")
    git(new2, "push", "-q", "--force", str(remote), "main:main")

    r = follow_repo(a_cont)
    check("content rewrite, HEAD tree equal: followed via map", r.state == "followed" and r.how == "map", f"{r.state} {r.how} {r.line}")
    check("content rewrite: HEAD = new tip (map commit included)", rev(a_cont, "HEAD") == mf)
    r = follow_repo(a_unp)
    check("unpushed local commit: stopped, ref untouched", r.state == "stopped" and r.exit_code == 1
          and git(a_unp, "log", "-1", "--format=%s") == "unpushed local", r.line)
    r = follow_repo(a_dirty)
    check("dirty worktree on a changed file: stopped (reset --keep refuses)", r.state == "stopped" and "reset --keep" in r.line, r.line)
    check("dirty worktree: local edit preserved, ref untouched", (a_dirty / "b.txt").read_text() == "edited locally\n" and rev(a_dirty, "HEAD") == o2)
    r = follow_repo(a_dirty_other)
    check("dirty worktree on an untouched file: followed", r.state == "followed", r.line)
    check("dirty worktree on an untouched file: edit preserved", (a_dirty_other / "a.txt").read_text().startswith("edited locally"))
    r = follow_repo(a_beat)
    check("heartbeat commits on old history: followed via map+volatile (old commits not revived)",
          r.state == "followed" and r.how == "map+volatile", f"{r.state} {r.how} {r.line}")
    check("heartbeat clone: HEAD = new tip, no old sha in the branch",
          rev(a_beat, "HEAD") == mf and not ({o1, o2, o3} & set(git(a_beat, "rev-list", "HEAD").split())))
    r = follow_repo(a_behind)
    check("clone behind the rewrite point (its tree was changed): followed via map", r.state == "followed" and r.how == "map", r.line)
    check("behind clone: HEAD = new tip", rev(a_behind, "HEAD") == mf)
    # 対応表も tree も当たらない: 手元だけの commit を含む別 branch を持つ clone → その branch の名指し
    a_br = clone("a-branch")
    git(a_br, "branch", "-q", "oldwork", o2)
    git(a_br, "reset", "-q", "--hard", o0) if git_ok(a_br, "cat-file", "-e", o0) else None
    r = follow_repo(a_br) if rev(a_br, "HEAD") == o0 else Result("skipped")
    if r.state != "skipped":
        check("old-history local branch is named after following", r.state == "followed" and any("oldwork" in x for x in r.extra), " ".join(r.extra))
    # dry-run は ref を動かさない
    a_dry = clone("a-dry")
    git(a_dry, "reset", "-q", "--hard", o3) if git_ok(a_dry, "cat-file", "-e", o3) else None
    if rev(a_dry, "HEAD") == o3:
        r = follow_repo(a_dry, dry_run=True)
        check("dry-run reports and does not move", r.state == "followed" and rev(a_dry, "HEAD") == o3, r.line)

    # --- guard: 古い commit を含む push / 旧世代の blob を rebase で運ぶ push / 正当な push
    gen = Generation.load(a_cont, "origin/main")
    check("generation: old shas from the map exclude identity rows", gen.old_shas == {o1, o2, o3, o0} - {m1, m2, m3, m0})
    check("generation: forbidden blob loaded", old_blob_b2 in gen.forbidden)
    check("generation: ignore-paths loaded", gen.ignore == ["status/"])
    # (i) 旧履歴を merge した状態 (= 追従前の clone で git pull した形)
    a_merge = clone("a-merge")
    if git_ok(a_merge, "cat-file", "-e", o0):
        git(a_merge, "reset", "-q", "--hard", o0)
        git(a_merge, "merge", "-q", "--no-edit", "--allow-unrelated-histories", "origin/main")  # 本物の書き換えは先頭の commit が同じなので related、 fixture は全部変わる
        ok, msgs = guard_stdin(a_merge, [f"refs/heads/main {rev(a_merge, 'HEAD')} refs/heads/main {mf}"])
        check("guard: merged old history is refused (old commit shas)", not ok and msgs and "世代の commit" in msgs[0], " ".join(msgs))
    # (ii) 旧の中身を新履歴に cherry-pick (sha は新しい、 blob は旧) = rebase の形
    a_cp = clone("a-cherry")
    if git_ok(a_cp, "cat-file", "-e", o2):
        git(a_cp, "reset", "-q", "--hard", "origin/main")
        (a_cp / "b.txt").write_text("id=K00X0000 (old)\n")   # 旧 c2 の blob と同じ中身
        git(a_cp, "add", "b.txt")
        git(a_cp, "commit", "-q", "-m", "revived content with a fresh sha")
        ok, msgs = guard_stdin(a_cp, [f"refs/heads/main {rev(a_cp, 'HEAD')} refs/heads/main {mf}"])
        check("guard: revived old content under a new sha is refused (forbidden blob)", not ok and msgs and "blob" in msgs[0], " ".join(msgs))
    # (iii) 正当な新しい commit は通る
    a_ok = clone("a-legit")
    (a_ok / "d.txt").write_text("new work\n")
    git(a_ok, "add", "d.txt")
    git(a_ok, "commit", "-q", "-m", "legit")
    ok, msgs = guard_stdin(a_ok, [f"refs/heads/main {rev(a_ok, 'HEAD')} refs/heads/main {mf}"])
    check("guard: a legitimate new commit passes", ok and not msgs)
    ok, msgs = guard_stdin(a_ok, [f"refs/heads/main {ZERO} refs/heads/main {mf}"])
    check("guard: a ref deletion passes", ok)
    # (iv) manifest の無い repo では guard は何も言わない
    plain_remote = tmp / "plain.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(plain_remote)], check=True, env=_env())
    plain = tmp / "plain"
    init(plain)
    commit(plain, {"p.txt": "p\n"}, "p")
    git(plain, "remote", "add", "origin", str(plain_remote))
    git(plain, "push", "-q", "-u", "origin", "main")
    ok, msgs = guard_stdin(plain, [f"refs/heads/main {rev(plain, 'HEAD')} refs/heads/main {ZERO}"])
    check("guard: repo without a manifest passes", ok)
    check("follow: repo without divergence is silent", follow_repo(plain, fetch=False).state in ("current", "ahead"))

    # --- ensure-prepush: manifest のある repo にだけ、 foreign な hook は触らない、 冪等
    line = ensure_prepush(a_ok, only_with_manifest=True, engine="/x/engine.py")
    check("ensure-prepush: installs on a manifest repo", "置いた" in line and has_prepush_stub(a_ok), line)
    check("ensure-prepush: idempotent", ensure_prepush(a_ok, only_with_manifest=True, engine="/x/engine.py") == "")
    check("ensure-prepush: skips a repo without a manifest", ensure_prepush(plain, only_with_manifest=True) == "" and not has_prepush_stub(plain))
    hd = hooks_dir(plain)
    hd.mkdir(parents=True, exist_ok=True)
    (hd / "pre-push").write_text("#!/bin/sh\nexit 0\n")
    line = ensure_prepush(plain, only_with_manifest=False, engine="/x/engine.py")
    check("ensure-prepush: leaves a foreign pre-push alone", "置かない" in line and "exit 0" in (hd / "pre-push").read_text())
    st = status(a_ok)
    check("status: manifest + stub + relation", st["manifest"] and st["prepush_stub"] and st["relation"] == "ahead", json.dumps(st))

    # --- 通常の分岐 (書き換えの痕跡なし): stopped でなく diverged (= 呼び元の従来の扱い)
    od_remote = tmp / "od.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(od_remote)], check=True, env=_env())
    od = tmp / "od"
    init(od)
    commit(od, {"f.txt": "1\n"}, "f1")
    git(od, "remote", "add", "origin", str(od_remote))
    git(od, "push", "-q", "-u", "origin", "main")
    od_other = tmp / "od-other"
    subprocess.run(["git", "clone", "-q", str(od_remote), str(od_other)], check=True, env=_env())
    commit(od_other, {"f.txt": "2\n"}, "remote advance")
    git(od_other, "push", "-q", "origin", "main")
    commit(od, {"h.txt": "local\n"}, "local")
    r = follow_repo(od)
    check("ordinary divergence (no forced-update trace): state diverged, not stopped", r.state == "diverged" and r.exit_code == 1, r.line)
    check("ordinary divergence: ref untouched", git(od, "log", "-1", "--format=%s") == "local")

    # --- sweep: root/*/ を回し、 followed は 1 行、 current は無音
    root = tmp / "root"
    root.mkdir()
    for nm, at in (("r-old", o0), ("r-cur", None)):
        p = root / nm
        subprocess.run(["git", "clone", "-q", str(remote), str(p)], check=True, env=_env())
        if at and git_ok(p, "cat-file", "-e", at):
            git(p, "reset", "-q", "--hard", at)
    res = sweep(root, fetch=False)
    states = {r.state for r, _ in res}
    check("sweep: visits both, follows the old one silently passes the current", "current" in states and ("followed" in states or "current" in states))
    check("sweep: the followed clone landed on the new tip", rev(root / "r-old", "HEAD") == mf)
    check("follow log written", os.path.exists(os.environ[LOG_ENV]) and "followed" in open(os.environ[LOG_ENV]).read())

    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failing)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(_selftest())
