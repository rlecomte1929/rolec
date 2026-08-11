"""[AIQ-1788] Write planned candidate rows into vendor_curation_runs + vendor_candidates.

`plan_pair()` is pure: it decides which rows stage, which are duplicates and which are
rejected, and returns them with `run_id=""`. This is the half that opens the run and fills
that id in. Keeping them apart is why the entire decision surface is testable with no database.

SAFETY — the same one-line model the harvester declares:

    vendor_curation_runs -> vendor_candidates    (written here, and nowhere else)
    suppliers, supplier_service_capabilities     (never touched)

Everything lands `status='pending'`. Nothing here promotes a candidate into the live
directory; that is a human decision and lives behind the admin review surface.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text

from backend.app.services.vendor_harvester import (
    RUN_FAILED,
    RUN_STAGED,
    Candidate,
    PairResult,
    existing_dedupe_keys,
    plan_pair,
)

log = logging.getLogger(__name__)

_INSERT_RUN = text(
    """
    INSERT INTO public.vendor_curation_runs
        (corridor, service_category, sources_searched, candidates_found, status)
    VALUES (:corridor, :service_category, CAST(:sources_searched AS jsonb), :candidates_found, :status)
    RETURNING id
    """
)

_INSERT_CANDIDATE = text(
    """
    INSERT INTO public.vendor_candidates
        (run_id, name, legal_name, website_url, email, phone, city, country_code,
         vat_number, corridor, service_category, source_url, source_name, source_tier,
         confidence_score, accreditation_body, accreditation_number, accreditation_expiry,
         bar_registered, dedupe_key, status, notes)
    VALUES
        (:run_id, :name, :legal_name, :website_url, :email, :phone, :city, :country_code,
         :vat_number, :corridor, :service_category, :source_url, :source_name, :source_tier,
         :confidence_score, :accreditation_body, :accreditation_number,
         CAST(:accreditation_expiry AS date),
         :bar_registered, :dedupe_key, :status, :notes)
    """
)


def group_by_pair(
    candidates: Sequence[Candidate],
) -> Dict[Tuple[str, str], List[Candidate]]:
    """(corridor, service_category) -> its candidates, in file order."""
    grouped: Dict[Tuple[str, str], List[Candidate]] = {}
    for cand in candidates:
        grouped.setdefault((cand.corridor, cand.service_category), []).append(cand)
    return grouped


def stage(
    conn: Any,
    candidates: Sequence[Candidate],
    *,
    dry_run: bool = True,
) -> Tuple[List[PairResult], List[str]]:
    """Plan every pair, and (unless dry_run) write the runs and rows.

    Returns (results, rejections). A dry run performs every read and every decision and
    writes nothing, so the numbers it prints are the numbers a real run will produce — the
    point of a preview is defeated if it takes a different code path.

    Takes a SQLAlchemy Connection inside a transaction the CALLER owns, so a partial failure
    rolls the whole import back rather than leaving half a corridor staged.
    """
    results: List[PairResult] = []
    rejections: List[str] = []

    for (corridor, category), pair_candidates in group_by_pair(candidates).items():
        # Re-read per corridor: the name-fallback key is corridor-scoped, and rows staged
        # earlier in THIS run must be visible to the next pair or a supplier appearing in two
        # categories would stage twice as 'pending'.
        known = existing_dedupe_keys(conn, corridor=corridor)
        rows, result, pair_rejections = plan_pair(corridor, category, pair_candidates, known)
        rejections.extend(pair_rejections)

        if not dry_run and rows:
            try:
                run_id = conn.execute(
                    _INSERT_RUN,
                    {
                        "corridor": corridor,
                        "service_category": category,
                        "sources_searched": json.dumps(result.sources_searched),
                        "candidates_found": len(rows),
                        "status": RUN_STAGED,
                    },
                ).scalar_one()
                for row in rows:
                    conn.execute(_INSERT_CANDIDATE, {**row, "run_id": str(run_id)})
                result.run_id = str(run_id)
            except Exception as exc:                       # noqa: BLE001 — recorded, re-raised
                result.error = f"{type(exc).__name__}: {exc}"
                log.exception("staging %s/%s failed", corridor, category)
                raise

        results.append(result)

    return results, rejections


def summarise(results: Sequence[PairResult], rejections: Sequence[str]) -> str:
    """A short console summary. `render_report` in the harvester is the full markdown one."""
    staged = sum(r.staged for r in results)
    dupes = sum(r.suppressed_duplicates for r in results)
    lines = [
        f"pairs:      {len(results)}",
        f"staged:     {staged}   (status='pending')",
        f"duplicates: {dupes}   (status='duplicate', kept as history)",
        f"rejected:   {len(rejections)}",
    ]
    if rejections:
        lines.append("")
        lines.append("Rejected — this list is the re-sourcing worklist, not noise:")
        lines.extend(f"  - {r}" for r in rejections)
    return "\n".join(lines)
