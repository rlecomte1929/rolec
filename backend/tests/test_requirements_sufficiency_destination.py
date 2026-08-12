"""[AIQ-1821] Destination normalisation in the sufficiency path.

`list_dossier_questions` and `list_approved_requirement_facts` both match
`destination_country` EXACTLY. Cases do not consistently store ISO-2: measured on prod
2026-08-12, **426 of 1389 wizard_cases store a country name** ("Germany", "Norway",
"France"). Un-normalised, those returned zero questions and zero facts while the endpoint
still reported `compute_status: "ok"` — which reads to the employee as "nothing is required
of you".

No DB, no network: `_resolve_destination` is exercised directly.
"""
from __future__ import annotations

import pytest

from backend.app.services.requirements_sufficiency import _resolve_destination


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The corridor this shipped for.
        ("NO", "NO"), ("Norway", "NO"), ("NORGE", "NO"), ("Oslo", "NO"), (" norway ", "NO"),
        # The three biggest name-storing populations in prod.
        ("Germany", "DE"), ("Singapore", "SG"), ("France", "FR"),
        # Already-ISO passes through untouched.
        ("FR", "FR"), ("DE", "DE"), ("US", "US"),
    ],
)
def test_names_and_cities_normalise_to_iso2(raw, expected):
    assert _resolve_destination(raw) == expected


def test_unmapped_destination_falls_back_to_raw():
    """An unknown country must behave exactly as before, not collapse to None.

    _normalize_destination_country returns None for anything not in its table; returning that
    directly would turn 'no facts for Atlantis' into 'no destination set', which is a different
    and worse claim.
    """
    assert _resolve_destination("Atlantis") == "Atlantis"


@pytest.mark.parametrize("raw", [None, ""])
def test_absent_destination_stays_none(raw):
    assert _resolve_destination(raw) is None


def test_normalisation_agrees_with_the_dossier_endpoint():
    """Both paths share one table now, so they cannot drift apart."""
    from backend.app.services.destination_normalizer import normalize_destination_country

    for raw in ("Norway", "Germany", "Singapore", "Paris", "Berlin"):
        assert _resolve_destination(raw) == normalize_destination_country(raw)
