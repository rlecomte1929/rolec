"""P2-08a (AIQ-702) — unit tests for the staleness helper.

Covers all 3 tiers, the exactly-N-days boundary, env override (valid + malformed),
input type coercion, and tz/naive handling.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.services.staleness import (
    DEFAULT_THRESHOLDS_DAYS,
    StalenessConfig,
    is_stale,
    load_config,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def _days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# All 3 tiers — fresh vs stale, with the exactly-N boundary explicit
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tier,threshold",
    [(t, n) for t, n in DEFAULT_THRESHOLDS_DAYS.items()],
)
def test_fresh_one_day_below_threshold(tier, threshold):
    assert is_stale(_days_ago(threshold - 1), tier, now=NOW) is False


@pytest.mark.parametrize(
    "tier,threshold",
    [(t, n) for t, n in DEFAULT_THRESHOLDS_DAYS.items()],
)
def test_exactly_threshold_days_is_stale(tier, threshold):
    # The exactly-N-days boundary: first day stale.
    assert is_stale(_days_ago(threshold), tier, now=NOW) is True


@pytest.mark.parametrize(
    "tier,threshold",
    [(t, n) for t, n in DEFAULT_THRESHOLDS_DAYS.items()],
)
def test_above_threshold_is_stale(tier, threshold):
    assert is_stale(_days_ago(threshold + 5), tier, now=NOW) is True


def test_just_now_is_not_stale():
    assert is_stale(NOW, "tier1_critical", now=NOW) is False
    assert is_stale(NOW, "tier1_stable", now=NOW) is False
    assert is_stale(NOW, "tier2", now=NOW) is False


# ─────────────────────────────────────────────────────────────────────────────
# Input type coercion
# ─────────────────────────────────────────────────────────────────────────────


def test_iso_string_with_z_suffix():
    assert is_stale("2026-05-05T12:00:00Z", "tier1_critical", now=NOW) is True


def test_iso_string_with_offset():
    assert is_stale("2026-05-05T12:00:00+00:00", "tier1_critical", now=NOW) is True


def test_date_input():
    assert is_stale(date(2026, 5, 5), "tier1_critical", now=NOW) is True


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 5, 5, 12, 0)
    assert is_stale(naive, "tier1_critical", now=NOW) is True


def test_now_defaults_to_real_clock():
    # Just exercise the no-`now` path; a very-old date must be stale.
    assert is_stale(datetime(2020, 1, 1, tzinfo=timezone.utc), "tier2") is True


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="unknown tier"):
        is_stale(NOW, "tier3", now=NOW)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Env override + defaults + malformed fallback
# ─────────────────────────────────────────────────────────────────────────────


def test_load_config_uses_defaults_when_env_unset():
    cfg = load_config({})
    assert cfg.thresholds_days == dict(DEFAULT_THRESHOLDS_DAYS)


def test_load_config_applies_full_override():
    cfg = load_config({
        "STALENESS_THRESHOLDS_DAYS": '{"tier1_critical": 7, "tier1_stable": 14, "tier2": 21}'
    })
    assert cfg.thresholds_days == {"tier1_critical": 7, "tier1_stable": 14, "tier2": 21}


def test_load_config_partial_override_falls_back_for_missing_tiers():
    cfg = load_config({"STALENESS_THRESHOLDS_DAYS": '{"tier1_critical": 7}'})
    assert cfg.thresholds_days["tier1_critical"] == 7
    assert cfg.thresholds_days["tier1_stable"] == DEFAULT_THRESHOLDS_DAYS["tier1_stable"]
    assert cfg.thresholds_days["tier2"] == DEFAULT_THRESHOLDS_DAYS["tier2"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[1, 2, 3]",          # array, not object
        '{"tier1_critical": "thirty"}',   # wrong type
        '{"tier1_critical": -1}',          # negative
        '{"tier1_critical": 1.5}',         # float, not int
    ],
)
def test_load_config_malformed_env_falls_back_safely(raw):
    cfg = load_config({"STALENESS_THRESHOLDS_DAYS": raw})
    # Whatever the bad input, tier1_critical falls back to the default.
    assert cfg.thresholds_days["tier1_critical"] == DEFAULT_THRESHOLDS_DAYS["tier1_critical"]


def test_is_stale_honours_injected_config():
    cfg = StalenessConfig(thresholds_days={"tier1_critical": 7, "tier1_stable": 14, "tier2": 21})
    # 10 days old < default 30 (fresh) but > injected 7 (stale).
    assert is_stale(_days_ago(10), "tier1_critical", now=NOW) is False
    assert is_stale(_days_ago(10), "tier1_critical", now=NOW, config=cfg) is True


def test_load_config_bool_rejected_for_int():
    # bools are technically ints in Python — explicitly reject so True doesn't
    # silently become threshold=1.
    cfg = load_config({"STALENESS_THRESHOLDS_DAYS": '{"tier1_critical": true}'})
    assert cfg.thresholds_days["tier1_critical"] == DEFAULT_THRESHOLDS_DAYS["tier1_critical"]
