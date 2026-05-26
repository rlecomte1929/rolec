"""
wizard_draft_mapper.py — Map wizard Case draft JSON to flat profile dicts.

Pure Python, no FastAPI / DB imports. Safe to call from tests and from
any service layer without pulling in the HTTP stack.

Touch policy: NEW FILE. Does not modify any existing module directly.

Usage:
    from backend.app.services.wizard_draft_mapper import extract_profile_from_wizard_draft

    profile = extract_profile_from_wizard_draft(draft_json_dict)
    # → {"origin_country": "France", "destination_country": "Spain",
    #    "contract_type": "lta", "family": {"hasSpouse": True, "childCount": 2}, ...}
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def extract_profile_from_wizard_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map wizard Case draft JSON into the flat profile shape expected by
    ``relocation_profile.compute_missing_fields``, ``compute_case_classification``,
    and ``compute_default_milestones``.

    Reads from two draft section hierarchies:
      • Wizard UI sections: relocationBasics, assignmentContext, familyMembers
      • Orchestrator answer map: assignment.*, family.*  (mapsTo dot-paths)

    All fields are optional — passing an incomplete draft is safe.

    S3/S4 additions (new in this module; backward-compatible):
      - contract_type  — from assignment.contractType → assignmentContext.contractType
      - family         — dict with hasSpouse, childCount, partnerVisaStatus,
                         spouseEmploymentIntent (from family.* or familyMembers.*)

    P4/P5 additions (backward-compatible):
      - employment_tenure_months        — assignment.employmentTenureMonths (int)
      - us_entity_confirmed             — assignment.usEntityConfirmed (bool)
      - specialized_knowledge_documented— assignment.specializedKnowledgeDocumented (bool)
      - japan_visa_category             — assignment.japanVisaCategory (str, "unknown" omitted)
      - estimated_package_cost_usd      — assignment.estimatedPackageCostBand → midpoint (float)
      - uk_sponsor_licence_confirmed    — assignment.ukSponsorLicenceConfirmed (bool)
      - uk_points_threshold_confirmed   — assignment.ukPointsThresholdConfirmed (bool)
    """
    if not draft or not isinstance(draft, dict):
        return {}

    basics = draft.get("relocationBasics") or {}
    ac = draft.get("assignmentContext") or {}
    out: Dict[str, Any] = {}

    # ── geography ────────────────────────────────────────────────────────────
    oc = basics.get("originCountry") or basics.get("origin_country")
    dc = (
        basics.get("destCountry")
        or basics.get("destination_country")
        or basics.get("hostCountry")
        or basics.get("host_country")
    )
    if oc:
        out["origin_country"] = oc
    if dc:
        out["destination_country"] = dc

    # ── dates ────────────────────────────────────────────────────────────────
    md = basics.get("targetMoveDate") or basics.get("move_date")
    if md:
        out["move_date"] = md

    # ── employment / assignment ───────────────────────────────────────────────
    et = basics.get("employmentType") or basics.get("employment_type")
    if et:
        out["employment_type"] = et
    ec = ac.get("employerCountry") or ac.get("employer_country") or basics.get("employerCountry")
    if ec:
        out["employer_country"] = ec
    if basics.get("worksRemote") is not None:
        out["works_remote"] = basics.get("worksRemote")
    if basics.get("hasCorporateTaxSupport") is not None:
        out["has_corporate_tax_support"] = basics.get("hasCorporateTaxSupport")

    # ── P2: nationality (employee) ────────────────────────────────────────────
    # Orchestrator path: draft.primaryApplicant.nationality
    # Wizard path: draft.employeeProfile.nationality
    ep = draft.get("employeeProfile") or {}
    pa = draft.get("primaryApplicant") or {}
    nat = (
        pa.get("nationality")
        or ep.get("nationality")
        or ep.get("nationalityCountry")
        or basics.get("nationality")
        or None
    )
    if nat:
        out["nationality"] = nat

    # ── S3: contract_type ─────────────────────────────────────────────────────
    # Priority: orchestrator path (draft.assignment.*) > wizard (assignmentContext.*) > basics.*
    assignment_section = draft.get("assignment") or {}
    ct = (
        assignment_section.get("contractType")
        or ac.get("contractType")
        or ac.get("contract_type")
        or basics.get("contractType")
        or basics.get("contract_type")
    )
    if ct:
        out["contract_type"] = ct

    # ── P4: immigration exception fields ─────────────────────────────────────
    # Orchestrator writes these under draft.assignment.* (mapsTo paths).
    # All are optional — missing values are safe (exception checks skip None).

    # employment_tenure_months: coerce string option value to int
    raw_tenure = assignment_section.get("employmentTenureMonths")
    tenure_months = _int_or_none(raw_tenure)
    if tenure_months is not None:
        out["employment_tenure_months"] = tenure_months

    # us_entity_confirmed: bool — True/False/None
    raw_us_entity = assignment_section.get("usEntityConfirmed")
    us_entity = _bool(raw_us_entity)
    if us_entity is not None:
        out["us_entity_confirmed"] = us_entity

    # specialized_knowledge_documented: bool — True/False/None
    raw_sk = assignment_section.get("specializedKnowledgeDocumented")
    sk = _bool(raw_sk)
    if sk is not None:
        out["specialized_knowledge_documented"] = sk

    # japan_visa_category: string — "eshs", "ict", "specified_skilled", "unknown"
    # Treat "unknown" as absent so the exception service flags ambiguity correctly.
    raw_jvc = (assignment_section.get("japanVisaCategory") or "").strip().lower()
    if raw_jvc and raw_jvc != "unknown":
        out["japan_visa_category"] = raw_jvc

    # estimated_package_cost_usd: convert cost band to numeric midpoint (USD).
    # Band values from q_estimated_package_cost options in question_bank.py.
    raw_cost_band = (assignment_section.get("estimatedPackageCostBand") or "").strip().lower()
    _COST_BAND_MIDPOINTS: Dict[str, float] = {
        "under_50k":  25_000.0,
        "50k_100k":   75_000.0,
        "100k_150k": 125_000.0,
        "150k_200k": 175_000.0,
        "over_200k": 225_000.0,
    }
    if raw_cost_band in _COST_BAND_MIDPOINTS:
        out["estimated_package_cost_usd"] = _COST_BAND_MIDPOINTS[raw_cost_band]
    elif raw_cost_band:
        # Fallback: try direct numeric parse (e.g. HR entered a raw dollar amount)
        try:
            out["estimated_package_cost_usd"] = float(
                raw_cost_band.replace("$", "").replace(",", "").strip()
            )
        except (TypeError, ValueError):
            pass

    # ── P5: UK Skilled Worker fields ─────────────────────────────────────────
    # Orchestrator writes these under draft.assignment.* (mapsTo paths).
    # Both are bool — None means not yet answered (treated as "not confirmed"
    # by _check_uk_skilled_worker which fires a warning/blocker for None).

    # uk_sponsor_licence_confirmed: bool — True/False/None
    raw_uksl = assignment_section.get("ukSponsorLicenceConfirmed")
    uksl = _bool(raw_uksl)
    if uksl is not None:
        out["uk_sponsor_licence_confirmed"] = uksl

    # uk_points_threshold_confirmed: bool — True/False/None
    raw_ukpt = assignment_section.get("ukPointsThresholdConfirmed")
    ukpt = _bool(raw_ukpt)
    if ukpt is not None:
        out["uk_points_threshold_confirmed"] = ukpt

    # ── S4: family profile ────────────────────────────────────────────────────
    # Orchestrator path: draft.family.* (mapsTo = "family.<field>")
    # Wizard path: draft.familyMembers.*
    fam_orch = draft.get("family") or {}
    fm_wiz = draft.get("familyMembers") or {}

    has_spouse = _bool(fam_orch.get("hasSpouse"))
    if has_spouse is None:
        # Wizard fallback: infer from maritalStatus
        ms = (fm_wiz.get("maritalStatus") or "").lower()
        if ms in ("married", "partnered", "civil_union"):
            has_spouse = True
        elif ms in ("single", "divorced", "widowed"):
            has_spouse = False

    child_count = _int_or_none(fam_orch.get("childCount"))
    if child_count is None:
        # Wizard fallback: count children list length
        children = fm_wiz.get("children")
        if isinstance(children, list):
            child_count = len(children)

    partner_visa_status = fam_orch.get("partnerVisaStatus") or None
    spouse_employment_intent = fam_orch.get("spouseEmploymentIntent") or None

    family_out: Dict[str, Any] = {}
    if has_spouse is not None:
        family_out["hasSpouse"] = has_spouse
    if child_count is not None:
        family_out["childCount"] = child_count
    if partner_visa_status:
        family_out["partnerVisaStatus"] = partner_visa_status
    if spouse_employment_intent:
        family_out["spouseEmploymentIntent"] = spouse_employment_intent
    if family_out:
        out["family"] = family_out

    return out


# ── Coerce helpers (module-private) ──────────────────────────────────────────

def _bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if str(v).lower() in ("true", "yes", "1"):
        return True
    if str(v).lower() in ("false", "no", "0"):
        return False
    return None


def _int_or_none(v: Any) -> Optional[int]:
    try:
        return int(str(v).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
