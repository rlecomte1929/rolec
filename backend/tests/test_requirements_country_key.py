"""AIQ-1473b — the shared country/corridor key resolver. Pure functions, no DB.

Canonical internal key = ISO alpha-2 UPPERCASE (AIQ-1473a). `to_iso` returns
None on unrecognised input so callers can fail closed (the AIQ-1349 silent-miss
guard, acted on in 1473c).
"""
from backend.app.services.requirements_country_key import (
    iso_to_catalog_name,
    normalize_corridor_code,
    resolve_catalog_country,
    to_iso,
)


def test_to_iso_from_iso_code():
    assert to_iso("SG") == "SG"
    assert to_iso("sg") == "SG"
    assert to_iso(" de ") == "DE"


def test_to_iso_from_full_name_any_case():
    assert to_iso("Singapore") == "SG"
    assert to_iso("UNITED KINGDOM") == "GB"
    assert to_iso("germany") == "DE"


def test_to_iso_aliases():
    assert to_iso("UK") == "GB"
    assert to_iso("USA") == "US"
    assert to_iso("usa") == "US"


def test_to_iso_unknown_or_empty_is_none():
    # None signals "unrecognised" so callers fail closed (1473c) instead of
    # querying with a bad key.
    assert to_iso("IT") is None          # no catalog data yet
    assert to_iso("Japan") is None
    assert to_iso("") is None
    assert to_iso("   ") is None
    assert to_iso(None) is None


def test_iso_to_catalog_name():
    assert iso_to_catalog_name("SG") == "SINGAPORE"
    assert iso_to_catalog_name("gb") == "UNITED KINGDOM"
    assert iso_to_catalog_name("XX") is None
    assert iso_to_catalog_name(None) is None


def test_same_canonical_key_across_representations():
    # Criterion: 'SG', 'SINGAPORE', 'Singapore' must resolve identically.
    assert to_iso("SG") == to_iso("SINGAPORE") == to_iso("Singapore") == "SG"
    # ...and therefore to the same catalog key Path B queries with.
    keys = {resolve_catalog_country(x) for x in ("SG", "SINGAPORE", "Singapore")}
    assert keys == {"SINGAPORE"}


def test_resolve_catalog_country_preserves_legacy_behaviour():
    # Exactly mirrors the former _resolve_catalog_country contract.
    assert resolve_catalog_country("SG") == "SINGAPORE"
    assert resolve_catalog_country("UK") == "UNITED KINGDOM"
    assert resolve_catalog_country("usa") == "UNITED STATES"
    assert resolve_catalog_country("UNITED KINGDOM") == "UNITED KINGDOM"
    assert resolve_catalog_country("IT") == "IT"       # unknown → raw upper
    assert resolve_catalog_country("Japan") == "JAPAN"
    assert resolve_catalog_country("") == "UNKNOWN"
    assert resolve_catalog_country("  ") == "UNKNOWN"


def test_normalize_corridor_code():
    assert normalize_corridor_code("fr") == "FR"
    assert normalize_corridor_code(" de ") == "DE"
    assert normalize_corridor_code("") == ""
    assert normalize_corridor_code(None) == ""
