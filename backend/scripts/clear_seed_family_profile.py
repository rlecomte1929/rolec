#!/usr/bin/env python3
"""Clear the invented family-of-four seed from stored `relocation_cases.profile_json`.

WHY. `familySize`, `dependents`, `Spouse.wantsToWork` and `HousingPreferences.bedroomsMin`
were pydantic DEFAULTS in backend/schemas.py (4, two blank Child(), True, 3). Every
construction of `RelocationProfile(userId=...)` wrote that family into profile_json —
`backend/main.py` alone has eleven, `POST /api/hr/cases` among them.

Measured on production 2026-08-22: **2001 of 2037 cases (98.2%)** carry all four markers
together, and **0 cases carry any other familySize**. Nothing has ever written a real one.

It was not inert. `app/services/rules_engine.py` branches on `spouse.get("wantsToWork")` on
the SERVING path, so the default put spouse work-authorisation requirements on the roadmap
of every single-person relocation; `compliance_engine`, `policy_engine`,
`services/country_resources` and `services/resources/context_service` read the same key.

The schema defaults are now None/[]. That stops NEW cases acquiring the seed; it does not
touch rows already written. This does.

WHAT IT CLEARS, AND WHAT IT DELIBERATELY DOES NOT

  This is the same two-arm shape as clear_invented_move_plan.py, and for the same reason:
  the seed is indistinguishable from a real family of four by value alone, so a value match
  is never sufficient on its own.

  ALL FOUR markers must be present in their exact default form:
      familySize == 4
      dependents == two Child() entries with every field null
      spouse.wantsToWork is True AND spouse.fullName is null
      movePlan.housing.bedroomsMin == 3

  AND the profile must show no sign of anyone having filled the family section in:
      no maritalStatus, no spouse name/nationality/occupation, no dependent carrying a
      firstName / dateOfBirth / currentGrade, no housing preferredAreas or mustHave.

  A real family of four is preserved because a human who entered one leaves at least one of
  those traces — a spouse name, a child's name, a marital status. A profile with four people,
  a working spouse, three bedrooms and not one identifying detail about any of them is the
  schema default and nothing else.

  Clearing sets the four keys back to what a fresh profile now produces (None / []). It does
  NOT delete the objects, so shape-dependent readers keep working, and it touches no other
  key in the blob.

  MEASURED ON PRODUCTION 2026-08-22: 2038 profiles scanned, 2002 match all four markers,
  2002 would clear, **0 are held back by the untouched test**. That looks like a guard that
  guards nothing, and the reason it is not is the same as arm B in
  clear_invented_move_plan.py: not one production profile has ever had a spouse name, a
  marital status, a named dependent or a housing preference entered. The predicate is
  universally true because the DATA is universally default. Keep the guard — it is what
  makes the script safe to re-run after real intake data starts arriving, which is exactly
  when it stops being universally true.

SAFETY. Dry run by default; --apply writes. Per-row, so a failure cannot half-write a blob.
Never run against production without a backup — see CLAUDE.md, "Migration discipline"
(this is a data backfill, not a schema change, so execute_sql/`--apply` is the right lane).

  python backend/scripts/clear_seed_family_profile.py                 # dry run, all rows
  python backend/scripts/clear_seed_family_profile.py --case <id>     # dry run, one case
  python backend/scripts/clear_seed_family_profile.py --apply --case <id>
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text  # noqa: E402

log = logging.getLogger("clear_seed_family_profile")

_CANDIDATES = text(
    "SELECT id::text AS id, profile_json FROM relocation_cases "
    "WHERE profile_json IS NOT NULL AND profile_json <> ''"
)
_ONE = text(
    "SELECT id::text AS id, profile_json FROM relocation_cases "
    "WHERE id::text = :id AND profile_json IS NOT NULL AND profile_json <> ''"
)
_UPDATE = text(
    "UPDATE relocation_cases SET profile_json = :profile, updated_at = NOW() "
    "WHERE id::text = :id"
)

_BLANK_CHILD_KEYS = ("firstName", "dateOfBirth", "currentGrade", "languageNeeds")


def _is_blank_child(child: Any) -> bool:
    return isinstance(child, dict) and all(child.get(k) in (None, "") for k in _BLANK_CHILD_KEYS)


def has_seed_markers(profile: Dict[str, Any]) -> Tuple[bool, str]:
    """All four defaults present, in exactly their default form."""
    if profile.get("familySize") != 4:
        return False, "familySize is not the default 4"

    dependents = profile.get("dependents")
    if not isinstance(dependents, list) or len(dependents) != 2:
        return False, "dependents is not the default pair"
    if not all(_is_blank_child(c) for c in dependents):
        return False, "a dependent carries real data"

    spouse = profile.get("spouse") or {}
    if spouse.get("wantsToWork") is not True:
        return False, "spouse.wantsToWork is not the default True"
    if spouse.get("fullName"):
        return False, "spouse has a name"

    housing = ((profile.get("movePlan") or {}).get("housing")) or {}
    if housing.get("bedroomsMin") != 3:
        return False, "bedroomsMin is not the default 3"

    return True, "all four schema defaults present"


def is_untouched_family(profile: Dict[str, Any]) -> Tuple[bool, str]:
    """No trace of a human having described a household."""
    if profile.get("maritalStatus"):
        return False, "maritalStatus was entered"

    spouse = profile.get("spouse") or {}
    for key in ("fullName", "nationality", "occupation", "educationLevel"):
        if spouse.get(key):
            return False, f"spouse.{key} was entered"

    for child in profile.get("dependents") or []:
        if isinstance(child, dict) and any(child.get(k) for k in _BLANK_CHILD_KEYS):
            return False, "a dependent was entered"

    housing = ((profile.get("movePlan") or {}).get("housing")) or {}
    if housing.get("preferredAreas") or housing.get("mustHave"):
        return False, "housing preferences were entered"

    return True, "family section entirely untouched"


def clear_keys(profile_raw: str) -> Optional[Tuple[str, str]]:
    """Return (updated_json, reason), or None when this row must not be touched."""
    try:
        profile = json.loads(profile_raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(profile, dict):
        return None

    seeded, why = has_seed_markers(profile)
    if not seeded:
        return None
    untouched, why_untouched = is_untouched_family(profile)
    if not untouched:
        return None

    profile["familySize"] = None
    profile["dependents"] = []
    if isinstance(profile.get("spouse"), dict):
        profile["spouse"]["wantsToWork"] = None
    housing = ((profile.get("movePlan") or {}).get("housing"))
    if isinstance(housing, dict):
        housing["bedroomsMin"] = None

    return json.dumps(profile), f"{why}; {why_untouched}"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Clear the invented family-of-four seed profile")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    p.add_argument("--case", help="Restrict to a single relocation_cases id")
    p.add_argument("--limit", type=int, help="Process at most N candidate rows")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from backend.database import db  # noqa: E402  (import after sys.path bootstrap)

    with db.engine.connect() as conn:
        if args.case:
            rows = [dict(r) for r in conn.execute(_ONE, {"id": args.case}).mappings().all()]
        else:
            rows = [dict(r) for r in conn.execute(_CANDIDATES).mappings().all()]

    if args.limit:
        rows = rows[: args.limit]

    tally: Counter = Counter()
    to_write: List[Tuple[str, str]] = []

    for row in rows:
        result = clear_keys(row["profile_json"])
        if result is None:
            tally["skipped"] += 1
            continue
        updated, reason = result
        tally["clear"] += 1
        to_write.append((row["id"], updated))
        log.info("CLEAR %s  %s", row["id"], reason)

    log.info("\nscanned=%d  clear=%d  skipped=%d", len(rows), tally["clear"], tally["skipped"])

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


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
