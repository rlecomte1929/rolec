"""Pets stub plugin — pet relocation vendors (travel docs, quarantine, transport).

Registered so `pets` is a first-class category everywhere (HR curation, the catalog
scraper/populate loop, admin coverage queue). Live vendors come from HR curation
(company_vendor_selections) like the other scraped categories, so the static dataset
starts empty; `score` mirrors the other stub plugins in case a seed dataset is added.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel

from .base import BasePlugin
from ..weights import derive_segment, get_weights

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "pets.json"


class PetsCriteria(BaseModel):
    species: str = "dog"
    count: int = 1


class PetsPlugin(BasePlugin):
    key = "pets"
    title = "Pets"

    @property
    def CriteriaModel(self) -> type:
        return PetsCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: PetsCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75}.get(item.get("availability_level", "high"), 100)
        w = get_weights("pets", segment=derive_segment(criteria))
        return {
            "score_raw": r * w["rating"] + a * w["availability"],
            "breakdown": {"rating": r, "availability": a},
            "summary": f"{item.get('name')} — {item.get('rating')}/5.",
            "rationale": "Pet relocation, travel documents, and quarantine requirements.",
            "pros": [],
            "cons": [],
            "metadata": {
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "availability_level": item.get("availability_level"),
                "confidence": item.get("confidence", 85),
            },
        }
