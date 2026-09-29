#!/usr/bin/env bash
# session-start-rewrite-follow.sh — SessionStart: 履歴を書き換えられた (force-push) repo の clone を、 書き換えられない層 (本 repo) の判定で新しい履歴に揃える + manifest のある repo に pre-push stub を置く (engine = scripts/lib/git_rewrite_follow.py。 fetch はしない = 同じ session の同期 sweep が fetch した remote-tracking ref を読む)
#
# なぜ層1 の hook か (2026-09-29): 追従の script が書き換えられる側の repo (個人層) の中に在ると、 その repo 自身を書き換えた
# とき古い履歴の Mac は script を pull できない。 本 hook は本 repo (書き換えない) から配線され、 判定も本 repo の lib だけで
# 行う。 同期 sweep (個人層の hook → 層1 engine repo-sync-sweep.sh) も同じ lib を diverged の repo に呼ぶので、 普段はそちらが
# 先に揃える。 本 hook は (a) 同期 sweep が配線されていない Mac (b) 同期 sweep の fetch が 8 秒で終わらず次の session に
# 回った repo (c) pre-push stub の設置、 を拾う。 並列の hook とは順序が無い (conventions/hook-authoring.md#parallel-hooks-no-ordering)
# ので fetch に依存せず「今 remote-tracking ref が示す状態」 だけを見る (= 遅れても次の session で揃う、 誤動作はしない)。
#
# 出力: 揃えた / 止まった / stub を置いた repo が 1 つでもあれば <system-reminder> で 1 行ずつ。 全て最新なら完全沈黙。
# 安全: pull / merge / rebase はしない。 reset --keep だけ (未 commit の変更は保つ、 書き換えで変わった file に重なれば止まる)。
# fail-open: python3 / engine 不在・例外・timeout は無出力 exit 0。
#
# env:
#   CLAUDE_REWRITE_FOLLOW=0            本 hook を止める (kill switch)
#   CLAUDE_REWRITE_FOLLOW_ROOT         走査 root (既定 $HOME/Claude)
#   CLAUDE_REWRITE_FOLLOW_FORCE=1      SessionStart 判定を skip (test 用)
#   CLAUDE_REWRITE_FOLLOW_ENGINE       CLI の path (test 用、 既定 = 本 repo の scripts/git-rewrite-follow.py)
#   GIT_REWRITE_FOLLOW_MAPS_FILE 等    対応表の外部供給 (lib の docstring)
# test = hooks/session-start-rewrite-follow.test.sh

set -u
[ "${CLAUDE_REWRITE_FOLLOW:-1}" = "0" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

if [ "${CLAUDE_REWRITE_FOLLOW_FORCE:-0}" != "1" ]; then
  raw="$(cat 2>/dev/null || true)"
  case "$raw" in
    *'"SessionStart"'*) : ;;
    *) exit 0 ;;
  esac
fi

ROOT="${CLAUDE_REWRITE_FOLLOW_ROOT:-$HOME/Claude}"
[ -d "$ROOT" ] || exit 0

# symlink (~/.claude/hooks/ → <base>/claude-config/hooks/) を辿って repo を特定する
SELF="${BASH_SOURCE[0]}"
while [ -L "$SELF" ]; do
  LINK="$(readlink "$SELF")"
  case "$LINK" in /*) SELF="$LINK" ;; *) SELF="$(dirname "$SELF")/$LINK" ;; esac
done
REPO="$(cd "$(dirname "$SELF")/.." 2>/dev/null && pwd)" || exit 0
ENGINE="${CLAUDE_REWRITE_FOLLOW_ENGINE:-$REPO/scripts/git-rewrite-follow.py}"
[ -f "$ENGINE" ] || exit 0

_TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then _TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then _TIMEOUT_BIN="gtimeout"; fi
if [ -n "$_TIMEOUT_BIN" ]; then
  out="$("$_TIMEOUT_BIN" 60 python3 "$ENGINE" sweep --root "$ROOT" --tsv 2>/dev/null)" || true
else
  out="$(python3 "$ENGINE" sweep --root "$ROOT" --tsv 2>/dev/null)" || true
fi
[ -n "$out" ] || exit 0

followed="$(printf '%s\n' "$out" | awk -F'\t' '$1=="F"{print "  - "$2}')"
stopped="$(printf '%s\n'  "$out" | awk -F'\t' '$1=="S"{print "  - "$2}')"
stubs="$(printf '%s\n'    "$out" | awk -F'\t' '$1=="P"{print "  - "$2}')"
[ -z "$followed" ] && [ -z "$stopped" ] && [ -z "$stubs" ] && exit 0

printf '<system-reminder>\n'
printf '🔀 履歴を書き換えられた repo への追従 (層1 session-start-rewrite-follow、 判定 = scripts/lib/git_rewrite_follow.py、 記録 = ~/.claude/state/rewrite-follow.log)\n'
if [ -n "$followed" ]; then
  printf '\n✅ 新しい履歴に揃えた (reset --keep、 未 commit の変更は保った):\n%s\n' "$followed"
fi
if [ -n "$stopped" ]; then
  printf '\n⚠️ 揃えられなかった (このリポで作業する前に解決。 git pull / merge / rebase はしない = 古い履歴が合流し、 消した中身が次の push で remote に戻る):\n%s\n' "$stopped"
  printf '   → 手元にしか無い commit の中身を確かめ、 要るものだけ新しい履歴に cherry-pick で載せ直す。 判定の再実行 = python3 %s follow --repo <repo>\n' "$ENGINE"
fi
if [ -n "$stubs" ]; then
  printf '\n🔒 古い世代の push を止める pre-push stub:\n%s\n' "$stubs"
fi
printf '</system-reminder>\n'
exit 0
