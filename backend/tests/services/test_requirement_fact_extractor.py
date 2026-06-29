"""AIQ-1090 (P4-01) — requirement_fact_extractor: pure LLM extraction service.

The LLM (and any network) is mocked. Tests are sync and drive the async service via
asyncio.run, so they don't depend on pytest-asyncio being configured locally.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

# NB: deliberately does NOT set DATABASE_URL — this is a pure-service test (no DB), and
# setting it at import time pollutes the shared env for the rest of the suite.
import backend.app.services.requirement_fact_extractor as rfe


def _ok_json(rtype: str = "document", conf=0.9) -> str:
    return (
        '{"facts": [{"text": "A valid passport is required.", '
        f'"requirement_type": "{rtype}", '
        '"source_quote": "You must hold a valid passport.", '
        f'"confidence_score": {conf}}}]}}'
    )


def test_happy_path_returns_populated_fact(monkeypatch):
    async def _fake_complete(*, system, user, json_object=False):
        assert json_object is True
        return _ok_json()

    monkeypatch.setattr(rfe, "complete_text", _fake_complete)
    facts = asyncio.run(
        rfe.extract_requirement_facts("https://gov.example/visa", corridor="FR-DE", content="raw source text")
    )
    assert len(facts) == 1
    f = facts[0]
    assert f.text and f.requirement_type == "document" and f.corridor == "FR-DE"
    assert 0.0 < f.confidence_score <= 1.0
    assert f.source_url == "https://gov.example/visa"
    assert f.extraction_method == "llm"
    assert f.source_quote  # populated here


def test_mask_pii_called_before_llm(monkeypatch):
    """The GDPR guard: fetched content must be masked BEFORE it reaches the LLM."""
    order: list[str] = []

    def _spy_mask(text: str) -> str:
        order.append("mask")
        return "MASKED"

    async def _spy_complete(*, system, user, json_object=False):
        order.append("llm")
        # the prompt must carry the masked text, not the raw input
        assert "MASKED" in user
        assert "secret-raw-content" not in user
        return _ok_json()

    monkeypatch.setattr(rfe, "mask_pii", _spy_mask)
    monkeypatch.setattr(rfe, "complete_text", _spy_complete)
    asyncio.run(rfe.extract_requirement_facts("https://x", corridor="FR-DE", content="secret-raw-content"))
    assert order == ["mask", "llm"], "mask_pii must run before the LLM call"


def test_malformed_json_returns_empty(monkeypatch):
    async def _bad(*, system, user, json_object=False):
        return "this is not json {{{"

    monkeypatch.setattr(rfe, "complete_text", _bad)
    facts = asyncio.run(rfe.extract_requirement_facts("https://x", content="text"))
    assert facts == []


def test_bad_type_coerced_and_confidence_clamped(monkeypatch):
    async def _weird(*, system, user, json_object=False):
        return (
            '{"facts": ['
            '{"text": "Pay a 100 EUR fee.", "requirement_type": "MONEY", "confidence_score": 5},'
            '{"text": "Apply within 30 days.", "requirement_type": "timeline", "confidence_score": 0},'
            '{"text": "", "requirement_type": "document", "confidence_score": 0.8}'
            ']}'
        )

    monkeypatch.setattr(rfe, "complete_text", _weird)
    facts = asyncio.run(rfe.extract_requirement_facts("https://x", content="text"))
    # empty-text fact dropped → 2 remain
    assert len(facts) == 2
    assert facts[0].requirement_type == "other"  # MONEY → other
    assert facts[0].confidence_score == 1.0       # 5 clamped to 1.0
    assert facts[1].requirement_type == "timeline"
    assert facts[1].confidence_score == 0.5       # 0 → default (never 0)


def test_service_is_pure_no_db_imports():
    src = Path(rfe.__file__).read_text()
    for forbidden in ("import sqlalchemy", "from sqlalchemy", "supabase", "from ..database", "from ...database", "from backend.database"):
        assert forbidden not in src, f"pure extractor must not reference {forbidden!r}"
