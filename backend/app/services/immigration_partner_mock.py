"""
Mock immigration-partner adapter (AIQ-379c).

A zero-dependency, in-memory implementation of the AIQ-379b ``PartnerAdapter``
contract. It lets the whole status-sync flow (AIQ-379d) be developed and tested
with NO real partner and NO MCP Tunnel — the fixtures stand in for a partner API
returning permit-lifecycle status.

Selectable at runtime via ``immigration_partner_factory.get_partner_adapter`` —
this module is never imported by production sync code directly; the factory is.

See ``docs/design/aiq-379-mcp-tunnel-partner-api.md`` §1.1 (Topology B) and §2.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from .immigration_partner_adapter import (
    CaseStatus,
    MilestoneStatus,
    MilestoneType,
    PartnerAdapter,
    PartnerMilestone,
)


def _ms(
    milestone_type: MilestoneType,
    status: MilestoneStatus,
    sort_order: int,
    target_date: Optional[date] = None,
    completed_date: Optional[date] = None,
    notes: Optional[str] = None,
    evidence_url: Optional[str] = None,
) -> PartnerMilestone:
    return PartnerMilestone(
        milestone_type=milestone_type,
        status=status,
        sort_order=sort_order,
        target_date=target_date,
        completed_date=completed_date,
        notes=notes,
        evidence_url=evidence_url,
    )


# ---------------------------------------------------------------------------
# Fixtures — three cases at different points of the permit lifecycle.
# Dates are hard-coded so tests are deterministic.
# ---------------------------------------------------------------------------

_FIXTURES: Dict[str, CaseStatus] = {
    # Early: dossier still being assembled.
    "MOCK-CASE-EARLY": CaseStatus(
        partner_ref="MOCK-CASE-EARLY",
        stage=MilestoneType.DOSSIER_ASSEMBLY,
        updated_at=datetime(2026, 6, 4, 8, 30, tzinfo=timezone.utc),
        milestones=[
            _ms(MilestoneType.PREFLIGHT_CHECK, MilestoneStatus.COMPLETED, 0,
                completed_date=date(2026, 6, 1), notes="Eligibility confirmed"),
            _ms(MilestoneType.DOSSIER_ASSEMBLY, MilestoneStatus.IN_PROGRESS, 1,
                target_date=date(2026, 6, 12), notes="Awaiting criminal-record certificate"),
        ],
    ),
    # In review: filed with the authority, decision pending.
    "MOCK-CASE-REVIEW": CaseStatus(
        partner_ref="MOCK-CASE-REVIEW",
        stage=MilestoneType.VISA_DECISION,
        updated_at=datetime(2026, 6, 5, 9, 12, tzinfo=timezone.utc),
        milestones=[
            _ms(MilestoneType.PREFLIGHT_CHECK, MilestoneStatus.COMPLETED, 0,
                completed_date=date(2026, 5, 10)),
            _ms(MilestoneType.DOSSIER_ASSEMBLY, MilestoneStatus.COMPLETED, 1,
                completed_date=date(2026, 5, 18)),
            _ms(MilestoneType.APPLICATION_FILED, MilestoneStatus.COMPLETED, 2,
                completed_date=date(2026, 5, 22), notes="Filed at Munich Auslanderbehorde"),
            _ms(MilestoneType.BIOMETRIC_APPOINTMENT, MilestoneStatus.COMPLETED, 3,
                completed_date=date(2026, 5, 29)),
            _ms(MilestoneType.VISA_DECISION, MilestoneStatus.IN_PROGRESS, 4,
                target_date=date(2026, 6, 20), notes="Decision pending"),
        ],
    ),
    # Granted: visa issued, with an evidence scan.
    "MOCK-CASE-GRANTED": CaseStatus(
        partner_ref="MOCK-CASE-GRANTED",
        stage=MilestoneType.VISA_ISSUED,
        updated_at=datetime(2026, 6, 3, 14, 0, tzinfo=timezone.utc),
        milestones=[
            _ms(MilestoneType.APPLICATION_FILED, MilestoneStatus.COMPLETED, 0,
                completed_date=date(2026, 4, 14)),
            _ms(MilestoneType.VISA_DECISION, MilestoneStatus.COMPLETED, 1,
                completed_date=date(2026, 5, 30), notes="Approved"),
            _ms(MilestoneType.VISA_ISSUED, MilestoneStatus.COMPLETED, 2,
                completed_date=date(2026, 6, 2),
                evidence_url="https://mock-partner.example/scans/MOCK-CASE-GRANTED/visa.pdf"),
        ],
    ),
}

# Public list of the partner_refs this mock knows about — handy for 379d tests.
MOCK_PARTNER_REFS: List[str] = list(_FIXTURES.keys())


class MockPartnerAdapter(PartnerAdapter):
    """In-memory ``PartnerAdapter`` backed by the fixtures above.

    Deep-copies every returned model so callers can mutate results without
    corrupting the shared fixtures.
    """

    def _case(self, partner_ref: str) -> CaseStatus:
        try:
            return _FIXTURES[partner_ref].model_copy(deep=True)
        except KeyError:
            raise ValueError(f"Unknown partner_ref: {partner_ref!r}") from None

    def get_case_status(self, partner_ref: str) -> CaseStatus:
        return self._case(partner_ref)

    def list_milestones(self, partner_ref: str) -> List[PartnerMilestone]:
        return self._case(partner_ref).milestones

    def get_milestone_evidence(
        self, partner_ref: str, milestone_type: MilestoneType
    ) -> Optional[str]:
        for m in self._case(partner_ref).milestones:
            if m.milestone_type is milestone_type:
                return m.evidence_url
        return None
