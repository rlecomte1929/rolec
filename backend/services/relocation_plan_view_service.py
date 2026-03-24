"""
Build ``RelocationPlanViewResponse`` for GET /api/relocation-plans/{case_id}/view.

Loads milestones + wizard draft + (optional) mobility documents/evaluations in a small
number of queries; runs phase engine, status derivation, and next-action selection.

# TODO (event-driven / scale — not implemented now)
# - Invalidate or patch projection on case_document / case_requirement_evaluations writes.
# - Consider materialized plan snapshots + version counter to avoid full recompute per GET.
# - Reconcile milestone PATCH events with derivation so manual + system status stay aligned.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from ..database import Database
from ..relocation_plan_next_action import (
    _deps_satisfied,
    _successor_counts,
    build_next_action_reason,
    infer_plan_task_cta_type,
    select_next_action_for_relocation_plan,
)
from ..relocation_plan_service import (
    EnrichedPlanTask,
    PhasedPlanPhaseBlock,
    _is_terminal_plan_status,
    build_phased_plan_from_milestones,
    compute_phase_completion_ratio,
    compute_phase_statuses,
    map_milestone_status_to_plan_status,
)
from ..relocation_plan_status_derivation import (
    DerivationThresholds,
    RelocationPlanDerivationContext,
    apply_derived_statuses_to_enriched_tasks,
    employment_letter_satisfied,
    is_due_soon,
    is_overdue,
    passport_copy_satisfied,
)
from ..relocation_plan_view_schemas import (
    RelocationPlanAutoCompletionSource,
    RelocationPlanCta,
    RelocationPlanCtaType,
    RelocationPlanDataFreshness,
    RelocationPlanNextAction,
    RelocationPlanPhase,
    RelocationPlanPhaseStatus,
    RelocationPlanPhaseTask,
    RelocationPlanPhaseTaskCounts,
    RelocationPlanRequiredInput,
    RelocationPlanRequiredInputType,
    RelocationPlanSummary,
    RelocationPlanTaskOwner,
    RelocationPlanTaskPriority,
    RelocationPlanTaskStatus,
    RelocationPlanViewResponse,
    RelocationPlanViewRole,
)

log = logging.getLogger(__name__)

_THRESHOLDS = DerivationThresholds()

_SHIPMENT_SERVICE_KEYS = frozenset({"movers", "shipment", "shipping"})


def _move_includes_shipment_from_selected_services(keys: Set[str]) -> Optional[bool]:
    """
    When the case has an explicit service selection set but no shipment-related key,
    treat shipment as out of scope (``False``). Empty set → unknown (``None``).
    """
    if not keys:
        return None
    lowered = {str(k).strip().lower() for k in keys}
    if lowered & _SHIPMENT_SERVICE_KEYS:
        return True
    return False


def _parse_iso_date_only(value: Optional[str]) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()[:10]
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _coerce_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if hasattr(value, "isoformat"):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _safe_task_owner(raw: str) -> RelocationPlanTaskOwner:
    try:
        return RelocationPlanTaskOwner(str(raw or "").strip().lower())
    except ValueError:
        return RelocationPlanTaskOwner.JOINT


def _safe_task_status(raw: str) -> RelocationPlanTaskStatus:
    try:
        return RelocationPlanTaskStatus(str(raw or "").strip().lower())
    except ValueError:
        return RelocationPlanTaskStatus.NOT_STARTED


def _safe_task_priority(raw: str) -> RelocationPlanTaskPriority:
    try:
        return RelocationPlanTaskPriority(str(raw or "").strip().lower())
    except ValueError:
        return RelocationPlanTaskPriority.STANDARD


def _safe_phase_status(raw: str) -> RelocationPlanPhaseStatus:
    try:
        return RelocationPlanPhaseStatus(str(raw or "").strip().lower())
    except ValueError:
        return RelocationPlanPhaseStatus.UPCOMING


def _wire_cta(internal: str) -> Tuple[RelocationPlanCtaType, str]:
    m: Dict[str, Tuple[RelocationPlanCtaType, str]] = {
        "upload_document": (RelocationPlanCtaType.UPLOAD_DOCUMENT, "Upload document"),
        "open_form": (RelocationPlanCtaType.COMPLETE_WIZARD_STEP, "Continue"),
        "review_case": (RelocationPlanCtaType.VIEW_DETAILS, "Review"),
        "view_requirements": (RelocationPlanCtaType.VIEW_DETAILS, "View requirements"),
        "contact_hr": (RelocationPlanCtaType.CONTACT_HR, "Contact HR"),
        "open_quotes": (RelocationPlanCtaType.OPEN_INTERNAL_ROUTE, "Get quotes"),
        "open_resources": (RelocationPlanCtaType.OPEN_INTERNAL_ROUTE, "Open resources"),
    }
    return m.get(internal, (RelocationPlanCtaType.VIEW_DETAILS, "Continue"))


def _required_input_present(key: str, ctx: RelocationPlanDerivationContext) -> bool:
    k = (key or "").strip().lower()
    if "passport" in k:
        return passport_copy_satisfied(ctx)
    if "employment" in k or "contract" in k or "assignment" in k:
        return employment_letter_satisfied(ctx)
    return False


def _auto_completion_source(t: EnrichedPlanTask) -> RelocationPlanAutoCompletionSource:
    baseline = map_milestone_status_to_plan_status(t.raw_milestone_status)
    if t.status == baseline:
        return RelocationPlanAutoCompletionSource.UNSPECIFIED
    if t.task_code in ("upload_passport_copy", "upload_assignment_letter"):
        return RelocationPlanAutoCompletionSource.DOCUMENT_PRESENCE
    return RelocationPlanAutoCompletionSource.SYSTEM_RULE


def _blocked_by_codes(t: EnrichedPlanTask, status_by_code: Dict[str, str]) -> List[str]:
    out: List[str] = []
    for d in t.depends_on:
        st = status_by_code.get(d)
        if st is None:
            continue
        if not _is_terminal_plan_status(st):
            out.append(d)
    return out


def _mobility_documents_and_evals(
    db: Database,
    mobility_case_id: Optional[str],
    request_id: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Optional[datetime], Optional[datetime]]:
    if not mobility_case_id:
        return [], {}, None, None
    cid = mobility_case_id.strip()
    doc_rows: List[Dict[str, Any]] = []
    eval_by_code: Dict[str, str] = {}
    doc_ts: Optional[datetime] = None
    comp_ts: Optional[datetime] = None
    try:
        with db.engine.connect() as conn:
            dr = conn.execute(
                text(
                    """
                    SELECT document_key, document_status, person_id, updated_at, created_at
                    FROM case_documents
                    WHERE case_id = :cid
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"cid": cid},
            ).mappings().all()
            for row in dr:
                doc_rows.append(dict(row))
                for col in ("updated_at", "created_at"):
                    ts = _coerce_dt(row.get(col))
                    if ts and (doc_ts is None or ts > doc_ts):
                        doc_ts = ts
            er = conn.execute(
                text(
                    """
                    SELECT e.evaluation_status, r.requirement_code, e.evaluated_at, e.updated_at
                    FROM case_requirement_evaluations AS e
                    INNER JOIN requirements_catalog AS r ON r.id = e.requirement_id
                    WHERE e.case_id = :cid
                    ORDER BY e.created_at ASC, e.id ASC
                    """
                ),
                {"cid": cid},
            ).mappings().all()
            for row in er:
                code = (row.get("requirement_code") or "").strip()
                st = (row.get("evaluation_status") or "").strip()
                if code:
                    eval_by_code[code] = st
                for col in ("evaluated_at", "updated_at"):
                    ts = _coerce_dt(row.get(col))
                    if ts and (comp_ts is None or ts > comp_ts):
                        comp_ts = ts
    except ProgrammingError as ex:
        log.debug("relocation plan view: mobility tables missing: %s", ex)
    except Exception as ex:
        log.warning("relocation plan view: mobility snapshot failed: %s", ex)
    return doc_rows, eval_by_code, doc_ts, comp_ts


