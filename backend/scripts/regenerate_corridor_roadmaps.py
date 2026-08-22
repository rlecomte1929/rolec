#!/usr/bin/env python3
"""Regenerate case_milestones for cases on a corridor, so they pick up the overlay.

WHY. #1938 wired `roadmap_corridor_overlay` into `timeline_service.compute_default_milestones`.
Milestones are written once, at case creation/submit, so every case created before it keeps
the generic pack. 55 cases already have corridor_* milestones; Andrea's 6ecadafe has 16
generic task_* ones and none of the CSEP journey.

This is the bulk arm of `POST /api/hr/cases/{case_id}/roadmap/regenerate`. Same service, same
reconciliation, same protections — it only chooses WHICH cases.

GUARDED AND OPT-IN
  * Dry run by default. `--apply` writes.
  * `--corridor ES_IE` (or `--case <id>`) is REQUIRED. There is no "all cases" mode: a
    roadmap is what an employee is told to do, and a repo script should not be able to
    rewrite every one of them from one typo.
  * Never touches `roadmap_review_status`. An absent row there means RELEASED, so writing
    one could publish an unreviewed roadmap or retract a released one. Regenerating the
    STEPS and deciding whether HR approved them are separate decisions.
  * Completed/in-progress milestones and service-owned rows are preserved by the service
    itself — see roadmap_regeneration_service.PROTECTED_STATUSES / PROTECTED_SOURCES.
  * Idempotent: re-running reports no_change for cases already regenerated.

  python backend/scripts/regenerate_corridor_roadmaps.py --corridor ES_IE
  python backend/scripts/regenerate_corridor_roadmaps.py --corridor ES_IE --apply
  python backend/scripts/regenerate_corridor_roadmaps.py --case 6ecadafe-... --apply
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

from backend.app.services.roadmap_regeneration_service import (  # noqa: E402
    regenerate_case_milestones,
)

log = logging.getLogger("regenerate_corridor_roadmaps")

# wizard_cases holds the draft the generator reads; relocation_cases is the case shell.
_BY_CORRIDOR = text(
    """
    SELECT wc.id::text AS case_id, wc.draft_json
      FROM wizard_cases wc
     WHERE upper(COALESCE(wc.draft_json::jsonb #>> '{relocationBasics,originCountry}', '')) = :origin
       AND upper(COALESCE(wc.draft_json::jsonb #>> '{relocationBasics,destCountry}', '')) = :dest
    """
)
_BY_CASE = text("SELECT id::text AS case_id, draft_json FROM wizard_cases WHERE id::text = :id")


def _parse_corridor(value: str) -> Tuple[str, str]:
    parts = value.replace("-", "_").split("_")
    if len(parts) != 2 or not all(len(p) == 2 for p in parts):
        raise SystemExit(f"--corridor must look like ES_IE, got {value!r}")
    return parts[0].upper(), parts[1].upper()


#: Errors worth one more attempt: the connection died, not the work.
#: Deliberately narrow — a broad `except Exception: retry` would paper over a genuine data
#: fault by running it twice, and on an --apply run that is a second write.
_TRANSIENT_DB_MARKERS = (
    "ssl connection has been closed",
    "server closed the connection",
    "connection already closed",
    "terminating connection",
    "could not receive data from server",
    "eof detected",
)


def _is_transient_db_error(exc: BaseException) -> bool:
    text_form = f"{type(exc).__name__}: {exc}".lower()
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        text_form += f" {type(cause).__name__}: {cause}".lower()
    return any(marker in text_form for marker in _TRANSIENT_DB_MARKERS)


def _regenerate_with_retry(db: Any, case_id: str, draft: Dict[str, Any], *, apply: bool):
    """One retry, and only for a dropped connection.

    MEASURED 2026-08-22 on the FR_NO population: the FIRST case of every run died with
    `SSL connection has been closed unexpectedly`, and it was POSITION-dependent, not
    case-dependent — a case that succeeded inside a batch failed when run first, and vice
    versa. So a bulk run silently lost one case, and `--case <id>` — the obvious way to
    check a single case before committing to a bulk write — failed 100% of the time.

    Supabase's transaction pooler closes it. `pool_pre_ping` is already on in db_config and
    does not catch this: the connection is alive when pinged and dies on the first real
    statement. A warm-up `SELECT 1` does not catch it either — that was tried, the SELECT
    succeeded, and the following case still failed, so the warm-up was removed rather than
    left in as a no-op whose docstring claimed otherwise.

    Safe on an --apply run because `regenerate_case_milestones` is idempotent: a second run
    over an already-regenerated case is a no-op (test_a_second_run_is_a_no_op). A retry on a
    NON-transient error would not be safe — it would run genuinely faulty work twice, and on
    --apply that is a second write — which is why the marker list is narrow rather than a
    bare `except Exception: retry`.
    """
    try:
        return regenerate_case_milestones(db, case_id, draft=draft, apply=apply)
    except Exception as exc:
        if not _is_transient_db_error(exc):
            raise
        log.warning("transient DB error on %s (%s) — retrying once",
                    case_id, exc.__class__.__name__)
        return regenerate_case_milestones(db, case_id, draft=draft, apply=apply)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Regenerate roadmaps for a corridor's cases")
    p.add_argument("--corridor", help="e.g. ES_IE. Required unless --case is given.")
    p.add_argument("--case", help="Regenerate exactly one case id.")
    p.add_argument("--apply", action="store_true", help="Write. Omit for a dry run.")
    p.add_argument("--limit", type=int, help="Process at most N cases")
    args = p.parse_args(argv)

    if not args.corridor and not args.case:
        raise SystemExit("Refusing to run unscoped — pass --corridor ES_IE or --case <id>.")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from backend.database import db  # noqa: E402  (import after sys.path bootstrap)

    with db.engine.connect() as conn:
        if args.case:
            rows = [dict(r) for r in conn.execute(_BY_CASE, {"id": args.case}).mappings().all()]
        else:
            origin, dest = _parse_corridor(args.corridor)
            rows = [dict(r) for r in conn.execute(
                _BY_CORRIDOR, {"origin": origin, "dest": dest}
            ).mappings().all()]

    if args.limit:
        rows = rows[: args.limit]

    log.info("scope: %s  cases=%d  mode=%s",
             args.case or args.corridor, len(rows), "APPLY" if args.apply else "DRY RUN")

    tally: Counter = Counter()
    for row in rows:
        case_id = row["case_id"]
        try:
            draft = json.loads(row.get("draft_json") or "{}")
            if not isinstance(draft, dict):
                draft = {}
        except (TypeError, json.JSONDecodeError):
            draft = {}
        try:
            plan = _regenerate_with_retry(db, case_id, draft, apply=args.apply)
        except Exception:
            tally["failed"] += 1
            log.exception("FAIL  %s", case_id)
            continue
        summary = plan.summary()
        tally["no_change" if plan.is_noop else "changed"] += 1
        for key, value in summary.items():
            tally[key] += value
        log.info(
            "%-9s %s  +%d ~%d -%d (kept %d)",
            "NO-CHANGE" if plan.is_noop else "CHANGE",
            case_id, summary["inserted"], summary["updated"], summary["deleted"],
            summary["kept_protected"],
        )

    log.info(
        "\ncases=%d  changed=%d  no_change=%d  failed=%d  inserted=%d updated=%d deleted=%d",
        len(rows), tally["changed"], tally["no_change"], tally["failed"],
        tally["inserted"], tally["updated"], tally["deleted"],
    )
    if not args.apply:
        log.info("DRY RUN — nothing written. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
