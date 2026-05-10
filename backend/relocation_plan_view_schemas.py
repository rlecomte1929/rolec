"""
Canonical response contract for GET /api/relocation-plans/{case_id}/view (future).

Pydantic v2 models shared by employee and HR clients. No routing or DB logic here—
only types, validation, and optional sample builders for tests/OpenAPI examples.

Frontend usage (intended):
- **summary**: global progress header, completion ring, counters.
- **next_action**: hero card; ``cta`` drives primary button (route or action key).
- **phases**: accordion / stepper; ``phase.status`` picks styling; tasks inside for drill-down.
- **role**: gate copy and which CTAs are shown (same payload shape; server may omit HR-only tasks for employees).
- **data_freshness**: subtle "as of" labels; avoid exposing raw admin pipeline IDs.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums — stable wire values (snake_case strings)
# ---------------------------------------------------------------------------


class RelocationPlanViewRole(str, Enum):
    """Who is requesting the view; affects copy and optional field filtering on the server."""

    EMPLOYEE = "employee"
    HR = "hr"


class RelocationPlanTaskStatus(str, Enum):
    """
    Normalized task lifecycle for the plan UI.
    Maps from case_milestone.status + reconciliation (when implemented).
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RelocationPlanPhaseStatus(str, Enum):
    """High-level phase state for timeline / stepper chrome."""

    COMPLETED = "completed"
    ACTIVE = "active"
    UPCOMING = "upcoming"
    BLOCKED = "blocked"


class RelocationPlanTaskOwner(str, Enum):
    """RACI-style owner for filters and badges."""

    EMPLOYEE = "employee"
    HR = "hr"
    JOINT = "joint"
    PROVIDER = "provider"


class RelocationPlanTaskPriority(str, Enum):
    """Display priority; drives urgency stripes and next-action ordering."""

    STANDARD = "standard"
    CRITICAL = "critical"


class RelocationPlanCtaType(str, Enum):
    """
    Machine-readable CTA for the client router.
    Unknown future types should extend this enum rather than free-form strings.
    """

    UPLOAD_DOCUMENT = "upload_document"
    OPEN_INTERNAL_ROUTE = "open_internal_route"
    OPEN_EXTERNAL_URL = "open_external_url"
    COMPLETE_WIZARD_STEP = "complete_wizard_step"
    CONTACT_HR = "contact_hr"
    OPEN_MESSAGES = "open_messages"
    VIEW_DETAILS = "view_details"
    NONE = "none"


class RelocationPlanRequiredInputType(str, Enum):
    """Typed gating inputs for progressive disclosure and checklist rows."""

    DOCUMENT = "document"
    PROFILE_FIELD = "profile_field"
    ASSIGNMENT_FIELD = "assignment_field"
    APPROVAL = "approval"
    OTHER = "other"


class RelocationPlanAutoCompletionSource(str, Enum):
    """Explains how ``status`` was inferred (for tooltips / support); no internal IDs."""

    DOCUMENT_PRESENCE = "document_presence"
    MANUAL = "manual"
    EVALUATION = "evaluation"
    SYSTEM_RULE = "system_rule"
    UNSPECIFIED = "unspecified"


# ---------------------------------------------------------------------------
# Nested DTOs
# ---------------------------------------------------------------------------


class RelocationPlanSummary(BaseModel):
    """
    Header metrics for the plan. ``completion_ratio`` is completed / total tasks
    (excluding ``not_applicable`` from denominator when server applies that rule).
    """

    model_config = {"frozen": False}

    total_tasks: int = Field(ge=0, description="All tasks in the plan projection.")
    completed_tasks: int = Field(ge=0)
    in_progress_tasks: int = Field(ge=0)
    blocked_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0, description="Incomplete tasks with due_date strictly before today.")
    due_soon_tasks: int = Field(
        ge=0,
        description="Incomplete tasks due within the server's configured soon window (e.g. 7 days).",
    )
    completion_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="0..1 for progress ring; 0 when total_tasks is 0.",
    )


class RelocationPlanCta(BaseModel):
    """Action button / deep link for next-action card or task row."""

    model_config = {"frozen": False}

    type: RelocationPlanCtaType = Field(description="Client maps this to a handler.")
    label: str = Field(min_length=1, description="Short button or link text.")
    target: Optional[str] = Field(
        default=None,
        description="Internal path (e.g. /employee/...) or external URL when type allows.",
    )


