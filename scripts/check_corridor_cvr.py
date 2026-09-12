#!/usr/bin/env python3
"""Gate: do not treat a corridor as CVR-verified without a filled relief section.

WHY THIS EXISTS

Huyen eval-first: pending `requirement_items` must not flip to approved without a
Case Verification Report whose section 6 (Relief moment) Response is Yes or No.
IE→ES today has only `docs/corridors/ie-es/CVR-TEMPLATE.md` with that cell blank,
which is why its 25 rows stay pending.

The registry is a git directory (`docs/corridors/<slug>/`), not a `cvr_records`
table and not `corridor.status=live`. This guard reads the artifact. It does not
import serving engines or an LLM, and it does not write `review_status`.

USAGE
    python3 scripts/check_corridor_cvr.py --corridor IE_ES
    python3 scripts/check_corridor_cvr.py --corridor IE_ES --root /path/to/repo

EXIT CODES
  0  a markdown file under docs/corridors/<slug>/ has section 6 Response Yes or No
  1  missing dir, template-only, or Response cell blank
  2  bad invocation
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

_SECTION_6 = re.compile(
    r"^##\s*6\b[^\n]*\n(?P<body>.*?)(?=^##\s+\d|\Z)",
    re.MULTILINE | re.DOTALL,
)
_RESPONSE_ROW = re.compile(
    r"^\|\s*Response\s*\(Yes/No\)\s*\|\s*(?P<value>[^|]*)\|",
    re.IGNORECASE | re.MULTILINE,
)
_YES_NO = frozenset({"yes", "no"})


def docs_slug(corridor_id: str) -> str:
    """IE_ES / IE-ES → ie-es. The pair id, not a destination country_code."""
    return corridor_id.strip().replace("-", "_").lower().replace("_", "-")


def section_6_response(markdown: str) -> Optional[str]:
    match = _SECTION_6.search(markdown)
    if not match:
        return None
    row = _RESPONSE_ROW.search(match.group("body"))
    if not row:
        return None
    value = (row.group("value") or "").strip()
    if value.lower() not in _YES_NO:
        return None
    return value


def iter_cvr_markdown(docs_dir: Path) -> List[Path]:
    if not docs_dir.is_dir():
        return []
    return sorted(p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md")


def check(root: Path, corridor_id: str) -> Tuple[int, List[str]]:
    cid = corridor_id.strip()
    if not cid:
        return 2, ["--corridor is required (pair id, e.g. IE_ES — not country_code Ireland)"]
    slug = docs_slug(cid)
    docs_dir = root / "docs" / "corridors" / slug
    paths = iter_cvr_markdown(docs_dir)
    if not paths:
        return 1, [
            f"{docs_dir}: no CVR markdown for corridor {cid}. "
            f"A filled Case Verification Report is required before approving "
            f"requirement_items for this pair (section 6 Response Yes or No)."
        ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if section_6_response(text) is not None:
            return 0, []
    return 1, [
        f"{docs_dir}: corridor {cid} has {len(paths)} markdown file(s) but none "
        f"fill section 6 Response with Yes or No. The empty CVR template is not a CVR."
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corridor",
        required=True,
        help="Corridor pair id (IE_ES), not a destination country_code",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repo root (directory that contains docs/corridors/)",
    )
    args = parser.parse_args(argv)
    code, messages = check(args.root.resolve(), args.corridor)
    for line in messages:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
