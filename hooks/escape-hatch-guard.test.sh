#!/usr/bin/env bash
# escape-hatch-guard.test.sh — gate の escape hatch の deny と、 本人の指示の記録 (承認台帳) による通過を hook の入出力で検査 (承認は実物の approve CLI で記録)
#
# 正本: claude-config/hooks/escape-hatch-guard.test.sh
# 何を見るか:
#   1. 述語 (--selftest)
#   2. 承認なし = deny (env の escape hatch / git config core.hooksPath / 設定の差し替え + commit)。 bash と zsh の quote の違い
#   3. 無関係な command・data の中の文字列・Bash 以外の tool = 無音
#   4. 実物の approve CLI (agent-rule-guard.py approve --latest) で記録 → 同じ command が通る
#   5. 記録が効かない形: 別の session / --change に対象の名前が無い / 30 分より古い / 領域違い / file 違い / 他 session の記録の写し
#   6. 故障: 解析の部品が無い = 1 行出して通す (fail-open) / 読めない入力 = 1 行出して通す / 台帳の部品が無い = deny
# hermetic: 承認台帳は一時 dir (MANUSCRIPT_CLAIM_GUARD_STATE_DIR)、 transcript は合成。 本物の台帳・transcript は読まない。
# ESCAPE_HATCH_GUARD_HOOK で別の hook を差し替えられる (赤 → 緑の確認用 = 何もしない hook で落ちること)。

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="${ESCAPE_HATCH_GUARD_HOOK:-$HERE/escape-hatch-guard.py}"
ENGINE="$HERE/../scripts/agent-rule-guard.py"
[ -f "$HOOK" ] || { echo "FAIL: hook が無い: $HOOK"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 不在"; exit 0; }
[ -f "$ENGINE" ] || { echo "SKIP: agent-rule-guard.py が無い ($ENGINE)"; exit 0; }

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export MANUSCRIPT_CLAIM_GUARD_STATE_DIR="$T/state"
unset CLAUDE_CODE_SESSION_ID CLAUDE_CONFIG_AGENT_SESSION CODEX_SESSION_ID CODEX_THREAD_ID 2>/dev/null || true

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  PASS  $1"; }
ng() { fail=$((fail+1)); echo "  FAIL  $1"; }

SID_A="sess-a-0001"
SID_B="sess-b-0002"
HOOK_REAL="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$HERE/escape-hatch-guard.py")"

# event を組んで hook に渡す (command は argv で渡す = quote をそのまま保つ)
run_hook() {  # $1 = session id, $2 = command, [$3 = tool name]
  python3 -c 'import json,sys; print(json.dumps({"hook_event_name":"PreToolUse","tool_name":sys.argv[3],"session_id":sys.argv[1],"cwd":"/tmp","tool_input":{"command":sys.argv[2]}}))' \
    "$1" "$2" "${3:-Bash}" | python3 "$HOOK" 2>"$T/stderr"
}
is_deny() { case "$1" in *'"permissionDecision": "deny"'*) return 0 ;; *) return 1 ;; esac; }
expect_deny() {  # $1 = label, $2 = session, $3 = command
  local out; out="$(run_hook "$2" "$3")"
  if is_deny "$out"; then ok "$1"; else ng "$1 — deny されない: ${out:0:200}"; fi
}
expect_pass() {
  local out; out="$(run_hook "$2" "$3")"
  if [ -z "$out" ]; then ok "$1"; else ng "$1 — 出力あり: ${out:0:200}"; fi
}

# 合成 transcript (本人の発言 1 つ)。 approve --latest がこの発言を引く
make_transcript() {  # $1 = session id, $2 = 本人の発言
  python3 - "$T/transcripts/$1.jsonl" "$2" <<'PY'
import json, os, sys, datetime
p, text = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(p), exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
with open(p, "w", encoding="utf-8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": now, "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n")
PY
}
approve() {  # $1 = session id, $2 = change, [$3 = region], [$4 = file]
  python3 "$ENGINE" approve --session "claude:$1" --transcript "$T/transcripts/$1.jsonl" \
    --file "${4:-$HOOK_REAL}" --region "${3:-section:guard-escape}" --change "$2" --latest
}
ledger() { printf '%s/approvals/claude-%s.jsonl' "$MANUSCRIPT_CLAIM_GUARD_STATE_DIR" "$1"; }

echo "=== 1. 述語 (--selftest) ==="
st="$(python3 "$HOOK" --selftest 2>&1)"; rc=$?
printf '%s\n' "$st" | tail -1 | sed 's/^/  /'
[ "$rc" -eq 0 ] && ok "selftest" || ng "selftest rc=$rc"

