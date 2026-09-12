#!/usr/bin/env python3
"""CLI wrapper for RP-MEM-002. Run from repo root:

    python -m backend.app.services.requirement_decay
    python scripts/report_requirement_decay.py
"""
from backend.app.services.requirement_decay import main

if __name__ == "__main__":
    raise SystemExit(main())
