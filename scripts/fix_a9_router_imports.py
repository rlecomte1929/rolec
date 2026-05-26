#!/usr/bin/env python3
"""
fix_a9_router_imports.py  —  AUDIT-A9.4 residual import fix
============================================================
After AUDIT-A9.3 moved 155 modules from backend/services/ into
backend/app/services/, 85 import sites in non-service files were
left pointing at the now-deleted backend.services tree.

This script fixes them in place.  Run from the repo root on the
audit/stage-1-security branch after removing .git/index.lock.

Usage:
    python scripts/fix_a9_router_imports.py           # live run
    python scripts/fix_a9_router_imports.py --dry-run # preview
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

# 1.  backend/app/routers/**  and  backend/app/recommendations/**
#     depth: backend.app.{routers,recommendations}
#     3-dot → backend.services  ➜  2-dot → backend.app.services
RULE_3DOT_TO_2DOT = (
    re.compile(r"\bfrom \.\.\.services\."),
    "from ..services.",
    "3-dot → 2-dot (routers/recommendations)",
)

# 2.  backend/app/services/**  (files that survived in-place + newly copied)
#     depth: backend.app.services
#     3-dot → backend.services  ➜  sibling import (1-dot, drop the word "services")
RULE_3DOT_TO_SIBLING = (
    re.compile(r"\bfrom \.\.\.services\.(\w)"),
    r"from .\1",
    "3-dot → sibling (app/services → app/services)",
)

# 3.  backend/app/main.py  (depth: backend.app)
#     2-dot → backend.services  ➜  1-dot → backend.app.services
RULE_2DOT_TO_1DOT = (
    re.compile(r"\bfrom \.\.services\."),
    "from .services.",
    "2-dot → 1-dot (app/main.py)",
)

# 4.  backend/routes/**  (depth: backend.routes)
#     2-dot → backend.services  ➜  2-dot+app → backend.app.services
RULE_2DOT_TO_APPSERVICES = (
    re.compile(r"\bfrom \.\.services\."),
    "from ..app.services.",
    "2-dot → ..app.services (backend/routes/)",
)


# ---------------------------------------------------------------------------
# File sets
# ---------------------------------------------------------------------------

def files_in(path: str):
    return list((ROOT / path).rglob("*.py"))


APP_ROUTERS       = files_in("backend/app/routers")
APP_RECOMMENDATIONS = files_in("backend/app/recommendations")
APP_SERVICES      = files_in("backend/app/services")
APP_MAIN          = [ROOT / "backend" / "app" / "main.py"]
BACKEND_ROUTES    = files_in("backend/routes")


def apply_rule(text: str, rule) -> tuple[str, int]:
    pattern, replacement, _ = rule
    new_text, n = pattern.subn(replacement, text)
    return new_text, n


def fix_file(path: Path, rules: list) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    total = 0
    for rule in rules:
        text, n = apply_rule(text, rule)
        if n:
            label = rule[2]
            print(f"  [{label}]  {n}x  {path.relative_to(ROOT)}")
            total += n
    if total and not DRY_RUN:
        path.write_text(text, encoding="utf-8")
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if DRY_RUN:
        print("DRY RUN — no files will be modified\n")

    grand_total = 0

    print("=== backend/app/routers/ ===")
    for f in sorted(APP_ROUTERS):
        grand_total += fix_file(f, [RULE_3DOT_TO_2DOT])

    print("\n=== backend/app/recommendations/ ===")
    for f in sorted(APP_RECOMMENDATIONS):
        grand_total += fix_file(f, [RULE_3DOT_TO_2DOT])

    print("\n=== backend/app/services/ (sibling fix) ===")
    for f in sorted(APP_SERVICES):
        grand_total += fix_file(f, [RULE_3DOT_TO_SIBLING])

    print("\n=== backend/app/main.py ===")
    for f in APP_MAIN:
        grand_total += fix_file(f, [RULE_2DOT_TO_1DOT])

    print("\n=== backend/routes/ ===")
    for f in sorted(BACKEND_ROUTES):
        grand_total += fix_file(f, [RULE_2DOT_TO_APPSERVICES])

    print(f"\nTotal substitutions: {grand_total}")
    if DRY_RUN:
        print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
