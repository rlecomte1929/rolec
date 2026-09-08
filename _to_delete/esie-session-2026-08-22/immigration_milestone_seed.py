"""Immigration-milestone templates + idempotent seeder, per corridor (DOC-4).

Gap (2026-08-22): a case's ``immigration_milestones`` stays empty until something creates
rows, and nothing seeds them from the corridor — so the HR immigration timeline reads empty
for corridors that ARE otherwise covered. This module holds the ES->IE (Critical Skills
Employment Permit) milestone timeline and an idempotent seeder.

PROVENANCE. No content is invented. Every milestone and its planning anchor is derived from
an authored, cited ``requirement_items`` row and the CSEP_2026 pathway sequence
(``corridors/ES_IE/pathways/CSEP_2026/v1.yaml``). The ``lead_time_days`` are INDICATIVE
planning offsets (relative to the move date; negative = before) to be confirmed with counsel;
the SEQUENCE and the statutory anchors (IRP/Stamp 1 registration within 90 days of arrival,
Immigration Act 2004 s.9) are the load-bearing part.

NOT wired into the case lifecycle here. Call ``seed_case_milestones()`` from the
immigration-file-open flow, or run ``backend/scripts/seed_case_milestones.py`` to backfill an
existing case — after the underlying rows are counsel-attested.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Ordered milestone template. lead_time_days is relative to the move date (day 0);
# negative = before the move. book_early_alert flags the traps the pathway calls out.
_ES_IE_CSEP: List[Dict[str, Any]] = [
    {"milestone_type": "csep_eligibility_confirmed", "book_early_alert": True, "lead_time_days": -112,
     "basis": "CSEP occupation list + salary threshold (requirement_items)"},
    {"milestone_type": "employment_permit_granted", "book_early_alert": True, "lead_time_days": -84,
     "basis": "CSEP eligibility; Employment Permits Act 2024 (indicative ~12wk processing)"},
    {"milestone_type": "d_visa_lodged", "book_early_alert": True, "lead_time_days": -70,
     "basis": "Entry visa after permit; up to 3 months before travel (requirement_items)"},
    {"milestone_type": "dependant_join_family_visas_lodged", "book_early_alert": True, "lead_time_days": -70,
     "basis": "Dependant Join Family 'D' visa required (flagged for counsel)"},
    {"milestone_type": "d_visa_granted", "book_early_alert": True, "lead_time_days": -14,
     "basis": "~8-week visa decision (requirement_items)"},
    {"milestone_type": "travel_to_ireland", "book_early_alert": False, "lead_time_days": 0,
     "basis": "CSEP_2026 pathway sequence"},
    {"milestone_type": "revenue_job_registration_rpn", "book_early_alert": True, "lead_time_days": 1,
     "basis": "Register job with Revenue immediately to avoid emergency tax (requirement_items)"},
    {"milestone_type": "ppsn_application", "book_early_alert": False, "lead_time_days": 7,
     "basis": "PPSN application on/after arrival (requirement_items)"},
    {"milestone_type": "irp_stamp1_registration", "book_early_alert": True, "lead_time_days": 21,
     "basis": "IRP/Stamp 1 registration; statutory limit 90 days of arrival (Immigration Act 2004 s.9)"},
    {"milestone_type": "spouse_stamp1g_registration", "book_early_alert": False, "lead_time_days": 21,
     "basis": "Spouse Stamp 1G right to work (flagged for counsel)"},
    {"milestone_type": "irp_card_received", "book_early_alert": False, "lead_time_days": 35,
     "basis": "IRP card ~10 working days after registration (requirement_items)"},
]

MILESTONE_TEMPLATES: Dict[Tuple[str, str], List[Dict[str, Any]]] = {
    ("ES", "IE"): _ES_IE_CSEP,
}


def _norm(cc: Optional[str]) -> str:
    return (cc or "").strip().upper()


def get_template(corridor_from: str, corridor_to: str) -> List[Dict[str, Any]]:
    """Milestone template for a corridor, or [] when none is defined (fail-closed: an
    unknown corridor seeds nothing rather than a default set)."""
    return MILESTONE_TEMPLATES.get((_norm(corridor_from), _norm(corridor_to)), [])


def build_milestone_rows(
    case_id: str,
    org_id: Optional[str],
    corridor_from: str,
    corridor_to: str,
    move_date: Optional[date] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Pure: expand the corridor template into insert-ready row dicts. ``target_date`` is
    ``move_date + lead_time_days`` or None when no move date is known (never fabricate a
    date). Deterministic given its inputs — the id is derived from the natural key, not
    random — so a re-run is stable and diffable."""
    tmpl = get_template(corridor_from, corridor_to)
    ts = (now or datetime(1970, 1, 1)).isoformat()
    rows: List[Dict[str, Any]] = []
    for i, m in enumerate(tmpl):
        target = (move_date + timedelta(days=m["lead_time_days"])).isoformat() if move_date else None
        mid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{case_id}:{m['milestone_type']}"))
        rows.append({
            "id": mid,
            "case_id": case_id,
            "org_id": org_id,
            "milestone_type": m["milestone_type"],
            "status": "pending",
            "sort_order": i + 1,
            "target_date": target,
            "book_early_alert": bool(m["book_early_alert"]),
            "created_at": ts,
            "updated_at": ts,
        })
    return rows


def case_has_milestones(conn: Any, case_id: str) -> bool:
    from sqlalchemy import text
    n = conn.execute(
        text("SELECT COUNT(*) FROM public.immigration_milestones WHERE case_id = :c"),
        {"c": case_id},
    ).scalar()
    return bool(n)


def seed_case_milestones(
    conn: Any,
    case_id: str,
    org_id: Optional[str],
    corridor_from: str,
    corridor_to: str,
    move_date: Optional[date] = None,
    now: Optional[datetime] = None,
    force: bool = False,
) -> int:
    """Insert the corridor milestone set for a case. Idempotent: skips when the case already
    has milestones (the table has no unique constraint) unless ``force=True``. Never deletes
    existing rows unless force. Returns the number of rows inserted."""
    from sqlalchemy import text
    now = now or datetime.utcnow()
    rows = build_milestone_rows(case_id, org_id, corridor_from, corridor_to, move_date, now)
    if not rows:
        return 0
    if case_has_milestones(conn, case_id):
        if not force:
            return 0
        conn.execute(text("DELETE FROM public.immigration_milestones WHERE case_id = :c"), {"c": case_id})
    conn.execute(
        text("""
            INSERT INTO public.immigration_milestones
                (id, case_id, org_id, milestone_type, status, sort_order,
                 target_date, book_early_alert, created_at, updated_at)
            VALUES
                (:id, :case_id, :org_id, :milestone_type, :status, :sort_order,
                 :target_date, :book_early_alert, :created_at, :updated_at)
        """),
        rows,
    )
    return len(rows)
