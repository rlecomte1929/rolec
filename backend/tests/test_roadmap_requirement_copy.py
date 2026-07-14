"""The roadmap's copy must come from the requirements dossier, and must not drift.

The roadmap told an EU national moving to Germany "Tax ID, social security, or
host-country equivalents" while, for that exact case, requirement_items already knew
it was the Sozialversicherung. This overlays the specific copy onto the generic step.

The map is keyed on requirement TITLE. That is safe — the seeder's natural key is
country_code + purpose + title and there is no delete path, so a changed title orphans
its row and titles are effectively immutable. But a drifted title would silently revert
the roadmap to generic copy, which is exactly the class of silent no-op this codebase
keeps producing. TestTheMapCannotDrift turns it into a loud failure.
"""
from __future__ import annotations

import glob
import os
from types import SimpleNamespace

import pytest

yaml = pytest.importorskip("yaml")

from backend.app.services.roadmap_requirement_copy import (
    _REQUIREMENT_TO_MILESTONE,
    enrich_milestones_with_requirements,
)

_SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seeds", "requirements")


def _seeded_titles():
    """Every (country_code, title) the seeder actually writes — honouring
    purposes_by_country, so a requirement declared for a country that is NOT seeded
    for any purpose does not count."""
    out = set()
    for path in sorted(glob.glob(os.path.join(_SEED_DIR, "*.yaml"))):
        with open(path, "r", encoding="utf-8") as fh:
            seed = yaml.safe_load(fh) or {}
        seeded_countries = {c.upper() for c in (seed.get("purposes_by_country") or {})}
        for req in seed.get("requirements", []) or []:
            for country, spec in (req.get("countries") or {}).items():
                if country.upper() in seeded_countries:
                    out.add((country.upper(), spec["title"]))
    return out


def _item(title, description, pillar="RESIDENCE", outcome="action"):
    return SimpleNamespace(
        title=title, description=description, pillar=pillar, outcomeType=outcome
    )


def _dto(country, items):
    return SimpleNamespace(destCountry=country, requirements=items)


def _milestone(mt, title, description, **kw):
    base = {
        "milestone_type": mt,
        "title": title,
        "description": description,
        "status": "pending",
        "owner": "employee",
        "sort_order": 70,
        "target_date": "2026-12-04",
        "criticality": "normal",
    }
    base.update(kw)
    return base


class TestTheMapCannotDrift:
    """A renamed requirement must fail HERE, not silently revert the roadmap to
    'host-country equivalents' in production."""

    def test_every_mapped_title_is_actually_seeded(self):
        seeded = _seeded_titles()
        missing = sorted(k for k in _REQUIREMENT_TO_MILESTONE if k not in seeded)
        assert missing == [], (
            "these requirement titles are mapped to a roadmap step but no seed file "
            f"produces them — the roadmap would silently stay generic: {missing}"
        )

    def test_every_target_is_a_real_milestone_type(self):
        from backend.relocation_plan_task_library import TASK_BY_MILESTONE_TYPE

        unknown = sorted(
            {v for v in _REQUIREMENT_TO_MILESTONE.values() if v not in TASK_BY_MILESTONE_TYPE}
        )
        assert unknown == [], f"mapped to milestone types that do not exist: {unknown}"


class TestNoTwoRequirementsFightOverAStep:
    """If two requirements for one (country, nationality class) mapped to the same
    milestone, one would silently win. Assert that never happens for real content."""

    def test_no_collision_for_any_seeded_country(self):
        from collections import Counter

        by_country = {}
        for (country, title), target in _REQUIREMENT_TO_MILESTONE.items():
            by_country.setdefault(country, []).append((title, target))

        for country, entries in by_country.items():
            # Requirements are nationality-scoped, so an EU-only and a third-country-only
            # item CAN share a target (they never co-occur). Collisions only matter within
            # one nationality class — approximate that by grouping the titles that could
            # plausibly co-occur: everything except the known EU/TC identity + permit pairs.
            counts = Counter(t for _, t in entries)
            for target, n in counts.items():
                if n > 1 and target not in ("task_passport_upload", "task_employment_letter", "task_visa_submit"):
                    pytest.fail(
                        f"{country}: {n} requirements map to {target} and could co-occur"
                    )


