"""Tax & finance advisor stub plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "tax_finance.json"


class TaxFinanceCriteria(BaseModel):
    expat_tax: bool = True
    wealth_planning: bool = False


class TaxFinancePlugin(BasePlugin):
    key = "tax_finance"
    title = "Tax & Finance Advisor"

    @property
    def CriteriaModel(self) -> type:
        return TaxFinanceCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: TaxFinanceCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75}.get(item.get("availability_level", "high"), 100)
        return {"score_raw": r * 0.7 + a * 0.3, "breakdown": {"rating": r, "availability": a},
                "summary": f"{item.get('name')} — {item.get('rating')}/5.",
                "rationale": "Tax and financial planning for expats.", "pros": [], "cons": [],
                "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                             "availability_level": item.get("availability_level"), "confidence": item.get("confidence", 85)}}
