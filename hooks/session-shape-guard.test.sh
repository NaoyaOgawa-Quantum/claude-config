#!/usr/bin/env bash
# session-shape-guard.test.sh — session-shape-guard.sh の self-test (deny / warn / pass / fail-open / opt-out、 hermetic)
#
# 正本: claude-config/hooks/session-shape-guard.test.sh
# 実行: bash hooks/session-shape-guard.test.sh (run-all-checks.sh が自動発見)
#
# 象限: deny (SESSION.md に日付の節 / commit hash / messageId / 1000 byte 超の行、 非公開 repo の README 自称正本) /
#       warn (CLAUDE.md の「SESSION に決定事項を記録」 = additionalContext だけ) /
#       pass (SESSION.md の案件 pointer 行・対象外の file・壊れた JSON・engine 不在・CLAUDE_SESSION_SHAPE_GUARD=0)。
# path は架空値 (実 user 名・実 home を使わない)。 engine は同 repo の scripts/check-session-shape.py (= 本物の述語で hook の配線を検査)。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/session-shape-guard.sh"
ENGINE="$HERE/../scripts/check-session-shape.py"
[ -f "$HOOK" ] || { echo "FAIL: hook not found: $HOOK"; exit 1; }
[ -f "$ENGINE" ] || { echo "FAIL: engine not found: $ENGINE"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 不在 — test 省略"; exit 0; }

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  PASS  $1"; }
ng() { fail=$((fail+1)); echo "  FAIL  $1"; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/session-shape-guard-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
# 非公開 repo (marker 無し) を 1 つ用意 = README の自称正本が deny になる側
REPO="$TMP/repo"
mkdir -p "$REPO" && git -C "$REPO" init -q -b main 2>/dev/null

mk() { # <tool> <file_path> <text>  → hook 入力 JSON
  python3 -c '
import json, sys
tool, path, text = sys.argv[1], sys.argv[2], sys.argv[3]
ti = {"file_path": path}
if tool == "Write":
    ti["content"] = text
elif tool == "Edit":
    ti["old_string"] = "x"; ti["new_string"] = text
else:
    ti["edits"] = [{"old_string": "x", "new_string": text}]
print(json.dumps({"tool_name": tool, "tool_input": ti}, ensure_ascii=False))
' "$1" "$2" "$3"
}
decision() { # <json> → deny | warn | pass
  local out
  out="$(printf '%s' "$1" | env -u CLAUDE_SESSION_SHAPE_GUARD bash "$HOOK" 2>/dev/null)"
  case "$out" in
    *'"permissionDecision": "deny"'*) echo deny ;;
    *additionalContext*) echo warn ;;
    *) echo pass ;;
  esac
}
assert() { # <label> <expect> <json>
  local got; got="$(decision "$3")"
  if [ "$got" = "$2" ]; then ok "$1"; else ng "$1 (expect=$2 got=$got)"; fi
}

S="$REPO/SESSION.md"
assert "deny: Write で SESSION.md に日付の節" deny "$(mk Write "$S" $'# SESSION\n\n## 2026-09-28 — 何をした (session x)\n- y\n')"
assert "deny: Edit で SESSION.md に backtick の commit hash" deny "$(mk Edit "$S" '- 案件 B — 適用済 (`79fecfa` / `8a94202`)')"
assert "deny: MultiEdit で SESSION.md に messageId" deny "$(mk MultiEdit "$S" '- 送信済 19ab0000deadbeef')"
assert "deny: SESSION.md に 1000 byte 超の 1 行" deny "$(mk Edit "$S" "- $(printf '経緯%.0s' $(seq 1 520))")"
assert "pass: SESSION.md の案件 pointer 行" pass "$(mk Edit "$S" '- 案件 A — 次 = X → [正本](DESIGN.md)')"
assert "pass: 最終更新 (sweep 済: hash) の行" pass "$(mk Edit "$S" '最終更新: 2026-09-28 (sweep 済: abc1234)')"
assert "deny: 非公開 repo の README が自分を正本と宣言" deny "$(mk Write "$REPO/docs/README.md" $'# docs\n\n本 README が正本。\n')"
assert "warn: CLAUDE.md の『SESSION.md に決定事項を記録』" warn "$(mk Edit "$REPO/CLAUDE.md" '- 重要な判断時 → SESSION.md に決定事項を記録')"
assert "pass: CLAUDE.md の現在地の指示 (否定形)" pass "$(mk Edit "$REPO/CLAUDE.md" '- SESSION.md には現在地の行だけを置く (決定は書かない)')"
assert "pass: 対象外の file に日付の節" pass "$(mk Write "$REPO/notes.md" $'## 2026-09-28 — x\n')"
assert "pass: 壊れた JSON は通す (fail-open)" pass '{"tool_name": "Write", "tool_input": {"file_path": "SESSION.md", "content": '
assert "pass: file_path 無しは通す" pass '{"tool_name": "Write", "tool_input": {"content": "## 2026-09-28 x"}}'

# opt-out: engine が BLOCK を WARN に落とす → hook は deny を出さない
out="$(mk Write "$S" $'## 2026-09-28 — x\n' | CLAUDE_SESSION_SHAPE_GUARD=0 bash "$HOOK" 2>/dev/null)"
case "$out" in *'"permissionDecision": "deny"'*) ng "opt-out: CLAUDE_SESSION_SHAPE_GUARD=0 で deny しない";; *) ok "opt-out: CLAUDE_SESSION_SHAPE_GUARD=0 で deny しない";; esac

# engine 不在 → 通す (fail-open)
out="$(mk Write "$S" $'## 2026-09-28 — x\n' | SESSION_SHAPE_ENGINE="$TMP/missing.py" bash "$HOOK" 2>/dev/null)"
[ -z "$out" ] && ok "fail-open: engine 不在は無出力で通す" || ng "fail-open: engine 不在は無出力で通す"

# deny の理由に engine の見出しが入る (= 何が止めたかが model に届く)
out="$(mk Write "$S" $'## 2026-09-28 — x\n' | bash "$HOOK" 2>/dev/null)"
case "$out" in *dated-heading*) ok "deny の理由に engine の finding (dated-heading) が入る";; *) ng "deny の理由に engine の finding が入る";; esac

echo "session-shape-guard.test: pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
