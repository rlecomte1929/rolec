"""Tests for E-PIPE-6 pipeline worker — the chain orchestration + fail-soft.

Stage functions are monkeypatched on the worker module, so this tests the wiring
(order, status aggregation, isolation) without DB / OCR / LLM. Async driven via
asyncio.run (no pytest-asyncio in repo).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from backend.app.services import rce_pipeline_worker as worker


def _patch_chain(monkeypatch, *, doc, ocr=None, extract_status="ok", persons=0,
                 contradictions=0, ocr_raises=False, extract_raises=False,
                 detect_raises=False, resolve_raises=False, calls=None):
    calls = calls if calls is not None else []

    monkeypatch.setattr(worker, "_load_rce_document", lambda eng, rid: doc)

    async def _parse(**kw):
        calls.append("ocr")
        if ocr_raises:
            raise RuntimeError("ocr boom")
        return ocr

    async def _extract(**kw):
        calls.append("extract")
        if extract_raises:
            raise RuntimeError("extract boom")
        return SimpleNamespace(status=extract_status)

    def _resolve(case_id, *, engine):
        calls.append("resolve")
        if resolve_raises:
            raise RuntimeError("resolve boom")
        return persons

    def _detect(case_id, *, engine):
        calls.append("detect")
        if detect_raises:
            raise RuntimeError("detect boom")
        return [object()] * contradictions

    monkeypatch.setattr(worker, "parse_stored_document", _parse)
    monkeypatch.setattr(worker, "run_extraction_for_document", _extract)
    monkeypatch.setattr(worker, "resolve_case_persons", _resolve)
    monkeypatch.setattr(worker, "run_contradiction_detection_for_case", _detect)
    return calls


def _doc():
    return {
        "document_id": uuid4(), "case_id": uuid4(), "mime_type": "image/jpeg",
        "storage_uri": "c/x.jpg", "original_filename": "passport.jpg",
        "document_type_code": "PASSPORT_TD3",
    }


def test_happy_chain_runs_all_stages_in_order():
    calls = []
    monkey = _MP()
    _patch_chain(monkey, doc=_doc(), ocr=SimpleNamespace(ok=True),
                 extract_status="ok", persons=2, contradictions=3, calls=calls)
    rid = str(uuid4())
    res = asyncio.run(worker.process_rce_document(rid, engine="ENG"))
    monkey.undo()
    assert calls == ["ocr", "extract", "resolve", "detect"]
    assert res.ocr_ok is True
    assert res.extraction_status == "ok"
    assert res.persons_resolved == 2
    assert res.contradictions_detected == 3
    assert res.errors == []


def test_document_not_found_short_circuits():
    monkey = _MP()
    monkey.setattr(worker, "_load_rce_document", lambda eng, rid: None)
    res = asyncio.run(worker.process_rce_document(str(uuid4()), engine="ENG"))
    monkey.undo()
    assert res.extraction_status == "no_document"
    assert res.ocr_ok is False


def test_ocr_failure_is_failsoft_and_detection_still_runs():
    calls = []
    monkey = _MP()
    _patch_chain(monkey, doc=_doc(), ocr_raises=True, persons=1, contradictions=0, calls=calls)
    res = asyncio.run(worker.process_rce_document(str(uuid4()), engine="ENG"))
    monkey.undo()
    # OCR raised → recorded as an error, extraction skipped, but resolve + detect ran
    assert any(e.startswith("ocr:") for e in res.errors)
    assert "detect" in calls and "resolve" in calls
    assert res.ocr_ok is False


def test_extraction_failure_isolated_detection_still_runs():
    calls = []
    monkey = _MP()
    _patch_chain(monkey, doc=_doc(), ocr=SimpleNamespace(ok=True),
                 extract_raises=True, contradictions=1, calls=calls)
    res = asyncio.run(worker.process_rce_document(str(uuid4()), engine="ENG"))
    monkey.undo()
    assert res.extraction_status == "failed"
    assert any(e.startswith("extract:") for e in res.errors)
    assert calls[-1] == "detect"
    assert res.contradictions_detected == 1


def test_never_raises_even_if_every_stage_fails():
    monkey = _MP()
    _patch_chain(monkey, doc=_doc(), ocr_raises=True, extract_raises=True,
                 resolve_raises=True, detect_raises=True)
    res = asyncio.run(worker.process_rce_document(str(uuid4()), engine="ENG"))
    monkey.undo()
    assert isinstance(res, worker.PipelineResult)
    assert len(res.errors) >= 2  # ocr + resolve + detect at least


# Minimal monkeypatch helper (these are plain functions, not pytest fixtures, so we
# manage setattr/undo manually to keep the module-level patching explicit).
class _MP:
    def __init__(self):
        self._saved = []

    def setattr(self, obj, name, val):
        self._saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, val)

    def undo(self):
        for obj, name, old in reversed(self._saved):
            setattr(obj, name, old)
