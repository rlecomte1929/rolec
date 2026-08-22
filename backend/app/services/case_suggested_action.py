"""AIQ-378c (AIQ-818) — Suggested-action / auto-draft reminder (deterministic MVP).

Turns a case-delay signal (from AIQ-378a ``scan_active_cases``) into a useful HR
nudge: a per-stage **suggested action** and a **templated draft reminder** string,
attached to the case-health alert payload (AIQ-378b).

Fully deterministic — a per-stage template keyed on ``milestone_type``, covering
both the live ``case_milestones`` vocabulary (`task_*` / `service_*`) and the
``immigration_partner_adapter`` one. **Drafts only from real signal fields**
(case_id, stage, title, owner, days_behind, expected_date); it never fabricates
case facts, names, or dates. An unrecognised stage falls back to the milestone's
own curated title rather than to an invented instruction (AIQ-2041).

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
    # ── case_milestones vocabulary (AIQ-2041) ────────────────────────────────
    # The live table uses `task_*` / `service_*` keys, not the immigration
    # partner-adapter vocabulary below. Each milestone carries a curated `title`,
    # but titles are written for the EMPLOYEE ("Upload passport copy"); HR needs
    # the corresponding HR move ("Chase the employee for..."). These supply that.
    # Only keys whose meaning is unambiguous from the name are templated — the
    # opaque codes (`pre_departure_ai_01`, `post_arrival_corridor_07`, ~90 of them)
    # deliberately fall through to the milestone's real title rather than to an
    # invented sentence.
    "task_profile_core": "Chase the employee to confirm their core profile details.",
    "task_passport_upload": "Chase the employee for a passport copy.",
    "task_employment_letter": "Chase the employment / assignment letter.",
    "task_family_dependents": "Chase the employee to confirm family and dependant details.",
    "task_hr_case_review": "Review this case yourself — it is waiting on HR.",
    "task_route_verify": "Verify the destination route on this case.",
    "task_immigration_review": "Schedule the immigration review for this case.",
    "task_visa_docs_prep": "Check the visa / work-permit application pack is being assembled.",
    "task_visa_submit": "Confirm the visa / work-permit application was submitted.",
    "task_biometrics": "Check whether a biometrics appointment is needed and booked.",
    "task_eu_registration": "Confirm the employee registered as an EU/EEA resident locally.",
    "task_arrival_registration": "Confirm arrival registration is done.",
    "task_tax_local_registration": "Confirm tax / local registration is done.",
    "task_temp_housing": "Check temporary housing is arranged.",
    "task_movers_shipment": "Check the movers / shipment booking is progressing.",
    "task_travel_plan": "Check travel is planned and booked.",
    "task_settling_in": "Follow up on the post-arrival settling-in steps.",
    "service_movers_quote": "Chase the moving quotes so the employee can compare.",
    "service_movers_book_mover": "Confirm a mover has been booked.",
    "service_movers_pack_ship": "Confirm packing / shipping is scheduled.",
    "service_housing_criteria": "Chase the employee for their housing search criteria.",
    "service_housing_quote": "Chase the housing quotes.",
    "service_housing_viewings": "Check viewings are being arranged.",
    "service_housing_sign_lease": "Confirm the lease has been signed.",
    "service_schools_shortlist": "Chase the school shortlist.",
    "service_schools_contact_admissions": "Check admissions have been contacted.",
    "service_schools_submit_applications": "Confirm school applications were submitted.",
    "service_schools_confirm_enrolment": "Confirm school enrolment.",
    "service_banking_appt": "Check the account-opening appointment is booked.",
    "service_banking_open_account": "Confirm the local bank account is open.",

    # ── immigration_partner_adapter vocabulary (AIQ-378c) ────────────────────
    # Retained: this service is also reachable from the partner-sync path.
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


def suggested_action_for_stage(stage: str, title: str = "", owner: str = "") -> str:
    """The deterministic suggested action for one overdue milestone.

    Resolution order, most specific first — every step uses real data, none invents:
      1. an HR-framed template for a milestone_type we recognise;
      2. the milestone's own curated ``title``, framed by ``owner`` — for the ~90
         opaque milestone types ('pre_departure_ai_01') whose meaning cannot be
         read off the key but whose title is specific and human-written;
      3. the generic fallback.
    """
    key = (stage or "").strip().lower()
    templated = _STAGE_ACTIONS.get(key)
    if templated:
        return templated

    clean_title = (title or "").strip()
    if clean_title:
        who = (owner or "").strip().lower()
        if who == "hr":
            return f"Waiting on HR: {clean_title}."
        if who in ("employee", "joint"):
            return f"Chase the employee: {clean_title}."
        return f"Follow up: {clean_title}."

    return _FALLBACK_ACTION


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

    action = suggested_action_for_stage(
        stage, title=str(signal.get("title") or ""), owner=str(signal.get("owner") or "")
    )
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
