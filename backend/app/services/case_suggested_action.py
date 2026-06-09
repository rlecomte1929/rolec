"""AIQ-378c (AIQ-818) — Suggested-action / auto-draft reminder (deterministic MVP).

Turns a case-delay signal (from AIQ-378a ``scan_active_cases``) into a useful HR
nudge: a per-stage **suggested action** and a **templated draft reminder** string,
attached to the case-health alert payload (AIQ-378b).

MVP is fully deterministic — a per-stage template keyed on
``immigration_milestones.milestone_type`` (mirrors
``immigration_partner_adapter.MilestoneType``). **Drafts only from the real signal
fields** (case_id, stage, days_behind, expected_date); it never fabricates case
facts, names, or dates.

ENHANCEMENT (separate, OFF the critical path — not built here): an LLM-drafted
reminder via the Claude API, and — only once the feature shape is verified against
current Anthropic docs — a Managed-Agents / "Dreaming" delivery. Per the design
(§5.2) that path must be flag-gated OFF by default and unit-tested with a mocked
client; it is intentionally left as a seam (see ``build_suggested_action``'s
``use_llm`` note) rather than shipped with an unverified SDK.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

# Per-stage HR-facing suggested action. Keyed on milestone_type. Keep these as
# concrete, do-able next steps — not restatements of "this is late".
_STAGE_ACTIONS: Dict[str, str] = {
    "preflight_check": "Complete the pre-flight eligibility check so the application can start.",
    "dossier_assembly": "Chase the employee for the outstanding dossier documents.",
    "criminal_record_ordered": "Confirm the criminal-record certificate was ordered and track its arrival.",
    "application_filed": "Confirm the application was filed with the authority and capture the receipt.",
    "biometric_appointment": "Book or confirm the biometric appointment slot.",
    "visa_decision": "Follow up with the authority or partner on the pending visa decision.",
    "visa_issued": "Confirm the visa has been issued and collected.",
    "arrival": "Confirm the employee's arrival and start the local onboarding steps.",
    "local_registration": "Confirm local / residence registration is booked or completed.",
    "work_permit_issued": "Confirm the work permit has been issued.",
    "permit_renewal_reminder": "Start the permit-renewal process before the current permit lapses.",
}

_FALLBACK_ACTION = "Review this case and follow up on the overdue step."


def _humanize_stage(stage: str) -> str:
    """'dossier_assembly' -> 'Dossier assembly' (display label only)."""
    return (stage or "").replace("_", " ").strip().capitalize() or "this step"


def suggested_action_for_stage(stage: str) -> str:
    """The deterministic per-stage suggested action (fallback for unknown stages)."""
    return _STAGE_ACTIONS.get((stage or "").strip().lower(), _FALLBACK_ACTION)


def build_suggested_action(signal: Mapping[str, Any]) -> Dict[str, str]:
    """Return ``{suggested_action, draft_reminder}`` for one delay signal.

    ``signal`` is one ``scan_active_cases`` row: case_id, stage, days_behind,
    expected_date. Output is deterministic and uses only those real fields.

    (Enhancement seam: a future flag-gated ``use_llm`` path would replace
    ``draft_reminder`` with a Claude-drafted message built from the SAME fields —
    never fabricated — and is intentionally not implemented here.)
    """
    stage = str(signal.get("stage") or "")
    case_id = str(signal.get("case_id") or "")
    days_behind = signal.get("days_behind")
    expected_date = signal.get("expected_date")

    action = suggested_action_for_stage(stage)
    stage_label = _humanize_stage(stage)

    days_part = (
        f"{days_behind} day(s) past its target date" if days_behind is not None else "past its target date"
    )
    date_part = f" ({expected_date})" if expected_date else ""
    case_part = f"case {case_id}" if case_id else "this case"

    draft_reminder = (
        f"Quick check-in on {case_part}: the '{stage_label}' step is {days_part}{date_part}. "
        f"{action} Please reply if anything is blocking you."
    )

    return {"suggested_action": action, "draft_reminder": draft_reminder}
