"""CRAWL-02 / AIQ-1094-FU — tests for the LLM resource-extractor fallback wiring.

Exercises `_crawl_source` with every external call mocked in the pipeline
namespace (no network, no DB, no LLM). Verifies the fallback only fires when the
rule-based extractor recovered nothing AND the flag is on AND the per-run cap is
not hit, and that LLM candidates flow through the same dedup + staging path.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.crawler import pipeline  # noqa: E402
from backend.crawler.config.models import CrawlConfig, CrawlSource  # noqa: E402
from backend.crawler.chunkers.chunker import Chunk  # noqa: E402
from backend.crawler.extractors.models import StagedResourceCandidate  # noqa: E402


def _source() -> CrawlSource:
    return CrawlSource(
        source_name="Lisboa Câmara",
        base_url="https://gov.pt",
        country_code="PT",
        country_name="Portugal",
        city_name="Lisbon",
        content_domain="healthcare",
    )


def _chunk() -> Chunk:
    return Chunk(
        chunk_index=0,
        heading_path="",
        chunk_text="Dense prose with no clear heading structure about healthcare.",
        chunk_hash="h0",
        source_url="https://gov.pt",
        page_title="Health",
    )


def _llm_candidate() -> StagedResourceCandidate:
    return StagedResourceCandidate(
        country_code="PT",
        title="Registering with a health centre",
        category_key="healthcare",
        body="Bring your residence certificate and NIF to the local Centro de Saúde.",
        source_url="https://gov.pt",
        source_name="Lisboa Câmara",
        trust_tier="T1",
        confidence_score=0.7,
        extraction_method="llm_structured_extraction",
        provenance={"source_url": "https://gov.pt"},
    )


def _wire(monkeypatch, *, rule_based, llm_candidates, dup=False):
    """Patch every external call _crawl_source makes; return the llm-call counter."""
    monkeypatch.setattr(
        pipeline, "fetch_page",
        lambda *a, **k: SimpleNamespace(success=True, final_url="https://gov.pt", content="<html></html>"),
    )
    monkeypatch.setattr(pipeline, "parse_html", lambda *a, **k: SimpleNamespace(page_title="Health"))
    monkeypatch.setattr(pipeline, "write_document", lambda *a, **k: "doc-1")
    monkeypatch.setattr(pipeline, "chunk_document", lambda *a, **k: [_chunk()])
    monkeypatch.setattr(pipeline, "write_chunk", lambda *a, **k: "chunk-1")
    monkeypatch.setattr(pipeline, "extract_resource_candidates", lambda *a, **k: list(rule_based))
    monkeypatch.setattr(pipeline, "extract_event_candidates", lambda *a, **k: [])
    monkeypatch.setattr(pipeline, "check_resource_duplicate", lambda *a, **k: (dup, None))
    monkeypatch.setattr(pipeline, "write_resource_candidate", lambda *a, **k: None)

    calls: list = []

    async def fake_llm(*a, **k):
        calls.append(1)
        return list(llm_candidates)

    monkeypatch.setattr(pipeline, "extract_resource_candidates_llm", fake_llm)
    return calls


def _run(flag=False, preset_calls=0, max_per_run=25):
    config = CrawlConfig(
        sources=[], llm_fallback_enabled=flag, llm_fallback_max_per_run=max_per_run
    )
    report = pipeline.PipelineReport(run_id="run-1")
    report.llm_fallback_calls = preset_calls
    pipeline._crawl_source(_source(), config, "run-1", report)
    return report


def test_fallback_fires_when_rulebased_empty_and_flag_on(monkeypatch):
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()])
    report = _run(flag=True)
    assert len(calls) == 1                      # LLM was invoked
    assert report.llm_fallback_calls == 1
    assert report.resources_staged_llm == 1
    assert report.resources_staged == 1         # grand total includes the LLM one


def test_fallback_not_called_when_rulebased_has_candidates(monkeypatch):
    rb = [_llm_candidate()]  # any non-empty rule-based result
    calls = _wire(monkeypatch, rule_based=rb, llm_candidates=[_llm_candidate()])
    report = _run(flag=True)
    assert calls == []                          # cost control: no LLM call
    assert report.llm_fallback_calls == 0
    assert report.resources_staged_llm == 0


def test_fallback_disabled_by_default(monkeypatch):
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()])
    report = _run(flag=False)                   # default OFF
    assert calls == []
    assert report.llm_fallback_calls == 0


def test_env_override_enables_fallback(monkeypatch):
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()])
    monkeypatch.setenv("CRAWLER_LLM_FALLBACK", "1")
    report = _run(flag=False)                   # config flag off, env override on
    assert len(calls) == 1
    assert report.resources_staged_llm == 1


def test_configurable_cap_respected(monkeypatch):
    # CRAWL-03: the cap is now a CrawlConfig field. At the (low) configured cap → no call.
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()])
    report = _run(flag=True, preset_calls=2, max_per_run=2)
    assert calls == []                          # cap reached → no further LLM calls
    assert report.resources_staged_llm == 0


def test_default_cap_is_25(monkeypatch):
    # Default unchanged: field defaults to 25; under it the fallback still fires.
    assert CrawlConfig(sources=[]).llm_fallback_max_per_run == 25
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()])
    report = _run(flag=True, preset_calls=24)   # under the default 25 → fires
    assert len(calls) == 1
    assert report.resources_staged_llm == 1


def test_llm_candidate_goes_through_dedup(monkeypatch):
    calls = _wire(monkeypatch, rule_based=[], llm_candidates=[_llm_candidate()], dup=True)
    report = _run(flag=True)
    assert len(calls) == 1                       # LLM ran
    assert report.duplicates_detected == 1       # but the candidate was a duplicate
    assert report.resources_staged_llm == 0      # so nothing staged
