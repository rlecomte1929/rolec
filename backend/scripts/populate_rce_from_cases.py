"""AIQ-941 — populate the rce.* engine from REAL public.cases, keyed to public id.

Foundation for the "rule changed → employee banner" flow. The rce engine writer
(corridor_persistence.persist_corridor_case) already exists but was only ever
called by the demo seed (seed_corridor_case.py) with a synthetic uuid5 case_id —
so rce.cases / rce.rule_citations were disconnected from real cases.

This wires that writer to real public.cases, calling persist with
``case_id = public.cases.id``. That UNIFIES the two id-spaces (rce.cases.case_id
== public.cases.id), so active_case_finder returns public case ids directly and
the AIQ-693 banner (GET /api/cases/{id}/rule-updates) resolves by construction —
no bridge column, no sync table.

Idempotent (persist_corridor_case upserts ON CONFLICT). Safe by default: runs in
--dry-run (coverage report only); pass --apply to write.

Coverage: only corridors with a loadable pathway YAML are materialised (today:
IN→DE Blue Card). Cases in uncovered corridors are logged-skipped — adding a
pathway YAML (e.g. FR_NO) widens coverage with no change here.

    DATABASE_URL=postgresql://... python -m backend.scripts.populate_rce_from_cases            # dry-run
    DATABASE_URL=postgresql://... python -m backend.scripts.populate_rce_from_cases --apply
"""
from __future__ import annotations

import argparse
import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..database import db
from ..app.services import corridor_registry
from ..app.services.corridor_persistence import persist_corridor_case
from ..relopass.corridors import load_corridor

log = logging.getLogger(__name__)

# public.cases.status (lowercase) → rce.cases.status CHECK vocabulary (uppercase).
_STATUS_MAP = {
    "draft": "DRAFT",
    "active": "ACTIVE",
    "on_hold": "BLOCKED",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
}
# Cases we bother materialising — in-flight ones a rule change could affect.
_ACTIVE_PUBLIC_STATUSES = ("active", "on_hold", "draft")

# public.cases stores country fields inconsistently — some rows hold ISO-2 codes
# ("IN", "DE"), others full names ("INDIA", "GERMANY"). Corridor pathway YAMLs are
# keyed by ISO-2 (IN_DE, FR_NO), so a name-spelled case silently misses coverage
# (e.g. "INDIA_GERMANY" never resolves to "IN_DE"). Normalise names → ISO-2 here so
# both spellings resolve. Covers the names seen in prod + common relocation markets;
# already-ISO values pass through unchanged.
_COUNTRY_NAME_TO_ISO = {
    "FRANCE": "FR", "GERMANY": "DE", "INDIA": "IN", "NORWAY": "NO",
    "SPAIN": "ES", "NETHERLANDS": "NL", "SWITZERLAND": "CH", "JAPAN": "JP",
    "CANADA": "CA", "SINGAPORE": "SG", "IRELAND": "IE", "BELGIUM": "BE",
    "ITALY": "IT", "PORTUGAL": "PT", "SWEDEN": "SE", "DENMARK": "DK",
    "UNITED KINGDOM": "GB", "UK": "GB", "GREAT BRITAIN": "GB",
    "UNITED STATES": "US", "USA": "US", "UNITED STATES OF AMERICA": "US",
    "UNITED ARAB EMIRATES": "AE", "UAE": "AE",
}


def to_iso_country(cc: Optional[str]) -> Optional[str]:
    """Map a country name to its ISO-2 code; pass ISO-2 (or unknown) through."""
    if not cc:
        return cc
    s = cc.strip().upper()
    return _COUNTRY_NAME_TO_ISO.get(s, s)


def map_status(public_status: Optional[str]) -> str:
    return _STATUS_MAP.get((public_status or "").strip().lower(), "ACTIVE")


