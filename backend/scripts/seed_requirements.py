#!/usr/bin/env python3
"""AIQ-1349 — idempotent loader for versioned requirement seeds.

Reads a YAML seed (see backend/seeds/requirements/) and upserts each entry into
``requirement_items`` via ``crud.create_requirement_item`` (natural key:
country_code + purpose + title), so re-runs update in place rather than
duplicate. This is the repeatable production path for filling requirement data
country-by-country.

Usage:
    python backend/scripts/seed_requirements.py --file backend/seeds/requirements/long_term_only.yaml
    python backend/scripts/seed_requirements.py --file <yaml> --dry-run
    python backend/scripts/seed_requirements.py --file <yaml> --country GERMANY

The YAML→payload expansion (`build_payloads`) is pure and unit-tested; the DB
write is a thin loop. Exit 0 on success/no-op, 1 on error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Deterministic namespace so re-runs produce stable ids (the natural key still
# governs upsert, but a stable id keeps citations/cross-refs reproducible).
_SEED_NS = uuid.UUID("a1c9e349-0000-4000-8000-000000000001")


def build_payloads(seed: Dict[str, Any], only_country: Optional[str] = None) -> List[Dict[str, Any]]:
    """Pure: expand a seed dict into requirement_items payloads (one per
    requirement × country × purpose). No DB, no clock side effects beyond the
    passed-in stamp."""
    stamp = datetime(2026, 1, 1)  # placeholder; real stamp applied at write time
    purposes_by_country: Dict[str, List[str]] = seed.get("purposes_by_country", {})
    payloads: List[Dict[str, Any]] = []
    for req in seed.get("requirements", []):
        pillar = req["pillar"]
        severity = req["severity"]
        owner = req["owner"]
        applies = req.get("applies_to_assignment_types") or None
        applies_json = json.dumps(applies) if applies else None
        for country, spec in (req.get("countries") or {}).items():
            if only_country and country.upper() != only_country.upper():
                continue
            purposes = purposes_by_country.get(country, [])
            for purpose in purposes:
                title = spec["title"]
                payloads.append({
                    "id": str(uuid.uuid5(_SEED_NS, f"{country}|{purpose}|{title}")),
                    "country_code": country.upper(),
                    "purpose": purpose,
                    "pillar": pillar,
                    "title": title,
                    "description": spec["description"],
                    "severity": severity,
                    "owner": owner,
                    "required_fields_json": json.dumps(req.get("required_fields", [])),
                    "citations_json": json.dumps(req.get("citations", [])),
                    "applies_to_assignment_types_json": applies_json,
                    "last_verified_at": stamp,
                })
    return payloads


def _load_yaml(path: str) -> Dict[str, Any]:
    import yaml  # local import so the pure path/tests don't require pyyaml unless used
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed requirement_items from a YAML file (idempotent).")
    parser.add_argument("--file", required=True, help="Path to the YAML seed.")
    parser.add_argument("--country", default=None, help="Only seed this country (full name).")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be upserted; no writes.")
    args = parser.parse_args(argv)

    try:
        seed = _load_yaml(args.file)
        payloads = build_payloads(seed, only_country=args.country)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR loading/expanding seed: {exc}", file=sys.stderr)
        return 1

    print(f"{len(payloads)} requirement(s) to upsert from {args.file}"
          + (f" (country={args.country})" if args.country else ""))
    if args.dry_run:
        for p in payloads:
            print(f"  - {p['country_code']}/{p['purpose']}: {p['title']} "
                  f"[{p['pillar']}] applies={p['applies_to_assignment_types_json']}")
        return 0

    try:
        from backend.app import crud
        from backend.app.db import SessionLocal
        now = datetime.utcnow()
        with SessionLocal() as db:
            for p in payloads:
                p = dict(p, last_verified_at=now)
                crud.create_requirement_item(db, p)
        print(f"Upserted {len(payloads)} requirement(s).")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR writing requirements: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
