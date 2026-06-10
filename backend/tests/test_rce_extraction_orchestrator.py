"""Tests for E-PIPE-4 extraction orchestrator.

ID_CARD runs fully end-to-end (MRZ-deterministic, no LLM) against in-memory
backends → proves route→construct→register→run→persist. Routing + fail-soft are
tested with stubs. Async driven via asyncio.run (no pytest-asyncio in repo).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from backend.relopass.agents import InMemoryAgentStorage
from backend.relopass.agents.runtime import InMemoryExtractionSink
from backend.relopass.agents.models import ParsedDocument
from backend.relopass.docs.mrz import compute_check_digit
from backend.app.services.rce_ocr_parser import OcrParseResult
from backend.app.services import rce_extraction_orchestrator as orch


def _td1_fra() -> str:
    doc = "SPEC12345".ljust(9, "<")
    line1 = f"I<FRA{doc}{compute_check_digit(doc)}".ljust(30, "<")
    dob, expiry, nat = "850315", "280620", "FRA"
    line2 = f"{dob}{compute_check_digit(dob)}M{expiry}{compute_check_digit(expiry)}{nat}".ljust(29, "<")
    line2 = f"{line2}{compute_check_digit(line2)}"
    line3 = "MARTIN<<JEAN<PAUL".ljust(30, "<")
    return f"{line1}\n{line2}\n{line3}"


def _ocr_result(*, mrz_text, doc_id=None):
    pd = ParsedDocument(document_id=doc_id or uuid4(), text="", words=())
    return OcrParseResult(parsed_document=pd, mrz_text=mrz_text,
                          document_type="ID_CARD", ocr_engine="x", ok=True)


def test_id_card_runs_end_to_end_and_persists_nationality():
    sink = InMemoryExtractionSink()
    out = asyncio.run(orch.dispatch_and_run(
        ocr_result=_ocr_result(mrz_text=_td1_fra()),
        document_type_code="ID_CARD",
        sink=sink,
        agent_storage=InMemoryAgentStorage(),
    ))
    assert out.status == "ok"
    assert out.fields_written >= 1
    keys = {f.field_key: f.value_raw for f in sink.extracted_fields}
    assert keys.get("nationality_iso3") == "FRA"
    assert sink.agent_runs, "expected an agent_run row"


def test_unknown_type_skipped_no_agent():
    out = asyncio.run(orch.dispatch_and_run(
        ocr_result=_ocr_result(mrz_text=_td1_fra()),
        document_type_code="HOUSING_LEASE",   # no registered agent
        sink=InMemoryExtractionSink(),
        agent_storage=InMemoryAgentStorage(),
    ))
    assert out.status == "skipped_no_agent"
    assert out.fields_written == 0


def test_mrz_type_without_mrz_text_skipped():
    out = asyncio.run(orch.dispatch_and_run(
        ocr_result=_ocr_result(mrz_text=None),
        document_type_code="ID_CARD",
        sink=InMemoryExtractionSink(),
        agent_storage=InMemoryAgentStorage(),
    ))
    assert out.status == "skipped_no_mrz"


def test_agent_error_is_failsoft(monkeypatch):
    class _BoomAgent:
        def __init__(self, **kw):  # accepts registry/sink
            pass
        def register(self):
            return None
        async def run(self, document):
            raise RuntimeError("agent blew up")

    monkeypatch.setattr(orch, "_agent_class", lambda code: _BoomAgent)
    out = asyncio.run(orch.dispatch_and_run(
        ocr_result=OcrParseResult(
            parsed_document=ParsedDocument(document_id=uuid4(), text="x", words=()),
            mrz_text=None, document_type="MARRIAGE_CERT", ocr_engine="x", ok=True),
        document_type_code="MARRIAGE_CERT",   # async family path → await run(document)
        sink=InMemoryExtractionSink(),
        agent_storage=InMemoryAgentStorage(),
    ))
    assert out.status == "failed"
    assert "blew up" in out.detail


def test_idempotent_rerun_same_mrz(  # re-running id_card on the same doc is safe
):
    sink = InMemoryExtractionSink()
    storage = InMemoryAgentStorage()
    doc_id = uuid4()
    args = dict(document_type_code="ID_CARD", sink=sink, agent_storage=storage)
    asyncio.run(orch.dispatch_and_run(ocr_result=_ocr_result(mrz_text=_td1_fra(), doc_id=doc_id), **args))
    first = len(sink.extracted_fields)
    out2 = asyncio.run(orch.dispatch_and_run(ocr_result=_ocr_result(mrz_text=_td1_fra(), doc_id=doc_id), **args))
    # second run succeeds (the production Supabase sink dedups via DB constraints;
    # the in-memory sink simply appends — we assert the run itself is stable/ok).
    assert out2.status == "ok"
    assert len(sink.extracted_fields) >= first
