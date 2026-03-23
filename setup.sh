#!/bin/bash
# ~/Claude/claude-config/setup.sh
# 新しい端末で clone 後に実行するセットアップスクリプト
#   1. CONVENTIONS.md の symlink を作成（相対パス）
#   2. NaoyaOgawa-Quantum の全リポを ~/Claude 以下に clone（未取得のもののみ）
#
# 使い方:
#   mkdir -p ~/Claude && cd ~/Claude
#   gh repo clone NaoyaOgawa-Quantum/claude-config
#   cd claude-config && ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIRNAME="$(basename "$SCRIPT_DIR")"

# --- 1. Symlink ---
echo "=== Step 1: Setting up symlinks ==="

REL_TARGET="$REPO_DIRNAME/CONVENTIONS.md"
LINK="$CLAUDE_DIR/CONVENTIONS.md"

if [ -L "$LINK" ]; then
    echo "  Symlink already exists: $LINK -> $(readlink "$LINK")"
elif [ -f "$LINK" ]; then
    echo "  WARNING: $LINK exists as a regular file."
    echo "  Back up to $LINK.bak and replace with symlink."
    mv "$LINK" "$LINK.bak"
    ln -s "$REL_TARGET" "$LINK"
    echo "  Created: $LINK -> $REL_TARGET"
else
    ln -s "$REL_TARGET" "$LINK"
    echo "  Created: $LINK -> $REL_TARGET"
fi

# --- 2. Clone all NaoyaOgawa-Quantum repos ---
echo ""
echo "=== Step 2: Cloning NaoyaOgawa-Quantum repos ==="

if ! command -v gh &> /dev/null; then
    echo "  ERROR: gh (GitHub CLI) is not installed. Skipping repo sync."
    echo "  Install with: brew install gh"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo "  ERROR: gh is not authenticated. Run: gh auth login"
    exit 1
fi

# Get all repo names from GitHub
REPOS=$(gh repo list NaoyaOgawa-Quantum --limit 100 --json name --jq '.[].name')
CLONED=0
SKIPPED=0

for REPO in $REPOS; do
    TARGET_DIR="$CLAUDE_DIR/$REPO"
    if [ -d "$TARGET_DIR" ]; then
        SKIPPED=$((SKIPPED + 1))
    else
        echo "  Cloning NaoyaOgawa-Quantum/$REPO ..."
        gh repo clone "NaoyaOgawa-Quantum/$REPO" "$TARGET_DIR" 2>&1 | sed 's/^/    /'
        CLONED=$((CLONED + 1))
    fi
done

echo ""
echo "=== Done ==="
echo "  Cloned: $CLONED repos"
echo "  Skipped (already exist): $SKIPPED repos"
