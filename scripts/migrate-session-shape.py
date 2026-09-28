#!/usr/bin/env python3
"""migrate-session-shape.py — SESSION.md の日付つき節を SESSION-archive へ verbatim MOVE し、 「案件ごとの現在地 + 正本への link」 の形へ一括で寄せる (既定 dry-run)

なぜ: SESSION.md の形の契約 (CONVENTIONS.md#session-no-durable-record、 gate = check-session-shape.py) を入れた時点で、 既存の
SESSION.md の多くは「## 2026-09-28 — 何をした」 の節 (= 変更履歴の形) を積んでいる。 gate は追加行と行数の成長しか見ないので
既存分は止まらないが、 次に触る commit で 200 行超の file は止まり、 そのたびに手で組み直すことになる。 既存分は機械で移す
(行単位 + 読み直し照合、 削除ゼロ = verbatim MOVE)。

規則 (file ごと):
  1. 先頭の見出し (`# …`) から最初の `## ` までを preamble として残す。
  2. top-level `## ` 節のうち見出しに日付 (20YY-MM[-DD]) を含む節 = 移す候補。 ただし日付が今日より後 (= 期限) の節と、
     未完了の `[ ]` を持つ節は記録でなく現在地 = 移さない (`### ` 小節も同じ。 見出しの期限は gate が止めるので人が本文へ移す)。 `### ` 以下は親の節と一緒に動く。
     日付を含まない `## ` 節の中に日付つきの `### ` 小節が並ぶ形 (「## 現在の状態」 の下に「### 直近の更新 (日付)」 ×N) も同じ規則で
     小節ごとに移す (日付を含まない小節が無ければ最新の 1 つを `### 現在地` として残す)。 見るのは `##` と `###` の 2 段まで。
  3. 日付を含まない `## ` 節 (Open items / 次のステップ / 現在の再開点 など) は残す (順序も保つ)。
  4. 日付を含まない節が 1 つも無い file では、 最も新しい日付の節 1 つを `## 現在地` として残す (元の見出しは節の 1 行目に
     「(直近の節: …)」 で残す = 再開に要る状態を消さない)。 日付を含まない節が在れば、 日付つきの節は全部移す。
  5. 移す節は archive へ verbatim (順序そのまま) = `SESSION-archive.md` (無ければ作る) か、 `SESSION-archive/` dir だけが在る repo では
     `SESSION-archive/<日付>-session-shape-move.md`。 archive 側の見出しは「## <日付> SESSION.md の日付つき節を verbatim MOVE …」。
  6. preamble の直後に契約への pointer を 1 行 (`> 📌 …`) 足す (既に `session-no-durable-record` を含む行が在れば足さない)。
  7. 書いたら `git add` → check-session-shape.py --staged を通す (通らなければ元に戻して報告) → --commit で commit (明示 path) → --push。

前提 (満たさない repo は skip して理由を出す): git repo / SESSION.md が tracked で clean / archive path が clean / fetch して behind 0。

使い方:
  migrate-session-shape.py --repo DIR [--repo DIR …] [--apply] [--commit] [--push]
  migrate-session-shape.py --root ROOT --all [--exclude NAME …] [--apply] [--commit] [--push]   # ROOT/*/SESSION.md と ROOT/*/*/SESSION.md
  migrate-session-shape.py --selftest
  既定 = dry-run (何を移すかを出すだけ)。 --apply で file を書く、 --commit で commit、 --push で push。

限界: 日付を含まない節の中に溜まった経緯 (= 「現在状態」 の見出しの下に 200 行) は動かさない (形が同じなので機械で区別できない、
gate の行数の予算がその repo を次に触る commit で止める)。 見出しの日付の書式は 20YY-MM / 20YY-MM-DD だけ (和暦・「9/28」 は見ない)。
stdlib only。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATE_RE = re.compile(r"(?<!\d)(20\d{2})-(\d{2})(?:-(\d{2}))?(?!\d)")
H2_RE = re.compile(r"^## ")
RULE_DOC = "CONVENTIONS.md#session-no-durable-record"
BANNER = ("> 📌 SESSION.md = 案件ごとの現在地 + 正本への link (進んだら置き換える、 日付を見出しにした節・commit hash・messageId を置かない = "
          "層1 claude-config/{rule})。 日付つきの節は {arch} へ verbatim MOVE 済 ({today})。")


def _git(repo: Path, *args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=timeout, errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 99, str(exc)
    return r.returncode, (r.stdout + r.stderr)


def heading_date(text: str):
    m = DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
    try:
        return _dt.date(y, mo, d)
    except ValueError:
        return None


OPEN_BOX_RE = re.compile(r"^\s*[-*+]\s+\[ \]")


def record_date(section: list[str], today_d):
    """節の見出しの日付を「記録の日付」 として返す。 記録でない節 (= 現在地) は None。
    今日より後の日付 (= 期限。 例「(<未来の日付> 締切)」) の見出しと、 未完了の `[ ]` を持つ節は、 日付があっても現在地 = 移さない
    (見出しの期限の日付は gate が引き続き止めるので、 人が日付を本文へ移す)。"""
    d = heading_date(section[0])
    if d is None:
        return None
    if today_d is not None and d > today_d:
        return None
    if any(OPEN_BOX_RE.match(l) for l in section[1:]):
        return None
    return d


def _today_date(today: str):
    try:
        return _dt.date.fromisoformat(today)
    except ValueError:
        return None


def split_sections(lines: list[str], marker: str = "## ") -> tuple[list[str], list[list[str]]]:
    """preamble と `## ` 節の列に分ける (節 = 見出し行から次の `## ` の直前まで)。 marker = "### " で小節にも使う。"""
    idx = [i for i, l in enumerate(lines) if l.startswith(marker)]
    if not idx:
        return lines, []
    preamble = lines[: idx[0]]
    sections = []
    for k, i in enumerate(idx):
        j = idx[k + 1] if k + 1 < len(idx) else len(lines)
        sections.append(lines[i:j])
    return preamble, sections


def plan(text: str, today: str, arch_rel: str) -> dict | None:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    preamble, sections = split_sections(lines)
    td = _today_date(today)
    dated = [s for s in sections if record_date(s, td)]
    undated = [s for s in sections if not record_date(s, td)]
    def _has_nested_dated(sec):
        _, subs = split_sections(sec[1:], "### ")
        return any(record_date(x, td) for x in subs)
    if not dated and not any(_has_nested_dated(u) for u in undated):
        return None
    kept_current = None
    if not undated and dated:
        newest = max(dated, key=lambda s: (heading_date(s[0]), -dated.index(s)))
        kept_current = newest
        moved = [s for s in dated if s is not newest]
    else:
        moved = dated
    out: list[str] = list(preamble)
    while out and out[-1] == "":
        out.pop()
    if not any(RULE_DOC in l for l in out):
        out += ["", BANNER.format(rule=RULE_DOC, arch=arch_rel, today=today)]
    if kept_current is not None:
        body = kept_current[1:]
        out += ["", "## 現在地", "", f"(直近の節: {kept_current[0][3:].strip()} — 経緯は {arch_rel})"]
        out += body
    for s in undated:
        s = _lift_nested(s, moved, arch_rel, td)
        out += [""] + s if (out and out[-1] != "") else list(s)
    if not moved:
        return None  # 見出しの書き換えだけの変更は作らない (banner だけの commit を全 repo に撒かない)
    new_text = "\n".join(out).rstrip("\n") + "\n"
    arch_block = [f"## {today} SESSION.md の日付つき節を verbatim MOVE (形の契約 = 案件ごとの現在地、 層1 claude-config/{RULE_DOC}、 道具 = migrate-session-shape.py)", ""]
    for s in moved:
        arch_block += s + [""]
    return {"new_text": new_text, "archive_block": "\n".join(arch_block).rstrip("\n") + "\n",
            "moved": len(moved), "kept_current": kept_current is not None, "before": len(lines), "after": len(new_text.splitlines())}


def _lift_nested(section: list[str], moved: list[list[str]], arch_rel: str, td=None) -> list[str]:
    """日付を含まない ## 節の中の、 日付つき ### 小節を moved へ移し、 残りを返す (小節の順序は保つ)。
    記録でない小節 (期限の日付・未完了の [ ]) は record_date が None を返す = 現在地として残る。"""
    head, subs = split_sections(section[1:], "### ")
    dated = [x for x in subs if record_date(x, td)]
    if not dated:
        return section
    undated = [x for x in subs if not record_date(x, td)]
    keep = None
    if not undated:
        keep = max(dated, key=lambda x: (heading_date(x[0]), -dated.index(x)))
        if len(dated) == 1:
            return section  # 移すものが無い (見出しの書き換えだけ) = 触らない
    out = [section[0]] + head
    for x in subs:
        if record_date(x, td) and x is not keep:
            moved.append([f"### (from {section[0][3:].strip()}) " + x[0][4:]] + x[1:])
            continue
        if x is keep:
            out += ["### 現在地", "", f"(直近の小節: {x[0][4:].strip()} — 経緯は {arch_rel})"] + x[1:]
        else:
            out += x
    return out


def archive_target(repo: Path, today: str) -> Path:
    if (repo / "SESSION-archive.md").exists() or not (repo / "SESSION-archive").is_dir():
        return repo / "SESSION-archive.md"
    return repo / "SESSION-archive" / f"{today}-session-shape-move.md"


def write_archive(path: Path, block: str, repo_name: str) -> None:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        # 先頭の見出し (# …) と、 その直後の空行 / 引用行の後に差し込む (新しいものが上)
        lines = old.split("\n")
        ins = 0
        if lines and lines[0].startswith("# "):
            ins = 1
            while ins < len(lines) and (lines[ins] == "" or lines[ins].startswith(">")):
                ins += 1
        new = "\n".join(lines[:ins]).rstrip("\n") + ("\n\n" if ins else "") + block + "\n" + "\n".join(lines[ins:]).lstrip("\n")
        path.write_text(new.rstrip("\n") + "\n", encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# SESSION-archive — {repo_name}\n\n> 📦 SESSION.md から移した日付つき節 (grep 専用、 verbatim)。 現在地は SESSION.md。\n\n{block}", encoding="utf-8")


def _filter_of(repo: Path, rel: str) -> str:
    rc, out = _git(repo, "check-attr", "filter", "--", rel)
    val = out.strip().rsplit(": ", 1)[-1] if rc == 0 and out.strip() else "unspecified"
    return val or "unspecified"


def _encrypt_gap(repo: Path, arch_rel: str) -> str | None:
    """SESSION.md に filter (git-crypt など) が付いているのに、 移し先の archive に同じ filter が無ければ理由を返す。
    付いていない path へ移すと、 暗号化されていた中身が平文で commit される (実測: 平文の archive が push された)。"""
    f_s = _filter_of(repo, "SESSION.md")
    if f_s in ("unspecified", "unset"):
        return None
    f_a = _filter_of(repo, arch_rel)
    if f_a != f_s:
        return (f"SESSION.md は filter={f_s} (暗号化) なのに移し先 {arch_rel} は filter={f_a} = 平文で commit される。 "
                f".gitattributes で移し先にも同じ filter を付けて commit してから")
    return None


def process_repo(repo: Path, *, apply: bool, commit: bool, push: bool, today: str, gate: Path | None) -> str:
    name = repo.name
    sp = repo / "SESSION.md"
    if not sp.is_file():
        return f"skip {name}: SESSION.md 無し"
    rc, _ = _git(repo, "rev-parse", "--show-toplevel")
    if rc != 0:
        return f"skip {name}: git repo でない"
    rc, out = _git(repo, "status", "--porcelain", "--", "SESSION.md", "SESSION-archive.md", "SESSION-archive")
    if out.strip():
        return f"skip {name}: SESSION.md / archive が dirty"
    rc, out = _git(repo, "ls-files", "--error-unmatch", "SESSION.md")
    if rc != 0:
        return f"skip {name}: SESSION.md が untracked"
    arch = archive_target(repo, today)
    arch_rel = str(arch.relative_to(repo))
    gap = _encrypt_gap(repo, arch_rel)
    if gap:
        return f"skip {name}: {gap}"
    p = plan(sp.read_text(encoding="utf-8"), today, arch_rel)
    if p is None:
        return f"skip {name}: 日付つきの top-level 節が無い"
    summary = f"{name}: {p['before']} → {p['after']} 行、 移す節 {p['moved']}" + (" (直近の節を 現在地 として残す)" if p["kept_current"] else "") + f" → {arch_rel}"
    if not apply:
        return "dry-run " + summary
    rc, out = _git(repo, "fetch", "-q", timeout=25)
    if rc != 0:
        return f"skip {name}: fetch 失敗 ({out.strip()[:60]})"
    rc, out = _git(repo, "rev-list", "--count", "HEAD..@{u}")
    if rc == 0 and out.strip() not in ("", "0"):
        return f"skip {name}: behind {out.strip()} (pull してから)"
    before_arch = arch.read_text(encoding="utf-8") if arch.exists() else None
    sp.write_text(p["new_text"], encoding="utf-8")
    write_archive(arch, p["archive_block"], name)
    _git(repo, "add", "--", "SESSION.md", arch_rel)
    if gate is not None and gate.exists():
        r = subprocess.run([sys.executable, str(gate), "--staged", "--repo", str(repo)], capture_output=True, text=True)
        if r.returncode != 0:
            _git(repo, "reset", "-q", "--", "SESSION.md", arch_rel)
            _git(repo, "checkout", "--", "SESSION.md")
            if before_arch is None:
                arch.unlink(missing_ok=True)
            else:
                arch.write_text(before_arch, encoding="utf-8")
            return f"revert {name}: gate rc={r.returncode}: " + r.stdout.strip().splitlines()[0][:120] if r.stdout.strip() else f"revert {name}: gate rc={r.returncode}"
    if not commit:
        return "applied (staged) " + summary
    msg = (f"SESSION: 日付つきの節 {p['moved']} を {arch_rel} へ verbatim MOVE (形の契約 = 案件ごとの現在地、 層1 {RULE_DOC})\n\n"
           f"- {p['before']} → {p['after']} 行。 道具 = claude-config/scripts/migrate-session-shape.py\n\n"
           "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>")
    rc, out = _git(repo, "commit", "-q", "-m", msg, "--", "SESSION.md", arch_rel, timeout=120)
    if rc != 0:
        return f"commit 失敗 {name}: {out.strip()[-200:]}"
    if push:
        rc, out = _git(repo, "push", "-q", timeout=90)
        if rc != 0:
            return f"committed, push 失敗 {name}: {out.strip()[-120:]}"
        return "committed+pushed " + summary
    return "committed " + summary


def run_selftest() -> int:
    ok = True

    def check(c: bool, label: str) -> None:
        nonlocal ok
        print(f"  [{'PASS' if c else 'FAIL'}] {label}")
        ok = ok and c

    today = "2026-01-31"
    # plan: 日付のみの file → 直近の節を残す
    t = "# S\n\nintro\n\n## 2026-01-10: old\n\n- a\n\n## 2026-01-20 — new\n\n- b `abc1234`\n### sub (2026-01-20)\n- c\n"
    p = plan(t, today, "SESSION-archive.md")
    check(p is not None and p["moved"] == 1 and p["kept_current"], "日付のみの file: 直近 1 節を残し他を移す")
    check("## 現在地" in p["new_text"] and "2026-01-20 — new" in p["new_text"] and "## 2026-01-20" not in p["new_text"], "残す節の見出しは 現在地 になり元の見出しは行に残る")
    check("## 2026-01-10: old" in p["archive_block"] and "- a" in p["archive_block"], "archive に旧節が verbatim")
    check("session-no-durable-record" in p["new_text"], "契約への pointer 行が入る")
    # plan: 日付なしの節が在る → 全部移す、 順序保持
    t2 = "# S\n\n## 現在の再開点\n\n- x\n\n## 2026-01-05: log\n\n- y\n\n## Open items\n\n- [ ] z\n"
    p2 = plan(t2, today, "SESSION-archive.md")
    check(p2["moved"] == 1 and not p2["kept_current"] and "## 現在の再開点" in p2["new_text"] and "## Open items" in p2["new_text"]
          and p2["new_text"].index("現在の再開点") < p2["new_text"].index("Open items"), "日付なしの節が在れば日付つきは全部移し、 残りの順序を保つ")
    check(plan("# S\n\n## 現在地\n\n- a\n", today, "x") is None, "日付つき節が無ければ None")
    t3 = "# S\n\n## 現在の状態\n\nlead\n\n### 直近の更新 (2026-01-10: a)\n\n- a\n\n### 直近の更新 (2026-01-20: b)\n\n- b\n\n### 次の判定点\n\n- j\n\n## 残タスク\n\n- t\n"
    p3 = plan(t3, today, "SESSION-archive.md")
    check(p3 is not None and p3["moved"] == 2 and "### 直近の更新" not in p3["new_text"] and "### 次の判定点" in p3["new_text"]
          and "## 残タスク" in p3["new_text"] and "(from 現在の状態) 直近の更新 (2026-01-20: b)" in p3["archive_block"],
          "日付なし ## の中の日付つき ### 小節を移し、 日付なしの小節と後続の ## は残す")
    t4 = "# S\n\n## 現在の状態\n\n### 更新 (2026-01-10)\n\n- a\n\n### 更新 (2026-01-20)\n\n- b\n"
    p4 = plan(t4, today, "SESSION-archive.md")
    check(p4 is not None and p4["moved"] == 1 and "### 現在地" in p4["new_text"] and "- b" in p4["new_text"] and "- a" in p4["archive_block"],
          "日付つき ### だけなら最新の小節を 現在地 として残す")
    # 見出しの日付が記録の日付でない節 = 現在地 (移さない): 今日より後の日付 (期限) / 未完了の [ ] を持つ節
    t5 = "# S\n\n## 現在の再開点\n\n- x\n\n## 申請書の提出 (2026-06-30 締切)\n\n- 残 = 提出\n\n## 2026-01-05: log\n\n- y\n"
    p5 = plan(t5, today, "SESSION-archive.md")
    check(p5 is not None and p5["moved"] == 1 and "## 申請書の提出 (2026-06-30 締切)" in p5["new_text"]
          and "締切" not in p5["archive_block"] and "## 2026-01-05: log" in p5["archive_block"],
          "見出しの日付が今日より後 (期限) の節は現在地として残し、 過去の記録の節だけ移す")
    t6 = "# S\n\n## 現在の状態\n\n### 手続き (2026-01-10)\n\n- [x] 署名\n- [ ] 郵送\n\n### 更新 (2026-01-12)\n\n- done\n\n### 次\n\n- j\n"
    p6 = plan(t6, today, "SESSION-archive.md")
    check(p6 is not None and p6["moved"] == 1 and "- [ ] 郵送" in p6["new_text"] and "- [ ] 郵送" not in p6["archive_block"]
          and "- done" in p6["archive_block"],
          "未完了の [ ] を持つ節 (小節) は日付が過去でも現在地として残す")
    # end-to-end: 一時 repo で apply + gate + commit
    with tempfile.TemporaryDirectory(prefix="migrate-session-shape-") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        (repo / "SESSION.md").write_text(t, encoding="utf-8")
        (repo / "SESSION-archive").mkdir()
        (repo / "SESSION-archive" / "2025-12.md").write_text("# old\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
        gate = HERE / "check-session-shape.py"
        r0 = process_repo(repo, apply=False, commit=False, push=False, today=today, gate=gate)
        check(r0.startswith("dry-run") and "SESSION-archive/2026-01-31-session-shape-move.md" in r0, "dry-run は書かず、 dir 型の archive 先を選ぶ")
        check((repo / "SESSION.md").read_text(encoding="utf-8") == t, "dry-run で file は変わらない")
        r1 = process_repo(repo, apply=True, commit=True, push=False, today=today, gate=gate)
        check(r1.startswith("committed "), f"apply + gate + commit が通る: {r1[:80]}")
        arch = repo / "SESSION-archive" / "2026-01-31-session-shape-move.md"
        check(arch.exists() and "## 2026-01-10: old" in arch.read_text(encoding="utf-8"), "archive file が作られ旧節が在る")
        new = (repo / "SESSION.md").read_text(encoding="utf-8")
        check("## 現在地" in new and "abc1234" in new, "残した節の中身 (hash 行を含む既存行) はそのまま")
        st = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
        check(st.strip() == "", "commit 後は clean")
        r2 = process_repo(repo, apply=True, commit=True, push=False, today=today, gate=gate)
        check(r2.startswith("skip") and "無い" in r2, "2 回目は移すものが無く skip")
        # SESSION.md が暗号化 (filter 指定) で移し先が同じ filter でなければ、 書く前に止まる (平文の archive を作らない)
        repo3 = Path(tmp) / "repo3"
        repo3.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo3, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo3, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo3, check=True)
        (repo3 / ".gitattributes").write_text("SESSION.md filter=selftestcrypt\n", encoding="utf-8")
        (repo3 / "SESSION.md").write_text(t2, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo3, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo3, check=True)
        r5 = process_repo(repo3, apply=True, commit=True, push=False, today=today, gate=gate)
        check(r5.startswith("skip") and "平文" in r5 and not (repo3 / "SESSION-archive.md").exists()
              and (repo3 / "SESSION.md").read_text(encoding="utf-8") == t2,
              "SESSION.md が暗号化で移し先が平文なら、 何も書かずに止まる")
        (repo3 / ".gitattributes").write_text("SESSION.md filter=selftestcrypt\nSESSION-archive.md filter=selftestcrypt\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-q", "-am", "attr"], cwd=repo3, check=True)
        r6 = process_repo(repo3, apply=False, commit=False, push=False, today=today, gate=gate)
        check(r6.startswith("dry-run"), "移し先にも同じ filter があれば進む")
        # 既存の SESSION-archive.md に差し込む形 (見出しの直後)
        repo2 = Path(tmp) / "repo2"
        repo2.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo2, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=repo2, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo2, check=True)
        (repo2 / "SESSION.md").write_text(t2, encoding="utf-8")
        (repo2 / "SESSION-archive.md").write_text("# SESSION-archive — repo2\n\n> 📦 note\n\n## 2025-12-01 older\n\n- q\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo2, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo2, check=True)
        r3 = process_repo(repo2, apply=True, commit=False, push=False, today=today, gate=gate)
        a = (repo2 / "SESSION-archive.md").read_text(encoding="utf-8")
        check(r3.startswith("applied") and a.index("2026-01-31 SESSION.md") < a.index("## 2025-12-01 older") and a.startswith("# SESSION-archive — repo2\n\n> 📦 note\n"),
              "既存 archive では見出しと引用行の直後 (新しいものが上) に差し込む")
    print("migrate-session-shape selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--root", default=str(Path.home() / "Claude"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--today", default=_dt.date.today().isoformat())
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    repos = [Path(r).expanduser().resolve() for r in a.repo]
    if a.all:
        root = Path(a.root).expanduser()
        for sp in sorted(list(root.glob("*/SESSION.md")) + list(root.glob("*/*/SESSION.md"))):
            if sp.is_symlink():
                continue
            d = sp.parent
            if d.name in a.exclude or any(x in str(d.relative_to(root)) for x in a.exclude):
                continue
            repos.append(d.resolve())
    if not repos:
        ap.print_help()
        return 0
    gate = HERE / "check-session-shape.py"
    for repo in repos:
        print(process_repo(repo, apply=a.apply, commit=a.commit, push=a.push, today=a.today, gate=gate))
    return 0


if __name__ == "__main__":
    sys.exit(main())
