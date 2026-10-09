#!/usr/bin/env python3
"""codex-parent-worker-record-nudge.py — Codex由来の環境IDがあるClaude workerだけに記録条項を渡す (UserPromptSubmit/Stop、非blocking)。

Ordinary Claude sessions without the Codex parent environment remain unchanged.
The common implementation is scripts/lib/codex_worker_contract.py. No permission
decision, parent command rewrite, configuration mutation or model call is made.
"""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/lib'))
from codex_worker_contract import main

if __name__=='__main__':
    raise SystemExit(main('claude'))
