"""AIQ-378c (AIQ-818) — unit tests for the deterministic suggested-action builder.

Validation Criteria: the template produces a stage-appropriate suggested action +
draft reminder for EVERY pipeline stage; unknown stage falls back; the draft is
built only from the real signal fields (no fabricated facts).
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import case_suggested_action as csa  # noqa: E402
from backend.app.services.immigration_partner_adapter import MilestoneType  # noqa: E402


def _sig(stage, case_id="case-1", days_behind=8, expected_date="2026-06-01"):
    return {"case_id": case_id, "stage": stage, "days_behind": days_behind,
            "expected_date": expected_date, "severity": "warning"}


def test_every_milestone_stage_has_a_specific_action():
    # Every real pipeline stage maps to a concrete, non-fallback suggested action.
    for mt in MilestoneType:
        action = csa.suggested_action_for_stage(mt.value)
        assert action and action != csa._FALLBACK_ACTION, f"no action for stage {mt.value}"


def test_build_returns_action_and_reminder_per_stage():
    for mt in MilestoneType:
        out = csa.build_suggested_action(_sig(mt.value))
        assert set(out) == {"suggested_action", "draft_reminder"}
        assert out["suggested_action"] == csa._STAGE_ACTIONS[mt.value]
        # the reminder embeds the action so HR can send it as-is
        assert out["suggested_action"] in out["draft_reminder"]


def test_unknown_stage_falls_back():
    out = csa.build_suggested_action(_sig("some_unmapped_stage"))
    assert out["suggested_action"] == csa._FALLBACK_ACTION


def test_draft_uses_only_real_fields():
    out = csa.build_suggested_action(_sig("dossier_assembly", case_id="C-42", days_behind=5, expected_date="2026-05-30"))
    draft = out["draft_reminder"]
    assert "C-42" in draft
    assert "5 day(s)" in draft
    assert "2026-05-30" in draft
    assert "Dossier assembly" in draft  # humanized stage label


def test_missing_fields_degrade_without_leaking_none():
    out = csa.build_suggested_action({"stage": "visa_decision"})  # no case_id/days/date
    draft = out["draft_reminder"]
    assert "None" not in draft
    assert "this case" in draft           # case_id fallback
    assert "past its target date" in draft  # days_behind fallback
    assert out["suggested_action"] == csa._STAGE_ACTIONS["visa_decision"]


def test_actions_are_distinct_across_stages():
    actions = [csa._STAGE_ACTIONS[mt.value] for mt in MilestoneType]
    assert len(set(actions)) == len(actions)  # no two stages share an action


# ── AIQ-2041: the live milestone vocabulary, and honest fallbacks ───────────

def test_live_task_vocabulary_is_templated_hr_side():
    """case_milestones uses task_*/service_* keys, and titles are employee-framed.

    Before AIQ-2041 every one of these fell through to the generic fallback, so an
    HR user got "Review this case and follow up on the overdue step." for all 16
    milestone types that can actually be flagged today.
    """
    action = csa.suggested_action_for_stage("task_passport_upload")
    assert action != csa._FALLBACK_ACTION
    assert "passport" in action.lower()
    # An HR-owned step reads as HR's own job, not as something to chase.
    assert "yourself" in csa.suggested_action_for_stage("task_hr_case_review").lower()


def test_unknown_stage_uses_the_milestones_real_title_not_an_invention():
    """~90 milestone types exist; the opaque codes cannot be templated honestly.

    'pre_departure_ai_01' says nothing about what it is, but its curated title does.
    Using the title is real data; inventing a sentence for the code would not be.
    """
    action = csa.suggested_action_for_stage(
        "pre_departure_ai_01",
        title="Gather core identity and employment documents",
        owner="employee",
    )
    assert action == "Chase the employee: Gather core identity and employment documents."


def test_unknown_stage_owner_hr_reads_as_waiting_on_hr():
    action = csa.suggested_action_for_stage(
        "post_arrival_corridor_07", title="Optional EU residence documentation", owner="hr"
    )
    assert action.startswith("Waiting on HR:")


def test_unknown_stage_and_no_title_falls_back_to_generic():
    """Never fabricate: with neither a template nor a title there is nothing to say."""
    assert csa.suggested_action_for_stage("mystery_code_42") == csa._FALLBACK_ACTION
    assert csa.suggested_action_for_stage("mystery_code_42", title="  ") == csa._FALLBACK_ACTION


def test_build_suggested_action_threads_title_and_owner():
    out = csa.build_suggested_action(
        {
            "case_id": "c1",
            "stage": "immigration_ai_03",
            "days_behind": 12,
            "expected_date": "2026-06-01",
            "title": "Register under the EEA regulations with UDI",
            "owner": "employee",
        }
    )
    assert "Register under the EEA regulations with UDI" in out["suggested_action"]
    assert "12 day(s)" in out["draft_reminder"]
