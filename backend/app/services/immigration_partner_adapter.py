"""
Immigration partner integration — backend contract only (AIQ-379b).

Defines the partner-AGNOSTIC tool/adapter surface that any immigration law-firm
integration must implement, so a Claude agent (via MCP Tunnel) or a scheduled
sync can pull real-time permit status into a ReloPass case.

The vocabulary here maps 1:1 onto ``public.immigration_milestones``
(``supabase/migrations/20260518120000_immigration_core_tables.sql`` §4) so the
sync service (AIQ-379d) is a pure translation, not a remapping layer.

See ``docs/design/aiq-379-mcp-tunnel-partner-api.md`` §2 for the tool surface
and the rationale (Topology B: ReloPass hosts the MCP server wrapping this
adapter; only concrete adapters know about a specific partner).

No partner-specific logic lives here. Concrete partners subclass
``PartnerAdapter`` — ``MockPartnerAdapter`` (AIQ-379c) and ``LivePartnerAdapter``
(AIQ-379e). ``extra="forbid"`` keeps the wire contract tight so a partner cannot
smuggle un-modelled fields past the boundary.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Canonical vocabularies — mirror immigration_milestones exactly
# ---------------------------------------------------------------------------


class MilestoneType(str, Enum):
    """Application lifecycle stages — mirrors ``immigration_milestones.milestone_type``."""

    PREFLIGHT_CHECK = "preflight_check"
    DOSSIER_ASSEMBLY = "dossier_assembly"
    CRIMINAL_RECORD_ORDERED = "criminal_record_ordered"
    APPLICATION_FILED = "application_filed"
    BIOMETRIC_APPOINTMENT = "biometric_appointment"
    VISA_DECISION = "visa_decision"
    VISA_ISSUED = "visa_issued"
    ARRIVAL = "arrival"
    LOCAL_REGISTRATION = "local_registration"
    WORK_PERMIT_ISSUED = "work_permit_issued"
    PERMIT_RENEWAL_REMINDER = "permit_renewal_reminder"


class MilestoneStatus(str, Enum):
    """Per-milestone status — mirrors ``immigration_milestones.status``."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Wire models — one PartnerMilestone == one immigration_milestones row
# ---------------------------------------------------------------------------


class PartnerMilestone(BaseModel):
    """One lifecycle milestone as reported by a partner.

    Every field maps to a column on ``immigration_milestones``. ReloPass-derived
    columns (``book_early_alert``, ``org_id``, ``id``, timestamps) are deliberately
    NOT modelled here — they are set ReloPass-side by the sync service (AIQ-379d),
    not supplied by the partner.
    """

    model_config = ConfigDict(extra="forbid")

    milestone_type: MilestoneType
    status: MilestoneStatus = MilestoneStatus.PENDING
    target_date: Optional[date] = None
    completed_date: Optional[date] = None
    notes: Optional[str] = None
    evidence_url: Optional[str] = None
    sort_order: int = 0


class CaseStatus(BaseModel):
    """Full status snapshot for one immigration case, as returned by a ``PartnerAdapter``."""

    model_config = ConfigDict(extra="forbid")

    partner_ref: str = Field(..., description="The partner's own case identifier.")
    stage: MilestoneType = Field(
        ..., description="Current lifecycle stage (the most-advanced active milestone_type)."
    )
    updated_at: datetime = Field(..., description="When the partner last updated this case.")
    milestones: List[PartnerMilestone] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# The adapter interface every partner integration implements
# ---------------------------------------------------------------------------


class PartnerAdapter(ABC):
    """Partner-agnostic interface every immigration-partner integration implements.

    Concrete adapters (``MockPartnerAdapter`` — AIQ-379c; ``LivePartnerAdapter`` —
    AIQ-379e) translate a specific partner API into this canonical surface. No
    partner name, credential detail, or transport assumption belongs in this base
    class — that all lives in the concrete subclass.
    """

    @abstractmethod
    def get_case_status(self, partner_ref: str) -> CaseStatus:
        """Return the full current status snapshot for a partner case."""
        raise NotImplementedError

    @abstractmethod
    def list_milestones(self, partner_ref: str) -> List[PartnerMilestone]:
        """Return just the milestone list for a partner case."""
        raise NotImplementedError

    @abstractmethod
    def get_milestone_evidence(
        self, partner_ref: str, milestone_type: MilestoneType
    ) -> Optional[str]:
        """Return an evidence URL (e.g. a visa scan) for a milestone, or ``None``."""
        raise NotImplementedError


def case_status_json_schema() -> dict:
    """Canonical JSON Schema for the ``CaseStatus`` contract.

    Useful for documentation and for any cross-language partner that consumes the
    schema directly rather than the Python models.
    """
    return CaseStatus.model_json_schema()
