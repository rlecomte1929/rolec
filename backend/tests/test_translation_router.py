"""Parker-I — translation router: auth gate, cache hit/miss, entity round-trip.

Drives the real router over a minimal FastAPI app. Auth is overridden via
dependency_overrides; persistence uses a shared in-memory SQLite engine; the DeepL/NLLB
adapters are monkeypatched to a deterministic fake (no network/keys).
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.db import Base  # noqa: E402
from backend.app import models  # noqa: E402,F401 — registers TranslationCache
from backend.app.routers import translation  # noqa: E402
from backend.app.auth_deps import get_current_user  # noqa: E402
from backend.app.services import translation_deepl, translation_nllb  # noqa: E402
from backend.app.services.translation_types import AdapterResult  # noqa: E402


def _fake_translate(text, src, tgt):
    # Tags the language but preserves the original tokens verbatim, so entity names
    # (capitalised proper nouns) survive a round-trip unchanged.
    return AdapterResult(
        text=f"({tgt}) {text}",
        provider="deepl",
        model_version="deepl-test",
        cost_usd=round(len(text) * 1e-6, 6),
        quality_score=None,
    )


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(translation, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(translation_deepl, "translate", _fake_translate)
    monkeypatch.setattr(translation_nllb, "translate", _fake_translate)

    app = FastAPI()
    app.include_router(translation.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "role": "EMPLOYEE"}
    return TestClient(app)


def _body(**over):
    base = {"text": "Welcome to Berlin", "src": "en", "tgt": "de", "domain": "comm"}
    base.update(over)
    return base


def test_requires_authentication():
    # No dependency override → real get_current_user → 401 without a token.
    app = FastAPI()
    app.include_router(translation.router)
    resp = TestClient(app).post("/api/translate", json=_body())
    assert resp.status_code == 401


def test_first_call_miss_second_call_hit(client):
    first = client.post("/api/translate", json=_body())
    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert first.json()["cost_usd"] > 0

    second = client.post("/api/translate", json=_body())
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["cost_usd"] == 0.0
    assert second.json()["text"] == first.json()["text"]


def test_roundtrip_preserves_entity_names(client):
    src_text = "Welcome to Berlin with ReloPass"
    forward = client.post("/api/translate", json=_body(text=src_text, src="en", tgt="de"))
    assert forward.status_code == 200
    de_text = forward.json()["text"]

    back = client.post("/api/translate", json=_body(text=de_text, src="de", tgt="en"))
    assert back.status_code == 200
    en_text = back.json()["text"]

    for entity in ("Berlin", "ReloPass"):
        assert entity in de_text
        assert entity in en_text


def test_validation_rejects_empty_text(client):
    resp = client.post("/api/translate", json=_body(text=""))
    assert resp.status_code == 422


def test_validation_rejects_bad_domain(client):
    resp = client.post("/api/translate", json=_body(domain="bogus"))
    assert resp.status_code == 422


def test_unavailable_provider_returns_503(client, monkeypatch):
    from backend.app.services.translation_types import TranslationUnavailable

    def _down(text, src, tgt):
        raise TranslationUnavailable("down")

    monkeypatch.setattr(translation_deepl, "translate", _down)
    monkeypatch.setattr(translation_nllb, "translate", _down)
    resp = client.post("/api/translate", json=_body(text="something new entirely"))
    assert resp.status_code == 503


def test_rate_limit_bucket_applies_to_translate_path():
    """SEC-004 path bucket: /api/translate is per-user limited at TRANSLATE_LIMIT."""
    from backend.app import rate_limits

    rate_limits.reset_path_limit_storage()
    user_key = "user:abc"
    allowed = 0
    for _ in range(120):
        if rate_limits.path_limit("/api/translate", "1.2.3.4", user_key) is None:
            allowed += 1
        else:
            break
    assert allowed == 60  # TRANSLATE_LIMIT = "60/minute"
    rate_limits.reset_path_limit_storage()
