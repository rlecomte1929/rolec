#!/usr/bin/env python3
"""Demand-pull gate: new corridor profiles must name a real anchoring case.

WHY THIS EXISTS

Corridors are created as git directories (`corridors/<ID>/corridor.yaml`), not as rows
in a registry table. A NOT NULL on a fictional `anchor_case_id` column would not stop
someone from adding an empty profile and later loading approved `requirement_items`.

This guard encodes "no corridor without a real case" at the YAML layer that actually
creates corridors. Profiles that already existed when the rule landed are grandfathered;
the grandfather set is frozen in this file and must not grow to dodge the check.

A new profile needs `corridor.anchor.case_id` and/or `corridor.anchor.case_ref`.
`note` alone is not enough.

USAGE
    python3 scripts/check_corridor_anchor.py
    python3 scripts/check_corridor_anchor.py --root /path/to/repo

EXIT CODES
  0  every non-grandfathered corridor.yaml has a usable anchor
  1  a new profile is missing case_id/case_ref
  2  bad invocation or unreadable YAML
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

# Frozen 2026-09-12. Do not add ids here to skip the rule for a new pair.
GRANDFATHERED = frozenset({
    "DE_NO",
    "ES_IE",
    "ES_NL",
    "FR_CH",
    "FR_DE",
    "FR_ES",
    "FR_NL",
    "FR_NO",
    "FR_SG",
    "IE_ES",
    "IN_DE",
    "NO_FR",
    "US_EC",
})


def _nonempty(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def corridor_block(doc: Any) -> Mapping[str, Any]:
    if not isinstance(doc, Mapping):
        return {}
    block = doc.get("corridor")
    return block if isinstance(block, Mapping) else doc


def has_usable_anchor(doc: Any) -> bool:
    block = corridor_block(doc)
    raw = block.get("anchor")
    if not isinstance(raw, Mapping):
        return False
    return _nonempty(raw.get("case_id")) is not None or _nonempty(raw.get("case_ref")) is not None


def iter_corridor_yaml(root: Path) -> List[Path]:
    corridors = root / "corridors"
    if not corridors.is_dir():
        return []
    return sorted(
        p for p in corridors.iterdir()
        if p.is_dir() and (p / "corridor.yaml").is_file()
    )


def check(root: Path) -> Tuple[int, List[str]]:
    """Return (exit_code, messages). Exit 2 if YAML cannot be read."""
    try:
        import yaml
    except ImportError:
        return 2, ["PyYAML is required (backend/requirements.txt)"]

    paths = iter_corridor_yaml(root)
    if not paths:
        return 2, [f"no corridors/*/corridor.yaml under {root}"]

    errors: List[str] = []
    for d in paths:
        cid = d.name
        path = d / "corridor.yaml"
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return 2, [f"{path}: unreadable YAML ({exc})"]
        if cid in GRANDFATHERED:
            continue
        if not has_usable_anchor(doc):
            errors.append(
                f"{path}: new corridor profile must declare corridor.anchor.case_id "
                f"and/or corridor.anchor.case_ref (a real anchoring case). "
                f"Do not add {cid!r} to GRANDFATHERED."
            )
    if errors:
        return 1, errors
    return 0, []


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repo root (directory that contains corridors/)",
    )
    args = parser.parse_args(argv)
    code, messages = check(args.root.resolve())
    for line in messages:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
