"""
Policy Assistant RAG (Sprint A): index builder.

Walks the loaded policy for a company, generates human-readable chunks
(one per benefit row, one per Section C jurisdiction override), embeds
them, and upserts into policy_assistant_chunks. Called on publish_draft
and from a manual rebuild endpoint (Sprint B).

Chunking strategy: each chunk is meant to fit comfortably in an LLM
context window WITHOUT pulling in a whole policy. One concept per
chunk so the retriever can pick exactly the relevant ones.

Source types covered in Sprint A:
  - matrix_benefit  : a base policy_config_benefits row
  - matrix_override : a Section C jurisdiction_overrides row

Out of Sprint A scope (deferred to a later sprint):
  - canonical_doc   : extracted facts from PDF documents
  - exclusion       : explicit exclusion rows (separate table)
  - evidence_rule   : evidence requirement rules
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .policy_assistant_embedder import Embedder, get_default_embedder

log = logging.getLogger(__name__)


# --- Chunk text formatters --------------------------------------------------

def format_benefit_chunk(row: Dict[str, Any]) -> str:
    """
    Render one base benefit row as a self-contained paragraph.
    Includes label, category, value (amount + currency + frequency),
    notes, and which targeting axes apply. The retriever's keyword
    matcher uses the rendered text, so include synonyms naturally.
    """
    label = row.get("benefit_label") or row.get("benefit_key") or "(unnamed benefit)"
    category = row.get("category") or "uncategorized"
    parts: List[str] = [f"{label} (category: {category})."]

    if row.get("covered") is False:
        parts.append("This benefit is NOT covered by the policy.")
    else:
        amount = row.get("amount_value")
        currency = row.get("currency_code")
        freq = row.get("unit_frequency") or "one_time"
        if amount is not None and currency:
            parts.append(f"Coverage: {currency} {amount:g} ({freq.replace('_', ' ')}).")
        elif row.get("percentage_value") is not None:
            parts.append(f"Coverage: {row['percentage_value']:g}% of reference, {freq.replace('_', ' ')}.")
        else:
            parts.append(f"Coverage frequency: {freq.replace('_', ' ')}.")

    notes = (row.get("notes") or "").strip()
    if notes:
        parts.append(f"Notes: {notes}")

    targeting_bits: List[str] = []
    for field, label_word in (
        ("assignment_types", "assignment types"),
        ("employee_levels", "employee levels"),
        ("family_statuses", "family statuses"),
    ):
        raw = row.get(field)
        items: List[str] = []
        if isinstance(raw, list):
            items = [str(x) for x in raw if x]
        elif isinstance(raw, str) and raw.startswith("["):
            try:
                items = [str(x) for x in json.loads(raw) if x]
            except Exception:
                items = []
        if items:
            targeting_bits.append(f"{label_word}: {', '.join(items)}")
    if targeting_bits:
        parts.append("Applies to: " + "; ".join(targeting_bits) + ".")

    return " ".join(parts)


def format_override_chunk(
    base_row: Dict[str, Any], override_row: Dict[str, Any]
) -> str:
    """
    Render a Section C override row as a region-specific addendum to the
    base benefit. Always references the parent benefit so the chunk is
    self-contained — the retriever may pick the override without the
    base, and the LLM still has enough context.
    """
    label = base_row.get("benefit_label") or base_row.get("benefit_key") or "(benefit)"
    countries_raw = override_row.get("jurisdiction_countries")
    countries: List[str] = []
    if isinstance(countries_raw, list):
        countries = [str(c).upper() for c in countries_raw if c]
    elif isinstance(countries_raw, str) and countries_raw.startswith("["):
        try:
            countries = [str(c).upper() for c in json.loads(countries_raw) if c]
        except Exception:
            countries = []

    parts: List[str] = [
        f"Region-specific override for '{label}' in {', '.join(countries) or '(no country)'}."
    ]

    level = override_row.get("employee_level")
    atype = override_row.get("assignment_type")
    if level and atype:
        parts.append(f"Applies to {level} on {atype} assignments.")
    elif level:
        parts.append(f"Applies to {level} (any assignment type).")
    elif atype:
        parts.append(f"Applies to {atype} assignments (any level).")
    else:
        parts.append("Applies to any employee in this region.")

    amount = override_row.get("amount_value")
    currency = override_row.get("currency_code")
    if amount is not None and currency:
        parts.append(f"Override: {currency} {amount:g}.")
    elif amount is not None:
        parts.append(f"Override amount: {amount:g} (currency inherited from base).")
    else:
        parts.append("Cap inherited from base; clauses below override.")

    reimb = (override_row.get("reimbursement_md") or "").strip()
    if reimb:
        parts.append(f"Reimbursement terms: {reimb}")
    repay = (override_row.get("repayment_md") or "").strip()
    if repay:
        parts.append(f"Repayment terms: {repay}")

    return " ".join(parts)


# --- Indexer ---------------------------------------------------------------

def index_company_policy(
    company_id: str,
    *,
    embedder: Optional[Embedder] = None,
) -> Dict[str, Any]:
    """
    Rebuild the chunk index for one company. Walks the latest published
    matrix version (or draft if no published yet) and its Section C
    overrides. Idempotent: deletes prior chunks for the company first.

    Returns a small summary dict for logging.
    """
    if not company_id:
        return {"company_id": None, "chunks": 0, "skipped": True, "reason": "no_company_id"}

    embedder = embedder or get_default_embedder()
    log.info("indexing policy for company=%s embedder=%s", company_id, embedder.name)

    benefits, overrides_by_benefit_id = _load_policy_for_indexing(company_id)
    if not benefits:
        # Wipe stale chunks; nothing to insert.
        _delete_chunks_for_company(company_id)
        return {"company_id": company_id, "chunks": 0, "skipped": False, "reason": "no_published_policy"}

    chunks: List[Dict[str, Any]] = []
    for b in benefits:
        chunks.append({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "policy_version_id": str(b.get("_policy_version_id") or "") or None,
            "source_type": "matrix_benefit",
            "source_ref": f"policy_config_benefits.{b.get('id')}",
            "chunk_text": format_benefit_chunk(b),
            "chunk_metadata": {
                "benefit_key": b.get("benefit_key"),
                "category": b.get("category"),
            },
        })
        for ov in overrides_by_benefit_id.get(str(b.get("id") or ""), []):
            chunks.append({
                "id": str(uuid.uuid4()),
                "company_id": company_id,
                "policy_version_id": str(b.get("_policy_version_id") or "") or None,
                "source_type": "matrix_override",
                "source_ref": f"policy_benefit_jurisdiction_overrides.{ov.get('id')}",
                "chunk_text": format_override_chunk(b, ov),
                "chunk_metadata": {
                    "benefit_key": b.get("benefit_key"),
                    "category": b.get("category"),
                    "jurisdiction_countries": _coerce_countries(ov.get("jurisdiction_countries")),
                    "employee_level": ov.get("employee_level"),
                    "assignment_type": ov.get("assignment_type"),
                },
            })

    # Embed in one batch for efficiency.
    embeddings = embedder.embed_batch([c["chunk_text"] for c in chunks])
    for c, emb in zip(chunks, embeddings):
        c["embedding"] = emb

    _delete_chunks_for_company(company_id)
    _insert_chunks(chunks)
    log.info(
        "indexed company=%s chunks=%d embedder=%s",
        company_id, len(chunks), embedder.name,
    )
    return {"company_id": company_id, "chunks": len(chunks), "skipped": False, "embedder": embedder.name}


# --- DB helpers ------------------------------------------------------------

def _load_policy_for_indexing(company_id: str):
    """
    Return (benefits, overrides_by_benefit_id) from the latest published
    matrix version. Falls back to draft if no published yet (so the
    assistant has something to answer with even pre-publish, useful for
    HR demoing).
    """
    cfg = db.ensure_policy_config(company_id, "compensation_allowance")
    if not cfg:
        return [], {}
    pid = str(cfg["id"])
    pub = db.get_latest_published_policy_config_version(company_id, "compensation_allowance")
    if pub:
        version = pub
    else:
        version = db.get_policy_config_draft_for_config(pid)
    if not version:
        return [], {}
    vid = str(version["id"])
    benefits = db.list_policy_config_benefits(vid) or []
    for b in benefits:
        b["_policy_version_id"] = vid
    benefit_ids = [str(b.get("id")) for b in benefits if b.get("id")]
    if benefit_ids and hasattr(db, "list_jurisdiction_overrides_for_benefit_rows"):
        overrides_by_id = db.list_jurisdiction_overrides_for_benefit_rows(benefit_ids) or {}
    else:
        overrides_by_id = {}
    return benefits, overrides_by_id


def _delete_chunks_for_company(company_id: str) -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM policy_assistant_chunks WHERE company_id = :co"),
            {"co": company_id},
        )


def _insert_chunks(chunks: List[Dict[str, Any]]) -> None:
    if not chunks:
        return
    now = datetime.utcnow().isoformat()
    # SQLite stores embedding as JSON-string; Postgres has a native vector
    # column. detect_dialect picks the right serialization.
    dialect = db.engine.dialect.name
    is_sqlite = dialect == "sqlite"
    with db.engine.begin() as conn:
        for c in chunks:
            params = {
                "id": c["id"],
                "company_id": c["company_id"],
                "policy_version_id": c.get("policy_version_id"),
                "source_type": c["source_type"],
                "source_ref": c["source_ref"],
                "chunk_text": c["chunk_text"],
                "chunk_metadata": json.dumps(c.get("chunk_metadata") or {}),
                "embedding": (
                    json.dumps(c.get("embedding") or [])
                    if is_sqlite
                    else c.get("embedding")
                ),
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                text(
                    """
                    INSERT INTO policy_assistant_chunks (
                        id, company_id, policy_version_id, source_type, source_ref,
                        chunk_text, chunk_metadata, embedding, created_at, updated_at
                    ) VALUES (
                        :id, :company_id, :policy_version_id, :source_type, :source_ref,
                        :chunk_text, :chunk_metadata, :embedding, :created_at, :updated_at
                    )
                    """
                ),
                params,
            )


def _coerce_countries(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(c).upper() for c in raw if c]
    if isinstance(raw, str) and raw.startswith("["):
        try:
            return [str(c).upper() for c in json.loads(raw) if c]
        except Exception:
            return []
    return []
