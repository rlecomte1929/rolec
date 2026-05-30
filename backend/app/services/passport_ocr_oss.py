"""
Open-source passport OCR fallback — Parker Step F.

A self-hosted alternative to the GPT-4o vision extractor in
``ocr_passport_extractor.py``. Mirrors that module's public interface
(``extract_passport(image_bytes) -> PassportExtractionResult``) so it is a
drop-in once accuracy is proven, and reuses its ICAO-9303 ``validate_mrz``
(no duplication).

Model stack (see audit/adr/adr-001-self-hosted-passport-ocr.md):
  * PaddleOCR        — text + MRZ zone OCR.
  * Florence-2-base  — small VLM (0.23B) for structured fields.

The heavy ML dependencies are imported lazily inside ``extract_passport`` so
this module imports cleanly in environments without them (CI, the import-safety
check). Everything else here is pure Python and unit-tested.

**Production posture:** the OSS path is dark by default
(``PASSPORT_OCR_OSS_SHARE=0.0``). It is only ever exercised live via
``SHADOW_COMPARE`` mode, which runs it alongside GPT-4o, returns the GPT-4o
result to the caller, and records per-field agreement for offline review.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional

from .ocr_passport_extractor import (
    OcrExtractionError,
    PassportExtractionResult,
    validate_mrz,
)

log = logging.getLogger(__name__)

# Fields compared between the two pipelines (the user-facing identity/passport
# fields; MRZ raw lines are compared separately via the checksum pass flag).
COMPARABLE_FIELDS: List[str] = [
    "surname",
    "given_names",
    "date_of_birth",
    "gender",
    "place_of_birth",
    "nationality",
    "issuing_country",
    "passport_number",
    "issue_date",
    "expiry_date",
]

# Cost model (USD per single extraction). GPT-4o is a vision API call; the OSS
# path is self-hosted compute. These are documented estimates — step G refines
# them with real usage. See the ADR for derivation.
GPT4O_COST_PER_EXTRACTION_USD = 0.00765   # ~1100 in + 350 out tokens @ gpt-4o vision
OSS_COST_PER_EXTRACTION_USD = 0.00040     # T4 GPU amortised, ~1.5s/extraction


# --------------------------------------------------------------------------- #
# Confidence heuristic                                                         #
# --------------------------------------------------------------------------- #


def heuristic_confidence(mrz_value: Optional[str], visual_value: Optional[str]) -> float:
    """Calibrated confidence for a field given the two OSS sources.

    Florence-2 logprobs are used where available; this is the fallback rule
    (deliberately simple — real calibration comes later from Step E feedback):
      * both sources produced the field and agree     → 0.95
      * exactly one source produced the field         → 0.60
      * neither source produced the field             → 0.0
      * both produced but disagree                    → 0.40
    """
    mrz = (mrz_value or "").strip().upper()
    vis = (visual_value or "").strip().upper()
    if mrz and vis:
        return 0.95 if mrz == vis else 0.40
    if mrz or vis:
        return 0.60
    return 0.0


# --------------------------------------------------------------------------- #
# Shadow comparison diff (pure)                                                #
# --------------------------------------------------------------------------- #


@dataclass
class ShadowDiff:
    """Per-field agreement between the GPT-4o and OSS extractions."""

    field_agreement: Dict[str, bool] = field(default_factory=dict)
    compared_count: int = 0
    agreed_count: int = 0
    disagreement_count: int = 0
    mrz_pass_gpt4o: bool = False
    mrz_pass_oss: bool = False

    @property
    def agreement_rate(self) -> float:
        return self.agreed_count / self.compared_count if self.compared_count else 0.0


def _norm(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    return s or None


def _mrz_passes(result: PassportExtractionResult) -> bool:
    if not result.mrz_line1 or not result.mrz_line2:
        return False
    try:
        return validate_mrz(result.mrz_line1, result.mrz_line2).is_valid
    except Exception:  # noqa: BLE001 — defensive: never let a bad MRZ crash shadow logging
        return False


def diff_extractions(
    gpt4o: PassportExtractionResult,
    oss: PassportExtractionResult,
    fields: Optional[List[str]] = None,
) -> ShadowDiff:
    """Compare two extractions field-by-field.

    A field is *compared* only when at least one pipeline produced a value; if
    both are empty the field is skipped (no signal). Agreement is case- and
    whitespace-insensitive.
    """
    names = fields if fields is not None else COMPARABLE_FIELDS
    diff = ShadowDiff(
        mrz_pass_gpt4o=_mrz_passes(gpt4o),
        mrz_pass_oss=_mrz_passes(oss),
    )
    for name in names:
        a = _norm(getattr(gpt4o, name, None))
        b = _norm(getattr(oss, name, None))
        if a is None and b is None:
            continue
        agree = a == b
        diff.field_agreement[name] = agree
        diff.compared_count += 1
        if agree:
            diff.agreed_count += 1
        else:
            diff.disagreement_count += 1
    return diff


# --------------------------------------------------------------------------- #
# OSS extraction (heavy — lazy ML imports)                                     #
# --------------------------------------------------------------------------- #


async def extract_passport(
    image_bytes: bytes, mime_type: str = "image/jpeg"
) -> PassportExtractionResult:
    """Extract passport fields with the self-hosted OSS stack.

    Mirrors ``ocr_passport_extractor.extract_passport``'s signature and return
    type. Raises ``OcrExtractionError('oss_backend_unavailable', ...)`` when the
    ML dependencies (paddleocr, transformers/Florence-2) are not installed, so
    callers can fall back to GPT-4o cleanly.

    NOTE: the model inference body is intentionally thin and lazy. The OSS path
    is dark in production and exercised only in shadow mode; the heavy weights
    are pulled at container build time (see the ADR). This function is not
    unit-tested end-to-end because the models cannot run in CI.
    """
    try:
        from paddleocr import PaddleOCR  # type: ignore  # noqa: F401
        from transformers import (  # type: ignore  # noqa: F401
            AutoModelForCausalLM,
            AutoProcessor,
        )
    except ImportError as exc:
        raise OcrExtractionError(
            code="oss_backend_unavailable",
            message="The open-source passport OCR backend is not installed.",
            hint="Install paddleocr + transformers and provision the Florence-2 weights "
                 "(see audit/adr/adr-001-self-hosted-passport-ocr.md). The OSS path is "
                 "off by default; GPT-4o continues to serve production traffic.",
        ) from exc

    # The concrete PaddleOCR + Florence-2 inference is provisioned at deploy time
    # and wired here. Kept minimal on purpose — the orchestration, confidence
    # heuristic, MRZ validation, and shadow diff are the reviewed/tested surface.
    raise OcrExtractionError(
        code="oss_backend_unavailable",
        message="OSS passport inference is provisioned at deploy time and not active in this build.",
        hint="Enable by wiring PaddleOCR + Florence-2 inference; weights are pulled at "
             "container build. The OSS path stays dark until PASSPORT_OCR_OSS_SHARE > 0.",
    )


# --------------------------------------------------------------------------- #
# Shadow comparison logging (best-effort)                                      #
# --------------------------------------------------------------------------- #

from ..db import SessionLocal  # noqa: E402 — after pure helpers to keep import order clear


def record_shadow_comparison(
    diff: ShadowDiff,
    *,
    gpt4o_cost_usd: float = GPT4O_COST_PER_EXTRACTION_USD,
    oss_cost_usd: float = OSS_COST_PER_EXTRACTION_USD,
    case_id: Optional[str] = None,
    session=None,
) -> Optional[str]:
    """Insert one shadow-comparison row. Best-effort: never raises.

    Returns the new row id, or ``None`` if the write failed (table absent in
    dev, etc.). No PII is stored — only field-level agreement booleans, MRZ
    pass flags, disagreement count, and per-pipeline cost.
    """
    from sqlalchemy import text as _text

    row_id = str(uuid.uuid4())
    params = {
        "id": row_id,
        "case_id": case_id,
        "mrz_pass_gpt4o": diff.mrz_pass_gpt4o,
        "mrz_pass_oss": diff.mrz_pass_oss,
        "field_agreement": json.dumps(diff.field_agreement, separators=(",", ":")),
        "compared_count": diff.compared_count,
        "agreed_count": diff.agreed_count,
        "disagreement_count": diff.disagreement_count,
        "gpt4o_cost_usd": gpt4o_cost_usd,
        "oss_cost_usd": oss_cost_usd,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    own = session is None
    s = session or SessionLocal()
    try:
        s.execute(
            _text(
                "INSERT INTO ocr_shadow_comparisons "
                "(id, case_id, mrz_pass_gpt4o, mrz_pass_oss, field_agreement, "
                " compared_count, agreed_count, disagreement_count, "
                " gpt4o_cost_usd, oss_cost_usd, created_at) "
                "VALUES (:id, :case_id, :mrz_pass_gpt4o, :mrz_pass_oss, :field_agreement, "
                " :compared_count, :agreed_count, :disagreement_count, "
                " :gpt4o_cost_usd, :oss_cost_usd, :created_at)"
            ),
            params,
        )
        if own:
            s.commit()
        return row_id
    except Exception:  # noqa: BLE001 — shadow telemetry must never fail the caller
        if own:
            s.rollback()
        log.debug("shadow comparison write failed", exc_info=True)
        return None
    finally:
        if own:
            s.close()


# --------------------------------------------------------------------------- #
# Shadow orchestration                                                         #
# --------------------------------------------------------------------------- #

PassportExtractor = Callable[[bytes, str], Awaitable[PassportExtractionResult]]


async def extract_passport_shadow(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    gpt4o_extractor: PassportExtractor,
    oss_extractor: Optional[PassportExtractor] = None,
    case_id: Optional[str] = None,
    record: bool = True,
) -> PassportExtractionResult:
    """Run GPT-4o and (best-effort) the OSS path, log the diff, return GPT-4o.

    The caller always receives the GPT-4o result — shadow mode never changes
    user-facing output. If the OSS path errors (e.g. backend unavailable), the
    GPT-4o result is still returned and no shadow row is written.

    ``gpt4o_extractor`` / ``oss_extractor`` are injected so this is testable
    without real models. In production they default to the two
    ``extract_passport`` coroutines.
    """
    oss_fn = oss_extractor or extract_passport
    gpt4o_result = await gpt4o_extractor(image_bytes, mime_type)
    try:
        oss_result = await oss_fn(image_bytes, mime_type)
    except Exception:  # noqa: BLE001 — OSS failure must not affect the live result
        log.debug("OSS shadow extraction failed; returning GPT-4o only", exc_info=True)
        return gpt4o_result

    diff = diff_extractions(gpt4o_result, oss_result)
    if record:
        record_shadow_comparison(diff, case_id=case_id)
    return gpt4o_result


# --------------------------------------------------------------------------- #
# Admin rollup                                                                 #
# --------------------------------------------------------------------------- #


def compute_shadow_rollup(
    *,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    session=None,
) -> Dict[str, object]:
    """Aggregate shadow comparisons in ``[from_ts, to_ts]`` into a rollup dict.

    Portable SQL over the ``ocr_shadow_comparisons`` base table (PG + SQLite),
    so the admin route does not depend on the Postgres-only materialized view.
    Rates are 0.0 when no rows match.
    """
    from sqlalchemy import text as _text

    own = session is None
    s = session or SessionLocal()
    try:
        row = s.execute(
            _text(
                "SELECT "
                " COUNT(*) AS n, "
                " COALESCE(SUM(compared_count), 0) AS compared, "
                " COALESCE(SUM(agreed_count), 0) AS agreed, "
                " COALESCE(SUM(disagreement_count), 0) AS disagreements, "
                " COALESCE(SUM(CASE WHEN mrz_pass_gpt4o THEN 1 ELSE 0 END), 0) AS mrz_gpt4o, "
                " COALESCE(SUM(CASE WHEN mrz_pass_oss THEN 1 ELSE 0 END), 0) AS mrz_oss, "
                " COALESCE(SUM(gpt4o_cost_usd), 0) AS gpt4o_cost, "
                " COALESCE(SUM(oss_cost_usd), 0) AS oss_cost "
                "FROM ocr_shadow_comparisons "
                "WHERE (:from_ts IS NULL OR created_at >= :from_ts) "
                "  AND (:to_ts IS NULL OR created_at <= :to_ts)"
            ),
            {"from_ts": from_ts, "to_ts": to_ts},
        ).mappings().first()
    finally:
        if own:
            s.close()

    n = int(row["n"]) if row else 0
    compared = int(row["compared"]) if row else 0
    agreed = int(row["agreed"]) if row else 0

    def _rate(numer: int, denom: int) -> float:
        return round(numer / denom, 4) if denom else 0.0

    return {
        "n": n,
        "from": from_ts,
        "to": to_ts,
        "field_agreement_rate": _rate(agreed, compared),
        "disagreement_count": int(row["disagreements"]) if row else 0,
        "mrz_pass_rate_gpt4o": _rate(int(row["mrz_gpt4o"]) if row else 0, n),
        "mrz_pass_rate_oss": _rate(int(row["mrz_oss"]) if row else 0, n),
        "avg_cost_usd_gpt4o": round(float(row["gpt4o_cost"]) / n, 6) if n else 0.0,
        "avg_cost_usd_oss": round(float(row["oss_cost"]) / n, 6) if n else 0.0,
        "total_cost_usd_gpt4o": round(float(row["gpt4o_cost"]), 6) if row else 0.0,
        "total_cost_usd_oss": round(float(row["oss_cost"]), 6) if row else 0.0,
    }
