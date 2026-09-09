"""Admin catalog display helpers — not a serving engine.

`country_profiles.country_code` is mixed ISO-2 ("DE") and FULL UPPERCASE names
("FRANCE", "AUSTRALIA"). Requirement rows follow the catalog-name convention.
The admin list must look up both keys and must not show a high confidence score
when there is nothing in the catalog to be confident about.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from .requirements_country_key import iso_to_catalog_name, resolve_catalog_country, to_iso_alpha2


def catalog_lookup_keys(country_code: str) -> list[str]:
    """Keys that may hold sources / requirements for one destination profile."""
    keys: set[str] = set()
    raw = (country_code or "").strip()
    if not raw:
        return []
    keys.add(raw)
    keys.add(raw.upper())
    iso = to_iso_alpha2(raw)
    if iso:
        keys.add(iso)
        name = iso_to_catalog_name(iso)
        if name:
            keys.add(name)
    catalog = resolve_catalog_country(raw)
    if catalog and catalog != "UNKNOWN":
        keys.add(catalog)
    return sorted(keys)


def evidence_backed_confidence(
    score: Optional[float],
    requirements_count: int,
    source_count: int,
) -> Optional[float]:
    """Drop or cap a stored research score when the catalog has no evidence.

    An empty catalog with no sources cannot be "high confidence". Requirements
    with no sources cannot claim the high band either.
    """
    if requirements_count <= 0:
        return None
    if source_count <= 0:
        if score is None:
            return None
        return min(float(score), 0.39)
    return score


def unique_domains(domains: Iterable[str], *, limit: int = 3) -> list[str]:
    seen: list[str] = []
    for domain in domains:
        if domain and domain not in seen:
            seen.append(domain)
        if len(seen) >= limit:
            break
    return seen


def dedupe_by_id(rows: Sequence[object]) -> list:
    out = []
    seen: set = set()
    for row in rows:
        rid = getattr(row, "id", None)
        if rid in seen:
            continue
        seen.add(rid)
        out.append(row)
    return out
