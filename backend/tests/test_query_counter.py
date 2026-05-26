"""
Tests for AUDIT-B7 / PERF-5 query counter.
"""
from __future__ import annotations

import contextvars
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

# Avoid contaminating the real module-level engine: each test creates its own
# in-memory SQLite engine and rebinds the listener-flag for installation.


def test_query_counter_counts_executes_and_resets_per_request(monkeypatch, caplog):
    """
    Two requests against the same app:
    - request A runs 3 SELECTs → middleware logs count=3
    - request B runs 1 SELECT  → middleware logs count=1 (does NOT carry over)
    """
    # Re-import the module fresh so the install-once flag starts False.
    import importlib
    from backend.app.services import query_counter as qc_mod
    importlib.reload(qc_mod)

    engine = create_engine("sqlite:///:memory:")
    qc_mod.install_query_counter(engine)

    app = FastAPI()
    app.add_middleware(qc_mod.QueryCountMiddleware, threshold=10)

    @app.get("/a")
    def endpoint_a():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT 2"))
            conn.execute(text("SELECT 3"))
        return {"count_seen": qc_mod.current_count()}

    @app.get("/b")
    def endpoint_b():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"count_seen": qc_mod.current_count()}

    client = TestClient(app)

    with caplog.at_level(logging.DEBUG, logger="backend.app.services.query_counter"):
        ra = client.get("/a")
        rb = client.get("/b")

    assert ra.status_code == 200
    assert rb.status_code == 200
    # The handler observes its own count before the middleware reads it.
    assert ra.json()["count_seen"] == 3
    assert rb.json()["count_seen"] == 1

    # Middleware emits a log line per request — find both.
    messages = [r.message for r in caplog.records]
    a_log = next(m for m in messages if "GET /a" in m)
    b_log = next(m for m in messages if "GET /b" in m)
    assert "count=3" in a_log
    assert "count=1" in b_log
    assert "status=OK" in a_log  # 3 <= threshold 10
    assert "status=OK" in b_log


def test_query_counter_logs_warning_above_threshold(monkeypatch, caplog):
    """20 queries against a threshold of 5 → WARNING with status=OVER."""
    import importlib
    from backend.app.services import query_counter as qc_mod
    importlib.reload(qc_mod)

    engine = create_engine("sqlite:///:memory:")
    qc_mod.install_query_counter(engine)

    app = FastAPI()
    app.add_middleware(qc_mod.QueryCountMiddleware, threshold=5)

    @app.get("/spammy")
    def spammy():
        with engine.connect() as conn:
            for _ in range(20):
                conn.execute(text("SELECT 1"))
        return {"ok": True}

    client = TestClient(app)
    with caplog.at_level(logging.WARNING, logger="backend.app.services.query_counter"):
        r = client.get("/spammy")
    assert r.status_code == 200

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    msg = warnings[0].message
    assert "count=20" in msg
    assert "threshold=5" in msg
    assert "status=OVER" in msg


def test_query_counter_off_flag_silences_listener(monkeypatch):
    """RELOPASS_QUERY_COUNTER_OFF=1 means install is a no-op."""
    import importlib
    from backend.app.services import query_counter as qc_mod
    importlib.reload(qc_mod)
    monkeypatch.setenv("RELOPASS_QUERY_COUNTER_OFF", "1")

    engine = create_engine("sqlite:///:memory:")
    qc_mod.install_query_counter(engine)

    # Run a query; counter should NOT increment (listener never attached).
    qc_mod.reset_count()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    assert qc_mod.current_count() == 0


def test_current_count_outside_request_returns_zero(monkeypatch):
    """Calling current_count() with no ContextVar set returns 0 (not LookupError)."""
    import importlib
    from backend.app.services import query_counter as qc_mod
    importlib.reload(qc_mod)

    # Fresh contextvar — nothing set yet
    new_ctx = contextvars.Context()
    result = new_ctx.run(qc_mod.current_count)
    assert result == 0
