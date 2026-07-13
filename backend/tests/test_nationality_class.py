"""Nationality classification — the P0 honesty fix.

Before this, the engine had no nationality dimension: a French citizen relocating
to France was served the third-country-national visa track (VLS-TS, ANEF, DGEF).
These tests pin the classifier that makes that impossible.
"""
from __future__ import annotations

import pytest

from backend.app.services.nationality_class import (
    EU_EEA,
    OWN_NATIONAL,
    THIRD_COUNTRY,
    classify,
)


class TestOwnNational:
    def test_french_citizen_returning_to_france(self):
        assert classify("FR", "FRANCE") == OWN_NATIONAL

    def test_accepts_full_country_name_as_nationality(self):
        assert classify("France", "FRANCE") == OWN_NATIONAL

    def test_accepts_adjectival_nationality(self):
        assert classify("French", "FRANCE") == OWN_NATIONAL

    def test_norwegian_returning_to_norway(self):
        assert classify("NO", "NORWAY") == OWN_NATIONAL


class TestEuEea:
    def test_norwegian_to_france_is_eea_not_third_country(self):
        # Norway is EEA-but-not-EU: free movement still applies.
        assert classify("NO", "FRANCE") == EU_EEA

    def test_french_to_norway_is_eea(self):
        assert classify("FR", "NORWAY") == EU_EEA

    def test_swedish_to_france_is_eea(self):
        assert classify("SE", "FRANCE") == EU_EEA


class TestThirdCountry:
    def test_indian_to_france_is_third_country(self):
        assert classify("IN", "FRANCE") == THIRD_COUNTRY

    def test_us_to_france_is_third_country(self):
        assert classify("US", "FRANCE") == THIRD_COUNTRY

    def test_french_to_united_states_is_third_country(self):
        # Free movement is not global — an EU passport buys nothing in the US.
        assert classify("FR", "UNITED STATES") == THIRD_COUNTRY

    def test_norwegian_to_singapore_is_third_country(self):
        assert classify("NO", "SINGAPORE") == THIRD_COUNTRY


class TestUnknownFailsOpen:
    """We only ever suppress a requirement when we POSITIVELY know the person is
    EU/EEA. An unknown nationality returns None so the caller keeps the full list
    and makes no claim either way — never a fabricated 'nothing required'."""

    @pytest.mark.parametrize("nationality", [None, "", "   ", "Klingon"])
    def test_unknown_nationality_is_none(self, nationality):
        assert classify(nationality, "FRANCE") is None

    @pytest.mark.parametrize("dest", [None, "", "Atlantis"])
    def test_unknown_destination_is_none(self, dest):
        assert classify("FR", dest) is None
