"""
Load crawl sources from config files.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional

from .models import CrawlSource

log = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "sources.json"
FIXTURES_PATH = _CONFIG_DIR / "fixtures" / "sources_oslo_pilot.json"


def _dict_to_source(d: dict) -> CrawlSource:
    return CrawlSource(
        source_name=d.get("source_name", ""),
        base_url=d.get("base_url", ""),
        country_code=d.get("country_code", ""),
        country_name=d.get("country_name", ""),
        city_name=d.get("city_name"),
        source_type=d.get("source_type", "official"),
        trust_tier=d.get("trust_tier", "T0"),
        content_domain=d.get("content_domain", "admin_essentials"),
        crawl_strategy=d.get("crawl_strategy", "single_page"),
        allowed_paths=d.get("allowed_paths", []),
        denied_paths=d.get("denied_paths", []),
        max_depth=d.get("max_depth", 1),
        language_code=d.get("language_code", "en"),
        is_active=d.get("is_active", True),
        notes=d.get("notes"),
    )


def load_sources(config_path: Optional[Path] = None) -> List[CrawlSource]:
    """Load sources from JSON config."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        path = FIXTURES_PATH
    if not path.exists():
        log.warning("No crawl source config found at %s", path)
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.error("Failed to load crawl config %s: %s", path, e)
        return []

    sources_raw = data.get("sources", data) if isinstance(data, dict) else data
    if not isinstance(sources_raw, list):
        sources_raw = [sources_raw]

    return [_dict_to_source(s) for s in sources_raw if isinstance(s, dict) and s.get("source_name") and s.get("base_url")]


def get_sources_for_scope(
    sources: List[CrawlSource],
    *,
    source_name: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    content_domain: Optional[str] = None,
) -> List[CrawlSource]:
    """Filter sources by scope."""
    out = [s for s in sources if s.is_active]
    if source_name:
        out = [s for s in out if s.source_name == source_name]
    if country_code:
        out = [s for s in out if s.country_code.upper() == country_code.upper()]
    if city_name:
        out = [s for s in out if (s.city_name or "").lower() == city_name.lower()]
    if content_domain:
        out = [s for s in out if s.content_domain == content_domain]
    return out
