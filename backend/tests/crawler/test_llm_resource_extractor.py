"""CRAWL-01 / AIQ-1094 — tests for the LLM-backed resource extractor fallback.

No network, no key: `llm_client.complete_text` is monkeypatched. Async is driven
via `asyncio.run` (this repo has no pytest-asyncio — mirrors test_llm_client_text.py).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import llm_client  # noqa: E402
from backend.crawler.chunkers.chunker import Chunk  # noqa: E402
from backend.crawler.config.models import CrawlSource  # noqa: E402
from backend.crawler.extractors import llm_resource_extractor as ext  # noqa: E402
from backend.crawler.extractors.models import StagedResourceCandidate  # noqa: E402


def _chunk(text: str, idx: int = 0) -> Chunk:
    return Chunk(
        chunk_index=idx,
        heading_path="Living in Lisbon > Healthcare",
        chunk_text=text,
        chunk_hash=f"h{idx}",
        source_url="https://gov.pt/health",
        page_title="Healthcare for newcomers",
        country_code="PT",
        city_name="Lisbon",
    )


def _source() -> CrawlSource:
    return CrawlSource(
        source_name="Lisboa Câmara",
        base_url="https://gov.pt",
        country_code="PT",
        country_name="Portugal",
        city_name="Lisbon",
        trust_tier="T1",
        content_domain="healthcare",
    )


def _run(chunks):
    return asyncio.run(
        ext.extract_resource_candidates_llm(
            chunks=chunks,
            source=_source(),
            source_url="https://gov.pt/health",
            page_title="Healthcare for newcomers",
        )
    )


def test_happy_path_returns_llm_candidate_and_masks_pii(monkeypatch):
    """One valid resource → one StagedResourceCandidate with the LLM method,
    a clamped confidence, and mask_pii applied to the chunk text before egress."""
    masked_calls: list[str] = []
    real_mask = ext.mask_pii

    def spy_mask(text: str) -> str:
        masked_calls.append(text)
        return real_mask(text)

    monkeypatch.setattr(ext, "mask_pii", spy_mask)

    captured: dict = {}

    async def fake_complete_text(*, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["kwargs"] = kwargs
        return json.dumps(
            {
                "resources": [
                    {
                        "title": "Registering with a local health centre",
                        "summary": "How newcomers register at a Centro de Saúde.",
                        "body": "Bring your residence certificate and NIF to the local "
                        "Centro de Saúde to register and receive a user number. "
                        "Registration is free and unlocks subsidised public care.",
                        "category_key": "healthcare",
                        "confidence_score": 1.4,  # out of range → must clamp to 1.0
                        "tags": ["health", "registration", "sns"],
                    }
                ]
            }
        )

    monkeypatch.setattr(llm_client, "complete_text", fake_complete_text)

    out = _run([_chunk("Email maria@example.com to book. Phone +351 912 345 678.")])

    assert len(out) == 1
    cand = out[0]
    assert isinstance(cand, StagedResourceCandidate)
    assert cand.extraction_method == "llm_structured_extraction"
    assert cand.category_key == "healthcare"
    assert cand.country_code == "PT"
    assert cand.source_url == "https://gov.pt/health"
    assert cand.title and cand.body
    # confidence clamped into [0, 1]
    assert 0.0 < cand.confidence_score <= 1.0
    assert cand.confidence_score == 1.0

    # mask_pii ran on the chunk text BEFORE the LLM, and the raw PII never
    # reached the prompt.
    assert masked_calls, "mask_pii was not called"
    assert "maria@example.com" not in captured["user"]
    assert "+351 912 345 678" not in captured["user"]
    # JSON-mode requested
    assert captured["kwargs"].get("json_object") is True
    # CRAWL-03: provenance records the real model that was sent (not 'auto'), and it
    # matches the model actually passed to complete_text.
    assert cand.provenance["llm_model"] == llm_client._OPENAI_DEFAULT_MODEL
    assert cand.provenance["llm_model"] != "auto"
    assert captured["kwargs"].get("model") == llm_client._OPENAI_DEFAULT_MODEL


def test_malformed_json_returns_empty_without_raising(monkeypatch):
    async def fake_complete_text(*, system, user, **kwargs):
        return "Sorry, I cannot help with that."  # not JSON, no array

    monkeypatch.setattr(llm_client, "complete_text", fake_complete_text)
    out = _run([_chunk("Some dense prose about living in Lisbon.")])
    assert out == []


def test_llm_exception_returns_empty(monkeypatch):
    async def boom(*, system, user, **kwargs):
        raise RuntimeError("openai: insufficient_quota")

    monkeypatch.setattr(llm_client, "complete_text", boom)
    out = _run([_chunk("Prose that would otherwise be extracted.")])
    assert out == []


def test_empty_chunks_short_circuits_without_llm(monkeypatch):
    called = {"n": 0}

    async def fake_complete_text(*, system, user, **kwargs):
        called["n"] += 1
        return "[]"

    monkeypatch.setattr(llm_client, "complete_text", fake_complete_text)
    assert _run([]) == []
    assert called["n"] == 0  # no LLM call when there are no chunks


def test_invalid_category_falls_back_to_domain_default(monkeypatch):
    async def fake_complete_text(*, system, user, **kwargs):
        return json.dumps(
            {
                "resources": [
                    {
                        "title": "Public transport passes",
                        "body": "Buy a Navegante card at any metro station to use buses, "
                        "trams and the metro across Lisbon for a flat monthly fee.",
                        "category_key": "totally_made_up_category",  # invalid → default
                        "confidence_score": 0.7,
                    }
                ]
            }
        )

    monkeypatch.setattr(llm_client, "complete_text", fake_complete_text)
    out = _run([_chunk("Transport info.")])
    assert len(out) == 1
    # source.content_domain == 'healthcare' → default category for this source
    assert out[0].category_key == "healthcare"
    assert out[0].confidence_score == 0.7
