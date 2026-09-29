#!/usr/bin/env bash
# pre-commit-bib.test.sh — pre-commit-bib (全 repo 共通の git pre-commit) の配線 test: SESSION.md の形の gate と変数の直後の全角文字の gate が commit を止める / 通す / escape hatch で通る (hermetic)
#
# 正本: claude-config/scripts/pre-commit-bib.test.sh
# 実行: bash scripts/pre-commit-bib.test.sh (run-all-checks.sh が自動発見)
#
# 述語と閾値の SoT = check-session-shape.py docstring (selftest がそこを持つ)。 ここは**配線**の固定 =
# .git/hooks/pre-commit → pre-commit-bib の symlink を張った一時 repo で、 日付を見出しにした節を SESSION.md に足す commit が
# 止まる (exit ≠ 0 かつ engine の見出しが stderr に出る) / 案件の pointer 行は通る / CLAUDE_SESSION_SHAPE_GUARD=0 で通る
# (= 止めたのがこの gate だという証拠)。 個人層の chain hook は HOME を偽の dir にして外す (他 user と同じ状態で測る)。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/pre-commit-bib"
[ -f "$HOOK" ] || { echo "FAIL: not found: $HOOK"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 不在 — test 省略"; exit 0; }
command -v git >/dev/null 2>&1 || { echo "SKIP: git 不在 — test 省略"; exit 0; }

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  PASS  $1"; }
ng() { fail=$((fail+1)); echo "  FAIL  $1"; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/pre-commit-bib-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAKE_HOME="$TMP/home"; mkdir -p "$FAKE_HOME"
REPO="$TMP/repo"; mkdir -p "$REPO"
(
  cd "$REPO" && git init -q -b main && git config user.email t@example.invalid && git config user.name t \
  && ln -sf "$HOOK" .git/hooks/pre-commit \
  && printf '# S\n\n- 案件 A — 次 = X → [正本](DESIGN.md)\n' > SESSION.md && git add SESSION.md \
  && HOME="$FAKE_HOME" git commit -q -m init
) >/dev/null 2>&1 || { echo "FAIL: 一時 repo の初期化"; exit 1; }

try_commit() { # <file content> [env...] → stderr を $OUT に、 rc を返す
  local content="$1"; shift
  printf '%s' "$content" > "$REPO/SESSION.md"
  (cd "$REPO" && git add SESSION.md && env HOME="$FAKE_HOME" "$@" git commit -q -m t 2>"$TMP/err" >/dev/null)
  local rc=$?
  OUT="$(cat "$TMP/err")"
  (cd "$REPO" && git reset -q --hard HEAD) >/dev/null 2>&1
  return $rc
}

if try_commit $'# S\n\n## 2026-09-28 — 何をした\n- y\n'; then
  ng "日付の節を足す commit が通ってしまった"
else
  case "$OUT" in *"check-session-shape:"*) ok "日付の節を足す commit を pre-commit-bib が止める (engine の見出しつき)";; *) ng "止まったが engine の見出しが無い (別の gate?): $(printf '%s' "$OUT" | head -3)";; esac
fi

if try_commit $'# S\n\n- 案件 A — 次 = Y → [正本](DESIGN.md)\n'; then ok "案件の pointer 行の commit は通る"; else ng "pointer 行の commit が止まった: $(printf '%s' "$OUT" | head -3)"; fi

if try_commit $'# S\n\n## 2026-09-28 — 何をした\n' CLAUDE_SESSION_SHAPE_GUARD=0; then ok "escape hatch (CLAUDE_SESSION_SHAPE_GUARD=0) で通る = 止めたのはこの gate"; else ng "escape hatch でも止まる: $(printf '%s' "$OUT" | head -3)"; fi

# 暗号化の一致: SESSION.md に filter が付いた repo で、 filter の無い SESSION-archive.md を足す commit を止める
# (filter の driver は設定しない = 属性の食い違いだけで止まることを見る)。 CLAUDE_SESSION_CRYPT_GUARD=0 で通る = この gate が止めた証拠。
CREPO="$TMP/crepo"; mkdir -p "$CREPO"
(
  cd "$CREPO" && git init -q -b main && git config user.email t@example.invalid && git config user.name t \
  && ln -sf "$HOOK" .git/hooks/pre-commit \
  && printf 'SESSION.md filter=selftestcrypt\n' > .gitattributes \
  && printf '# S\n\n- 案件 A — 次 = X → [正本](DESIGN.md)\n' > SESSION.md && git add .gitattributes SESSION.md \
  && HOME="$FAKE_HOME" git commit -q -m init
) >/dev/null 2>&1 || { echo "FAIL: 暗号化の一時 repo の初期化"; exit 1; }
CINIT="$(git -C "$CREPO" rev-parse HEAD)"
try_archive() { # [env...] → stderr を $OUT に、 rc を返す
  printf '# SESSION-archive\n\n## 2026-01-01 — 移した節\n- x\n' > "$CREPO/SESSION-archive.md"
  (cd "$CREPO" && git add SESSION-archive.md && env HOME="$FAKE_HOME" "$@" git commit -q -m t 2>"$TMP/err" >/dev/null)
  local rc=$?
  OUT="$(cat "$TMP/err")"
  (cd "$CREPO" && git reset -q --hard "$CINIT" && git clean -qfd) >/dev/null 2>&1  # 通ってしまった commit も戻す
  return $rc
}
if try_archive; then
  ng "暗号化された SESSION.md の隣に平文の archive を足す commit が通ってしまった"
