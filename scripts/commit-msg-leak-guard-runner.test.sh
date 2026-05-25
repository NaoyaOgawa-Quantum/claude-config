#!/bin/bash
# commit-msg-leak-guard-runner.test.sh — self-tests for the git-side runner
#
# 設計: runner に git commit-msg hook 互換の引数 ($1=msg file path、 $2=
#       source 種別) を渡し、 exit code + stderr を確認。 claude-code 側 hook
#       (= odakin-prefs/hooks/commit-msg-leak-guard.test.sh) と相補。
#
# 実行: bash commit-msg-leak-guard-runner.test.sh
#       全 pass で exit 0、 fail があれば exit 1

set -uo pipefail

RUNNER="$(dirname "$0")/commit-msg-leak-guard-runner.sh"
[ -x "$RUNNER" ] || { echo "ERROR: $RUNNER not executable"; exit 1; }

PASS=0
FAIL=0
FAILED_CASES=""

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# expect_block <case_name> <message_content> [source]
# message を temp file に書き runner に渡す、 exit 1 + stderr に reject
# 文字列を期待。 source default = "message"。
# 本 test は **claude-config 内で実行されること** を assume (= 親 repo に
# .claude/public-repo.marker あり、 runner が marker check を pass する)。
expect_block() {
  local name="$1" content="$2" source="${3:-message}"
  local msg_file stderr_out exit_code
  msg_file="$TMPDIR_TEST/msg-$RANDOM.txt"
  printf '%s' "$content" > "$msg_file"

  # 親 repo (= claude-config) で run。 marker check を pass するため
  stderr_out="$("$RUNNER" "$msg_file" "$source" 2>&1 >/dev/null)"
  exit_code=$?

  if [ "$exit_code" != "1" ]; then
    FAIL=$((FAIL+1))
    FAILED_CASES="${FAILED_CASES}  [exit!=1] $name (exit=$exit_code)\n"
    return
  fi
  if ! echo "$stderr_out" | grep -q "commit rejected"; then
    FAIL=$((FAIL+1))
    FAILED_CASES="${FAILED_CASES}  [no-reject-msg] $name\n"
    return
  fi
  PASS=$((PASS+1))
}

# expect_pass <case_name> <message_content> [source]
# exit 0 + stderr 空を期待
expect_pass() {
  local name="$1" content="$2" source="${3:-message}"
  local msg_file stderr_out stdout_out exit_code
  msg_file="$TMPDIR_TEST/msg-$RANDOM.txt"
  printf '%s' "$content" > "$msg_file"

  stderr_out="$("$RUNNER" "$msg_file" "$source" 2>&1 >/dev/null)"
  stdout_out="$("$RUNNER" "$msg_file" "$source" 2>/dev/null)"
  exit_code=$?

  if [ "$exit_code" != "0" ]; then
    FAIL=$((FAIL+1))
    FAILED_CASES="${FAILED_CASES}  [exit!=0] $name (exit=$exit_code)\n"
    return
  fi
  if [ -n "$stderr_out" ]; then
    FAIL=$((FAIL+1))
    FAILED_CASES="${FAILED_CASES}  [unexpected-stderr] $name: $(echo "$stderr_out" | head -1)\n"
    return
  fi
  if [ -n "$stdout_out" ]; then
    FAIL=$((FAIL+1))
    FAILED_CASES="${FAILED_CASES}  [unexpected-stdout] $name\n"
    return
  fi
  PASS=$((PASS+1))
}

# cd to claude-config (= 親 repo に marker あり、 runner が marker pass する)
cd "$(dirname "$RUNNER")/.." || exit 1
[ -f ".claude/public-repo.marker" ] || {
  echo "ERROR: test expects to run from claude-config (marker not found)"
  exit 1
}

# ====================================================================
# BLOCK cases
# ====================================================================
expect_block "block-private-repo-name" \
  "fix bayes-kai/CLAUDE.md path"

expect_block "block-lectures" \
  "lectures: SESSION.md update"

expect_block "block-einstein-cartan" \
  "Add einstein-cartan retraction marker macro"

expect_block "block-twcu-phys-web" \
  "twcu-phys-web セッションで作業"

expect_block "block-multiline" \
  "first line short
body with bayes-kai mention
end"

expect_block "block-amend-source" \
  "fix bayes-kai oversight" \
  "commit"

# ====================================================================
# PASS cases
# ====================================================================
expect_pass "pass-clean-typo" \
  "fix typo"

expect_pass "pass-allowlist-gmail-mcp-config" \
  "fix gmail-mcp-config oauth flow"

expect_pass "pass-allowlist-odakin-prefs" \
  "odakin-prefs: add new hook"

expect_pass "pass-public-claude-config" \
  "claude-config: refine convention"

expect_pass "pass-public-LorentzArena" \
  "LorentzArena: fix WebRTC reconnect"

# merge source = skip
expect_pass "skip-merge-source" \
  "Merge branch 'feature' (with bayes-kai)" \
  "merge"

# squash source = skip
expect_pass "skip-squash-source" \
  "squashed commits (with bayes-kai)" \
  "squash"

# git scrubs comment lines (^#) so we should too
expect_pass "skip-comment-only-leak" \
  "fix typo
# Please enter the commit message for your changes (bayes-kai related)
# Lines starting with '#' will be ignored."

# empty message = skip
expect_pass "skip-empty-message" \
  ""

# ====================================================================
echo ""
echo "=== commit-msg-leak-guard-runner self-test ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Failed cases:"
  printf "$FAILED_CASES"
  exit 1
fi
echo "OK"
exit 0
