"""E-PIPE-2 · OCR → ParsedDocument adapter.

Turns a stored case document into the relopass extraction runtime's input shape
(:class:`backend.relopass.agents.models.ParsedDocument`) plus, for TD documents,
the ``mrz_text`` string the PASSPORT_TD3 / ID_CARD agents take in ``run(...)``.

OCR-engine routing: passport/ID MRZ documents go through
``ocr_passport_extractor.extract_passport`` (GPT-4o vision → PassportExtractionResult
with MRZ lines + identity fields); every other type goes through Mistral Document AI
(``mistral_ocr_client.mistral_ocr_text``, E-PIPE-OCR) for real text. So this adapter:
  - maps a passport OCR result → ParsedDocument (+ mrz_text), and
  - maps general OCR text → ParsedDocument for all other types, and
  - is **fail-soft** throughout: any failure (or an unset MISTRAL_API_KEY) returns an
    empty-but-valid ParsedDocument and records why, so the downstream orchestrator
    (E-PIPE-4) never crashes and the document simply yields no fields.

The vendor calls live in extract_passport / mistral_ocr_client, which govern their
own PII handling (you cannot mask an image you must OCR); this module maps + routes.
"""

from __future__ import annotations

import logging
import re
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
    ocr_engine: str                  # 'gpt4o_passport' | 'mistral_ocr' | 'none'
    ok: bool                         # False when no engine ran / OCR failed (fail-soft)


# ── Pure mappers ──────────────────────────────────────────────────────────────


_FILLER_RUN = re.compile(r"<+")
_TD3_LINE_LEN = 44


def normalize_mrz_filler(line: str, target: int = _TD3_LINE_LEN) -> str:
    """Pad or trim the longest ``<`` filler run so ``line`` is exactly ``target``.

    Vision OCR reads every MRZ *character* correctly but miscounts long runs of the
    ``<`` filler — measured against gpt-4o on a clean TD3 render: line lengths came
    back (42, 45) and (44, 45) on consecutive runs of the same image. ``parse_mrz``
    is strict about the 44-char layout (rightly — it decodes by position), so it
    returned MRZ_FORMAT_UNRECOGNIZED and the passport agent emitted **zero fields**
    despite the OCR having read the document perfectly. ICAO TD3 pads the name field
    to 39 chars and the personal number to 14, so this hits real passports exactly as
    hard as synthetic ones.

    Adjusting filler is information-preserving — ``<`` is padding, not data — and the
    correction is independently verifiable: the ICAO check digits are computed over
    the data characters, so ``parse_mrz`` still rejects anything this gets wrong. That
    is why the fix lives here at the OCR boundary rather than inside ``parse_mrz``:
    the parser's strictness is a feature for every other caller, and only OCR output
    carries this particular noise.
    """
    if not line or len(line) == target:
        return line
    runs = [(m.start(), m.end()) for m in _FILLER_RUN.finditer(line)]
    if not runs:
        return line  # nothing safe to adjust — let parse_mrz reject it
    start, end = max(runs, key=lambda r: r[1] - r[0])
    delta = target - len(line)
    if delta > 0:
        return line[:end] + ("<" * delta) + line[end:]
    trim = min(-delta, end - start)
    return line[: end - trim] + line[end:]


