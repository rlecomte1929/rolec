"""
AIQ-1700 — HR curation runs over the FULL ranked list, and the top_n slice runs after.

`recommend()` used to do `matching[:top_n]` and only then call `apply_hr_curation`, so
curation was a filter over the top-N rather than a selector over the candidates: a
supplier HR had approved but that ranked below the cut was discarded before the
allowlist was ever consulted. Measured on real prod inputs, a company approving 3 of the
12 Singapore movers rendered 1 — and only 4 of 78 companies approve everything, so 74
were exposed.

Two things this must NOT break, both verified below because both were live behaviour:
  * `top_n` still caps the master picks (curating first must not blow past it), and
  * HR's custom vendors are still never truncated — they are appended after the masters
    and, before this change, the slice ran before they existed.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app import db as app_db  # noqa: E402
from backend.app.recommendations import engine  # noqa: E402
from backend.app.recommendations.registry import get_plugin  # noqa: E402
from backend.app.services import (  # noqa: E402
    service_catalog,
    supplier_registry,
    vendor_curation,
)

_CRITERIA = {
    "origin_city": "Amsterdam",
    "destination_city": "Singapore",
    "destination_country": "SG",
    "move_type": "international",
}
_COMPANY = "company-1"
# 12 candidates named so the ranking is deterministic: rating descends with the index,
# so mover-11 and mover-12 are the two that fall outside a top_n of 10.
_N = 12


def _supplier_id(i: int) -> str:
    return f"sup-{i:02d}"


def _master_id(i: int) -> str:
    return f"m-{i:02d}"


@pytest.fixture
def wired(monkeypatch):
    """Stub every DB-backed input of recommend(); the ranking/curation logic is real."""
    monkeypatch.setattr(app_db, "SessionLocal", MagicMock(), raising=False)
    monkeypatch.setattr(engine, "_load_cluster_cache", lambda *a, **k: None)
    # No static dataset — the registry rows alone are the candidates.
    monkeypatch.setattr(get_plugin("movers"), "load_dataset", lambda: [], raising=False)
    monkeypatch.setattr(
        supplier_registry, "search_by_service_destination",
        lambda *a, **k: [
            {
                "item_id": _supplier_id(i), "name": f"Mover {i:02d}", "city": "Singapore",
                "rating": 5.0 - i * 0.1, "rating_count": 100 - i,
                "availability_level": "high", "confidence": 85,
                "_source": "supplier_registry", "_preferred_partner": False,
                "specialization_tags": [],
            }
            for i in range(1, _N + 1)
        ],
        raising=False,
    )
    monkeypatch.setattr(
        service_catalog, "external_ids_for_supplier_ids", lambda cat, ids: set(),
        raising=False,
    )

    calls = {"batched": 0, "per_item": 0}

    def _batched(category, item_ids):
        calls["batched"] += 1
        return {
            str(i): {"id": _master_id(int(str(i).split("-")[1])), "external_id": str(i)}
            for i in item_ids if str(i).startswith("sup-")
        }

    def _per_item(category, item_id):  # must NOT be reached on the hot path any more
        calls["per_item"] += 1
        return None

    monkeypatch.setattr(
        service_catalog, "find_masters_by_supplier_or_external_ids", _batched,
        raising=False,
    )
    monkeypatch.setattr(
        service_catalog, "find_master_by_supplier_or_external_id", _per_item,
        raising=False,
    )

    def _approve(master_ids, order=None, customs=()):
        sels = [
            {"master_item_id": m, "selected": True,
             "display_order": (order or {}).get(m, i)}
            for i, m in enumerate(master_ids)
        ]
        sels += [
            {"master_item_id": None, "selected": True, "display_order": 90 + i,
             "custom_item_json": {"name": name}, "id": f"cust-{i}"}
            for i, name in enumerate(customs)
        ]
        monkeypatch.setattr(vendor_curation, "list_curation", lambda **k: sels,
                            raising=False)

    return _approve, calls


def _names(resp):
    return [r.name for r in resp.recommendations]


def test_approved_supplier_ranked_below_top_n_still_renders(wired):
    """Criterion 1 — the reported bug. 3 approved, 2 of them ranked 11th/12th."""
    approve, _ = wired
    approve([_master_id(1), _master_id(11), _master_id(12)])

    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    # Before AIQ-1700 this returned ONLY 'Mover 01' — the other two were cut before
    # curation ran, even though 9 slots were free.
    assert _names(resp) == ["Mover 01", "Mover 11", "Mover 12"]
    assert resp.criteria_echo.get("hr_curation_status") is None


def test_top_n_still_caps_the_master_picks(wired):
    """Criterion 2 — curating first must not blow past top_n."""
    approve, _ = wired
    approve([_master_id(i) for i in range(1, _N + 1)])

    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    assert len(_names(resp)) == 10
    assert _names(resp)[0] == "Mover 01"


def test_hr_pending_still_fires_on_zero_approvals(wired, monkeypatch):
    """Criterion 3 — the empty-state contract, including the record_demand side effect."""
    approve, _ = wired
    approve([])
    recorded = {}
    import backend.app.services.employee_demand as employee_demand
    monkeypatch.setattr(employee_demand, "record_demand",
                        lambda **kw: recorded.update(kw), raising=False)

    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    assert _names(resp) == []
    assert resp.criteria_echo.get("hr_curation_status") == "hr_pending"
    assert recorded.get("category") == "movers"


def test_display_order_still_wins_over_engine_rank(wired):
    """Criterion 4 — AIQ-1530 survives the reordering."""
    approve, _ = wired
    approve(
        [_master_id(1), _master_id(2), _master_id(3)],
        order={_master_id(3): 0, _master_id(2): 1, _master_id(1): 2},
    )

    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    assert _names(resp) == ["Mover 03", "Mover 02", "Mover 01"]


def test_custom_vendors_are_not_truncated_by_the_slice(wired):
    """Criterion 5 — the regression a naive `items[:top_n]` would have introduced.

    Customs are appended after the masters. Before AIQ-1700 the slice ran first, so a
    company with 10 approved masters + 2 customs legitimately received 12 items; that
    must still hold now the slice runs last.
    """
    approve, _ = wired
    approve([_master_id(i) for i in range(1, _N + 1)],
            customs=("Bob's Removals", "Acme Moving"))

    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    names = _names(resp)
    assert len(names) == 12, "10 masters capped by top_n + 2 customs never truncated"
    assert names[-2:] == ["Bob's Removals", "Acme Moving"]


def test_master_resolution_is_batched(wired):
    """Criterion 6 — O(1) queries, not one per candidate.

    Curating the full list instead of the top_n slice is only safe because the master
    lookup was batched first; per-item resolution would be ~80 queries per category on
    registry-heavy datasets.
    """
    approve, calls = wired
    approve([_master_id(i) for i in range(1, _N + 1)])

    engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    assert calls["batched"] == 1
    assert calls["per_item"] == 0


def test_uncurated_path_still_slices_to_top_n(wired):
    """No company_id (admin debug / internal jobs) — behaviour must be unchanged."""
    approve, calls = wired
    approve([])

    resp = engine.recommend("movers", _CRITERIA, top_n=3, company_id=None)

    assert len(_names(resp)) == 3
    assert resp.criteria_echo.get("hr_curation_status") is None
    assert calls["batched"] == 0, "no curation → no master lookup at all"


# ── AIQ-1694·4 — production-time audit logging is a side-effect on recommend() ──

def test_recommend_logs_a_deduped_production_audit_record(wired, monkeypatch):
    """recommend() writes ONE 'produced' audit record (masked input + output), keyed by
    a stable id, and its OUTPUT is unchanged by the logging."""
    approve, _ = wired
    approve([_master_id(1), _master_id(2), _master_id(3)])  # a real (non-empty) recommendation
    calls = []
    from backend.app.services import ai_decision_logger as adl
    monkeypatch.setattr(adl, "record_ai_recommendation",
                        lambda **kw: calls.append(kw) or "row-1")
    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)

    assert _names(resp) == ["Mover 01", "Mover 02", "Mover 03"], "output unaffected by logging"
    assert len(calls) == 1
    kw = calls[0]
    assert kw["feature"] == "supplier_reco:movers"
    assert kw["skip_if_exists"] is True          # dedup on re-compute
    assert kw["company_id"] == _COMPANY
    assert kw["recommendation_id"]               # stable id present
    assert kw["ai_output"]["category"] == "movers"


def test_recommend_does_not_log_without_a_company(wired, monkeypatch):
    calls = []
    from backend.app.services import ai_decision_logger as adl
    monkeypatch.setattr(adl, "record_ai_recommendation", lambda **kw: calls.append(kw))
    # company_id=None → uncurated path returns top_n items, but there is no tenant to audit.
    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=None)
    assert resp.recommendations                   # non-empty result...
    assert calls == []                            # ...but no audit write


def test_recommend_survives_an_audit_logging_failure(wired, monkeypatch):
    approve, _ = wired
    approve([_master_id(1), _master_id(2)])
    from backend.app.services import ai_decision_logger as adl

    def boom(**kw):
        raise RuntimeError("audit backend down")

    monkeypatch.setattr(adl, "record_ai_recommendation", boom)
    resp = engine.recommend("movers", _CRITERIA, top_n=10, company_id=_COMPANY)
    assert resp.recommendations, "a logging failure must never break the recommendation"
