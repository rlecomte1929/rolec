"""E-PIPE-2 · OCR → ParsedDocument adapter.

Turns a stored case document into the relopass extraction runtime's input shape
(:class:`backend.relopass.agents.models.ParsedDocument`) plus, for TD documents,
the ``mrz_text`` string the PASSPORT_TD3 / ID_CARD agents take in ``run(...)``.

OCR-engine reality (2026-06-10): the only document OCR wired in prod is
``ocr_passport_extractor.extract_passport`` (GPT-4o vision → PassportExtractionResult
with MRZ lines + identity fields). There is **no** general OCR engine yet — Mistral
Document AI is the stated direction (audit 2026-04-15) but unintegrated. So this
adapter:
  - maps a passport OCR result → ParsedDocument (+ mrz_text), and
  - is **fail-soft** for every other type: returns an empty-but-valid ParsedDocument
    and records why, so the downstream orchestrator (E-PIPE-4) never crashes and the
    document simply yields no fields until a general OCR engine lands.

No new LLM/vendor call is added here (the GPT-4o call lives in extract_passport,
which already governs its own PII handling); this module only maps + orchestrates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Tuple
from uuid import UUID

from backend.relopass.agents.models import ParsedDocument

log = logging.getLogger(__name__)

# Document-type codes whose identity comes from an ICAO 9303 MRZ — these carry an
# mrz_text the passport_td3 / id_card agents consume.
_MRZ_DOC_TYPES = {"PASSPORT", "PASSPORT_TD3", "ID_CARD"}


@dataclass(frozen=True)
class OcrParseResult:
    """What the OCR adapter hands the extraction orchestrator (E-PIPE-4)."""

    parsed_document: ParsedDocument
    mrz_text: Optional[str]          # for TD docs; None otherwise
    document_type: str               # PASSPORT / CONTRACT / OTHER / ...
    ocr_engine: str                  # 'gpt4o_passport' | 'none'
    ok: bool                         # False when no engine ran / OCR failed (fail-soft)


# ── Pure mappers ──────────────────────────────────────────────────────────────


def mrz_text_from_lines(
    mrz_line1: Optional[str], mrz_line2: Optional[str]
) -> Optional[str]:
    """Join the two MRZ lines into the ``mrz_text`` the agents parse, or None if
    either is missing/blank."""
    l1 = (mrz_line1 or "").strip()
    l2 = (mrz_line2 or "").strip()
    if l1 and l2:
        return f"{l1}\n{l2}"
    return None


def _passport_text(result: Any) -> str:
    """A readable text body for the ParsedDocument. extract_passport returns
    structured fields, not raw OCR text, so synthesise a stable summary (MRZ +
    key fields) — the passport/id_card agents use mrz_text, not this; it exists so
    ParsedDocument.text is populated and human-inspectable."""
    lines = []
    if getattr(result, "mrz_line1", None) and getattr(result, "mrz_line2", None):
        lines.append("MRZ:")
        lines.append(str(result.mrz_line1))
        lines.append(str(result.mrz_line2))
    for label, attr in (
        ("surname", "surname"), ("given_names", "given_names"),
        ("date_of_birth", "date_of_birth"), ("nationality", "nationality"),
        ("passport_number", "passport_number"), ("expiry_date", "expiry_date"),
    ):
        val = getattr(result, attr, None)
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


def passport_result_to_parsed_document(
    result: Any,
    *,
    document_id: UUID,
    case_id: Optional[UUID] = None,
    mime_type: Optional[str] = None,
) -> OcrParseResult:
    """Map a PassportExtractionResult → ParsedDocument + mrz_text."""
    parsed = ParsedDocument(
        document_id=document_id,
        case_id=case_id,
        mime_type=mime_type,
        language=None,
        text=_passport_text(result),
        words=(),  # extract_passport returns structured fields, not bbox words
    )
    return OcrParseResult(
        parsed_document=parsed,
        mrz_text=mrz_text_from_lines(
            getattr(result, "mrz_line1", None), getattr(result, "mrz_line2", None)
        ),
        document_type="PASSPORT",
        ocr_engine="gpt4o_passport",
        ok=True,
    )


def _empty_parsed_document(
    *, document_id: UUID, case_id: Optional[UUID], mime_type: Optional[str]
) -> ParsedDocument:
    return ParsedDocument(
        document_id=document_id, case_id=case_id, mime_type=mime_type,
        language=None, text="", words=(),
    )


# ── Orchestration ─────────────────────────────────────────────────────────────


async def parse_stored_document(
    *,
    document_id: UUID,
    storage_path: str,
    mime_type: str,
    case_id: Optional[UUID] = None,
    file_name: Optional[str] = None,
    document_type: Optional[str] = None,
    downloader: Optional[Callable[[str], bytes]] = None,
    passport_ocr: Optional[Callable[[bytes, str], Awaitable[Any]]] = None,
) -> OcrParseResult:
    """Download a stored document and produce its ParsedDocument (+ mrz_text).

    Fail-soft: any failure (download, OCR, or no engine for the type) returns an
    empty-but-valid ParsedDocument with ``ok=False`` and a logged reason — never
    raises into the caller (mirrors document_extraction_queue's detached contract).

    ``downloader`` / ``passport_ocr`` are injectable for testing; defaults use the
    Supabase admin client and ocr_passport_extractor.extract_passport.
    """
    doc_type = (document_type or _classify(file_name, mime_type)).upper()
    try:
        if doc_type not in _MRZ_DOC_TYPES and doc_type != "PASSPORT":
            # No general OCR engine yet (Mistral unintegrated). Fail-soft empty doc.
            log.info(
                "rce_ocr_parser: no OCR engine for document_type=%s (doc=%s) — "
                "empty ParsedDocument until general OCR lands", doc_type, document_id,
            )
            return OcrParseResult(
                _empty_parsed_document(document_id=document_id, case_id=case_id, mime_type=mime_type),
                None, doc_type, "none", False,
            )

        content = (downloader or _default_downloader)(storage_path)
        ocr = passport_ocr or _default_passport_ocr
        result = await ocr(content, mime_type)
        return passport_result_to_parsed_document(
            result, document_id=document_id, case_id=case_id, mime_type=mime_type
        )
    except Exception as exc:  # never raise into the pipeline
        log.warning(
            "rce_ocr_parser failed-soft for doc=%s type=%s: %s", document_id, doc_type, exc
        )
        return OcrParseResult(
            _empty_parsed_document(document_id=document_id, case_id=case_id, mime_type=mime_type),
            None, doc_type, "none", False,
        )


def _classify(file_name: Optional[str], mime_type: Optional[str]) -> str:
    # Reuse the existing intake heuristic so passport routing matches the queue.
    from .document_extraction_queue import classify_document

    return classify_document(file_name, mime_type)


def _default_downloader(storage_path: str) -> bytes:
    from .supabase_client import get_supabase_admin_client

    return get_supabase_admin_client().storage.from_("immigration-documents").download(storage_path)


async def _default_passport_ocr(content: bytes, mime_type: str) -> Any:
    from .ocr_passport_extractor import extract_passport

    return await extract_passport(content, mime_type)
