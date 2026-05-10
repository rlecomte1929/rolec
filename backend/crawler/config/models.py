"""
Source registry models for crawl configuration.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CrawlSource:
    """Single crawl source configuration."""

    source_name: str
    base_url: str
    country_code: str
    country_name: str
    city_name: Optional[str] = None
    source_type: str = "official"  # official, institutional, commercial, community
    trust_tier: str = "T0"  # T0, T1, T2, T3
    content_domain: str = "admin_essentials"  # admin_essentials, housing, schools, events, etc.
    crawl_strategy: str = "single_page"  # single_page, site_map, link_follow, rss_or_feed, structured_api
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    max_depth: int = 1
    language_code: str = "en"
    is_active: bool = True
    notes: Optional[str] = None

    def matches_url(self, url: str) -> bool:
        """Check if URL is within allowed scope."""
        if not url.startswith(self.base_url.rstrip("/")):
            base = self.base_url.rstrip("/")
            return url.startswith(base + "/") or url == base
        return True


# Content domain -> category key mapping for extraction
CONTENT_DOMAIN_TO_CATEGORY = {
    "admin_essentials": "admin_essentials",
    "housing": "housing",
    "schools": "schools_childcare",
    "schools_childcare": "schools_childcare",
    "healthcare": "healthcare",
    "transport": "transport",
    "daily_life": "daily_life",
    "community": "community",
    "events": "culture_leisure",
    "culture_leisure": "culture_leisure",
    "nature": "nature",
    "cost_of_living": "cost_of_living",
    "safety": "safety",
}


@dataclass
class CrawlConfig:
    """Runtime crawl configuration."""

    sources: List[CrawlSource]
    dry_run: bool = False
    parse_only: bool = False
    extract_only: bool = False
    max_documents_per_source: int = 50
    user_agent: str = "ReloPassBot/1.0 (crawler-staging)"
    timeout_seconds: int = 15
    retry_count: int = 2
