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
    assert to_iso("ZZ") is None          # genuinely unmapped code (IT/SE are now catalog-mapped)
    assert to_iso("Narnia") is None      # fictional name — real ones keep getting catalog-mapped
    assert to_iso("") is None
    assert to_iso("   ") is None
    assert to_iso(None) is None


def test_iso_to_catalog_name():
    assert iso_to_catalog_name("SG") == "SINGAPORE"
    assert iso_to_catalog_name("gb") == "UNITED KINGDOM"
    assert iso_to_catalog_name("XX") is None
    assert iso_to_catalog_name(None) is None


def test_ireland_is_covered():
    """IE resolves, so Otto's Ireland research can reach `requirement_items`.

    Before this entry existed, `mappings.resolve()` refused every staged IE entity with
    "no requirement catalog coverage for 'IE'" and `--promote` wrote 0 rows — which is why
    `requirement_items` held nothing for IRELAND while `otto_staging` held ready facts.
    This test fails against that state.
    """
    assert to_iso("IE") == "IE"
    assert to_iso("Ireland") == "IE"
    assert iso_to_catalog_name("IE") == "IRELAND"
    assert resolve_catalog_country("IE") == "IRELAND"


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
    assert resolve_catalog_country("ZZ") == "ZZ"       # unknown → raw upper
    assert resolve_catalog_country("Japan") == "JAPAN"
    assert resolve_catalog_country("") == "UNKNOWN"
    assert resolve_catalog_country("  ") == "UNKNOWN"


def test_normalize_corridor_code():
    assert normalize_corridor_code("fr") == "FR"
    assert normalize_corridor_code(" de ") == "DE"
    assert normalize_corridor_code("") == ""
    assert normalize_corridor_code(None) == ""


def test_spain_is_covered():
    """ES resolves, so the IE→ES corridor's 25 requirement records can be served.

    Case destinations are stored as ISO alpha-2 (`relocation_cases.dest_country_code`), and
    `requirements_builder` puts them through `resolve_catalog_country`. Misses fall back to
    the raw value upper-cased, so before this entry existed `"ES"` stayed `"ES"` and matched
    none of the 25 rows sitting at `country_code='SPAIN'` — the corridor was applied to
    production and could never be served, whatever a reviewer approved.

    Exactly the Ireland failure above. That fix was applied to one row of the map and never
    generalised, which is what `test_every_corridor_destination_resolves` is for.
    """
    assert to_iso("ES") == "ES"
    assert iso_to_catalog_name("ES") == "SPAIN"
    assert resolve_catalog_country("ES") == "SPAIN"
    # The full name already worked by falling through to raw-upper; both must agree now.
    assert resolve_catalog_country("Spain") == "SPAIN"


def test_denmark_is_covered():
    """DK resolves, so Otto's Danish research can reach `requirement_items`.

    `mappings.resolve()` refuses an entity whose destination has no catalog coverage, so
    without this the six Denmark-destination facts in the B3 batch promote nothing.
    """
    assert iso_to_catalog_name("DK") == "DENMARK"
    assert resolve_catalog_country("DK") == "DENMARK"


def test_switzerland_is_covered():
    """CH resolves — the FR_CH corridor profile targets it.

    `nationality_class` already models Swiss free movement under the EU–Swiss AFMP, so the
    codebase treats CH as a first-class destination everywhere except here.
    """
    assert iso_to_catalog_name("CH") == "SWITZERLAND"
    assert resolve_catalog_country("CH") == "SWITZERLAND"


def test_ecuador_is_covered():
    """EC resolves — the US_EC corridor profile (Seattle→Quito, Abraham) targets it.

    Ecuador is a brand-new destination. Without this, US→EC facts stage but
    `mappings.resolve()` refuses to promote them (no catalog coverage), so they reach no
    case. `to_iso` must also resolve the full name, since destinations are stored either way.
    """
    assert to_iso("EC") == "EC"
    assert to_iso("Ecuador") == "EC"
    assert iso_to_catalog_name("EC") == "ECUADOR"
    assert resolve_catalog_country("EC") == "ECUADOR"
    assert resolve_catalog_country("Ecuador") == "ECUADOR"


