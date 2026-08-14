"""Living Areas = 0 regression fix — neighbourhoods are ADVISORY content.

Locks the three-layer bug that rendered the housing category empty on a
Paris→Oslo case (verified root cause):

  * Layer 2 (scorer): a field-poor supplier-shaped row (``city`` forced to the
    destination, no ``avg_rent_2br``) reached ``score()`` and ``None > b_max``
    raised ``TypeError`` → the whole category threw → (0). A shell must now
    score 0, never crash.
  * Layer 2 (engine loop): one raising item blanked the entire category for
    every category. A single bad item must now drop, siblings survive.
  * Layers 1 & 3 (advisory): ``living_areas`` is advisory content, not a vendor
    marketplace. The engine must (a) skip the supplier-registry override and
    (b) bypass ``apply_hr_curation`` — otherwise the ``la-*`` rows are dropped
    against the never-seeded ``service_catalog_items`` masters and the category
    returns ``([], 'hr_pending')`` → (0), even though 5 real Oslo neighbourhoods
    exist in the static dataset.

These assert the FIXED behaviour: on current ``main`` they reproduce the bug
(TypeError / blanked category / hr_pending); after the fix they pass.
"""
from __future__ import annotations

from backend.app.recommendations import engine
from backend.app.recommendations.plugins.base import BasePlugin
from backend.app.recommendations.plugins.living_areas import (
    LivingAreasCriteria,
    LivingAreasPlugin,
)

OSLO = {"destination_city": "Oslo", "destination_country": "NO"}


def _shell(**over):
    """The field-poor registry shell: city forced to destination, no rent/sqm/tags/coords."""
    base = {"item_id": "la-o1", "name": "Frogner", "city": "Oslo",
            "rating": 4.3, "availability_level": "high"}
    base.update(over)
    return base


def _oslo_static_rows():
    return [r for r in LivingAreasPlugin().load_dataset() if r.get("city") == "Oslo"]


# ── Layer 2: scorer hardening ────────────────────────────────────────────────

def test_score_shell_without_rent_scores_zero_not_crash():
    # Was: rent = item.get("avg_rent_2br") -> None; `if rent > b_max` -> TypeError.
    out = LivingAreasPlugin().score(LivingAreasCriteria(**OSLO), _shell())
    assert out["score_raw"] == 0


# ── advisory flag (the core seam) ────────────────────────────────────────────

def test_living_areas_is_advisory_and_base_default_is_not():
    assert LivingAreasPlugin().advisory is True
    # movers/schools/banks inherit the default and keep the gated registry+HR path.
    assert BasePlugin.advisory is False


# ── Layer 2: engine loop resilience (global, all categories) ─────────────────

def test_one_raising_item_does_not_blank_the_category(monkeypatch):
    plugin = engine.get_plugin("living_areas")
    good = {"item_id": "la-o1", "name": "Frogner", "city": "Oslo", "avg_rent_2br": 25000,
            "typical_sqm_range": [70, 100], "tags": {"safety": 8}, "rating": 4.4,
            "availability_level": "high", "lat": 59.9, "lng": 10.7}
    poison = _shell(item_id="poison")
    monkeypatch.setattr(engine, "_load_dataset_with_registry", lambda *a, **k: [good, poison])

    real_score = plugin.score

    def flaky(criteria, item):
        if item.get("item_id") == "poison":
            raise RuntimeError("boom")
        return real_score(criteria, item)

    monkeypatch.setattr(plugin, "score", flaky)

    resp = engine.recommend("living_areas", OSLO)  # must not raise
    ids = [r.item_id for r in resp.recommendations]
    assert "la-o1" in ids and "poison" not in ids


# ── Layer 1: advisory skips the supplier-registry override ───────────────────

def test_advisory_skips_supplier_registry(monkeypatch):
    # A raising sentinel is swallowed by _load_dataset_with_registry's `except: pass`,
    # so record calls instead and assert the registry was never queried.
    calls: list = []

    def _rec(*a, **k):
        calls.append(k.get("service_category"))
        return []

    monkeypatch.setattr(
        "backend.app.services.supplier_registry.search_by_service_destination", _rec
    )
    resp = engine.recommend("living_areas", OSLO)  # no company_id
    assert calls == []  # advisory must not query the supplier registry
    assert len(resp.recommendations) >= 1  # the real Oslo neighbourhoods


# ── Layer 3: advisory bypasses HR curation even with a company_id ────────────

def test_advisory_category_bypasses_hr_curation(monkeypatch):
    monkeypatch.setattr(engine, "_load_dataset_with_registry", lambda *a, **k: _oslo_static_rows())

    def _boom_curation(*a, **k):
        raise AssertionError("apply_hr_curation must not run for an advisory category")

    monkeypatch.setattr(
        "backend.app.services.employee_recommendations_filter.apply_hr_curation", _boom_curation
    )
    resp = engine.recommend("living_areas", OSLO, company_id="co-x")
    assert len(resp.recommendations) >= 1
    assert resp.criteria_echo.get("hr_curation_status") is None
