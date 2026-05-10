#!/bin/bash
# find-personal-layer.sh — sourceable helper to resolve the personal-layer dir.
#
# 正本: claude-config/scripts/lib/find-personal-layer.sh
#
# Usage (from another script):
#     . "$(dirname "$0")/lib/find-personal-layer.sh"
#     LAYER="$(find_personal_layer)"
#     if [ -n "$LAYER" ] && [ -f "$LAYER/sensitive-terms.txt" ]; then
#         # use $LAYER/sensitive-terms.txt
#     fi
#
# Returns: absolute path of the personal-layer directory on stdout, or
# empty string if none is detected (or detection disabled).
#
# 検出ロジックは `setup.sh` Step 5a (L592-622) と同じ — どちらかが変わったら
# 両方を sync する責任が編集者にある。 Conceptual reference は
# `docs/personal-layer.md`。
#
# Logic:
#   1. CLAUDE_PERSONAL_LAYER=none      → empty (detection disabled)
#   2. CLAUDE_PERSONAL_LAYER=<dir>     → that dir if it has both
#                                        `.claude-personal-layer` and `CLAUDE.md`,
#                                        otherwise empty (silent fallback)
#   3. それ以外                          → scan <base>/*/ for the marker file;
#                                        exactly one match → that dir,
#                                        zero or multiple → empty
#
# `<base>` は本 file の location から計算される: 本 file は
# `<base>/claude-config/scripts/lib/` に置かれているので、 三つ親が <base>。
#
# Layer-1 (claude-config, public) の design contract:
#   - 本 helper は特定の personal-layer ディレクトリ名 (例: `<owner>-prefs`) を
#     literal で持たない。 検出は完全に dynamic。
#   - foreign user (= 個人層を持たない claude-config 利用者) では空文字を
#     返すので、 呼び出し側は「空なら skip / fallback」 で graceful に扱う。
#   - 複数個人層が見つかった場合は silent に空を返す (各 caller の用途では
#     fail-safe な選択。 setup.sh はこれを error にして symlink 競合を避ける)。

find_personal_layer() {
    local self_dir base layers d
    self_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    # self_dir = .../claude-config/scripts/lib
    # base     = .../   (parent of claude-config repo root)
    base="$(cd "$self_dir/../../.." && pwd)"

    if [ "${CLAUDE_PERSONAL_LAYER:-}" = "none" ]; then
        echo ""
        return 0
    fi
    if [ -n "${CLAUDE_PERSONAL_LAYER:-}" ]; then
        if [ -f "$CLAUDE_PERSONAL_LAYER/.claude-personal-layer" ] && \
           [ -f "$CLAUDE_PERSONAL_LAYER/CLAUDE.md" ]; then
            echo "${CLAUDE_PERSONAL_LAYER%/}"
        else
            # explicit but invalid → silent fallback to empty
            echo ""
        fi
        return 0
    fi

    layers=()
    for d in "$base"/*/; do
        if [ -f "${d}.claude-personal-layer" ] && [ -f "${d}CLAUDE.md" ]; then
            layers+=("${d%/}")
        fi
    done
    if [ "${#layers[@]}" -eq 1 ]; then
        echo "${layers[0]}"
    else
        echo ""
    fi
}
