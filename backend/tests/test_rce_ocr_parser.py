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
    _bucket_for_storage_path,
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


def test_parse_stored_general_type_uses_mistral_ocr():  # E-PIPE-OCR happy path
    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/marriage.pdf", mime_type="application/pdf",
        document_type="MARRIAGE_CERT",
        downloader=lambda path: b"pdf-bytes",
        general_ocr=lambda content, mime: "Certificate of Marriage\nAnna & Erik",
    ))
    assert out.ok is True
    assert out.ocr_engine == "mistral_ocr"
    assert "Certificate of Marriage" in out.parsed_document.text
    assert out.mrz_text is None  # general docs carry no MRZ
    assert out.document_type == "MARRIAGE_CERT"


def test_parse_stored_general_type_no_text_is_failsoft_empty():  # MISTRAL_API_KEY unset / blank doc
    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/contract.pdf", mime_type="application/pdf",
        document_type="CONTRACT",
        downloader=lambda path: b"never-used",
        general_ocr=lambda content, mime: "",  # engine disabled → empty
    ))
    # A valid ParsedDocument is still returned (empty), fail-soft, no MRZ.
    assert isinstance(out.parsed_document, ParsedDocument)
    assert out.parsed_document.text == ""
    assert out.mrz_text is None
    assert out.ok is False
    assert out.ocr_engine == "none"


def test_parse_stored_general_ocr_failure_is_failsoft():  # Mistral API error → fail-soft
    def _boom(content, mime):
        raise RuntimeError("Mistral 503")

    out = asyncio.run(parse_stored_document(
        document_id=uuid4(), storage_path="c/diploma.pdf", mime_type="application/pdf",
        document_type="DIPLOMA",
        downloader=lambda path: b"pdf-bytes",
        general_ocr=_boom,
    ))
    assert out.ok is False
    assert out.ocr_engine == "none"
    assert isinstance(out.parsed_document, ParsedDocument)


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


# ── Storage-bucket resolution ─────────────────────────────────────────────────
#
# Every test above injects `downloader=`, which is exactly why the real one went
# unexercised: `_default_downloader` was hardcoded to the immigration bucket, so
# every upload from the case_documents path 404'd and was swallowed by the
# fail-soft above. These assert the pure resolver instead, so no Supabase is needed.


def test_case_docs_prefix_resolves_to_the_case_documents_bucket():
    """The roadmap-CTA upload path: case_documents.py writes
    case-docs/{case}/{key}/{ts}_{file} into the `case-documents` bucket."""
    path = "case-docs/356442ac-ea69-490e-995c-6652bec959e2/passport_copy/20260810T101112_passport.pdf"
    assert _bucket_for_storage_path(path) == "case-documents"


def test_immigration_path_still_resolves_to_the_immigration_bucket():
    """document_upload_service.py writes {case_id}/{doc_id}.{ext} into
    `immigration-documents`. This is the pre-existing behaviour and must not move."""
    assert _bucket_for_storage_path("8e1677d3-d30f-470f-a2a4-feb7ebfb9132/9eda25ef.pdf") == (
        "immigration-documents"
    )


def test_bucket_resolution_defaults_safely_on_empty_input():
    """storage_uri is nullable in rce.documents — never raise on it."""
    assert _bucket_for_storage_path("") == "immigration-documents"
    assert _bucket_for_storage_path(None) == "immigration-documents"


def test_case_docs_prefix_must_be_anchored():
    """A path merely CONTAINING 'case-docs/' is not the case-documents shape —
    only a prefix is, so this must not over-match."""
    assert _bucket_for_storage_path("archive/case-docs/x.pdf") == "immigration-documents"
