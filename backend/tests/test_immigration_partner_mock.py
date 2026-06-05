"""
Unit tests for the mock immigration-partner adapter + selector (AIQ-379c).

Verifies the mock conforms to the AIQ-379b contract and that the feature-flag
factory selects it without touching production code paths.
"""
from __future__ import annotations

import pytest

from backend.app.services.immigration_partner_adapter import (  # noqa: E402
    CaseStatus,
    MilestoneStatus,
    MilestoneType,
    PartnerAdapter,
    PartnerMilestone,
)
from backend.app.services.immigration_partner_factory import (  # noqa: E402
    ADAPTER_MODE_ENV,
    get_partner_adapter,
)
from backend.app.services.immigration_partner_mock import (  # noqa: E402
    MOCK_PARTNER_REFS,
    MockPartnerAdapter,
)


@pytest.fixture
def adapter() -> MockPartnerAdapter:
    return MockPartnerAdapter()


def test_mock_implements_contract(adapter):
    assert isinstance(adapter, PartnerAdapter)


@pytest.mark.parametrize("ref", MOCK_PARTNER_REFS)
def test_get_case_status_conforms_to_schema(adapter, ref):
    cs = adapter.get_case_status(ref)
    assert isinstance(cs, CaseStatus)
    # Re-validate the serialized form against the contract — proves conformance.
    assert CaseStatus.model_validate(cs.model_dump()) == cs
    assert cs.partner_ref == ref


def test_three_lifecycle_fixtures_present(adapter):
    stages = {ref: adapter.get_case_status(ref).stage for ref in MOCK_PARTNER_REFS}
    assert stages == {
        "MOCK-CASE-EARLY": MilestoneType.DOSSIER_ASSEMBLY,
        "MOCK-CASE-REVIEW": MilestoneType.VISA_DECISION,
        "MOCK-CASE-GRANTED": MilestoneType.VISA_ISSUED,
    }


def test_list_milestones_returns_partner_milestones(adapter):
    milestones = adapter.list_milestones("MOCK-CASE-REVIEW")
    assert milestones and all(isinstance(m, PartnerMilestone) for m in milestones)
    # The in-progress case has exactly one IN_PROGRESS milestone (the current stage).
    in_progress = [m for m in milestones if m.status is MilestoneStatus.IN_PROGRESS]
    assert len(in_progress) == 1
    assert in_progress[0].milestone_type is MilestoneType.VISA_DECISION


def test_get_milestone_evidence(adapter):
    # Granted case has an evidence scan on VISA_ISSUED.
    url = adapter.get_milestone_evidence("MOCK-CASE-GRANTED", MilestoneType.VISA_ISSUED)
    assert url and url.endswith("visa.pdf")
    # A milestone without evidence returns None.
    assert adapter.get_milestone_evidence("MOCK-CASE-EARLY", MilestoneType.PREFLIGHT_CHECK) is None


def test_unknown_partner_ref_raises(adapter):
    with pytest.raises(ValueError):
        adapter.get_case_status("NOPE-404")


def test_returned_models_are_isolated_copies(adapter):
    # Mutating a returned result must not corrupt the shared fixture.
    cs = adapter.get_case_status("MOCK-CASE-EARLY")
    cs.milestones[0].notes = "MUTATED"
    again = adapter.get_case_status("MOCK-CASE-EARLY")
    assert again.milestones[0].notes != "MUTATED"


# ---------------------------------------------------------------------------
# Feature-flag selector
# ---------------------------------------------------------------------------


def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.delenv(ADAPTER_MODE_ENV, raising=False)
    assert isinstance(get_partner_adapter(), MockPartnerAdapter)


def test_factory_explicit_mock_arg():
    assert isinstance(get_partner_adapter("mock"), MockPartnerAdapter)


def test_factory_reads_env(monkeypatch):
    monkeypatch.setenv(ADAPTER_MODE_ENV, "mock")
    assert isinstance(get_partner_adapter(), MockPartnerAdapter)


def test_factory_live_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        get_partner_adapter("live")


def test_factory_unknown_mode_raises():
    with pytest.raises(ValueError):
        get_partner_adapter("banana")
