"""
AIQ-832 / F1 · Tests for immigration_requirement_service.get_requirements.

The endpoint's fail-closed decision rests on get_requirements returning an empty
list for an unseeded corridor (which the route maps to covered=False). These
tests pin that contract and the row→RequirementResult mapping, mocking the DB
layer (_fetch_requirements) so they run without a live database.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, List
from unittest.mock import patch

from backend.app.services.immigration_requirement_service import (
    RequirementResult,
    get_requirements,
)

_SVC = "backend.app.services.immigration_requirement_service"


def _row(document_name: str, is_required: bool = True) -> Dict[str, Any]:
    return {
        "document_type": "passport",
        "document_name": document_name,
        "is_required": is_required,
        "is_conditional": False,
        "condition_expression": None,
        "freshness_days": 90,
        "requires_apostille": False,
        "apostille_countries": None,
        "requires_translation": False,
        "translation_languages": None,
        "can_be_prefilled": False,
        "can_be_ocr_extracted": False,
        "typical_processing_days": 21,
        "book_early_flag": False,
        "book_early_reason": None,
        "success_tips": None,
        "common_rejection_reasons": None,
        "form_url": None,
        "form_version": None,
    }


class TestGetRequirements(unittest.TestCase):
    def test_unseeded_corridor_returns_empty_list(self) -> None:
        """No rows for the corridor → empty list (route reads this as covered=False)."""
        with patch(f"{_SVC}._fetch_requirements", return_value=[]):
            result = get_requirements("NO", "JP", "blue_card")
        self.assertEqual(result, [])

    def test_seeded_corridor_maps_rows_to_results(self) -> None:
        """Rows map to RequirementResult objects with fields preserved."""
        with patch(f"{_SVC}._fetch_requirements", return_value=[_row("Passport")]):
            result: List[RequirementResult] = get_requirements("FR", "DE", "blue_card")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], RequirementResult)
        self.assertEqual(result[0].document_name, "Passport")
        self.assertEqual(result[0].typical_processing_days, 21)
        self.assertTrue(result[0].is_required)

    def test_required_documents_sort_before_optional(self) -> None:
        """Sort contract: required first, then alphabetical by document_name."""
        rows = [_row("Optional Doc", is_required=False), _row("Required Doc", is_required=True)]
        with patch(f"{_SVC}._fetch_requirements", return_value=rows):
            result = get_requirements("FR", "DE", "blue_card")
        self.assertEqual([r.document_name for r in result], ["Required Doc", "Optional Doc"])


if __name__ == "__main__":
    unittest.main()
