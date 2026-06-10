"""Tests for E-PIPE-2 OCR → ParsedDocument adapter.

Pure mappers + the fail-soft orchestrator. The orchestrator is async; driven via
asyncio.run (pytest-asyncio is not installed in this repo). OCR + storage are
injected, so no GPT-4o / Supabase calls.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from backend.relopass.agents.models import ParsedDocument
from backend.app.services.rce_ocr_parser import (
    OcrParseResult,
    mrz_text_from_lines,
    parse_stored_document,
    passport_result_to_parsed_document,
)

# A valid ICAO TD3 passport MRZ (the canonical UTO specimen).
_MRZ1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
_MRZ2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def _passport_result():
    return SimpleNamespace(
        mrz_line1=_MRZ1, mrz_line2=_MRZ2,
        surname="ERIKSSON", given_names="ANNA MARIA",
        date_of_birth="1974-08-12", nationality="UTO",
        passport_number="L898902C3", expiry_date="2012-04-15",
    )


# ── mrz_text_from_lines ────────────────────────────────────────────────────────


def test_mrz_text_joins_two_lines():
    assert mrz_text_from_lines(_MRZ1, _MRZ2) == f"{_MRZ1}\n{_MRZ2}"


def test_mrz_text_none_when_a_line_missing():
    assert mrz_text_from_lines(_MRZ1, None) is None
    assert mrz_text_from_lines("", _MRZ2) is None
    assert mrz_text_from_lines(None, None) is None


# ── passport_result_to_parsed_document (Criterion 1) ───────────────────────────


def test_passport_result_yields_parsed_document_with_text_and_mrz():
    doc_id = uuid4()
    out = passport_result_to_parsed_document(_passport_result(), document_id=doc_id, mime_type="image/jpeg")
    assert isinstance(out.parsed_document, ParsedDocument)
    assert out.parsed_document.document_id == doc_id
    assert "MRZ:" in out.parsed_document.text
    assert "ERIKSSON" in out.parsed_document.text
    # the mrz_text is the two lines, exactly what passport_td3/id_card agents parse
    assert out.mrz_text == f"{_MRZ1}\n{_MRZ2}"
    assert out.document_type == "PASSPORT"
    assert out.ocr_engine == "gpt4o_passport"
    assert out.ok is True


# ── parse_stored_document orchestration ────────────────────────────────────────


def test_parse_stored_passport_happy_path():
    async def _fake_ocr(content, mime_type):
        assert content == b"img-bytes"
        return _passport_result()

    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/x.jpg", mime_type="image/jpeg",
        document_type="PASSPORT",
        downloader=lambda path: b"img-bytes",
        passport_ocr=_fake_ocr,
    ))
    assert out.ok is True
    assert out.mrz_text == f"{_MRZ1}\n{_MRZ2}"
    assert "ERIKSSON" in out.parsed_document.text


def test_parse_stored_general_type_is_failsoft_empty(  # Criterion 2 (no general OCR engine yet)
):
    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/contract.pdf", mime_type="application/pdf",
        document_type="CONTRACT",
        downloader=lambda path: b"never-used",
        passport_ocr=None,
    ))
    # A valid ParsedDocument is still returned (empty), fail-soft, no MRZ.
    assert isinstance(out.parsed_document, ParsedDocument)
    assert out.parsed_document.text == ""
    assert out.mrz_text is None
    assert out.ok is False
    assert out.ocr_engine == "none"


def test_parse_stored_ocr_failure_is_failsoft(  # Criterion 3
):
    async def _boom_ocr(content, mime_type):
        raise RuntimeError("OCR engine down")

    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/x.jpg", mime_type="image/jpeg",
        document_type="PASSPORT",
        downloader=lambda path: b"img-bytes",
        passport_ocr=_boom_ocr,
    ))
    assert out.ok is False
    assert out.mrz_text is None
    assert isinstance(out.parsed_document, ParsedDocument)


def test_parse_stored_download_failure_is_failsoft():
    def _boom_dl(path):
        raise RuntimeError("storage 500")

    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/x.jpg", mime_type="image/jpeg",
        document_type="PASSPORT",
        downloader=_boom_dl,
    ))
    assert out.ok is False
