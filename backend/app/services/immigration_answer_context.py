"""
Anonymised applicant context for the grounded immigration answer (Slice 3).

Builds a short, ANONYMISED summary of the applicant's situation — currently the
family signal (spouse + dependent count), which drives conditional/family-
reunification requirements — so the answer engine can tailor WHICH of the grounded
sources matter. Counts + booleans only (never names/DOB/passport); passed through
mask_pii as defense-in-depth per the GDPR data-minimisation rule. Returns None when
there is no useful signal (the engine then behaves exactly as before).

Fast-follow: assignment_type (STA/LTA/PERMANENT) once case-model resolution is
reliable — it changes the permit path and is high-value tailoring context.
"""
from typing import Optional

from .immigration_service import _load_profile_for_case
from .pii_masker import mask_pii


def build_applicant_context(case_id: str) -> Optional[str]:
    profile = _load_profile_for_case(case_id)
    if not profile:
        return None

    deps = profile.get("dependents") or []
    dependents_count = len(deps) if isinstance(deps, list) else 0
    has_spouse = bool(profile.get("spouse_nationality"))

    if has_spouse and dependents_count:
        summary = f"Relocating with a spouse and {dependents_count} dependent(s)"
    elif has_spouse:
        summary = "Relocating with a spouse"
    elif dependents_count:
        summary = f"Relocating with {dependents_count} dependent(s)"
    else:
        return None

    # Defense-in-depth: the summary is anonymised by construction, but the hard
    # rule is that anything reaching an LLM prompt passes through mask_pii first.
    return mask_pii(summary)
