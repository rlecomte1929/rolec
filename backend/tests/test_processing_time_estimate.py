"""Tests for the corridor-level processing-time estimator (P2-04a).

Pure stdlib — no ML extras, no real database. The platform-data branch is
exercised through a tiny fake SQLAlchemy session that replays preset rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.services.processing_time_estimate import (
    MIN_PLATFORM_CASES,
    estimate_from_durations,
    load_official_ranges,
    processing_time_estimate,
    _percentile,
)

VALID_SOURCES = {"platform_data", "official_only"}


# ──────────────────────────────────────────────────────────────────────────────
# Fake session: session.execute(...).mappings().all() -> preset rows
# ──────────────────────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Replays a fixed list of completed-case rows for any query."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_args, **_kwargs):
        return _Result(self._rows)


def _completed_rows(durations_days):
    """Build wizard_cases-shaped rows for completed cases with given durations."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for d in durations_days:
        rows.append(
            {
                "created_at": base,
                "updated_at": base + timedelta(days=d),
                "status": "completed",
                "total_ms": 0,
                "done_ms": 0,
                "last_actual": base + timedelta(days=d),
            }
        )
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Pure core
# ──────────────────────────────────────────────────────────────────────────────


def test_percentile_linear_interpolation():
    vals = [float(x) for x in range(1, 26)]  # 1..25
    assert _percentile(vals, 0.5) == 13.0
    assert round(_percentile(vals, 0.9)) == 23
    assert _percentile([5.0], 0.9) == 5.0


def test_estimate_from_durations_below_threshold_returns_none():
    assert estimate_from_durations(list(range(1, MIN_PLATFORM_CASES))) is None  # 19 values


def test_estimate_from_durations_at_threshold_returns_percentiles():
    result = estimate_from_durations(list(range(1, 26)))  # 25 values, 1..25
    assert result == (13, 23)


def test_estimate_drops_nonpositive_durations():
    # 19 real durations + zeros/negatives -> still below threshold (zeros dropped)
    assert estimate_from_durations(list(range(1, 20)) + [0, 0, -5]) is None


# ──────────────────────────────────────────────────────────────────────────────
# Validation Criterion: >= 20 platform cases -> platform_data with sample size
# ──────────────────────────────────────────────────────────────────────────────


def test_platform_data_branch_with_enough_cases():
    session = _FakeSession(_completed_rows(list(range(1, 26))))  # 25 completed cases
    est = processing_time_estimate(
        pathway_type="EU_BLUE_CARD", corridor=("IN", "DE"), session=session
    )
    assert est is not None
    assert est["source"] == "platform_data"
    assert est["sample_size"] == 25
    assert est["p50_days"] == 13
    assert est["p90_days"] == 23
    assert est["source_url"] is None


# ──────────────────────────────────────────────────────────────────────────────
# Validation Criterion: < 20 platform cases -> official fallback with citation
# ──────────────────────────────────────────────────────────────────────────────


def test_falls_back_to_official_when_below_threshold():
    session = _FakeSession(_completed_rows(list(range(1, 19))))  # only 18 completed cases
    est = processing_time_estimate(
        pathway_type="EU_BLUE_CARD", corridor=("IN", "DE"), session=session
    )
    assert est is not None
    assert est["source"] == "official_only"
    assert est["sample_size"] == 0
    assert est["p50_days"] == 28  # low_days from seed
    assert est["p90_days"] == 84  # high_days from seed
    assert est["source_url"]  # citation present
    assert "make-it-in-germany" in est["source_url"]


def test_official_only_when_no_session():
    est = processing_time_estimate(
        pathway_type="EEA_REGISTRATION", corridor=("FR", "NO"), session=None
    )
    assert est is not None
    assert est["source"] == "official_only"
    assert est["p50_days"] == 1
    assert est["p90_days"] == 90
    assert "udi.no" in (est["source_url"] or "")


# ──────────────────────────────────────────────────────────────────────────────
# Validation Criterion: never a processing time without a source
# ──────────────────────────────────────────────────────────────────────────────


def test_none_when_no_source_available():
    # Unknown corridor, no platform data -> no fabricated estimate.
    est = processing_time_estimate(
        pathway_type="LONG_STAY_VISA", corridor=("ZZ", "ZZ"), session=None
    )
    assert est is None


def test_every_returned_estimate_carries_a_valid_source():
    cases = [
        processing_time_estimate(pathway_type="EEA_REGISTRATION", corridor=("FR", "NO")),
        processing_time_estimate(pathway_type="LONG_STAY_VISA", corridor=("US", "FR")),
        processing_time_estimate(pathway_type="LONG_STAY_VISA", corridor=("BR", "PT")),
        processing_time_estimate(
            pathway_type="EU_BLUE_CARD",
            corridor=("IN", "DE"),
            session=_FakeSession(_completed_rows(list(range(1, 30)))),
        ),
    ]
    for est in cases:
        assert est is not None
        assert est["source"] in VALID_SOURCES
        assert est["p50_days"] <= est["p90_days"]


# ──────────────────────────────────────────────────────────────────────────────
# Seed file integrity
# ──────────────────────────────────────────────────────────────────────────────


def test_official_seed_file_loads_all_five_corridors():
    index = load_official_ranges()
    keys = set(index.keys())
    assert ("FR", "NO", "EEA_REGISTRATION") in keys
    assert ("US", "FR", "LONG_STAY_VISA") in keys
    assert ("IN", "DE", "EU_BLUE_CARD") in keys
    assert ("UK", "DE", "EU_BLUE_CARD") in keys
    assert ("BR", "PT", "LONG_STAY_VISA") in keys
    # Every entry has a resolvable https source and a sane range.
    for entry in index.values():
        assert entry["source"]["url"].startswith("https://")
        assert 0 < entry["low_days"] <= entry["high_days"]
