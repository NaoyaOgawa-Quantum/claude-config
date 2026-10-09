#!/usr/bin/env python3
"""headless-record-clause-nudge.py — Claude Bash の記録条項注入の入口。共通実装と検査は scripts/lib/headless_record_clause.py。--selftest。

Compatibility exports keep existing receipt readers and explicit --run callers
working. This adapter makes no permission decision. Codex uses its own adapter.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from headless_record_clause import *

if __name__ == '__main__':
    raise SystemExit(main())
