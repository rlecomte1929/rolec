"""
Primary next-action selection for the phased relocation plan (employee + HR + provider views).

Pure logic over ``PhasedPlanPhaseBlock`` / ``EnrichedPlanTask`` from ``relocation_plan_service``.
No FastAPI or database.

Business rules (sort key — lower tuple wins; see ``_sort_key``):
1. Tasks in an *active* phase beat *blocked* phases, which beat *upcoming* phases.
2. ``blocked`` tasks are excluded unless every *eligible* task (non-terminal) is ``blocked``,
   then the same ordering applies within the blocked-only pool.
3. ``critical`` priority before ``standard``.
4. ``overdue`` (by ``target_date``) before *due soon* before neither.
5. Owner affinity: current viewer role, then ``joint``, then other roles.
6. Dependencies satisfied (all present ``depends_on`` are terminal) before unsatisfied.
7. Tie-breaks: more downstream dependents in the visible plan first, then ``task_code``.

``in_progress`` is ranked slightly ahead of ``not_started`` (active work first).

Reason strings are human-readable; ``cta_type`` is a stable UI hint
(``upload_document``, ``open_form``, ``review_case``, ``view_requirements``,
``contact_hr``, ``open_quotes``, ``open_resources``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .relocation_plan_service import EnrichedPlanTask, PhasedPlanPhaseBlock, _is_terminal_plan_status
from .relocation_plan_status_derivation import DerivationThresholds, is_due_soon, is_overdue

# Normalized viewer roles for plan views.
_KNOWN_VIEWER_ROLES: Set[str] = {"employee", "hr", "provider"}

_PHASE_STATUS_RANK = {"active": 0, "blocked": 1, "upcoming": 2, "completed": 3}

_PRIORITY_RANK = {"critical": 0, "standard": 1}

# CTA hints by canonical task_code (MVP library).
_TASK_CODE_TO_CTA: Dict[str, str] = {
    "confirm_employee_core_profile": "open_form",
    "confirm_family_details": "open_form",
    "upload_passport_copy": "upload_document",
    "upload_assignment_letter": "upload_document",
    "verify_destination_route": "review_case",
    "hr_review_case_data": "review_case",
    "schedule_immigration_review": "review_case",
    "prepare_visa_pack": "view_requirements",
    "submit_visa_application": "view_requirements",
    "book_biometrics": "open_form",
    "arrange_temporary_housing": "open_quotes",
    "arrange_movers": "open_quotes",
    "coordinate_relocation_providers": "open_resources",
    "plan_travel": "open_form",
    "complete_arrival_registration": "open_form",
    "tax_local_registration": "open_form",
    "settle_in": "open_resources",
}


def _norm_role(role: str) -> str:
    r = (role or "").strip().lower()
    return r if r in _KNOWN_VIEWER_ROLES else "employee"


def _phase_status_for_task(blocks: Sequence[PhasedPlanPhaseBlock], phase_key: str) -> str:
    for b in blocks:
        if b.phase_key == phase_key:
            return (b.status or "upcoming").strip().lower()
    return "upcoming"


def _owner_affinity_rank(owner: str, viewer_role: str) -> int:
    """
    Lower = better fit for the viewer.
    Order: viewer role → joint → everyone else.
    """
    o = (owner or "").strip().lower()
    v = _norm_role(viewer_role)
    if o == v:
        return 0
    if o == "joint":
        return 1
    return 2


def _actionable_for_viewer(task: EnrichedPlanTask, viewer_role: str) -> bool:
    """True if the viewer can meaningfully act (own role or joint)."""
    return _owner_affinity_rank(task.owner, viewer_role) <= 1


def _due_rank(target_date: Optional[str], *, today: date, thresholds: DerivationThresholds) -> int:
    if is_overdue(target_date, today=today):
        return 0
    if is_due_soon(target_date, today=today, thresholds=thresholds):
        return 1
    return 2


def _status_work_rank(status: str) -> int:
    s = (status or "").strip().lower()
    if s == "in_progress":
        return 0
    return 1


def _collect_tasks(blocks: Sequence[PhasedPlanPhaseBlock]) -> List[EnrichedPlanTask]:
    out: List[EnrichedPlanTask] = []
    for b in blocks:
        out.extend(b.tasks)
    return out


def _successor_counts(tasks: Sequence[EnrichedPlanTask]) -> Dict[str, int]:
    """How many *present* tasks depend on this task_code (downstream pressure)."""
    present: Set[str] = {t.task_code for t in tasks}
    counts: Dict[str, int] = {t.task_code: 0 for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            if d in present:
                counts[d] = counts.get(d, 0) + 1
    return counts


def _status_by_code(tasks: Sequence[EnrichedPlanTask]) -> Dict[str, str]:
    return {t.task_code: t.status for t in tasks}


def _deps_satisfied(task: EnrichedPlanTask, status_by_code: Mapping[str, str]) -> bool:
    for d in task.depends_on:
        if d not in status_by_code:
            continue
        if not _is_terminal_plan_status(status_by_code[d]):
            return False
    return True


def _eligible_tasks(tasks: Sequence[EnrichedPlanTask]) -> List[EnrichedPlanTask]:
    return [t for t in tasks if not _is_terminal_plan_status(t.status)]


def _selection_pool(eligible: Sequence[EnrichedPlanTask]) -> List[EnrichedPlanTask]:
    non_blocked = [t for t in eligible if t.status != "blocked"]
    return list(non_blocked if non_blocked else eligible)


def infer_plan_task_cta_type(task: EnrichedPlanTask, viewer_role: str) -> str:
    base = _TASK_CODE_TO_CTA.get(task.task_code, "view_requirements")
    o = (task.owner or "").strip().lower()
    v = _norm_role(viewer_role)
    # Cross-role nudges: if this task is not for the viewer, surface escalation CTAs.
    if v == "employee" and o == "hr" and base == "review_case":
        return "contact_hr"
    if v == "employee" and o == "provider" and base == "open_resources":
        return "contact_hr"
    if v == "hr" and o == "employee" and task.task_code in (
        "upload_passport_copy",
        "upload_assignment_letter",
    ):
        return "view_requirements"
    return base


# Backwards-compatible alias
_infer_cta_type = infer_plan_task_cta_type


def _blocking_immigration_downstream(task: EnrichedPlanTask, successor_count: int) -> bool:
    if task.phase_key != "immigration":
        return False
    return successor_count >= 2


def build_next_action_reason(
    task: EnrichedPlanTask,
    *,
    viewer_role: str,
    downstream_successor_count: int,
    deps_satisfied: bool,
    today: date,
    thresholds: DerivationThresholds,
) -> str:
    """Single structured sentence for UI; deterministic from task + flags."""
    v = _norm_role(viewer_role)
    o = (task.owner or "").strip().lower()

    if task.status == "blocked":
        if task.task_code == "prepare_visa_pack":
            return "Required before visa/work permit pack can start"
        if task.task_code == "submit_visa_application":
            return "Visa pack must be ready before submission"
        if _blocking_immigration_downstream(task, downstream_successor_count):
            return "Blocking downstream immigration steps"
        return "Waiting on prerequisites before this step can advance"

    if is_overdue(task.target_date, today=today):
        if o == v or o == "joint":
            return "Overdue and owned by you"
        return "Overdue — follow up with the assigned owner"

    if is_due_soon(task.target_date, today=today, thresholds=thresholds):
        if o == v or o == "joint":
            return "Due soon and owned by you"
        return "Due soon — coordinate with the assigned owner"

    if not deps_satisfied:
        return "Upstream steps still open for this task"

    if _blocking_immigration_downstream(task, downstream_successor_count):
        return "Blocking downstream immigration steps"

    if task.status == "in_progress":
        if o == v or o == "joint":
            return "In progress — finish remaining items"
        return "In progress — monitor with the assigned owner"

    if o != v and o != "joint":
        if o == "hr":
            return "Waiting for HR review"
        if o == "provider":
            return "Waiting for provider update"
        return "Owned by another party on this case"

    return "Next recommended step in your relocation plan"


def _sort_key(
    task: EnrichedPlanTask,
    *,
    blocks: Sequence[PhasedPlanPhaseBlock],
    viewer_role: str,
    today: date,
    thresholds: DerivationThresholds,
    status_by_code: Mapping[str, str],
    successor_count: int,
) -> Tuple[int, int, int, int, int, int, int, str]:
    phase_st = _phase_status_for_task(blocks, task.phase_key)
    phase_rank = _PHASE_STATUS_RANK.get(phase_st, 2)
    pri = _PRIORITY_RANK.get((task.priority or "standard").strip().lower(), 1)
    due = _due_rank(task.target_date, today=today, thresholds=thresholds)
    own = _owner_affinity_rank(task.owner, viewer_role)
    deps_rank = 0 if _deps_satisfied(task, status_by_code) else 1
    work = _status_work_rank(task.status)
    # More downstream dependents = more urgent to surface (negate for ascending sort).
    tie_down = -min(successor_count, 99)
    return (phase_rank, pri, due, own, deps_rank, work, tie_down, task.task_code)


def _pick_task(
    pool: Sequence[EnrichedPlanTask],
    *,
    blocks: Sequence[PhasedPlanPhaseBlock],
    viewer_role: str,
    today: date,
    thresholds: DerivationThresholds,
    all_tasks: Sequence[EnrichedPlanTask],
) -> Optional[EnrichedPlanTask]:
    if not pool:
        return None
    status_by_code = _status_by_code(all_tasks)
    succ = _successor_counts(all_tasks)
    ranked = sorted(
        pool,
        key=lambda t: _sort_key(
            t,
            blocks=blocks,
            viewer_role=viewer_role,
            today=today,
            thresholds=thresholds,
            status_by_code=status_by_code,
            successor_count=succ.get(t.task_code, 0),
        ),
    )
    return ranked[0]


@dataclass(frozen=True)
class RelocationPlanNextActionResult:
    """Structured result for API layers (convert to dict if needed)."""

    next_action: Optional[Dict[str, Any]]
    empty_state_reason: Optional[str]

    def as_dict(self) -> Dict[str, Any]:
        return {"next_action": self.next_action, "empty_state_reason": self.empty_state_reason}


def _empty_reason_when_no_viewer_actionable(
    pool: Sequence[EnrichedPlanTask], viewer_role: str
) -> str:
    """Stable copy when open work exists but none for this viewer (employee vs HR vs provider)."""
    v = _norm_role(viewer_role)
    owners = {(t.owner or "").strip().lower() for t in pool}
    if v == "employee":
        if owners <= {"hr"}:
            return "Waiting for HR review"
        if owners <= {"provider"}:
            return "Waiting for provider update"
        return "No action required right now"
    if v == "hr":
        if owners <= {"employee"}:
            return "Waiting for employee action"
        if owners <= {"provider"}:
            return "Waiting for provider update"
        return "No action required right now"
    # provider viewer
    if "provider" not in owners and owners:
        return "Waiting for employee or HR action"
    return "No action required right now"


def select_next_action_for_relocation_plan(
    blocks: Sequence[PhasedPlanPhaseBlock],
    viewer_role: str,
    *,
    today: Optional[date] = None,
    thresholds: Optional[DerivationThresholds] = None,
    allow_cross_role_next_action: bool = False,
) -> RelocationPlanNextActionResult:
    """
    Return exactly one primary next action for ``viewer_role``, or null with a stable reason.

    ``blocks`` should be the canonical phased plan (e.g. from ``build_phased_plan_from_milestones``).

    When ``allow_cross_role_next_action`` is False (default), tasks owned solely by another
    party are omitted; if that leaves no candidates, the result is null with
    ``Waiting for HR review`` / ``Waiting for provider update`` / etc.
    Set True for HR dashboards that should surface employee-owned work and vice versa.
    """
    day = today or date.today()
    th = thresholds or DerivationThresholds()
    all_tasks = _collect_tasks(blocks)
    eligible = _eligible_tasks(all_tasks)
    if not eligible:
        return RelocationPlanNextActionResult(
            next_action=None,
            empty_state_reason="No action required right now",
        )

    pool = _selection_pool(eligible)
    pick_pool = pool if allow_cross_role_next_action else [t for t in pool if _actionable_for_viewer(t, viewer_role)]
    if not pick_pool:
        return RelocationPlanNextActionResult(
            next_action=None,
            empty_state_reason=_empty_reason_when_no_viewer_actionable(pool, viewer_role),
        )

    winner = _pick_task(
        pick_pool,
        blocks=blocks,
        viewer_role=viewer_role,
        today=day,
        thresholds=th,
        all_tasks=all_tasks,
    )
    if winner is None:
        return RelocationPlanNextActionResult(
            next_action=None,
            empty_state_reason="No action required right now",
        )

    status_by_code = _status_by_code(all_tasks)
    succ = _successor_counts(all_tasks)
    reason = build_next_action_reason(
        winner,
        viewer_role=viewer_role,
        downstream_successor_count=succ.get(winner.task_code, 0),
        deps_satisfied=_deps_satisfied(winner, status_by_code),
        today=day,
        thresholds=th,
    )
    cta = _infer_cta_type(winner, viewer_role)

    payload: Dict[str, Any] = {
        "task_id": winner.task_id,
        "task_code": winner.task_code,
        "milestone_type": winner.milestone_type,
        "phase_key": winner.phase_key,
        "title": winner.title,
        "short_label": winner.short_label,
        "owner": winner.owner,
        "status": winner.status,
        "reason": reason,
        "cta_type": cta,
    }
    return RelocationPlanNextActionResult(next_action=payload, empty_state_reason=None)
