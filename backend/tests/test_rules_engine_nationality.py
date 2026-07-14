"""rules_engine nationality gating + the anti-silence gate.

ReloPass_Fixture_NO-FR.md §3.1 (Honesty assertion): immigration for a French
national returning to France MUST be an explicit, stated `nothing_to_do` WITH a
reason. "Test FAILS if immigration is absent, null, or silent — a correct answer
of 'none' must be *stated*, not implied by omission."

So there are two failure modes to guard, not one:
  1. Serving the visa track to an EEA national (wrong content).
  2. Serving an empty list (silence reads as a broken screen / nothing required).
"""
from __future__ import annotations

from backend.app.services.rules_engine import apply_rules

# The real shape of the FRANCE catalog: the non-EEA salaried route.
FRANCE_ITEMS = [
    {
        "id": "visa",
        "title": "Long-stay work visa (VLS-TS Salarié / Passeport Talent)",
        "pillar": "RESIDENCE",
        "severity": "BLOCKER",
        "owner": "EMPLOYEE",
        "requiredFields": [],
        "appliesToNationalityClasses": ["THIRD_COUNTRY"],
    },
    {
        "id": "anef",
        "title": "ANEF VLS-TS validation (within 90 days of arrival)",
        "pillar": "RESIDENCE",
        "severity": "BLOCKER",
        "owner": "EMPLOYEE",
        "requiredFields": [],
        "appliesToNationalityClasses": ["THIRD_COUNTRY"],
    },
    {
        "id": "dgef",
        "title": "DGEF work authorization (employer-initiated)",
        "pillar": "EMPLOYMENT",
        "severity": "WARN",
        "owner": "HR",
        "requiredFields": [],
        "appliesToNationalityClasses": ["THIRD_COUNTRY"],
    },
    {
        "id": "passport",
        "title": "Valid passport",
        "pillar": "IDENTITY",
        "severity": "BLOCKER",
        "owner": "EMPLOYEE",
        "requiredFields": [],
        "appliesToNationalityClasses": None,  # applies to everyone
    },
]


def _draft(nationality, dest="FRANCE"):
    return {
        "relocationBasics": {"destCountry": dest, "purpose": "employment"},
        "employeeProfile": {"nationality": nationality},
    }


def _titles(items):
    return [i["title"] for i in items]


def _action_titles(items):
    """Titles of ACTIONABLE requirements only. The `nothing_to_do` confirmation
    legitimately says the word "visa" (in a sentence that negates it), so an
    honest check asks whether anything is being *demanded* of the employee."""
    return [i["title"] for i in items if i.get("outcomeType") != "nothing_to_do"]


class TestFrenchNationalReturningHome:
    def test_no_visa_requirements_are_served(self):
        _, expanded, _ = apply_rules(_draft("FR"), FRANCE_ITEMS)
        titles = _action_titles(expanded)
        assert not any("visa" in t.lower() for t in titles)
        assert not any("ANEF" in t for t in titles)
        assert not any("DGEF" in t for t in titles)

    def test_universal_items_survive(self):
        _, expanded, _ = apply_rules(_draft("FR"), FRANCE_ITEMS)
        assert "Valid passport" in _titles(expanded)

    def test_immigration_is_STATED_not_silent(self):
        """The anti-silence gate. A correct answer of 'none' must be stated."""
        _, expanded, _ = apply_rules(_draft("FR"), FRANCE_ITEMS)
        confirmations = [i for i in expanded if i.get("outcomeType") == "nothing_to_do"]
        assert len(confirmations) == 1, "immigration must resolve to exactly one stated confirmation"
        item = confirmations[0]
        assert item.get("reason"), "the confirmation MUST carry a populated reason"
        assert item["pillar"] == "RESIDENCE"
        assert item["severity"] == "INFO"

    def test_suppressed_titles_are_recorded_not_dropped(self):
        _, _, flags = apply_rules(_draft("FR"), FRANCE_ITEMS)
        waived = flags.get("nationalityWaived") or []
        assert "Long-stay work visa (VLS-TS Salarié / Passeport Talent)" in waived
        assert "DGEF work authorization (employer-initiated)" in waived


class TestEeaNationalNotOwnNational:
    def test_norwegian_to_france_also_skips_the_visa_track(self):
        # Norway is EEA-but-not-EU — free movement still applies.
        _, expanded, _ = apply_rules(_draft("NO"), FRANCE_ITEMS)
        assert not any("visa" in t.lower() for t in _action_titles(expanded))
        assert any(i.get("outcomeType") == "nothing_to_do" for i in expanded)


class TestThirdCountryNationalRegression:
    """The visa track must still work. This is the regression guard."""

    def test_indian_national_gets_the_full_visa_set(self):
        _, expanded, flags = apply_rules(_draft("IN"), FRANCE_ITEMS)
        titles = _titles(expanded)
        assert "Long-stay work visa (VLS-TS Salarié / Passeport Talent)" in titles
        assert "ANEF VLS-TS validation (within 90 days of arrival)" in titles
        assert "DGEF work authorization (employer-initiated)" in titles
        assert "Valid passport" in titles

    def test_no_nothing_to_do_confirmation_for_third_country(self):
        _, expanded, _ = apply_rules(_draft("IN"), FRANCE_ITEMS)
        assert not any(i.get("outcomeType") == "nothing_to_do" for i in expanded)
        _, _, flags = apply_rules(_draft("IN"), FRANCE_ITEMS)
        assert not flags.get("nationalityWaived")


class TestUnknownNationalityChangesNothing:
    """We only suppress when we positively know. Unknown ⇒ status quo, and
    crucially ⇒ no fabricated 'nothing required'."""

    def test_missing_nationality_keeps_full_list(self):
        _, expanded, flags = apply_rules(_draft(None), FRANCE_ITEMS)
        assert len(_titles(expanded)) == len(FRANCE_ITEMS)
        assert not flags.get("nationalityWaived")

    def test_missing_nationality_makes_no_confirmation_claim(self):
        _, expanded, _ = apply_rules(_draft(None), FRANCE_ITEMS)
        assert not any(i.get("outcomeType") == "nothing_to_do" for i in expanded)