class RelocationPlanNextAction(BaseModel):
    """
    Single highlighted step. ``blocking`` indicates whether downstream work should be discouraged
    until this item is addressed (UX-only hint; full dependency graph lives on tasks).
    """

    model_config = {"frozen": False}

    task_id: str = Field(description="Stable id; same family as case_milestone.id in v1.")
    title: str
    owner: RelocationPlanTaskOwner
    status: RelocationPlanTaskStatus
    priority: RelocationPlanTaskPriority
    due_date: Optional[date] = None
    reason: str = Field(description="One-line why this is next (human-readable).")
    cta: Optional[RelocationPlanCta] = None
    blocking: bool = Field(default=False, description="True if UX should treat this as a hard gate.")


class RelocationPlanPhaseTaskCounts(BaseModel):
    """Per-phase rollup for collapsed phase headers."""

    model_config = {"frozen": False}

    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    blocked: int = Field(ge=0)


class RelocationPlanRequiredInput(BaseModel):
    """A single prerequisite the UI can show as a sub-checklist or badge."""

    model_config = {"frozen": False}

    type: RelocationPlanRequiredInputType
    key: str = Field(description="Stable key, e.g. passport_copy, aligned with catalog when present.")
    label: str
    present: bool = Field(description="Whether the system considers this input satisfied.")


class RelocationPlanPhaseTask(BaseModel):
    """
    One row in the phased plan. ``task_code`` is a stable template key (e.g. passport_upload);
    ``task_id`` is the instance id for PATCH/reconcile.
    ``blocked_by`` / ``depends_on`` use task_code strings for readability across phases.
    """

    model_config = {"frozen": False}

    task_id: str
    task_code: str = Field(description="Template / milestone_type style key, stable across cases.")
    title: str
    short_label: Optional[str] = Field(default=None, description="Compact label for dense lists.")
    status: RelocationPlanTaskStatus
    owner: RelocationPlanTaskOwner
    priority: RelocationPlanTaskPriority
    due_date: Optional[date] = None
    is_overdue: bool = False
    is_due_soon: bool = False
    blocked_by: List[str] = Field(
        default_factory=list,
        description="task_codes (or ids) currently preventing progress; empty if not blocked.",
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="Logical prerequisites (task_code) for ordering hints.",
    )
    why_this_matters: Optional[str] = Field(default=None, description="Employee-friendly rationale.")
    instructions: List[str] = Field(default_factory=list, description="Bullet steps for the task detail panel.")
    required_inputs: List[RelocationPlanRequiredInput] = Field(default_factory=list)
    cta: Optional[RelocationPlanCta] = None
    auto_completion_source: RelocationPlanAutoCompletionSource = Field(
        default=RelocationPlanAutoCompletionSource.UNSPECIFIED,
        description="How status was derived; safe to show in help text.",
    )
    notes_enabled: bool = Field(
        default=True,
        description="Whether the client should show notes for this task (policy / role gated server-side).",
    )


class RelocationPlanPhase(BaseModel):
    """A grouped slice of the timeline (pre-departure, immigration, arrival, ...)."""

    model_config = {"frozen": False}

    phase_key: str = Field(description="Stable key, e.g. pre_departure.")
    title: str = Field(description="Localized display title.")
    status: RelocationPlanPhaseStatus
    completion_ratio: float = Field(ge=0.0, le=1.0)
    task_counts: RelocationPlanPhaseTaskCounts
    tasks: List[RelocationPlanPhaseTask] = Field(default_factory=list)


class RelocationPlanDataFreshness(BaseModel):
    """Timestamps for transparency; all optional if sources are unavailable."""

    model_config = {"frozen": False}

    documents_checked_at: Optional[datetime] = None
    compliance_checked_at: Optional[datetime] = None