class TestTheCopyBecomesSpecific:
    def test_germany_gets_the_anmeldung_and_the_sozialversicherung(self, monkeypatch):
        import backend.app.services.roadmap_requirement_copy as mod

        dto = _dto("GERMANY", [
            _item("Residence registration (Anmeldung)",
                  "Register your home address at the local Bürgeramt, typically within 14 days."),
            _item("Social security registration (Sozialversicherung)",
                  "The employer typically initiates this and a social security number is issued.",
                  pillar="SOCIAL_SECURITY"),
        ])
        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: dto,
        )

        before = [
            _milestone("task_arrival_registration", "Complete arrival registration",
                       "Local registration or residency steps required shortly after arrival."),
            _milestone("task_tax_local_registration", "Tax / local registration",
                       "Tax ID, social security, or host-country equivalents.", sort_order=75),
            _milestone("task_movers_shipment", "Arrange movers / shipment", "Quotes, inventory.", sort_order=60),
        ]
        after = {m["milestone_type"]: m for m in mod.enrich_milestones_with_requirements("c1", before)}

        assert after["task_arrival_registration"]["title"] == "Residence registration (Anmeldung)"
        assert "Bürgeramt" in after["task_arrival_registration"]["description"]
        assert after["task_tax_local_registration"]["title"] == "Social security registration (Sozialversicherung)"
        # untouched
        assert after["task_movers_shipment"]["title"] == "Arrange movers / shipment"

    def test_only_the_copy_changes(self, monkeypatch):
        import backend.app.services.roadmap_requirement_copy as mod

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: _dto("GERMANY", [
                _item("Residence registration (Anmeldung)", "Bürgeramt, 14 days."),
            ]),
        )
        before = [_milestone("task_arrival_registration", "Complete arrival registration", "generic")]
        after = mod.enrich_milestones_with_requirements("c1", before)[0]

        for field in ("status", "owner", "sort_order", "target_date", "criticality", "milestone_type"):
            assert after[field] == before[0][field], f"{field} must not be touched by a copy overlay"

    def test_a_nothing_to_do_confirmation_never_becomes_a_task(self, monkeypatch):
        """"No visa or residence permit required" is a stated answer, not a step."""
        import backend.app.services.roadmap_requirement_copy as mod

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: _dto("GERMANY", [
                _item("No visa or residence permit required", "Freedom of movement applies.",
                      outcome="nothing_to_do"),
            ]),
        )
        before = [_milestone("task_visa_submit", "Submit visa / work permit application", "generic")]
        after = mod.enrich_milestones_with_requirements("c1", before)[0]
        assert after["title"] == "Submit visa / work permit application"


class TestItFailsOpen:
    def test_a_requirements_failure_returns_the_roadmap_untouched(self, monkeypatch):
        import backend.app.services.roadmap_requirement_copy as mod

        def boom(_cid):
            raise RuntimeError("db down")

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements", boom
        )
        before = [_milestone("task_arrival_registration", "Complete arrival registration", "generic")]
        after = mod.enrich_milestones_with_requirements("c1", before)
        assert after == before, "a generic roadmap beats a 500 — this must fail open"

    def test_an_uncatalogued_country_is_a_no_op(self, monkeypatch):
        import backend.app.services.roadmap_requirement_copy as mod

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: _dto("ATLANTIS", [_item("Something", "x")]),
        )
        before = [_milestone("task_arrival_registration", "Complete arrival registration", "generic")]
        assert mod.enrich_milestones_with_requirements("c1", before) == before

    def test_empty_input_is_a_no_op(self):
        assert enrich_milestones_with_requirements("c1", []) == []


