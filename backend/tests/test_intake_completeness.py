"""Server-side intake-completeness guard (the submit 400 + field-level error map)."""
from backend.intake_completeness import (
    REQUIRED_INTAKE_BASICS,
    incomplete_intake_detail,
    missing_intake_basics,
)


def test_missing_basics_lists_only_absent():
    draft = {"relocationBasics": {"originCountry": "FR", "originCity": "Paris", "destCountry": "DE"}}
    assert missing_intake_basics(draft) == ["destCity", "purpose", "targetMoveDate"]


def test_complete_basics_returns_empty():
    full = {k: "x" for k in REQUIRED_INTAKE_BASICS}
    assert missing_intake_basics({"relocationBasics": full}) == []


def test_missing_basics_handles_empty_or_malformed_draft():
    assert missing_intake_basics({}) == REQUIRED_INTAKE_BASICS
    assert missing_intake_basics({"relocationBasics": None}) == REQUIRED_INTAKE_BASICS


def test_detail_has_field_map_when_pinpointed():
    detail = incomplete_intake_detail(["destCity", "purpose"])
    assert isinstance(detail, dict)
    assert detail["missingFields"] == ["relocationBasics.destCity", "relocationBasics.purpose"]
    assert detail["suggestedStep"] == 1


def test_detail_is_string_fallback_when_nothing_pinpointed():
    assert isinstance(incomplete_intake_detail([]), str)
