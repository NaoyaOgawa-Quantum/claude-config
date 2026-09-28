#!/usr/bin/env bash
# session-shape-guard.sh — PreToolUse(Edit|Write|MultiEdit): SESSION.md に日付の節・commit hash・messageId・経緯の長い 1 行を書く / README が自分を正本と宣言する / CLAUDE.md が「SESSION・README に書け」 と指示する変更を、 書く瞬間に止める (deny) か知らせる (warn)
#
# 正本: claude-config/hooks/session-shape-guard.sh (setup.sh / scripts/sync-hook-settings.sh が ~/.claude/hooks/ に symlink、
#       hooks/settings-entries.json で PreToolUse[Edit|Write|MultiEdit] に登録)
#
# 判定の実体 = scripts/check-session-shape.py --text <file_path> (stdin = 書こうとしている本文)。 述語・閾値・文言はそこだけが持つ。
#   exit 1 → permissionDecision=deny (理由 = engine の出力)
#   exit 0 で出力あり (WARN) → additionalContext で知らせる (止めない)
#   それ以外 (engine 不在・python 不在・入力が読めない・exit 3) → 通す (fail-open。 commit の gate 〔pre-commit-bib /
#   public-precommit-runner〕 が同じ engine で二重に見る)
#
# Why: 「SESSION に正本を置かない」 の規約と messageId 密度の検出器があっても、 決定の経緯・commit hash・検証結果を
#   「日付 + 何をした」 の節として SESSION に足す形で違反が続いた (実測: 走査した SESSION.md のほぼ全部に日付の節)。 書き込みヘッドが
#   SESSION に在るまま新しい事実が同じペン先で落ちる瞬間に、 形で止める。 Bash の heredoc 経由の書き込みは本 hook の射程外
#   (= commit の gate が捕まえる)。 一般則 = docs/convention-design-principles.md#time-keyed-file-appends-only
#
# 見る tool_input: Write.content / Edit.new_string / MultiEdit.edits[].new_string。 file_path の basename が
#   SESSION.md / README(.xx).md / CLAUDE.md / AGENTS.md 以外なら即通す (engine 側でも同じ判定)。
# 環境変数: CLAUDE_SESSION_SHAPE_GUARD=0 (engine が BLOCK を WARN に落とす) / SESSION_SHAPE_ENGINE (test 用に engine を差し替え)
set -u
command -v python3 >/dev/null 2>&1 || exit 0
INPUT="$(cat 2>/dev/null || true)"
[ -n "$INPUT" ] || exit 0
# 高速パス: 対象 file 名を含まなければ python を起こさない
case "$INPUT" in
  *SESSION.md*|*README*|*CLAUDE.md*|*AGENTS.md*) : ;;
  *) exit 0 ;;
esac

if [ -n "${SESSION_SHAPE_ENGINE:-}" ]; then
  ENGINE="$SESSION_SHAPE_ENGINE"
else
  HERE="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "${BASH_SOURCE[0]}" 2>/dev/null)"
  ENGINE="$HERE/../scripts/check-session-shape.py"
fi
[ -f "$ENGINE" ] || exit 0

# file_path と本文を tool_input から取り出す (JSON は python で読む = jq 依存を作らない)
PARSED="$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get("tool_input") or {}
path = ti.get("file_path") or ""
if not path:
    sys.exit(0)
if "content" in ti and isinstance(ti["content"], str):
    text = ti["content"]
elif "new_string" in ti and isinstance(ti["new_string"], str):
    text = ti["new_string"]
elif isinstance(ti.get("edits"), list):
    text = "\n".join(e.get("new_string", "") for e in ti["edits"] if isinstance(e, dict))
else:
    sys.exit(0)
sys.stdout.write(path + "\n" + text)
' 2>/dev/null)" || exit 0
[ -n "$PARSED" ] || exit 0
FILE_PATH="${PARSED%%$'\n'*}"
TEXT="${PARSED#*$'\n'}"
[ "$FILE_PATH" = "$PARSED" ] && TEXT=""

OUT="$(printf '%s\n' "$TEXT" | python3 "$ENGINE" --text "$FILE_PATH" 2>/dev/null)"
rc=$?
if [ "$rc" -eq 1 ]; then
  REASON="$(printf '%s\n' "$OUT" | head -8)"
  printf '%s\n' "$REASON" >&2
  python3 -c '
import json, sys
reason = sys.stdin.read()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
      "permissionDecisionReason": "session-shape-guard: SESSION / README の形に反する書き込みを止めた。\n" + reason}}, ensure_ascii=False))
' <<< "$REASON"
  exit 0
fi
if [ "$rc" -eq 0 ] && [ -n "$OUT" ]; then
  MSG="$(printf '%s\n' "$OUT" | head -6)"
  python3 -c '
import json, sys
msg = sys.stdin.read()
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "session-shape-guard (warn): " + msg}}, ensure_ascii=False))
' <<< "$MSG"
fi
exit 0
