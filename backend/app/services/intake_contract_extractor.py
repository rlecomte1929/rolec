"""[W1-3] Employment contract / offer letter → proposed intake fields, with confidence.

HR uploads the contract they already hold; this proposes the intake the employee would
otherwise retype. AUTHORING-TIME ONLY: it calls an LLM, so nothing on a served request path
may import it (CLAUDE.md, "Generation/serving split"). The only caller is the HR
propose endpoint, and its output is a PROPOSAL — a human confirms before anything is stored.

THE SHAPE IS FLAT snake_case, NOT the nested CaseDraftDTO.
`case_assignments.intake_draft` holds the v2 wizard's flat draft; the nested
`relocationBasics/employeeProfile/...` shape is what `intake_draft_to_case_draft`
explicitly cannot read, and storing it is the exact T18 production failure recorded there
("stored verbatim, echoed back by GET, and unreadable here"). So the keys below are drawn
from `RECOGNISED_INTAKE_KEYS` rather than chosen, and a test asserts they stay a subset of
it — otherwise a field we propose could be silently dropped at submit time.

GDPR (CLAUDE.md, "Data minimisation"). `mask_pii` is MANDATORY before the prompt and is
applied here. Be precise about what that does and does not buy: it redacts phone, IBAN,
passport, SSN/D-number, national ID and email, so those never reach the sub-processor. It
does NOT redact an uncued personal name, and it cannot — the employee's name and salary are
the fields this feature exists to read, so they DO reach OpenAI, a DPA-covered sub-processor
registered in docs/security/PRIV-004_sub-processor_register.md. That is a deliberate,
documented transfer, not an oversight. Never log the OCR text or the extraction.

CONFIDENCE IS THE MODEL'S, AND IT IS ADVISORY. It orders the review queue; it is not a
threshold anything auto-accepts on. There is no confidence at which a field is written
without a human pressing confirm.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date as _date
from typing import Any, Dict, Optional

from .llm_client import complete
from .pii_masker import mask_pii, safe_log_text  # noqa: F401  (safe_log_text for callers)

log = logging.getLogger(__name__)

_MAX_CHARS = 24_000  # a contract is longer than a receipt; still bounded

# MUST stay a subset of backend.intake_draft_to_case_draft.RECOGNISED_INTAKE_KEYS.
# A key outside it is stored and then silently ignored by the submit guard.
PROPOSED_FIELDS = (
    "full_name",
    "nationality",
    "job_title",
    "salary_band",
    "contract_type",
    "contract_start",
    "target_date",
    "origin_city",
    "origin_country",
    "dest_city",
    "dest_country",
)

_FIELD_DESCRIPTIONS = {
    "full_name": "The employee's full name as written on the contract.",
    "nationality": "The employee's nationality as an ISO 3166-1 alpha-2 code (e.g. VE, ES).",
    "job_title": "The job title / role named in the contract.",
    "salary_band": "Gross annual salary with its currency, verbatim (e.g. '58000 EUR').",
    "contract_type": "One of: permanent, fixed_term, assignment, intra_company_transfer.",
    "contract_start": "Employment start date as ISO YYYY-MM-DD.",
    "target_date": "Intended relocation / arrival date as ISO YYYY-MM-DD, if stated separately.",
    "origin_city": "City the employee is moving FROM.",
    "origin_country": "Country moving FROM, ISO 3166-1 alpha-2.",
    "dest_city": "City of the work location they are moving TO.",
    "dest_country": "Country of the work location, ISO 3166-1 alpha-2.",
}

_SYSTEM = (
    "You extract relocation-intake fields from the text of an employment contract or offer "
    "letter. Return ONLY what the document actually states. If a field is not present, return "
    "null for its value and 0 for its confidence — never guess, never infer a country from a "
    "currency or a city from an employer name. Confidence is 0.0-1.0 and expresses how "
    "directly the document states the field: 1.0 when it is written verbatim, lower when you "
    "had to interpret. Some identifiers may appear redacted as [PHONE], [EMAIL], [PASSPORT] "
    "and similar; treat those as absent."
)


def _field_schema() -> Dict[str, Any]:
    props = {
        name: {
            "type": "object",
            "properties": {
                "value": {"type": ["string", "null"], "description": _FIELD_DESCRIPTIONS[name]},
                "confidence": {"type": "number", "description": "0.0-1.0; 0 when absent."},
            },
            "required": ["value", "confidence"],
            "additionalProperties": False,
        }
        for name in PROPOSED_FIELDS
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(PROPOSED_FIELDS),
        "additionalProperties": False,
    }


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_COUNTRY = re.compile(r"^[A-Za-z]{2}$")


def _clean_value(field: str, raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    # A model that "cannot find it" sometimes says so in prose instead of returning null.
    if value.lower() in {"null", "none", "n/a", "unknown", "not stated", "not specified"}:
        return None
    if field in ("nationality", "origin_country", "dest_country"):
        return value.upper() if _ISO_COUNTRY.match(value) else None
    if field in ("contract_start", "target_date"):
        head = value[:10]
        if not _ISO_DATE.match(head):
            return None
        # Structure is not validity: '2026-13-01' matches the pattern and is not a date.
        # A start date of month 13 would be stored, shown to HR as a reading, and confirmed.
        try:
            _date.fromisoformat(head)
        except ValueError:
            return None
        return head
    return value


def _clean_confidence(raw: Any) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    return max(0.0, min(1.0, float(raw)))


def normalise_extraction(result: Any) -> Dict[str, Dict[str, Any]]:
    """LLM output → {field: {value, confidence}} for every PROPOSED_FIELD.

    Pure, so the cleaning rules are testable without an LLM. A field whose value does not
    survive cleaning is reported as absent with confidence 0 — never as a rejected string
    the reviewer might mistake for a real reading.
    """
    result = result if isinstance(result, dict) else {}
    out: Dict[str, Dict[str, Any]] = {}
    for field in PROPOSED_FIELDS:
        entry = result.get(field)
        entry = entry if isinstance(entry, dict) else {}
        value = _clean_value(field, entry.get("value"))
        confidence = _clean_confidence(entry.get("confidence")) if value is not None else 0.0
        out[field] = {"value": value, "confidence": round(confidence, 3)}
    return out


def empty_extraction() -> Dict[str, Dict[str, Any]]:
    return {f: {"value": None, "confidence": 0.0} for f in PROPOSED_FIELDS}


async def extract_intake_fields(ocr_text: str) -> Dict[str, Dict[str, Any]]:
    """OCR markdown of a contract/offer → {field: {value, confidence}}.

    Fail-soft: returns every field empty when there is nothing to do (no text, no API key,
    or any error). HR then sees an empty proposal and fills it in by hand, which is strictly
    better than a 500 on a document that simply did not parse.
    """
    if not (ocr_text or "").strip():
        return empty_extraction()
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        log.info("OPENAI_API_KEY unset — intake contract extraction disabled")
        return empty_extraction()

    masked = mask_pii(ocr_text)[:_MAX_CHARS]  # MANDATORY before the LLM (GDPR)
    try:
        result = await complete(system=_SYSTEM, user=masked, schema=_field_schema())
    except Exception as exc:
        log.warning("extract_intake_fields: LLM call failed err=%s", exc)
        return empty_extraction()
    return normalise_extraction(result)


def proposal_to_draft_patch(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Confirmed {field: value-or-{value,...}} → the flat snake_case patch to store.

    Drops blanks rather than writing empty strings, matching intake_draft_to_case_draft's
    contract: an absent key leaves any existing value alone, an empty string overwrites good
    data with nothing. Unknown keys are dropped — a caller cannot smuggle arbitrary keys
    into the stored draft through the confirm body.
    """
    patch: Dict[str, Any] = {}
    for field in PROPOSED_FIELDS:
        raw = fields.get(field)
        if isinstance(raw, dict):
            raw = raw.get("value")
        value = _clean_value(field, raw)
        if value is not None:
            patch[field] = value
    return patch
