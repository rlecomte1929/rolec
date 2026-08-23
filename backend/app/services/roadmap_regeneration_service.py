"""Recompute a case's `case_milestones` from the CURRENT generator, idempotently.

WHY THIS EXISTS. #1938 wired the corridor overlay (`roadmap_corridor_overlay` →
`timeline_service.compute_default_milestones`) into milestone generation, so an ES→IE
third-country national now gets the real CSEP journey. Milestones are only ever written at
case *creation*/submit, so every case created before that keeps the generic pack forever.
Andrea's case 6ecadafe is the live example: 16 `task_*` rows, 0 corridor steps, including
`task_visa_docs_prep` / `task_visa_submit` / `task_biometrics` — generic copy the corridor
overlay exists to supersede.

THE IDEMPOTENCY HAZARD, WHICH IS NOT OBVIOUS. `db.upsert_case_milestone` is an upsert only
when handed a `milestone_id`; without one it unconditionally INSERTs. The three existing
seeding sites in backend/main.py call it without an id, which is safe exactly once. Running
that loop again against a seeded case duplicates every row. So reconciliation here matches
existing rows by `milestone_type` FIRST and passes the id back, which is what makes a second
run a no-op rather than a doubling.

WHAT IS PROTECTED, AND WHY

  source='service'   Externally managed (a selected service owns them). `delete_case_
                     milestones(exclude_source='service')` already draws this line; this
                     module draws the same one rather than inventing a second policy.

  status in PROTECTED_STATUSES   A row someone has completed or started is EVIDENCE, not a
                     projection. A stale generic step that the employee already ticked off
                     is kept even when the generator no longer emits it — deleting it would
                     silently erase work, and "the roadmap changed" is never a reason to
                     unremember that somebody did something.

  roadmap_review_status   NEVER touched. Absent row means RELEASED, so writing anything here
                     could publish an unreviewed roadmap or retract a released one. The HR
                     gate is a separate decision from what the steps are.

Everything else the generator no longer emits is deleted, because leaving it produces the
one outcome worse than either list alone: the generic visa pack shown *beside* the CSEP
pack, with nothing telling the employee which is real.

Pure where it can be: `milestone_inputs_from_draft` and `plan_regeneration` take data and
return data, so the reconciliation logic is testable without a database.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .timeline_service import compute_default_milestones

log = logging.getLogger(__name__)

# A milestone owned by a selected service, not by the roadmap generator.
PROTECTED_SOURCES = frozenset({"service"})

# Progress is evidence. Never delete a row carrying it, even if the generator moved on.
PROTECTED_STATUSES = frozenset({"completed", "done", "complete", "in_progress", "blocked"})


@dataclass
class RegenerationPlan:
    """What a regeneration WOULD do. Returned by the dry run and executed by the wet one."""

    inserts: List[Dict[str, Any]] = field(default_factory=list)
    # (milestone_id, payload) — payload already carries any preserved status/actual_date.
    updates: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    delete_ids: List[str] = field(default_factory=list)
    kept_protected: List[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        """True when nothing would change. An update that rewrites identical values is not
        a change — otherwise 'idempotent' would only ever mean 'does not duplicate'."""
        return not self.inserts and not self.updates and not self.delete_ids

    def summary(self) -> Dict[str, int]:
        return {
            "inserted": len(self.inserts),
            "updated": len(self.updates),
            "deleted": len(self.delete_ids),
            "kept_protected": len(self.kept_protected),
        }


def milestone_inputs_from_draft(draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The generator's kwargs, read out of a wizard draft.

    Lifted verbatim from the three identical blocks in backend/main.py (~6100, ~8100,
    ~11295) so regeneration cannot drift from creation. Those three sites are deliberately
    NOT refactored to call this — that is a wider change than a roadmap fix should carry —
    but any correction belongs here and there together.
    """
    draft = draft if isinstance(draft, dict) else {}
    assignment_context = draft.get("assignmentContext") or {}
    assignment = draft.get("assignment") or {}
    basics = draft.get("relocationBasics") or {}
    employee_profile = draft.get("employeeProfile") or {}
    primary_applicant = draft.get("primaryApplicant") or {}

    return {
        "case_draft": draft,
        "contract_type": (
            assignment.get("contractType")
            or assignment_context.get("contractType")
            or basics.get("contractType")
            or None
        ),
        "family_profile": draft.get("family") or None,
        "destination_country": basics.get("destCountry") or basics.get("destination_country") or None,
        "origin_country": basics.get("originCountry") or basics.get("origin_country") or None,
        "nationality": (
            primary_applicant.get("nationality")
            or employee_profile.get("nationality")
            or employee_profile.get("nationalityCountry")
            or basics.get("nationality")
            or None
        ),
    }


