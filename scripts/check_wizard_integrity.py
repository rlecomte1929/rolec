#!/usr/bin/env python3
"""
Wizard integrity check: assert no duplicate question IDs in question bank.
Run: python scripts/check_wizard_integrity.py
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.question_bank import get_all_questions


def main() -> int:
    questions = get_all_questions()
    ids = [q.id for q in questions]
    seen: set[str] = set()
    duplicates: list[str] = []
    for qid in ids:
        if qid in seen:
            duplicates.append(qid)
        seen.add(qid)
    if duplicates:
        print(f"FAIL: Duplicate question IDs: {duplicates}")
        return 1
    print(f"OK: {len(ids)} unique question IDs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