class TestTheGenericDeadlineNeverContradictsTheRealOne:
    """Seen live: the roadmap showed, side by side,

        "Register as EU/EEA resident at local authority"
            ...Registration with local authorities WITHIN 3 MONTHS of arrival.
        "Residence registration (Anmeldung)"
            ...typically WITHIN 14 DAYS of moving in.

    The 3-month figure is the EU directive's general rule. Germany's Anmeldung is 14
    days; the Dutch gemeente registration is 5. An employee who reads the first and
    misses the second gets fined. The generic step must stop asserting a deadline it
    does not know."""

    def test_the_free_movement_step_drops_its_generic_deadline(self, monkeypatch):
        import backend.app.services.roadmap_requirement_copy as mod

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: _dto("GERMANY", [
                _item("Residence registration (Anmeldung)",
                      "Register at the local Bürgeramt, typically within 14 days of moving in."),
            ]),
        )
        before = [
            _milestone("task_eu_registration", "Register as EU/EEA resident at local authority",
                       "EU/EEA free movement: no work permit required. Registration with local "
                       "authorities within 3 months of arrival.", sort_order=4),
            _milestone("task_arrival_registration", "Complete arrival registration", "generic"),
        ]
        after = {m["milestone_type"]: m for m in mod.enrich_milestones_with_requirements("c1", before)}

        eu = after["task_eu_registration"]
        assert "3 months" not in eu["description"], (
            "the generic 3-month figure contradicts Germany's 14-day Anmeldung deadline"
        )
        # ...but it must still STATE the answer only it can give.
        assert "no visa and no residence permit" in eu["description"].lower()
        # ...and the real deadline survives, on the step that owns it.
        assert "14 days" in after["task_arrival_registration"]["description"]

    def test_without_a_country_specific_step_the_generic_note_is_left_alone(self, monkeypatch):
        """No specific registration requirement → nothing to contradict → don't touch it."""
        import backend.app.services.roadmap_requirement_copy as mod

        monkeypatch.setattr(
            "backend.app.services.requirements_builder.compute_case_requirements",
            lambda cid: _dto("FRANCE", [
                _item("Valid passport or national identity card", "x", pillar="IDENTITY"),
            ]),
        )
        before = [_milestone("task_eu_registration", "Register as EU/EEA resident at local authority",
                             "...within 3 months of arrival.", sort_order=4)]
        after = mod.enrich_milestones_with_requirements("c1", before)[0]
        assert after["description"] == before[0]["description"]


class TestTheSpecificCopyActuallyREACHESTheEmployee:
    """The overlay wrote a `description`. Nothing rendered it.

    `why_this_matters` — the explanatory line under each roadmap task — comes from the
    static task library, and the milestone row's own `description` is surfaced nowhere.
    So the title said "Residence registration (Anmeldung)" while the text beneath it
    still read "Local registration or residency steps are often time-bound after entry",
    and the free-movement step still said "within 3 months" beside Germany's real 14-day
    deadline. The copy was written and thrown away.

    Caught only because the live check grepped the RESPONSE for "3 months" rather than
    trusting that the titles had changed.
    """

    def test_an_enriched_row_surfaces_its_own_description(self):
        from backend.relocation_plan_service import adapt_milestone_row

        row = {
            "id": "m1",
            "milestone_type": "task_arrival_registration",
            "title": "Residence registration (Anmeldung)",
            "description": "Register at the local Bürgeramt, typically within 14 days of moving in.",
            "status": "pending",
            "requirement_copy": True,
        }
        task = adapt_milestone_row(row)
        assert "14 days" in task.why_this_matters, (
            "the specific deadline must reach the employee, not just sit in the DB"
        )

    def test_an_unenriched_row_keeps_the_library_text(self):
        """Only rows the overlay rewrote may override the library. Everything else is
        untouched."""
        from backend.relocation_plan_service import adapt_milestone_row
        from backend.relocation_plan_task_library import TASK_BY_MILESTONE_TYPE

        row = {
            "id": "m2",
            "milestone_type": "task_arrival_registration",
            "title": "Complete arrival registration",
            "description": "Local registration or residency steps required shortly after arrival.",
            "status": "pending",
            # no requirement_copy marker
        }
        task = adapt_milestone_row(row)
        assert task.why_this_matters == TASK_BY_MILESTONE_TYPE["task_arrival_registration"].why_this_matters
