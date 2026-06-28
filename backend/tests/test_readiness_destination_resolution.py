"""
Slice B1 — destination resolution priority.

Locks the rule that the canonical `relocation_cases.host_country` column
beats the historical `profile_json.movePlan.destination` blob. The blob
can drift (e.g. monica's case had host_country="Japan" but the blob
still said "Singapore"); without the priority fix the readiness summary
mislabels assignments.

Pure-function tests — no DB. Covers the priority logic via
extract_destination_from_profile + extract_destination_from_case_profile
+ a stubbed resolver that mirrors the production order.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.readiness_service import (  # noqa: E402
    extract_destination_from_profile,
    extract_destination_from_case_profile,
    normalize_destination_key,
)


class _StubResolver:
    """Mirrors db.resolve_readiness_destination_for_assignment priority
    without a database — passes the same case/profile shapes through the
    same extractor functions."""

    def __init__(self, *, employee_profile=None, case=None):
        self.employee_profile = employee_profile
        self.case = case

    def resolve(self):
        raw = extract_destination_from_profile(self.employee_profile)
        # Fall back when the profile destination is missing OR doesn't normalise
        # (e.g. city-only "Amsterdam") — mirrors the real resolver (AIQ-1321).
        if not normalize_destination_key(raw) and self.case:
            host = str(self.case.get("host_country") or "").strip() or None
            if normalize_destination_key(host):
                raw = host
            else:
                blob = extract_destination_from_case_profile(self.case.get("profile_json"))
                if normalize_destination_key(blob):
                    raw = blob
        return raw, normalize_destination_key(raw)


class DestinationResolutionPriorityTests(unittest.TestCase):
    def test_employee_profile_wins_when_present(self):
        r = _StubResolver(
            employee_profile={"movePlan": {"destination": "France"}},
            case={"host_country": "Japan", "profile_json": '{"movePlan": {"destination": "Singapore"}}'},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "France")
        self.assertEqual(key, "FR")

    def test_canonical_host_country_beats_stale_blob(self):
        """The fix that prompted slice B1: monica's case had
        host_country=Japan but the blob still said Singapore."""
        r = _StubResolver(
            employee_profile=None,
            case={"host_country": "Japan", "profile_json": '{"movePlan": {"destination": "Singapore"}}'},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "Japan")
        self.assertEqual(key, "JP")

    def test_blob_used_only_when_canonical_empty(self):
        r = _StubResolver(
            employee_profile=None,
            case={"host_country": None, "profile_json": '{"movePlan": {"destination": "Germany"}}'},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "Germany")
        self.assertEqual(key, "DE")

    def test_returns_none_when_nothing_set(self):
        r = _StubResolver(
            employee_profile=None,
            case={"host_country": None, "profile_json": None},
        )
        raw, key = r.resolve()
        self.assertIsNone(raw)
        self.assertIsNone(key)

    def test_blank_host_country_falls_through_to_blob(self):
        r = _StubResolver(
            employee_profile=None,
            case={"host_country": "  ", "profile_json": '{"movePlan": {"destination": "Spain"}}'},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "Spain")
        self.assertEqual(key, "ES")


class DestinationFallbackOnUnnormalizableTests(unittest.TestCase):
    """AIQ-1321: the resolver must fall back to the canonical host_country when the
    profile destination is truthy but doesn't normalise (e.g. a city-only value), not
    only when it's empty — otherwise readiness degrades to no_destination."""

    def test_city_only_profile_falls_back_to_host_country(self):
        # "Amsterdam" alone has no country → normalises to None → use host_country.
        r = _StubResolver(
            employee_profile={"movePlan": {"destination": "Amsterdam"}},
            case={"host_country": "NL", "profile_json": None},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "NL")
        self.assertEqual(key, "NL")

    def test_reported_aiq1321_case_resolves(self):
        # The actual case 120d6fd0: movePlan "Amsterdam, NL" normalises (via #1058) → used as-is.
        r = _StubResolver(
            employee_profile={"movePlan": {"destination": "Amsterdam, NL"}},
            case={"host_country": "NL", "profile_json": None},
        )
        raw, key = r.resolve()
        self.assertEqual(raw, "Amsterdam, NL")
        self.assertEqual(key, "NL")

    def test_unnormalizable_everywhere_stays_no_destination(self):
        # Nothing resolves → key None (no_destination), correctly.
        r = _StubResolver(
            employee_profile={"movePlan": {"destination": "Atlantis"}},
            case={"host_country": None, "profile_json": None},
        )
        _, key = r.resolve()
        self.assertIsNone(key)


class CombinedCityCountryNormalizationTests(unittest.TestCase):
    """AIQ-1311 follow-up: the wizard stores movePlan.destination as "<city>, <country>"
    (e.g. "Amsterdam, NL"). That must normalize to the country key so HR readiness
    resolves (NL has a template) instead of degrading to reason="no_destination"."""

    def test_city_plus_iso2_code(self):
        self.assertEqual(normalize_destination_key("Amsterdam, NL"), "NL")
        self.assertEqual(normalize_destination_key("Oslo, NO"), "NO")

    def test_city_plus_country_name(self):
        self.assertEqual(normalize_destination_key("Paris, France"), "FR")
        self.assertEqual(normalize_destination_key("Munich, Germany"), "DE")

    def test_city_state_country_three_parts(self):
        self.assertEqual(normalize_destination_key("New York, NY, US"), "US")

    def test_plain_inputs_unaffected(self):
        # No comma → unchanged behavior.
        self.assertEqual(normalize_destination_key("NL"), "NL")
        self.assertEqual(normalize_destination_key("Singapore"), "SG")
        self.assertIsNone(normalize_destination_key("Atlantis"))
        self.assertIsNone(normalize_destination_key(None))

    def test_unresolvable_tokens_return_none(self):
        # A comma string with no recognizable country token still yields None.
        self.assertIsNone(normalize_destination_key("Somewhere, Nowhere"))


if __name__ == "__main__":
    unittest.main()
