"""RP-MEM-001 / RP-MEM-003 — in-process approved-catalog cache with write invalidation.

Render is --workers 1. TTL is minutes, not 30 days. Keys include a per-country
generation token so a requirement_items write drops only that country's entries.
"""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

TTL_SECONDS = 15 * 60

_generation: Dict[str, int] = {}
# (country, purpose, gen) -> (expires_at, snapshots)
_store: Dict[Tuple[str, str, int], Tuple[float, Tuple[Dict[str, Any], ...]]] = {}

_SNAPSHOT_KEYS = (
    "id",
    "country_code",
    "purpose",
    "pillar",
    "title",
    "description",
    "severity",
    "owner",
    "required_fields_json",
    "citations_json",
    "applies_to_assignment_types_json",
    "applies_to_nationality_classes_json",
    "applies_to_regimes_json",
    "verification_status",
    "review_status",
    "attestation_status",
    "attested_by",
    "attested_at",
    "non_obvious",
    "timing",
    "last_verified_at",
)


def _country(code: Optional[str]) -> str:
    return (code or "").strip().upper()


def _purpose(purpose: Optional[str]) -> str:
    return (purpose or "").strip().lower()


def generation_for(country_code: str) -> int:
    return _generation.get(_country(country_code), 0)


def reset_for_tests() -> None:
    _generation.clear()
    _store.clear()


def invalidate_country(
    country_code: str,
    *,
    item_id: Optional[str] = None,
    reason: str = "",
) -> int:
    key = _country(country_code)
    if not key:
        return 0
    nxt = _generation.get(key, 0) + 1
    _generation[key] = nxt
    drop = [k for k in _store if k[0] == key]
    for k in drop:
        _store.pop(k, None)
    log.info(
        "catalog_cache: invalidate country=%s gen=%s item_id=%s reason=%s",
        key,
        nxt,
        item_id,
        reason or "write",
    )
    return nxt


def _snapshot(item: Any) -> Dict[str, Any]:
    return {k: getattr(item, k, None) for k in _SNAPSHOT_KEYS}


def _restore(rows: Sequence[Dict[str, Any]]) -> List[Any]:
    return [SimpleNamespace(**row) for row in rows]


def get_catalog_rows(
    country_code: str,
    purpose: Optional[str],
    loader: Callable[[], Iterable[Any]],
    *,
    now: Optional[float] = None,
    ttl_seconds: int = TTL_SECONDS,
) -> List[Any]:
    """Return destination catalog rows (all review_status), compiling via `loader` on miss."""
    country = _country(country_code)
    purpose_key = _purpose(purpose)
    gen = generation_for(country)
    cache_key = (country, purpose_key, gen)
    clock = time.time() if now is None else now
    hit = _store.get(cache_key)
    if hit is not None and hit[0] > clock:
        log.info("catalog_cache: cache_hit country=%s purpose=%s gen=%s", country, purpose_key, gen)
        return _restore(hit[1])

    log.info("catalog_cache: cache_miss country=%s purpose=%s gen=%s", country, purpose_key, gen)
    loaded = tuple(_snapshot(item) for item in loader())
    _store[cache_key] = (clock + ttl_seconds, loaded)
    return _restore(loaded)
