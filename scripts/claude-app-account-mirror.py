#!/usr/bin/env python3
"""Claude desktop app の session 一覧を account をまたいで見えるようにする: 別の account の session を、 app 公式のインポートと同じ形の「写し」 にして今の account の一覧にも置く (既定 dry-run、 --apply で書く、 常駐 = install-claude-app-account-mirror.sh)。

背景: desktop app (Code タブ) の session 一覧は Claude account ごとの dir
(`<userData>/claude-code-sessions/<accountUuid>/<orgUuid>/local_<uuid>.json`、 1 session 1 file) から読まれ、
今の account の分しか出ない。 本 script は、 ある account の session を別の account の dir に「インポートした
session」 として写す。 写しの中身は app の公式インポート (registerExternalSession → finishRegisterExternalSession)
が disk に書くものと同じ = 最小の record と、 同じ変換をした会話記録
(`<その dir>/imported-staging/<新しい cli id>.jsonl`) の組。 写しを開くと app が「インポートしたセッションを
再開しますか？」 と聞き、 会話記録を `<configDir>/projects/<cwd の slug>/` へ移す = 写しは元と別の会話記録を持つ
独立した session になる (両 account で同時に開いても元は壊れない)。

規則 (正本 = conventions/multi-account-machine-surface.md#session-list-per-account):
  - 書くのは「今 app が表示していない account」 の dir だけ (`<userData>/config.json` の lastKnownAccountUuid。
    app が起動していなければ全部)。 書く直前に毎回見直す (一覧は account 切替・再起動の時にしか読み直されない)。
  - 書き込みは一時 file → rename (一時 file は `local_*.json` に当たらない名前)。 会話記録を先、 record を後。
    消すときは record を先。 台帳 (`<state>/ledger.json`) は書く前に「作成中」 を記録する (途中で落ちても拾える)。
  - 写す範囲 = アーカイブしていない session + 直近 N 日 (既定 14) に動いた session のうち、 会話記録が残っていて
    cwd が在るもの。 TCC で守られた場所 (Desktop / Documents / Downloads / CloudStorage / /Volumes 等) の cwd は
    stat しない (= 在るとみなす。 launchd から stat すると許可の確認が出るか失敗し、 手で回した時と判断が割れる)。
  - 未開封 (resumeConfirmed が無く staged file が在る) の写しは、 元が進めば同じ id のまま差し替え (会話記録は
    前回の続きだけ足す)、 元が消えた/範囲外になれば消す。 開いた写しは二度と触らない。 開いた写しの元が後で
    進めば、 新しい写しを 1 つ足す。
  - インポートで未開封の session (自分の写しを含む) は写さない (ping-pong 防止)。 開いた写しは普通の session
    なので、 開いた後に動いていれば逆向きにも写す。
  - 本人が消した写しは作り直さない (開いた後に消したものも = その元はその account にもう写さない。 戻すなら台帳の
    該当行を消す)。 本人が変えた題名・アーカイブは差し替えで上書きしない。
  - 題名の頭に元 account の印 (`⇄<email の local-part> `。 引けない account は uuid の先頭 8 桁)。 既に印のある
    題名は印を付け替える。
  - app の版 (Info.plist の CFBundleShortVersionString) が変わったら、 本体 (app.asar) にインポートの前提
    (record の形・会話記録の変換・再開時の移動・imported-staging・保存 dir の形) が残っているかを確かめる
    (版ごとに 1 回、 結果は `<state>/app-check.json`)。 1 つでも欠けたら写さない (状態に出る)。

使い方:
  claude-app-account-mirror.py                    計画だけ出す (dry-run、 何も書かない)
  claude-app-account-mirror.py --apply            写す (launchd からはこれ + --quiet)
  claude-app-account-mirror.py --undo [--apply]   未開封の写しを全部取り消し、 止めるスイッチを置く
  claude-app-account-mirror.py --status           常駐・直近の実行・app の点検・台帳・次の実行の見込み
  claude-app-account-mirror.py --notice           session 開始用: 未導入・停止・失敗のときだけ 1 行 (他は無音)
  claude-app-account-mirror.py --app-check        app 本体の点検をやり直して結果を出す
  claude-app-account-mirror.py --watch-paths      launchd の WatchPaths にする dir を 1 行ずつ
  claude-app-account-mirror.py --print-plist      launchd の plist (install script が使う)
  claude-app-account-mirror.py --selftest

常駐 (launchd、 本人が terminal で入れる): bash install-claude-app-account-mirror.sh [--status | --uninstall]。
⚠️ Claude (auto mode) から --apply / --undo --apply / install を実行しない: classifier が「session 記録の改ざん」
として止める (実測)。 dry-run・--status・--notice は読むだけ。

止める: touch ~/.claude/account-mirror.off (消せば再開)。 ⚠️ desktop の configDir は ~/.claude 固定
(= 環境変数 CLAUDE_CONFIG_DIR は見ない。 desktop app は Finder から起動され、 その値を持たない)。

範囲外: スマホから新しく始めた session (desktop の一覧に載らない) / マシンをまたぐこと。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover (Windows)
    fcntl = None

LABEL = "com.claude-config.account-mirror"
MARK = "\u21c4"                      # ⇄
DEFAULT_DAYS = 14
MAX_LINE = 16 * 1024 * 1024          # app の 1 行の上限 (16 MiB)
IMPORTED_FROM = "local-1p-code"      # app の既定 (code1p)
STAGING = "imported-staging"
SLUG_MAX = 200
TMP_PREFIX = ".account-mirror-"      # record の一時 file (local_*.json に当たらない)
CHECKER_VERSION = 1                  # 下の APP_CHECKS を変えたら上げる (= cache を捨てる)
HEAD_BYTES = 65536
STALE_MS = 24 * 3600 * 1000
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MARK_RE = re.compile("^(?:" + MARK + r"\S*(?:\s+|$))+")
APP_PROC_RE = re.compile(r"/Claude\.app/Contents/MacOS/Claude$")
PROTECTED_REL = ("Desktop", "Documents", "Downloads", "Library/CloudStorage", "Library/Mobile Documents",
                 "Library/Containers", "Library/Group Containers", "Pictures", "Movies", "Music")
GONE_REASONS = {"source-deleted", "out-of-range", "cwd-missing", "no-transcript", "not-local", "cwd-too-long",
                "no-cli"}

# app 本体 (main process の JS) に残っているべき前提。 名前は minify で変わるので識別子は \w で受ける。
_ID = rb"[\w$]+"
APP_CHECKS = [
    ("インポートの record の形", rb"\{sessionId:" + _ID + rb",cliSessionId:" + _ID + rb"\.cliSessionId,cwd:" + _ID
     + rb",originCwd:" + _ID + rb",title:" + _ID + rb"\.title,createdAt:" + _ID + rb",lastActivityAt:" + _ID
     + rb",indexedAt:" + _ID + rb",isArchived:" + _ID + rb"\.isArchived===!0,importedFrom:" + _ID
     + rb"\.importedFrom\?\?[\w$.]+\.code1p,stagedTranscriptPath:" + _ID + rb","),
    ("会話記録の変換 (sessionId と toolUseResult.agentId を外す)",
     rb"let\{sessionId:" + _ID + rb",\.\.\.(" + _ID + rb")\}=" + _ID + rb",(" + _ID + rb")=\1\.toolUseResult;"
     rb"if\(typeof \2==\"object\"&&\2&&\"agentId\"in \2\)\{let\{agentId:" + _ID + rb",\.\.\.(" + _ID + rb")\}=\2;"
     rb"\1\.toolUseResult=\3\}return \1\}"),
    ("cwd の無い行を写さない", rb"function " + _ID + rb"\((" + _ID + rb")\)\{let (" + _ID + rb")=\1\?\.cwd;"
     rb"return typeof \2==\"string\"&&\2\.length>0\?\2:void 0\}"),
    ("1 行の上限 16 MiB", rb"=16777216[;,]"),
    ("再開の確認 (confirmImportedSessionResume)", rb"async confirmImportedSessionResume\(" + _ID + rb"\)\{"),
    ("imported-staging", rb"\"imported-staging\""),
    ("staging は保存 dir の直下だけ", rb"rejected a staging file outside the private staging dir"),
    ("importedFrom の既定 local-1p-code", rb"code1p:\"local-1p-code\""),
    ("一覧は local_*.json を読む", rb"startsWith\(\"local_\"\)&&" + _ID + rb"\.endsWith\(\"\.json\"\)"),
    ("cwd の slug (英数字以外を -)", rb"\.replace\(/\[\^a-zA-Z0-9\]/g,\"-\"\)"),
    ("保存 dir = <userData>/<base>/<account>/<org>", rb"\(0," + _ID + rb"\.join\)\(this\.userDataPath,this\.baseDir,"
     rb"this\.currentAccountId,this\.currentOrgId\)"),
    ("claude-code-sessions", rb"\"claude-code-sessions\""),
]
CONFIRM_BODY = (b'"projects"', b".cliSessionId}.jsonl", b"resumeConfirmed=!0", b"stagedTranscriptPath")


# ---- 小道具 ---------------------------------------------------------------------------------

def now_ms() -> int:
    return int(time.time() * 1000)


def read_json(path: str):
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def dump_compact(obj) -> bytes:
    """JSON.stringify と同じ詰めた形 (非 ASCII はそのまま。 孤立 surrogate を含むときだけ \\u で逃がす)。"""
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except UnicodeEncodeError:
        return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def write_atomic(path: str, data: bytes, before_replace=None, mode: int = 0o600) -> bool:
    """同じ dir の一時 file に書いて rename。 before_replace() が False なら書かずに False。"""
    tmp = os.path.join(os.path.dirname(path), f"{TMP_PREFIX}{uuid.uuid4().hex}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if before_replace is not None and not before_replace():
            os.unlink(tmp)
            return False
        os.replace(tmp, path)
        return True
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _base36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


def cli_slug(cwd: str) -> str:
    """app の cliProjectDirSlug(cwd, "host") と同じ: NFC → UTF-16 の code unit ごとに英数字以外を "-"、 200 超は切って hash。"""
    n = unicodedata.normalize("NFC", cwd)
    units = n.encode("utf-16-le", "surrogatepass")
    cus = [units[i] | (units[i + 1] << 8) for i in range(0, len(units), 2)]
    r = "".join(chr(c) if (48 <= c <= 57 or 65 <= c <= 90 or 97 <= c <= 122) else "-" for c in cus)
    if len(r) <= SLUG_MAX:
        return r
    h = 0
    for c in cus:
        h = ((h << 5) - h + c) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return f"{r[:SLUG_MAX]}-{_base36(abs(h))}"


def mirror_title(title, label: str) -> str:
    base = MARK_RE.sub("", title if isinstance(title, str) else "").strip() or "session"
    return f"{MARK}{label} {base}"


def human_ms(ms) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ms) / 1000))
    except (TypeError, ValueError, OverflowError, OSError):
        return "?"


def short_path(p: str, home: str) -> str:
    return "~" + p[len(home):] if p == home or p.startswith(home + "/") else p


# ---- 会話記録の変換 (app の import と同じ) ------------------------------------------------------

def transform_line(raw: bytes):
    """1 行を app の import と同じに変換する。 写さない行 (JSON でない / cwd が無い) は None。"""
    try:
        obj = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    cwd = obj.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    obj.pop("sessionId", None)
    tur = obj.get("toolUseResult")
    if isinstance(tur, dict) and "agentId" in tur:
        tur = dict(tur)
        tur.pop("agentId")
        obj["toolUseResult"] = tur
    return dump_compact(obj) + b"\n"


def iter_complete_lines(f, limit: int):
    """(行 or None, 行末の offset)。 改行で終わる行だけ (書きかけの最後の行は読まない)。 limit を超える行は None。"""
    while True:
        line = f.readline(limit + 1)
        if not line:
            return
        if not line.endswith(b"\n"):
            if len(line) <= limit:
                return  # EOF の書きかけ
            while True:  # 長すぎる行は改行まで読み捨てる
                chunk = f.readline(1 << 20)
                if not chunk:
                    return
                if chunk.endswith(b"\n"):
                    break
            yield None, f.tell()
            continue
        yield line, f.tell()


def clone_file(src: str, dst: str) -> bool:
    """APFS の clonefile (中身を複写しない写し)。 使えなければ False (呼ぶ側が普通に写す)。"""
    if sys.platform != "darwin" or os.environ.get("ACCOUNT_MIRROR_NO_CLONE"):
        return False
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.clonefile
        fn.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32)
        return fn(os.fsencode(src), os.fsencode(dst), 0) == 0
    except (OSError, AttributeError):
        return False


def stage_transcript(src: str, tmp: str, start: int = 0, base: str | None = None, limit: int = MAX_LINE):
    """src の start 以降の完全な行を変換して tmp に書く (base があれば先にその中身をそのまま写す)。
    返り値 = (src の読んだ位置, tmp の大きさ)。"""
    if base and clone_file(base, tmp):
        fd = os.open(tmp, os.O_WRONLY | os.O_APPEND)
    else:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        if base:
            with open(base, "rb") as b, open(fd, "wb", closefd=False) as o:
                shutil.copyfileobj(b, o, 1 << 20)
    with os.fdopen(fd, "ab") as out:
        consumed = start
        with open(src, "rb") as f:
            f.seek(start)
            for line, end in iter_complete_lines(f, limit):
                consumed = end
                if line is None:
                    continue
                t = transform_line(line)
                if t is not None:
                    out.write(t)
        out.flush()
        os.fsync(out.fileno())
        return consumed, out.tell()


def head_hash(path: str, n: int) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read(min(n, HEAD_BYTES))).hexdigest()


# ---- app 本体の点検 ------------------------------------------------------------------------------

def app_version(app: str):
    try:
        with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
            v = plistlib.load(f).get("CFBundleShortVersionString")
        return v if isinstance(v, str) else None
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None


def _asar_js(asar: str):
    with open(asar, "rb") as f:
        head = f.read(16)
        size = struct.unpack("<I", head[4:8])[0]
        strlen = struct.unpack("<I", head[12:16])[0]
        header = json.loads(f.read(strlen))
        base = 8 + size

        def walk(node, prefix):
            for name, child in (node.get("files") or {}).items():
                p = f"{prefix}/{name}"
                if "files" in child:
                    yield from walk(child, p)
                elif p.endswith(".js") and not child.get("unpacked"):
                    f.seek(base + int(child["offset"]))
                    yield p, f.read(int(child["size"]))
        yield from walk(header, "")


def run_app_check(app: str) -> dict:
    ver = app_version(app)
    res = {"version": ver, "checker": CHECKER_VERSION, "checked_at": now_ms(), "ok": False, "missing": []}
    if ver is None:
        res["missing"] = ["app が見つからない (Info.plist)"]
        return res
    found = set()
    confirm_ok = False
    try:
        for _name, data in _asar_js(os.path.join(app, "Contents", "Resources", "app.asar")):
            for label, pat in APP_CHECKS:
                if label not in found and re.search(pat, data):
                    found.add(label)
            i = data.find(b"async confirmImportedSessionResume(")
            if i >= 0 and all(t in data[i:i + 1600] for t in CONFIRM_BODY):
                confirm_ok = True
    except (OSError, ValueError, struct.error, KeyError) as e:
        res["missing"] = [f"app.asar を読めない ({type(e).__name__})"]
        return res
    missing = [label for label, _ in APP_CHECKS if label not in found]
    if not confirm_ok:
        missing.append("再開の確認が会話記録を projects/ へ移す")
    res["missing"] = missing
    res["ok"] = not missing
    return res


def app_check(paths, save: bool, force: bool = False) -> dict:
    ver = app_version(paths.app)
    cache = None
    with contextlib.suppress(OSError, ValueError):
        cache = read_json(paths.app_cache)
    if (not force and isinstance(cache, dict) and cache.get("version") == ver
            and cache.get("checker") == CHECKER_VERSION and ver is not None):
        return cache
    res = run_app_check(paths.app)
    if save:
        os.makedirs(paths.state_dir, exist_ok=True)
        write_atomic(paths.app_cache, dump_compact(res))
    return res


# ---- 場所・account・record ---------------------------------------------------------------------

class Paths:
    def __init__(self, a):
        self.home = os.path.abspath(os.path.expanduser(a.home or "~"))
        self.user_data = a.user_data or os.path.join(self.home, "Library", "Application Support", "Claude")
        self.sessions_root = os.path.join(self.user_data, "claude-code-sessions")
        self.config_json = os.path.join(self.user_data, "config.json")
        self.config_dir = a.desktop_config_dir or os.path.join(self.home, ".claude")
        self.projects = os.path.join(self.config_dir, "projects")
        self.off = os.path.join(self.config_dir, "account-mirror.off")
        self.state_dir = a.state_dir or os.path.join(self.config_dir, "state", "account-mirror")
        self.ledger = os.path.join(self.state_dir, "ledger.json")
        self.status = os.path.join(self.state_dir, "status.json")
        self.app_cache = os.path.join(self.state_dir, "app-check.json")
        self.lock = os.path.join(self.state_dir, "lock")
        self.app = a.app or "/Applications/Claude.app"
        self.plist = os.path.join(a.launch_agents_dir or os.path.join(self.home, "Library", "LaunchAgents"),
                                  LABEL + ".plist")
        self.install_sh = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "install-claude-app-account-mirror.sh")


def known_accounts(home: str) -> dict:
    """accountUuid → {email, org} (CLI 系の .claude.json の oauthAccount。 1 file の中の組は常に整合)。"""
    out = {}
    cands = [os.path.join(home, ".claude.json")]
    with contextlib.suppress(OSError):
        cands += [os.path.join(home, n, ".claude.json") for n in sorted(os.listdir(home))
                  if n.startswith(".claude") and os.path.isdir(os.path.join(home, n))]
    for p in cands:
        try:
            oa = read_json(p).get("oauthAccount") or {}
        except (OSError, ValueError, AttributeError):
            continue
        u, e = oa.get("accountUuid"), oa.get("emailAddress")
        if isinstance(u, str) and isinstance(e, str) and u and e:
            out.setdefault(u, {"email": e, "org": oa.get("organizationUuid")})
    return out


def discover_accounts(paths, known: dict) -> dict:
    """accountUuid → {org, dir, label}。 org dir は session の在る方 (両方 / どちらも無いなら oauth の org)。"""
    accts = {}
    try:
        names = sorted(os.listdir(paths.sessions_root))
    except OSError:
        return accts
    for a in names:
        adir = os.path.join(paths.sessions_root, a)
        if not UUID_RE.match(a) or not os.path.isdir(adir):
            continue
        orgs = {}
        with contextlib.suppress(OSError):
            for o in os.listdir(adir):
                od = os.path.join(adir, o)
                if UUID_RE.match(o) and os.path.isdir(od):
                    with contextlib.suppress(OSError):
                        orgs[o] = sum(1 for n in os.listdir(od) if n.startswith("local_") and n.endswith(".json"))
        pref = (known.get(a) or {}).get("org")
        used = [o for o, c in orgs.items() if c > 0]
        if len(used) == 1:
            org = used[0]
        elif pref in orgs:
            org = pref
        elif used:
            org = max(used, key=lambda o: orgs[o])
        elif len(orgs) == 1:
            org = next(iter(orgs))
        else:
            org = None  # session が 1 つも無く org dir が複数 = どこに書けば一覧に出るか決められない
        if org:
            email = (known.get(a) or {}).get("email")
            label = re.sub(r"\s+", "", email.split("@", 1)[0]) if email else a[:8]
            accts[a] = {"org": org, "dir": os.path.join(adir, org), "label": label or a[:8]}
    seen = {}
    for a, info in accts.items():
        seen.setdefault(info["label"], []).append(a)
    for label, ids in seen.items():
        if len(ids) > 1:
            for a in ids:
                accts[a]["label"] = f"{label}-{a[:4]}"
    return accts


def load_records(adir: str):
    recs, unreadable = {}, set()
    try:
        names = os.listdir(adir)
    except OSError:
        return None, set()
    for n in names:
        if not (n.startswith("local_") and n.endswith(".json")):
            continue
        sid = n[:-5]
        try:
            d = read_json(os.path.join(adir, n))
            if not isinstance(d, dict) or d.get("sessionId") != sid:
                raise ValueError
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            unreadable.add(sid)
            continue
        recs[sid] = d
    return recs, unreadable


def transcript_index(projects: str) -> dict:
    idx = {}
    try:
        top = list(os.scandir(projects))
    except OSError:
        return idx
    for d in top:
        if not d.is_dir(follow_symlinks=False):
            continue
        try:
            for e in os.scandir(d.path):
                if e.name.endswith(".jsonl") and e.is_file(follow_symlinks=False):
                    idx.setdefault(e.name[:-6], []).append(e.path)
        except OSError:
            continue
    return idx


def find_transcript(idx: dict, rec: dict):
    cli = rec.get("cliSessionId")
    hits = idx.get(cli) if isinstance(cli, str) else None
    if not hits:
        return None
    root = os.path.dirname(os.path.dirname(hits[0]))
    for c in (rec.get("cwd"), rec.get("originCwd")):
        if isinstance(c, str) and c:
            want = os.path.join(root, cli_slug(c), cli + ".jsonl")
            if want in hits:
                return want
    return max(hits, key=lambda p: os.stat(p).st_mtime_ns if os.path.exists(p) else 0)


def _protected(p: str, home: str) -> bool:
    if p == "/Volumes" or p.startswith("/Volumes/"):
        return True
    return any(p == os.path.join(home, r) or p.startswith(os.path.join(home, r) + "/") for r in PROTECTED_REL)


def cwd_status(cwd, home: str) -> str:
    """ok / missing / assumed (TCC で守られた場所 = stat しない) / unknown (stat できない)。"""
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        return "missing"
    p = os.path.normpath(cwd)
    if _protected(p, home):
        return "assumed"
    if p.startswith(home + "/"):
        parts = p[len(home) + 1:].split("/", 1)
        link = os.path.join(home, parts[0])
        try:
            if os.path.islink(link):  # 例 ~/Dropbox → ~/Library/CloudStorage/Dropbox (向き先には触らない)
                tgt = os.readlink(link)
                tgt = tgt if os.path.isabs(tgt) else os.path.normpath(os.path.join(home, tgt))
                full = os.path.normpath(os.path.join(tgt, parts[1])) if len(parts) > 1 else tgt
                if _protected(full, home):
                    return "assumed"
        except OSError:
            return "unknown"
    try:
        st = os.stat(p)
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    except OSError:
        return "unknown"
    return "ok" if stat.S_ISDIR(st.st_mode) else "missing"


# ---- app が表示している account ----------------------------------------------------------------

def app_running() -> bool:
    try:
        out = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # 分からない = 起動中とみなす (書く先を絞る側に倒す)
    return any(APP_PROC_RE.search(line.strip()) for line in out.splitlines())


class Gate:
    """書いてよい account か (= app が表示していない account)。 書く直前に毎回呼ぶ。"""

    def __init__(self, paths, mode: str):
        self.paths, self.mode = paths, mode
        self._running_at, self._running = 0.0, True

    def running(self) -> bool:
        if self.mode in ("yes", "no"):
            return self.mode == "yes"
        if time.monotonic() - self._running_at > 2.0:
            self._running, self._running_at = app_running(), time.monotonic()
        return self._running

    def displayed(self):
        try:
            v = read_json(self.paths.config_json).get("lastKnownAccountUuid")
            return v if isinstance(v, str) else None
        except (OSError, ValueError, AttributeError):
            return None

    def writable(self, acct: str) -> bool:
        if not self.running():
            return True
        d = self.displayed()
        return d is not None and d != acct


# ---- 台帳 ----------------------------------------------------------------------------------------

def load_ledger(path: str) -> dict:
    try:
        d = read_json(path)
        if isinstance(d, dict) and isinstance(d.get("mirrors"), dict):
            return d
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        raise RuntimeError(f"台帳を読めない: {path} ({type(e).__name__}) — 直すまで何も書かない") from e
    return {"version": 1, "mirrors": {}}


# ---- 本体 ----------------------------------------------------------------------------------------

class Mirror:
    def __init__(self, args, paths):
        self.a, self.p = args, paths
        self.now = args.now if args.now is not None else now_ms()
        self.gate = Gate(paths, args.app_running)
        self.known = known_accounts(paths.home)
        self.accts = discover_accounts(paths, self.known)
        self.records, self.unreadable = {}, {}
        for acct, info in self.accts.items():
            recs, bad = load_records(info["dir"])
            self.records[acct] = recs
            self.unreadable[acct] = bad
        self.tx = transcript_index(paths.projects)
        self.ledger = load_ledger(paths.ledger)
        self.mirrors = self.ledger["mirrors"]
        self.planned = {"create": 0, "update": 0, "remove": 0}
        self.counts = {"create": 0, "update": 0, "remove": 0, "blocked": 0, "failed": 0}  # 実際にやった数
        self.skips = {}
        self.examples = []
        self.errors = []

    # -- 台帳を保存 (apply のときだけ)
    def save(self):
        if self.a.apply:
            os.makedirs(self.p.state_dir, exist_ok=True)
            write_atomic(self.p.ledger, dump_compact(self.ledger))

    def label(self, acct):
        info = self.accts.get(acct)
        return info["label"] if info else acct[:8]

    def observe(self, m: dict) -> str:
        """台帳の写しが今どうなっているか: unopened / opened / missing / unknown / no-account。"""
        dst = m.get("dst_account")
        if dst not in self.accts or self.records.get(dst) is None:
            return "no-account"
        sid = m["session_id"]
        if sid in self.unreadable[dst]:
            return "unknown"
        r = self.records[dst].get(sid)
        if r is None:
            return "missing"
        staged = r.get("stagedTranscriptPath")
        if r.get("resumeConfirmed") or not staged or not os.path.isfile(staged):
            return "opened"
        if staged != m.get("staged_path") or r.get("cliSessionId") != m.get("cli"):
            return "opened"  # app が書き換えた = 自分の物として扱わない
        return "unopened"

    def eligible(self, acct: str, rec: dict):
        """(写せるか, 理由, 会話記録の path)。"""
        if not isinstance(rec.get("cliSessionId"), str) or not rec.get("cliSessionId"):
            return False, "no-cli", None
        if rec.get("sshConfig") or rec.get("wslConfig") or rec.get("movedToCloud"):
            return False, "not-local", None
        archived = rec.get("isArchived") is True
        last = rec.get("lastActivityAt") if isinstance(rec.get("lastActivityAt"), (int, float)) else 0
        if archived and last < self.now - self.a.days * 86400000:
            return False, "out-of-range", None
        cwd = rec.get("cwd")
        cs = cwd_status(cwd, self.p.home)
        if cs == "missing":
            return False, "cwd-missing", None
        if cs == "unknown":
            return False, "cwd-unknown", None
        if len(cli_slug(cwd)) > SLUG_MAX:
            return False, "cwd-too-long", None
        tx = find_transcript(self.tx, rec)
        if not tx:
            return False, "no-transcript", None
        return True, "ok", tx

    def src_sig(self, rec, tx):
        st = os.stat(tx)
        return [rec.get("cliSessionId"), st.st_size, st.st_mtime_ns, rec.get("lastActivityAt"),
                rec.get("title"), rec.get("isArchived") is True]

    def skip(self, reason):
        self.skips[reason] = self.skips.get(reason, 0) + 1

    # -- 計画
    def plan(self):
        acts = []
        by_sid = {}
        for sid, m in self.mirrors.items():
            m["_obs"] = self.observe(m)
            by_sid[sid] = m
        # 台帳の状態を観測に合わせる (書かない判断だけ。 書くのは apply)
        for sid, m in self.mirrors.items():
            st, obs = m.get("state"), m["_obs"]
            if obs in ("no-account", "unknown"):
                continue
            if st == "creating":
                acts.append({"op": "recover", "m": m})
            elif st == "removing":
                acts.append({"op": "finish-remove", "m": m})
            elif st in ("unopened", "opened"):
                if obs == "missing":
                    acts.append({"op": "mark", "m": m, "state": "user_deleted"})
                elif obs == "opened" and st != "opened":
                    acts.append({"op": "mark", "m": m, "state": "opened"})
                elif obs == "opened":
                    r = self.records[m["dst_account"]].get(sid) or {}
                    if not r.get("stagedTranscriptPath") and os.path.isfile(m.get("staged_path") or ""):
                        acts.append({"op": "drop-orphan", "m": m})
        state_now = {sid: next((x["state"] for x in acts if x["op"] == "mark" and x["m"] is m), m.get("state"))
                     for sid, m in self.mirrors.items()}
        gens = {}
        for sid, m in self.mirrors.items():
            gens.setdefault((m["src_account"], m["src_session_id"], m["dst_account"]), []).append(m)
        for v in gens.values():
            v.sort(key=lambda m: (m.get("created_at") or 0, m.get("seq") or 0))
        # 元ごと
        src_ok = {}
        for acct in self.accts:
            recs = self.records.get(acct)
            if recs is None:
                continue
            for sid, rec in recs.items():
                own = by_sid.get(sid)
                if own is not None and own.get("dst_account") == acct:
                    s = state_now.get(sid)
                    if s in ("creating", "unopened", "removing"):
                        self.skip("unopened-mirror")
                        continue
                    if s == "opened" and (rec.get("lastActivityAt") or 0) <= (own.get("last_activity_written") or 0):
                        self.skip("opened-mirror-unchanged")
                        continue
                elif rec.get("importedFrom") and not rec.get("resumeConfirmed"):
                    self.skip("unopened-import")
                    continue
                ok, why, tx = self.eligible(acct, rec)
                src_ok[(acct, sid)] = (ok, why)
                if not ok:
                    self.skip(why)
                    continue
                sig = self.src_sig(rec, tx)
                for dst in self.accts:
                    if dst == acct or self.records.get(dst) is None:
                        continue
                    g = gens.get((acct, sid, dst)) or []
                    latest = g[-1] if g else None
                    lst = state_now.get(latest["session_id"]) if latest else None
                    if latest is None or lst == "removed":
                        acts.append({"op": "create", "src": acct, "rec": rec, "tx": tx, "sig": sig, "dst": dst})
                    elif lst == "unopened":
                        if latest.get("src_sig") != sig:
                            acts.append({"op": "update", "m": latest, "rec": rec, "tx": tx, "sig": sig})
                    elif lst == "opened":
                        if (rec.get("lastActivityAt") or 0) > (latest.get("src_last_activity") or 0) \
                                and latest.get("src_sig") != sig:
                            acts.append({"op": "create", "src": acct, "rec": rec, "tx": tx, "sig": sig, "dst": dst})
        # 元が消えた / 範囲外 → 未開封の写しを消す
        for sid, m in self.mirrors.items():
            if state_now.get(sid) != "unopened" or m["_obs"] != "unopened":
                continue
            src, ssid = m["src_account"], m["src_session_id"]
            if (src not in self.accts or self.records.get(src) is None or not self.records[src]
                    or self.accts[src]["org"] != m.get("src_org")):
                continue  # 元の account の dir が無い / 読めない / 空 / 別の org dir = 決めない (一斉に消さない)
            if ssid in self.unreadable.get(src, set()):
                continue
            if ssid not in self.records[src]:
                acts.append({"op": "remove", "m": m, "reason": "source-deleted"})
                continue
            ok, why = src_ok.get((src, ssid), (True, "ok"))
            if not ok and why in GONE_REASONS:
                acts.append({"op": "remove", "m": m, "reason": why})
        return acts

    # -- 実行
    def run(self, acts):
        order = {"recover": 0, "finish-remove": 1, "mark": 2, "drop-orphan": 3, "remove": 4, "update": 5, "create": 6}
        acts = sorted(acts, key=lambda x: order[x["op"]])
        creates = sorted((x for x in acts if x["op"] == "create"),
                         key=lambda x: -(x["rec"].get("lastActivityAt") or 0))
        acts = [x for x in acts if x["op"] != "create"] + creates
        for x in acts:
            op = x["op"]
            dst = x["dst"] if op == "create" else x["m"]["dst_account"]
            main_op = op in ("create", "update", "remove")
            if main_op:
                self.planned[op] += 1
                x["result"] = "planned"
                if len(self.examples) < 400:
                    self.examples.append(x)
            if not self.a.apply:
                continue
            if op == "mark":
                x["m"]["state"] = x["state"]
                x["m"]["updated_at"] = self.now
                self.save()
                continue
            if not self.gate.writable(dst):
                res = "blocked"
            else:
                try:
                    res = getattr(self, "do_" + op.replace("-", "_"))(x) or "done"
                except Exception as e:  # 1 件の失敗で全体を止めない (状態に出す)
                    res = "failed"
                    self.errors.append(f"{op} {x.get('m', {}).get('session_id', '')}: {type(e).__name__}: {e}")
            if main_op:
                x["result"] = res
                self.counts[op if res == "done" else res] += 1
            elif res == "failed":
                self.counts["failed"] += 1
        for m in self.mirrors.values():
            m.pop("_obs", None)

    def _staging(self, dst):
        d = os.path.join(self.accts[dst]["dir"], STAGING)
        os.makedirs(d, mode=0o700, exist_ok=True)
        return d

    def _stage(self, dst, tx, m, incremental: bool):
        """会話記録を一時 file に作る。 返り値 = (一時 file, 読んだ位置, 大きさ)。"""
        tmp = os.path.join(self._staging(dst), f".import-{uuid.uuid4()}.tmp")
        start, base = 0, None
        if incremental and m and m.get("src_transcript") == tx and m.get("src_consumed"):
            try:
                ok = (os.path.getsize(tx) >= m["src_consumed"]
                      and head_hash(tx, m["src_consumed"]) == m.get("src_head")
                      and os.path.getsize(m["staged_path"]) == m.get("staged_bytes"))
            except OSError:
                ok = False
            if ok:
                start, base = m["src_consumed"], m["staged_path"]
        try:
            consumed, size = stage_transcript(tx, tmp, start, base, self.a.max_line)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
        return tmp, consumed, size

    def _note_src(self, m, rec, tx, sig, consumed, size, title, archived):
        m.update({"src_cli": rec.get("cliSessionId"), "src_transcript": tx, "src_sig": sig,
                  "src_last_activity": rec.get("lastActivityAt") or 0, "src_consumed": consumed,
                  "src_head": head_hash(tx, consumed), "staged_bytes": size, "title_written": title,
                  "archived_written": archived, "last_activity_written": rec.get("lastActivityAt") or 0,
                  "updated_at": self.now})

    def do_create(self, x):
        dst, rec, tx, sig = x["dst"], x["rec"], x["tx"], x["sig"]
        info = self.accts[dst]
        sid, cli = f"local_{uuid.uuid4()}", str(uuid.uuid4())
        staged = os.path.join(info["dir"], STAGING, cli + ".jsonl")
        m = {"session_id": sid, "cli": cli, "dst_account": dst, "dst_org": info["org"], "staged_path": staged,
             "src_account": x["src"], "src_org": self.accts[x["src"]]["org"], "src_session_id": rec["sessionId"],
             "state": "creating", "created_at": self.now}
        self.mirrors[sid] = m
        self.save()
        try:
            tmp, consumed, size = self._stage(dst, tx, None, False)
        except BaseException:
            del self.mirrors[sid]
            self.save()
            raise
        if not self.gate.writable(dst):
            os.unlink(tmp)
            del self.mirrors[sid]
            self.save()
            return "blocked"
        os.replace(tmp, staged)
        title = mirror_title(rec.get("title"), self.label(x["src"]))
        archived = rec.get("isArchived") is True
        record = {"sessionId": sid, "cliSessionId": cli, "cwd": rec["cwd"], "originCwd": rec["cwd"], "title": title,
                  "createdAt": rec.get("createdAt") or self.now,
                  "lastActivityAt": rec.get("lastActivityAt") or rec.get("createdAt") or self.now,
                  "indexedAt": now_ms(), "isArchived": archived, "importedFrom": IMPORTED_FROM,
                  "stagedTranscriptPath": staged}
        if rec.get("adoptedFromOtherSurface") is True:
            record["adoptedFromOtherSurface"] = True
        if isinstance(rec.get("cliMcpAppServerNames"), list) and rec["cliMcpAppServerNames"]:
            record["cliMcpAppServerNames"] = list(rec["cliMcpAppServerNames"])
        if rec.get("ranInSandboxVm") is True:
            record["ranInSandboxVm"] = True
        if not write_atomic(os.path.join(info["dir"], sid + ".json"), dump_compact(record),
                            before_replace=lambda: self.gate.writable(dst)):
            os.unlink(staged)
            del self.mirrors[sid]
            self.save()
            return "blocked"
        self._note_src(m, rec, tx, sig, consumed, size, title, archived)
        m["state"] = "unopened"
        self.ledger["seq"] = self.ledger.get("seq", 0) + 1
        m["seq"] = self.ledger["seq"]
        self.save()

    def do_update(self, x):
        m, rec, tx, sig = x["m"], x["rec"], x["tx"], x["sig"]
        dst = m["dst_account"]
        rpath = os.path.join(self.accts[dst]["dir"], m["session_id"] + ".json")
        same_cli = m.get("src_cli") == rec.get("cliSessionId")
        tmp, consumed, size = self._stage(dst, tx, m, same_cli)
        try:
            cur = read_json(rpath)
        except (OSError, ValueError):
            os.unlink(tmp)
            raise
        if (cur.get("resumeConfirmed") or cur.get("stagedTranscriptPath") != m["staged_path"]
                or not os.path.isfile(m["staged_path"]) or not self.gate.writable(dst)):
            os.unlink(tmp)  # 開かれた / 表示された = 触らない (次の実行で台帳が追いつく)
            return "blocked"
        os.replace(tmp, m["staged_path"])
        title = mirror_title(rec.get("title"), self.label(m["src_account"]))
        if cur.get("title") == m.get("title_written"):
            cur["title"] = title
        else:
            title = m.get("title_written")  # 本人が変えた題名は触らない
        archived = rec.get("isArchived") is True
        if bool(cur.get("isArchived")) == bool(m.get("archived_written")):
            cur["isArchived"] = archived
        else:
            archived = m.get("archived_written")
        cur["lastActivityAt"] = rec.get("lastActivityAt") or cur.get("lastActivityAt")
        if rec.get("createdAt"):
            cur["createdAt"] = rec["createdAt"]
        if not write_atomic(rpath, dump_compact(cur), before_replace=lambda: self.gate.writable(dst)):
            return "blocked"
        self._note_src(m, rec, tx, sig, consumed, size, title, archived)
        self.save()

    def _remove_files(self, m):
        dst = m["dst_account"]
        rpath = os.path.join(self.accts[dst]["dir"], m["session_id"] + ".json")
        with contextlib.suppress(FileNotFoundError):
            os.unlink(rpath)  # record が先 (= 中身の無い record を一覧に出さない)
        if m.get("staged_path"):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(m["staged_path"])

    def do_remove(self, x):
        m = x["m"]
        m["state"] = "removing"
        m["removed_reason"] = x.get("reason")
        self.save()
        self._remove_files(m)
        m["state"] = "removed"
        m["updated_at"] = self.now
        self.save()

    def do_finish_remove(self, x):
        self.do_remove({"m": x["m"], "reason": x["m"].get("removed_reason")})

    def do_recover(self, x):
        """作成中に落ちた写し: record が在れば未開封として拾い、 無ければ staged を片付けて台帳から外す。"""
        m = x["m"]
        r = self.records[m["dst_account"]].get(m["session_id"]) or {}
        if m["_obs"] in ("unopened", "opened"):
            m["state"] = m["_obs"]
            m["src_sig"] = None  # 未開封なら次の実行で全部写し直す (どこまで写したか分からない)
            m["src_consumed"] = 0
            m["title_written"] = r.get("title")
            m["archived_written"] = r.get("isArchived") is True
            m["last_activity_written"] = r.get("lastActivityAt") or 0
            m["src_last_activity"] = r.get("lastActivityAt") or 0
        else:
            if m["_obs"] == "missing" and m.get("staged_path"):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(m["staged_path"])
            self.mirrors.pop(m["session_id"], None)
        self.save()

    def do_drop_orphan(self, x):
        with contextlib.suppress(FileNotFoundError):
            os.unlink(x["m"]["staged_path"])

    def sweep_tmp(self):
        """自分の一時 file の残り (1 時間より古い) を片付ける。 表示中の account の dir には触らない。"""
        cutoff = time.time() - 3600
        for acct, info in self.accts.items():
            if not self.gate.writable(acct):
                continue
            for d, pre in ((info["dir"], TMP_PREFIX), (os.path.join(info["dir"], STAGING), ".import-")):
                with contextlib.suppress(OSError):
                    for n in os.listdir(d):
                        p = os.path.join(d, n)
                        if n.startswith(pre) and n.endswith(".tmp"):
                            with contextlib.suppress(OSError):
                                if os.lstat(p).st_mtime < cutoff:
                                    os.unlink(p)

    # -- 取り消し
    def undo(self):
        n_done, blocked = 0, []
        for sid, m in self.mirrors.items():
            obs = self.observe(m)
            if m.get("state") not in ("creating", "unopened", "removing") or obs not in ("unopened", "missing"):
                continue
            if not self.a.apply:
                n_done += 1
                continue
            if not self.gate.writable(m["dst_account"]):
                blocked.append(m)
                continue
            m["state"] = "removing"
            m["removed_reason"] = "undo"
            self.save()
            self._remove_files(m)
            m["state"] = "removed"
            m["updated_at"] = self.now
            self.save()
            n_done += 1
        return n_done, blocked


# ---- 出力 ----------------------------------------------------------------------------------------

def describe(mr: Mirror, acts, apply: bool, quiet: bool, check: dict) -> str:
    out = io.StringIO()
    c = mr.counts
    changed = (c["create"] or c["update"] or c["remove"] or c["failed"]) if apply else any(mr.planned.values())
    if quiet and not changed and not mr.errors:
        return ""
    gate = mr.gate
    running = gate.running()
    disp = gate.displayed()
    head = "account-mirror" + ("" if apply else " (dry-run = 何も書かない)")
    print(f"{head} {human_ms(mr.now)} — app {check.get('version')} (点検 {'ok' if check.get('ok') else 'NG'}) / "
          f"app {'起動中、 表示中 = ' + mr.label(disp) if running else '停止中 (全 account に書ける)'}", file=out)
    pairs = {}
    for x in mr.examples:
        if x["op"] == "create":
            key = (x["src"], x["dst"])
        else:
            key = (x["m"]["src_account"], x["m"]["dst_account"])
        v = pairs.setdefault(key, {"create": 0, "update": 0, "remove": 0, "wait": 0, "failed": 0})
        res = x.get("result")
        if apply and res == "blocked":
            v["wait"] += 1
        elif apply and res == "failed":
            v["failed"] += 1
        else:
            v[x["op"]] += 1
    verb = ("作った", "差し替えた", "消した") if apply else ("作る", "差し替え", "消す")
    for (s, d), v in sorted(pairs.items(), key=lambda kv: (mr.label(kv[0][0]), mr.label(kv[0][1]))):
        if quiet and not (v["create"] or v["update"] or v["remove"] or v["failed"]):
            continue
        extra = ""
        if v["wait"]:
            extra += f" / 待ち {v['wait']} (表示中の account・開かれた)"
        if v["failed"]:
            extra += f" / 失敗 {v['failed']}"
        if not apply and not gate.writable(d):
            extra += " ← 表示中の account なので今は書かない"
        print(f"  {mr.label(s)} → {mr.label(d)}: {verb[0]} {v['create']} / {verb[1]} {v['update']} / "
              f"{verb[2]} {v['remove']}{extra}", file=out)
    if not pairs:
        print("  変更なし", file=out)
    if not quiet:
        shown = 0
        for x in mr.examples:
            if shown >= 8:
                break
            if x["op"] == "create":
                rec = x["rec"]
                size = os.path.getsize(x["tx"]) if os.path.exists(x["tx"]) else 0
                print(f"  + {mirror_title(rec.get('title'), mr.label(x['src']))}  [{mr.label(x['dst'])}] "
                      f"({short_path(rec.get('cwd', ''), mr.p.home)}, {size / 1e6:.1f} MB, "
                      f"最終 {human_ms(rec.get('lastActivityAt'))})", file=out)
            elif x["op"] == "update":
                print(f"  ~ {x['m'].get('title_written')}  [{mr.label(x['m']['dst_account'])}]", file=out)
            else:
                print(f"  - {x['m'].get('title_written')}  [{mr.label(x['m']['dst_account'])}] ({x.get('reason')})",
                      file=out)
            shown += 1
        if mr.skips:
            names = {"out-of-range": "範囲外", "no-transcript": "会話記録なし", "cwd-missing": "cwd なし",
                     "cwd-unknown": "cwd を確かめられない", "unopened-mirror": "未開封の写し",
                     "unopened-import": "未開封のインポート", "opened-mirror-unchanged": "開いた写し (動きなし)",
                     "no-cli": "cli id なし", "not-local": "手元でない", "cwd-too-long": "cwd が長すぎ"}
            print("  写さない: " + " / ".join(f"{names.get(k, k)} {v}" for k, v in sorted(mr.skips.items())),
                  file=out)
    for e in mr.errors[:5]:
        print(f"  ⚠️ {e}", file=out)
    return out.getvalue()


def write_status(paths, data: dict):
    os.makedirs(paths.state_dir, exist_ok=True)
    write_atomic(paths.status, dump_compact(data))


def notice(paths) -> str:
    """session 開始用。 未導入・停止・失敗・止まっている時だけ 1 行 (他は空)。"""
    if os.path.exists(paths.off) or not os.path.isdir(paths.sessions_root):
        return ""
    accts = discover_accounts(paths, known_accounts(paths.home))
    if len(accts) < 2:
        return ""
    inst = "bash " + short_path(paths.install_sh, paths.home)
    head = "🔀 desktop の session 一覧の写し (account-mirror)"
    if not os.path.exists(paths.plist):
        return (f"{head}: この Mac に未導入 = もう片方の account の session が一覧に出ない。 入れる = {inst}"
                f" (止めておくなら touch {short_path(paths.off, paths.home)})")
    try:
        with open(paths.plist, "rb") as f:
            watch = set(plistlib.load(f).get("WatchPaths") or [])
    except (OSError, ValueError, plistlib.InvalidFileException):
        watch = set()
    if any(info["dir"] not in watch for info in accts.values()):
        return f"{head}: 見張る dir が今の account と合わない (account が増えた?) = 入れ直す: {inst}"
    try:
        st = read_json(paths.status)
    except (OSError, ValueError):
        st = None
    ver = app_version(paths.app)
    try:
        chk = read_json(paths.app_cache)
    except (OSError, ValueError):
        chk = None
    if isinstance(chk, dict) and chk.get("version") == ver and not chk.get("ok"):
        miss = "、 ".join(chk.get("missing") or [])[:200]
        return (f"{head}: 止まっています — Claude {ver} の本体に写しの前提が見つからない ({miss})。 "
                f"仕組みを確かめるまで写しません (状態 = {inst} --status)")
    if not isinstance(st, dict):
        try:
            age = time.time() - os.path.getmtime(paths.plist)
        except OSError:
            age = 0
        return f"{head}: 入れてから 1 度も動いていない = 状態 = {inst} --status" if age > 3600 else ""
    if not st.get("ok"):
        return f"{head}: 直近の実行が失敗 ({human_ms(st.get('at'))}): {str(st.get('error'))[:200]} = 状態 = {inst} --status"
    if now_ms() - int(st.get("at") or 0) > STALE_MS:
        return f"{head}: 24 時間以上動いていない (最後 {human_ms(st.get('at'))}) = 状態 = {inst} --status"
    return ""


def status_text(paths, args) -> str:
    out = io.StringIO()
    h = paths.home
    print(f"常駐 (launchd {LABEL}): {'入っている' if os.path.exists(paths.plist) else '未導入'}"
          f"{'' if os.path.exists(paths.plist) else ' = bash ' + short_path(paths.install_sh, h)}", file=out)
    if os.path.exists(paths.off):
        print(f"止めるスイッチ: あり ({short_path(paths.off, h)}) = 何も写さない。 消せば再開", file=out)
    try:
        st = read_json(paths.status)
        print(f"直近の実行: {human_ms(st.get('at'))} {'ok' if st.get('ok') else 'NG: ' + str(st.get('error'))}"
              f" (作る {st.get('create', 0)} / 差し替え {st.get('update', 0)} / 消す {st.get('remove', 0)} / "
              f"待ち {st.get('blocked', 0)} / 失敗 {st.get('failed', 0)})", file=out)
    except (OSError, ValueError):
        print("直近の実行: 記録なし", file=out)
    chk = app_check(paths, save=False)
    print(f"app の点検: Claude {chk.get('version')} → {'ok' if chk.get('ok') else 'NG: ' + '、 '.join(chk.get('missing') or [])}",
          file=out)
    try:
        led = load_ledger(paths.ledger)
        cnt = {}
        for m in led["mirrors"].values():
            cnt[m.get("state")] = cnt.get(m.get("state"), 0) + 1
        names = {"unopened": "未開封", "opened": "開いた", "removed": "消した", "user_deleted": "本人が消した",
                 "creating": "作成中", "removing": "削除中"}
        print("台帳: " + (" / ".join(f"{names.get(k, k)} {v}" for k, v in sorted(cnt.items())) or "空")
              + f" ({short_path(paths.ledger, h)})", file=out)
    except RuntimeError as e:
        print(f"台帳: {e}", file=out)
    return out.getvalue()


# ---- 入口 ----------------------------------------------------------------------------------------

def plist_dict(paths, a) -> dict:
    """launchd の job: 各 account の session dir を見張り (WatchPaths)、 保険に 5 分ごと、 間隔は最短 60 秒。"""
    args = [a.python or sys.executable, os.path.abspath(__file__)]
    for flag, val in (("--home", a.home), ("--user-data", a.user_data), ("--desktop-config-dir", a.desktop_config_dir),
                      ("--state-dir", a.state_dir), ("--app", a.app)):
        if val:
            args += [flag, val]
    args += ["--apply", "--quiet"]
    log = a.log or os.path.join(paths.home, "Library", "Logs", "claude-account-mirror.log")
    watch = [info["dir"] for info in discover_accounts(paths, known_accounts(paths.home)).values()]
    return {"Label": LABEL, "ProgramArguments": args, "WatchPaths": watch, "StartInterval": 300,
            "ThrottleInterval": 60, "RunAtLoad": True, "ProcessType": "Background", "LowPriorityIO": True,
            "Nice": 10, "EnvironmentVariables": {"PYTHONIOENCODING": "utf-8"},
            "StandardOutPath": log, "StandardErrorPath": log}


@contextlib.contextmanager
def locked(paths):
    os.makedirs(paths.state_dir, exist_ok=True)
    fd = os.open(paths.lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                yield False
                return
        yield True
    finally:
        os.close(fd)


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--undo", action="store_true", help="未開封の写しを全部取り消す (+ 止めるスイッチ)")
    g.add_argument("--status", action="store_true")
    g.add_argument("--notice", action="store_true")
    g.add_argument("--app-check", action="store_true")
    g.add_argument("--watch-paths", action="store_true")
    g.add_argument("--print-plist", action="store_true", help="launchd の plist を出す (install script が使う)")
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--apply", action="store_true", help="書く (既定は dry-run)")
    ap.add_argument("--quiet", action="store_true", help="変化が無ければ何も出さない (launchd 用)")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS, help="アーカイブ済みでも写す直近の日数")
    ap.add_argument("--app-running", choices=("auto", "yes", "no"), default="auto")
    ap.add_argument("--home")
    ap.add_argument("--user-data")
    ap.add_argument("--desktop-config-dir")
    ap.add_argument("--state-dir")
    ap.add_argument("--app")
    ap.add_argument("--launch-agents-dir")
    ap.add_argument("--python", help="--print-plist: launchd から起動する python (既定 = 今の python)")
    ap.add_argument("--log", help="--print-plist: log の path (既定 ~/Library/Logs/claude-account-mirror.log)")
    ap.add_argument("--now", type=int, help=argparse.SUPPRESS)
    ap.add_argument("--max-line", type=int, default=MAX_LINE, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(sys.argv[1:] if argv is None else argv)
    if a.selftest:
        return selftest()
    paths = Paths(a)
    if a.notice:
        try:
            msg = notice(paths)
        except Exception:  # session 開始を止めない
            msg = ""
        if msg:
            print(msg)
        return 0
    if a.status:
        print(status_text(paths, a), end="")
        return 0
    if a.print_plist:
        sys.stdout.buffer.write(plistlib.dumps(plist_dict(paths, a)))
        return 0
    if a.watch_paths:
        for info in discover_accounts(paths, known_accounts(paths.home)).values():
            print(info["dir"])
        return 0
    if a.app_check:
        res = app_check(paths, save=True, force=True)
        print(f"Claude {res.get('version')}: {'ok' if res.get('ok') else 'NG'}")
        for m in res.get("missing") or []:
            print(f"  欠け: {m}")
        return 0 if res.get("ok") else 1
    if a.undo:
        return cmd_undo(a, paths)
    return cmd_run(a, paths)


def cmd_run(a, paths) -> int:
    if os.path.exists(paths.off):
        if not a.quiet:
            print(f"止めるスイッチがある ({short_path(paths.off, paths.home)}) = 何もしない")
        return 0
    if not os.path.isdir(paths.sessions_root):
        if not a.quiet:
            print("desktop app の session の保存 dir が無い = 何もしない")
        return 0
    ctx = locked(paths) if a.apply else contextlib.nullcontext(True)
    with ctx as got:
        if not got:
            if not a.quiet:
                print("別の実行が動いている = 今回は何もしない")
            return 0
        status = {"at": now_ms(), "ok": True, "error": None}
        try:
            check = app_check(paths, save=a.apply)
            status["app_version"] = check.get("version")
            status["app_check_ok"] = bool(check.get("ok"))
            if not check.get("ok"):
                msg = (f"Claude {check.get('version')} の本体に写しの前提が見つからない: "
                       + "、 ".join(check.get("missing") or []) + " = 写さない")
                if a.apply:
                    try:
                        prev = read_json(paths.status).get("stopped")
                    except (OSError, ValueError, AttributeError):
                        prev = None
                    status.update(ok=True, stopped=msg)
                    write_status(paths, status)
                    if a.quiet and prev == msg:
                        return 0  # 同じ理由で止まり続けている = log に毎回は書かない
                print(msg)
                return 0 if a.apply else 1
            mr = Mirror(a, paths)
            if len(mr.accts) < 2:
                if a.apply:
                    write_status(paths, status)
                if not a.quiet:
                    print("account が 1 つしか無い = 写す先が無い")
                return 0
            if a.apply:
                mr.sweep_tmp()
            acts = mr.plan()
            mr.run(acts)
            status.update({k: mr.counts[k] for k in mr.counts})
            status["planned"] = dict(mr.planned)
            status["accounts"] = {k: v["label"] for k, v in mr.accts.items()}
            if mr.errors:
                status["ok"] = False
                status["error"] = mr.errors[0]
            text = describe(mr, acts, a.apply, a.quiet, check)
            if text:
                print(text, end="")
        except Exception as e:
            status.update(ok=False, error=f"{type(e).__name__}: {e}")
            if a.apply:
                with contextlib.suppress(Exception):
                    write_status(paths, status)
            raise
        if a.apply:
            write_status(paths, status)
        return 0 if status["ok"] else 1


def cmd_undo(a, paths) -> int:
    ctx = locked(paths) if a.apply else contextlib.nullcontext(True)
    with ctx as got:
        if not got:
            print("別の実行が動いている = 少し待ってやり直す")
            return 1
        mr = Mirror(a, paths)
        n, blocked = mr.undo()
        if a.apply:
            os.makedirs(os.path.dirname(paths.off), exist_ok=True)
            with open(paths.off, "a"):
                pass
            print(f"未開封の写しを {n} 件取り消した。 止めるスイッチを置いた ({short_path(paths.off, paths.home)}、 "
                  f"消せば再開)")
            if blocked:
                labels = sorted({mr.label(m["dst_account"]) for m in blocked})
                print(f"⚠️ {len(blocked)} 件は app が表示中の account ({'、 '.join(labels)}) なので残した = "
                      f"app で別の account に切り替えるか app を終了してから、 もう一度 --undo --apply")
            return 0
        print(f"(dry-run) 取り消す未開封の写し: {n} 件。 書くには --undo --apply")
        return 0


# ---- selftest ------------------------------------------------------------------------------------

def _fake_asar(path: str, files: dict):
    entries, blob, off = {}, b"", 0
    for name, data in files.items():
        entries[name] = {"size": len(data), "offset": str(off)}
        blob += data
        off += len(data)
    js = json.dumps({"files": {".vite": {"files": {"build": {"files": entries}}}}}).encode()
    pad = (4 - len(js) % 4) % 4
    pickle = struct.pack("<II", 4 + len(js) + pad, len(js)) + js + b"\0" * pad
    with open(path, "wb") as f:
        f.write(struct.pack("<II", 4, len(pickle)) + pickle + blob)


GOOD_JS = (
    b'var Bb="claude-code-sessions",kPt="imported-staging",Hb={code1p:"local-1p-code",terminalCli:"terminal-cli"};'
    b'function y9(e){let t=e?.cwd;return typeof t=="string"&&t.length>0?t:void 0}'
    b'function hMa(e){if(typeof e!="object"||!e)return e;let{sessionId:t,...n}=e,r=n.toolUseResult;'
    b'if(typeof r=="object"&&r&&"agentId"in r){let{agentId:e,...t}=r;n.toolUseResult=t}return n}var gMa=16777216;'
    b'class L{getStorageDir(){return(0,Y.join)(this.userDataPath,this.baseDir,this.currentAccountId,this.currentOrgId)}'
    b'load(){a=e.filter((e=>e.startsWith("local_")&&e.endsWith(".json")))}'
    b'reg(){t.q0.warn("[registerExternalSession] rejected a staging file outside the private staging dir")}'
    b'fin(){m={sessionId:r,cliSessionId:s.cliSessionId,cwd:a,originCwd:a,title:s.title,createdAt:d,lastActivityAt:f,'
    b'indexedAt:u,isArchived:s.isArchived===!0,importedFrom:s.importedFrom??t.cJ.code1p,stagedTranscriptPath:o,}}'
    b'async confirmImportedSessionResume(e){let n=(0,Y.join)(t.AP(),"projects",e);let i=(0,Y.join)(n,`${r.cliSessionId}.jsonl`),'
    b'a=r.stagedTranscriptPath;r.resumeConfirmed=!0}}'
    b'function uir(e,t){let n=e,r=n.replace(/[^a-zA-Z0-9]/g,"-");return r}'
)


def selftest() -> int:
    fails = []
    n_ok = [0]

    def check(label, cond):
        if cond:
            n_ok[0] += 1
            print(f"PASS {label}")
        else:
            fails.append(label)
            print(f"FAIL {label}")

    A = "aaaaaaaa-1111-4111-8111-111111111111"   # 架空の account / org の uuid
    B = "bbbbbbbb-2222-4222-8222-222222222222"
    OA = "0a0a0a0a-3333-4333-8333-333333333333"
    OB = "0b0b0b0b-4444-4444-8444-444444444444"
    DAY = 86400000
    NOW = 1_800_000_000_000

    with tempfile.TemporaryDirectory() as tdir:
        home = os.path.join(tdir, "home")
        ud = os.path.join(home, "ud")
        app = os.path.join(tdir, "Claude.app")
        os.makedirs(os.path.join(app, "Contents", "Resources"))

        def set_app(ver, js):
            with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleShortVersionString": ver}, f)
            _fake_asar(os.path.join(app, "Contents", "Resources", "app.asar"), {"index.js": js})

        set_app("9.1.0", GOOD_JS)
        for acct, email, org in ((A, "alpha" + "@" + "example.invalid", OA), (B, "beta" + "@" + "example.invalid", OB)):
            d = os.path.join(home, f".claude-{email.split('@')[0]}")
            os.makedirs(d)
            with open(os.path.join(d, ".claude.json"), "w") as f:
                json.dump({"oauthAccount": {"accountUuid": acct, "emailAddress": email, "organizationUuid": org}}, f)
            for o in (OA, OB):
                os.makedirs(os.path.join(ud, "claude-code-sessions", acct, o))
        dirA = os.path.join(ud, "claude-code-sessions", A, OA)
        dirB = os.path.join(ud, "claude-code-sessions", B, OB)
        proj = os.path.join(home, ".claude", "projects")
        work = os.path.join(home, "work")
        os.makedirs(work)
        state = os.path.join(home, ".claude", "state", "account-mirror")

        def set_displayed(acct):
            with open(os.path.join(ud, "config.json"), "w") as f:
                json.dump({"lastKnownAccountUuid": acct} if acct else {}, f)

        def add_session(adir, cwd, title, last, archived=False, lines=None, cli=None, extra=None):
            sid, cli = f"local_{uuid.uuid4()}", cli or str(uuid.uuid4())
            rec = {"sessionId": sid, "cliSessionId": cli, "cwd": cwd, "originCwd": cwd, "title": title,
                   "createdAt": last - 1000, "lastActivityAt": last, "isArchived": archived,
                   "model": "m", "permissionMode": "default"}
            rec.update(extra or {})
            with open(os.path.join(adir, sid + ".json"), "w") as f:
                json.dump(rec, f)
            if lines is not None:
                pd = os.path.join(proj, cli_slug(cwd))
                os.makedirs(pd, exist_ok=True)
                with open(os.path.join(pd, cli + ".jsonl"), "wb") as f:
                    f.write(lines)
            return sid, cli, rec

        def tx_path(cwd, cli):
            return os.path.join(proj, cli_slug(cwd), cli + ".jsonl")

        def line(**kw):
            return json.dumps(kw, ensure_ascii=False).encode() + b"\n"

        def run(*extra, running="yes", now=NOW):
            argv = ["--home", home, "--user-data", ud, "--app", app, "--app-running", running, "--now", str(now),
                    "--launch-agents-dir", os.path.join(home, "LA")] + list(extra)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(argv)
            return rc, buf.getvalue()

        def ledger():
            return read_json(os.path.join(state, "ledger.json"))["mirrors"]

        def recs(adir):
            return {n[:-5]: read_json(os.path.join(adir, n)) for n in os.listdir(adir)
                    if n.startswith("local_") and n.endswith(".json")}

        def snapshot():
            out = {}
            for root, _dirs, files in os.walk(tdir):
                for n in files:
                    p = os.path.join(root, n)
                    if os.path.islink(p):
                        continue
                    with open(p, "rb") as f:
                        out[p] = f.read()
            return out

        # ---- 純粋関数
        check("slug: 英数字以外を -", cli_slug("/home/x/Claude") == "-home-x-Claude")
        check("slug: 日本語 1 文字 = - 1 個 (UTF-16 code unit)", cli_slug("/a/東京") == "-a---")
        check("slug: BMP 外の文字 = - 2 個", cli_slug("/a/\U0001F600") == "-a---")
        long = "/" + "a" * 250
        check("slug: 200 超は切って hash", len(cli_slug(long)) > SLUG_MAX and cli_slug(long).startswith("-" + "a" * 199))
        check("題名: 印を付ける", mirror_title("作業", "alpha") == "\u21c4alpha 作業")
        check("題名: 既にある印は付け替える (二重にしない)",
              mirror_title("\u21c4beta 作業", "alpha") == "\u21c4alpha 作業")
        check("題名: 空なら session", mirror_title("", "alpha") == "\u21c4alpha session")
        t = transform_line(line(type="user", cwd="/w", sessionId="s", toolUseResult={"agentId": "x", "k": 1}, z=2))
        check("変換: sessionId と toolUseResult.agentId を外し、 順序は保つ",
              t == b'{"type":"user","cwd":"/w","toolUseResult":{"k":1},"z":2}\n')
        check("変換: cwd の無い行は写さない", transform_line(line(type="custom-title", sessionId="s")) is None)
        check("変換: JSON でない行は写さない", transform_line(b"{oops\n") is None)
        check("変換: 孤立 surrogate は \\u で逃がす",
              transform_line(b'{"cwd":"/w","t":"\\ud800"}\n') == b'{"cwd":"/w","t":"\\ud800"}\n')
        check("cwd: TCC で守られた場所は stat しない",
              cwd_status(os.path.join(home, "Documents", "no-such"), home) == "assumed")
        os.symlink(os.path.join(home, "Library", "CloudStorage", "Box"), os.path.join(home, "Box"))
        check("cwd: home 直下の symlink の向き先が守られた場所なら stat しない",
              cwd_status(os.path.join(home, "Box", "x"), home) == "assumed")
        check("cwd: 無い = missing", cwd_status(os.path.join(home, "nope"), home) == "missing")
        check("cwd: 在る = ok", cwd_status(work, home) == "ok")

        # ---- 1 回目: app 起動中・表示中 = A → B にだけ書く
        set_displayed(A)
        body = (line(type="user", cwd=work, sessionId="orig", uuid="u1", message={"content": "hi"})
                + line(type="custom-title", customTitle="x", sessionId="orig")
                + b"{broken\n"
                + line(type="assistant", cwd=work, sessionId="orig", uuid="u2",
                       toolUseResult={"agentId": "ag", "out": "ok"})
                + b'{"type":"user","cwd":"' + work.encode() + b'","partial":tru')  # 書きかけの最後の行
        sA1, cA1, rA1 = add_session(dirA, work, "A の作業", NOW - DAY, lines=body,
                                    extra={"cliMcpAppServerNames": ["x"]})
        sA2, cA2, _ = add_session(dirA, work, "A の古い保存", NOW - 30 * DAY, archived=True, lines=line(cwd=work))
        sA3, _cA3, _ = add_session(dirA, os.path.join(home, "gone"), "cwd なし", NOW - DAY, lines=line(cwd=work))
        sA4, _cA4, _ = add_session(dirA, work, "会話記録なし", NOW - DAY)
        sA5, _cA5, _ = add_session(dirA, work, "古いが未アーカイブ", NOW - 90 * DAY, lines=line(cwd=work))
        sB1, cB1, _ = add_session(dirB, work, "\u21c4alpha B の作業", NOW - 2 * DAY, lines=line(cwd=work, k=1))

        before = snapshot()
        rc, out = run()
        check("dry-run: 何も書かない", snapshot() == before and rc == 0)
        check("dry-run: 計画に B 向けの作成が出る", "alpha → beta: 作る 2" in out)
        check("dry-run: 表示中の A 向けは待ちと出る", "beta → alpha: 作る 1 / 差し替え 0 / 消す 0 ← 表示中" in out)

        rc, out = run("--apply")
        check("apply: rc 0", rc == 0)
        rb = recs(dirB)
        mine = {sid: r for sid, r in rb.items() if r.get("importedFrom")}
        check("apply: B に写しが 2 件 (範囲外・cwd なし・会話記録なしは写さない)", len(mine) == 2)
        check("apply: 表示中の A には何も書かない", all(not r.get("importedFrom") for r in recs(dirA).values()))
        m1 = next((r for r in mine.values() if r["title"] == "\u21c4alpha A の作業"), None)
        check("apply: 題名に元 account の印", m1 is not None)
        if m1:
            keys = ["sessionId", "cliSessionId", "cwd", "originCwd", "title", "createdAt", "lastActivityAt",
                    "indexedAt", "isArchived", "importedFrom", "stagedTranscriptPath", "cliMcpAppServerNames"]
            check("record: 公式インポートと同じ最小の形", list(m1.keys()) == keys)
            check("record: importedFrom = local-1p-code", m1["importedFrom"] == IMPORTED_FROM)
            check("record: lastActivityAt は元のまま", m1["lastActivityAt"] == rA1["lastActivityAt"])
            check("record: cli は新しい", m1["cliSessionId"] != cA1 and UUID_RE.match(m1["cliSessionId"]))
            sp = m1["stagedTranscriptPath"]
            check("staged: <dir>/imported-staging/<cli>.jsonl",
                  sp == os.path.join(dirB, STAGING, m1["cliSessionId"] + ".jsonl"))
            with open(sp, "rb") as f:
                staged = f.read()
            check("staged: cwd の無い行・壊れた行・書きかけの行は落ち、 sessionId/agentId は外れる",
                  staged.count(b"\n") == 2 and b"sessionId" not in staged and b"agentId" not in staged
                  and b'"out":"ok"' in staged)
            check("record: file の mode 600",
                  stat.S_IMODE(os.stat(os.path.join(dirB, m1["sessionId"] + ".json")).st_mode) == 0o600)
        led = ledger()
        check("台帳: 2 件 unopened", sorted(m["state"] for m in led.values()) == ["unopened", "unopened"])
        check("一時 file が残らない",
              not [n for n in os.listdir(dirB) + os.listdir(os.path.join(dirB, STAGING)) if n.endswith(".tmp")])
        st = read_json(os.path.join(state, "status.json"))
        check("status: ok で件数 (表示中の A 向けの 1 件は待ち)",
              st["ok"] and st["create"] == 2 and st["blocked"] == 1 and st["planned"]["create"] == 3)
        check("apply の出力: やった数と待ち", "alpha → beta: 作った 2" in out and "beta → alpha: 作った 0" in out
              and "待ち 1" in out)

        # ---- 2 回目: 変化なし = 何もしない
        snap = snapshot()
        rc, out = run("--apply", "--quiet")
        check("冪等: 2 回目は何も変えない (status だけ)",
              rc == 0 and out == "" and {k: v for k, v in snapshot().items() if not k.endswith("status.json")}
              == {k: v for k, v in snap.items() if not k.endswith("status.json")})

        # ---- 元が進む → 未開封の写しを同じ id のまま差し替え (続きだけ足す)。 本人の題名・アーカイブは残す
        mid = m1["sessionId"]
        rp = os.path.join(dirB, mid + ".json")
        r = read_json(rp)
        r["title"] = "本人が付けた題名"
        r["isArchived"] = True
        r["lastFocusedAt"] = 5
        with open(rp, "w") as f:
            json.dump(r, f)
        with open(tx_path(work, cA1), "ab") as f:
            f.write(b'e,"uuid":"u3"}\n' + line(type="assistant", cwd=work, uuid="u4"))
        ra = read_json(os.path.join(dirA, sA1 + ".json"))
        ra["lastActivityAt"] = NOW - 1000
        ra["title"] = "A の作業 (続き)"
        with open(os.path.join(dirA, sA1 + ".json"), "w") as f:
            json.dump(ra, f)
        rc, out = run("--apply")
        r2 = read_json(rp)
        check("差し替え: 同じ session id・cli のまま", r2["cliSessionId"] == m1["cliSessionId"])
        check("差し替え: 本人が変えた題名・アーカイブ・app が足した field は残す",
              r2["title"] == "本人が付けた題名" and r2["isArchived"] is True and r2["lastFocusedAt"] == 5)
        check("差し替え: lastActivityAt は元に追従", r2["lastActivityAt"] == NOW - 1000)
        with open(m1["stagedTranscriptPath"], "rb") as f:
            staged2 = f.read()
        check("差し替え: 書きかけだった行と新しい行が足される (重複なし)",
              staged2.startswith(staged) and staged2.count(b"\n") == 4 and staged2.count(b'"uuid":"u3"') == 1)
        # 完全に写し直したときと同じ中身か
        with tempfile.TemporaryDirectory() as t2:
            full = os.path.join(t2, "f")
            stage_transcript(tx_path(work, cA1), full)
            with open(full, "rb") as f:
                check("差し替え: 続きだけ足した結果 = 全部写し直した結果", f.read() == staged2)
            os.environ["ACCOUNT_MIRROR_NO_CLONE"] = "1"
            try:
                src = os.path.join(t2, "src.jsonl")
                with open(src, "wb") as f:
                    f.write(line(cwd=work, n=1, sessionId="s") + line(cwd=work, n=2))
                c0, _ = stage_transcript(src, os.path.join(t2, "first"))
                with open(src, "ab") as f:
                    f.write(line(cwd=work, n=3))
                stage_transcript(src, os.path.join(t2, "inc"), start=c0, base=os.path.join(t2, "first"))
                stage_transcript(src, os.path.join(t2, "all"))
                with open(os.path.join(t2, "inc"), "rb") as f, open(os.path.join(t2, "all"), "rb") as g:
                    a1, a2 = f.read(), g.read()
                check("clone が使えない時も続きを足せる (普通に写す)", a1 == a2 and a1.count(b"\n") == 3)
            finally:
                os.environ.pop("ACCOUNT_MIRROR_NO_CLONE", None)
        # 続きだけ足す経路を本当に通っているか: staged の 1 byte を (大きさを変えずに) 変えておくと残る。
        # 大きさが台帳と違えば全部写し直す (= 変えた byte は消える)
        sp = m1["stagedTranscriptPath"]

        def poke(path, old, new):
            with open(path, "rb") as f:
                b = f.read()
            with open(path, "wb") as f:
                f.write(b.replace(old, new, 1))

        def grow(n):
            with open(tx_path(work, cA1), "ab") as f:
                f.write(line(type="user", cwd=work, uuid=f"g{n}"))
            ra["lastActivityAt"] += 1
            with open(os.path.join(dirA, sA1 + ".json"), "w") as f:
                json.dump(ra, f)
            run("--apply")
            with open(sp, "rb") as f:
                return f.read()

        poke(sp, b'"uuid":"u1"', b'"uuid":"U1"')
        got = grow(1)
        check("差し替え: 続きだけ足す (前に写した部分は読み直さない)", b'"uuid":"U1"' in got and b'"uuid":"g1"' in got)
        poke(sp, b'"uuid":"U1"', b'"uuid":"U1x"')
        got = grow(2)
        check("差し替え: staged の大きさが台帳と違えば全部写し直す", b'"uuid":"u1"' in got and b"U1" not in got
              and b'"uuid":"g2"' in got)

        # ---- 写しを開く (app が resumeConfirmed を立て、 staged を projects/ へ移す) → 二度と触らない
        r = read_json(rp)
        newp = os.path.join(proj, cli_slug(work), r["cliSessionId"] + ".jsonl")
        os.replace(r["stagedTranscriptPath"], newp)
        r["resumeConfirmed"] = True
        r.pop("stagedTranscriptPath")
        with open(rp, "w") as f:
            json.dump(r, f)
        rc, out = run("--apply")
        check("開いた写し: 台帳が opened", ledger()[mid]["state"] == "opened")
        check("開いた写し: 中身に触らない", read_json(rp) == r)
        with open(sp, "w") as f:  # 開くのと差し替えが競ったときに残る、 どの record も指さない staged
            f.write("{}\n")
        rc, out = run("--apply")
        check("開いた写し: 誰も指さない staged の残りは片付ける", not os.path.exists(sp) and read_json(rp) == r)
        # 開いた写しの元がさらに進む → 新しい写しを 1 つ足す
        ra["lastActivityAt"] = NOW - 500
        with open(os.path.join(dirA, sA1 + ".json"), "w") as f:
            json.dump(ra, f)
        with open(tx_path(work, cA1), "ab") as f:
            f.write(line(type="user", cwd=work, uuid="u5"))
        rc, out = run("--apply")
        gens = [m for m in ledger().values() if m["src_session_id"] == sA1 and m["dst_account"] == B]
        check("開いた後に元が進む → 新しい写しを足す (2 世代)", len(gens) == 2)
        check("開いた写し: やはり触らない", read_json(rp) == r)

        # ---- 開いた写しは、 開いた後に動けば逆向き (= 元の account) にも写す。 動いていなければ写さない
        set_displayed(B)
        rc, out = run("--apply")
        back = [x for x in recs(dirA).values() if x.get("importedFrom")]
        check("開いた写し (動きなし) は逆向きに写さない / 未開封の写しも写さない",
              all(x["title"] != "\u21c4beta 本人が付けた題名" for x in back))
        check("表示中が B に変わると A に書ける (B の元 session の写し)",
              any(x["title"] == "\u21c4beta B の作業" for x in back))
        check("B の題名の印 (\u21c4alpha) は付け替える", all(not x["title"].startswith("\u21c4beta \u21c4") for x in back))
        r["lastActivityAt"] = NOW - 100
        with open(rp, "w") as f:
            json.dump(r, f)
        with open(newp, "ab") as f:
            f.write(line(type="user", cwd=work, uuid="b1"))
        rc, out = run("--apply")
        back = [x for x in recs(dirA).values() if x.get("importedFrom")]
        check("開いた写しが動いた → 逆向きに写す",
              any(x["title"] == "\u21c4beta 本人が付けた題名" for x in back))
        check("未開封の写しは写さない (ping-pong なし)",
              not [x for x in back if "\u21c4beta \u21c4" in x["title"]]
              and len([m for m in ledger().values() if m["dst_account"] == A]) == 2)

        # ---- 本人が消した写しは作り直さない
        victim = next(x for x in back if x["title"] == "\u21c4beta B の作業")
        os.unlink(os.path.join(dirA, victim["sessionId"] + ".json"))
        os.unlink(victim["stagedTranscriptPath"])
        rc, out = run("--apply")
        check("本人が消した → user_deleted、 作り直さない",
              ledger()[victim["sessionId"]]["state"] == "user_deleted"
              and not [x for x in recs(dirA).values() if x.get("title") == "\u21c4beta B の作業"])

        # ---- 範囲外になった / 元が消えた → 未開封の写しを消す。 表示中の account の写しは待つ
        set_displayed(A)
        g2 = next(m for m in gens if m["session_id"] != mid)
        ra["isArchived"] = True
        ra["lastActivityAt"] = NOW - 20 * DAY
        with open(os.path.join(dirA, sA1 + ".json"), "w") as f:
            json.dump(ra, f)
        rc, out = run("--apply")
        check("範囲外 → 未開封の写しを消す (record も staged も)",
              ledger()[g2["session_id"]]["state"] == "removed"
              and not os.path.exists(os.path.join(dirB, g2["session_id"] + ".json"))
              and not os.path.exists(g2["staged_path"]))
        check("範囲外: 開いた写しは残す", os.path.exists(rp))
        other = next(m for m in ledger().values() if m["dst_account"] == B and m["state"] == "unopened")
        os.unlink(os.path.join(dirA, other["src_session_id"] + ".json"))
        set_displayed(B)
        rc, out = run("--apply")
        check("表示中の account の写しは消さない (待ち)", ledger()[other["session_id"]]["state"] == "unopened"
              and os.path.exists(os.path.join(dirB, other["session_id"] + ".json")))
        rc, out = run("--apply", running="no")
        check("app が止まっていれば消す (元が消えた)", ledger()[other["session_id"]]["state"] == "removed")

        # ---- 元の account の dir が読めない → 消さない (一斉に消さない)
        set_displayed(None)
        sA6, cA6, _ = add_session(dirA, work, "後から", NOW - DAY, lines=line(cwd=work))
        rc, out = run("--apply", running="no")
        m6 = next(m for m in ledger().values() if m["src_session_id"] == sA6 and m["dst_account"] == B)
        os.rename(dirA, dirA + ".x")
        rc, out = run("--apply", running="no")
        check("元の account の dir が無い → 写しを消さない", ledger()[m6["session_id"]]["state"] == "unopened")
        dirA_other = os.path.join(ud, "claude-code-sessions", A, OB)
        sX, _cX, _ = add_session(dirA_other, os.path.join(home, "nope"), "別の org dir の session", NOW - DAY)
        rc, out = run("--apply", running="no")
        check("元の account が別の org dir に移った → 写しを消さない", ledger()[m6["session_id"]]["state"] == "unopened")
        os.unlink(os.path.join(dirA_other, sX + ".json"))
        os.rename(dirA + ".x", dirA)
        # 他人が作った未開封のインポート (会話記録が projects/ にあっても) は写さない
        sI, _cI, _ = add_session(dirA, work, "誰かのインポート", NOW - DAY, lines=line(cwd=work),
                                 extra={"importedFrom": "terminal-cli",
                                        "stagedTranscriptPath": os.path.join(dirA, STAGING, "x.jsonl")})
        rc, out = run("--apply", running="no")
        check("未開封のインポートは写さない", not [m for m in ledger().values() if m["src_session_id"] == sI])
        os.unlink(os.path.join(dirA, sI + ".json"))

        # ---- 作成中に落ちた写しを拾う
        led_all = read_json(os.path.join(state, "ledger.json"))
        ghost = "local_" + str(uuid.uuid4())
        gcli = str(uuid.uuid4())
        gstaged = os.path.join(dirB, STAGING, gcli + ".jsonl")
        with open(gstaged, "w") as f:
            f.write("{}\n")
        led_all["mirrors"][ghost] = {"session_id": ghost, "cli": gcli, "dst_account": B, "dst_org": OB,
                                     "staged_path": gstaged, "src_account": A, "src_org": OA,
                                     "src_session_id": sA6, "state": "creating", "created_at": NOW}
        with open(os.path.join(state, "ledger.json"), "w") as f:
            json.dump(led_all, f)
        rc, out = run("--apply", running="no")
        check("作成中に落ちた写し: staged を片付けて台帳から外す",
              ghost not in ledger() and not os.path.exists(gstaged))

        # ---- app の版が変わり、 前提が欠けた → 写さない・状態に出す
        set_app("9.2.0", GOOD_JS.replace(b"confirmImportedSessionResume", b"confirmSomethingElse"))
        sA7, _c, _ = add_session(dirA, work, "版が変わった後", NOW - DAY, lines=line(cwd=work))
        before = snapshot()
        rc, out = run("--apply", running="no")
        chk = read_json(os.path.join(state, "app-check.json"))
        check("app 点検: 欠けを見つける", chk["version"] == "9.2.0" and not chk["ok"]
              and any("confirmImportedSessionResume" in m for m in chk["missing"]))
        check("app 点検: 欠けたら写さない",
              not [m for m in ledger().values() if m["src_session_id"] == sA7])
        st = read_json(os.path.join(state, "status.json"))
        check("app 点検: 状態に止まった理由", st.get("stopped") and st.get("app_check_ok") is False)
        rc, out = run("--apply", "--quiet", running="no")
        check("app 点検: 同じ理由で止まり続けるなら log に毎回は書かない", rc == 0 and out == "")
        os.makedirs(os.path.join(home, "LA"), exist_ok=True)
        with open(os.path.join(home, "LA", LABEL + ".plist"), "wb") as f:
            plistlib.dump({"Label": LABEL, "WatchPaths": [dirA, dirB]}, f)
        rc, out = run("--notice")
        check("notice: 止まっていると出る", "止まっています" in out and "9.2.0" in out)
        set_app("9.3.0", GOOD_JS)
        rc, out = run("--apply", running="no")
        check("app 点検: 版ごとに点検し直す (直れば写す)",
              [m for m in ledger().values() if m["src_session_id"] == sA7])

        # ---- notice の各場合
        rc, out = run("--notice")
        check("notice: 正常なら無音", out == "")
        st = read_json(os.path.join(state, "status.json"))
        st["at"] = now_ms() - 3 * DAY
        write_atomic(os.path.join(state, "status.json"), dump_compact(st))
        rc, out = run("--notice")
        check("notice: 24 時間以上動いていない", "24 時間以上" in out)
        st.update(at=now_ms(), ok=False, error="OSError: x")
        write_atomic(os.path.join(state, "status.json"), dump_compact(st))
        rc, out = run("--notice")
        check("notice: 直近の失敗", "失敗" in out)
        with open(os.path.join(home, "LA", LABEL + ".plist"), "wb") as f:
            plistlib.dump({"Label": LABEL, "WatchPaths": [dirA]}, f)
        rc, out = run("--notice")
        check("notice: 見張る dir が足りない → 入れ直し", "入れ直す" in out)
        os.unlink(os.path.join(home, "LA", LABEL + ".plist"))
        rc, out = run("--notice")
        check("notice: 未導入 → 入れるコマンド", "未導入" in out and "install-claude-app-account-mirror.sh" in out)
        rc, out = run("--watch-paths")
        check("watch-paths: 各 account の session dir", sorted(out.splitlines()) == sorted([dirA, dirB]))
        buf = io.BytesIO()
        with contextlib.redirect_stdout(io.TextIOWrapper(buf, encoding="utf-8")) as w:
            main(["--home", home, "--user-data", ud, "--print-plist", "--python", "/x/python3"])
            w.flush()
        pl = plistlib.loads(buf.getvalue())
        check("plist: 見張る dir・5 分ごと・最短 60 秒・--apply --quiet",
              sorted(pl["WatchPaths"]) == sorted([dirA, dirB]) and pl["StartInterval"] == 300
              and pl["ThrottleInterval"] == 60 and pl["ProgramArguments"][0] == "/x/python3"
              and pl["ProgramArguments"][-2:] == ["--apply", "--quiet"] and pl["Label"] == LABEL)

        # ---- 長すぎる行は飛ばす
        sA8, c8, _ = add_session(dirA, work, "長い行", NOW - DAY,
                                 lines=line(cwd=work, big="x" * 300) + line(cwd=work, small=1))
        rc, out = run("--apply", "--max-line", "200", running="no")
        m8 = next(m for m in ledger().values() if m["src_session_id"] == sA8 and m["dst_account"] == B)
        with open(m8["staged_path"], "rb") as f:
            got = f.read()
        check("長すぎる行は飛ばし、 次の行は写す", got.count(b"\n") == 1 and b'"small":1' in got)

        # ---- 取り消し: 未開封だけ消し、 表示中の account は残し、 止めるスイッチを置く
        set_displayed(A)
        unopened = [m for m in ledger().values() if m["state"] == "unopened"]
        rc, out = run("--undo")
        check("undo dry-run: 何も消さない", all(os.path.exists(m["staged_path"]) for m in unopened))
        rc, out = run("--undo", "--apply")
        onA = [m for m in unopened if m["dst_account"] == A]
        onB = [m for m in unopened if m["dst_account"] == B]
        check("undo: 表示中でない account の未開封の写しを消す",
              onB and all(not os.path.exists(os.path.join(dirB, m["session_id"] + ".json")) for m in onB))
        check("undo: 表示中の account の写しは残して知らせる",
              (not onA or all(os.path.exists(os.path.join(dirA, m["session_id"] + ".json")) for m in onA))
              and (not onA or "表示中" in out))
        check("undo: 開いた写しは残す", os.path.exists(rp))
        check("undo: 止めるスイッチを置く", os.path.exists(os.path.join(home, ".claude", "account-mirror.off")))
        snap = snapshot()
        rc, out = run("--apply", running="no")
        check("止めるスイッチ: 何もしない", snapshot() == snap and "止めるスイッチ" in out)
        rc, out = run("--notice")
        check("止めるスイッチ: notice も無音", out == "")

        # ---- 台帳が壊れていたら何も書かない
        os.unlink(os.path.join(home, ".claude", "account-mirror.off"))
        with open(os.path.join(state, "ledger.json"), "w") as f:
            f.write("{oops")
        snap = snapshot()
        try:
            run("--apply", running="no")
            raised = False
        except RuntimeError:
            raised = True
        check("台帳が壊れている → 止まる (何も書かない、 状態は失敗)", raised and all(
            v == snapshot().get(k) for k, v in snap.items() if not k.endswith("status.json")))
        check("台帳が壊れている → 状態 NG", read_json(os.path.join(state, "status.json"))["ok"] is False)

    # account が 1 つ / app の session dir が無い
    with tempfile.TemporaryDirectory() as t3:
        os.makedirs(os.path.join(t3, "ud", "claude-code-sessions", A, OA))
        argv = ["--home", t3, "--user-data", os.path.join(t3, "ud"), "--notice"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(argv)
        check("notice: account が 1 つなら無音", buf.getvalue() == "")

    print(f"selftest: {n_ok[0]} ok, {len(fails)} fail")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
