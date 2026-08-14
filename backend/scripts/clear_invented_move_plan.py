#!/usr/bin/env python3
"""Clear the invented "Oslo, Norway" -> "Singapore" move plan from stored cases.

WHY. `MovePlan.origin` / `.destination` were pydantic DEFAULTS in backend/schemas.py, so they
were written into `relocation_cases.profile_json` for every case that never set them — 1365 of
1401 production cases (97.4%) carried the pair, including Paris->Oslo cases on the FR-NO
corridor. `frontend/src/features/cases/caseEssentials.ts` resolves
`movePlan.origin ?? caseOriginHint` — movePlan FIRST — so the invented value beat the real route
and `HrCaseSummary` rendered "Oslo, Norway -> Singapore" for cases that were nothing of the sort.

The schema defaults are now "". That stops NEW cases acquiring the pair; it does not touch rows
already written. This does.

WHAT IT CLEARS, AND WHAT IT DELIBERATELY DOES NOT
  origin AND destination must first be EXACTLY the invented pair ("Oslo, Norway" /
  "Singapore"). Then ONE of two independent proofs must hold:

    A. the case's own route columns CONTRADICT the pair, or
    B. the ENTIRE movePlan is untouched — no targetArrivalDate, no shippingDatePreference, no
       preferred areas, no schooling date, no inventory — so nobody ever filled this form in and
       the pair can only have come from the schema default.

  Measured on production 2026-08-13: 1377 candidates; arm A fires on 597, arm B on all 1377.

  WHY ARM B COVERS EVERYTHING — which looks like a filter that filters nothing, until you check
  the reason. Exactly 1377 cases have a `movePlan` at all, and of those, **0 have a
  targetArrivalDate, 0 have preferred areas, and 0 have an origin other than "Oslo, Norway"**.
  Nothing in production has ever written a real move plan; the whole sub-object is default. Arm
  B is universally true because the DATA is universally default, not because the predicate is
  vacuous.

  That the filter still discriminates is therefore proved by unit test, not by prod data — prod
  holds no genuine move plan to preserve. See backend/tests/test_clear_invented_move_plan.py: a
  real Oslo -> Singapore case with agreeing route columns survives arm A, and any single real
  movePlan field defeats arm B.

  Only the two keys are cleared. The rest of movePlan (targetArrivalDate, housing, schooling,
  movers) is preserved — it is empty today, but this script must stay correct once something
  starts writing it.

  NOTE: Postgres-only SQL (jsonb operators). This is a production ops tool, like its sibling
  backfill_fact_evidence.py; it will not run against the local SQLite fallback.

--dry-run (THE DEFAULT) writes nothing and prints exactly what would change.

Usage:
    python backend/scripts/clear_invented_move_plan.py                 # dry run
    python backend/scripts/clear_invented_move_plan.py --limit 20      # dry run, first 20
    python backend/scripts/clear_invented_move_plan.py --apply         # write
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import text  # noqa: E402

log = logging.getLogger("clear_invented_move_plan")

INVENTED_ORIGIN = "Oslo, Norway"
INVENTED_DESTINATION = "Singapore"

# Cases carrying the exact invented pair. The route columns come along so the contradiction can
# be judged per row rather than assumed for the batch.
_CANDIDATES = text(
    """
    SELECT id, corridor, origin_city, dest_city,
           origin_country_code, dest_country_code, home_country, host_country,
           profile_json
      FROM public.relocation_cases
     WHERE profile_json IS NOT NULL
       AND profile_json <> ''
       AND (profile_json::jsonb)->'movePlan'->>'origin' = :origin
       AND (profile_json::jsonb)->'movePlan'->>'destination' = :destination
     ORDER BY id
    """
)

_UPDATE = text("UPDATE public.relocation_cases SET profile_json = :profile WHERE id = :id")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def contradicts(row: Dict[str, Any]) -> Tuple[bool, str]:
    """Do this case's own route columns disagree with Oslo -> Singapore?

    Returns (contradicts, reason). Absence of route data is NOT a contradiction — an unknown
    route is not evidence that the stored one is wrong, so those rows are skipped.
    """
    origin_signals = {_norm(row.get("origin_city")), _norm(row.get("origin_country_code")),
                      _norm(row.get("home_country"))} - {""}
    dest_signals = {_norm(row.get("dest_city")), _norm(row.get("dest_country_code")),
                    _norm(row.get("host_country"))} - {""}
    corridor = _norm(row.get("corridor"))

    if not origin_signals and not dest_signals and not corridor:
        return False, "no route data to compare"

    # "Oslo, Norway" as an ORIGIN is contradicted by any origin signal that is not Oslo/Norway.
    oslo_terms = {"oslo", "no", "nor", "norway"}
    sg_terms = {"singapore", "sg", "sgp"}

    if origin_signals and not (origin_signals & oslo_terms):
        return True, f"origin is {sorted(origin_signals)}, not Oslo/Norway"
    if dest_signals and not (dest_signals & sg_terms):
        return True, f"destination is {sorted(dest_signals)}, not Singapore"
    if corridor:
        # corridor is stored like "FR-NO"; the trailing half is the destination.
        tail = corridor.split("-")[-1].strip()
        if tail and tail not in sg_terms:
            return True, f"corridor {row.get('corridor')} does not end in SG"
    return False, "route data is consistent with Oslo -> Singapore"


def is_untouched_move_plan(profile_raw: str) -> bool:
    """True when NO movePlan field other than the invented pair was ever set.

    A user who genuinely typed "Oslo, Norway" would have set something else too — an arrival
    date, a shipping preference, a preferred area. When all of those are empty, the pair can
    only have come from the pydantic default, so it is safe to clear even with no route columns
    to contradict it. Measured 2026-08-13: all 779 candidate rows lacking route data are
    untouched by every one of these fields.
    """
    try:
        mp = (json.loads(profile_raw) or {}).get("movePlan") or {}
    except (TypeError, ValueError, AttributeError):
        return False
    if not isinstance(mp, dict):
        return False
    if mp.get("targetArrivalDate") or mp.get("shippingDatePreference"):
        return False
    housing = mp.get("housing") if isinstance(mp.get("housing"), dict) else {}
    if housing.get("preferredAreas") or housing.get("mustHave") or housing.get("desiredMoveInDate"):
        return False
    schooling = mp.get("schooling") if isinstance(mp.get("schooling"), dict) else {}
    if schooling.get("schoolingStartDate") or schooling.get("priorities"):
        return False
    movers = mp.get("movers") if isinstance(mp.get("movers"), dict) else {}
    if movers.get("inventoryRough") or movers.get("specialItems"):
        return False
    return True


def clear_keys(profile_raw: str) -> Optional[str]:
    """Blank the two invented keys, preserving the rest of the profile. None if nothing to do."""
    try:
        profile = json.loads(profile_raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(profile, dict):
        return None
    mp = profile.get("movePlan")
    if not isinstance(mp, dict):
        return None
    if mp.get("origin") != INVENTED_ORIGIN or mp.get("destination") != INVENTED_DESTINATION:
        return None
    mp["origin"] = ""
    mp["destination"] = ""
    return json.dumps(profile)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Clear the invented Oslo->Singapore move plan")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    p.add_argument("--limit", type=int, help="Process at most N candidate rows")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from backend.database import db  # noqa: E402  (import after sys.path bootstrap)

    with db.engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            _CANDIDATES, {"origin": INVENTED_ORIGIN, "destination": INVENTED_DESTINATION}
        ).mappings().all()]

    if args.limit:
        rows = rows[: args.limit]

    tally: Counter = Counter()
    to_write: List[Tuple[str, str]] = []

    for row in rows:
        will_clear, reason = contradicts(row)
        if not will_clear and is_untouched_move_plan(row["profile_json"]):
            # Arm B: no contradiction available, but the form was never filled in, so the pair
            # can only be the schema default.
            will_clear, reason = True, "movePlan entirely untouched — the pair is the default"
        if not will_clear:
            tally["skipped"] += 1
            log.info("SKIP  %s  %s", row["id"], reason)
            continue
        updated = clear_keys(row["profile_json"])
        if updated is None:
            tally["unparseable"] += 1
            log.info("SKIP  %s  profile_json not in the expected shape", row["id"])
            continue
        tally["clear"] += 1
        to_write.append((row["id"], updated))
        log.info("CLEAR %s  %s", row["id"], reason)

    log.info(
        "\ncandidates=%d  clear=%d  skipped=%d  unparseable=%d",
        len(rows), tally["clear"], tally["skipped"], tally["unparseable"],
    )

    if not args.apply:
        log.info("DRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    written = 0
    for case_id, profile in to_write:
        with db.engine.begin() as conn:
            conn.execute(_UPDATE, {"profile": profile, "id": case_id})
        written += 1
    log.info("APPLIED — %d row(s) updated.", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
