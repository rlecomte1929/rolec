"""P3-04e (AIQ follow-up to P3-04) — guard the confidence + source-provenance
fields on the roadmap-step API model, and the confidence_pct → level bucketing.

P3-04 shipped the frontend confidence display; it renders only when a roadmap
step carries confidence data. This task makes the live ``/roadmap/tracks``
endpoint emit it, derived from the step's linked ``requirements`` row
(confidence_pct → level, citations[0] → source). These guards pin the contract
the frontend (RoadmapV2Step / RoadmapStep) consumes so it can't silently break.
"""
from __future__ import annotations

import pytest

# The live router is cases_read.py (cases.py is the unwired dead duplicate).
from backend.app.routers.cases_read import RoadmapStepV2, _bucket_confidence, _tier_to_confidence


CONFIDENCE_FIELDS = ("confidence_level", "source_url", "source_fetched_at", "source_excerpt")


class TestRoadmapStepConfidenceFields:
    @pytest.mark.parametrize("field", CONFIDENCE_FIELDS)
    def test_field_present_and_optional(self, field):
        assert field in RoadmapStepV2.model_fields, (
            f"RoadmapStepV2 is missing {field!r} — the P3-04 confidence display "
            "consumes it on every roadmap step."
        )
        # Optional → defaults to None so steps without a requirement omit it.
        assert RoadmapStepV2.model_fields[field].default is None

    def test_absent_fields_round_trip_as_none(self):
        step = RoadmapStepV2(id="s1", title="Step", status="available", owner="employee", sort_order=0)
        dumped = step.model_dump()
        for field in CONFIDENCE_FIELDS:
            assert dumped[field] is None

    def test_populated_fields_round_trip(self):
        step = RoadmapStepV2(
            id="s1",
            title="Apply for long-stay visa",
            status="available",
            owner="employee",
            sort_order=0,
            confidence_level="HIGH",
            source_url="https://france-visas.gouv.fr/en/long-stay",
            source_fetched_at="2026-06-01",
            source_excerpt="A long-stay visa is required for stays over 90 days.",
        )
        dumped = step.model_dump()
        assert dumped["confidence_level"] == "HIGH"
        assert dumped["source_url"].startswith("https://")
        assert dumped["source_excerpt"]


class TestBucketConfidence:
    @pytest.mark.parametrize(
        "pct,expected",
        [
            (100, "HIGH"),
            (80, "HIGH"),     # >=80 boundary → green/HIGH
            (79, "MEDIUM"),
            (50, "MEDIUM"),   # >=50 boundary → yellow/MEDIUM
            (49, "LOW"),
            (0, "LOW"),
            (None, None),     # no linked requirement → no badge
        ],
    )
    def test_thresholds(self, pct, expected):
        assert _bucket_confidence(pct) == expected


class TestTierToConfidence:
    """[P3-04e-FU] source_pages.tier → roadmap-step confidence level."""

    @pytest.mark.parametrize(
        "tier,expected",
        [
            ("1", "HIGH"),
            ("2", "MEDIUM"),
            ("3", "LOW"),
            (" 1 ", "HIGH"),    # whitespace-tolerant
            (None, "UNKNOWN"),  # no source page → honest UNKNOWN
            ("", "UNKNOWN"),
            ("9", "UNKNOWN"),   # unrecognised tier → UNKNOWN, never fabricated HIGH
        ],
    )
    def test_tier_mapping(self, tier, expected):
        assert _tier_to_confidence(tier) == expected
