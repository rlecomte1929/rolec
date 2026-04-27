"""
HR Resources preview: synthetic-context smoke tests.

We don't hit the FastAPI router here — the rendering shape is enforced by
get_resources_page_data_for_preview, and the route is a thin wrapper.
"""
from __future__ import annotations

from backend.services.resources.public_service import (
    build_preview_context,
    get_resources_page_data_for_preview,
)


def test_build_preview_context_defaults() -> None:
    ctx = build_preview_context(country_code="no")
    assert ctx["countryCode"] == "NO"
    assert ctx["familyType"] == "single"
    assert ctx["relocationType"] == "permanent"
    assert ctx["hasChildren"] is False
    assert ctx["previewMode"] is True
    # Single + permanent → networking + registration tags merged in
    tags = set(ctx["recommendedTags"])
    assert "networking" in tags
    assert "registration" in tags


def test_build_preview_context_family_with_children() -> None:
    ctx = build_preview_context(
        country_code="DE",
        country_name="Germany",
        city_name="  Berlin  ",
        family_type="family",
        relocation_type="long_term",
    )
    assert ctx["countryCode"] == "DE"
    assert ctx["countryName"] == "Germany"
    assert ctx["cityName"] == "Berlin"
    assert ctx["hasChildren"] is True  # implied by family
    tags = set(ctx["recommendedTags"])
    assert "schools" in tags
    assert "schooling" in tags  # long_term branch


def test_build_preview_context_normalizes_invalid_inputs() -> None:
    ctx = build_preview_context(
        country_code="fr",
        family_type="bogus",
        relocation_type="forever",
    )
    assert ctx["countryCode"] == "FR"
    assert ctx["familyType"] == "single"
    assert ctx["relocationType"] == "permanent"


def test_get_resources_page_data_for_preview_shape() -> None:
    """Payload matches /api/resources/page shape so the frontend can reuse rendering."""
    payload = get_resources_page_data_for_preview(
        country_code="NO",
        country_name="Norway",
        city_name="Oslo",
        family_type="single",
        relocation_type="permanent",
    )
    # Same composite shape as get_resources_page_data
    for key in ("context", "categories", "resources", "events", "recommended", "hints", "filtersApplied"):
        assert key in payload, f"missing {key}"
    assert payload["context"]["countryCode"] == "NO"
    assert payload["context"]["previewMode"] is True
    assert isinstance(payload["resources"], list)
    assert isinstance(payload["events"], list)
    assert isinstance(payload["recommended"], dict)


def test_preview_payload_has_no_case_id_leak() -> None:
    payload = get_resources_page_data_for_preview(country_code="DE")
    # Synthetic context must not invent a case id
    assert payload["context"]["caseId"] is None