def mrz_text_from_lines(
    mrz_line1: Optional[str], mrz_line2: Optional[str]
) -> Optional[str]:
    """Join the two MRZ lines into the ``mrz_text`` the agents parse, or None if
    either is missing/blank. Filler runs are length-normalised first — see
    ``normalize_mrz_filler``."""
    l1 = (mrz_line1 or "").strip()
    l2 = (mrz_line2 or "").strip()
    if l1 and l2:
        return f"{normalize_mrz_filler(l1)}\n{normalize_mrz_filler(l2)}"
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
    general_ocr: Optional[Callable[[bytes, str], str]] = None,
) -> OcrParseResult:
    """Download a stored document and produce its ParsedDocument (+ mrz_text).

    Fail-soft: any failure (download, OCR, or no engine for the type) returns an
    empty-but-valid ParsedDocument with ``ok=False`` and a logged reason — never
    raises into the caller (mirrors document_extraction_queue's detached contract).

    ``downloader`` / ``passport_ocr`` / ``general_ocr`` are injectable for testing;
    defaults use the Supabase admin client, ocr_passport_extractor.extract_passport,
    and mistral_ocr_client.mistral_ocr_text respectively.
    """
    doc_type = (document_type or _classify(file_name, mime_type)).upper()
    try:
        content = (downloader or _default_downloader)(storage_path)

        if doc_type in _MRZ_DOC_TYPES or doc_type == "PASSPORT":
            result = await (passport_ocr or _default_passport_ocr)(content, mime_type)
            return passport_result_to_parsed_document(
                result, document_id=document_id, case_id=case_id, mime_type=mime_type
            )

        # General OCR (Mistral Document AI) for every non-MRZ type.
        text = (general_ocr or _default_general_ocr)(content, mime_type)
        if not text:
            # No engine ran (MISTRAL_API_KEY unset) or the document was blank.
            log.info(
                "rce_ocr_parser: general OCR returned no text for document_type=%s "
                "(doc=%s) — MISTRAL_API_KEY unset or empty document", doc_type, document_id,
            )
            return OcrParseResult(
                _empty_parsed_document(document_id=document_id, case_id=case_id, mime_type=mime_type),
                None, doc_type, "none", False,
            )
        parsed = ParsedDocument(
            document_id=document_id, case_id=case_id, mime_type=mime_type,
            language=None, text=text, words=(),
        )
        return OcrParseResult(parsed, None, doc_type, "mistral_ocr", True)
    except Exception as exc:  # never raise into the pipeline
        log.warning(
            "rce_ocr_parser failed-soft for doc=%s type=%s: %s", document_id, doc_type, exc
        )
        return OcrParseResult(
            _empty_parsed_document(document_id=document_id, case_id=case_id, mime_type=mime_type),
            None, doc_type, "none", False,
        )


def _classify(file_name: Optional[str], mime_type: Optional[str]) -> str:
    # Reuse the shared heuristic so routing matches the ingest path.
    #
    # [AIQ-1764] Previously imported from `document_extraction_queue`. That made
    # the rce pipeline depend on the module the ownership ruling narrows to OCR
    # ingest — the reason that module is narrowed rather than deleted. Now both
    # paths depend on the neutral classifier module instead of on each other.
    from .document_classifier import classify_document

    return classify_document(file_name, mime_type)


# Two upload paths write into rce.documents, into DIFFERENT storage buckets:
#
#   document_upload_service (immigration)  -> "immigration-documents", uri "{case_id}/{doc_id}.{ext}"
#   case_documents (the roadmap-CTA path)  -> "case-documents",        uri "case-docs/{case}/{key}/..."
#
# rce.documents has no bucket column, but the two prefixes are distinguishable, so the
# stored storage_uri already carries the discriminator. Before this was resolved the
# downloader was hardcoded to the immigration bucket, so every case_documents upload
# 404'd here and was swallowed by parse_stored_document's fail-soft — the document row
# existed, the extraction silently never ran.
#
# Constants are local on purpose: BUCKET_IMMIGRATION_DOCS is already duplicated across
# two service modules, and the "case-documents" constant (_FORM_DOC_BUCKET) lives in a
# ROUTER — a service importing a router is the wrong direction. AIQ-1764 also
# deliberately decoupled this module from document_extraction_queue; importing from it
# again would undo that.
_BUCKET_CASE_DOCUMENTS = "case-documents"
_BUCKET_IMMIGRATION_DOCS = "immigration-documents"
_CASE_DOCS_PREFIX = "case-docs/"


def _bucket_for_storage_path(storage_path: Optional[str]) -> str:
    """The storage bucket a given rce.documents.storage_uri lives in."""
    return (
        _BUCKET_CASE_DOCUMENTS
        if (storage_path or "").startswith(_CASE_DOCS_PREFIX)
        else _BUCKET_IMMIGRATION_DOCS
    )


def _default_downloader(storage_path: str) -> bytes:
    from .supabase_client import get_supabase_admin_client

    bucket = _bucket_for_storage_path(storage_path)
    return get_supabase_admin_client().storage.from_(bucket).download(storage_path)


async def _default_passport_ocr(content: bytes, mime_type: str) -> Any:
    from .ocr_passport_extractor import extract_passport

    return await extract_passport(content, mime_type)


def _default_general_ocr(content: bytes, mime_type: str) -> str:
    from .mistral_ocr_client import mistral_ocr_text

    return mistral_ocr_text(content, mime_type)