def resolve_pathway_file(origin_cc: Optional[str], dest_cc: Optional[str]):
    """(origin, dest country codes) → (pathway Path|None, corridor_id, pathway_id|None).

    Picks the corridor's first declared pathway. Returns a None path when the
    corridor is unknown or has no loadable pathway YAML (→ skip the case).
    """
    if not origin_cc or not dest_cc:
        return None, None, None
    # Normalise country names → ISO-2 before building the corridor id so that
    # name-spelled cases (e.g. INDIA_GERMANY) resolve to their pathway (IN_DE).
    cid = corridor_registry.normalize_corridor_id(
        f"{to_iso_country(origin_cc)}_{to_iso_country(dest_cc)}"
    )
    pathways = corridor_registry.get_pathways(cid)
    if not pathways:
        return None, cid, None
    pid = pathways[0].id
    return corridor_registry.get_pathway_file(cid, pid), cid, pid


def populate_rce_for_public_case(case: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Materialise one public case into rce.* keyed to ``case['id']``.

    Returns the persist summary, or None when the case's corridor has no loadable
    pathway (skip). Reusable per-case so a future cron / create-hook can call it.
    """
    path, cid, pid = resolve_pathway_file(case.get("origin_country_code"), case.get("dest_country_code"))
    if path is None:
        log.info("skip case %s — no pathway for corridor %s", case.get("id"), cid)
        return None
    corridor = load_corridor(path)
    case_id = case["id"] if isinstance(case["id"], uuid.UUID) else uuid.UUID(str(case["id"]))
    target = case.get("target_move_date") or case.get("actual_move_date") or date.today()
    return persist_corridor_case(
        corridor,
        case_id=case_id,
        target_arrival_date=target,
        status=map_status(case.get("status")),
    )


def fetch_active_public_cases() -> List[Dict[str, Any]]:
    sql = text(
        """
        SELECT id, origin_country_code, dest_country_code, target_move_date,
               actual_move_date, status
        FROM public.cases
        WHERE lower(coalesce(status,'')) = ANY(:statuses)
        ORDER BY created_at
        """
    )
    with db.engine.connect() as conn:
        return [dict(r) for r in conn.execute(sql, {"statuses": list(_ACTIVE_PUBLIC_STATUSES)}).mappings().all()]


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Populate rce.* from public.cases (keyed to public id)")
    ap.add_argument("--apply", action="store_true", help="actually write rce.* rows (default: dry-run)")
    args = ap.parse_args(argv)

    cases = fetch_active_public_cases()
    covered, skipped = [], []
    for c in cases:
        path, cid, pid = resolve_pathway_file(c.get("origin_country_code"), c.get("dest_country_code"))
        (covered if path is not None else skipped).append((c, cid, pid))

    print(f"active public cases: {len(cases)}  |  covered (have pathway): {len(covered)}  |  skipped (no pathway): {len(skipped)}")
    by_corridor: Dict[str, int] = {}
    for _, cid, _ in skipped:
        by_corridor[cid or "?"] = by_corridor.get(cid or "?", 0) + 1
    if by_corridor:
        print("  skipped by corridor: " + ", ".join(f"{k}={v}" for k, v in sorted(by_corridor.items())))

    if not args.apply:
        print("\nDRY-RUN — pass --apply to materialise the covered cases into rce.* (idempotent).")
        for c, cid, pid in covered:
            print(f"  would persist case {c['id']} → corridor {cid}/{pid}")
        return 0

    total: Dict[str, int] = {}
    for c, cid, pid in covered:
        summary = populate_rce_for_public_case(c) or {}
        for k, n in summary.items():
            total[k] = total.get(k, 0) + n
        print(f"  persisted case {c['id']} ({cid}/{pid}): " + ", ".join(f"{k}={n}" for k, n in summary.items()))
    print("\n✔ rce.* populated (keyed to public.cases.id). Totals: " + ", ".join(f"rce.{k}={n}" for k, n in sorted(total.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
