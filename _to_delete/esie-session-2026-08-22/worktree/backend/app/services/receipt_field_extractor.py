"""[AIQ-1149] Structured expense-field extraction from an OCR'd receipt.

A pure follow-up to the general OCR endpoint (AIQ-1148): given the OCR'd markdown of an expense
receipt, mask PII and ask the LLM for {vendor_name, amount, currency, date} so a future expense
form can auto-fill. Fail-soft — returns {} when there's nothing to do (empty text, no key, or any
error); the OCR endpoint still returns the raw text either way.

GDPR (CLAUDE.md): the OCR text may carry the employee's name / card number, so it MUST pass through
mask_pii before the LLM. Never log the OCR text.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .llm_client import complete
from .pii_masker import mask_pii

log = logging.getLogger(__name__)

_MAX_CHARS = 12_000  # cap the masked text fed to the prompt

_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": ["string", "null"], "description": "Merchant / vendor name on the receipt."},
        "amount": {"type": ["number", "null"], "description": "Total amount paid (not subtotals/tax)."},
        "currency": {"type": ["string", "null"], "description": "ISO-4217 currency code, e.g. EUR."},
        "date": {"type": ["string", "null"], "description": "Receipt date as ISO YYYY-MM-DD."},
    },
    "required": ["vendor_name", "amount", "currency", "date"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You extract structured fields from the text of an expense receipt. Return the TOTAL amount paid "
    "(not subtotals or tax lines), the merchant/vendor name, the ISO-4217 currency code, and the receipt "
    "date as ISO YYYY-MM-DD. If a field is not present, return null for it — do not guess."
)


def _clean_str(v: Any) -> Optional[str]:
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s or None


def _clean_amount(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().replace(",", ""))
        except ValueError:
            return None
    return None


def _clean_currency(v: Any) -> Optional[str]:
    s = _clean_str(v)
    if not s:
        return None
    s = s.upper()
    return s if len(s) == 3 and s.isalpha() else None


def _clean_date(v: Any) -> Optional[str]:
    s = _clean_str(v)
    if not s:
        return None
    head = s[:10]
    parts = head.split("-")
    if (
        len(parts) == 3
        and len(parts[0]) == 4 and parts[0].isdigit()
        and parts[1].isdigit() and parts[2].isdigit()
    ):
        return head
    return None


async def extract_expense_fields(ocr_text: str) -> Dict[str, Any]:
    """OCR text of an expense receipt → {vendor_name, amount, currency, date} (any may be None).

    Returns {} when there's nothing to extract (empty text, no OPENAI_API_KEY, or any error) so the
    caller can degrade gracefully.
    """
    if not (ocr_text or "").strip():
        return {}
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        log.info("OPENAI_API_KEY unset — expense field extraction disabled")
        return {}

    masked = mask_pii(ocr_text)[:_MAX_CHARS]  # MANDATORY before the LLM (GDPR)
    try:
        result = await complete(system=_SYSTEM, user=masked, schema=_SCHEMA)
    except Exception as exc:
        log.warning("extract_expense_fields: LLM call failed err=%s", exc)
        return {}
    if not isinstance(result, dict):
        return {}
    return {
        "vendor_name": _clean_str(result.get("vendor_name")),
        "amount": _clean_amount(result.get("amount")),
        "currency": _clean_currency(result.get("currency")),
        "date": _clean_date(result.get("date")),
    }
