#!/usr/bin/env python3
"""CLI gate: a corridor's requirement_items must not be approved without a filled CVR.

WHY THIS EXISTS

IE→ES still has `docs/corridors/ie-es/CVR-TEMPLATE.md` with Status NOT STARTED. Approving
`requirement_items` without a Case Verification Report would serve unverified facts. The
lawyer_review_gate already blocks `needs_lawyer_review` without attestation; this guard
covers the relief-moment / session evidence the CVR template records in section 6.

This is a CLI check, not a request-path parser. Pass `--corridor` (registry id, e.g.
`IE_ES`) — never a destination country alone, because several corridors share one.

USAGE
    python3 scripts/check_corridor_cvr.py --corridor IE_ES
    python3 scripts/check_corridor_cvr.py --corridor IE_ES --root /path/to/repo

EXIT CODES
  0  docs/corridors/<slug>/ has a markdown file whose section 6 Response is Yes or No
  1  no filled CVR (blank template, missing dir, or section 6 empty)
  2  bad invocation
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

_HEADING_6 = re.compile(r"^##\s*6(?:\.|\s|:|$)", re.MULTILINE)
_NEXT_H2 = re.compile(r"^##\s+", re.MULTILINE)
_RESPONSE_LABEL = re.compile(r"response", re.IGNORECASE)
_YES_NO = re.compile(r"^(yes|no)$", re.IGNORECASE)


def corridor_docs_slug(corridor_id: str) -> str:
    return corridor_id.strip().replace("_", "-").lower()


def extract_section_6(markdown: str) -> str:
    match = _HEADING_6.search(markdown)
    if not match:
        return ""
    rest = markdown[match.end() :]
    nxt = _NEXT_H2.search(rest)
    return rest[: nxt.start()] if nxt else rest


def section_6_response(markdown: str) -> Optional[str]:
    """Return 'Yes'/'No' when section 6's Response cell is filled; else None."""
    section = extract_section_6(markdown)
    if not section:
        return None
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or re.fullmatch(r"\|[\s\-:|]+\|?", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if not _RESPONSE_LABEL.search(cells[0]):
            continue
        value = cells[1].strip()
        if _YES_NO.fullmatch(value):
            return value[0].upper() + value[1:].lower()
        return None
    return None


def iter_cvr_markdown(docs_dir: Path) -> List[Path]:
    if not docs_dir.is_dir():
        return []
    return sorted(p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".markdown"})


def check(root: Path, corridor_id: str) -> Tuple[int, List[str]]:
    cid = corridor_id.strip()
    if not cid:
        return 2, ["--corridor is required (registry id such as IE_ES, not a country code)"]
    slug = corridor_docs_slug(cid)
    docs_dir = root / "docs" / "corridors" / slug
    if not docs_dir.is_dir():
        return 1, [f"{docs_dir}: no corridor docs dir; cannot treat {cid} as CVR-complete"]
    files = iter_cvr_markdown(docs_dir)
    if not files:
        return 1, [f"{docs_dir}: no markdown files with a filled section 6 Response (Yes/No)"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        if section_6_response(text) is not None:
            return 0, []
    return 1, [
        f"{docs_dir}: no CVR with section 6 Response filled Yes or No "
        f"(template-only is incomplete; do not approve requirement_items for {cid})"
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corridor",
        required=True,
        help="Registry corridor id (e.g. IE_ES). Not a destination country code.",
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
