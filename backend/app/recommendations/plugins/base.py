"""Base plugin interface for the Recommendation Engine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, TypeVar

from pydantic import BaseModel

from ..types import AvailabilityLevel, RecommendationTier

T = TypeVar("T", bound=BaseModel)


class BasePlugin(ABC):
    """Base class for recommendation plugins."""

    key: str = ""
    title: str = ""

    @property
    @abstractmethod
    def CriteriaModel(self) -> Type[BaseModel]:
        """Pydantic model for criteria validation."""
        ...

    @abstractmethod
    def load_dataset(self) -> List[Dict[str, Any]]:
        """Load dataset items from JSON."""
        ...

    @abstractmethod
    def score(self, criteria: BaseModel, item: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single item. Returns dict with score_raw, breakdown, summary, rationale, pros, cons, metadata."""
        ...

    def normalize(self, scores: List[float]) -> List[float]:
        """Normalize raw scores to 0-100. Default: min-max scaling, safe when constant."""
        if not scores:
            return []
        mn, mx = min(scores), max(scores)
        if mx - mn < 1e-9:
            return [85.0] * len(scores)
        return [100.0 * (s - mn) / (mx - mn) for s in scores]

    def tier(self, score: float) -> RecommendationTier:
        """Map score to tier."""
        if score >= 85:
            return RecommendationTier.BEST_MATCH
        if score >= 70:
            return RecommendationTier.GOOD_FIT
        if score >= 50:
            return RecommendationTier.OK
        return RecommendationTier.WEAK

    def validate_and_parse(self, criteria_dict: Dict[str, Any]) -> BaseModel:
        """Parse and validate criteria."""
        return self.CriteriaModel.model_validate(criteria_dict)
