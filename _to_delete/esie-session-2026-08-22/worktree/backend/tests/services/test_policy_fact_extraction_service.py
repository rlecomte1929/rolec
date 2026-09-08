"""
Tests for backend.app.services.policy_fact_extraction_service.

Covers the EXTRACT-BUG-1 regression (audit Prompt A): the deterministic
currency regex must match €- and £-denominated amounts, not just USD/EUR/$/GBP
letter codes.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.policy_fact_extraction_service import (  # noqa: E402
    _CURRENCY_RE,
    extract_minimal_policy_facts,
)


class TestCurrencyRegex:
    """Direct assertions on the regex."""

    @pytest.mark.parametrize(
        "text,expected_match",
        [
            # Euro + pound — the symbols \b fails to anchor before.
            ("capped at €5,000", "€5,000"),
            ("up to £1,200 per month", "£1,200 per month"),
            ("housing allowance: €2,500/month cap", "€2,500"),
            ("€150/day",                      "€150"),
            ("€12,000",                        "€12,000"),
            ("lump sum: €20,000 (all-inclusive)", "€20,000"),
            # Letter codes still work.
            ("USD 10,000 per year",            "USD 10,000 per year"),
            ("up to EUR 7,500",                "EUR 7,500"),
            # Dollar sign — previously the only symbol that worked.
            ("cost: $500",                     "$500"),
        ],
    )
    def test_matches_cover_euro_pound_and_letter_codes(self, text, expected_match):
        m = _CURRENCY_RE.search(text)
        assert m is not None, f"no match in {text!r}"
        assert m.group(0).strip() == expected_match.strip(), (
            f"expected {expected_match!r}, got {m.group(0)!r} in {text!r}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "no currency here",
            # Adjacent-to-word should NOT match — these are not sensible prices.
            "abc€5",
            "notacurrencyEUR 100",
        ],
    )
    def test_no_spurious_matches(self, text):
        assert _CURRENCY_RE.search(text) is None, f"unexpected match in {text!r}"


class TestExtractorOnDummies:
    """
    End-to-end assertion that extract_minimal_policy_facts produces at least
    one `allowance_cap` row for each of the three HR policy dummies. The
    dummies have 5, 3, and 1 euro-denominated caps respectively; pre-fix the
    extractor returned zero.
    """

    def _chunk(self, idx: int, text: str) -> dict:
        return {
            "id": f"chunk-{idx}",
            "chunk_index": idx,
            "section_title": "test",
            "text_content": text,
            "page_number": None,
        }

    def test_dummy_1_text_produces_euro_caps(self):
        chunks = [
            self._chunk(0, "Legal fees capped at €5,000"),
            self._chunk(1, "Household goods shipment: up to €12,000"),
            self._chunk(2, "Temporary housing: 60 days max, €150/day cap"),
            self._chunk(3, "Housing allowance: €2,500/month cap"),
            self._chunk(4, "Schooling: up to €15,000/year per child"),
        ]
        facts = extract_minimal_policy_facts(chunks)
        caps = [f for f in facts if f.get("fact_type") == "allowance_cap"]
        assert len(caps) >= 5, (
            f"expected >=5 allowance_cap rows, got {len(caps)}; "
            f"spans={[f['normalized_value_json'].get('raw_span') for f in caps]}"
        )

    def test_dummy_2_text_produces_euro_caps(self):
        chunks = [
            self._chunk(0, "Per diem: €75/day"),
            self._chunk(1, "Accommodation: company-arranged or reimbursed (~€3,000/month guideline)"),
        ]
        facts = extract_minimal_policy_facts(chunks)
        caps = [f for f in facts if f.get("fact_type") == "allowance_cap"]
        assert len(caps) >= 2, f"expected >=2 allowance_cap rows, got {len(caps)}"

    def test_dummy_3_text_produces_euro_caps(self):
        chunks = [self._chunk(0, "Lump sum: €20,000 (all-inclusive)")]
        facts = extract_minimal_policy_facts(chunks)
        caps = [f for f in facts if f.get("fact_type") == "allowance_cap"]
        assert len(caps) >= 1, f"expected >=1 allowance_cap row, got {len(caps)}"