def _is_protected(row: Dict[str, Any]) -> bool:
    if (row.get("source") or "") in PROTECTED_SOURCES:
        return True
    return str(row.get("status") or "").strip().lower() in PROTECTED_STATUSES


def _has_progress(row: Dict[str, Any]) -> bool:
    return str(row.get("status") or "").strip().lower() in PROTECTED_STATUSES


def _payload(milestone: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "milestone_type": milestone["milestone_type"],
        "title": milestone["title"],
        "description": milestone.get("description"),
        "target_date": milestone.get("target_date"),
        "status": milestone.get("status", "pending"),
        "sort_order": milestone.get("sort_order", 0),
        "owner": milestone.get("owner", "joint"),
        "criticality": milestone.get("criticality", "normal"),
        "notes": milestone.get("notes"),
    }


def _differs(existing: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Only the fields regeneration owns. `status`/`actual_date` are excluded on purpose —
    they are the employee's, and comparing them would make every run look like a change."""
    for key in ("title", "description", "target_date", "sort_order", "owner", "criticality"):
        if (existing.get(key) or None) != (payload.get(key) or None):
            return True
    return False


def plan_regeneration(
    existing: Sequence[Dict[str, Any]],
    generated: Sequence[Dict[str, Any]],
) -> RegenerationPlan:
    """Reconcile existing rows against a freshly generated set. Pure — no database."""
    plan = RegenerationPlan()
    by_type: Dict[str, Dict[str, Any]] = {}
    for row in existing:
        mtype = str(row.get("milestone_type"))
        if mtype not in by_type:
            by_type[mtype] = row
            continue
        # A SECOND row for the same milestone_type. Keeping only the first — the obvious
        # `setdefault` — drops the duplicate out of the reconciliation entirely, so it is
        # never a delete candidate and survives every future run, invisible. Since
        # `upsert_case_milestone` inserts unconditionally without an id, duplicates are the
        # exact damage a naive regeneration causes, so this cleans them up instead.
        # Protection still wins: a duplicate carrying progress or owned by a service stays.
        if _is_protected(row):
            plan.kept_protected.append(mtype)
        else:
            plan.delete_ids.append(str(row.get("id")))

    generated_types = set()
    for milestone in generated:
        mtype = str(milestone["milestone_type"])
        generated_types.add(mtype)
        payload = _payload(milestone)
        current = by_type.get(mtype)
        if current is None:
            plan.inserts.append(payload)
            continue
        if _has_progress(current):
            # Keep what the employee did; refresh only the wording/timing around it.
            payload["status"] = current.get("status")
        if _differs(current, payload):
            plan.updates.append((str(current.get("id")), payload))

    for mtype, row in by_type.items():
        if mtype in generated_types:
            continue
        if _is_protected(row):
            plan.kept_protected.append(mtype)
            continue
        plan.delete_ids.append(str(row.get("id")))

    return plan


def regenerate_case_milestones(
    db: Any,
    case_id: str,
    *,
    draft: Optional[Dict[str, Any]] = None,
    selected_services: Optional[Sequence[str]] = None,
    target_move_date: Optional[str] = None,
    apply: bool = True,
    request_id: Optional[str] = None,
) -> RegenerationPlan:
    """Recompute and (optionally) persist a case's milestones.

    `apply=False` returns the plan without writing — the backfill's dry run, and what the
    endpoint returns when asked to preview.
    """
    if draft is None:
        draft = _load_draft(db, case_id)

    kwargs = milestone_inputs_from_draft(draft)
    generated = compute_default_milestones(
        case_id=case_id,
        selected_services=list(selected_services) if selected_services else None,
        target_move_date=str(target_move_date) if target_move_date else None,
        **kwargs,
    )
    existing = db.list_case_milestones(case_id, request_id=request_id)
    plan = plan_regeneration(existing, generated)

    if not apply:
        return plan

    for payload in plan.inserts:
        db.upsert_case_milestone(case_id=case_id, request_id=request_id, **payload)
    for milestone_id, payload in plan.updates:
        db.upsert_case_milestone(
            case_id=case_id, milestone_id=milestone_id, request_id=request_id, **payload
        )
    for milestone_id in plan.delete_ids:
        db.delete_case_milestone(milestone_id, case_id=case_id, request_id=request_id)

    log.info(
        "roadmap regenerate case_id=%s %s", case_id, json.dumps(plan.summary(), sort_keys=True)
    )
    return plan


def _wizard_draft(case_id: str) -> Dict[str, Any]:
    """The nested CaseDraftDTO from `wizard_cases`, or {} when there is no row."""
    try:
        from ..db import SessionLocal
        from .. import crud as app_crud

        with SessionLocal() as session:
            case = app_crud.get_case(session, case_id)
            if not case:
                return {}
            raw = json.loads(getattr(case, "draft_json", None) or "{}")
            return raw if isinstance(raw, dict) else {}
    except Exception:  # pragma: no cover - defensive, mirrors the seeding sites
        log.warning("roadmap regenerate: could not load wizard draft case_id=%s", case_id, exc_info=True)
        return {}


def _assignment_intake_draft(db: Any, case_id: str) -> Dict[str, Any]:
    """The assignment's FLAT snake_case intake draft, converted to the nested shape.

    Two stores hold a case's intake and they are not the same table:

        wizard_cases.draft_json          nested camelCase  (the v1 wizard)
        case_assignments.intake_draft    flat snake_case   (the v2 Pathway wizard,
                                                            and the HR contract prefill)

    `intake_draft_to_case_draft` is the server-authoritative bridge between them (AIQ-1311),
    written so the backend can work "straight from the reliable assignment autosave instead
    of depending on the frontend having patched the right wizard_cases row".
    """
    try:
        assignment = db.get_assignment_by_case_id(case_id)
        if not assignment:
            return {}
        raw = assignment.get("intake_draft")
        if isinstance(raw, str):
            raw = json.loads(raw or "{}")
        if not isinstance(raw, dict) or not raw:
            return {}
        from backend.intake_draft_to_case_draft import intake_draft_to_case_draft

        converted = intake_draft_to_case_draft(raw)
        return converted if isinstance(converted, dict) else {}
    except Exception:  # pragma: no cover - defensive; a bad draft must not stop regeneration
        log.warning(
            "roadmap regenerate: could not load intake draft case_id=%s", case_id, exc_info=True
        )
        return {}


def _load_draft(db: Any, case_id: str) -> Dict[str, Any]:
    """The best available intake for a case, across BOTH stores.

    WHY THIS READS TWO PLACES. Regeneration used to read `wizard_cases` alone. The HR
    contract prefill writes `case_assignments.intake_draft`. Different tables, so they never
    met: an end-to-end run on 2026-08-23 prefilled a fresh ES→IE case with
    origin_country=ES / dest_country=IE / nationality=VE, regeneration then read an ABSENT
    wizard row, saw no corridor, and produced the generic 16-step pack — while everything it
    needed sat one table over. Both features' unit tests passed, because each was tested
    against its own store.

    The wizard draft WINS where it has a value: it is the employee's own answer, and an HR
    extraction is a proposal about them. The intake draft only fills what is missing — which
    today is usually everything, because most cases have no wizard row at all.
    """
    wizard = _wizard_draft(case_id)
    intake = _assignment_intake_draft(db, case_id)
    if not intake:
        return wizard
    if not wizard:
        return intake

    # Section-wise merge: keep every wizard value, add only keys it does not have. A whole
    # section present but EMPTY in the wizard draft (the `_default_wizard_draft` skeleton
    # writes `{}` x4) must not shadow a populated one.
    merged: Dict[str, Any] = dict(intake)
    for section, value in wizard.items():
        if isinstance(value, dict) and isinstance(merged.get(section), dict):
            combined = dict(merged[section])
            combined.update({k: v for k, v in value.items() if v not in (None, "", [], {})})
            merged[section] = combined
        elif value not in (None, "", [], {}):
            merged[section] = value
    return merged
