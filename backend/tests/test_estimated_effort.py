"""Roadmap redesign — the additive `estimated_effort` plan-view field."""
from backend.relocation_plan_task_library import estimated_effort_for
from backend.relocation_plan_view_schemas import RelocationPlanPhaseTask


def test_estimated_effort_known_codes():
    assert estimated_effort_for("confirm_family_details") == "~10 min"
    assert estimated_effort_for("upload_passport_copy") == "~5 min"
    assert estimated_effort_for("hr_review_case_data") == "~1 day"


def test_estimated_effort_open_ended_or_unknown_is_none():
    # settle_in is open-ended (empty string in the map) → None
    assert estimated_effort_for("settle_in") is None
    assert estimated_effort_for("zzz_unknown_code") is None
    assert estimated_effort_for("") is None


def test_schema_exposes_estimated_effort_field():
    assert "estimated_effort" in RelocationPlanPhaseTask.model_fields
    # default is None (additive, non-breaking)
    t = RelocationPlanPhaseTask(
        task_id="t1", task_code="x", title="X", status="not_started",
        owner="employee", priority="standard",
    )
    assert t.estimated_effort is None
