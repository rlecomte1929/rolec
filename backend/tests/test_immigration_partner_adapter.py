"""
Unit tests for the immigration partner adapter contract (AIQ-379b).

Asserts the partner-agnostic contract maps 1:1 onto ``public.immigration_milestones``
and that ``CaseStatus`` round-trips through JSON without loss.
"""
from __future__ import annotations

import pytest

from backend.app.services.immigration_partner_adapter import (  # noqa: E402
    CaseStatus,
    MilestoneStatus,
    MilestoneType,
    PartnerAdapter,
    PartnerMilestone,
    case_status_json_schema,
)

# The canonical vocabularies documented in
# supabase/migrations/20260518120000_immigration_core_tables.sql §4 — kept here
# verbatim so this test fails loudly if the enums and the DDL ever diverge.
DDL_MILESTONE_TYPES = {
    "preflight_check",
    "dossier_assembly",
    "criminal_record_ordered",
    "application_filed",
    "biometric_appointment",
    "visa_decision",
    "visa_issued",
    "arrival",
    "local_registration",
    "work_permit_issued",
    "permit_renewal_reminder",
}
DDL_MILESTONE_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "blocked",
    "not_applicable",
}


def test_milestone_type_matches_ddl():
    assert {m.value for m in MilestoneType} == DDL_MILESTONE_TYPES


def test_milestone_status_matches_ddl():
    assert {s.value for s in MilestoneStatus} == DDL_MILESTONE_STATUSES


def test_case_status_round_trips():
    payload = {
        "partner_ref": "PARTNER-2026-00481",
        "stage": "application_filed",
        "updated_at": "2026-06-05T09:12:00Z",
        "milestones": [
            {
                "milestone_type": "application_filed",
                "status": "completed",
                "target_date": "2026-06-01",
                "completed_date": "2026-06-02",
                "notes": "Filed at Munich Auslanderbehorde",
                "evidence_url": None,
                "sort_order": 3,
            }
        ],
    }
    cs = CaseStatus.model_validate(payload)
    assert cs.stage is MilestoneType.APPLICATION_FILED
    assert cs.milestones[0].status is MilestoneStatus.COMPLETED

    # model -> json -> model is stable and lossless
    again = CaseStatus.model_validate_json(cs.model_dump_json())
    assert again == cs


def test_milestone_defaults_to_pending():
    m = PartnerMilestone.model_validate({"milestone_type": "preflight_check"})
    assert m.status is MilestoneStatus.PENDING
    assert m.sort_order == 0


def test_unknown_field_rejected():
    # extra="forbid" keeps the wire contract tight — partners cannot smuggle fields.
    with pytest.raises(Exception):
        PartnerMilestone.model_validate(
            {"milestone_type": "arrival", "partner_secret_code": "x"}
        )


def test_invalid_enum_rejected():
    with pytest.raises(Exception):
        PartnerMilestone.model_validate({"milestone_type": "not_a_real_stage"})


def test_json_schema_is_emitted():
    schema = case_status_json_schema()
    assert schema["title"] == "CaseStatus"
    assert "partner_ref" in schema["properties"]
    assert "milestones" in schema["properties"]


def test_partner_adapter_is_abstract():
    # The base class is a pure interface — it must not be instantiable.
    with pytest.raises(TypeError):
        PartnerAdapter()  # type: ignore[abstract]
