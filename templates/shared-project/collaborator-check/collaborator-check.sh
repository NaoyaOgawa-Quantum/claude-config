#!/usr/bin/env bash
# collaborator-check.sh — 共有リポの各 clone で session 開始時に走り、 その repo が各自の手元に要る設定 (個人の token・道具) と初回に読む節を、 欠けている時だけ直し方つきで出す。
#
# 正本 = claude-config の templates/shared-project/collaborator-check/ 。 repo の
# tools/collaborator-check/ は写し (共同編集者は claude-config を持たないので repo 単体で動く)。
# 直すときは正本を直し、 scripts/install-collaborator-check.py install <repo> で配り直す。
# 規約 = conventions/shared-repo.md#collaborator-check
#
# 設定 = repo root の .collaborator-check.conf (1 行 1 項目、 # で始まる行と空行は無視):
#   file <path> [<上書きの環境変数>] -- <直し方>     例: file ~/.secrets/svc-token SVC_TOKEN_FILE -- 自分の token を発行して置く
#   command <名前> -- <直し方>                       例: command latexmk -- TeX Live を入れる
#   read <file の節> -- <何が書いてあるか>            例: read CLAUDE.md §共同編集者向け -- 招待された人の手順
#
# 出力: file / command が揃っていれば何も出さない。 read は clone ごとの初回だけ出す
# (印 = .git/collaborator-check.seen)。 欠けた項目と初回の read を 1 block で出す。
# 終了値は常に 0 (session を止めない)。 呼び方:
#   bash tools/collaborator-check/collaborator-check.sh            # 普通に (Claude Code の SessionStart hook もこれ)
#   bash tools/collaborator-check/collaborator-check.sh --all      # 揃っている項目も ✅ で出す (確認用、 初回の印は付けない)

ALL=0
[ "${1:-}" = "--all" ] && ALL=1

ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)" || exit 0
CONF="$ROOT/.collaborator-check.conf"
[ -f "$CONF" ] || exit 0

GITDIR="$(git -C "$ROOT" rev-parse --absolute-git-dir 2>/dev/null)"
SEEN=""
[ -n "$GITDIR" ] && SEEN="$GITDIR/collaborator-check.seen"
FIRST=0
if [ -n "$SEEN" ] && [ ! -e "$SEEN" ]; then FIRST=1; fi

missing=""
ok=""
reads=""

expand_home() {
  case "$1" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s/%s' "$HOME" "${1#\~/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  head="${line%% -- *}"
  how=""
  [ "$head" != "$line" ] && how="${line#* -- }"
  set -f
  # shellcheck disable=SC2086
  set -- $head
  set +f
  kind="${1:-}"
  case "$kind" in
    file)
      path="$(expand_home "${2:-}")"
      envvar="${3:-}"
      shown="${2:-}"
      if [ -n "$envvar" ]; then
        val="$(printenv "$envvar" 2>/dev/null)"
        if [ -n "$val" ]; then path="$(expand_home "$val")"; shown="$val (\$$envvar)"; fi
      fi
      if [ -s "$path" ]; then
        ok="$ok
  ✅ $shown がある"
      else
        missing="$missing
  ❌ $shown が無い → $how"
      fi
      ;;
    command)
      name="${2:-}"
      if command -v "$name" >/dev/null 2>&1; then
        ok="$ok
  ✅ $name がある"
      else
        missing="$missing
  ❌ $name が無い → $how"
      fi
      ;;
    read)
      shift
      reads="$reads
  📖 $* を読む${how:+ ($how)}"
      ;;
    *)
      missing="$missing
  ⚠️ .collaborator-check.conf の読めない行: $line"
      ;;
  esac
done < "$CONF"

show_reads=0
[ "$FIRST" = 1 ] && [ -n "$reads" ] && show_reads=1
[ "$ALL" = 1 ] && [ -n "$reads" ] && show_reads=1

if [ -z "$missing" ] && [ "$show_reads" = 0 ] && [ "$ALL" = 0 ]; then
  exit 0
fi

echo "🧩 この共有リポを手元で使う準備 (tools/collaborator-check。 設定 = .collaborator-check.conf)"
[ "$show_reads" = 1 ] && [ "$ALL" = 0 ] && echo "  この clone で初めての session:"
[ "$show_reads" = 1 ] && printf '%s\n' "${reads#?}"
[ -n "$missing" ] && printf '%s\n' "${missing#?}"
[ "$ALL" = 1 ] && [ -n "$ok" ] && printf '%s\n' "${ok#?}"
if [ -n "$missing" ] || [ "$show_reads" = 1 ]; then
  echo "  → agent はこの block を user に 1 項目 1 行で伝える (❌ は直すまで毎回出る)"
fi

if [ "$FIRST" = 1 ] && [ "$ALL" = 0 ] && [ -n "$SEEN" ]; then
  : > "$SEEN" 2>/dev/null || true
fi
exit 0
