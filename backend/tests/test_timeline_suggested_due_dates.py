"""AIQ-1340 — suggested due dates on the LIVE roadmap (timeline) path.

AIQ-1258 computed suggested dates on a dead path; this ports the behaviour to the
timeline mapper (`_enriched_to_schema_task`). For a task with no real deadline it
estimates ``move_date − phase lead time`` and flags it suggested — for pre-move
phases only (``arrival``/``post_arrival`` stay undated). Real deadlines are never
overwritten.
"""
from __future__ import annotations

import datetime

from backend.app.services import relocation_plan_view_service as svc
from backend.app.services.roadmap_lead_times import lead_time_days_for_phase
from backend.relocation_plan_service import EnrichedPlanTask
from backend.relocation_plan_status_derivation import RelocationPlanDerivationContext

MOVE = datetime.date(2026, 9, 1)


def _task(phase_key: str, target_date: str | None = None) -> EnrichedPlanTask:
    return EnrichedPlanTask(
        task_id="id-t1",
        task_code="t1",
        milestone_type="mt",
        phase_key=phase_key,
        title="T",
        short_label="t",
        owner="employee",
        priority="standard",
        status="not_started",
        raw_milestone_status="pending",
        depends_on=(),
        sequence_in_phase=10,
        auto_completion_hint="manual",
        why_this_matters="",
        instructions=(),
        required_inputs=(),
        target_date=target_date,
    )


def _map(t: EnrichedPlanTask, move_date: datetime.date | None):
    return svc._enriched_to_schema_task(
        t,
        ctx=RelocationPlanDerivationContext(),
        status_by_code={},
        viewer_role="employee",
        today=datetime.date(2026, 1, 1),
        move_date=move_date,
    )


# ── lead_time_days_for_phase ────────────────────────────────────────────────

def test_pre_move_phases_have_lead_times():
    assert lead_time_days_for_phase("immigration") == 90
    assert lead_time_days_for_phase("pre_departure") == 90
    assert lead_time_days_for_phase("logistics") == 45


def test_arrival_and_unknown_phases_have_no_lead_time():
    assert lead_time_days_for_phase("arrival") is None
    assert lead_time_days_for_phase("post_arrival") is None
    assert lead_time_days_for_phase("nonsense") is None


# ── mapper compute ──────────────────────────────────────────────────────────

def test_undated_pre_move_task_gets_suggested_date():
    out = _map(_task("immigration"), MOVE)
    assert out.due_date == MOVE - datetime.timedelta(days=90)
    assert out.due_date_is_suggested is True


def test_logistics_uses_its_own_lead_time():
    out = _map(_task("logistics"), MOVE)
    assert out.due_date == MOVE - datetime.timedelta(days=45)
    assert out.due_date_is_suggested is True


def test_real_deadline_is_kept_and_not_flagged():
    out = _map(_task("immigration", target_date="2026-05-01"), MOVE)
    assert out.due_date == datetime.date(2026, 5, 1)
    assert out.due_date_is_suggested is False


def test_arrival_task_stays_undated():
    out = _map(_task("arrival"), MOVE)
    assert out.due_date is None
    assert out.due_date_is_suggested is False


def test_no_move_date_no_suggestion():
    out = _map(_task("immigration"), None)
    assert out.due_date is None
    assert out.due_date_is_suggested is False