def _enriched_to_schema_task(
    t: EnrichedPlanTask,
    *,
    ctx: RelocationPlanDerivationContext,
    status_by_code: Dict[str, str],
    viewer_role: str,
    today: date,
) -> RelocationPlanPhaseTask:
    due = _parse_iso_date_only(t.target_date)
    internal_cta = infer_plan_task_cta_type(t, viewer_role)
    cta_t, cta_label = _wire_cta(internal_cta)
    terminal = _is_terminal_plan_status(t.status)
    overdue = bool(not terminal and is_overdue(t.target_date, today=today))
    due_soon = bool(not terminal and is_due_soon(t.target_date, today=today, thresholds=_THRESHOLDS))
    req_in: List[RelocationPlanRequiredInput] = []
    for ri in t.required_inputs:
        if not isinstance(ri, dict):
            continue
        try:
            rit = RelocationPlanRequiredInputType(str(ri.get("type") or "other").strip().lower())
        except ValueError:
            rit = RelocationPlanRequiredInputType.OTHER
        key = str(ri.get("key") or "")
        label = str(ri.get("label") or key or "Input")
        req_in.append(
            RelocationPlanRequiredInput(
                type=rit,
                key=key,
                label=label,
                present=_required_input_present(key, ctx),
            )
        )
    return RelocationPlanPhaseTask(
        task_id=t.task_id,
        task_code=t.task_code,
        title=t.title,
        short_label=t.short_label or None,
        status=_safe_task_status(t.status),
        owner=_safe_task_owner(t.owner),
        priority=_safe_task_priority(t.priority),
        due_date=due,
        is_overdue=overdue,
        is_due_soon=due_soon,
        blocked_by=_blocked_by_codes(t, status_by_code),
        depends_on=list(t.depends_on),
        why_this_matters=t.why_this_matters or None,
        instructions=list(t.instructions),
        required_inputs=req_in,
        cta=RelocationPlanCta(type=cta_t, label=cta_label, target=None),
        auto_completion_source=_auto_completion_source(t),
        notes_enabled=True,
    )


