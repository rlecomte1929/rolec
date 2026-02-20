"""Medical providers recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "medical.json"


class MedicalCriteria(BaseModel):
    specialty_needs: List[str] = Field(default_factory=lambda: ["general"])
    preferred_languages: List[str] = Field(default_factory=lambda: ["en"])
    wait_time_sensitivity: int = Field(default=5, ge=0, le=10)


class MedicalPlugin(BasePlugin):
    key = "medical"
    title = "Medical Providers"

    @property
    def CriteriaModel(self) -> type:
        return MedicalCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: MedicalCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        need = set(criteria.specialty_needs or ["general"])
        have = set(item.get("specialties", []) or [])
        spec_score = 100.0 if need.issubset(have) else max(0, 100 - 30 * len(need - have))
        langs = set(criteria.preferred_languages or ["en"])
        item_langs = set(item.get("languages", []) or [])
        lang_score = 100.0 if langs.issubset(item_langs) else 70.0
        wait_days = item.get("wait_time_days", 5)
        sens = criteria.wait_time_sensitivity
        wait_score = max(0, 100 - wait_days * (2 if sens >= 7 else 1))
        rating = item.get("rating", 4.0) * 20.0
        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        avail_score = avail_map.get(avail, 100)
        score_raw = spec_score * 0.3 + lang_score * 0.2 + wait_score * 0.2 + rating * 0.2 + avail_score * 0.1
        rationale = f"Specialties {item.get('specialties')}. Wait ~{wait_days} days."
        if avail in ("low", "scarce"):
            rationale += f" Limited availability."
        return {
            "score_raw": min(100, score_raw),
            "breakdown": {"specialty": spec_score, "language": lang_score, "wait": wait_score,
                          "rating": rating, "availability": avail_score},
            "summary": f"{item.get('name')} — {item.get('specialties')}, ~{wait_days}d wait, {item.get('rating')}/5.",
            "rationale": rationale,
            "pros": [f"Rating {item.get('rating')}/5"],
            "cons": [f"~{wait_days} days wait"] if wait_days > 7 else [],
            "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                         "availability_level": avail, "confidence": item.get("confidence", 90)},
        }
