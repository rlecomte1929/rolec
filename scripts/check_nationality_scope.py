#!/usr/bin/env python3
"""A national of the destination country must never be served immigration-permission content.

WHY THIS EXISTS — a defect found in production on 2026-08-30.

Romain asked whether Denis, a French national returning to France, needs a carte de sejour.
He does not. Residence in your own country is unconditional. The platform said otherwise:
three approved `FRANCE` rows scoped `["OWN_NATIONAL", "EU_EEA"]` told a French citizen he
might need a permanent residence card, a worker's carte de sejour, or a student's. Ireland
carried the same defect on six rows, one of which refuted itself — "PPS Number (EU/EEA
nationals)" was scoped to Irish nationals while its own description read "EU citizens
**other than Irish and UK citizens**".

THE LEGAL DISTINCTION the data collapsed:

  OWN_NATIONAL   national of the destination. UNCONDITIONAL right to enter, reside, work.
                 No visa, no permit, no registration, no conditions that can lapse.
  EU_EEA         free movement under Directive 2004/38/EC Art. 7 — CONDITIONAL on being a
                 worker, self-employed, self-sufficient or a student. Art. 7(3) "retained
                 worker status" exists precisely because that status CAN lapse.
  THIRD_COUNTRY  entry visa + employment permit + immigration registration.

Content written for the second class was scoped to reach the first. The two are not
interchangeable and must not share a scope array for permission content.

WHAT IS DELIBERATELY *NOT* A VIOLATION — the boundary this guard must not break:

  * Posting rules under Reg. 883/2004 (A1 certificates, social-security coordination) turn
    on the SENDING STATE, not on nationality. An Irish national posted from Spain is
    genuinely in scope, so OWN_NATIONAL belongs there.
  * Establishment steps — identity document, employment contract, proof of address, health
    affiliation — apply to a returning national too. `backend/seeds/requirements/france.yaml`
    seeds exactly these as [OWN_NATIONAL, EU_EEA] and its own comment warns against
    "fixing" them. That seed is correct; do not let this guard argue with it.
  * Tax, PRSI and social-charge liability follow residence and employment, not nationality.
    Those belong at `applies_to_nationality_classes = null` (universal), not in any class.

So the guard matches PERMISSION concepts only — residence cards, entry rights, registration
obligations, free-movement worker status — and nothing else.

USAGE
  python scripts/check_nationality_scope.py                    # predicate self-test only
  DATABASE_URL=postgresql://... python scripts/check_nationality_scope.py --db

Exit codes: 0 clean · 1 violations found · 2 could not run the DB sweep.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

OWN_NATIONAL = "OWN_NATIONAL"

# Permission concepts: a right to BE somewhere that must be established, evidenced or
# retained. Matched on the title, which is what a reader sees.
_PERMISSION_PATTERNS = (
    r"carte de s[ée]jour",
    r"residence card",
    r"right of residence",
    r"residence registration",
    r"residence right if",
    r"retained worker",
    r"entry documents",
    r"entry rights",
    r"no visa for",
    r"free-?mover",
    r"registration certificate",
    r"immigration registration",
)

# Concepts that LOOK like permission content but are not, and legitimately keep
# OWN_NATIONAL. Checked first — an exemption beats a match.
_NOT_PERMISSION_PATTERNS = (
    r"a1 certificate",              # Reg. 883/2004 posting — turns on the sending state
    r"social security coordination",
    r"proof of address",
    r"justificatif de domicile",
    r"puma",                        # French health affiliation, residence-BASED but not permission
    r"cpam",
)

_PERMISSION_RE = re.compile("|".join(_PERMISSION_PATTERNS), re.I)
_EXEMPT_RE = re.compile("|".join(_NOT_PERMISSION_PATTERNS), re.I)


def is_permission_content(title: str) -> bool:
    """True when the title describes a right to enter/reside that must be established.

    Exemptions win: a posting certificate mentions residence but is not permission.
    """
    t = title or ""
    if _EXEMPT_RE.search(t):
        return False
    return bool(_PERMISSION_RE.search(t))


def _scope_of(row: Dict[str, Any]) -> Optional[List[str]]:
    raw = row.get("applies_to_nationality_classes_json")
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def violates(row: Dict[str, Any]) -> bool:
    """True when permission content is scoped to reach a national of the destination."""
    scope = _scope_of(row)
    if not scope or OWN_NATIONAL not in scope:
        return False
    return is_permission_content(row.get("title") or "")


def scan(rows: Iterable[Dict[str, Any]]) -> List[Tuple[str, str]]:
    return [
        (str(r.get("country_code") or "?"), str(r.get("title") or "?"))
        for r in rows
        if violates(r)
    ]


def _db_rows() -> List[Dict[str, Any]]:
    from sqlalchemy import create_engine, text  # imported lazily; not needed for the self-test

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set — cannot run the DB sweep", file=sys.stderr)
        sys.exit(2)
    url = re.sub(r"^postgres://", "postgresql://", url)
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT country_code, title, applies_to_nationality_classes_json "
                "FROM public.requirement_items"
            ))
            return [dict(r._mapping) for r in result]
    except Exception as exc:  # noqa: BLE001 — surface any connection/permission failure
        print(f"could not read requirement_items: {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", action="store_true",
                    help="sweep public.requirement_items via DATABASE_URL")
    args = ap.parse_args()

    if not args.db:
        print("[nationality-scope] predicate loaded; pass --db to sweep requirement_items")
        return 0

    offenders = scan(_db_rows())
    if offenders:
        print(f"❌  {len(offenders)} permission requirement(s) reach a national of the "
              f"destination country:\n", file=sys.stderr)
        for country, title in sorted(offenders):
            print(f"  {country}: {title}", file=sys.stderr)
        print("\nA national of the destination has an unconditional right to enter, reside "
              "and work there. Scope these to [\"EU_EEA\"].", file=sys.stderr)
        return 1

    print("✅  No permission requirement reaches a national of its own destination.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