def _build_summary(tasks: List[EnrichedPlanTask], *, today: date) -> RelocationPlanSummary:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    in_progress = sum(1 for t in tasks if t.status == "in_progress")
    blocked = sum(1 for t in tasks if t.status == "blocked")
    na = sum(1 for t in tasks if t.status == "not_applicable")
    overdue_tasks = 0
    due_soon_tasks = 0
    for t in tasks:
        if _is_terminal_plan_status(t.status):
            continue
        if is_overdue(t.target_date, today=today):
            overdue_tasks += 1
        elif is_due_soon(t.target_date, today=today, thresholds=_THRESHOLDS):
            due_soon_tasks += 1
    denom = total - na
    ratio = round(completed / denom, 4) if denom > 0 else 0.0
    return RelocationPlanSummary(
        total_tasks=total,
        completed_tasks=completed,
        in_progress_tasks=in_progress,
        blocked_tasks=blocked,
        overdue_tasks=overdue_tasks,
        due_soon_tasks=due_soon_tasks,
        completion_ratio=ratio,
    )


def _build_next_action_schema(
    winner: Optional[EnrichedPlanTask],
    *,
    viewer_role: str,
    all_tasks: Sequence[EnrichedPlanTask],
    today: date,
) -> Optional[RelocationPlanNextAction]:
    if winner is None:
        return None
    status_by_code = {t.task_code: t.status for t in all_tasks}
    succ = _successor_counts(all_tasks)
    dsat = _deps_satisfied(winner, status_by_code)
    reason = build_next_action_reason(
        winner,
        viewer_role=viewer_role,
        downstream_successor_count=succ.get(winner.task_code, 0),
        deps_satisfied=dsat,
        today=today,
        thresholds=_THRESHOLDS,
    )
    internal = infer_plan_task_cta_type(winner, viewer_role)
    cta_t, cta_label = _wire_cta(internal)
    due = _parse_iso_date_only(winner.target_date)
    return RelocationPlanNextAction(
        task_id=winner.task_id,
        title=winner.title,
        owner=_safe_task_owner(winner.owner),
        status=_safe_task_status(winner.status),
        priority=_safe_task_priority(winner.priority),
        due_date=due,
        reason=reason,
        cta=RelocationPlanCta(type=cta_t, label=cta_label, target=None),
        blocking=winner.status == "blocked",
    )


