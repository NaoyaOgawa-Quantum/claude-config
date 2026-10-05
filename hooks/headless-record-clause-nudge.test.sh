#!/usr/bin/env bash
# headless-record-clause-nudge.test.sh — 自動検査から headless 起動の注入・誤爆・stdin 保持の selftest を実行する
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/lib/test-err-trap.sh"
python3 "$ROOT/hooks/headless-record-clause-nudge.py" --selftest
