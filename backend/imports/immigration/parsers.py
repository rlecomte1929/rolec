"""Read `immigration_facts_seed.json`, clean it, and reject what cannot be stored.

The seed is a faithful export of what was vetted, **not** a cleaned file: it still carries
`destination_country='UK'` (8 rows) and `confidence='med'` (7 rows). Both are values the
`public` CHECK constraints reject. Normalising here rather than in the export is deliberate —
the export stays a record of what a human actually signed off, and the two mappings stay
covered by tests against real data instead of being silently true because someone ran a
different SQL statement once.

A row that cannot be made valid is a `rejection`, never a coerced insert. `fact_type` is the
case that matters: an unrecognised value has no safe default, and guessing `other` would file a
fee under miscellany where no reviewer would ever find it again.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

#: `public.knowledge_packs` / `requirement_entities` share this CHECK list. 'UK' is NOT in it.
DESTINATION_COUNTRIES = {
    "SG", "US", "DE", "GB", "ES", "IT", "AE", "FR", "NO", "JP", "NZ", "DK",
    "BE", "AT", "PT", "CA", "AU", "NL", "CH", "SE", "IE",
}

FACT_TYPES = {
    "eligibility", "document", "step", "deadline", "fee", "where_to_apply", "account", "other",
}

CONFIDENCES = {"low", "medium", "high"}

#: The two documented data-cleaning fixes. Kept as data so the tests can assert the mapping
#: rather than re-implement it.
COUNTRY_FIXES = {"UK": "GB"}
CONFIDENCE_FIXES = {"med": "medium"}

DOMAIN = "immigration"


@dataclass(frozen=True)
class FactRow:
    """One seed fact, cleaned and known-storable."""

    destination_country: str
    topic_key: str
    entity_title: str
    fact_type: str
    fact_key: str
    fact_text: str
    applies_to: Dict[str, Any]
    source_url: str
    evidence_quote: str | None
    confidence: str
    accuracy_tier: str
    #: Human-readable note per applied fix, surfaced in the dry-run so a reviewer can see that
    #: the 8 GB rows arrived as 'UK' rather than wondering why the counts moved.
    fixes: Tuple[str, ...] = ()

    @property
    def entity_key(self) -> Tuple[str, str]:
        """Dedupe key for `requirement_entities` — matches the table's natural key."""
        return (self.destination_country, self.topic_key)

    @property
    def fact_key_full(self) -> Tuple[str, str, str]:
        """Dedupe key for `requirement_facts`, resolved to (entity, fact_key) at write time."""
        return (self.destination_country, self.topic_key, self.fact_key)

    @property
    def needs_review(self) -> bool:
        return self.accuracy_tier == "needs_review"


def normalise_text(value: str) -> str:
    """Fold a string to the form both sides of the evidence check are compared in.

    Publishers serve the same sentence with non-breaking spaces, typographic quotes and soft
    hyphens; a vetted quote is typed with ASCII ones. Comparing raw would fail honest matches
    and push real evidence onto the manual worklist, so both sides are folded identically.

    This is a presentation fold, not a content edit: it never inserts, removes or reorders
    words, so it cannot make a quote match a document that does not contain it.
    """
    text = unicodedata.normalize("NFKC", value)
    text = (
        text.replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-")
        .replace("­", "")
    )
    return re.sub(r"\s+", " ", text).strip()


class RowError(ValueError):
    """The seed file itself is unreadable — not a per-row problem."""


