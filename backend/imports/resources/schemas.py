"""
Canonical import schemas for Resources module.
Define expected field names, types, and validation rules.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# --- Enums (must match DB / resource_entry_type, resource_audience_type, etc.) ---
CATEGORY_KEYS = frozenset({
    "admin_essentials", "housing", "schools_childcare", "schools", "healthcare",
    "transport", "daily_life", "community", "events", "culture_leisure",
    "nature", "cost_of_living", "safety",
})
RESOURCE_TYPES = frozenset({
    "guide", "checklist_item", "provider", "place", "event_source", "tip",
    "official_link", "cost_snapshot", "safety_tip", "community_group",
    "school", "healthcare_facility", "housing_listing_source", "transport_info",
})
AUDIENCE_TYPES = frozenset({"all", "single", "couple", "family", "with_children", "spouse_job_seeker"})
BUDGET_TIERS = frozenset({"low", "mid", "high"})
SOURCE_TYPES = frozenset({"official", "institutional", "commercial", "community", "internal_curated"})
TRUST_TIERS = frozenset({"T0", "T1", "T2", "T3"})
EVENT_TYPES = frozenset({
    "cinema", "concert", "festival", "sports", "family_activity", "networking",
    "museum", "theater", "market", "nature", "kids_activity", "community_event",
})
STATUSES = frozenset({"draft", "in_review", "approved", "published", "archived"})
TAG_GROUPS = frozenset({
    "family_type", "budget", "interest", "age_group", "indoor_outdoor",
    "free_paid", "weekday_weekend", "general",
})


@dataclass
class ImportCategory:
    key: str
    label: str
    description: Optional[str] = None
    icon_name: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    row_num: int = 0


@dataclass
class ImportTag:
    key: str
    label: str
    tag_group: Optional[str] = None
    row_num: int = 0


@dataclass
class ImportSource:
    source_name: str
    publisher: Optional[str] = None
    source_type: str = "community"
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
    content_hash: Optional[str] = None
    notes: Optional[str] = None
    trust_tier: str = "T2"
    row_num: int = 0


@dataclass
class ImportResource:
    country_code: str
    country_name: Optional[str] = None
    city_name: Optional[str] = None
    category_key: str = ""
    title: str = ""
    summary: Optional[str] = None
    resource_type: str = "guide"
    audience_type: str = "all"
    body: Optional[str] = None
    content_json: Optional[Dict[str, Any]] = None
    min_child_age: Optional[int] = None
    max_child_age: Optional[int] = None
    budget_tier: Optional[str] = None
    language_code: Optional[str] = None
    is_family_friendly: bool = False
    is_featured: bool = False
    address: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_range_text: Optional[str] = None
    external_url: Optional[str] = None
    booking_url: Optional[str] = None
    contact_info: Optional[str] = None
    opening_hours: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    trust_tier: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    status: str = "draft"
    is_visible_to_end_users: bool = False
    internal_notes: Optional[str] = None
    review_notes: Optional[str] = None
    external_key: Optional[str] = None
    row_num: int = 0


@dataclass
class ImportEvent:
    country_code: str
    country_name: Optional[str] = None
    city_name: str = ""
    title: str = ""
    event_type: str = "cinema"
    start_datetime: str = ""
    description: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    end_datetime: Optional[str] = None
    price_text: Optional[str] = None
    currency: Optional[str] = None
    is_free: bool = False
    is_family_friendly: bool = False
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    language_code: Optional[str] = None
    external_url: Optional[str] = None
    booking_url: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    trust_tier: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    status: str = "draft"
    is_visible_to_end_users: bool = False
    internal_notes: Optional[str] = None
    review_notes: Optional[str] = None
    external_key: Optional[str] = None
    row_num: int = 0


@dataclass
class ImportBundle:
    """Single JSON bundle containing all entity types."""
    categories: List[ImportCategory] = field(default_factory=list)
    tags: List[ImportTag] = field(default_factory=list)
    sources: List[ImportSource] = field(default_factory=list)
    resources: List[ImportResource] = field(default_factory=list)
    events: List[ImportEvent] = field(default_factory=list)
