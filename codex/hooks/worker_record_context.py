#!/usr/bin/env python3
"""Deliver the shared worker record contract through native Codex lifecycle context."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/lib'))
from codex_worker_contract import main

if __name__=='__main__':
    raise SystemExit(main('codex'))
