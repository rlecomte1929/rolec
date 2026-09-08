"""DB-free unit tests for the DOC-1 corridor-requirements fallback shaping."""
from backend.app.services.corridor_requirements_fallback import (
    build_covered_fallback,
    map_corridor_item,
)


def test_map_marks_source_and_maps_fields():
    m = map_corridor_item({
        "title": "Entry D visa", "description": "d", "category": "RESIDENCE",
        "non_obvious": True, "timing": "before travel", "sources": ["https://x"],
        "verification_status": "representative", "attestation_status": None,
    })
    assert m["document_name"] == "Entry D visa"
    assert m["document_type"] == "RESIDENCE"
    assert m["source_kind"] == "corridor_requirement"
    assert m["book_early_flag"] is True
    assert m["book_early_reason"] == "before travel"
    assert m["form_url"] == "https://x"
    assert m["verification_status"] == "representative"


def test_map_handles_missing_fields():
    m = map_corridor_item({"title": "T"})
    assert m["form_url"] is None
    assert m["book_early_flag"] is False
    assert m["sources"] == []
    assert m["document_type"] == "corridor_requirement"


def test_build_covered_fallback_shape():
    resp = build_covered_fallback("ES", "IE", "join_family", [{"title": "A", "sources": []}])
    assert resp["covered"] is True
    assert resp["is_fallback"] is True
    assert resp["coverage_reason"] == "corridor_requirements_fallback"
    assert resp["corridor"] == "ES→IE"
    assert resp["document_count"] == 1
    assert resp["requirements"][0]["document_name"] == "A"


def test_build_covered_fallback_empty():
    resp = build_covered_fallback("ES", "IE", "x", [])
    assert resp["document_count"] == 0
    assert resp["requirements"] == []
