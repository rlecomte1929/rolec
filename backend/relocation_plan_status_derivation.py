"""
Derived relocation-plan task statuses from profile, documents, and explicit milestone rows.

Pure logic — callers load ``profile``, ``case_documents``, etc. from DB/API and pass a
``RelocationPlanDerivationContext``. No FastAPI or SQL here.

Precedence (highest wins when merging candidates):
  ``not_applicable`` > ``blocked`` > ``completed`` > ``in_progress`` > ``not_started``

Manual milestone row (explicit user/HR action in ``case_milestones.status``) participates
as **additional candidates** in pass 1 with the same precedence — so e.g. rule ``blocked``
beats explicit ``completed``. Pass 2 merges dependency ``blocked`` against pass-1 status
with the same precedence, so an unmet ``depends_on`` can override a stale ``done`` unless
a higher-precedence status wins (e.g. ``not_applicable`` beats ``blocked``).

If source data is missing, rules fall back to ``not_started`` (never invent completion).

Debug traces are only populated when ``include_debug=True``; strip before external APIs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .relocation_plan_task_library import TaskLibraryEntry

# Aligns with requirement_evaluation_service._MET_DOC_STATUSES (subset for "on file").
_MET_DOC_STATUSES: FrozenSet[str] = frozenset({"uploaded", "under_review", "approved"})
_REJECT_DOC_STATUSES: FrozenSet[str] = frozenset({"rejected"})

VALID_PLAN_STATUSES: FrozenSet[str] = frozenset(
    {"not_applicable", "blocked", "completed", "in_progress", "not_started"}
)

# Earlier in list = higher priority (wins merge).
STATUS_PRECEDENCE: Tuple[str, ...] = (
    "not_applicable",
    "blocked",
    "completed",
    "in_progress",
    "not_started",
)

_STATUS_INDEX: Dict[str, int] = {s: i for i, s in enumerate(STATUS_PRECEDENCE)}


def status_precedence_rank(status: str) -> int:
    return _STATUS_INDEX.get(status, len(STATUS_PRECEDENCE))


def merge_status_candidates(candidates: Iterable[str]) -> str:
    """Pick the winning status from parallel signals using ``STATUS_PRECEDENCE``."""
    best: Optional[str] = None
    best_rank = len(STATUS_PRECEDENCE) + 1
    for c in candidates:
        if c not in VALID_PLAN_STATUSES:
            continue
        r = status_precedence_rank(c)
        if r < best_rank:
            best_rank = r
            best = c
    return best if best is not None else "not_started"


# ---------------------------------------------------------------------------
# Thresholds & due helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DerivationThresholds:
    """Tunable windows for client copy (due soon / overdue)."""

    due_soon_days: int = 7
    """Calendar days inclusive from today through today+due_soon_days for *due soon*."""


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def is_overdue(target_date: Optional[str], *, today: Optional[date] = None) -> bool:
    """True if target is strictly before today and a date was provided."""
    d = _parse_iso_date(target_date)
    if d is None:
        return False
    day = today or date.today()
    return d < day


def is_due_soon(
    target_date: Optional[str],
    *,
    today: Optional[date] = None,
    thresholds: Optional[DerivationThresholds] = None,
) -> bool:
    """
    True if target falls in (today, today+thresholds.due_soon_days] inclusive upper bound.
    Not overdue: same-day due is "soon", not overdue.
    """
    d = _parse_iso_date(target_date)
    if d is None:
        return False
    day = today or date.today()
    th = thresholds or DerivationThresholds()
    if d < day:
        return False
    horizon = day.fromordinal(day.toordinal() + max(0, th.due_soon_days))
    return d <= horizon


# ---------------------------------------------------------------------------
# Context (only fields we can populate from real ReloPass/mobility sources today)
# ---------------------------------------------------------------------------


@dataclass
class RelocationPlanDerivationContext:
    """
    Snapshot for derivation. All fields optional — absent means "unknown, stay conservative".

    - ``profile``: assignment ``profile`` / case draft JSON (``primaryApplicant``, ``movePlan``,
      ``complianceDocs``, ``dependents``, ``spouse``, …).
    - ``case_documents``: mobility-style rows ``{document_key, document_status, person_id?}``.
    - ``requirement_eval_by_code``: normalized evaluation outcome per ``requirements_catalog``
      code (e.g. ``passport_copy_uploaded`` -> ``met`` / ``missing`` / ``needs_review``).
    - ``selected_service_keys``: wizard ``case_services`` keys (``movers``, ``housing``, …).
    - ``move_includes_shipment``: explicit override when known; else may infer from services.
    - ``destination_requires_biometrics``: when ``False``, biometrics task becomes N/A; when
      ``None``, do **not** assume — keep ``not_started``.
    """

    profile: Optional[Dict[str, Any]] = None
    case_documents: Optional[List[Dict[str, Any]]] = None
    requirement_eval_by_code: Optional[Dict[str, str]] = None
    selected_service_keys: Optional[Set[str]] = None
    move_includes_shipment: Optional[bool] = None
    destination_requires_biometrics: Optional[bool] = None


# ---------------------------------------------------------------------------
# Profile / document helpers (mirror hr_case_readiness / requirement eval conventions)
# ---------------------------------------------------------------------------


def _nz(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (dict, list)):
        return bool(val)
    s = str(val).strip()
    if not s or s.lower() == "unknown":
        return False
    return True


def _norm_eval(val: Optional[str]) -> str:
    return (val or "").strip().lower()


def _profile_primary_applicant(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not profile or not isinstance(profile, dict):
        return {}
    pa = profile.get("primaryApplicant")
    return pa if isinstance(pa, dict) else {}


def _profile_move_plan(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not profile or not isinstance(profile, dict):
        return {}
    mp = profile.get("movePlan")
    return mp if isinstance(mp, dict) else {}


def _compliance_docs(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not profile or not isinstance(profile, dict):
        return {}
    cd = profile.get("complianceDocs")
    return cd if isinstance(cd, dict) else {}


def passport_copy_satisfied(ctx: RelocationPlanDerivationContext) -> bool:
    """
    True if profile flags passport upload **or** mobility ``case_documents`` shows an on-file
    passport-like doc in a met status **or** requirement eval ``passport_copy_uploaded`` is met.
    """
    cd = _compliance_docs(ctx.profile)
    if cd.get("hasPassportScans") is True:
        return True
    ev = ctx.requirement_eval_by_code or {}
    if _norm_eval(ev.get("passport_copy_uploaded")) in ("met", "satisfied", "pass"):
        return True
    docs = ctx.case_documents or []
    for row in docs:
        dk = _norm_key(row.get("document_key"))
        if not dk or "passport" not in dk:
            continue
        st = _norm_key(row.get("document_status"))
        if st in _MET_DOC_STATUSES:
            return True
    return False


def employment_letter_satisfied(ctx: RelocationPlanDerivationContext) -> bool:
    cd = _compliance_docs(ctx.profile)
    if cd.get("hasEmploymentLetter") is True:
        return True
    ev = ctx.requirement_eval_by_code or {}
    if _norm_eval(ev.get("signed_employment_contract")) in ("met", "satisfied", "pass"):
        return True
    docs = ctx.case_documents or []
    for row in docs:
        dk = _norm_key(row.get("document_key"))
        if not dk:
            continue
        if "contract" not in dk and "employment" not in dk:
            continue
        st = _norm_key(row.get("document_status"))
        if st in _MET_DOC_STATUSES:
            return True
    return False


def _norm_key(v: Any) -> str:
    return str(v or "").strip().lower()


def employee_core_profile_satisfied(ctx: RelocationPlanDerivationContext) -> bool:
    pa = _profile_primary_applicant(ctx.profile)
    emp = pa.get("employer") if isinstance(pa.get("employer"), dict) else {}
    return (
        _nz(pa.get("fullName"))
        and _nz(pa.get("nationality"))
        and _nz(emp.get("jobLevel"))
        and _nz(emp.get("roleTitle"))
    )


def family_details_satisfied(ctx: RelocationPlanDerivationContext) -> bool:
    """Same household signal as ``build_intake_checklist_items`` (marital / spouse / children)."""
    if not ctx.profile or not isinstance(ctx.profile, dict):
        return False
    spouse = ctx.profile.get("spouse") if isinstance(ctx.profile.get("spouse"), dict) else {}
    deps = ctx.profile.get("dependents")
    if not isinstance(deps, list):
        deps = []
    fam_ok = (
        _nz(ctx.profile.get("maritalStatus"))
        or _nz(spouse.get("fullName"))
        or any(
            _nz(d.get("firstName")) or _nz(d.get("fullName")) for d in deps if isinstance(d, dict)
        )
    )
    return fam_ok


def route_data_satisfied(ctx: RelocationPlanDerivationContext) -> bool:
    mp = _profile_move_plan(ctx.profile)
    return _nz(mp.get("origin")) and _nz(mp.get("destination"))


def _infer_move_includes_shipment(ctx: RelocationPlanDerivationContext) -> Optional[bool]:
    if ctx.move_includes_shipment is not None:
        return ctx.move_includes_shipment
    keys = ctx.selected_service_keys
    if keys is None:
        return None
    lowered = {str(k).strip().lower() for k in keys}
    if "movers" in lowered or "shipment" in lowered or "shipping" in lowered:
        return True
    return None


# ---------------------------------------------------------------------------
# Explicit milestone → candidate statuses (merged with derived)
# ---------------------------------------------------------------------------


def explicit_status_candidates(raw_milestone_status: Optional[str]) -> List[str]:
    """
    Map ``case_milestones.status`` into plan vocabulary candidates.

    ``skipped`` → ``not_applicable`` (user/HR marked not doing this item).
    ``pending`` / ``overdue`` → no explicit candidate (derive only).
    """
    s = (raw_milestone_status or "").strip().lower()
    if s == "done":
        return ["completed"]
    if s == "skipped":
        return ["not_applicable"]
    if s == "blocked":
        return ["blocked"]
    if s == "in_progress":
        return ["in_progress"]
    if s in ("not_applicable", "n/a", "na"):
        return ["not_applicable"]
    return []


# ---------------------------------------------------------------------------
# Per-task rule candidates (no cross-task deps here — pass 2 adds blocking)
# ---------------------------------------------------------------------------


def _rule_candidates_for_task(task_code: str, ctx: RelocationPlanDerivationContext) -> List[str]:
    if task_code == "confirm_employee_core_profile":
        return ["completed"] if employee_core_profile_satisfied(ctx) else ["not_started"]

    if task_code == "confirm_family_details":
        return ["completed"] if family_details_satisfied(ctx) else ["not_started"]

    if task_code == "upload_passport_copy":
        return ["completed"] if passport_copy_satisfied(ctx) else ["not_started"]

    if task_code == "upload_assignment_letter":
        return ["completed"] if employment_letter_satisfied(ctx) else ["not_started"]

    if task_code == "verify_destination_route":
        if route_data_satisfied(ctx):
            return ["completed"]
        return ["not_started"]

    if task_code == "prepare_visa_pack":
        if not passport_copy_satisfied(ctx):
            return ["blocked"]
        return ["not_started"]

    if task_code == "book_biometrics":
        if ctx.destination_requires_biometrics is False:
            return ["not_applicable"]
        return ["not_started"]

    if task_code == "arrange_movers":
        inc = _infer_move_includes_shipment(ctx)
        if inc is False:
            return ["not_applicable"]
        return ["not_started"]

    # Default: no automatic completion signal in MVP
    return ["not_started"]


def rule_candidates_with_library(
    entry: TaskLibraryEntry,
    ctx: RelocationPlanDerivationContext,
) -> List[str]:
    """Dispatch by ``task_code``; unknown codes stay ``not_started`` unless library adds hints."""
    return _rule_candidates_for_task(entry.task_code, ctx)


# ---------------------------------------------------------------------------
# Dependency blocking (pass 2)
# ---------------------------------------------------------------------------


def _terminal_for_deps(status: str) -> bool:
    return status in ("completed", "not_applicable")


def dependency_block_candidates(
    task_code: str,
    entry: TaskLibraryEntry,
    effective_by_code: Mapping[str, str],
) -> List[str]:
    """
    If any ``depends_on`` task is not terminal, emit ``blocked`` (task is actionable later
    but not yet).
    """
    for dep in entry.depends_on:
        st = effective_by_code.get(dep)
        if st is None:
            # Dependency not in plan slice — do not block (partial views).
            continue
        if not _terminal_for_deps(st):
            return ["blocked"]
    return []


# ---------------------------------------------------------------------------
# Result + orchestration
# ---------------------------------------------------------------------------


@dataclass
class DerivationResult:
    """One task's derived outcome."""

    status: str
    candidates_merged: Tuple[str, ...] = ()
    debug_trace: Optional[Dict[str, Any]] = None


