#!/usr/bin/env bash
# overleaf-push-file.sh — GitHub 側で commit 済みの file を、 指定した分だけ Overleaf に載せる。
#
# Overleaf が正本の repo (conventions/overleaf-integration.md) で、 手元の main を丸ごと push せず、
# 名指しした file だけを Overleaf の最新の上に 1 commit として載せる。 手順は次のとおりで、 手で踏むと長い:
#   overleaf/master の worktree を作る → HEAD の file を写す → commit → push → 取り直して一致を確かめる → main に merge
#
# 既定は dry-run (何が載るかを numstat で見せるだけ)。 実際に載せるのは --push を付けたときだけ。
# ⚠️ Overleaf への push は共著者の編集環境を直接変える。 --push は本人の明示の OK を得てから付ける。
#
# 使い方 (repo の root で):
#   bash ~/Claude/claude-config/scripts/overleaf-push-file.sh -m "<commit message (英語)>" <file> [<file> ...]
#   bash ~/Claude/claude-config/scripts/overleaf-push-file.sh -m "..." --push <file> [...]
#
# 前提: repo に scripts/overleaf-sync.sh があり (PROJECT_ID の正本・token の場所・fetch と --merge を持つ)、
#       載せる file は HEAD に commit 済みで、 作業ツリーに未 commit の変更が無い。
# 終了値: 0 = 載せた / dry-run で差分を見せた / 差分なし、 1 = 前提が欠けた・一致しなかった。
set -euo pipefail

MSG=""; PUSH=0; FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MSG="$2"; shift 2 ;;
    --push) PUSH=1; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) FILES+=("$1"); shift ;;
  esac
done
[ -n "$MSG" ] && [ ${#FILES[@]} -gt 0 ] || { echo "usage: $0 -m <message> [--push] <file>..." >&2; exit 1; }

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
SYNC="scripts/overleaf-sync.sh"
[ -f "$SYNC" ] || { echo "[overleaf-push-file] $SYNC が無い (この repo は Overleaf 連携の形でない)" >&2; exit 1; }
PROJECT_ID="$(sed -n 's/^PROJECT_ID="\([0-9a-f]*\)".*/\1/p' "$SYNC" | head -1)"
[ -n "$PROJECT_ID" ] || { echo "[overleaf-push-file] PROJECT_ID を $SYNC から読めない" >&2; exit 1; }
TOKEN_FILE="${OVERLEAF_TOKEN_FILE:-$HOME/.secrets/overleaf-token}"
[ -s "$TOKEN_FILE" ] || { echo "[overleaf-push-file] token が無い: $TOKEN_FILE" >&2; exit 1; }
mask() { sed -E 's/olp_[A-Za-z0-9]+/olp_REDACTED/g'; }

for f in "${FILES[@]}"; do
  git cat-file -e "HEAD:$f" 2>/dev/null || { echo "[overleaf-push-file] HEAD に無い: $f" >&2; exit 1; }
  git diff --quiet HEAD -- "$f" || { echo "[overleaf-push-file] 未 commit の変更がある: $f (先に commit する)" >&2; exit 1; }
done

STATUS="$(bash "$SYNC" 2>&1 | mask | tail -1)"
echo "$STATUS"
case "$STATUS" in *"behind=0"*) ;; *) echo "[overleaf-push-file] Overleaf が先に進んでいる。 先に bash $SYNC --merge で取り込む" >&2; exit 1 ;; esac

WT="$(mktemp -d)/wt"
cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT
git worktree add -q --detach "$WT" overleaf/master
for f in "${FILES[@]}"; do
  mkdir -p "$WT/$(dirname "$f")"
  git show "HEAD:$f" > "$WT/$f"
  git -C "$WT" add -- "$f"
done
if git -C "$WT" diff --cached --quiet; then
  echo "[overleaf-push-file] 差分なし (Overleaf は既に同じ中身)"; exit 0
fi
echo "[overleaf-push-file] Overleaf に載る差分 (追加 削除 file):"
git -C "$WT" diff --cached --numstat
if [ "$PUSH" -ne 1 ]; then
  echo "[overleaf-push-file] dry-run。 載せるには本人の OK を得てから --push を付ける"; exit 0
fi
git -C "$WT" commit -q -m "$MSG"
git -C "$WT" push "https://git:$(cat "$TOKEN_FILE")@git.overleaf.com/$PROJECT_ID" HEAD:master 2>&1 | mask | tail -2
bash "$SYNC" 2>&1 | mask | tail -1
for f in "${FILES[@]}"; do
  git diff --quiet overleaf/master HEAD -- "$f" || { echo "[overleaf-push-file] 載せた後の中身が一致しない: $f" >&2; exit 1; }
done
cleanup; trap - EXIT
bash "$SYNC" --merge 2>&1 | mask | tail -2
echo "[overleaf-push-file] 載せて一致を確かめ、 main に merge した。 残り = git push origin (と、 repo の「Overleaf マージ後チェック」)"
