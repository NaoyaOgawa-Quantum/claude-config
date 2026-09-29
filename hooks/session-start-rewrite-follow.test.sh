#!/usr/bin/env bash
# session-start-rewrite-follow.test.sh — SessionStart の追従 hook の入口 test (判定本体の test = scripts/lib/git_rewrite_follow.py を直接実行)
#
# 一時 root に bare remote + clone を作り、 remote の履歴を書き換え (message だけ、 tree は同じ) てから hook を回す:
# 揃えた行が出て HEAD が新しい先頭になる / 最新の clone だけなら沈黙 / SessionStart 以外は沈黙 / kill switch で沈黙 /
# 手元にしか無い commit は「揃えられなかった」 で HEAD は動かない。 git の設定は一時 file に隔離する。

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/session-start-rewrite-follow.sh"
pass=0; fail=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export TMPDIR="$TMP"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$TMP/gitconfig"
git config --global user.email t@t; git config --global user.name t; git config --global init.defaultBranch main
export GIT_REWRITE_FOLLOW_LOG="$TMP/follow.log" GIT_REWRITE_FOLLOW_MAPS_FILE="$TMP/no-maps" GIT_REWRITE_FOLLOW_MAPS=""
ROOT="$TMP/Claude"; mkdir -p "$ROOT"
export CLAUDE_REWRITE_FOLLOW_ROOT="$ROOT"
SS='{"hook_event_name":"SessionStart","session_id":"abcdef12","source":"startup"}'

ok() { pass=$((pass+1)); }
ng() { fail=$((fail+1)); echo "FAIL: $1"; echo "  got: $2"; }

mk_remote() {  # $1 = name → bare remote path、 seed clone = $TMP/seed-$1
  local r="$TMP/remotes/$1.git"; mkdir -p "$r"; git init -q --bare "$r"
  git clone -q "$r" "$TMP/seed-$1" 2>/dev/null
  echo "v1" > "$TMP/seed-$1/f.txt"
  ( cd "$TMP/seed-$1" && git add -A && git commit -qm init && git push -q origin HEAD:main )
  echo "$r"
}
rewrite_message() {  # $1 = name: seed の先頭 commit の message だけを変えて force-push (tree は同じ)
  ( cd "$TMP/seed-$1" && git commit -q --amend -m "rewritten" && git push -q --force origin HEAD:main )
}

# --- 1. 最新の clone だけ → 沈黙
R1="$(mk_remote cur)"; git clone -q "$R1" "$ROOT/repo-cur"
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
[ -z "$out" ] && ok || ng "最新だけなら沈黙" "$out"

# --- 2. 書き換えられた remote → 揃えた行 + HEAD = 新しい先頭 + 未追跡 file は残る
R2="$(mk_remote rw)"; git clone -q "$R2" "$ROOT/repo-rw"
echo "keep" > "$ROOT/repo-rw/untracked.txt"
rewrite_message rw
want="$(cd "$TMP/seed-rw" && git rev-parse HEAD)"
( cd "$ROOT/repo-rw" && git fetch -q )      # 同期 sweep の fetch に相当 (hook 自身は fetch しない)
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
printf '%s' "$out" | grep -q "揃えた" && printf '%s' "$out" | grep -q "repo-rw" && ok || ng "書き換えに揃えた行" "$out"
[ "$(cd "$ROOT/repo-rw" && git rev-parse HEAD)" = "$want" ] && ok || ng "HEAD = 新しい先頭" "$(cd "$ROOT/repo-rw" && git rev-parse HEAD)"
[ -f "$ROOT/repo-rw/untracked.txt" ] && ok || ng "未追跡 file が残る" "missing"
printf '%s' "$out" | grep -q "<system-reminder>" && ok || ng "system-reminder 包装" "$out"
grep -q "followed" "$TMP/follow.log" 2>/dev/null && ok || ng "追従の記録" "$(cat "$TMP/follow.log" 2>/dev/null)"

# --- 3. 2 回目は沈黙 (既に最新)
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
[ -z "$out" ] && ok || ng "揃えた後は沈黙" "$out"

# --- 4. fetch 前 (remote-tracking ref が古い) は何もしない (誤動作しない、 次の session で揃う)
R4="$(mk_remote late)"; git clone -q "$R4" "$ROOT/repo-late"
rewrite_message late
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
printf '%s' "$out" | grep -q "repo-late" && ng "fetch 前は触らない" "$out" || ok
( cd "$ROOT/repo-late" && git fetch -q )
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
printf '%s' "$out" | grep -q "repo-late" && ok || ng "fetch 後に揃う" "$out"

# --- 5. 手元にしか無い commit → 揃えられなかった行、 HEAD は動かない、 pull --rebase を案内しない
R5="$(mk_remote loc)"; git clone -q "$R5" "$ROOT/repo-loc"
( cd "$ROOT/repo-loc" && echo mine > mine.txt && git add -A && git commit -qm "local only" )
rewrite_message loc
( cd "$ROOT/repo-loc" && git fetch -q )
before="$(cd "$ROOT/repo-loc" && git rev-parse HEAD)"
out="$(printf '%s' "$SS" | bash "$HOOK" 2>/dev/null)"
printf '%s' "$out" | grep -q "揃えられなかった" && printf '%s' "$out" | grep -q "repo-loc" && ok || ng "止まった行" "$out"
[ "$(cd "$ROOT/repo-loc" && git rev-parse HEAD)" = "$before" ] && ok || ng "止まった repo の HEAD は動かない" "moved"
printf '%s' "$out" | grep -q "pull --rebase をして" && ng "危ない案内" "$out" || ok

# --- 6. SessionStart 以外 / kill switch / FORCE
out="$(printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Bash"}' | bash "$HOOK" 2>/dev/null)"
[ -z "$out" ] && ok || ng "PreToolUse では沈黙" "$out"
R6="$(mk_remote ks)"; git clone -q "$R6" "$ROOT/repo-ks"; rewrite_message ks; ( cd "$ROOT/repo-ks" && git fetch -q )
out="$(printf '%s' "$SS" | CLAUDE_REWRITE_FOLLOW=0 bash "$HOOK" 2>/dev/null)"
[ -z "$out" ] && ok || ng "kill switch で沈黙" "$out"
out="$(CLAUDE_REWRITE_FOLLOW_FORCE=1 bash "$HOOK" </dev/null 2>/dev/null)"
printf '%s' "$out" | grep -q "repo-ks" && ok || ng "FORCE=1 は stdin 無しで回る" "$out"

# --- 7. symlink 経由 (~/.claude/hooks/ と同じ置き方) でも engine を見つける
R7="$(mk_remote ln)"; git clone -q "$R7" "$ROOT/repo-ln"; rewrite_message ln; ( cd "$ROOT/repo-ln" && git fetch -q )
ln -s "$HOOK" "$TMP/linked-hook.sh"
out="$(printf '%s' "$SS" | bash "$TMP/linked-hook.sh" 2>/dev/null)"
printf '%s' "$out" | grep -q "repo-ln" && ok || ng "symlink 経由でも動く" "$out"

echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
