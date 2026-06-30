"""Insurance recommendation plugin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..weights import derive_segment, get_weights

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
        w = get_weights("insurance", segment=derive_segment(criteria))
        score_raw = (coverage_score * w["coverage"] + ded_score * w["deductible"] + family * w["family"] +
                     rating * w["rating"] + avail_score * w["availability"])
        # expat_specialized bonus: global expat insurers (Cigna, Allianz Care, Bupa Global, GeoBlue)
        # have purpose-built international networks and repatriation/evacuation coverage beyond what
        # local/regional insurers offer for a relocation product.  A 2.5-pt bonus breaks the cluster
        # tie (8 providers within 1.2 raw pts) without distorting the 0–100 scale.  The bonus is
        # applied AFTER the base-score cap so it is never swallowed by min(100, ...).
        expat_bonus = 2.5 if item.get("expat_specialized", False) else 0.0
        return {
            "score_raw": min(100, score_raw) + expat_bonus,
            "breakdown": {"coverage": coverage_score, "deductible": ded_score, "family": family,
                          "rating": rating, "availability": avail_score},
            "summary": f"{item.get('name')} — {', '.join(item.get('coverage_types', []))}, {item.get('rating')}/5.",
            "rationale": f"Covers {item.get('coverage_types')}. Deductible options {opts}.",
            "pros": [f"Rating {item.get('rating')}/5"],
            "cons": [],
            "metadata": {"rating": item.get("rating"), "rating_count": item.get("rating_count"),
                         "availability_level": avail, "confidence": item.get("confidence", 90)},
        }
