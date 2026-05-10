"""Electricity providers recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "electricity.json"


class ElectricityCriteria(BaseModel):
    green_preference: bool = True
    contract_flexibility: str = "medium"
    pricing_transparency_priority: int = Field(default=8, ge=0, le=10)


class ElectricityPlugin(BasePlugin):
    key = "electricity"
    title = "Electricity"

    @property
    def CriteriaModel(self) -> type:
        return ElectricityCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: ElectricityCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        green = 100.0 if (not criteria.green_preference or item.get("green_options")) else 50.0
        flex = item.get("contract_flexibility", "medium")
        flex_map = {"high": 100, "medium": 75, "low": 50}
        flex_score = flex_map.get(flex, 75)
        trans = item.get("pricing_transparency", 7) * 10.0
        rating = item.get("rating", 4.0) * 20.0
        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50}
        avail_score = avail_map.get(avail, 100)
        score_raw = green * 0.3 + flex_score * 0.25 + trans * 0.2 + rating * 0.15 + avail_score * 0.1
        return {
            "score_raw": min(100, score_raw),
            "breakdown": {"green": green, "flexibility": flex_score, "transparency": trans,
                          "rating": rating, "availability": avail_score},
            "summary": f"{item.get('name')} — {flex} flexibility, green={item.get('green_options')}, {item.get('rating')}/5.",
            "rationale": f"Contract flexibility {flex}. Pricing transparency {item.get('pricing_transparency')}/10.",
            "pros": [f"Rating {item.get('rating')}/5"],
            "cons": [] if item.get("green_options") else ["No green options"],
            "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                         "availability_level": avail, "confidence": item.get("confidence", 90)},
        }
