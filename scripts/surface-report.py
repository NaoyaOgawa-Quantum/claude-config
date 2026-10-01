#!/usr/bin/env python3
"""surface-report.py — 通知を押した先に開く「いま何が鳴っているか」 の 1 枚を作る (surface の行 + 公開ページの見張り + 直近に出した通知を HTML 1 枚に)

正本 = conventions/macos-clickable-notifications.md (#click-target-contract / #click-target-contains-the-notification /
#click-target-page-design / #notification-body-must-be-ranked)。 頁の描画 = lib/ledger_page.py。

この engine が持つもの: 行の重大度・並べ方・節の組み方・見張りと控えの読み方・selftest。
呼ぶ側 (下の層) が持つもの: どの surface をどの順に・どの名前で出すか、 見張りの台帳の場所 = `--config` の JSON。

何を出すか (上から):
  0a. 公開ページの告知で未確認のもの = 台帳ごとに `web-page-watch.py --surface --json` をその場で読む
      (state を読むだけ・network に出ない。 ここで巡回すると定期実行の側が通知しなくなる =
      public-page-watch.md#surface-reads-state-only)。 行ごとにそのページへの link
  0b. 直近に出した通知 = `claude-notify.sh` の控え (既定 24 時間・新しい順に 5 件、 同じ文は 1 回)
  1.  鳴っている行 (先頭の marker が重大度) を **重大度 → surface の優先順 → file 内の順** で
  2.  期限の台帳 (config の `digest_stem` の surface) を 1 項目 1 行に (字下げ = 項目、 字下げなし = 見出し)
  3.  残りの surface を折りたたみで全部

なぜ 0a / 0b が先頭か: click で applet に渡るのは「起こされた」 だけで、 どの通知が押されたかは渡らない。
  1〜3 は surface dir の file = それを書いた時点 (session の開始など) の写しなので、 定期実行が session の外で
  見つけた変化はそこに無い。 写しだけで頁を作ると、 通知を押しても頁のどこにもその文が無い (実測)。
  押された通知の文 (0b) と、 その行き先 (0a) を、 写しを経由せずに先頭へ置く。 無ければ節ごと出さない。
  0a が読めなかったら黙らずに ⚠️ の 1 行を出す (= 「告知なし」 と「読めていない」 を区別する)。

config (JSON、 すべて任意。 `~` は展開する):
  priority            surface の stem の優先順 (無いものは後ろにアルファベット順)
  labels              stem → 人に見せる名前
  digest_stem         期限の台帳として 1 行ずつ表にする surface の stem (無ければ節を出さない)
  page_watch_ledgers  web-page-watch の台帳の path の list
  surface_dir         既定 ~/.claude/surface
  report_path         既定 ~/.claude/state/claude-reminder-report.html (surface dir に置かない =
                      surface/*.txt を glob して読む側の入力に混ざらないように)
  notify_log          既定 ~/.claude/state/claude-notify-log.tsv (claude-notify.sh と同じ既定)
  recent_hours / recent_max   0b の窓 (既定 24 / 5)
  title               頁の題 (既定「いま鳴っているもの」)
  footer_html         脚注に足す HTML (全件の一覧の入口など)
  critical_marks / warn_marks   重大度の marker (既定 🚨 🔴 ❗ / ⚠️ 🔥。 通知本文を選ぶ側と同じ集合に揃える)

usage:
  surface-report.py [--config C] --write      HTML を書いて path を出す (click の script から呼ぶ)
  surface-report.py [--config C] --open       書いて open する (人が手で見たいとき。 試験では使わない = 画面が開く)
  surface-report.py [--config C] --top N      通知本文用: 優先順の上位 N 行を stdout へ
  surface-report.py [--config C] --selftest   合成データだけで検査 (config を渡せば、 その形も検査する)

env (selftest と試験用): CLAUDE_SURFACE_DIR / CLAUDE_REPORT_PATH / CLAUDE_NOTIFY_LOG が config より優先、
  CLAUDE_REPORT_WEBWATCH=0 で 0a を読まない。
fail-open: --write の失敗は stderr に 1 行で exit 0 (通知の経路を止めない)。 config が読めない時は既定値で作り、
  頁の先頭に ⚠️ を出す。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from ledger_page import parse_item, render_page  # noqa: E402

WEBWATCH_ENGINE = HERE / "web-page-watch.py"

DEFAULTS: dict = {
    "priority": [],
    "labels": {},
    "digest_stem": None,
    "page_watch_ledgers": [],
    "surface_dir": "~/.claude/surface",
    "report_path": "~/.claude/state/claude-reminder-report.html",
    "notify_log": "~/.claude/state/claude-notify-log.tsv",
    "recent_hours": 24,
    "recent_max": 5,
    "title": "いま鳴っているもの",
    "footer_html": "",
    "critical_marks": ["🚨", "🔴", "❗"],
    "warn_marks": ["⚠️", "🔥"],
}
SOON_MARKS = ("⏰", "🎫", "📥")


def load_config(path: str | None) -> tuple[dict, str | None]:
    """(config, 読めなかった理由 or None)。 知らない key は理由として返す (= 綴りの誤りを黙らせない)。"""
    cfg = dict(DEFAULTS)
    if not path:
        return cfg, None
    try:
        raw = json.loads(Path(os.path.expanduser(path)).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return cfg, f"config を読めない ({path}: {type(e).__name__})"
    if not isinstance(raw, dict):
        return cfg, f"config が object でない ({path})"
    unknown = sorted(k for k in raw if k not in DEFAULTS and not k.startswith("_"))
    cfg.update({k: v for k, v in raw.items() if k in DEFAULTS})
    return cfg, (f"config に知らない key: {', '.join(unknown)} ({path})" if unknown else None)


def _path(cfg: dict, key: str, env: str) -> Path:
    return Path(os.path.expanduser(os.environ.get(env) or cfg[key]))


def severity(line: str, cfg: dict) -> str | None:
    s = line.lstrip()
    if s.startswith(tuple(cfg["critical_marks"])):
        return "CRITICAL"
    if s.startswith(tuple(cfg["warn_marks"])):
        return "WARN"
    return None


def read_surfaces(sdir: Path, cfg: dict) -> list[dict]:
    """surface/*.txt を優先順に読む。 各 dict = {stem,label,header,body,lines,mtime}。"""
    prio = list(cfg["priority"])
    labels = cfg["labels"]
    out: list[dict] = []
    try:
        files = [p for p in sdir.glob("*.txt") if p.is_file()]
    except Exception:  # noqa: BLE001
        return out
    files.sort(key=lambda p: (prio.index(p.stem) if p.stem in prio else len(prio), p.stem))
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        lines = text.splitlines()
        header, body = "", lines
        if lines and lines[0].startswith("#"):
            header = lines[0].lstrip("# ").strip()
            body = lines[1:]
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except Exception:  # noqa: BLE001
            mtime = None
        out.append({"stem": p.stem, "label": labels.get(p.stem, p.stem), "header": header,
                    "body": "\n".join(body).strip("\n"), "lines": lines, "mtime": mtime})
    return out


def findings(surfaces: list[dict], cfg: dict) -> list[dict]:
    """鳴っている行を 重大度 → surface 優先順 → file 内の出現順 で並べる。

    glob 順 (= アルファベット順) の 1 行目を取ると、 締切を抱えたまま無関係な台帳の定期点検の行が
    先頭に来る (実測。 #notification-body-must-be-ranked)。
    """
    items: list[dict] = []
    for si, s in enumerate(surfaces):
        for li, line in enumerate(s["lines"]):
            sev = severity(line, cfg)
            if sev:
                items.append({"sev": sev, "text": line.strip(), "stem": s["stem"], "label": s["label"],
                              "rank": (0 if sev == "CRITICAL" else 1, si, li)})
    items.sort(key=lambda d: d["rank"])
    return items


def digest_rows(surfaces: list[dict], cfg: dict) -> list[dict]:
    """期限の台帳の surface を「見出し」 と「項目」 に分ける (= 字下げで区別する)。"""
    stem = cfg.get("digest_stem")
    d = next((s for s in surfaces if stem and s["stem"] == stem), None)
    if not d:
        return []
    rows: list[dict] = []
    for line in d["lines"]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            rows.append(dict(parse_item(line), kind="item"))
        else:
            rows.append({"kind": "head", "title": line.strip()})
    return rows


# ---------------------------------------------------------------------------
# 写しを経由しない 2 節 (= 押された通知の文と、 その行き先)
# ---------------------------------------------------------------------------
def page_watch_items(ledgers: list[str]) -> list[dict]:
    """台帳ごとに web-page-watch の --surface --json を読む。 読めなければ ⚠️ の item を 1 つ返す。"""
    if os.environ.get("CLAUDE_REPORT_WEBWATCH") == "0":
        return []
    out: list[dict] = []
    for led in ledgers:
        lp = Path(os.path.expanduser(led))
        if not lp.exists():
            out.append({"kind": "unreadable", "mark": "⚠️", "line": f"⚠️ 見張りの台帳が無い ({led})"})
            continue
        try:
            r = subprocess.run([sys.executable, str(WEBWATCH_ENGINE), "--ledger", str(lp), "--surface", "--json"],
                               capture_output=True, text=True, timeout=20, check=False)
            out.extend(json.loads(r.stdout or "[]"))
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            out.append({"kind": "unreadable", "mark": "⚠️",
                        "line": f"⚠️ 公開ページの見張りの状態を読めなかった ({lp.name}: {type(e).__name__})"})
    return out


def page_watch_rows(items: list[dict]) -> list[dict]:
    """見張りの item を表の行に。 変化は本文 (今すぐやることまで) + そのページへの link。"""
    rows: list[dict] = []
    for it in items:
        mark = it.get("mark") or ""
        title = it.get("message") or (it.get("line") or "")[len(mark):].strip()
        date = ""
        try:
            if it.get("at"):
                at = datetime.fromisoformat(str(it["at"]))
                date = f"{at.month}/{at.day} {at:%H:%M}"
        except ValueError:
            pass
        rows.append({"mark": mark, "delta": "", "days": None, "date": date, "title": title, "src": "",
                     "ident": it.get("id") or "", "acct": "", "self_act": False, "raw": it.get("line") or "",
                     "tone": "crit" if it.get("kind") == "change" else "warn",
                     "href": it.get("url") or "", "href_label": "ページを開く"})
    return rows


def recent_notification_rows(log: Path, hours: float, limit: int, now: float | None = None) -> list[dict]:
    """claude-notify.sh の控え (epoch <tab> title <tab> body) から、 窓の中を新しい順に (同じ文は 1 回)。"""
    now = time.time() if now is None else now
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for ln in reversed(lines):
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        try:
            ts = float(parts[0])
        except ValueError:
            continue
        if now - ts > hours * 3600:
            break
        title, body = parts[1].strip(), (parts[2].strip() if len(parts) > 2 else "")
        if (title, body) in seen:
            continue
        seen.add((title, body))
        t = datetime.fromtimestamp(ts)
        rows.append({"mark": "", "delta": t.strftime("%H:%M"), "days": None, "date": f"{t.month}/{t.day}",
                     "title": f"{title} — {body}" if body else title, "src": "", "ident": "", "acct": "",
                     "self_act": False, "raw": ln, "tone": "calm"})
        if len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------------------
# 頁の組み立て
# ---------------------------------------------------------------------------
def _tone(mark: str, cfg: dict) -> str:
    if mark in cfg["critical_marks"]:
        return "crit"
    if mark in cfg["warn_marks"]:
        return "warn"
    return "soon" if mark in SOON_MARKS else "calm"


def build_html(cfg: dict, config_error: str | None = None) -> str:
    surfaces = read_surfaces(_path(cfg, "surface_dir", "CLAUDE_SURFACE_DIR"), cfg)
    items = findings(surfaces, cfg)
    n_crit = sum(1 for i in items if i["sev"] == "CRITICAL")

    rows = digest_rows(surfaces, cfg)
    only = [r for r in rows if r.get("kind") == "item"]
    n_over = sum(1 for r in only if isinstance(r.get("days"), int) and r["days"] < 0)
    n_today = sum(1 for r in only if r.get("days") == 0)
    n_week = sum(1 for r in only if isinstance(r.get("days"), int) and 0 < r["days"] <= 7)

    fire_rows = [dict(parse_item(i["text"]), tone="crit" if i["sev"] == "CRITICAL" else "warn", **{"from": i["label"]})
                 for i in items]
    ledger_rows = [r if r.get("kind") == "head" else dict(r, tone=_tone(r.get("mark", ""), cfg)) for r in rows]
    blocks = []
    for s in surfaces:
        if s["stem"] == cfg.get("digest_stem") or not s["body"].strip():
            continue
        n = sum(1 for ln in s["lines"] if severity(ln, cfg))
        blocks.append({"label": s["label"], "badge": n or "",
                       "when": s["mtime"].strftime("%-m/%-d %H:%M") if s["mtime"] else "",
                       "header": s["header"], "text": s["body"], "open": bool(n)})

    lead: list[dict] = []
    if config_error:
        lead.append({"kind": "rows", "heading": "頁の設定", "rows": [
            {"mark": "⚠️", "delta": "", "days": None, "date": "", "title": config_error, "tone": "warn"}]})
    ww = page_watch_rows(page_watch_items(cfg["page_watch_ledgers"]))
    if ww:
        lead.append({"kind": "rows", "heading": "公開ページの告知 — 今すぐ対応",
                     "note": f"{len(ww)} 件 (確認するまで出続ける)", "rows": ww})
    recent = recent_notification_rows(_path(cfg, "notify_log", "CLAUDE_NOTIFY_LOG"),
                                      float(cfg["recent_hours"]), int(cfg["recent_max"]))
    if recent:
        lead.append({"kind": "rows", "heading": "直近に出した通知",
                     "note": f"{cfg['recent_hours']} 時間以内・新しい順", "rows": recent})

    sections = lead + [{"kind": "rows", "heading": "鳴っている finding",
                        "note": f"重 {n_crit} / 警 {len(items) - n_crit}", "rows": fire_rows,
                        "empty": "鳴っているものはありません"}]
    if cfg.get("digest_stem"):
        sections.append({"kind": "rows", "heading": cfg["labels"].get(cfg["digest_stem"], cfg["digest_stem"]),
                         "note": f"{len(only)} 件", "rows": ledger_rows,
                         "empty": "surface がまだ書かれていません"})
    sections.append({"kind": "raw", "heading": "surface 全文", "blocks": blocks,
                     "empty": "ほかの surface はありません。"})
    footer = ("この頁は通知を押すたびに作り直されます (元 = surface の file = それを書いた時点の写し。 "
              "先頭の「公開ページの告知」 と「直近に出した通知」 だけは押した時点の状態)。")
    if cfg.get("footer_html"):
        footer += " " + cfg["footer_html"]
    return render_page(cfg["title"], stamp=datetime.now().strftime("%-m/%-d (%a) %H:%M"),
                       stats=[(n_over, "超過", "over"), (n_today, "今日", "today"), (n_week, "7日以内", "")],
                       sections=sections, footer_html=footer)


def write_report(cfg: dict, config_error: str | None = None) -> Path:
    out = _path(cfg, "report_path", "CLAUDE_REPORT_PATH")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(cfg, config_error), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# selftest (合成データだけ)
# ---------------------------------------------------------------------------
def _selftest(config_path: str | None) -> int:
    import tempfile

    ok = fail = 0

    def check(desc: str, cond: bool) -> None:
        nonlocal ok, fail
        print(f"[{'PASS' if cond else 'FAIL'}] {desc}")
        ok, fail = ok + bool(cond), fail + (not cond)

    if config_path:
        _, err = load_config(config_path)
        check(f"渡された config が読めて、 知らない key が無い ({config_path})", err is None)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        sdir = tdp / "surface"
        sdir.mkdir()
        (sdir / "alpha-feedback.txt").write_text("# 点検\n  ⚠️  定期点検の期限 6 件\n", encoding="utf-8")
        (sdir / "ledger.txt").write_text(
            "# 期限\n📋 期限の近い義務 2 件\n  🔴 -11d 9/9 返事をする 🙋\n  ⏰ +4d 9/24 様式を出す\n", encoding="utf-8")
        nlog = tdp / "notify-log.tsv"
        cfg_file = tdp / "cfg.json"
        cfg_file.write_text(json.dumps({
            "priority": ["ledger"], "labels": {"ledger": "期限の台帳"}, "digest_stem": "ledger",
            "surface_dir": str(sdir), "report_path": str(tdp / "r.html"), "notify_log": str(nlog),
            "footer_html": "見本の脚注"}), encoding="utf-8")
        for k in ("CLAUDE_SURFACE_DIR", "CLAUDE_REPORT_PATH", "CLAUDE_NOTIFY_LOG"):
            os.environ.pop(k, None)
        os.environ["CLAUDE_REPORT_WEBWATCH"] = "0"   # 実機の見張りの state を読まない
        cfg, err = load_config(str(cfg_file))
        check("config を読める", err is None and cfg["digest_stem"] == "ledger")
        _, err2 = load_config(str(tdp / "missing.json"))
        check("読めない config は理由を返す (既定値で作り続ける)", bool(err2))
        (tdp / "typo.json").write_text('{"priorty": []}', encoding="utf-8")
        check("知らない key は理由として返す (綴りの誤りを黙らせない)",
              "priorty" in (load_config(str(tdp / "typo.json"))[1] or ""))

        surfaces = read_surfaces(sdir, cfg)
        check("優先順が glob 順を上書きする", surfaces[0]["stem"] == "ledger")
        items = findings(surfaces, cfg)
        check("finding は 2 件 (⏰ は拾わない)", len(items) == 2)
        check("最上位は CRITICAL の台帳の行 (= 定期点検の行が先頭に来ない)",
              items[0]["sev"] == "CRITICAL" and "返事をする" in items[0]["text"])
        check("台帳の見出しと項目を字下げで分ける",
              [r["kind"] for r in digest_rows(surfaces, cfg)] == ["head", "item", "item"])

        t = write_report(cfg).read_text(encoding="utf-8")
        check("HTML に CRITICAL 行と finding でない ⏰ の項目が入る", "返事をする" in t and "様式を出す" in t)
        check("超過の件数が出る", "<b>1</b><span>超過</span>" in t)
        check("台帳の節の見出しは labels の名前", "<h2>期限の台帳" in t)
        check("脚注に config の footer_html が足される", "見本の脚注" in t)
        check("控えも見張りの告知も無ければ、 先頭の 2 節は出ない",
              "<h2>直近に出した通知" not in t and "<h2>公開ページの告知" not in t)

        now = time.time()
        nlog.write_text(f"{now - 90000:.0f}\t古い通知\t25 時間前\n"
                        f"{now - 600:.0f}\tページが更新された\t見本の議案ページ が変わった\n"
                        f"{now - 300:.0f}\tページが更新された\t見本の議案ページ が変わった\n"
                        f"{now - 60:.0f}\t予定の重なり\t明日 2 件\n", encoding="utf-8")
        rec = recent_notification_rows(nlog, 24, 5, now)
        check("控えは窓の中だけ・新しい順・同じ文は 1 回",
              [r["title"].split(" — ")[0] for r in rec] == ["予定の重なり", "ページが更新された"])
        check("控えの上限件数を守る", len(recent_notification_rows(nlog, 24, 1, now)) == 1)
        t = write_report(cfg).read_text(encoding="utf-8")
        check("写しに無い通知の文が頁に出る (= 押した文が必ず在る)",
              "見本の議案ページ が変わった" in t and "古い通知" not in t)
        check("直近の通知は finding より前",
              "<h2>直近に出した通知" in t and t.index("<h2>直近に出した通知") < t.index("<h2>鳴っている finding"))

        ww = page_watch_rows([
            {"kind": "change", "mark": "🔔", "id": "sample-gian", "url": "https://example.org/gian.html",
             "label": "見本の議案ページ", "message": "見本の議案ページ が変わった → 今すぐ: 中身を見る [TODO-1]",
             "at": "2031-01-02T03:04:05+09:00", "line": "🔔 見本 ... --ack sample-gian"},
            {"kind": "unreadable", "mark": "⚠️", "id": "b", "url": "https://example.org/b", "label": "B",
             "message": "B を 3 回続けて読めていない (timeout)", "at": None, "line": "⚠️ B を ... — https://example.org/b"},
            {"kind": "unreadable", "mark": "⚠️", "line": "⚠️ 公開ページの見張りの状態を読めなかった (x: ValueError)"}])
        check("変化の行は本文 + そのページへの link + 気づいた時刻",
              ww[0]["href"] == "https://example.org/gian.html" and "今すぐ: 中身を見る" in ww[0]["title"]
              and ww[0]["date"] == "1/2 03:04" and ww[0]["tone"] == "crit")
        check("読めない行も link を持つ (url がある時)", ww[1]["href"] == "https://example.org/b" and ww[1]["tone"] == "warn")
        check("engine が読めなかった item も落とさない", "読めなかった" in ww[2]["title"])
        os.environ["CLAUDE_REPORT_WEBWATCH"] = "1"
        cfg_missing = dict(cfg, page_watch_ledgers=[str(tdp / "no-ledger.json")])
        check("台帳が無ければ ⚠️ を出す (黙って空にしない)",
              "見張りの台帳が無い" in build_html(cfg_missing))
        os.environ["CLAUDE_REPORT_WEBWATCH"] = "0"
        check("config が読めない時は頁の先頭に ⚠️", "<h2>頁の設定" in build_html(cfg, "config を読めない (x)"))

        nlog.unlink()
        for f in sdir.glob("*.txt"):
            f.unlink()
        check("何も無くても HTML を書ける", "鳴っているものはありません" in write_report(cfg).read_text(encoding="utf-8"))

    print(f"\n=== selftest: {ok} passed, {fail} failed ===")
    return 0 if fail == 0 else 1


def main(argv: list[str]) -> int:
    config_path = None
    if "--config" in argv:
        i = argv.index("--config")
        config_path = argv[i + 1] if i + 1 < len(argv) else None
    if "--selftest" in argv:
        return _selftest(config_path)
    cfg, err = load_config(config_path)
    if "--top" in argv:
        try:
            n = int(argv[argv.index("--top") + 1])
        except (IndexError, ValueError):
            n = 1
        for it in findings(read_surfaces(_path(cfg, "surface_dir", "CLAUDE_SURFACE_DIR"), cfg), cfg)[:n]:
            print(it["text"])
        return 0
    try:
        out = write_report(cfg, err)
    except Exception as e:  # noqa: BLE001 (fail-open: 通知の経路を止めない)
        print(f"surface-report: 書けませんでした: {e}", file=sys.stderr)
        return 0
    if "--open" in argv:
        subprocess.run(["/usr/bin/open", str(out)], check=False)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
