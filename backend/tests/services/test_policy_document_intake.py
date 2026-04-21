"""
Classifier tests — Prompt A EXTRACT-BUG-2 + the richer
ClassificationResult shape per REMEDIATION_PATCHES.md §3.

Covers:
- The recipe's three canonical fixtures (assignment-with-tax-section,
  standalone-tax-policy, unknown).
- The three HR Policy Dummy DOCX fixtures.
- Structural invariants of ClassificationResult (reasons, scores, margin).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import (  # noqa: E402
    DOC_TYPE_ASSIGNMENT_POLICY,
    DOC_TYPE_POLICY_SUMMARY,
    DOC_TYPE_TAX_POLICY,
    DOC_TYPE_UNKNOWN,
    SCOPE_GLOBAL,
    SCOPE_TAX_EQUALIZATION,
    SCOPE_UNKNOWN,
    ClassificationResult,
    _extract_text_from_docx,
    classify_by_keywords,
    classify_document,
)

_FIXTURES = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "source_docx"


def _dummy_text(name: str) -> str:
    path = _FIXTURES / name
    if not path.exists():
        pytest.skip(f"fixture missing: {name}")
    lines, err = _extract_text_from_docx(path.read_bytes())
    assert err is None
    return "\n".join(lines)


# --- Recipe fixtures (§3) ----------------------------------------------------

ASSIGNMENT_WITH_TAX_SECTION = """\
# Long-Term Assignment Policy

This policy governs assignees relocating for more than 12 months.

## Housing Allowance
Host country housing is provided up to €3,000/month.

## Tax & Payroll
Tax equalization applies. Hypothetical tax is deducted from home country salary.
Tax gross-up covers employer-provided benefits. Tax return preparation is
provided by the company's vendor.

## Repatriation
Return travel is covered within 30 days of assignment end.
"""

STANDALONE_TAX_POLICY = """\
# Tax Equalization Policy

This policy defines how hypothetical tax is calculated and applied.

Hypothetical tax methodology: ...
Tax gross-up on benefits: ...
Tax return preparation vendor: ...
"""

UNKNOWN_DOC = """\
# Quarterly Board Minutes
Attendees: ...
"""


class TestClassifierMisroute:
    """Regression tests for EXTRACT-BUG-2."""

    def test_assignment_with_tax_section_is_assignment(self) -> None:
        r = classify_by_keywords(ASSIGNMENT_WITH_TAX_SECTION)
        assert r.detected_document_type == DOC_TYPE_ASSIGNMENT_POLICY, r.reasons
        assert r.detected_policy_scope == SCOPE_GLOBAL

    def test_standalone_tax_policy_is_tax(self) -> None:
        r = classify_by_keywords(STANDALONE_TAX_POLICY)
        assert r.detected_document_type == DOC_TYPE_TAX_POLICY, r.reasons
        assert r.detected_policy_scope == SCOPE_TAX_EQUALIZATION

    def test_unknown_sets_review_required(self) -> None:
        r = classify_by_keywords(UNKNOWN_DOC)
        assert r.detected_document_type == DOC_TYPE_UNKNOWN
        assert r.review_required is True
        assert r.confidence == 0.0


class TestDummyFixtures:
    """End-to-end against the three canonical audit DOCX files."""

    def test_dummy_1_classifies_as_assignment_policy(self) -> None:
        r = classify_by_keywords(_dummy_text("HR_Policy_Dummy_1.docx"))
        assert r.detected_document_type == DOC_TYPE_ASSIGNMENT_POLICY, r.reasons
        assert r.review_required is False

    def test_dummy_2_classifies_as_assignment_policy(self) -> None:
        r = classify_by_keywords(_dummy_text("HR_Policy_Dummy_2.docx"))
        assert r.detected_document_type == DOC_TYPE_ASSIGNMENT_POLICY, r.reasons

    def test_dummy_3_stays_unknown_review_required(self) -> None:
        r = classify_by_keywords(_dummy_text("HR_Policy_Dummy_3.docx"))
        assert r.detected_document_type == DOC_TYPE_UNKNOWN
        assert r.review_required is True


class TestClassificationResultShape:
    """The new dataclass surface is stable and useful."""

    def test_result_carries_reasons_and_scores(self) -> None:
        r = classify_by_keywords(ASSIGNMENT_WITH_TAX_SECTION)
        assert isinstance(r, ClassificationResult)
        assert r.scores, "scores dict should be populated when any profile runs"
        assert r.reasons, "reasons list should explain the winner"

    def test_confidence_between_zero_and_one(self) -> None:
        r = classify_by_keywords(ASSIGNMENT_WITH_TAX_SECTION)
        assert 0.0 <= r.confidence <= 1.0

    def test_legacy_classify_document_tuple_preserved(self) -> None:
        """classify_document keeps its 3-tuple return for backward compat."""
        lines = ASSIGNMENT_WITH_TAX_SECTION.splitlines()
        doc_type, scope, needs_review = classify_document(lines)
        assert doc_type == DOC_TYPE_ASSIGNMENT_POLICY
        assert scope == SCOPE_GLOBAL
        assert needs_review is False


class TestProfileEligibility:
    """A profile with no primary hit in the title block must score 0."""

    def test_body_only_mobility_mention_not_assignment(self) -> None:
        # Body mentions mobility premium but the title is an employee handbook.
        text = (
            "# Acme Corp Employee Handbook\n"
            "Welcome!\n\n"
            "Section 9: mobility premium is 10% of base\n"
            "Section 9.1: home leave once per year\n"
        )
        r = classify_by_keywords(text)
        assert r.detected_document_type == DOC_TYPE_UNKNOWN

    def test_body_only_tax_mention_not_tax(self) -> None:
        text = (
            "# Random Document\n\n"
            "For context, hypothetical tax calculations apply here.\n"
        )
        r = classify_by_keywords(text)
        assert r.detected_document_type == DOC_TYPE_UNKNOWN
