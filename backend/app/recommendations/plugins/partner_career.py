"""Partner career support stub plugin — job-search partners and coaching providers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .base import BasePlugin
from ..weights import derive_segment, get_weights

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "partner_career.json"


class PartnerCareerCriteria(BaseModel):
    employment: Optional[str] = None
    language_level: Optional[str] = None
    wants_to_work: Optional[bool] = None


class PartnerCareerPlugin(BasePlugin):
    key = "partner_career"
    title = "Partner Career Support"
    # Candidate stubs until HR curates real vendors. Advisory so HR gating
    # does not hide the dataset as an empty "HR is finalizing" slate.
    advisory = True

    @property
    def CriteriaModel(self) -> type:
        return PartnerCareerCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: PartnerCareerCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        r = item.get("rating", 4.0) * 20.0
        a = {"high": 100, "medium": 75}.get(item.get("availability_level", "high"), 100)
        w = get_weights("partner_career", segment=derive_segment(criteria))
        return {
            "score_raw": r * w["rating"] + a * w["availability"],
            "breakdown": {"rating": r, "availability": a},
            "summary": f"{item.get('name')} — {item.get('rating')}/5.",
            "rationale": "Partner career coaching and job-search support (candidate providers).",
            "pros": [],
            "cons": [],
            "metadata": {
                "rating": item.get("rating"),
                "rating_count": item.get("rating_count"),
                "availability_level": item.get("availability_level"),
                "confidence": item.get("confidence", 55),
                "kind": item.get("kind"),
            },
        }
