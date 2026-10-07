#!/usr/bin/env python3
"""claude_config_dirs.py — every Claude Code config dir on this machine, so readers of per-session state see all of them.

Why: a Claude Code session keeps its live registry (`<config>/sessions/<pid>.json`), its transcript
(`<config>/projects/<cwd>/<sessionId>.jsonl`) and its state under the config dir it runs with. The default is
`~/.claude`; a session started with `CLAUDE_CONFIG_DIR=<dir>` (a Remote Control server pinned to one account =
every session started from a phone, a headless job, a CLI pinned to an account) writes under `<dir>`. A reader
that looks only at `~/.claude` does not see those sessions (measured on a desktop machine: a session
started from a phone through the account-pinned server was alive for days and missing from the live-session list,
from the double-dispatch check and from the model lookup; the harness's own `ListAgents` is per config dir too).
Convention: conventions/multi-account-machine-surface.md#peer-discovery-across-config-dirs.

What counts as a config dir: `~/.claude`, `$CLAUDE_CONFIG_DIR`, and every `~/.claude-*` directory that has a
`sessions/` or `projects/` subdirectory (a backup file such as `~/.claude.json.backup` is not a directory and a
directory without either subdirectory is not a config dir). Order: the default first, then the others sorted;
the same directory reached twice (a symlink) is listed once.

Env overrides (tests, fixtures): CLAUDE_SESSIONS_DIR / CLAUDE_PROJECTS_DIR name ONE directory and replace the scan
for that kind; CLAUDE_CONFIG_DIRS_HOME replaces the home directory that is scanned.

Read-only, never raises.
"""
from __future__ import annotations

import glob
import os

DEFAULT_NAME = ".claude"


def _home() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIRS_HOME") or os.path.expanduser("~")


def config_dirs() -> list[str]:
    """Config dirs on this machine, default first. A dir that does not exist is skipped (the default too)."""
    home = _home()
    default = os.path.join(home, DEFAULT_NAME)
    cands = [default]
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        cands.append(os.path.expanduser(env))
    try:
        # a real directory before a symlink to it, so the de-duplication keeps the real name
        others = sorted(glob.glob(os.path.join(home, DEFAULT_NAME + "-*")), key=lambda d: (os.path.islink(d), d))
    except Exception:
        others = []
    for d in others:
        if os.path.isdir(os.path.join(d, "sessions")) or os.path.isdir(os.path.join(d, "projects")):
            cands.append(d)
    out: list[str] = []
    seen: set[str] = set()
    for d in cands:
        try:
            if not os.path.isdir(d):
                continue
            key = os.path.realpath(d)
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _sub(kind: str, env_name: str) -> list[str]:
    override = os.environ.get(env_name)
    if override:
        return [override]
    out = []
    for d in config_dirs():
        p = os.path.join(d, kind)
        if os.path.isdir(p):
            out.append(p)
    return out


def sessions_dirs() -> list[str]:
    """Every `<config>/sessions` (the harness's live-session registry: `<pid>.json`)."""
    return _sub("sessions", "CLAUDE_SESSIONS_DIR")


def projects_dirs() -> list[str]:
    """Every `<config>/projects` (transcripts)."""
    return _sub("projects", "CLAUDE_PROJECTS_DIR")


def label(config_dir: str) -> str:
    """Short name of a config dir: 'default' for ~/.claude, the suffix for ~/.claude-<x> ('x'), else the basename."""
    base = os.path.basename(os.path.normpath(config_dir or ""))
    if base == DEFAULT_NAME:
        return "default"
    if base.startswith(DEFAULT_NAME + "-"):
        return base[len(DEFAULT_NAME) + 1:]
    return base or "?"


def label_of(path: str) -> str:
    """Label of the config dir that holds `path` (a registry file, a sessions dir, a transcript)."""
    p = os.path.normpath(path or "")
    while p and p != os.path.dirname(p):
        base = os.path.basename(p)
        if base == DEFAULT_NAME or base.startswith(DEFAULT_NAME + "-"):
            return label(p)
        p = os.path.dirname(p)
    return "?"


def socket_address(entry: dict) -> str:
    """`uds:<socket>` from a registry entry's messagingSocketPath, or ''. SendMessage accepts this as `to`, and the
    harness delivers to a session on this machine whatever config dir or account it runs with (measured:
    a default-dir session reached an account-pinned session this way and got the reply; the name did not resolve)."""
    sock = (entry or {}).get("messagingSocketPath")
    return f"uds:{sock}" if isinstance(sock, str) and sock.endswith(".sock") else ""


def _selftest() -> int:
    import json
    import tempfile

    fails: list[str] = []

    def check(name: str, ok: bool) -> None:
        print(("ok: " if ok else "NG: ") + name)
        if not ok:
            fails.append(name)

    saved = {k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIRS_HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_SESSIONS_DIR", "CLAUDE_PROJECTS_DIR")}
    try:
        with tempfile.TemporaryDirectory() as td:
            for k in saved:
                os.environ.pop(k, None)
            os.environ["CLAUDE_CONFIG_DIRS_HOME"] = td
            os.makedirs(os.path.join(td, ".claude", "sessions"))
            os.makedirs(os.path.join(td, ".claude", "projects"))
            os.makedirs(os.path.join(td, ".claude-alpha", "sessions"))
            os.makedirs(os.path.join(td, ".claude-beta", "projects"))
            os.makedirs(os.path.join(td, ".claude-junk"))  # neither subdir = not a config dir
            with open(os.path.join(td, ".claude.json.backup"), "w") as fh:
                fh.write("{}")
            os.symlink(os.path.join(td, ".claude-alpha"), os.path.join(td, ".claude-alias"))
            names = [label(d) for d in config_dirs()]
            check("default first, then the others; junk and files skipped", names[0] == "default" and "junk" not in names and "json.backup" not in "".join(names))
            check("a symlink to a listed dir is listed once", sorted(names) in (sorted(["default", "alpha", "beta"]),) and len(names) == 3)
            check("sessions dirs only where they exist", [label_of(p) for p in sessions_dirs()] == ["default", "alpha"])
            check("projects dirs only where they exist", [label_of(p) for p in projects_dirs()] == ["default", "beta"])
            ext = os.path.join(td, "elsewhere")
            os.makedirs(os.path.join(ext, "sessions"))
            os.environ["CLAUDE_CONFIG_DIR"] = ext
            check("$CLAUDE_CONFIG_DIR outside the home pattern is included", any(os.path.samefile(p, os.path.join(ext, "sessions")) for p in sessions_dirs()))
            os.environ["CLAUDE_SESSIONS_DIR"] = "/x/only"
            check("CLAUDE_SESSIONS_DIR replaces the scan", sessions_dirs() == ["/x/only"])
            check("label", (label(os.path.join(td, ".claude")), label("/h/.claude-odakin"), label("/h/cfg")) == ("default", "odakin", "cfg"))
            check("label_of a transcript path", label_of("/h/.claude-odakin/projects/-w/abc.jsonl") == "odakin" and label_of("/nowhere/x") == "?")
            check("socket address", socket_address({"messagingSocketPath": "/tmp/cc-socks/1.sock"}) == "uds:/tmp/cc-socks/1.sock"
                  and socket_address({}) == "" and socket_address({"messagingSocketPath": "x"}) == "")
            json.dumps(config_dirs())
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("claude_config_dirs selftest: " + ("ALL PASS" if not fails else f"FAILED {len(fails)}"))
    return 1 if fails else 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(_selftest())
    for d in config_dirs():
        print(f"{label(d)}\t{d}")
