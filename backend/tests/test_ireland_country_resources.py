"""
[AIQ-1746 / T18-06] Ireland's settle-in pack.

Before this, `country_resources.py` had no `IE` branch, so an IE/Dublin case fell
through to the generic defaults at the bottom of get_default_section_content(). Those
defaults are where the T18 campaign's worst single line came from:

    admin_essentials → {"title": "Residence registration", "timeline": "Within 7-14 days"}

That is wrong for EVERY Irish case. An EEA citizen registers nothing at all (Citizens
Information: they "do not need to register with the immigration authorities"); a
non-EEA national registers for an IRP within 90 days, not 7-14.

`test_no_generic_residence_registration_deadline` is the discriminating case — it fails
against the pre-AIQ-1746 tree, because that tree returns the generic block for IE.

Nationality is deliberately NOT branched on: get_default_section_content takes no
nationality argument and `nationality` appears nowhere in the resources read path, so
the registration item is written to be true for BOTH branches instead.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.country_resources import (  # noqa: E402
    RESOURCE_SECTIONS,
    get_default_section_content,
)
from backend.app.services.rkg_resources import resources_to_sections  # noqa: E402

# Strings the ticket's criterion 1 forbids anywhere in the pack.
PLACEHOLDERS = (
    "will appear here",
    "Practical guidance for your relocation",
)


def _ie(section_key):
    return get_default_section_content("IE", "Dublin", section_key)


def _all_text(obj) -> str:
    """Flatten a section to searchable text."""
    if isinstance(obj, dict):
        return " ".join(_all_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_all_text(v) for v in obj)
    return str(obj)


class IrelandSettleInPackTests(unittest.TestCase):
    def test_no_generic_residence_registration_deadline(self) -> None:
        """THE discriminating test. The generic default claims a 7-14 day residence
        registration; Ireland has no such requirement for anyone."""
        text = _all_text(_ie("admin_essentials"))
        self.assertNotIn("Within 7-14 days", text)

    def test_registration_item_is_true_for_both_nationality_branches(self) -> None:
        titles = " ".join(t.get("title", "") for t in _ie("admin_essentials")["topics"])
        timings = " ".join(t.get("timeline", "") for t in _ie("admin_essentials")["topics"])
        both = titles + " " + timings
        # EEA: nothing to register.
        self.assertIn("not required for EU/EEA", titles)
        # Non-EEA: the real deadline, not the generic one.
        self.assertIn("90 days", both)

    def test_no_placeholder_strings_in_any_section(self) -> None:
        for key in RESOURCE_SECTIONS:
            text = _all_text(_ie(key))
            for ph in PLACEHOLDERS:
                self.assertNotIn(ph, text, f"section {key!r} still carries placeholder {ph!r}")

    def test_housing_lists_at_least_six_named_dublin_areas(self) -> None:
        """Ticket criterion 2."""
        hoods = _ie("housing").get("neighborhoods") or []
        self.assertGreaterEqual(len(hoods), 6, f"only {len(hoods)} areas")
        joined = " ".join(hoods)
        for expected in ("Grand Canal Dock", "Ranelagh", "Rathmines"):
            self.assertIn(expected, joined)

    def test_cost_of_living_carries_real_figures_not_em_dashes(self) -> None:
        """Ticket criterion 3 — the campaign saw Average rent '—', Transport pass '—'."""
        items = _ie("cost_of_living").get("items") or []
        self.assertGreaterEqual(len(items), 4)
        for item in items:
            value = str(item.get("value", ""))
            self.assertNotIn("—", value, f"{item.get('label')!r} still an em-dash placeholder")
            self.assertTrue(value.strip(), f"{item.get('label')!r} has an empty value")
        joined = _all_text(items)
        self.assertIn("2,012", joined)   # Daft Q1 2026 Dublin 1-bed
        self.assertIn("Daft", joined)    # …and its basis is named

    def test_ppsn_revenue_bank_ordering_is_stated(self) -> None:
        """The sequencing insight: an EEA citizen has no IRP, so PPSN → Revenue → bank
        is the only order that completes. This is the single most useful thing in the pack."""
        text = _all_text(_ie("admin_essentials"))
        self.assertIn("PPS", text)
        self.assertIn("Revenue", text)
        for marker in ("1.", "2.", "3."):
            self.assertIn(marker, text)

    def test_emergency_number_is_irish(self) -> None:
        # 112 alone was a generic-EU tell; 999 is the commonly used Irish number.
        self.assertIn("999", _all_text(_ie("safety")))

    def test_every_admin_topic_carries_a_source_link(self) -> None:
        """Ticket criterion 5 — every factual claim has a source URL."""
        for topic in _ie("admin_essentials")["topics"]:
            self.assertTrue(
                str(topic.get("link") or "").startswith("http"),
                f"{topic.get('title')!r} has no source link",
            )

    def test_rent_control_change_is_dated(self) -> None:
        """RPZs were abolished 1 March 2026 — most third-party guidance is still stale,
        so the pack must state the change rather than inherit the old regime."""
        self.assertIn("1 March 2026", _all_text(_ie("safety")) + _all_text(_ie("housing")))


class NeighbourhoodsSurviveTheCmsPathTests(unittest.TestCase):
    """resources_to_sections rebuilds `content` field by field from the defaults, and
    before AIQ-1746 it never copied `neighborhoods`. So the key vanished the moment a
    country had ANY country_resources row — seeding a country made its housing section
    LESS informative than leaving it empty. This test pins the passthrough."""

    def test_neighborhoods_survive_when_db_rows_exist(self) -> None:
        # One DB row in an unrelated category is enough to take the CMS path.
        rows = [{
            "id": "r1", "category_id": None, "title": "Some resource",
            "summary": "s", "resource_type": "guide", "external_url": None,
            "booking_url": None, "address": None, "price_range_text": None,
            "is_family_friendly": True, "trust_tier": "T0",
        }]
        sections = resources_to_sections("IE", "Dublin", rows)
        housing = next(s for s in sections if s["key"] == "housing")
        hoods = housing["content"].get("neighborhoods") or []
        self.assertGreaterEqual(len(hoods), 6, "neighbourhoods dropped on the CMS path")


if __name__ == "__main__":
    unittest.main()
