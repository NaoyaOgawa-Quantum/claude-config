#!/usr/bin/env bash
# install-public-commit-msg.test.sh — commit-msg stub の installer の test: marker の無い repo は既定で断る / --any-repo で置く / 2 回目は触らない / 置いた stub で private repo の commit が学生の識別子で止まる (hermetic)
#
# 正本: claude-config/scripts/install-public-commit-msg.test.sh
# 実行: bash scripts/install-public-commit-msg.test.sh (run-all-checks.sh が自動発見)
#
# 述語の SoT = check-student-identifiers.py docstring、 runner の Stage 0 = commit-msg-leak-guard-runner.sh。 ここは installer と
# 配線の固定。 git の global 設定は外す (GIT_CONFIG_GLOBAL=/dev/null)。 学籍番号の形の値は実行時に組み立てる。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
INST="$HERE/install-public-commit-msg.sh"
[ -f "$INST" ] || { echo "FAIL: not found: $INST"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "SKIP: git 不在"; exit 0; }

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  PASS  $1"; }
ng() { fail=$((fail+1)); echo "  FAIL  $1"; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/install-commit-msg-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
mkrepo() { mkdir -p "$1" && git -C "$1" init -q -b main && git -C "$1" config user.email t@example.invalid && git -C "$1" config user.name t; }

PRIV="$TMP/priv"; mkrepo "$PRIV"
if bash "$INST" "$PRIV" >/dev/null 2>&1; then ng "marker の無い repo に既定で置いた"; else ok "marker の無い repo は既定で断る (従来どおり)"; fi
[ -e "$PRIV/.git/hooks/commit-msg" ] && ng "断ったのに hook が在る" || ok "断ったときは hook を書かない"

if bash "$INST" --any-repo "$PRIV" >/dev/null 2>&1 && [ -x "$PRIV/.git/hooks/commit-msg" ] \
   && grep -q "commit-msg-leak-guard-runner.sh" "$PRIV/.git/hooks/commit-msg"; then
  ok "--any-repo で marker の無い repo にも同じ runner の stub を置く"
else
  ng "--any-repo で stub が置かれない"
fi
out="$(bash "$INST" --any-repo "$PRIV" 2>&1)"
case "$out" in *"up to date"*) ok "2 回目は up to date (書き換えない)";; *) ng "2 回目の出力が違う: $out";; esac
ls "$PRIV/.git/hooks/" | grep -q 'commit-msg.bak' && ng "自分の stub を退避した" || ok "自分の stub は退避しない"

PUB="$TMP/pub"; mkrepo "$PUB"; mkdir -p "$PUB/.claude"; : > "$PUB/.claude/public-repo.marker"
if bash "$INST" "$PUB" >/dev/null 2>&1 && grep -q "commit-msg-leak-guard-runner.sh" "$PUB/.git/hooks/commit-msg"; then
  ok "marker の在る repo は flag なしで従来どおり置く"
else
  ng "marker の在る repo に置けない"
fi

# 置いた stub で private repo の commit が止まる (runner の Stage 0)。 この test だけの架空の一覧を env で渡す。
if command -v python3 >/dev/null 2>&1 && [ -f "$HERE/check-student-identifiers.py" ]; then
  printf '%s\n' '{"schema": 1, "full_names_cjk": ["仮野 名子"], "full_names_latin": [["karino", "nako"]]}' > "$TMP/identity.json"
  printf '%s\n' '(?i)(?<![0-9a-z])[a-z][0-9]{2}[a-z][0-9]{3,4}(?![0-9a-z])' > "$TMP/patterns.txt"
  SID_ID="$(printf 'A%02dX%s' 12 3456)"
  printf 'x\n' > "$PRIV/a.txt"; git -C "$PRIV" add a.txt
  if (cd "$PRIV" && CLAUDE_STUDENT_IDENTITY="$TMP/identity.json" CLAUDE_PII_FILENAME_PATTERNS="$TMP/patterns.txt" \
        git commit -q -m "fix: see $SID_ID" 2>"$TMP/err" >/dev/null); then
    ng "private repo で学籍番号を含む message の commit が通ってしまった"
  else
    grep -q "check-student-identifiers: BLOCK" "$TMP/err" && ok "private repo で学籍番号を含む message の commit を止める (engine の BLOCK 見出しつき)" \
      || ng "止まったが engine の見出しが無い: $(head -3 "$TMP/err")"
  fi
  printf 'y\n' > "$PRIV/b.txt"; git -C "$PRIV" add b.txt   # 上の commit が (hook 無しで) 通った場合も stage を空にしない
  if (cd "$PRIV" && CLAUDE_STUDENT_IDENTITY="$TMP/identity.json" CLAUDE_PII_FILENAME_PATTERNS="$TMP/patterns.txt" \
        git commit -q -m "fix: 学生 A の件" >/dev/null 2>&1); then
    ok "識別子の無い message の commit は通る (private repo では公開 repo の leak 検出は走らない)"
  else
    ng "識別子の無い message の commit が止まった"
  fi
fi

echo "install-public-commit-msg.test: pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
