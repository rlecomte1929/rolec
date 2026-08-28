#!/usr/bin/env python3
"""Fail when the company plan-tier vocabulary drifts between Python and TypeScript.

WHY THIS EXISTS
---------------
`companies.plan_tier` was written by one vocabulary and read by another, and neither side
could see the other, so the admin UI confidently displayed a tier the database does not hold.

Measured against production on 2026-08-28, before the fix:

    SELECT plan_tier, count(*) FROM public.companies GROUP BY 1;
      starter → 116
      growth  →   3

`create_company` wrote {starter, growth, enterprise}. The frontend adapter recognised only
{low, medium, premium} and coerced everything else to 'low'. Zero of 119 rows matched, so:

  * every company rendered as "low", including the three on `growth` — an enterprise customer
    would have been shown as bottom-tier;
  * the "Premium" KPI tile and the medium/premium filter options were structurally dead, and
    an always-empty table reads as "no premium customers", not as a bug;
  * `update_company` whitelisted {low, medium, premium}, so setting a real tier appended
    nothing to its UPDATE and **returned success having written nothing**.

A TypeScript union cannot constrain Python, and the reverse is equally true — which is exactly
how the two sides drifted without either test suite noticing. This guard is the only thing that
reads both.

PLACEMENT MATTERS. It runs from `repo-hygiene`, which is deliberately unfiltered. A test living
in the frontend suite would not run for a Python-only edit (the `frontend` filter is
`frontend/**`), and a pytest would not run for a TypeScript-only edit. Either placement would
re-open the exact gap this exists to close.

NOT the same field: `types/relopass-api-contracts.ts` `PlanTier = basic|hr|admin` is the USER
profile tier used for sidebar gating. It is unrelated and deliberately not checked here.

Exit codes
----------
  0 — all four declarations agree (prints the vocabulary and where it was found)
  1 — they disagree (each site and its value are printed)
  2 — the guard could not run: a source file is missing, or a declaration could not be parsed.
      A pattern that silently matches nothing would make this guard pass over anything.

USAGE
-----
  python scripts/check_plan_tier_contract.py [--root .]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# (label, relative path, regex capturing the comma-separated member list)
SITES: List[Tuple[str, str, re.Pattern[str]]] = [
    (
        "python create_company",
        "backend/db/companies.py",
        re.compile(r"if plan_val not in \(([^)]*)\)"),
    ),
    (
        "python update_company",
        "backend/db/companies.py",
        re.compile(r"if pt in \(([^)]*)\)"),
    ),
    (
        "ts CompanyPlanTier",
        "frontend/src/types.ts",
        re.compile(r"export type CompanyPlanTier\s*=\s*([^;]*);"),
    ),
    (
        "ts CompanyV2PlanTier",
        "frontend/src/features/platform-v2/companies/adapter.ts",
        re.compile(r"export type CompanyV2PlanTier\s*=\s*([^;]*);"),
    ),
    (
        "ts VALID_PLAN",
        "frontend/src/features/platform-v2/companies/adapter.ts",
        re.compile(r"VALID_PLAN\s*=\s*new Set<CompanyV2PlanTier>\(\[([^\]]*)\]\)"),
    ),
]

_MEMBER = re.compile(r"['\"]([a-z_]+)['\"]")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    found: Dict[str, Set[str]] = {}
    for label, rel, pattern in SITES:
        path = root / rel
        if not path.is_file():
            print(f"::error::{rel} is missing - the plan-tier contract cannot be checked.")
            return 2
        match = pattern.search(path.read_text(encoding="utf-8"))
        if not match:
            print(
                f"::error::could not locate the {label} declaration in {rel}. "
                "The guard cannot silently pass over a declaration it failed to parse - "
                "update the pattern in this script if the code was refactored."
            )
            return 2
        members = set(_MEMBER.findall(match.group(1)))
        if not members:
            print(f"::error::{label} in {rel} parsed to an EMPTY vocabulary.")
            return 2
        found[label] = members

    distinct = {frozenset(v) for v in found.values()}
    if len(distinct) != 1:
        print(
            f"::error::company plan_tier vocabulary disagrees across {len(found)} declarations. "
            "The database keeps what Python writes; the UI renders what TypeScript accepts, "
            "and coerces anything it does not recognise - silently."
        )
        for label, members in found.items():
            print(f"    {label:24} {sorted(members)}")
        print(
            "\nTo fix: make all of them the same set. The producing side "
            "(backend/db/companies.py create_company) is the source of truth - verify against "
            "the live table before changing it:\n"
            "    SELECT plan_tier, count(*) FROM public.companies GROUP BY 1;"
        )
        return 1

    vocabulary = sorted(next(iter(distinct)))
    print(
        f"check_plan_tier_contract: OK - {len(found)} declaration(s) agree on {vocabulary}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