def derive_statuses_for_plan_tasks(
    tasks: Sequence[Tuple[TaskLibraryEntry, str]],
    ctx: RelocationPlanDerivationContext,
    *,
    include_debug: bool = False,
) -> Dict[str, DerivationResult]:
    """
    Two-pass derivation for a list of ``(library_entry, raw_milestone_status)``.

    Pass 1: merge explicit + rules per task.
    Pass 2: add ``blocked`` when a listed ``depends_on`` task is not terminal.
    """
    # Pass 1
    pass1: Dict[str, str] = {}
    traces: Dict[str, Dict[str, Any]] = {}
    for entry, raw in tasks:
        explicit = explicit_status_candidates(raw)
        rules = rule_candidates_with_library(entry, ctx)
        cands = list(explicit) + list(rules)
        st = merge_status_candidates(cands)
        pass1[entry.task_code] = st
        if include_debug:
            traces[entry.task_code] = {"pass1_candidates": cands, "pass1_status": st}

    # Pass 2 — dependency blocking (always merged; ``not_applicable`` beats ``blocked``).
    out: Dict[str, DerivationResult] = {}
    for entry, raw in tasks:
        p1_status = pass1[entry.task_code]
        p1_cands = traces[entry.task_code]["pass1_candidates"] if include_debug else []
        block = dependency_block_candidates(entry.task_code, entry, pass1)
        if block:
            final = merge_status_candidates([p1_status] + block)
        else:
            final = p1_status
        dbg = None
        merged: Tuple[str, ...] = ()
        if include_debug:
            dbg = traces.get(entry.task_code, {})
            dbg["pass2_block_candidates"] = block
            dbg["final_status"] = final
            merged = tuple(list(p1_cands) + block)
        out[entry.task_code] = DerivationResult(
            status=final,
            candidates_merged=merged,
            debug_trace=dbg,
        )
    return out


def apply_derived_statuses_to_enriched_tasks(
    enriched: Sequence[Any],
    ctx: RelocationPlanDerivationContext,
    *,
    include_debug: bool = False,
) -> None:
    """
    Mutates each ``EnrichedPlanTask``-like object with ``.task_code`` and ``.raw_milestone_status``
    and ``.status`` — replaces ``.status`` with derived value.

    Attach ``._derivation_debug`` on each object only when ``include_debug`` (internal; strip in API).
    """
    from .relocation_plan_task_library import get_task_library_entry_by_code

    pairs: List[Tuple[TaskLibraryEntry, str]] = []
    for t in enriched:
        entry = get_task_library_entry_by_code(getattr(t, "task_code", ""))
        if entry is None:
            continue
        raw = str(getattr(t, "raw_milestone_status", "") or "")
        pairs.append((entry, raw))

    results = derive_statuses_for_plan_tasks(pairs, ctx, include_debug=include_debug)
    for t in enriched:
        code = getattr(t, "task_code", "")
        res = results.get(code)
        if res is None:
            continue
        t.status = res.status
        if include_debug:
            setattr(t, "_derivation_debug", res.debug_trace)
