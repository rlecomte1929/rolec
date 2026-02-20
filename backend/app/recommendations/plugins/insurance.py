"""Insurance recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "insurance.json"


class InsuranceCriteria(BaseModel):
    coverage_types: List[str] = Field(default_factory=lambda: ["health"])
    deductible_preference: str = "medium"
    family_coverage: bool = True


class InsurancePlugin(BasePlugin):
    key = "insurance"
    title = "Insurance"

    @property
    def CriteriaModel(self) -> type:
        return InsuranceCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: InsuranceCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        need = set(criteria.coverage_types or ["health"])
        have = set(item.get("coverage_types", []) or [])
        coverage_score = 100.0 if need.issubset(have) else max(0, 100 - 25 * len(need - have))
        ded = criteria.deductible_preference
        opts = item.get("deductible_options", []) or []
        ded_score = 100.0 if ded in opts else 70.0
        family = 100.0 if (not criteria.family_coverage or item.get("family_coverage")) else 40.0
        rating = item.get("rating", 4.0) * 20.0
        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        avail_score = avail_map.get(avail, 100)
        score_raw = coverage_score * 0.35 + ded_score * 0.2 + family * 0.2 + rating * 0.15 + avail_score * 0.1
        return {
            "score_raw": min(100, score_raw),
            "breakdown": {"coverage": coverage_score, "deductible": ded_score, "family": family,
                          "rating": rating, "availability": avail_score},
            "summary": f"{item.get('name')} — {', '.join(item.get('coverage_types', []))}, {item.get('rating')}/5.",
            "rationale": f"Covers {item.get('coverage_types')}. Deductible options {opts}.",
            "pros": [f"Rating {item.get('rating')}/5"],
            "cons": [],
            "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                         "availability_level": avail, "confidence": item.get("confidence", 90)},
        }