S=CLAUDE_STUDENT_ID_GUARD
echo "=== 2. 承認なし = deny ==="
expect_deny "前置の代入" "$SID_A" "$S=0 git commit -m x"
expect_deny "single quote の値 (bash / zsh 共通)" "$SID_A" "$S='0' git commit -m x"
expect_deny "double quote の値" "$SID_A" "$S=\"0\" git commit -m x"
expect_deny "ANSI-C quote (\$'0')" "$SID_A" "$S=\$'0' git commit -m x"
expect_deny "export してから commit" "$SID_A" "export $S=0; git commit -m x"
expect_deny "zsh -c の中 / typeset -x" "$SID_A" "zsh -c 'typeset -x $S=0; git commit -m x'"
expect_deny "bash -lc の中" "$SID_A" "bash -lc \"$S=0 git commit -m x\""
expect_deny "double quote の中の \$(…)" "$SID_A" "out=\"\$($S=0 git commit -m x 2>&1)\""
expect_deny "git config core.hooksPath" "$SID_A" "git config core.hooksPath /dev/null"
expect_deny "--no-verify の省略形 (git は --no-verif を受ける)" "$SID_A" "git commit --no-verif -m x"
expect_deny "一覧の差し替え + commit" "$SID_A" "CLAUDE_STUDENT_IDENTITY=/dev/null git commit -m x"
out="$(run_hook "$SID_A" "$S=0 git commit -m x")"
case "$out" in
  *"agent-rule-guard.py approve"*"--region section:guard-escape"*"$S"*"--latest"*) ok "deny の文面に記録の command (対象の名前入り)" ;;
  *) ng "deny の文面に記録の command が無い: ${out:0:300}" ;;
esac
case "$out" in *"一般的な依頼"*) ok "deny の文面に「一般的な依頼は指示ではない」" ;; *) ng "一般的な依頼の注意が無い" ;; esac
printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin)["hookSpecificOutput"]; assert d["hookEventName"]=="PreToolUse"' \
  && ok "出力は PreToolUse の JSON" || ng "JSON 形が違う"
out="$(run_hook "$SID_A" "git commit --no-verify -m x")"
case "$out" in *"manuscript-claim-guard も"*) ok "--no-verify の deny は manuscript-claim-guard の無条件の拒否に触れる" ;; *) ng "--no-verify の注記が無い" ;; esac

echo "=== 3. 無関係・data = 無音 ==="
expect_pass "無関係な command" "$SID_A" "ls -la && git status"
expect_pass "echo の引数" "$SID_A" "echo $S=0"
expect_pass "commit message の中" "$SID_A" "git commit -m 'escape hatch = $S=0'"
expect_pass "heredoc の本文" "$SID_A" "$(printf 'cat > /tmp/x <<%s\nexport %s=0\ngit commit --no-verify\n%s' "'EOF'" "$S" "EOF")"
expect_pass "止めない値 (1)" "$SID_A" "$S=1 git commit -m x"
expect_pass "git config --get" "$SID_A" "git config --get core.hooksPath"
expect_pass "一覧の差し替えだけ (commit なし)" "$SID_A" "CLAUDE_STUDENT_IDENTITY=/tmp/l.json python3 x.py --tree /tmp/r"
out="$(run_hook "$SID_A" "$S=0 git commit -m x" Read)"
[ -z "$out" ] && ok "Bash 以外の tool は無音" || ng "Read で出力: $out"

echo "=== 4. 実物の approve CLI で記録 → 通る ==="
make_transcript "$SID_A" "学生の一覧の誤検出なので、 今回だけ $S=0 で commit して構いません"
if approve "$SID_A" "$S: 一覧の誤検出を 1 回通す (本人の指示)" >"$T/approve.out" 2>&1; then
  ok "approve CLI が section:guard-escape を記録した"
else
  ng "approve CLI が失敗: $(tr '\n' ' ' <"$T/approve.out" | cut -c1-300)"
fi
python3 - "$(ledger "$SID_A")" "$HOOK_REAL" <<'PY' && ok "台帳の行 = session / 領域 / file / 本人の発言の時刻" || ng "台帳の行の形が違う"
import json, sys, os
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
e = rows[-1]
assert e["session"].startswith("claude:sess-a"), e
assert e["regions"] == ["section:guard-escape"], e
assert os.path.basename(e["file"]) == "escape-hatch-guard.py", e
assert e["quote_time"] and e["at"], e
PY
expect_pass "記録の後は同じ command が通る" "$SID_A" "$S=0 git commit -m x"
expect_pass "quote 違い (zsh -c) も通る" "$SID_A" "zsh -c '$S=\"0\" git commit -m x'"
expect_deny "記録に名前の無い別の escape hatch は止まる" "$SID_A" "CLAUDE_LEAK_GUARD=0 git commit -m x"
expect_deny "記録に名前の無い core.hooksPath は止まる" "$SID_A" "git config core.hooksPath /dev/null"

