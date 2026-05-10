"""
Phased relocation plan engine — adapts flat ``case_milestones`` rows using the task library.

Pure functions + a thin façade class. Does not replace ``timeline_service`` or DB access;
call this after ``list_case_milestones`` to group, order, and enrich for API responses.

Sorting: phase order (``PHASE_ORDER``) → topological order on ``depends_on`` (within present
task set) → ``sequence_in_phase`` → ``task_code`` as final tie-break.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, DefaultDict, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .relocation_plan_task_library import (
    PHASE_ORDER,
    PHASE_TITLES,
    TaskLibraryEntry,
    get_task_library_entry_by_milestone_type,
    phase_index,
)

# ---------------------------------------------------------------------------
# Data carriers (adapter output; not Pydantic — keep free of FastAPI import cycles)
# ---------------------------------------------------------------------------


@dataclass
class EnrichedPlanTask:
    """One milestone row merged with library metadata (canonical plan task)."""

    task_id: str
    task_code: str
    milestone_type: str
    phase_key: str
    title: str
    short_label: str
    owner: str
    priority: str  # standard | critical
    status: str  # not_started | in_progress | completed | blocked | not_applicable
    raw_milestone_status: str
    depends_on: Tuple[str, ...]
    sequence_in_phase: int
    auto_completion_hint: str
    why_this_matters: str
    instructions: Tuple[str, ...]
    required_inputs: Tuple[Dict[str, str], ...]
    target_date: Optional[str] = None
    notes: Optional[str] = None
    # Preserve original row for PATCH / debugging (strip before external API if needed)
    raw_milestone: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhasedPlanPhaseBlock:
    """Tasks for one phase plus computed roll-up status."""

    phase_key: str
    phase_title: str
    status: str  # completed | active | upcoming | blocked
    tasks: List[EnrichedPlanTask] = field(default_factory=list)

    @property
    def task_counts(self) -> Dict[str, int]:
        return compute_phase_task_counts(self.tasks)


# ---------------------------------------------------------------------------
# Status mapping (DB milestone → plan vocabulary)
# ---------------------------------------------------------------------------


def map_milestone_status_to_plan_status(raw: Optional[str]) -> str:
    """
    Map ``case_milestones.status`` to plan task status.
    ``skipped`` counts as terminal (completed) for phase math — same as current tracker UX.
    """
    s = (raw or "pending").strip().lower()
    if s == "done":
        return "completed"
    if s == "skipped":
        return "completed"
    if s == "blocked":
        return "blocked"
    if s == "in_progress":
        return "in_progress"
    if s in ("not_applicable", "n/a", "na"):
        return "not_applicable"
    # pending, overdue, unknown
    return "not_started"


def _is_terminal_plan_status(st: str) -> bool:
    return st in ("completed", "not_applicable")


# ---------------------------------------------------------------------------
# Library hydration
# ---------------------------------------------------------------------------


def _criticality_to_priority(criticality: Optional[str]) -> str:
    return "critical" if (criticality or "").strip().lower() == "critical" else "standard"


def _synthetic_entry_for_unknown_milestone(milestone_type: str, title: str) -> TaskLibraryEntry:
    """Fallback for legacy or custom milestone rows not in the MVP library."""
    safe_code = (milestone_type or "unknown_task").strip() or "unknown_task"
    return TaskLibraryEntry(
        task_code=safe_code,
        milestone_type=milestone_type,
        phase_key="pre_departure",
        title=title or milestone_type,
        short_label=title or milestone_type,
        default_owner="joint",
        priority="standard",
        depends_on=(),
        auto_completion_hint="manual",
        why_this_matters="",
        instructions=(),
        required_inputs=(),
        sequence_in_phase=999,
    )


def hydrate_task_from_library(
    milestone_type: str,
    *,
    fallback_title: str = "",
) -> TaskLibraryEntry:
    """Return library row for ``milestone_type``, or a deterministic synthetic entry."""
    entry = get_task_library_entry_by_milestone_type(milestone_type)
    if entry:
        return entry
    return _synthetic_entry_for_unknown_milestone(milestone_type, fallback_title)


def adapt_milestone_row(row: Mapping[str, Any]) -> EnrichedPlanTask:
    """
    Merge one DB milestone dict with the task library.
    ``milestone_type`` is the stable join key to ``OPERATIONAL_TASK_DEFAULTS``.
    """
    mt = str(row.get("milestone_type") or "").strip()
    title_db = str(row.get("title") or "").strip()
    lib = hydrate_task_from_library(mt, fallback_title=title_db)

    title = title_db or lib.title
    owner = str(row.get("owner") or lib.default_owner).strip() or lib.default_owner
    crit_raw = row.get("criticality")
    if crit_raw is not None and str(crit_raw).strip() != "":
        priority = _criticality_to_priority(str(crit_raw))
    else:
        priority = lib.priority if lib.priority in ("critical", "standard") else "standard"

    raw_st = str(row.get("status") or "pending")
    plan_st = map_milestone_status_to_plan_status(raw_st)

    inputs: Tuple[Dict[str, str], ...] = tuple(
        {"type": ri.input_type, "key": ri.key, "label": ri.label} for ri in lib.required_inputs
    )

    return EnrichedPlanTask(
        task_id=str(row.get("id") or ""),
        task_code=lib.task_code,
        milestone_type=mt or lib.milestone_type,
        phase_key=lib.phase_key,
        title=title,
        short_label=lib.short_label,
        owner=owner,
        priority=priority,
        status=plan_st,
        raw_milestone_status=raw_st,
        depends_on=lib.depends_on,
        sequence_in_phase=lib.sequence_in_phase,
        auto_completion_hint=lib.auto_completion_hint,
        why_this_matters=lib.why_this_matters,
        instructions=lib.instructions,
        required_inputs=inputs,
        target_date=_norm_date_str(row.get("target_date")),
        notes=_norm_notes(row.get("notes")),
        raw_milestone=dict(row),
    )


def _norm_date_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()[:10]  # type: ignore[no-any-return]
        except Exception:
            return str(v)[:10]
    s = str(v).strip()
    return s[:10] if s else None


def _norm_notes(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ---------------------------------------------------------------------------
# Ordering: topological + tie-breaks
# ---------------------------------------------------------------------------


def _present_codes(tasks: Sequence[EnrichedPlanTask]) -> Set[str]:
    return {t.task_code for t in tasks}


def order_tasks_deterministic(tasks: Sequence[EnrichedPlanTask]) -> List[EnrichedPlanTask]:
    """
    Dependency-aware global order: only edges to tasks present in ``tasks`` are considered.
    Tie-break: ``phase_index``, ``sequence_in_phase``, ``task_code``.
    """
    if not tasks:
        return []
    present = _present_codes(tasks)
    by_code: Dict[str, EnrichedPlanTask] = {t.task_code: t for t in tasks}

    # predecessors[u] = tasks that must appear before u (in present set)
    predecessors: DefaultDict[str, Set[str]] = defaultdict(set)
    successors: DefaultDict[str, Set[str]] = defaultdict(set)
    in_degree: DefaultDict[str, int] = defaultdict(int)

    for t in tasks:
        preds = [d for d in t.depends_on if d in present and d != t.task_code]
        for d in preds:
            predecessors[t.task_code].add(d)
            successors[d].add(t.task_code)
        in_degree[t.task_code]  # ensure key exists

    for t in tasks:
        in_degree[t.task_code] = len(predecessors[t.task_code])

    def sort_key(tc: str) -> Tuple[int, int, str]:
        x = by_code[tc]
        return (phase_index(x.phase_key), x.sequence_in_phase, x.task_code)

    # Min-heap so each time we pop the globally smallest tie-break among ready tasks.
    heap: List[Tuple[Tuple[int, int, str], str]] = [
        (sort_key(tc), tc) for tc in by_code if in_degree[tc] == 0
    ]
    heapq.heapify(heap)
    ordered: List[str] = []
    seen: Set[str] = set()
    while heap:
        _, u = heapq.heappop(heap)
        if u in seen:
            continue
        seen.add(u)
        ordered.append(u)
        for v in successors[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                heapq.heappush(heap, (sort_key(v), v))

    if len(ordered) < len(by_code):
        remaining = [tc for tc in by_code if tc not in seen]
        remaining.sort(key=sort_key)
        ordered.extend(remaining)

    return [by_code[tc] for tc in ordered]


def group_tasks_by_phase(ordered_tasks: Sequence[EnrichedPlanTask]) -> List[PhasedPlanPhaseBlock]:
    """
    Bucket ordered tasks into ``PhasedPlanPhaseBlock`` rows following ``PHASE_ORDER``.
    Phases with no tasks are omitted.
    """
    by_phase: DefaultDict[str, List[EnrichedPlanTask]] = defaultdict(list)
    for t in ordered_tasks:
        by_phase[t.phase_key].append(t)

    blocks: List[PhasedPlanPhaseBlock] = []
    for pk in PHASE_ORDER:
        if pk not in by_phase:
            continue
        blocks.append(
            PhasedPlanPhaseBlock(
                phase_key=pk,
                phase_title=PHASE_TITLES.get(pk, pk.replace("_", " ").title()),
                status="upcoming",  # filled by compute_phase_statuses
                tasks=by_phase[pk],
            )
        )
    return blocks


def compute_phase_task_counts(tasks: Sequence[EnrichedPlanTask]) -> Dict[str, int]:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    in_progress = sum(1 for t in tasks if t.status == "in_progress")
    blocked = sum(1 for t in tasks if t.status == "blocked")
    return {"total": total, "completed": completed, "in_progress": in_progress, "blocked": blocked}


def compute_phase_completion_ratio(tasks: Sequence[EnrichedPlanTask]) -> float:
    if not tasks:
        return 0.0
    done = sum(1 for t in tasks if _is_terminal_plan_status(t.status))
    return round(done / len(tasks), 4)


def compute_phase_statuses(blocks: Sequence[PhasedPlanPhaseBlock]) -> None:
    """
    Mutates ``blocks[*].status``:
    1) Any task ``blocked`` → phase ``blocked``.
    2) Else all tasks terminal → ``completed``.
    3) Else first remaining phase → ``active``, all later non-terminal phases → ``upcoming``.
    """
    if not blocks:
        return

    for b in blocks:
        if any(t.status == "blocked" for t in b.tasks):
            b.status = "blocked"

    for b in blocks:
        if b.status == "blocked":
            continue
        if _phase_all_terminal(b.tasks):
            b.status = "completed"

    assigned_active = False
    for b in blocks:
        if b.status in ("blocked", "completed"):
            continue
        if not assigned_active:
            b.status = "active"
            assigned_active = True
        else:
            b.status = "upcoming"


def _phase_all_terminal(tasks: Sequence[EnrichedPlanTask]) -> bool:
    if not tasks:
        return True
    return all(_is_terminal_plan_status(t.status) for t in tasks)


# ---------------------------------------------------------------------------
# Façade
# ---------------------------------------------------------------------------


def build_phased_plan_from_milestones(milestones: Sequence[Mapping[str, Any]]) -> List[PhasedPlanPhaseBlock]:
    """
    Full adapter: flat milestone rows → ordered, enriched phase blocks with statuses.
    Does not hit the database.
    """
    enriched = [adapt_milestone_row(m) for m in milestones]
    ordered = order_tasks_deterministic(enriched)
    blocks = group_tasks_by_phase(ordered)
    compute_phase_statuses(blocks)
    return blocks


class RelocationPlanPhaseEngine:
    """Thin OO wrapper for injection / testing."""

    def build_phased_plan(self, milestones: Sequence[Mapping[str, Any]]) -> List[PhasedPlanPhaseBlock]:
        return build_phased_plan_from_milestones(milestones)

    def enrich_only(self, milestones: Sequence[Mapping[str, Any]]) -> List[EnrichedPlanTask]:
        """Library merge + deterministic sort, no phase grouping."""
        enriched = [adapt_milestone_row(m) for m in milestones]
        return order_tasks_deterministic(enriched)