def test_canada_is_covered():
    """CA resolves — a Destination Coverage Master destination (rank 5, Toronto).

    A destination-only entry like GB: no corridor profile, but Canada facts must resolve to a
    catalog name or `mappings.resolve()` refuses to promote them and they reach no case.
    """
    assert to_iso("CA") == "CA"
    assert to_iso("Canada") == "CA"
    assert iso_to_catalog_name("CA") == "CANADA"
    assert resolve_catalog_country("CA") == "CANADA"
    assert resolve_catalog_country("Canada") == "CANADA"


def test_australia_is_covered():
    """AU resolves — Destination Coverage Master rank 6 (Sydney), destination-only."""
    assert to_iso("AU") == "AU"
    assert to_iso("Australia") == "AU"
    assert iso_to_catalog_name("AU") == "AUSTRALIA"
    assert resolve_catalog_country("AU") == "AUSTRALIA"
    assert resolve_catalog_country("Australia") == "AUSTRALIA"


def test_uae_is_covered():
    """AE resolves — Destination Coverage Master rank 8 (Dubai), destination-only, non-EEA."""
    assert to_iso("AE") == "AE"
    assert iso_to_catalog_name("AE") == "UNITED ARAB EMIRATES"
    assert resolve_catalog_country("AE") == "UNITED ARAB EMIRATES"
    assert resolve_catalog_country("United Arab Emirates") == "UNITED ARAB EMIRATES"


def test_italy_and_sweden_are_covered():
    """IT + SE resolve — coverage-master destinations (Milan rank 11, Stockholm rank 14)."""
    assert resolve_catalog_country("IT") == "ITALY"
    assert resolve_catalog_country("Italy") == "ITALY"
    assert resolve_catalog_country("SE") == "SWEDEN"
    assert resolve_catalog_country("Sweden") == "SWEDEN"
    assert resolve_catalog_country("BE") == "BELGIUM"
    assert resolve_catalog_country("AT") == "AUSTRIA"


def test_tier3_destinations_are_covered():
    """SA/JP/PT/FI resolve — Tier-3 coverage-master destinations, destination-only.

    Saudi Arabia (rank 12, Riyadh), Japan (rank 18, Tokyo), Portugal (rank 24, Lisbon) and
    Finland (rank 26, Helsinki). All served on the third-country-national pathway; each must
    resolve to a catalog name or `mappings.resolve()` refuses to promote and they reach no case.
    """
    assert resolve_catalog_country("SA") == "SAUDI ARABIA"
    assert resolve_catalog_country("Saudi Arabia") == "SAUDI ARABIA"
    assert resolve_catalog_country("JP") == "JAPAN"
    assert resolve_catalog_country("Japan") == "JAPAN"
    assert resolve_catalog_country("PT") == "PORTUGAL"
    assert resolve_catalog_country("Portugal") == "PORTUGAL"
    assert resolve_catalog_country("FI") == "FINLAND"
    assert resolve_catalog_country("Finland") == "FINLAND"


def test_every_corridor_destination_resolves():
    """Every corridor profile's destination must resolve to a catalog name.

    THE generalisation. A corridor whose `destination_iso` does not resolve can hold
    source-verified requirement records, pass every other gate, be applied to production and
    approved by a human — and still serve nobody, because the lookup that turns a case's
    destination into a catalog key returns the raw ISO code and matches zero rows.

    That is not hypothetical: it happened to IE→ES, and it had happened to IE before it. Both
    were fixed one map row at a time. This test fails on the *next* one instead, at the moment
    the corridor profile is committed rather than after the data is live.
    """
    import re
    from pathlib import Path

    corridors = Path(__file__).resolve().parents[2] / "corridors"
    unresolvable = {}
    for profile in sorted(corridors.glob("*/corridor.yaml")):
        match = re.search(r'destination_iso:\s*"?([A-Za-z]{2})', profile.read_text())
        assert match, f"{profile.parent.name}/corridor.yaml declares no destination_iso"
        iso = match.group(1).upper()
        if iso_to_catalog_name(iso) is None:
            unresolvable[profile.parent.name] = iso

    assert not unresolvable, (
        "corridor destination(s) do not resolve to a catalog country, so their requirement "
        f"records can never be served: {unresolvable}. Add the ISO to _ISO_TO_CATALOG_NAME "
        "in backend/app/services/requirements_country_key.py."
    )
