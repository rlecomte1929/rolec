"""
Tests for the AI carbon estimator — Parker Step G.

Exercises the pure tokens→kWh→gCO₂e math, the in-code seed-default path, the unknown
-model global-default fallback (+ warning), and the in-process cache. The DB read is
monkeypatched out so these never touch a real database.
"""
from __future__ import annotations

import logging
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import ai_carbon_estimator as est  # noqa: E402


@pytest.fixture(autouse=True)
def _no_db_and_clean_cache(monkeypatch):
    # Force the in-code default path; never hit a real DB in these unit tests.
    monkeypatch.setattr(est, "_load_profile_from_db", lambda model_name: None)
    est.clear_cache()
    yield
    est.clear_cache()


def test_known_model_matches_hand_computed_grams():
    # gpt-4o seed: J_in=0.40, J_out=0.80, 400 gCO2e/kWh.
    # joules = 1000*0.40 + 500*0.80 = 800 J; kWh = 800/3_600_000; grams = kWh*400.
    grams = est.estimate_co2e_grams("gpt-4o", 1000, 500)
    assert grams == pytest.approx(800 / 3_600_000 * 400, rel=1e-9)
    assert grams == pytest.approx(0.088889, abs=1e-6)


def test_embedding_model_has_no_output_cost():
    # text-embedding-3-small: J_out=0.0 → only input tokens count.
    grams = est.estimate_co2e_grams("text-embedding-3-small", 1000, 999)
    assert grams == pytest.approx(1000 * 0.05 / 3_600_000 * 400, rel=1e-9)


def test_unknown_model_uses_global_default_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        grams = est.estimate_co2e_grams("totally-unknown-model", 1000, 500)
    # Same formula as the global default (0.40/0.80/400).
    assert grams == pytest.approx(800 / 3_600_000 * 400, rel=1e-9)
    assert any("no energy profile" in r.message for r in caplog.records)


def test_zero_tokens_is_zero_grams():
    assert est.estimate_co2e_grams("gpt-4o", 0, 0) == 0.0


def test_profile_is_cached(monkeypatch):
    calls = {"n": 0}
    real = est._DEFAULT_PROFILES["gpt-4o"]

    def counting_lookup(model_name):  # stands in for the DB read
        calls["n"] += 1
        return None

    monkeypatch.setattr(est, "_load_profile_from_db", counting_lookup)
    est.clear_cache()
    p1 = est.get_energy_profile("gpt-4o")
    p2 = est.get_energy_profile("gpt-4o")
    assert p1 is p2 is real
    assert calls["n"] == 1  # second call served from cache, no second lookup
