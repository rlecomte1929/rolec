"""Tests for the Cox case-duration survival model (Parker-A).

Skipped cleanly when the ML extras (lifelines/scikit-learn/scipy/pandas) are not
installed, so the rest of the suite stays green on ML-dep-less machines. Install
with `pip install -r backend/requirements.txt` to run them.
"""
from __future__ import annotations

import pytest

pytest.importorskip("lifelines")
pytest.importorskip("sklearn")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backend.app.services.case_duration_model import (  # noqa: E402
    InsufficientDataError,
    MIN_TRAINING_ROWS,
    CaseDurationModel,
    cross_validated_concordance,
    fit_cox_model,
    predict_remaining_duration,
    train_case_duration_model,
)

COUNTRIES = ["DE", "NL", "US", "JP", "GB"]
BANDS = ["junior", "mid", "senior"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]


def _synthetic_frame(n: int = 200, *, all_censored: bool = False, seed: int = 7) -> pd.DataFrame:
    """Build a survival frame with a genuine hazard signal.

    Duration is driven by the covariates (country/band base levels + a dependents
    and service-count effect) plus noise, so a fitted Cox model should achieve a
    cross-validated C-index comfortably above the 0.65 target.
    """
    rng = np.random.default_rng(seed)
    country_base = {"DE": 40, "NL": 45, "US": 90, "JP": 110, "GB": 60}
    band_base = {"junior": 0, "mid": 15, "senior": 35}

    rows = []
    for _ in range(n):
        country = rng.choice(COUNTRIES)
        band = rng.choice(BANDS)
        dependents = int(rng.integers(0, 4))
        services = int(rng.integers(1, 6))
        quarter = rng.choice(QUARTERS)
        mean = (
            country_base[country]
            + band_base[band]
            + dependents * 12
            + services * 6
        )
        true_duration = max(int(rng.normal(mean, mean * 0.12)), 1)

        if all_censored:
            event = 0
            observed = int(rng.integers(1, max(true_duration // 2, 2)))
        else:
            # Right-censor ~20% at a horizon shorter than the true duration.
            censor_at = int(rng.normal(mean * 1.4, mean * 0.2))
            if censor_at < true_duration and rng.random() < 0.25:
                event = 0
                observed = max(censor_at, 1)
            else:
                event = 1
                observed = true_duration

        rows.append(
            {
                "case_id": f"case-{_}",
                "duration_days": observed,
                "event_observed": event,
                "destination_country": country,
                "origin_country": rng.choice(COUNTRIES),
                "band": band,
                "dependents_count": dependents,
                "service_count": services,
                "seasonality_quarter": quarter,
            }
        )
    return pd.DataFrame(rows)


# ── Happy path ────────────────────────────────────────────────────────────────


def test_cross_validated_concordance_beats_target():
    df = _synthetic_frame(200)
    c_index = cross_validated_concordance(df, k=5)
    assert c_index >= 0.65, f"expected C-index >= 0.65, got {c_index:.3f}"


def test_fit_cox_model_returns_fitter():
    from lifelines import CoxPHFitter

    fitter = fit_cox_model(_synthetic_frame(200))
    assert isinstance(fitter, CoxPHFitter)
    assert fitter.concordance_index_ >= 0.6


def test_train_orchestrator_marks_servable():
    model = train_case_duration_model(_synthetic_frame(200))
    assert isinstance(model, CaseDurationModel)
    assert model.is_servable
    assert model.status == "active"
    assert model.n_training_rows == 200
    assert model.concordance is not None and model.concordance >= 0.65


# ── Edge: all-censored → sentinel, no crash ──────────────────────────────────


def test_all_censored_returns_unsafe_sentinel():
    df = _synthetic_frame(120, all_censored=True)
    model = train_case_duration_model(df)
    assert isinstance(model, CaseDurationModel)
    assert not model.is_servable
    assert model.status == "unsafe_to_serve"
    assert model.fitter is None
    # fallback priors are still populated so the route can serve an estimate
    assert model.overall_mean_duration > 0


def test_fit_cox_model_zero_events_raises():
    with pytest.raises(InsufficientDataError):
        fit_cox_model(_synthetic_frame(120, all_censored=True))


# ── Failure modes ─────────────────────────────────────────────────────────────


def test_missing_covariate_column_raises():
    df = _synthetic_frame(200).drop(columns=["band"])
    with pytest.raises(InsufficientDataError):
        fit_cox_model(df)
    with pytest.raises(InsufficientDataError):
        cross_validated_concordance(df)


def test_too_few_rows_raises():
    df = _synthetic_frame(MIN_TRAINING_ROWS - 5)
    with pytest.raises(InsufficientDataError):
        fit_cox_model(df)


# ── Prediction shape + fallback ──────────────────────────────────────────────


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeSession:
    """Minimal stand-in for predict_remaining_duration's build_case_covariates."""

    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return _FakeResult(self._row)


def _case_row():
    return {
        "id": "case-x",
        "created_at": "2026-05-01T00:00:00+00:00",
        "dest_country": "DE",
        "origin_country": "US",
        "draft_json": '{"employee": {"band": "senior"}, "family": {"dependents_count": 2}, "selected_services": ["a", "b", "c"]}',
    }


def test_predict_remaining_duration_shape():
    model = train_case_duration_model(_synthetic_frame(200))
    out = predict_remaining_duration(model, "case-x", _FakeSession(_case_row()))
    assert set(out) == {"median_days", "p20_days", "p80_days", "model_version", "n_training_cases"}
    assert all(isinstance(out[k], int) for k in ("median_days", "p20_days", "p80_days"))
    assert out["p20_days"] <= out["median_days"] <= out["p80_days"]
    assert out["model_version"] == model.model_version
    assert out["n_training_cases"] == 200


def test_predict_uses_fallback_when_unsafe():
    model = train_case_duration_model(_synthetic_frame(120, all_censored=True))
    out = predict_remaining_duration(model, "case-x", _FakeSession(_case_row()))
    assert out["p20_days"] <= out["median_days"] <= out["p80_days"]
    assert out["n_training_cases"] == model.n_training_rows


def test_predict_missing_case_raises():
    model = train_case_duration_model(_synthetic_frame(200))
    with pytest.raises(InsufficientDataError):
        predict_remaining_duration(model, "nope", _FakeSession(None))
