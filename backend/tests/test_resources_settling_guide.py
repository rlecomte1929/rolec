"""Settling guide on the Resources page payload (IDR-260909-D201).

Employees landing on /resources should always receive cultural awareness,
first-step admin, and community content from the curated country packs —
even when the published catalog is empty or already has a few listings.
"""
from __future__ import annotations

from backend.app.services.resources.public_service import (
    _get_curated_resources_as_public,
    get_resources_page_data_for_preview,
)


def test_preview_includes_settling_guide_for_norway() -> None:
    payload = get_resources_page_data_for_preview(
        country_code="NO",
        country_name="Norway",
        city_name="Oslo",
    )
    guide = payload["settlingGuide"]
    tips = guide["culturalAwareness"]["tips"]
    assert any("Punctuality" in t for t in tips)
    assert guide["culturalAwareness"]["intro"]
    titles = [s["title"] for s in guide["firstSteps"]]
    assert any("Folkeregisteret" in t for t in titles)
    groups = guide["community"]["groups"]
    assert any("Internations" in (g.get("title") or "") for g in groups)


def test_settling_guide_present_when_published_catalog_is_nonempty(monkeypatch) -> None:
    from backend.app.services.resources import public_service as ps

    monkeypatch.setattr(
        ps,
        "get_published_resources",
        lambda *a, **k: [
            {
                "id": "pub-1",
                "countryCode": "NO",
                "title": "A published listing",
                "summary": "Thin catalog row",
                "resourceType": "place",
                "isFamilyFriendly": False,
                "isFeatured": False,
            }
        ],
    )
    payload = get_resources_page_data_for_preview(
        country_code="NO",
        country_name="Norway",
        city_name="Oslo",
    )
    assert payload["resources"][0]["id"] == "pub-1"
    assert payload["settlingGuide"]["culturalAwareness"]["tips"]


def test_curated_resources_include_cultural_tips_and_cost_items() -> None:
    resources, categories = _get_curated_resources_as_public("NO", "Oslo")
    keys = {c["key"] for c in categories}
    assert "welcome" in keys
    titles = [r["title"] for r in resources]
    assert any("Punctuality" in t for t in titles)
    assert any("Average rent" in t or "rent" in t.lower() for t in titles)
    welcome_ids = [c["id"] for c in categories if c["key"] == "welcome"]
    assert welcome_ids
    welcome_cards = [r for r in resources if r.get("categoryId") == welcome_ids[0]]
    assert welcome_cards
