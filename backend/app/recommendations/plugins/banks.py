"""Banks recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "banks.json"


class BanksCriteria(BaseModel):
    preferred_languages: List[str] = Field(default_factory=lambda: ["en"])
    fee_sensitivity: str = "medium"
    expat_friendliness_priority: int = Field(default=8, ge=0, le=10)
    digital_priority: int = Field(default=8, ge=0, le=10)
    branch_need: str = "medium"


class BanksPlugin(BasePlugin):
    key = "banks"
    title = "Banks"

    @property
    def CriteriaModel(self) -> type:
        return BanksCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: BanksCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        langs = set((criteria.preferred_languages or ["en"]))
        item_langs = set(item.get("language_support", []) or [])
        lang_score = 100.0 if langs.issubset(item_langs) else max(0, 100 - 20 * (len(langs - item_langs)))
        fee = item.get("fee_level", "medium")
        fee_map = {"low": 100, "medium": 75, "high": 50}
        fee_score = fee_map.get(fee, 75)
        onboarding = item.get("onboarding_ease", 6) * 10.0
        digital = item.get("digital_features", 7) * 10.0
        expat = item.get("expat_friendly", 7) * 10.0
        branch = item.get("branch_availability", "medium")
        branch_map = {"high": 100, "medium": 75, "low": 50, "none": 30}
        branch_score = branch_map.get(branch, 75)
        rating = item.get("rating", 4.0) * 20.0
        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        avail_score = avail_map.get(avail, 100)
        score_raw = (lang_score * 0.2 + fee_score * 0.15 + onboarding * 0.1 + digital * 0.15 +
                     expat * 0.15 + branch_score * 0.1 + rating * 0.1 + avail_score * 0.05)
        return {
            "score_raw": min(100, score_raw),
            "breakdown": {"language": lang_score, "fees": fee_score, "onboarding": onboarding,
                          "digital": digital, "expat": expat, "branch": branch_score, "rating": rating,
                          "availability": avail_score},
            "summary": f"{item.get('name')} — {fee} fees, expat-friendly, {item.get('rating')}/5.",
            "rationale": f"Language support {item.get('language_support')}. Branch availability {branch}.",
            "pros": [f"Rating {item.get('rating')}/5", f"Expat score {expat/10}"],
            "cons": [],
            "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                         "availability_level": avail, "confidence": item.get("confidence", 90)},
        }
