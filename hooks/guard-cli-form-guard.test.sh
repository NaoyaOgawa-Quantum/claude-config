#!/usr/bin/env bash
# guard-cli-form-guard.test.sh — guard-cli-form-guard.py の self-test (配信対象外)
#
# 実行: bash hooks/guard-cli-form-guard.test.sh   (exit code = fail 数)

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/guard-cli-form-guard.py"
REPO="$(cd "$HERE/.." && pwd -P)"
ARG="$REPO/scripts/agent-rule-guard.py"
MCG="$REPO/scripts/manuscript-claim-guard.py"
FAIL=0

run() {  # run <期待する exit> <説明> <command> [env...]
  local want="$1" desc="$2" cmd="$3"; shift 3
  local payload got
  payload=$(python3 -c 'import json,sys; print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))' "$cmd")
  got=$(printf '%s' "$payload" | env "$@" python3 "$HOOK" 2>/dev/null; echo $?)
  got="${got##*$'\n'}"
  if [ "$got" = "$want" ]; then
    echo "ok   - $desc"
  else
    echo "FAIL - $desc (want $want, got $got)"
    FAIL=$((FAIL + 1))
  fi
}

# 通すもの
run 0 "単独・絶対 path の apply" "python3 $ARG apply --file /x/a.md --candidate /y/a.md --change 'a; b && c | d' --latest"
run 0 "単独・絶対 path の approve (引用に日本語と記号)" "python3 $MCG approve --file /x/a.md --region authority:file --quote '「OK」; ほか'"
run 0 "読むだけ (grep)" "command grep -n foo scripts/manuscript-claim-guard.py"
run 0 "読むだけ (sed と pipe)" "sed -n 1,5p $ARG | head -3"
run 0 "engine に触れない command" "ls -la && git status"
run 0 "解析できない command は通す" "python3 scripts/agent-rule-guard.py --change 'unterminated"

# 止めるもの
run 2 "cd と繋いだ形" "cd ~/Claude/claude-config && python3 scripts/agent-rule-guard.py apply --file a.md --latest"
run 2 "相対 path" "python3 scripts/agent-rule-guard.py approve --file a.md --latest"
run 2 "変数の代入と ; で繋いだ形" "SP=/tmp/x; python3 $ARG apply --candidate \$SP/a.md --latest"
run 2 "前置きの変数の代入" "FOO=1 python3 $ARG --help"
run 2 "pipe で繋いだ形" "python3 $ARG apply --file /x/a.md --latest 2>&1 | tail -3"
run 2 "改行で繋いだ形" "python3 $ARG --help
ls"
run 2 "python3 以外の interpreter" "/usr/bin/python3 $MCG --help"
run 2 "直接実行" "$ARG --help"
run 2 "別の場所の同名 engine" "python3 /tmp/elsewhere/scripts/agent-rule-guard.py --help"

# 無効化
run 0 "CLAUDE_GUARD_CLI_FORM_GUARD=0 で止めない" "python3 scripts/agent-rule-guard.py --help" CLAUDE_GUARD_CLI_FORM_GUARD=0

# 壊れた payload は通す (fail-open)
got=$(printf '{not json' | python3 "$HOOK" 2>/dev/null; echo $?)
if [ "${got##*$'\n'}" = "0" ]; then echo "ok   - 壊れた JSON は通す"; else echo "FAIL - 壊れた JSON は通す (got $got)"; FAIL=$((FAIL + 1)); fi

echo "fail=$FAIL"
exit "$FAIL"
