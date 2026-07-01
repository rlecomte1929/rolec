"""
Executive dashboard — the aggregation service composes existing data into one
payload, each panel soft-failing to {available: false} so a missing table never
500s the dashboard. reliability + nps are honest 'not instrumented' placeholders.
"""
import backend.app.services.exec_overview_service as svc


def test_health_score_from_dashboard():
    dash = {
        "source": "mock",
        "metrics": [
            {"alert": {"firing": False}},
            {"alert": {"firing": True}},
            {"alert": {"firing": False}},
            {"alert": {"firing": False}},
        ],
    }
    out = svc._health_score(dash)
    assert out["available"] is True
    assert out["score"] == 75  # 3 of 4 healthy
    assert out["data_source"] == "mock"


def test_safe_wraps_failures_as_unavailable():
    def boom():
        raise RuntimeError("relation does not exist")

    out = svc._safe(boom)
    assert out["available"] is False
    assert out["data_source"] == "unavailable"


def test_build_overview_composes_all_panels(monkeypatch):
    monkeypatch.setattr(svc, "_growth", lambda: {"available": True, "data_source": "live", "companies": 3})
    monkeypatch.setattr(svc, "_funnel", lambda window: {"available": True, "data_source": "live", "signups": 10})
    monkeypatch.setattr(svc, "_throughput", lambda window: {"available": True, "data_source": "live", "median_days": 42})
    monkeypatch.setattr(svc, "_ai_cost", lambda window: {"available": True, "data_source": "estimated", "total_cost_usd": 1.23})
    monkeypatch.setattr(svc, "_ai_health", lambda: {"available": True, "data_source": "mock", "score": 92})

    out = svc.build_exec_overview(window_days=30)
    assert out["window_days"] == 30
    for panel in ("growth", "funnel", "throughput", "ai_cost", "ai_health", "reliability", "nps"):
        assert panel in out
    assert out["growth"]["companies"] == 3
    # the two un-instrumented panels are honest placeholders
    assert out["reliability"]["available"] is False and out["reliability"]["note"]
    assert out["nps"]["available"] is False and out["nps"]["note"]


def test_one_failing_panel_does_not_break_the_rest(monkeypatch):
    monkeypatch.setattr(svc, "_growth", lambda: (_ for _ in ()).throw(RuntimeError("no table")))
    monkeypatch.setattr(svc, "_funnel", lambda window: {"available": True, "signups": 5})
    monkeypatch.setattr(svc, "_throughput", lambda window: {"available": True})
    monkeypatch.setattr(svc, "_ai_cost", lambda window: {"available": True})
    monkeypatch.setattr(svc, "_ai_health", lambda: {"available": True})

    out = svc.build_exec_overview()
    assert out["growth"]["available"] is False   # soft-failed
    assert out["funnel"]["available"] is True     # unaffected
