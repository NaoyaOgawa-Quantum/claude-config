#!/usr/bin/env bash
# bootstrap-stdio-mcps.test.sh — self-test for the generic stdio MCP bootstrap library.

set -u
SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/bootstrap-stdio-mcps.sh"
PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "  PASS: $1"; }
ng()  { FAIL=$((FAIL+1)); echo "  FAIL: $1"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------- T1: 引数不足 → silent exit 0 ----------
echo "=== T1: 引数不足 → silent exit 0 ==="
out="$(bash "$SCRIPT")"
[ -z "$out" ] && ok "no args silent" || ng "no args should be silent (got: $out)"
out="$(bash "$SCRIPT" "$TMP/reg.txt")"
[ -z "$out" ] && ok "missing base-dir silent" || ng "missing base-dir should be silent (got: $out)"

# ---------- T2: registry 不在 → silent ----------
echo "=== T2: registry 不在 → silent ==="
out="$(bash "$SCRIPT" "$TMP/nonexistent.txt" "$TMP")"
[ -z "$out" ] && ok "missing registry silent" || ng "missing registry should be silent (got: $out)"

# ---------- T3: 全 MCP 登録済 → 沈黙 ----------
echo "=== T3: 全 MCP 登録済 → silent ==="
mkdir -p "$TMP/base"
cat > "$TMP/reg.txt" <<'EOF'
classroom:classroom-cis
calendar-cis:calendar-cis
EOF
for d in classroom calendar-cis; do
  mkdir -p "$TMP/base/$d/node_modules"
  touch "$TMP/base/$d/server.mjs"
done
mock_list="classroom-cis: stdio - node /path
calendar-cis: stdio - node /path"
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="$mock_list" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
[ -z "$out" ] && ok "all-registered silent" || ng "all-registered should be silent (got: $out)"

# ---------- T4: 1 件 missing → 1 行出力 ----------
echo "=== T4: 1 件 missing → 1 行 ==="
partial="classroom-cis: stdio - node /path"
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="$partial" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
n=$(printf '%s\n' "$out" | grep -c "calendar-cis.*dry-run")
[ "$n" = "1" ] && ok "1 missing surfaces (n=$n)" || ng "1 missing should surface (n=$n, got: $out)"
# 既登録 (classroom-cis) は出ない
case "$out" in
  *"classroom-cis (dry-run"*) ng "registered should not appear" ;;
  *) ok "registered skipped" ;;
esac

# ---------- T5: 全 missing → 2 件出力 ----------
echo "=== T5: 全 missing → 2 件 ==="
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
n=$(printf '%s\n' "$out" | grep -c "dry-run")
[ "$n" = "2" ] && ok "both missing surface (n=$n)" || ng "both should surface (n=$n, got: $out)"

# ---------- T6: server.mjs 不在の pair → silent skip ----------
echo "=== T6: server.mjs 不在 → silent skip ==="
rm "$TMP/base/calendar-cis/server.mjs"
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
case "$out" in
  *"calendar-cis"*) ng "missing server.mjs should silent-skip" ;;
  *) ok "missing server.mjs silent-skipped" ;;
esac
# classroom-cis は出る
case "$out" in
  *"classroom-cis"*) ok "valid pair still surfaces" ;;
  *) ng "valid pair should surface" ;;
esac
touch "$TMP/base/calendar-cis/server.mjs"

# ---------- T7: comment / 空行 / トレーリング空白を skip ----------
echo "=== T7: registry comment と空行 skip ==="
cat > "$TMP/reg.txt" <<'EOF'
# comment line
classroom:classroom-cis

  # indented comment
calendar-cis:calendar-cis
EOF
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
n=$(printf '%s\n' "$out" | grep -c "dry-run")
[ "$n" = "2" ] && ok "comments/blanks skipped (n=$n)" || ng "comments/blanks (n=$n, out: $out)"

# ---------- T8: format "<mcp-name> = node <path>" (= 非 dry-run mode の出力形式 verify) ----------
echo "=== T8: 出力形式 (dry-run) ==="
out="$(CLAUDE_BOOTSTRAP_MCP_LIST="" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
case "$out" in
  *"classroom-cis (dry-run, would add: node "*"classroom/server.mjs"*) ok "dry-run output format ok" ;;
  *) ng "dry-run output format unexpected (got: $out)" ;;
esac

# ---------- T9: 登録済でも node_modules が lockfile とずれていれば npm install 対象 ----------
echo "=== T9: lockfile と node_modules のずれ (登録済 pair) ==="
cat > "$TMP/reg.txt" <<'EOF'
classroom:classroom-cis
calendar-cis:calendar-cis
EOF
mock_list="classroom-cis: stdio - node /path
calendar-cis: stdio - node /path"
lock() { # lock <dir> <googleapis ver> [optional-pkg]
  opt=""
  [ -n "${3:-}" ] && opt=",\"node_modules/$3\":{\"version\":\"1.0.0\",\"optional\":true}"
  printf '{"packages":{"":{"name":"x"},"node_modules/googleapis":{"version":"%s"}%s}}' "$2" "$opt" > "$1/package-lock.json"
}
hidden() { printf '{"packages":{"node_modules/googleapis":{"version":"%s"}}}' "$2" > "$1/node_modules/.package-lock.json"; }
lock "$TMP/base/classroom" 182.0.0;    hidden "$TMP/base/classroom" 176.0.0
lock "$TMP/base/calendar-cis" 182.0.0; hidden "$TMP/base/calendar-cis" 182.0.0
if command -v python3 >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  out="$(CLAUDE_BOOTSTRAP_MCP_LIST="$mock_list" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
  case "$out" in
    *"classroom-cis (dry-run, would npm install"*) ok "drifted registered pair surfaces" ;;
    *) ng "drifted registered pair should surface (got: $out)" ;;
  esac
  case "$out" in
    *"calendar-cis (dry-run"*) ng "in-sync pair should be silent (got: $out)" ;;
    *) ok "in-sync pair silent" ;;
  esac

  # T10: lockfile にあって入っていない optional (他 platform 用) はずれに数えない
  echo "=== T10: 未導入の optional はずれに数えない ==="
  lock "$TMP/base/classroom" 176.0.0 fsevents
  out="$(CLAUDE_BOOTSTRAP_MCP_LIST="$mock_list" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
  [ -z "$out" ] && ok "missing optional ignored" || ng "missing optional should be silent (got: $out)"

  # T11: hidden lockfile が無い (= 読めない) → fail-open で沈黙
  echo "=== T11: hidden lockfile 不在 → 沈黙 ==="
  lock "$TMP/base/classroom" 182.0.0; rm -f "$TMP/base/classroom/node_modules/.package-lock.json"
  out="$(CLAUDE_BOOTSTRAP_MCP_LIST="$mock_list" CLAUDE_BOOTSTRAP_NO_ADD=1 bash "$SCRIPT" "$TMP/reg.txt" "$TMP/base")"
  [ -z "$out" ] && ok "unreadable hidden lockfile silent" || ng "unreadable hidden lockfile should be silent (got: $out)"
else
  echo "  SKIP: python3 / npm が無い"
fi

echo
echo "=== Result: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
