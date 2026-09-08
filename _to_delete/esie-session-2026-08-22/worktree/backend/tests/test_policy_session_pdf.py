"""
[P5-4] Unit tests for policy_session_pdf.py

Tests:
 - build_policy_session_pdf returns non-empty bytes
 - Output starts with PDF magic bytes (%PDF-)
 - Works with zero evidence turns
 - Works with multiple turns
 - Works when all optional header fields are None
 - Works with all header fields provided
 - Handles special characters (ampersand, <, >) without crashing
 - Handles empty answer_text (falls back to no crash)
"""

import pytest


def _make_turn(question="What is my housing allowance?", answer_text="USD 5,000 per month.", evidence=None):
    return {
        "question": question,
        "answer_text": answer_text,
        "evidence": evidence or [],
    }


# ---------------------------------------------------------------------------
# Import guard — skip if reportlab not installed
# ---------------------------------------------------------------------------

try:
    import reportlab  # noqa: F401
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

pytestmark = pytest.mark.skipif(
    not HAS_REPORTLAB, reason="reportlab not installed"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

from backend.app.services.policy_session_pdf import build_policy_session_pdf  # noqa: E402


class TestBuildPolicySessionPdf:
    def test_returns_bytes(self):
        result = build_policy_session_pdf([_make_turn()])
        assert isinstance(result, bytes)

    def test_non_empty(self):
        result = build_policy_session_pdf([_make_turn()])
        assert len(result) > 0

    def test_pdf_magic_bytes(self):
        result = build_policy_session_pdf([_make_turn()])
        assert result[:5] == b"%PDF-", "Output must begin with PDF magic bytes"

    def test_single_turn_no_evidence(self):
        turns = [_make_turn(evidence=[])]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_multiple_turns(self):
        turns = [
            _make_turn("Q1?", "Answer 1"),
            _make_turn("Q2?", "Answer 2"),
            _make_turn("Q3?", "Answer 3"),
        ]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_with_evidence(self):
        turns = [
            _make_turn(
                evidence=[
                    {"label": "Policy §3.1", "excerpt": "Housing up to USD 5,000/month."},
                ]
            )
        ]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_all_header_fields_provided(self):
        result = build_policy_session_pdf(
            [_make_turn()],
            employee_name="Jane Smith",
            company_name="Acme Corp",
            tier="Manager",
            policy_version="v3 (effective 01/01/2026)",
        )
        assert result[:5] == b"%PDF-"

    def test_all_header_fields_none(self):
        result = build_policy_session_pdf(
            [_make_turn()],
            employee_name=None,
            company_name=None,
            tier=None,
            policy_version=None,
        )
        assert result[:5] == b"%PDF-"

    def test_special_characters_in_question(self):
        """Ampersand, angle brackets must be escaped without crashing."""
        turns = [_make_turn(question="What is rent & housing? <full details>")]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_special_characters_in_answer(self):
        turns = [_make_turn(answer_text="A&B < C > D")]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_empty_answer_text(self):
        """Empty answer_text should not crash — yields a minimal answer block."""
        turns = [_make_turn(answer_text="")]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_ten_turns_performance(self):
        """10 turns (= full session) should complete without error."""
        turns = [
            _make_turn(
                f"Question number {i}?",
                f"Answer number {i} with some detail.",
                evidence=[{"label": f"Policy §{i}", "excerpt": f"Excerpt {i}"}],
            )
            for i in range(1, 11)
        ]
        result = build_policy_session_pdf(turns, employee_name="Jane Smith", company_name="Acme Corp")
        assert result[:5] == b"%PDF-"

    def test_session_date_override(self):
        """Custom session_date should not cause a crash."""
        result = build_policy_session_pdf(
            [_make_turn()], session_date="2026-05-22"
        )
        assert result[:5] == b"%PDF-"

    def test_evidence_with_missing_excerpt(self):
        """Evidence without excerpt (only label) should render fine."""
        turns = [_make_turn(evidence=[{"label": "Policy §1", "excerpt": None}])]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"

    def test_evidence_with_missing_label(self):
        """Evidence without label should fall back to 'Policy source'."""
        turns = [_make_turn(evidence=[{"label": None, "excerpt": "Some text."}])]
        result = build_policy_session_pdf(turns)
        assert result[:5] == b"%PDF-"