echo "=== 5. 記録が効かない形 ==="
expect_deny "別の session の記録は効かない" "$SID_B" "$S=0 git commit -m x"
mkdir -p "$(dirname "$(ledger "$SID_B")")"
cp "$(ledger "$SID_A")" "$(ledger "$SID_B")"
expect_deny "他 session の記録を写しても効かない (session 欄が違う)" "$SID_B" "$S=0 git commit -m x"
rm -f "$(ledger "$SID_B")"
python3 - "$(ledger "$SID_B")" "$SID_B" "$HOOK_REAL" "$S" <<'PY'
import json, sys, datetime
path, sid, hook, name = sys.argv[1:5]
now = datetime.datetime.now(datetime.timezone.utc)
def row(minutes_ago, region="section:guard-escape", file=hook, change=name + ": x"):
    t = (now - datetime.timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
    return {"v": 1, "repo": "", "file": file, "regions": [region], "change": change, "quote": "q",
            "quote_time": t, "quote_msg_sha": "0", "session": "claude:" + sid, "at": t}
with open(path, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(row(31)) + "\n")                                  # 古い
    fh.write(json.dumps(row(1, region="section:intro")) + "\n")           # 領域違い
    fh.write(json.dumps(row(1, file="/tmp/other.py")) + "\n")             # file 違い
    fh.write(json.dumps(row(1, change="一覧の誤検出を通す")) + "\n")        # 対象の名前が無い
PY
expect_deny "古い記録 (31 分前) / 領域違い / file 違い / 名前の無い記録はどれも効かない" "$SID_B" "$S=0 git commit -m x"
python3 - "$(ledger "$SID_B")" "$SID_B" "$HOOK_REAL" "$S" <<'PY'
import json, sys, datetime
path, sid, hook, name = sys.argv[1:5]
t = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=29)).isoformat(timespec="seconds")
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"v": 1, "repo": "", "file": hook, "regions": ["section:guard-escape"], "change": name + ": x",
                         "quote": "q", "quote_time": t, "quote_msg_sha": "0", "session": "claude:" + sid, "at": t}) + "\n")
PY
expect_pass "陽性対照: 29 分前の正しい記録は効く" "$SID_B" "$S=0 git commit -m x"
expect_deny "session id が無い event は記録を照合できない = deny" "" "$S=0 git commit -m x"

echo "=== 6. 故障 ==="
out="$(ESCAPE_HATCH_GUARD_RULE_ENGINE="$T/none.py" run_hook "$SID_A" "CLAUDE_LEAK_GUARD=0 git commit -m x")"; rc=$?
if [ "$rc" -eq 0 ] && ! is_deny "$out" && printf '%s' "$out" | grep -q '検査していない'; then
  ok "解析の部品が無い = 1 行出して通す (fail-open)"
else
  ng "部品が無い時の挙動: rc=$rc out=${out:0:200}"
fi
out="$(printf 'not json' | python3 "$HOOK" 2>/dev/null)"; rc=$?
{ [ "$rc" -eq 0 ] && ! is_deny "$out" && printf '%s' "$out" | grep -q '検査していない'; } \
  && ok "読めない入力 = 1 行出して通す" || ng "読めない入力: rc=$rc out=${out:0:200}"
out="$(ESCAPE_HATCH_GUARD_DISPATCHER="$T/none.py" run_hook "$SID_A" "CLAUDE_LEAK_GUARD=0 git commit -m x")"
case "$out" in *'"permissionDecision": "deny"'*"台帳を読めない"*) ok "見つけた後に台帳の部品が無い = deny" ;; *) ng "台帳の部品が無い時: ${out:0:200}" ;; esac
out="$(ESCAPE_HATCH_GUARD_RULE_ENGINE="$T/none.py" run_hook "$SID_A" "ls -la")"
[ -z "$out" ] && ok "無関係な command は部品が無くても無音 (前段の絞り込み)" || ng "無関係な command で出力: $out"

echo
echo "=== Result: $pass passed, $fail failed ==="
[ "$fail" -eq 0 ]
