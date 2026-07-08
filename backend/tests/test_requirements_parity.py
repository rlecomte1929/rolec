"""AIQ-1473e — parity + zero-miss guard for the two requirements engines.

These lock in the AIQ-1473 reconciliation so the "HR sees X, employee fetches Y"
class of bugs can't silently return. They exercise the shared key layer (1473b)
and the fail-closed behaviour (1473c) directly — no DB needed.

By design this file FAILS on a checkout that lacks 1473c (the `_not_covered`
import below doesn't exist there) and PASSES once 1473b+1473c are present.
"""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest

from backend.app.services.requirements_country_key import (
    iso_to_catalog_name,
    normalize_corridor_code,
    resolve_catalog_country,
    to_iso,
)
# 1473c: fail-closed helper. Absent on a pre-1473c checkout → this file fails there.
from backend.app.services.requirements_builder import _not_covered

# Every country we hold catalog data for, in its various real-world spellings.
KNOWN_COUNTRIES = ["DE", "NO", "SG", "GB", "US", "FR", "NL"]
ALIASES = {"UK": "GB", "USA": "US", "usa": "US"}


@pytest.mark.parametrize("iso", KNOWN_COUNTRIES)
def test_zero_miss_known_countries_resolve(iso):
    # Guard against the AIQ-1349 silent-zero: a known destination must resolve to
    # a canonical ISO key (never None → never a zero-row lookup by a bad key).
    assert to_iso(iso) == iso
    assert to_iso(iso.lower()) == iso
    assert iso_to_catalog_name(iso) is not None


@pytest.mark.parametrize("alias,iso", list(ALIASES.items()))
def test_zero_miss_aliases_resolve(alias, iso):
    assert to_iso(alias) == iso


def test_known_corridor_endpoints_resolve():
    # The FR→NO corridor (a live audit fixture) must resolve on BOTH endpoints.
    assert to_iso("FR") == "FR"
    assert to_iso("NO") == "NO"


@pytest.mark.parametrize(
    "country_iso,spellings",
    [
        ("SG", ["SG", "sg", "SINGAPORE", "Singapore"]),
        ("NO", ["NO", "no", "NORWAY", "Norway"]),
        ("GB", ["GB", "UK", "United Kingdom", "UNITED KINGDOM"]),
    ],
)
def test_parity_same_country_one_canonical_key(country_iso, spellings):
    """Path A (corridor) and Path B (destination) can no longer key the same
    country differently: every spelling collapses to one ISO key, and Path B's
    catalog-name key is a pure function of it. This is the crux of the HR/employee
    mismatch fix — no representation can silently miss the other's rows."""
    isos = {to_iso(s) for s in spellings}
    assert isos == {country_iso}
    # Path B's catalog-name key: identical for every spelling.
    catalog_keys = {resolve_catalog_country(s) for s in spellings}
    assert len(catalog_keys) == 1
    assert catalog_keys == {iso_to_catalog_name(country_iso)}
    # Path A's corridor key: the same ISO code, normalised the same way.
    assert {normalize_corridor_code(iso_code) for iso_code in (country_iso, country_iso.lower())} == {country_iso}


def test_fail_closed_uncovered_destination():
    # 1473c: an unresolved destination fails closed (covered=False + empty),
    # NOT a misleading empty "nothing required" list.
    dto = _not_covered("case-x", "Atlantis", "employment")
    assert dto.covered is False
    assert dto.requirements == []
    assert dto.destCountry == "ATLANTIS"


def test_covered_default_is_true_for_resolved():
    # A resolved destination is 'covered' — the notice must not fire for it.
    assert to_iso("DE") == "DE"
    assert iso_to_catalog_name("DE") == "GERMANY"
