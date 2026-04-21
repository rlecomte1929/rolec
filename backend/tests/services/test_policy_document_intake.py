"""
Classifier tests — covers Prompt A EXTRACT-BUG-2.

The previous keyword-cascade classifier fired `tax_policy` as soon as any
"tax equalization" / "hypothetical tax" string appeared in the body, even
for documents whose title block described an assignment policy. The new
structured classifier gates each document type on a *primary* keyword in
the title block (first 600 chars) and only then tallies secondary/negative
signals from the body.

The three dummies are the shipping fixtures under
.audit_tmp/fixtures/source_docx/ (copied at audit time from OneDrive).
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
    _extract_text_from_docx,
    classify_by_keywords,
    classify_document,
)

_FIXTURES = Path(_REPO_ROOT) / ".audit_tmp" / "fixtures" / "source_docx"


def _lines(name: str) -> list:
    path = _FIXTURES / name
    if not path.exists():
        pytest.skip(f"fixture missing: {name}")
    lines, err = _extract_text_from_docx(path.read_bytes())
    assert err is None
    return lines


class TestClassifierMisroute:
    """
    The key regression: Dummy 1 and Dummy 2 must classify as assignment_policy.
    Pre-fix both returned tax_policy because 'Tax equalization' in §5 was
    enough to short-circuit the classifier.
    """

    def test_dummy_1_classifies_as_assignment_policy(self) -> None:
        lines = _lines("HR_Policy_Dummy_1.docx")
        doc_type, scope, needs_review = classify_document(lines)
        assert doc_type == DOC_TYPE_ASSIGNMENT_POLICY
        assert scope == SCOPE_GLOBAL
        assert needs_review is False, "structured long-term policy should be high-confidence"

    def test_dummy_2_classifies_as_assignment_policy(self) -> None:
        lines = _lines("HR_Policy_Dummy_2.docx")
        doc_type, scope, needs_review = classify_document(lines)
        assert doc_type == DOC_TYPE_ASSIGNMENT_POLICY
        assert scope == SCOPE_GLOBAL

    def test_dummy_3_stays_unknown_review_required(self) -> None:
        """
        Dummy 3 has 'permanent transfer' in its preamble, which matches
        the assignment_policy primary set. But the body has many
        'not specified' / 'not provided' / 'support may be provided' /
        'handled internally' markers, which trip the ambiguity override
        and demote the doc back to UNKNOWN with needs_review=True.
        """
        lines = _lines("HR_Policy_Dummy_3.docx")
        doc_type, scope, needs_review = classify_document(lines)
        assert doc_type == DOC_TYPE_UNKNOWN
        assert scope == SCOPE_UNKNOWN
        assert needs_review is True


class TestClassifyByKeywords:
    """Unit tests for the scoring function itself."""

    def test_no_primary_hit_scores_zero(self) -> None:
        # Body has mobility-like words but title block doesn't match any primary.
        text = [
            "Acme Corp Employee Handbook",
            "Welcome!",
            "Section 9: mobility premium is 10% of base",
            "Section 9.1: home leave once per year",
        ]
        doc_type, scope, score = classify_by_keywords(text)
        assert doc_type == DOC_TYPE_UNKNOWN
        assert score == 0

    def test_primary_in_title_plus_secondary_in_body(self) -> None:
        text = [
            "International Assignment Policy",
            "Assignment Type: Long-term",
            "",
            "Section 3: mobility premium 10% of base",
            "Section 4: home leave, household goods shipment",
        ]
        doc_type, scope, score = classify_by_keywords(text)
        assert doc_type == DOC_TYPE_ASSIGNMENT_POLICY
        assert scope == SCOPE_GLOBAL
        assert score > 3  # primary base + at least one secondary

    def test_tax_policy_does_not_win_on_body_mention_alone(self) -> None:
        """
        Critical regression case. A long-term assignment doc with a Tax &
        Payroll section that mentions 'tax equalization' must NOT classify
        as tax_policy — only assignment_policy profiles have their primary
        in the title block.
        """
        text = [
            "International Assignment Policy",
            "Assignment Type: Long-term",
            "",
            "Section 5: Tax equalization is provided for the employee",
            "mobility premium 10%, home leave, household goods",
        ]
        doc_type, _, _ = classify_by_keywords(text)
        assert doc_type == DOC_TYPE_ASSIGNMENT_POLICY

    def test_ambiguity_override_returns_unknown(self) -> None:
        text = [
            "International Assignment Policy",
            "Assignment Type: Permanent transfer",
            "",
            "Housing: not specified",
            "Legal fees: not specified",
            "Temp housing: not provided",
            "Schooling: not provided",
            "Support may be provided in exceptional cases",
            "Handled internally by HR",
        ]
        doc_type, _, score = classify_by_keywords(text)
        assert doc_type == DOC_TYPE_UNKNOWN
        assert score == 0