else
  case "$OUT" in *"check-session-shape:"*"archive-plaintext"*) ok "平文の archive を足す commit を pre-commit-bib が止める (engine の見出しつき)";; *) ng "止まったが engine の見出しが無い: $(printf '%s' "$OUT" | head -3)";; esac
fi
if try_archive CLAUDE_SESSION_CRYPT_GUARD=0; then ok "escape hatch (CLAUDE_SESSION_CRYPT_GUARD=0) で通る = 止めたのはこの gate"; else ng "escape hatch でも止まる: $(printf '%s' "$OUT" | head -3)"; fi

# README / SESSION を正本と書いた行: 非公開 repo の README / SESSION 以外の file でも止める
printf '# D\n\n- 手順は README.md §How to build が正本。\n' > "$REPO/DESIGN.md"
if (cd "$REPO" && git add DESIGN.md && env HOME="$FAKE_HOME" git commit -q -m t 2>"$TMP/err" >/dev/null); then
  ng "「README が正本」 の行を足す commit が通ってしまった"
else
  case "$(cat "$TMP/err")" in *"check-session-shape:"*"sot-claim"*) ok "「README が正本」 の行を足す commit を止める (engine の見出しつき)";; *) ng "止まったが engine の見出しが無い: $(head -3 "$TMP/err")";; esac
fi
(cd "$REPO" && git reset -q --hard HEAD && git clean -qfd) >/dev/null 2>&1

# 変数の直後の全角文字の gate (check-unbraced-multibyte-var.py): shell script に「$name + 読点」 を足す commit を止める
# (engine の BLOCK 見出しつき) / ${name} + 読点 は通る / CLAUDE_UNBRACED_MB_VAR_GUARD=0 で通る (= 止めたのがこの gate) /
# engine が見出しなしで異常終了しても commit は止めず 1 行出す (= 故障を違反と読まない)。 述語の SoT = engine の docstring。
# fixture の全角文字は printf の 8 進で書く (この file 自体が gate に当たらないように)。
UMV_BASE="$(git -C "$REPO" rev-parse HEAD)"
try_sh() { # <file content> [env...] → stderr を $OUT に、 rc を返す (通った commit も戻す)
  local content="$1"; shift
  printf '%s' "$content" > "$REPO/run.sh"
  (cd "$REPO" && git add run.sh && env HOME="$FAKE_HOME" "$@" git commit -q -m t 2>"$TMP/err" >/dev/null)
  local rc=$?
  OUT="$(cat "$TMP/err")"
  (cd "$REPO" && git reset -q --hard "$UMV_BASE" && git clean -qfd) >/dev/null 2>&1
  return $rc
}
UMV_BAD="$(printf '#!/usr/bin/env bash\necho "$name\343\200\201"\n')"
UMV_OK="$(printf '#!/usr/bin/env bash\necho "${name}\343\200\201"\n')"
if try_sh "$UMV_BAD"; then
  ng "「\$name + 読点」 を足す commit が通ってしまった"
else
  case "$OUT" in *"check-unbraced-multibyte-var: BLOCK"*) ok "「\$name + 読点」 を足す commit を pre-commit-bib が止める (engine の BLOCK 見出しつき)";; *) ng "止まったが engine の見出しが無い (別の gate?): $(printf '%s' "$OUT" | head -3)";; esac
fi
if try_sh "$UMV_OK"; then ok "「\${name} + 読点」 の commit は通る"; else ng "「\${name} + 読点」 の commit が止まった: $(printf '%s' "$OUT" | head -3)"; fi
if try_sh "$UMV_BAD" CLAUDE_UNBRACED_MB_VAR_GUARD=0; then ok "escape hatch (CLAUDE_UNBRACED_MB_VAR_GUARD=0) で通る = 止めたのはこの gate"; else ng "escape hatch でも止まる: $(printf '%s' "$OUT" | head -3)"; fi
# 偽の scripts dir = hook は写し (readlink の解決先をここにする)、 他は本物への symlink、 この engine だけ見出しなしの rc 1 で落ちる stub
FAKE_SCRIPTS="$TMP/fake-scripts"; mkdir -p "$FAKE_SCRIPTS"
for f in "$HERE"/*; do ln -s "$f" "$FAKE_SCRIPTS/$(basename "$f")"; done
rm -f "$FAKE_SCRIPTS/pre-commit-bib" "$FAKE_SCRIPTS/check-unbraced-multibyte-var.py"
cp "$HOOK" "$FAKE_SCRIPTS/pre-commit-bib"
printf 'import sys\nsys.exit(1)\n' > "$FAKE_SCRIPTS/check-unbraced-multibyte-var.py"
ln -sf "$FAKE_SCRIPTS/pre-commit-bib" "$REPO/.git/hooks/pre-commit"
if try_sh "$UMV_BAD"; then
  case "$OUT" in *"異常終了"*) ok "engine が見出しなしで落ちても commit は通り、 1 行出る";; *) ng "engine の故障で commit は通ったが 1 行が出ない";; esac
else
  ng "engine の故障で commit が止まった: $(printf '%s' "$OUT" | head -3)"
fi
ln -sf "$HOOK" "$REPO/.git/hooks/pre-commit"

echo "pre-commit-bib.test: pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
