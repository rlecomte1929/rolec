"""Pydantic gate for Otto JSONL rows.

Kept off `parsers.py`'s import graph so `classify_source` stays loadable in the
corridor fact-pack job (stdlib + PyYAML only).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class FactIngestRecord(BaseModel):
    """Otto JSONL object at the ingest gate.

    Required keys match `otto_staging.immigration_fact_candidates` NOT NULL columns that
    the file must supply. Extra keys (``quote_sha256``, research flags) are allowed.
    ``source_url`` is a string, not HttpUrl: live citations include ``source_records`` UUIDs.
    """

    model_config = ConfigDict(extra="allow")

    destination_country: str
    entity_topic_key: str
    fact_key: str
    fact_text: str
    source_url: str
    entity_title: Optional[str] = None
    fact_type: Optional[str] = None
    applies_to: Optional[Dict[str, Any]] = None
    evidence_quote: Optional[str] = None
    confidence: Optional[str] = None

    @field_validator(
        "destination_country",
        "entity_topic_key",
        "fact_key",
        "fact_text",
        "source_url",
        mode="before",
    )
    @classmethod
    def _required_nonempty(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("required")
        return text


def factrow_error_from_pydantic(exc: ValidationError) -> Exception:
    """Keep the CLI/test wording: name the field, do not dump a pydantic traceback."""
    from backend.imports.otto.parsers import REQUIRED_FIELDS, FactRowError

    missing: List[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        if loc == "applies_to":
            inp = err.get("input")
            return FactRowError(
                f"applies_to must be an object, got {type(inp).__name__}"
            )
        if loc in REQUIRED_FIELDS:
            if loc not in missing:
                missing.append(loc)
    if missing:
        return FactRowError(f"missing required field(s): {', '.join(missing)}")
    msg = str(exc.errors()[0].get("msg") or "invalid record")
    return FactRowError(msg)
