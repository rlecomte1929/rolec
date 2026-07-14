from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Tuple, Optional

from .nationality_class import EU_EEA, OWN_NATIONAL, THIRD_COUNTRY, classify


def apply_rules(case_draft: Dict[str, Any], base_requirements: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, Any]]:
    required_fields: List[str] = []
    expanded = list(base_requirements)
    flags: Dict[str, Any] = {}

    basics = case_draft.get("relocationBasics", {})
    family = case_draft.get("familyMembers", {})
    assignment = case_draft.get("assignmentContext", {})
    profile = case_draft.get("employeeProfile", {})

    purpose = basics.get("purpose")
    has_dependents = basics.get("hasDependents")
    # AIQ-1349 Phase 2: short-term assignments (STA, typically <12 months) don't
    # trigger the long-term, family-settling requirements — a spouse rarely seeks
    # local work authorization and children aren't enrolled in a local school for
    # a brief posting. Suppress those two so STA gets a lighter requirement set.
    # (LTA/PERMANENT keep the full set.)
    case_assignment_type = str(assignment.get("assignmentType") or "").strip().upper() or None
    is_sta = case_assignment_type == "STA"

    if basics.get("targetMoveDate") and profile.get("passportExpiry"):
        try:
            target = date.fromisoformat(str(basics["targetMoveDate"]))
            expiry = date.fromisoformat(str(profile["passportExpiry"]))
            if expiry <= target:
                expanded.append(_requirement(
                    "Passport expiry must be after target move date",
                    "IDENTITY",
                    "WARN",
                    "EMPLOYEE",
                    ["employeeProfile.passportExpiry"],
                ))
        except Exception:
            pass

    if has_dependents:
        required_fields += ["familyMembers.spouse.fullName", "familyMembers.children"]
        flags["hasDependents"] = True

    spouse = (family.get("spouse") or {})
    if spouse and spouse.get("wantsToWork"):
        if is_sta:
            flags.setdefault("staWaived", []).append("Dependent work authorization rules")
        else:
            expanded.append(_requirement(
                "Dependent work authorization rules",
                "DEPENDENTS",
                "WARN",
                "HR",
                ["familyMembers.spouse"],
            ))
            flags["spouseWork"] = True

    children = family.get("children") or []
    if children:
        flags["kids"] = True
        for child in children:
            if _child_age(child.get("dateOfBirth")) in range(5, 17):
                if is_sta:
                    flags.setdefault("staWaived", []).append("School enrollment documents")
                else:
                    expanded.append(_requirement(
                        "School enrollment documents",
                        "DEPENDENTS",
                        "WARN",
                        "HR",
                        ["familyMembers.children"],
                    ))
                    flags["kidsSchoolAge"] = True
                break

    if purpose == "employment":
        required_fields += [
            "assignmentContext.employerName",
            "assignmentContext.jobTitle",
            "assignmentContext.contractStartDate",
        ]

    # AIQ-1349: data-driven applicability. A requirement may declare
    # appliesToAssignmentTypes (a list, e.g. ["LTA","PERMANENT"]); drop it for a
    # case whose assignment_type isn't listed. None/empty ⇒ applies to all. Only
    # filters when the case has a known assignment_type (legacy cases keep all).
    if case_assignment_type:
        dropped = [r for r in expanded if not _applies_to_assignment_type(r, case_assignment_type)]
        if dropped:
            expanded = [r for r in expanded if _applies_to_assignment_type(r, case_assignment_type)]
            flags.setdefault("staWaived", []).extend(
                r.get("title") for r in dropped if r.get("title")
            )

    # Nationality gating. The FRANCE catalog is the non-EEA salaried route (its
    # own seed says "EEA/EU nationals have free movement and need none of this"),
    # but nothing enforced that, so a French citizen relocating home was served
    # the full French work-visa track. Drop requirements that don't apply to the
    # case's nationality class — and, critically, STATE the resulting "nothing
    # required" rather than leaving an empty pillar (see _immigration_confirmation).
    nationality_class = classify(profile.get("nationality"), basics.get("destCountry"))

    # An unknown nationality must still be FILTERED, and this is subtle enough to
    # be worth spelling out.
    #
    # "Unknown => don't filter" was safe while a catalog was a single track: not
    # filtering just kept the full list. It is NOT safe now that a catalog carries
    # two mutually exclusive tracks (the third-country visa file and the EU/EEA
    # establishment steps), because "don't filter" then means "serve BOTH" — and
    # the EU track asserts, in its own copy, that no visa is involved. An Indian
    # national with an unrecognised nationality string would read "As an EU/EEA
    # national you may enter and reside in France ... no visa is involved." That
    # is the fabricated free movement this module exists to prevent, arrived at
    # from the opposite direction.
    #
    # So when we don't know: filter as THIRD_COUNTRY — the most demanding track,
    # which can only ever OVER-show — but make no claim. No confirmation, no
    # waived list, no nationalityClass. Over-showing a visa step to an EU citizen
    # is a bad experience; telling a third-country national they need no visa is
    # a harm. We take the first every time.
    effective_class = nationality_class or THIRD_COUNTRY

    dropped = [r for r in expanded if not _applies_to_nationality_class(r, effective_class)]
    if dropped:
        expanded = [r for r in expanded if _applies_to_nationality_class(r, effective_class)]

        # Only record and only speak when we actually resolved the nationality.
        if nationality_class:
            flags["nationalityWaived"] = [r.get("title") for r in dropped if r.get("title")]
            flags["nationalityClass"] = nationality_class
            confirmation = _immigration_confirmation(
                nationality_class, basics.get("destCountry")
            )
            if confirmation is not None:
                expanded.append(confirmation)

    return required_fields, expanded, flags


