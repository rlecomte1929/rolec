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
