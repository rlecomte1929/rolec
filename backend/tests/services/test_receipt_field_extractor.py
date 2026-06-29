"""AIQ-1149 — receipt_field_extractor: structured expense fields from OCR text.

The LLM is mocked (no network). Sync tests drive the async service via asyncio.run.
Deliberately does NOT set DATABASE_URL at import (the AIQ-1090 test-pollution lesson).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import backend.app.services.receipt_field_extractor as rfe


def test_extracts_and_normalises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def _fake_complete(*, system, user, schema, **k):
        # messy values that must be normalised
        return {"vendor_name": "  Hotel Adlon ", "amount": "129.50", "currency": "eur", "date": "2026-06-01T10:00"}

    monkeypatch.setattr(rfe, "complete", _fake_complete)
    out = asyncio.run(rfe.extract_expense_fields("Receipt text ..."))
    assert out == {"vendor_name": "Hotel Adlon", "amount": 129.5, "currency": "EUR", "date": "2026-06-01"}


def test_mask_pii_runs_before_the_llm(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    order: list[str] = []

    def _spy_mask(text: str) -> str:
        order.append("mask")
        return "MASKED"

    async def _spy_complete(*, system, user, schema, **k):
        order.append("llm")
        assert user == "MASKED"  # the masked text, not the raw OCR
        return {"vendor_name": "X", "amount": 1, "currency": "EUR", "date": "2026-06-01"}

    monkeypatch.setattr(rfe, "mask_pii", _spy_mask)
    monkeypatch.setattr(rfe, "complete", _spy_complete)
    asyncio.run(rfe.extract_expense_fields("card 4242 4242 ... employee John Doe"))
    assert order == ["mask", "llm"]


def test_fail_soft_paths(monkeypatch):
    # empty text -> {}
    assert asyncio.run(rfe.extract_expense_fields("")) == {}
    # no key -> {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert asyncio.run(rfe.extract_expense_fields("text")) == {}
    # LLM error -> {}
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    async def _boom(*, system, user, schema, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(rfe, "complete", _boom)
    assert asyncio.run(rfe.extract_expense_fields("text")) == {}


def test_bad_values_normalise_to_none(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    async def _weird(*, system, user, schema, **k):
        return {"vendor_name": "", "amount": "not-a-number", "currency": "euros", "date": "yesterday"}

    monkeypatch.setattr(rfe, "complete", _weird)
    out = asyncio.run(rfe.extract_expense_fields("text"))
    assert out == {"vendor_name": None, "amount": None, "currency": None, "date": None}


def test_pure_no_db_imports():
    src = Path(rfe.__file__).read_text()
    for forbidden in ("import sqlalchemy", "from sqlalchemy", "supabase", "from ..database", "from ...database"):
        assert forbidden not in src