def _applies_to_nationality_class(requirement: Dict[str, Any], nationality_class: str) -> bool:
    """True when the requirement applies to the case's nationality class. A
    requirement with no ``appliesToNationalityClasses`` (None/empty) applies to
    all — same null-means-universal contract as appliesToAssignmentTypes."""
    allowed = requirement.get("appliesToNationalityClasses")
    if not allowed:
        return True
    norm = {str(a).strip().upper() for a in allowed if str(a).strip()}
    return (not norm) or (nationality_class in norm)


def _immigration_confirmation(
    nationality_class: str, dest_country: Optional[str]
) -> Optional[Dict[str, Any]]:
    """The anti-silence gate (ReloPass_Fixture_NO-FR.md §3.1).

    Suppressing the visa track leaves the immigration pillar empty, and an empty
    pillar reads as a broken screen — or worse, as "we didn't check". A correct
    answer of "none" must be *stated*, with its reason, not implied by omission.
    So we emit a positive confirmation in place of what we removed.

    Returns None when we have no right-to-enter claim to make. `classify` has
    three outcomes but only two of them confer free movement, and this function
    is called whenever *anything* was dropped — so an unguarded `else` would tell
    a third-country national "freedom of movement applies, no visa required" the
    moment any EU-scoped item was dropped from their list. That is the fabricated
    "nothing required" nationality_class.py's docstring calls the failure mode we
    must never have. Silence is wrong, but a confident lie is far worse: say
    nothing rather than invent a right the person does not have.
    """
    where = (dest_country or "the destination").title()
    if nationality_class == OWN_NATIONAL:
        reason = (
            f"You are a national of {where}. You have the right of entry and residence in "
            "your own country — no visa, residence permit, or immigration registration applies."
        )
    elif nationality_class == EU_EEA:
        reason = (
            f"You are an EU/EEA national moving to {where}. Freedom of movement applies — "
            "no visa or work permit is required."
        )
    else:
        return None
    return {
        "id": "immigration_nothing_to_do",
        "title": "No visa or residence permit required",
        "pillar": "RESIDENCE",
        "description": reason,
        "severity": "INFO",
        "owner": "EMPLOYEE",
        "requiredFields": [],
        "outcomeType": "nothing_to_do",
        "reason": reason,
    }


def _applies_to_assignment_type(requirement: Dict[str, Any], case_assignment_type: str) -> bool:
    """True when the requirement applies to the case's assignment type. A
    requirement with no ``appliesToAssignmentTypes`` (None/empty) applies to all."""
    allowed = requirement.get("appliesToAssignmentTypes")
    if not allowed:
        return True
    norm = {str(a).strip().upper() for a in allowed if str(a).strip()}
    return (not norm) or (case_assignment_type in norm)


def _child_age(date_str: Optional[str]) -> int:
    if not date_str:
        return 0
    try:
        dob = date.fromisoformat(str(date_str))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 0


def _requirement(title: str, pillar: str, severity: str, owner: str, required_fields: List[str]) -> Dict[str, Any]:
    return {
        "title": title,
        "pillar": pillar,
        "description": "System-generated requirement based on case context.",
        "severity": severity,
        "owner": owner,
        "requiredFields": required_fields,
    }