def build_relocation_plan_view_response(
    *,
    case_id: str,
    assignment_id: Optional[str],
    milestones: List[Dict[str, Any]],
    profile_draft: Dict[str, Any],
    mobility_case_id: Optional[str],
    db: Database,
    viewer_role: str,
    debug: bool = False,
    request_id: Optional[str] = None,
) -> RelocationPlanViewResponse:
    """
    Pure assembly + DB reads already performed by caller (milestones list, draft dict).
    Fetches mobility documents/evaluations when ``mobility_case_id`` is set (2 queries max).
    """
    doc_rows, eval_by_code, doc_ts, comp_ts = _mobility_documents_and_evals(db, mobility_case_id, request_id)

    selected_keys: Set[str] = set()
    if assignment_id:
        try:
            for row in db.list_case_services(assignment_id, request_id=request_id):
                if row.get("selected") in (True, 1):
                    sk = row.get("service_key")
                    if sk:
                        selected_keys.add(str(sk).strip().lower())
        except Exception as ex:
            log.debug("list_case_services skipped: %s", ex)

    ctx = RelocationPlanDerivationContext(
        profile=profile_draft if profile_draft else None,
        case_documents=doc_rows or None,
        requirement_eval_by_code=eval_by_code or None,
        selected_service_keys=selected_keys or None,
        move_includes_shipment=_move_includes_shipment_from_selected_services(selected_keys),
        destination_requires_biometrics=None,
    )

    blocks = build_phased_plan_from_milestones(milestones)
    flat: List[EnrichedPlanTask] = [t for b in blocks for t in b.tasks]
    apply_derived_statuses_to_enriched_tasks(flat, ctx, include_debug=debug)
    compute_phase_statuses(blocks)

    today = date.today()
    vr = _norm_viewer_role(viewer_role)
    role_wire = vr.value
    status_by_code = {t.task_code: t.status for t in flat}
    phases_out: List[RelocationPlanPhase] = []
    for b in blocks:
        counts = b.task_counts
        phases_out.append(
            RelocationPlanPhase(
                phase_key=b.phase_key,
                title=b.phase_title,
                status=_safe_phase_status(b.status),
                completion_ratio=compute_phase_completion_ratio(b.tasks),
                task_counts=RelocationPlanPhaseTaskCounts(
                    total=counts["total"],
                    completed=counts["completed"],
                    in_progress=counts["in_progress"],
                    blocked=counts["blocked"],
                ),
                tasks=[
                    _enriched_to_schema_task(
                        t,
                        ctx=ctx,
                        status_by_code=status_by_code,
                        viewer_role=role_wire,
                        today=today,
                    )
                    for t in b.tasks
                ],
            )
        )

    summary = _build_summary(flat, today=today)
    allow_cross = vr == RelocationPlanViewRole.HR
    na_pick = select_next_action_for_relocation_plan(
        blocks,
        role_wire,
        today=today,
        thresholds=_THRESHOLDS,
        allow_cross_role_next_action=allow_cross,
    )
    winner_task: Optional[EnrichedPlanTask] = None
    if na_pick.next_action:
        tid = str(na_pick.next_action.get("task_id") or "").strip()
        code = str(na_pick.next_action.get("task_code") or "").strip()

        def _match_winner(t: EnrichedPlanTask) -> bool:
            if tid and t.task_id == tid:
                return True
            if code and t.task_code == code:
                return True
            return False

        winner_task = next((t for t in flat if _match_winner(t)), None)
    next_schema = _build_next_action_schema(winner_task, viewer_role=role_wire, all_tasks=flat, today=today)

    empty_reason_out: Optional[str] = None
    if next_schema is None:
        empty_reason_out = na_pick.empty_state_reason
        if not empty_reason_out and na_pick.next_action:
            empty_reason_out = "Plan is updating—refresh if this message stays."

    freshness: Optional[RelocationPlanDataFreshness] = None
    if doc_ts or comp_ts:
        freshness = RelocationPlanDataFreshness(
            documents_checked_at=doc_ts,
            compliance_checked_at=comp_ts,
        )

    debug_payload: Optional[Dict[str, Any]] = None
    if debug:
        debug_payload = {
            "mobility_case_id": mobility_case_id,
            "document_row_count": len(doc_rows),
            "evaluation_codes": sorted(eval_by_code.keys()),
        }
        for t in flat:
            dbg = getattr(t, "_derivation_debug", None)
            if dbg:
                debug_payload.setdefault("derivation_traces", {})[t.task_code] = dbg

    return RelocationPlanViewResponse(
        case_id=case_id,
        assignment_id=assignment_id,
        role=vr,
        summary=summary,
        next_action=next_schema,
        phases=phases_out,
        last_evaluated_at=datetime.now(timezone.utc),
        data_freshness=freshness,
        empty_state_reason=empty_reason_out,
        debug=debug_payload,
    )


def _norm_viewer_role(viewer_role: str) -> RelocationPlanViewRole:
    r = (viewer_role or "").strip().lower()
    if r == "hr":
        return RelocationPlanViewRole.HR
    return RelocationPlanViewRole.EMPLOYEE


def load_profile_draft_for_case(session, case_id: str) -> Dict[str, Any]:
    """SQLAlchemy session: load ``Case`` and parse ``draft_json``."""
    from ..app import crud as app_crud

    case = app_crud.get_case(session, case_id)
    if not case:
        return {}
    try:
        import json

        raw = json.loads(getattr(case, "draft_json", None) or "{}")
        return raw if isinstance(raw, dict) else {}
    except (TypeError, ValueError):
        return {}


def get_relocation_plan_view_for_case_assignment(
    *,
    db: Database,
    session_factory: Any,
    case_id_effective: str,
    assignment: Dict[str, Any],
    viewer_role: str,
    debug: bool = False,
    request_id: Optional[str] = None,
) -> RelocationPlanViewResponse:
    """
    End-to-end loader for the HTTP handler: milestones, draft, mobility bridge, then assembly.
    """
    assignment_id = str(assignment.get("id") or "").strip() or None
    milestones = db.list_case_milestones(case_id_effective, request_id=request_id)
    mobility_case_id = db.get_mobility_case_id_for_assignment(assignment_id or "", request_id=request_id) if assignment_id else None
    with session_factory() as session:
        profile = load_profile_draft_for_case(session, case_id_effective)
    return build_relocation_plan_view_response(
        case_id=case_id_effective,
        assignment_id=assignment_id,
        milestones=milestones,
        profile_draft=profile,
        mobility_case_id=mobility_case_id,
        db=db,
        viewer_role=viewer_role,
        debug=debug,
        request_id=request_id,
    )
