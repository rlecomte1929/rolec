from backend.app.services.country_catalog_display import (
    catalog_lookup_keys,
    evidence_backed_confidence,
)


def test_catalog_lookup_keys_include_iso_and_full_name():
    assert "FRANCE" in catalog_lookup_keys("FR")
    assert "FR" in catalog_lookup_keys("FRANCE")
    assert "AUSTRALIA" in catalog_lookup_keys("AU")
    assert "AU" in catalog_lookup_keys("Australia")


def test_empty_catalog_never_keeps_a_high_score():
    assert evidence_backed_confidence(0.95, 0, 0) is None
    assert evidence_backed_confidence(0.95, 0, 2) is None


def test_requirements_without_sources_cannot_be_high():
    assert evidence_backed_confidence(0.9, 4, 0) == 0.39


def test_sourced_catalog_keeps_the_stored_score():
    assert evidence_backed_confidence(0.9, 4, 2) == 0.9
