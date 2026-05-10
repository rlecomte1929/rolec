"""Legal & admin stub plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "legal_admin.json"


class LegalAdminCriteria(BaseModel):
    services: List[str] = Field(default_factory=lambda: ["immigration", "lease"])


class LegalAdminPlugin(BasePlugin):
    key = "legal_admin"
    title = "Legal & Admin"

    @property
    def CriteriaModel(self) -> type:
        return LegalAdminCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: LegalAdminCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75}.get(item.get("availability_level", "medium"), 75)
        return {"score_raw": r * 0.7 + a * 0.3, "breakdown": {"rating": r, "availability": a},
                "summary": f"{item.get('name')} — {item.get('rating')}/5.",
                "rationale": "Legal and administrative support for relocation.", "pros": [], "cons": [],
                "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                             "availability_level": item.get("availability_level"), "confidence": item.get("confidence", 85)}}
