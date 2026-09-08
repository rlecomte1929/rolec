"""Candidate models for extraction output."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StagedResourceCandidate:
    """Extracted resource candidate for staging."""

    country_code: str
    title: str
    category_key: str = "admin_essentials"
    resource_type: str = "guide"
    audience_type: str = "all"
    summary: Optional[str] = None
    body: Optional[str] = None
    content_json: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source_url: str = ""
    source_name: str = ""
    trust_tier: str = "T0"
    confidence_score: Optional[float] = None
    extraction_method: str = "rule_based"
    provenance: Dict[str, Any] = field(default_factory=dict)
    country_name: Optional[str] = None
    city_name: Optional[str] = None


@dataclass
class StagedEventCandidate:
    """Extracted event candidate for staging."""

    country_code: str
    city_name: str
    title: str
    event_type: str = "community_event"
    description: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    price_text: Optional[str] = None
    currency: Optional[str] = None
    is_free: bool = False
    is_family_friendly: bool = False
    source_url: str = ""
    source_name: str = ""
    trust_tier: str = "T0"
    confidence_score: Optional[float] = None
    extraction_method: str = "rule_based"
    provenance: Dict[str, Any] = field(default_factory=dict)
    country_name: Optional[str] = None
