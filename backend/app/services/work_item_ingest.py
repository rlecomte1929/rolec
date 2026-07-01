"""
Mission Control P1 — ingestion: map intake rows into canonical work_item dicts.

Pure (no DB): `build_work_items(source, rows, existing_keys)` returns the new
work_items to insert, skipping any whose (source, source_id) is already ingested
(idempotent). Bodies are PII-masked and each item is triaged on the way in, so the
console shows a ranked, classified demand from the moment it lands. The DB writer is
a thin caller (in the router); this layer is the testable core.

Supported sources today: `feedback` (the bug/idea widget) and `support` tickets.
ai_feedback / contradiction mappers are a documented extension point — add a mapper
to _MAPPERS and they flow through unchanged.
"""
import hashlib
import re
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from .pii_masker import mask_pii
from .work_item_triage import classify_demand

_FEEDBACK_KIND = {"bug": "bug", "idea": "idea", "other": None}


def _title_from(text: str, limit: int = 120) -> str:
    if not text:
        return "(untitled)"
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:limit].strip() or "(untitled)"


def _dedupe_key(title: str) -> str:
    norm = re.sub(r"\s+", " ", (title or "").lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def _map_feedback(row: Dict[str, Any]) -> Dict[str, Any]:
    msg = row.get("message") or ""
    return {
        "source_id": str(row.get("id")),
        "source_url": row.get("page_url"),
        "title": _title_from(msg),
        "raw_body": msg,
        "kind_hint": _FEEDBACK_KIND.get(row.get("category")),
        "reporter_role": None,
        "company_id": None,
    }


def _map_support(row: Dict[str, Any]) -> Dict[str, Any]:
    content = row.get("raw_content") or ""
    return {
        "source_id": str(row.get("id")),
        "source_url": None,
        "title": row.get("subject") or _title_from(content),
        "raw_body": content,
        "kind_hint": None,
        "reporter_role": row.get("role") or row.get("from_email"),
        "company_id": row.get("company_id"),
    }


_MAPPERS = {"feedback": _map_feedback, "support": _map_support}


def build_work_items(
    source: str,
    rows: List[Dict[str, Any]],
    existing_keys: FrozenSet[Tuple[str, Optional[str]]] = frozenset(),
) -> List[Dict[str, Any]]:
    mapper = _MAPPERS.get(source)
    if mapper is None:
        return []

    out: List[Dict[str, Any]] = []
    for row in rows:
        mapped = mapper(row)
        source_id = mapped["source_id"]
        if (source, source_id) in existing_keys:
            continue
        body = mask_pii(mapped["raw_body"])
        triage = classify_demand(mapped["title"], body, kind_hint=mapped["kind_hint"])
        out.append({
            "source": source,
            "source_id": source_id,
            "source_url": mapped["source_url"],
            "kind": triage["kind"],
            "title": mapped["title"],
            "body": body,
            "reporter_role": mapped["reporter_role"],
            "company_id": mapped["company_id"],
            "status": "triaged",
            "priority": triage["priority"],
            "complexity": triage["complexity"],
            "auto_fixable": triage["auto_fixable"],
            "triage_json": triage,
            "dedupe_key": _dedupe_key(mapped["title"]),
        })
    return out
