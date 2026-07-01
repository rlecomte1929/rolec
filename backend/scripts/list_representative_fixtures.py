"""List eval fixtures still flagged ``verification_status: "representative"``.

Phase-1/2 eval work seeded synthetic golden sets so the gates are non-vacuous and
catch regressions — but synthetic data is NOT authoritative ground truth. Every
such fixture carries a ``verification_status: "representative"`` marker (in a JSON
``_meta`` block or a ``.jsonl`` ``_meta`` line). This script enumerates them so a
human can curate them into authoritative sets.

    python -m backend.scripts.list_representative_fixtures
    python -m backend.scripts.list_representative_fixtures --json

Exit code is always 0 (this is an inventory, not a gate). See
docs/eval/FIXTURE_CURATION.md for the promotion workflow.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

_MARKER = "representative"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_THIS_DIR)
_FIXTURES_DIR = Path(_BACKEND_DIR) / "tests" / "fixtures"


def find_representative_fixtures(root: Path = _FIXTURES_DIR) -> List[str]:
    """Relative paths of fixture files containing the representative marker."""
    hits: List[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if f'"verification_status": "{_MARKER}"' in text or f'"verification_status":"{_MARKER}"' in text:
            hits.append(str(path.relative_to(_BACKEND_DIR.rsplit("/", 1)[0])))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory representative (synthetic) eval fixtures.")
    parser.add_argument("--json", action="store_true", help="Emit JSON list.")
    args = parser.parse_args(argv)

    hits = find_representative_fixtures()
    if args.json:
        print(json.dumps({"count": len(hits), "fixtures": hits}, indent=2))
    else:
        print(f"{len(hits)} fixture file(s) flagged verification_status=representative (need human curation):\n")
        for h in hits:
            print(f"  - {h}")
        print("\nSee docs/eval/FIXTURE_CURATION.md for the promotion workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
