"""Banks recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..weights import derive_segment, get_weights

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

        # fee_sensitivity adjusts how much higher fee tiers are penalised.
        # "low" sensitivity = user is less bothered by fees → smaller penalty.
        fee = item.get("fee_level", "medium")
        fee_base_map = {"low": 100, "medium": 75, "high": 50}
        fee_penalty_scale = {"low": 0.25, "medium": 1.0, "high": 1.5}.get(criteria.fee_sensitivity, 1.0)
        fee_score = 100.0 - (100.0 - fee_base_map.get(fee, 75)) * fee_penalty_scale

        onboarding = item.get("onboarding_ease", 6) * 10.0
        digital = item.get("digital_features", 7) * 10.0
        expat = item.get("expat_friendly", 7) * 10.0

        # branch_need adjusts the branch score map: high need → heavy penalty for
        # limited/no branches; no need → branches are irrelevant.
        branch = item.get("branch_availability", "medium")
        bn = criteria.branch_need
        _branch_score_by_need: Dict[str, Dict[str, float]] = {
            "none":   {"high": 100, "medium": 90, "low": 80, "none": 100},
            "low":    {"high": 100, "medium": 85, "low": 75, "none": 65},
            "medium": {"high": 100, "medium": 75, "low": 45, "none": 15},
            "high":   {"high": 100, "medium": 50, "low": 20, "none": 0},
        }
        branch_score = _branch_score_by_need.get(bn, _branch_score_by_need["medium"]).get(branch, 75)

        rating = item.get("rating", 4.0) * 20.0
        avail = item.get("availability_level", "high")
        avail_map = {"high": 100, "medium": 75, "low": 50, "scarce": 25}
        avail_score = avail_map.get(avail, 100)

        # Dynamic weights: scale expat/digital by stated priority (0–10), branch
        # by need level, and fees by sensitivity.  Weights are renormalised to sum
        # to 1.0 so scores stay in the 0–100 range.
        base_w = dict(get_weights("banks", segment=derive_segment(criteria)))
        expat_mult = 0.5 + (criteria.expat_friendliness_priority / 10.0) * 1.5
        digital_mult = 0.5 + (criteria.digital_priority / 10.0) * 1.5
        branch_mult = {"none": 0.2, "low": 0.6, "medium": 1.8, "high": 2.5}.get(bn, 1.0)
        fee_mult = {"low": 0.4, "medium": 1.0, "high": 1.5}.get(criteria.fee_sensitivity, 1.0)
        w = dict(base_w)
        w["expat"] *= expat_mult
        w["digital"] *= digital_mult
        w["branch"] *= branch_mult
        w["fees"] *= fee_mult
        wsum = sum(w.values())
        w = {k: v / wsum for k, v in w.items()}

        score_raw = (lang_score * w["language"] + fee_score * w["fees"] + onboarding * w["onboarding"] +
                     digital * w["digital"] + expat * w["expat"] + branch_score * w["branch"] +
                     rating * w["rating"] + avail_score * w["availability"])
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