def _clean_row(raw: Dict[str, Any], index: int) -> Tuple[FactRow | None, str | None]:
    """Return (row, None) or (None, rejection). Never raises on row-level problems."""
    where = f"row {index}"

    def _str(key: str) -> str:
        return str(raw.get(key) or "").strip()

    country_raw = _str("destination_country").upper()
    topic_key = _str("topic_key")
    fact_key = _str("fact_key")
    fact_text = _str("fact_text")
    source_url = _str("source_url")

    label = f"{country_raw}/{topic_key}/{fact_key}" if topic_key or fact_key else where

    fixes: List[str] = []

    country = COUNTRY_FIXES.get(country_raw, country_raw)
    if country != country_raw:
        fixes.append(f"destination_country {country_raw}->{country}")
    if country not in DESTINATION_COUNTRIES:
        return None, f"{label}: destination_country {country_raw!r} is not a supported country"

    confidence_raw = (_str("confidence") or "medium").lower()
    confidence = CONFIDENCE_FIXES.get(confidence_raw, confidence_raw)
    if confidence != confidence_raw:
        fixes.append(f"confidence {confidence_raw!r}->{confidence!r}")
    if confidence not in CONFIDENCES:
        return None, f"{label}: confidence {confidence_raw!r} is not one of {sorted(CONFIDENCES)}"

    fact_type = _str("fact_type").lower()
    if fact_type not in FACT_TYPES:
        # No default. See the module docstring: 'other' would hide it from review.
        return None, f"{label}: fact_type {fact_type!r} is not one of {sorted(FACT_TYPES)}"

    for name, value in (("topic_key", topic_key), ("fact_key", fact_key),
                        ("fact_text", fact_text), ("source_url", source_url)):
        if not value:
            return None, f"{label}: {name} is empty"

    if source_url.startswith("http://"):
        # One real seed row (BE/d_visa_post_approval) recorded the scheme as http. The host
        # itself 301s to https and serves the identical document, so this upgrades the
        # transport without changing what is cited — and it is recorded in `fixes` so the
        # preview shows it rather than it happening quietly. A host with no https answer
        # fails at fetch time and never reaches the table.
        source_url = "https://" + source_url[len("http://"):]
        fixes.append("source_url http->https")
    if not source_url.startswith("https://"):
        return None, f"{label}: source_url is not http(s) ({source_url!r})"

    applies_to = raw.get("applies_to") or {}
    if not isinstance(applies_to, dict):
        return None, f"{label}: applies_to must be an object, got {type(applies_to).__name__}"

    quote = (raw.get("evidence_quote") or "").strip() or None

    return FactRow(
        destination_country=country,
        topic_key=topic_key,
        entity_title=_str("entity_title") or topic_key.replace("_", " ").title(),
        fact_type=fact_type,
        fact_key=fact_key,
        fact_text=fact_text,
        applies_to=applies_to,
        source_url=source_url,
        evidence_quote=quote,
        confidence=confidence,
        accuracy_tier=_str("accuracy_tier") or "needs_review",
        fixes=tuple(fixes),
    ), None


@dataclass
class SeedFile:
    rows: List[FactRow] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)

    @property
    def fixed(self) -> List[FactRow]:
        return [r for r in self.rows if r.fixes]

    @property
    def needs_review(self) -> List[FactRow]:
        return [r for r in self.rows if r.needs_review]

    @property
    def source_urls(self) -> List[str]:
        seen: Dict[str, None] = {}
        for row in self.rows:
            seen.setdefault(row.source_url, None)
        return list(seen)


def read_seed(path: Path) -> SeedFile:
    """Load and clean the seed. Duplicate natural keys inside the file are rejections.

    Two rows sharing `(country, topic_key, fact_key)` cannot both be stored — the second would
    be indistinguishable from a re-run of the first — so the collision is surfaced rather than
    resolved by insertion order.
    """
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RowError(f"cannot read seed: {exc}") from exc

    if not isinstance(payload, list):
        raise RowError(f"expected a JSON array of facts, got {type(payload).__name__}")

    seed = SeedFile()
    seen: Dict[Tuple[str, str, str], int] = {}

    for index, raw in enumerate(payload, start=1):
        if not isinstance(raw, dict):
            seed.rejections.append(f"row {index}: expected an object")
            continue
        row, rejection = _clean_row(raw, index)
        if rejection or row is None:
            seed.rejections.append(rejection or f"row {index}: unusable")
            continue
        if row.fact_key_full in seen:
            seed.rejections.append(
                f"{'/'.join(row.fact_key_full)}: duplicate of row {seen[row.fact_key_full]} "
                "in the seed file"
            )
            continue
        seen[row.fact_key_full] = index
        seed.rows.append(row)

    return seed


def summarise_seed(seed: SeedFile) -> str:
    lines = [
        f"seed:     {len(seed.rows)} fact(s) across "
        f"{len({r.destination_country for r in seed.rows})} country(ies), "
        f"{len(seed.source_urls)} source URL(s)",
    ]
    if seed.fixed:
        lines.append(f"    cleaned: {len(seed.fixed)} row(s)")
        for fix in sorted({f for r in seed.fixed for f in r.fixes}):
            n = sum(1 for r in seed.fixed if fix in r.fixes)
            lines.append(f"      - {fix}  ({n} row(s))")
    if seed.needs_review:
        lines.append(
            f"    {len(seed.needs_review)} row(s) tagged accuracy_tier='needs_review' "
            "— review these first"
        )
    if seed.rejections:
        lines.append(f"\n  {len(seed.rejections)} row(s) REJECTED (nothing will be written):")
        lines += [f"    - {r}" for r in seed.rejections]
    return "\n".join(lines)


def group_by_url(rows: Sequence[FactRow]) -> Dict[str, List[FactRow]]:
    """Facts sharing a URL share one `knowledge_docs` row, so they fetch once."""
    grouped: Dict[str, List[FactRow]] = {}
    for row in rows:
        grouped.setdefault(row.source_url, []).append(row)
    return grouped
