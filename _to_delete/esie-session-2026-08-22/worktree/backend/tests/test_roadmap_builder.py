"""
Tests for roadmap_builder.derive_roadmap() — AIQ-972.

The roadmap is requirements-driven: the "Visa & Permit" track is built only when
the immigration regime actually requires a visa/permit. EU/EEA free-movement and
domestic (same-country) moves get a lighter plan with no visa track.
"""
from backend.app.services.roadmap_builder import derive_roadmap


def _case(*, nationality=None, origin=None, dest=None, status="open"):
    """Build a minimal wizard case dict (the shape GET /api/cases/{id} returns)."""
    return {
        "id": "case-test",
        "status": status,
        "draft": {
            "relocationBasics": {"originCountry": origin, "destCountry": dest},
            "primaryApplicant": {"nationality": nationality},
            "assignmentContext": {"employerName": "Acme GmbH"},
        },
    }


def _has_visa_track(roadmap) -> bool:
    return any(t.get("id") == "visa" for t in roadmap["tracks"])


def _visa_step_keys(roadmap):
    return {s.get("key") for t in roadmap["tracks"] for s in t.get("steps", [])}


# ── Criterion 1: EU national, intra-EU move → no visa track ──────────────────

def test_eu_national_intra_eu_move_has_no_visa_track():
    # Polish (EU) national, Warsaw → Berlin (PL → DE) = eu_free_movement.
    roadmap = _case(nationality="PL", origin="PL", dest="DE")
    result = derive_roadmap(roadmap)
    assert not _has_visa_track(result)
    # No immigration steps (sponsorship / permit) leak into other tracks.
    assert "sponsorship" not in _visa_step_keys(result)
    assert "permit" not in _visa_step_keys(result)
    # Other tracks still present (lighter plan, not an empty one).
    track_ids = {t["id"] for t in result["tracks"]}
    assert "civil" in track_ids
    assert "settlement" in track_ids


# ── Criterion 2: non-EU national → visa track present ────────────────────────

def test_non_eu_national_into_eu_has_visa_track():
    # Indian (non-EEA) national, Bangalore → Berlin (IN → DE) = blue_card — a
    # visa/permit regime (not in _NO_VISA_REGIMES), so the visa track is retained.
    roadmap = _case(nationality="IN", origin="IN", dest="DE")
    result = derive_roadmap(roadmap)
    assert _has_visa_track(result)
    assert "permit" in _visa_step_keys(result)


# ── Criterion 3: domestic (same-country) move → no visa track ────────────────

def test_domestic_move_has_no_visa_track():
    # Same country origin == destination = domestic, no immigration required.
    roadmap = _case(nationality="DE", origin="DE", dest="DE")
    result = derive_roadmap(roadmap)
    assert not _has_visa_track(result)


# ── Backward compatibility: incomplete draft keeps the visa track (fail-open) ─

def test_empty_draft_keeps_visa_track():
    # No destination/nationality → regime "unknown" → visa track retained, so
    # existing callers that rely on a visa track for unknown routes don't break.
    result = derive_roadmap({"id": "c", "status": "open", "draft": {}})
    assert _has_visa_track(result)
