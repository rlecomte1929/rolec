"""Schools recommendation plugin."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import BasePlugin
from ..types import RecommendationTier

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "schools.json"


def _age_to_grade(age: int) -> int:
    """Approximate grade from age (simplified)."""
    return max(0, age - 5)


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


class SchoolsCriteria(BaseModel):
    child_ages: List[int] = Field(default_factory=lambda: [8])
    curriculum: str = "international"
    language_of_instruction: List[str] = Field(default_factory=lambda: ["en"])
    school_type: str = "either"
    budget_level: str = "medium"
    special_needs_support: bool = False
    priorities: Optional[Dict[str, int]] = None
    commute_max_minutes: int = 45
    target_start_date: Optional[str] = None
    flexibility: str = "flexible"
    weights: Optional[Dict[str, float]] = None


class SchoolsPlugin(BasePlugin):
    key = "schools"
    title = "Schools"

    @property
    def CriteriaModel(self) -> type:
        return SchoolsCriteria

    def load_dataset(self) -> List[Dict[str, Any]]:
        with open(DATASET_PATH, encoding="utf-8") as f:
            return json.load(f)

    def score(self, criteria: SchoolsCriteria, item: Dict[str, Any]) -> Dict[str, Any]:
        c = criteria
        w = c.weights or {}
        ages = c.child_ages or [8]
        grades_needed = [_age_to_grade(a) for a in ages]
        g_min, g_max = item.get("grades_supported", [0, 18])[:2]
        age_fit = 100.0
        for g in grades_needed:
            if g < g_min or g > g_max:
                age_fit = 40.0
                break

        curr = item.get("curriculum", "international")
        curr_fit = 100.0 if c.curriculum == "either" or curr == c.curriculum else 30.0

        langs = item.get("languages", []) or []
        need_langs = set((c.language_of_instruction or ["en"]))
        lang_fit = 100.0 if need_langs.issubset(set(langs)) or not need_langs else 60.0

        stype = item.get("type", "private")
        type_fit = 100.0 if c.school_type == "either" or stype == c.school_type else 30.0

        quality = item.get("quality_score", 6)
        extra = item.get("extracurricular_score", 6)
        prio = c.priorities or {}
        acad = prio.get("academics", 7)
        ext = prio.get("extracurricular", 6)
        quality_score = (quality * (acad / 10) + extra * (ext / 10)) * 5.0

        commute_mins = item.get("commute_minutes_estimate", 25)
        commute_fit = max(0, 100 - (commute_mins - c.commute_max_minutes) * 2)

        avail = item.get("seats_availability_level", "medium")
        waitlist = item.get("waitlist_weeks", 12)
        target = _parse_date(c.target_start_date)
        availability_score = 80.0
        if avail == "scarce":
            availability_score = 40.0
        elif avail == "low":
            availability_score = 55.0
        if target and waitlist > 20:
            weeks_to_start = (target - date.today()).days / 7 if target > date.today() else 0
            if weeks_to_start < waitlist:
                availability_score *= 0.7

        rating = item.get("rating", 4.0)
        rating_score = rating * 20.0

        w_fit = w.get("fit", 0.25)
        w_qual = w.get("quality", 0.2)
        w_lang = w.get("language", 0.15)
        w_comm = w.get("commute", 0.15)
        w_av = w.get("availability", 0.15)
        w_rat = w.get("rating", 0.1)

        score_raw = (
            w_fit * (age_fit * 0.4 + curr_fit * 0.3 + type_fit * 0.3)
            + w_qual * quality_score
            + w_lang * lang_fit
            + w_comm * commute_fit
            + w_av * availability_score
            + w_rat * rating_score
        )

        rationale = f"Ages {ages} → grades {grades_needed}. "
        rationale += f"Curriculum {curr}, {stype}. "
        rationale += f"Commute ~{commute_mins} min. "
        if avail in ("low", "scarce"):
            rationale += f"⚠ Admissions scarcity: waitlist ~{waitlist} weeks. "
        if item.get("application_deadline"):
            rationale += f"Application deadline {item['application_deadline']}. "

        pros = [f"Rating {rating}/5", f"Quality {quality}/10"]
        cons = []
        if avail in ("low", "scarce"):
            cons.append(f"Waitlist ~{waitlist} weeks")

        return {
            "score_raw": score_raw,
            "breakdown": {
                "age_fit": age_fit,
                "curriculum_fit": curr_fit,
                "language_fit": lang_fit,
                "quality": quality_score,
                "commute": commute_fit,
                "availability": availability_score,
                "rating": rating_score,
            },
            "summary": f"{item.get('name')} — {curr}, {stype}, ~{commute_mins} min, {rating}/5.",
            "rationale": rationale,
            "pros": pros,
            "cons": cons,
            "metadata": {
                "rating": rating,
                "rating_count": item.get("rating_count", 0),
                "availability_level": avail,
                "waitlist_weeks": waitlist,
                "confidence": item.get("confidence", 85),
                "estimated_cost_usd": int(
                    {"high": 45000, "medium": 28000, "low": 15000}.get(
                        item.get("tuition_level", "medium"), 28000
                    ) * 0.74
                ),
                "cost_type": "annual",
                "map_query": f"{item.get('name', '')}, {item.get('city', 'Singapore')}",
            },
        }
