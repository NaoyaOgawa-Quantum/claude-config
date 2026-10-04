"""launchd の無人ジョブについて「直近の run が既知の形で失敗したか」 を log 末尾から読む共有判定。

使い手 = scripts/check-cron-health.py (そのマシンの horizon) と scripts/fleet-heartbeat.py (他マシンへの beat)
→ scripts/check-fleet-status.py (reader)。 判定をここ 1 か所に置き、 3 者が同じ述語で話す。

なぜ終了コードだけでは足りないか (正本 = conventions/scheduled-tasks.md#reload-resets-exit-status):
  - launchd は plist を読み込み直した job の `launchctl list` の終了コードを 0 にする (次に走るまで)。
    失敗した run の後に plist が書き直されると、 失敗は exit 0 の顔になり、 終了コードだけ見る検出器から消える (実測)。
  - 終了コードは「失敗した」 しか言わず、 なぜかを言わない。 headless `claude -p` の routine は、 config dir の
    認証が切れると全部が起動直後に同じ文言で終わる (conventions/scheduled-tasks.md#headless-auth-expiry)。

述語 (= code-as-SoT):
  - log 末尾 LOG_TAIL_LINES 行 ≈ 直近 run の出力の終わり。 log は plist の StandardErrorPath → StandardOutPath →
    <log_dir>/<label>.log の順で探す
  - failure_kind: 末尾に AUTH_MARKERS のどれか = "auth" / "Prompt is too long" = "ptl" / それ以外 = ""
  - hidden_failure: 終了コードが 0 ∧ failure_kind ≠ "" ∧ log の更新が HIDDEN_FAIL_DAYS 日以内
    (= 古い log の末尾は「直近の run」 とは限らないので拾わない)
  - config_dir_of: plist の起動行の `CLAUDE_CONFIG_DIR=` (EnvironmentVariables も見る)
  - logged_in_email: その config dir が今 claude.ai でログイン済みなら email (= `claude auth status` を読むだけ)
  - missed_fire: 予定 (plist の StartCalendarInterval / StartInterval) の時刻から MISSED_GRACE_H 時間たっても、
    その run の分の log が書かれていない = 起動しなかった run か、 終わらずに止まっている run
    (終了コードも log 末尾も前回の run のことしか言わない = conventions/scheduled-tasks.md#missed-run-detection)。
    log が毎回書かれる job (= headless `claude -p` は終わる時に結果を書く、 runs_claude_p) にだけ使う
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import time
from pathlib import Path

LOG_TAIL_LINES = 6
# Claude CLI が認証切れで起動直後に終わるときの文言 (どれか 1 つが log 末尾にあれば認証切れ)
AUTH_MARKERS = ("Failed to authenticate", "OAuth session expired", "Not logged in",
                "Please run /login", "Invalid API key")
PTL_MARKER = "Prompt is too long"
HIDDEN_FAIL_DAYS = 3

_CONFIG_DIR_RE = re.compile(r'CLAUDE_CONFIG_DIR="?([^";\s]+)')


def load_plist(path) -> dict | None:
    try:
        with open(path, "rb") as fh:
            d = plistlib.load(fh)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def job_log_path(label: str, plist: dict | None, log_dir) -> Path:
    """job の log の path。 plist が stderr / stdout の行き先を持てばそれ、 無ければ <log_dir>/<label>.log。"""
    for k in ("StandardErrorPath", "StandardOutPath"):
        v = (plist or {}).get(k)
        if isinstance(v, str) and v:
            return Path(os.path.expanduser(v))
    return Path(log_dir) / f"{label}.log"


def log_tail(path, n: int = LOG_TAIL_LINES) -> list[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def failure_kind(path) -> str:
    """log 末尾の既知の失敗: 'auth' / 'ptl' / ''。"""
    tail = log_tail(path)
    if any(m in line for line in tail for m in AUTH_MARKERS):
        return "auth"
    if any(PTL_MARKER in line for line in tail):
        return "ptl"
    return ""


def log_age_days(path, now: float | None = None) -> float | None:
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return None
    return ((now if now is not None else time.time()) - mtime) / 86400.0


def hidden_failure(last_exit, path, now: float | None = None) -> bool:
    """終了コードは 0 なのに、 直近の run の log 末尾が既知の失敗 (= 読み込み直しで 0 に戻った)。"""
    if last_exit != 0 or not failure_kind(path):
        return False
    age = log_age_days(path, now)
    return age is not None and 0 <= age < HIDDEN_FAIL_DAYS


def config_dir_of(plist: dict | None) -> str:
    """plist の起動行 (または EnvironmentVariables) の CLAUDE_CONFIG_DIR。 無ければ空文字。"""
    if not isinstance(plist, dict):
        return ""
    env = plist.get("EnvironmentVariables") or {}
    if isinstance(env, dict) and env.get("CLAUDE_CONFIG_DIR"):
        return str(env["CLAUDE_CONFIG_DIR"])
    m = _CONFIG_DIR_RE.search(" ".join(str(a) for a in (plist.get("ProgramArguments") or [])))
    return m.group(1) if m else ""


# ── 予定の run が log に残っていない (= 起動しなかった run / 終わらない run) ──
MISSED_GRACE_H = 3        # 予定の時刻からこれだけたっても log が無ければ「残っていない」 (長い routine の実行時間を見込む)
MISSED_SLACK_S = 6 * 60   # log の時刻の丸め (beat の log_age_h は 0.1 時間単位) を見込む
_CLAUDE_P_RE = re.compile(r'\bclaude"?\s+(?:-p|--print)(?=\s|$)')
_GATE_RE = re.compile(r"routine-host-gate\.py")
_CAL_KEYS = ("Minute", "Hour", "Day", "Weekday", "Month")


def _command(plist: dict | None) -> str:
    return " ".join(str(a) for a in ((plist or {}).get("ProgramArguments") or [])) if isinstance(plist, dict) else ""


def runs_claude_p(plist: dict | None) -> bool:
    """起動行が headless `claude -p` を起動するか (= 毎回の run が、 終わる時に log へ結果を書く job)。"""
    return bool(_CLAUDE_P_RE.search(_command(plist)))


def is_gated(plist: dict | None) -> bool:
    """起動行が本番ホストの関門 (routine-host-gate.py) を通るか (= 本番でない機械では log を書かずに休む job)。"""
    return bool(_GATE_RE.search(_command(plist)))


def schedule_of(plist: dict | None) -> dict | None:
    """plist の予定。 {"cal": [{key: int}, ...]} (StartCalendarInterval、 key が無い = どれでも) /
    {"interval": 秒} (StartInterval) / None (予定が無い = RunAtLoad や KeepAlive だけの job)。"""
    if not isinstance(plist, dict):
        return None
    sci = plist.get("StartCalendarInterval")
    if isinstance(sci, dict):
        sci = [sci]
    if isinstance(sci, list):
        cal = [{k: int(e[k]) for k in _CAL_KEYS if isinstance(e.get(k), int)} for e in sci if isinstance(e, dict)]
        if cal:
            return {"cal": cal}
    si = plist.get("StartInterval")
    if isinstance(si, int) and si > 0:
        return {"interval": si}
    return None


def last_fire_before(schedule: dict | None, t: float, max_days: int = 400) -> float | None:
    """予定で、 時刻 t 以前の最後の起動予定 (epoch。 この機械の local time で読む)。 該当なし = None。
    StartInterval は起動の時刻が分からないので t - interval を返す (= その幅の中に 1 回は run があるはず)。
    Day と Weekday が両方あるときは cron と同じくどちらかが合えば起動する。"""
    if not schedule:
        return None
    if schedule.get("interval"):
        return t - schedule["interval"]
    import datetime as _dt
    end = _dt.datetime.fromtimestamp(t)
    best = None
    for e in schedule.get("cal") or []:
        hours = sorted([e["Hour"]] if "Hour" in e else range(24), reverse=True)
        mins = sorted([e["Minute"]] if "Minute" in e else range(60), reverse=True)
        for back in range(max_days + 1):
            day = (end - _dt.timedelta(days=back)).date()
            if "Month" in e and e["Month"] != day.month:
                continue
            dom = "Day" in e and e["Day"] == day.day
            dow = "Weekday" in e and e["Weekday"] % 7 == day.isoweekday() % 7   # launchd は 0 と 7 が日曜
            if "Day" in e and "Weekday" in e:
                if not (dom or dow):
                    continue
            elif ("Day" in e and not dom) or ("Weekday" in e and not dow):
                continue
            hit = next((c for h in hours for m in mins
                        for c in [_dt.datetime(day.year, day.month, day.day, h, m)] if c <= end), None)
            if hit is not None:
                ts = hit.timestamp()
                best = ts if best is None or ts > best else best
                break
    return best


def missed_fire(schedule: dict | None, log_mtime: float | None, now: float, since: float | None = None,
                grace_h: float = MISSED_GRACE_H) -> float | None:
    """予定の run の分の log が無ければ、 その予定の時刻 (epoch)。 有る / 判定できない = None。
    - 予定の時刻から grace_h 時間以上たった run だけを見る (= 実行中の run を「無い」 と言わない)
    - since (その機械が本番になった時刻など) より前の予定は見ない (= その機械が走らせる番でなかった run)
    - log の更新が予定の時刻 (- 丸め) 以後なら、 その run かそれより後の run が書いた"""
    fire = last_fire_before(schedule, now - grace_h * 3600)
    if fire is None or (since is not None and fire < since):
        return None
    if log_mtime is not None and log_mtime >= fire - MISSED_SLACK_S:
        return None
    return fire


def logged_in_email(config_dir: str, claude: str = "claude", timeout: int = 8) -> str:
    """config dir が今 claude.ai でログイン済みなら email (未ログイン・判定不能なら空文字)。 読むだけ。

    実在する絶対 path だけ問う (= 架空の dir で CLI を起動しない)。 env の API key は外して問う
    (混入すると auth status が別の答えを返す、 conventions/remote-control-server.md#local-auth-triage)。"""
    if not config_dir.startswith("/") or not os.path.isdir(config_dir):
        return ""
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
    env["CLAUDE_CONFIG_DIR"] = config_dir
    try:
        cp = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=timeout, env=env)
        st = json.loads(cp.stdout)
    except Exception:
        return ""
    if st.get("loggedIn") and st.get("authMethod") == "claude.ai":
        return st.get("email") or "(email 不明)"
    return ""