class RelocationPlanViewResponse(BaseModel):
    """
    Root payload for GET /api/relocation-plans/{case_id}/view.
    Same schema for employee and HR; server filters rows or redacts fields by ``role``.
    """

    model_config = {"frozen": False}

    case_id: str
    assignment_id: Optional[str] = Field(
        default=None,
        description="Primary assignment id when resolved; null for case-only contexts.",
    )
    role: RelocationPlanViewRole
    summary: RelocationPlanSummary
    next_action: Optional[RelocationPlanNextAction] = Field(
        default=None,
        description="Null when there is no actionable next step (e.g. all done or plan empty).",
    )
    phases: List[RelocationPlanPhase] = Field(default_factory=list)
    last_evaluated_at: Optional[datetime] = Field(
        default=None,
        description="When the projection was last computed (reconciliation / evaluation pass).",
    )
    data_freshness: Optional[RelocationPlanDataFreshness] = None
    empty_state_reason: Optional[str] = Field(
        default=None,
        description="When next_action is null, stable UX copy (e.g. waiting on another party).",
    )
    debug: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Internal diagnostics; only populated when the client passes debug=true (strip in proxies).",
    )


# ---------------------------------------------------------------------------
# Sample helpers (fixtures / OpenAPI examples — not production mapping)
# ---------------------------------------------------------------------------


def sample_relocation_plan_view_response() -> RelocationPlanViewResponse:
    """Static example matching the product contract; use in tests and route ``responses=`` examples."""
    return RelocationPlanViewResponse(
        case_id="550e8400-e29b-41d4-a716-446655440000",
        assignment_id="660e8400-e29b-41d4-a716-446655440001",
        role=RelocationPlanViewRole.EMPLOYEE,
        summary=RelocationPlanSummary(
            total_tasks=16,
            completed_tasks=2,
            in_progress_tasks=3,
            blocked_tasks=1,
            overdue_tasks=0,
            due_soon_tasks=2,
            completion_ratio=0.125,
        ),
        next_action=RelocationPlanNextAction(
            task_id="milestone-uuid-1",
            title="Upload passport copy",
            owner=RelocationPlanTaskOwner.EMPLOYEE,
            status=RelocationPlanTaskStatus.NOT_STARTED,
            priority=RelocationPlanTaskPriority.CRITICAL,
            due_date=date(2026, 3, 30),
            reason="Required before visa/work permit pack can start",
            cta=RelocationPlanCta(
                type=RelocationPlanCtaType.UPLOAD_DOCUMENT,
                label="Upload passport",
                target="/employee/my-case/documents",
            ),
            blocking=False,
        ),
        phases=[
            RelocationPlanPhase(
                phase_key="pre_departure",
                title="Pre-departure",
                status=RelocationPlanPhaseStatus.ACTIVE,
                completion_ratio=0.5,
                task_counts=RelocationPlanPhaseTaskCounts(
                    total=4,
                    completed=2,
                    in_progress=1,
                    blocked=0,
                ),
                tasks=[
                    RelocationPlanPhaseTask(
                        task_id="milestone-uuid-1",
                        task_code="passport_upload",
                        title="Upload passport copy",
                        short_label="Passport",
                        status=RelocationPlanTaskStatus.NOT_STARTED,
                        owner=RelocationPlanTaskOwner.EMPLOYEE,
                        priority=RelocationPlanTaskPriority.CRITICAL,
                        due_date=date(2026, 3, 30),
                        is_overdue=False,
                        is_due_soon=True,
                        blocked_by=["employee_profile_confirmed"],
                        depends_on=["employee_profile_confirmed"],
                        why_this_matters="Needed to verify identity and prepare the immigration pack.",
                        instructions=[
                            "Upload a readable passport copy",
                            "Ensure passport validity exceeds 6 months if required",
                        ],
                        required_inputs=[
                            RelocationPlanRequiredInput(
                                type=RelocationPlanRequiredInputType.DOCUMENT,
                                key="passport_copy",
                                label="Passport copy",
                                present=False,
                            )
                        ],
                        cta=RelocationPlanCta(
                            type=RelocationPlanCtaType.UPLOAD_DOCUMENT,
                            label="Upload document",
                            target="/employee/my-case/documents",
                        ),
                        auto_completion_source=RelocationPlanAutoCompletionSource.DOCUMENT_PRESENCE,
                        notes_enabled=True,
                    )
                ],
            )
        ],
        last_evaluated_at=datetime(2026, 3, 24, 12, 0, 0),
        data_freshness=RelocationPlanDataFreshness(
            documents_checked_at=datetime(2026, 3, 24, 11, 55, 0),
            compliance_checked_at=datetime(2026, 3, 24, 10, 0, 0),
        ),
    )


def relocation_plan_view_openapi_example() -> dict:
    """JSON-serializable dict for FastAPI ``openapi_examples`` or tests."""
    return sample_relocation_plan_view_response().model_dump(mode="json")
