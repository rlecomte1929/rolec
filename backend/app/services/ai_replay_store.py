"""
AI Replay Store (Phase 1 keystone) — a masked, replayable record of every
immigration answer / AI roadmap generation, written so the offline grader
(backend/eval/run_replay_grade.py) can re-grade past outputs without re-running
the LLM.

Why this exists
───────────────
policy_assistant_traces deliberately stores only a query_hash + chunk ids — never
the prompt or the model output (PII policy). That makes it impossible to grade a
past answer offline, to turn a thumbs-down into a regression case, or to measure
quality run-over-run. This store closes that gap WITHOUT re-introducing the leak:

  • The query and the model output pass through pii_masker.mask_pii() before they
    are persisted. Raw passport / IBAN / email / name text never lands in the row.
  • retrieved_chunk_ids are stored as-is — they point at immigration_corpus_chunks,
    which is published authority source text, not personal data. The grader joins
    on these to re-check citation validity / freshness / grounding.

The table (ai_replay_records) is service-role-only (RLS) — see the migration
supabase/migrations/<ts>_ai_replay_records.sql and the SQLite scaffold in
backend/db/misc.py.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from .. import db as _db
from .pii_masker import mask_pii


def _coerce_output_text(output: Any) -> str:
    """Render the model output as a string so it can be masked. Dicts/lists are
    JSON-serialised (sorted keys, compact) so the masked text stays grep-able."""
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, separators=(",", ":"), sort_keys=True, default=str)
    except Exception:
        return str(output)


def persist_replay_record(
    *,
    engine=None,
    trace_id: Optional[str],
    feature_key: str,
    corridor: Optional[str],
    query: str,
    output: Any,
    retrieved_chunk_ids: Optional[Sequence[str]] = None,
    prompt_version_id: Optional[str] = None,
    canary_arm: Optional[str] = None,
    result: Optional[str] = None,
    approved: bool = False,
) -> Optional[str]:
    """Persist one masked, replayable record. Returns the new row id, or None on
    failure (best-effort — never raises into the caller's request path).

    Both `query` and `output` are masked via mask_pii() before they touch the DB.
    """
    try:
        engine = engine or _db.engine
        rid = str(uuid.uuid4())
        chunk_ids = [str(c) for c in (retrieved_chunk_ids or [])]
        row = {
            "id": rid,
            "trace_id": trace_id,
            "feature_key": feature_key,
            "corridor": corridor,
            "query_masked": mask_pii(query or ""),
            "output_masked": mask_pii(_coerce_output_text(output)),
            "retrieved_chunk_ids": json.dumps(chunk_ids, separators=(",", ":")),
            "prompt_version_id": prompt_version_id,
            "canary_arm": canary_arm,
            "result": result,
            "approved": 1 if approved else 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ai_replay_records
                    (id, trace_id, feature_key, corridor, query_masked, output_masked,
                     retrieved_chunk_ids, prompt_version_id, canary_arm, result,
                     approved, created_at)
                    VALUES (:id, :trace_id, :feature_key, :corridor, :query_masked,
                            :output_masked, :retrieved_chunk_ids, :prompt_version_id,
                            :canary_arm, :result, :approved, :created_at)
                    """
                ),
                row,
            )
        return rid
    except Exception:
        return None


def list_replay_records(
    *,
    engine=None,
    feature_key: Optional[str] = None,
    corridor: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Read replay records (newest first), optionally scoped by feature/corridor.
    Used by the offline grader. Never raises — returns [] on failure."""
    try:
        engine = engine or _db.engine
        sql = "SELECT * FROM ai_replay_records WHERE 1=1"
        params: Dict[str, Any] = {"limit": int(limit)}
        if feature_key:
            sql += " AND feature_key = :feature_key"
            params["feature_key"] = feature_key
        if corridor:
            sql += " AND corridor = :corridor"
            params["corridor"] = corridor
        sql += " ORDER BY created_at DESC LIMIT :limit"
        with engine.begin() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []
