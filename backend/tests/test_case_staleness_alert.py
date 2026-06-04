"""P2-08e (AIQ-706) — unit tests for the active-case staleness admin alert.

Covers the pure aggregation core (threshold boundary, tier days, fail-open on
missing sources, env override, empty-active no-fire) and the evaluator wiring
(fires the ops notification only when breached; degrades on errors). The DB and
the notification client are mocked, so these run without Supabase or a populated
``relocation_cases`` — matching the validation criterion (verify by injecting
aged sources, since prod currently has none).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services import case_staleness_alert as csa
from backend.app.services.case_staleness_alert import (
    DEFAULT_ALERT_THRESHOLD_PCT,
    StalenessAlertSummary,
    evaluate_case_staleness_alert,
    load_threshold_pct,
    summarize_case_staleness,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def _days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# load_threshold_pct
# ─────────────────────────────────────────────────────────────────────────────


def test_threshold_default_when_unset():
    assert load_threshold_pct({}) == DEFAULT_ALERT_THRESHOLD_PCT


def test_threshold_accepts_fraction():
    assert load_threshold_pct({csa.ENV_THRESHOLD: "0.35"}) == 0.35


def test_threshold_accepts_percentage():
    assert load_threshold_pct({csa.ENV_THRESHOLD: "25"}) == 0.25


def test_threshold_malformed_falls_back():
    assert load_threshold_pct({csa.ENV_THRESHOLD: "abc"}) == DEFAULT_ALERT_THRESHOLD_PCT


def test_threshold_clamped():
    assert load_threshold_pct({csa.ENV_THRESHOLD: "-5"}) == 0.0
    assert load_threshold_pct({csa.ENV_THRESHOLD: "500"}) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# summarize_case_staleness — counting & tier
# ─────────────────────────────────────────────────────────────────────────────


def test_no_active_cases_never_breaches():
    s = summarize_case_staleness(
        total_active=0, case_oldest_sources={}, now=NOW, threshold_pct=0.2
    )
    assert s == StalenessAlertSummary(0, 0, 0, 0.0, 0.2, False)


def test_fresh_sources_not_stale():
    # tier1_critical default is 30 days; 29 days old is fresh.
    sources = {"c1": _days_ago(29), "c2": _days_ago(10)}
    s = summarize_case_staleness(
        total_active=5, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.stale_cases == 0
    assert s.breached is False


def test_exactly_threshold_days_is_stale():
    # is_stale is >= threshold: at exactly 30 days the source is the first day stale.
    sources = {"c1": _days_ago(30)}
    s = summarize_case_staleness(
        total_active=1, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.stale_cases == 1


def test_none_and_missing_sources_fail_open():
    # A case mapped to None (no datable source) is counted active but never stale.
    sources = {"c1": None, "c2": _days_ago(90)}
    s = summarize_case_staleness(
        total_active=4, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.cases_with_sources == 1
    assert s.stale_cases == 1
    # 1 / 4 = 25% > 20% → breach.
    assert s.breached is True


# ─────────────────────────────────────────────────────────────────────────────
# summarize_case_staleness — threshold boundary (strict >)
# ─────────────────────────────────────────────────────────────────────────────


def test_below_threshold_no_breach():
    # 1 stale of 10 active = 10% < 20%.
    sources = {f"c{i}": _days_ago(60) if i == 0 else _days_ago(1) for i in range(10)}
    s = summarize_case_staleness(
        total_active=10, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.stale_cases == 1
    assert s.stale_pct == 0.1
    assert s.breached is False


def test_exactly_at_threshold_does_not_breach():
    # 2 stale of 10 = exactly 20%; spec is ">20%", so strict-greater → no breach.
    sources = {f"c{i}": _days_ago(60) if i < 2 else _days_ago(1) for i in range(10)}
    s = summarize_case_staleness(
        total_active=10, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.stale_cases == 2
    assert s.stale_pct == 0.2
    assert s.breached is False


def test_above_threshold_breaches():
    # 3 stale of 10 = 30% > 20%.
    sources = {f"c{i}": _days_ago(60) if i < 3 else _days_ago(1) for i in range(10)}
    s = summarize_case_staleness(
        total_active=10, case_oldest_sources=sources, now=NOW, threshold_pct=0.2
    )
    assert s.stale_cases == 3
    assert s.stale_pct == 0.3
    assert s.breached is True


def test_env_threshold_override(monkeypatch):
    # With no explicit threshold_pct, the env value is used. 3/10 = 30% < 40%.
    monkeypatch.setenv(csa.ENV_THRESHOLD, "40")
    sources = {f"c{i}": _days_ago(60) if i < 3 else _days_ago(1) for i in range(10)}
    s = summarize_case_staleness(total_active=10, case_oldest_sources=sources, now=NOW)
    assert s.threshold_pct == 0.4
    assert s.breached is False


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_case_staleness_alert — wiring (DB + notification mocked)
# ─────────────────────────────────────────────────────────────────────────────


def test_evaluate_fires_when_breached(monkeypatch):
    monkeypatch.setattr(
        csa,
        "_fetch_active_case_sources",
        lambda: (4, {"c1": _days_ago(90), "c2": _days_ago(90), "c3": _days_ago(1)}),
    )
    captured = {}

    def fake_create(ntype, severity, title, message, dedupe, **kw):
        captured.update(
            ntype=ntype, severity=severity, dedupe=dedupe, payload=kw.get("payload")
        )
        return {"id": "notif-123"}

    import backend.app.services.ops_notification_service as ops

    monkeypatch.setattr(ops, "create_or_update_notification", fake_create)

    result = evaluate_case_staleness_alert(now=NOW)

    # 2 stale of 4 = 50% > 20%.
    assert result["breached"] is True
    assert result["alert_fired"] is True
    assert result["notification_id"] == "notif-123"
    assert captured["ntype"] == csa.NOTIFICATION_TYPE
    assert captured["severity"] == "high"
    assert captured["payload"]["stale_cases"] == 2


def test_evaluate_does_not_fire_when_below_threshold(monkeypatch):
    monkeypatch.setattr(
        csa,
        "_fetch_active_case_sources",
        lambda: (10, {"c0": _days_ago(90)}),  # 1/10 = 10%
    )
    import backend.app.services.ops_notification_service as ops

    def boom(*a, **k):  # must not be called
        raise AssertionError("notification should not fire below threshold")

    monkeypatch.setattr(ops, "create_or_update_notification", boom)

    result = evaluate_case_staleness_alert(now=NOW)
    assert result["breached"] is False
    assert result["alert_fired"] is False
    assert result["notification_id"] is None


def test_evaluate_degrades_on_empty(monkeypatch):
    # No active cases (fetch failure path returns (0, {})) → no alert, no error.
    monkeypatch.setattr(csa, "_fetch_active_case_sources", lambda: (0, {}))
    result = evaluate_case_staleness_alert(now=NOW)
    assert result["total_active"] == 0
    assert result["breached"] is False
    assert result["alert_fired"] is False