def selftest() -> int:
    import tempfile
    ok = []

    def ck(name, cond):
        ok.append((name, bool(cond)))

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        pl = {"ProgramArguments": ["/bin/sh", "-c", 'export CLAUDE_CONFIG_DIR="/x/.claude-a"; exec claude -p x'],
              "StandardErrorPath": str(d / "custom.log")}
        (d / "custom.log").write_text("warn\nFailed to authenticate: OAuth session expired\n")
        ck("plist の StandardErrorPath を使う", job_log_path("j", pl, d) == d / "custom.log")
        ck("plist 無しは <log_dir>/<label>.log", job_log_path("j", None, d) == d / "j.log")
        ck("auth を拾う", failure_kind(d / "custom.log") == "auth")
        (d / "p.log").write_text("x\nPrompt is too long\n")
        ck("ptl を拾う", failure_kind(d / "p.log") == "ptl")
        (d / "ok.log").write_text("Not logged in (昔の run)\n" + "ok\n" * 8)
        ck("末尾の外の昔の失敗は拾わない", failure_kind(d / "ok.log") == "")
        ck("log 不在は空", failure_kind(d / "none.log") == "" and log_age_days(d / "none.log") is None)
        t0 = (d / "custom.log").stat().st_mtime
        ck("exit 0 + 直近 log が失敗 = hidden", hidden_failure(0, d / "custom.log", now=t0 + 3600))
        ck("exit 1 は hidden でない (= 普通の失敗)", not hidden_failure(1, d / "custom.log", now=t0 + 3600))
        ck("古い log は hidden にしない", not hidden_failure(0, d / "custom.log", now=t0 + 86400 * 10))
        ck("起動行の CLAUDE_CONFIG_DIR", config_dir_of(pl) == "/x/.claude-a")
        ck("EnvironmentVariables の CLAUDE_CONFIG_DIR",
           config_dir_of({"EnvironmentVariables": {"CLAUDE_CONFIG_DIR": "/y"}}) == "/y")
        ck("plist 無しは空", config_dir_of(None) == "")
        ck("架空 / 相対の dir は auth status を叩かない",
           logged_in_email("/nonexistent/.claude-z") == "" and logged_in_email("rel") == "")
        # 予定の run が log に残っていない (missed_fire)
        import datetime as _dt
        gated = {"ProgramArguments": ["/bin/sh", "-c", 'cd x && { python3 "$HOME/c/routine-host-gate.py" r l.json; }'
                                      ' && exec "/u/bin/claude" -p --model m "do it"'],
                 "StartCalendarInterval": {"Hour": 7, "Minute": 30}}
        ck("claude -p を起動する job", runs_claude_p(gated) and not runs_claude_p({"ProgramArguments": ["sh", "-c", "claude-p x"]}))
        ck("関門を通る job", is_gated(gated) and not is_gated(pl))
        ck("予定 (dict 1 つ)", schedule_of(gated) == {"cal": [{"Minute": 30, "Hour": 7}]})
        ck("予定 (list / interval / 無し)",
           schedule_of({"StartCalendarInterval": [{"Hour": 7, "Minute": 10}, {"Hour": 13, "Minute": 10}]})
           == {"cal": [{"Minute": 10, "Hour": 7}, {"Minute": 10, "Hour": 13}]}
           and schedule_of({"StartInterval": 3600}) == {"interval": 3600} and schedule_of({"RunAtLoad": True}) is None)
        T = lambda *a: _dt.datetime(*a).timestamp()
        daily = {"cal": [{"Hour": 7, "Minute": 30}]}
        ck("毎日の最後の予定 (当日の前)", last_fire_before(daily, T(2030, 1, 5, 7, 0)) == T(2030, 1, 4, 7, 30))
        ck("毎日の最後の予定 (当日の後)", last_fire_before(daily, T(2030, 1, 5, 9, 0)) == T(2030, 1, 5, 7, 30))
        twice = {"cal": [{"Hour": 7, "Minute": 10}, {"Hour": 13, "Minute": 10}]}
        ck("1 日 2 回は遅い方", last_fire_before(twice, T(2030, 1, 5, 14, 0)) == T(2030, 1, 5, 13, 10))
        monthly = {"cal": [{"Day": 1, "Hour": 3, "Minute": 0}]}
        ck("毎月 1 日", last_fire_before(monthly, T(2030, 1, 20, 0, 0)) == T(2030, 1, 1, 3, 0))
        weekly = {"cal": [{"Weekday": 0, "Hour": 6, "Minute": 0}]}   # 2030-01-06 は日曜
        ck("毎週日曜 (0)", last_fire_before(weekly, T(2030, 1, 9, 0, 0)) == T(2030, 1, 6, 6, 0))
        ck("日曜は 7 でも同じ", last_fire_before({"cal": [{"Weekday": 7, "Hour": 6, "Minute": 0}]}, T(2030, 1, 9)) == T(2030, 1, 6, 6, 0))
        ck("毎時 (Minute だけ)", last_fire_before({"cal": [{"Minute": 5}]}, T(2030, 1, 5, 9, 3)) == T(2030, 1, 5, 8, 5))
        now = T(2030, 1, 5, 12, 0)
        ck("予定の後に log がある = 残っている", missed_fire(daily, T(2030, 1, 5, 8, 10), now) is None)
        ck("予定の後に log が無い = その予定", missed_fire(daily, T(2030, 1, 4, 8, 10), now) == T(2030, 1, 5, 7, 30))
        ck("log が一度も無い = その予定", missed_fire(daily, None, now) == T(2030, 1, 5, 7, 30))
        ck("予定から grace 内は見ない (実行中)", missed_fire(daily, T(2030, 1, 4, 8, 10), T(2030, 1, 5, 9, 0)) is None
           and missed_fire(daily, T(2030, 1, 4, 8, 10), T(2030, 1, 5, 10, 31)) == T(2030, 1, 5, 7, 30))
        ck("since より前の予定は見ない", missed_fire(daily, None, now, since=T(2030, 1, 5, 8, 0)) is None)
        ck("log の丸め (予定の 6 分前まで) は残っている扱い", missed_fire(daily, T(2030, 1, 5, 7, 25), now) is None)
        ck("予定が無い job は判定しない", missed_fire(None, None, now) is None)
        ck("StartInterval = 幅の中に log", missed_fire({"interval": 3600}, now - 3.5 * 3600, now) is None
           and missed_fire({"interval": 3600}, now - 5 * 3600, now) is not None)
        with open(d / "j.plist", "wb") as fh:
            plistlib.dump(pl, fh)
        ck("load_plist", (load_plist(d / "j.plist") or {}).get("StandardErrorPath") == str(d / "custom.log"))
        ck("load_plist 不在は None", load_plist(d / "no.plist") is None)
    for name, c in ok:
        print(f"  {'PASS' if c else 'FAIL'}  {name}")
    n = sum(1 for _, c in ok if c)
    print(f"launchd_job_log selftest: {n}/{len(ok)} passed")
    return 0 if n == len(ok) else 1


if __name__ == "__main__":
    import sys
    sys.exit(selftest() if "--selftest" in sys.argv else 0)
