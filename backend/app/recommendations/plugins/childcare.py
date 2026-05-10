"""Childcare stub plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "childcare.json"


class ChildcareCriteria(BaseModel):
    child_ages: List[int] = Field(default_factory=lambda: [3])


class ChildcarePlugin(BasePlugin):
    key = "childcare"
    title = "Childcare"

    @property
    def CriteriaModel(self) -> type:
        return ChildcareCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: ChildcareCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75, "low": 50}.get(item.get("availability_level", "medium"), 75)
        return {"score_raw": r * 0.7 + a * 0.3, "breakdown": {"rating": r, "availability": a},
                "summary": f"{item.get('name')} — {item.get('rating')}/5.",
                "rationale": "Childcare and preschool options.", "pros": [], "cons": [],
                "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                             "availability_level": item.get("availability_level"), "confidence": item.get("confidence", 85)}}
