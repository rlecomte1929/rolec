"""Storage stub plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..weights import derive_segment, get_weights

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "storage.json"


class StorageCriteria(BaseModel):
    volume_m3: float = 5.0
    duration_months: int = 3


class StoragePlugin(BasePlugin):
    key = "storage"
    title = "Furniture & Storage"

    @property
    def CriteriaModel(self) -> type:
        return StorageCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: StorageCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75}.get(item.get("availability_level", "high"), 100)
        w = get_weights("storage", segment=derive_segment(criteria))
        return {"score_raw": r * w["rating"] + a * w["availability"], "breakdown": {"rating": r, "availability": a},
                "summary": f"{item.get('name')} — {item.get('rating')}/5.",
                "rationale": "Storage and furniture solutions.", "pros": [], "cons": [],
                "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                             "availability_level": item.get("availability_level"), "confidence": item.get("confidence", 85)}}
