"""
Fixture payloads for policy processing E2E tests.

Service slice: visa_support, temporary_housing, home_search, school_search,
household_goods_shipment (via Layer-2 benefit_key mapping during normalization).
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.services.policy_document_intake import (
    DOC_TYPE_ASSIGNMENT_POLICY,
    DOC_TYPE_POLICY_SUMMARY,
    SCOPE_LONG_TERM,
)

# ---------------------------------------------------------------------------
# A — Summary-only upload (weak narrative; expect draft, not publishable)
# ---------------------------------------------------------------------------

SUMMARY_ONLY_RAW_TEXT = """
Acme Global Mobility Program — Summary

This document describes our general approach to supporting employees who may relocate.
Benefits may be considered on a case-by-case basis where appropriate and subject to approval.
The company aims to be reasonable when supporting international assignments.
"""


def summary_only_document_updates() -> Dict[str, Any]:
    return {
        "processing_status": "classified",
        "detected_document_type": DOC_TYPE_POLICY_SUMMARY,
        "detected_policy_scope": SCOPE_LONG_TERM,
        "raw_text": SUMMARY_ONLY_RAW_TEXT.strip(),
    }


def summary_only_clauses() -> List[Dict[str, Any]]:
    return [
        {
            "clause_type": "scope",
            "section_label": "Overview",
            "raw_text": "The company supports mobile employees in principle; details vary by situation.",
            "normalized_hint_json": {},
            "confidence": 0.72,
        },
        {
            "clause_type": "unknown",
            "section_label": "General",
            "raw_text": "Support may be available subject to discretion and internal approval when needed.",
            "normalized_hint_json": {},
            "confidence": 0.55,
        },
    ]


# ---------------------------------------------------------------------------
# C — Structured assignment policy (caps + exclusion; expect publish-ready path)
# ---------------------------------------------------------------------------

STRUCTURED_POLICY_RAW_TEXT = """
Structured Relocation Policy — Engineering Co

1. Immigration: Company reimburses work visa and work permit fees up to USD 4000 per assignment.
2. Temporary housing: Up to USD 5000 per month for temporary accommodation for eligible long-term assignments.
3. Home search: Lump sum home search assistance up to USD 2500.
4. Education: International school tuition support capped at USD 15000 per child per year.
5. Shipment: Household goods international shipment reimbursed up to USD 10000.
6. Exclusions: Personal income tax return preparation fees are not reimbursable.
"""


def structured_assignment_document_updates() -> Dict[str, Any]:
    return {
        "processing_status": "classified",
        "detected_document_type": DOC_TYPE_ASSIGNMENT_POLICY,
        "detected_policy_scope": SCOPE_LONG_TERM,
        "raw_text": STRUCTURED_POLICY_RAW_TEXT.strip(),
    }


def structured_policy_clauses() -> List[Dict[str, Any]]:
    return [
        {
            "clause_type": "benefit",
            "section_label": "Immigration",
            "raw_text": "Work visa and work permit fees reimbursed up to USD 4000 per assignment.",
            "normalized_hint_json": {},
            "confidence": 0.9,
        },
        {
            "clause_type": "benefit",
            # Avoid section_label "Housing" alone — it resolves to benefit_key ``housing`` and breaks
            # employee comparison gate (requires ``temporary_housing``).
            "section_label": "Temporary accommodation",
            "raw_text": "Temporary housing allowance up to USD 5000 per month for eligible long-term assignments.",
            "normalized_hint_json": {},
            "confidence": 0.88,
        },
        {
            "clause_type": "benefit",
            "section_label": "Home search",
            "raw_text": "Home search assistance lump sum up to USD 2500.",
            "normalized_hint_json": {},
            "confidence": 0.86,
        },
        {
            "clause_type": "benefit",
            "section_label": "Education",
            "raw_text": "International school tuition support capped at USD 15000 per child per year.",
            "normalized_hint_json": {},
            "confidence": 0.87,
        },
        {
            "clause_type": "benefit",
            "section_label": "Shipment",
            "raw_text": "Household goods international shipment reimbursed up to USD 10000.",
            "normalized_hint_json": {},
            "confidence": 0.89,
        },
        {
            "clause_type": "exclusion",
            "section_label": "Exclusions",
            "raw_text": "Personal income tax return preparation fees are not reimbursable.",
            "normalized_hint_json": {},
            "confidence": 0.85,
        },
    ]
