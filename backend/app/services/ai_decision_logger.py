"""
ai_decision_logger — production-time AI-recommendation audit write (AIQ-1694·3).

`ai_decisions` (migration 20260527000000 + 20261007000000) records the model output
(`ai_output`), the human decision (`decision`/`reason`/`outcome`), and — since AIQ-1694 —
the PII-masked INPUT (`input_context`) that produced the recommendation. The existing
`POST /api/ai/decisions` writes on a *human* action; this module writes the
**production-time** record (`decision = 'produced'`) when the AI produces a recommendation,
so every recommendation path leaves a durable, verifiable trail.

COMPLIANCE (root CLAUDE.md GDPR hard gate): the input is masked via `pii_masker.mask_pii`
BEFORE it is written — raw user PII never reaches `input_context`. Masking is applied to
every string leaf of the input (structure preserved).

Best-effort: a logging failure must NEVER fail the recommendation request — mirrors
`ai_trace_logger`. All writes are wrapped; the function returns the new row id or None.

NOTE (from AIQ-1694·2): `(feature, recommendation_id)` is NOT unique in prod, so there is
no DB upsert — this always INSERTs a fresh 'produced' row; converging it with the later
human decision is application-level (out of scope here).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from .pii_masker import mask_pii

log = logging.getLogger(__name__)

# decision sentinel for a production-time record (before any human acts).
# Allowed by ai_decisions_decision_check as of migration 20261007000000.
PRODUCED = "produced"


def mask_input_context(value: Any) -> Any:
    """Recursively mask every string leaf of the input via `mask_pii`, preserving
    structure. Pure + total (mask_pii never raises), so it is safe on any input and
    unit-testable without a DB. This is the compliance-load-bearing step."""
    if isinstance(value, str):
        return mask_pii(value)
    if isinstance(value, dict):
        return {k: mask_input_context(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_input_context(v) for v in value]
    return value


_INSERT_SQL = """
INSERT INTO ai_decisions (
    id, created_at, updated_at, actor_id, company_id,
    feature, recommendation_id, ai_output, decision,
    input_context, model_name, produced_at
) VALUES (
    CAST(:id AS uuid), :now, :now,
    CASE WHEN :actor IS NULL THEN NULL ELSE CAST(:actor AS uuid) END, :company,
    :feature, :rec_id, CAST(:ai_output AS jsonb), :decision,
    CAST(:input_context AS jsonb), :model_name, :produced_at
)
"""


def record_ai_recommendation(
    *,
    feature: str,
    recommendation_id: str,
    input_context: Any,
    ai_output: Any,
    company_id: Optional[str],
    actor_id: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Optional[str]:
    """Write a production-time `ai_decisions` row (decision='produced') linking the
    PII-masked input, the model output, and provenance. Best-effort — never raises
    into the caller. Returns the new row id, or None on any failure."""
    try:
        masked_input = mask_input_context(input_context)
        # Lazy import to avoid a circular import at module load (mirrors ai_trace_logger).
        from ...database import db
        from sqlalchemy import text

        new_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        params = {
            "id": new_id,
            "now": now,
            "actor": actor_id,
            "company": company_id,
            "feature": feature,
            "rec_id": recommendation_id,
            "ai_output": json.dumps(ai_output),
            "decision": PRODUCED,
            "input_context": json.dumps(masked_input),
            "model_name": model_name,
            "produced_at": now,
        }
        with db.engine.begin() as conn:
            conn.execute(text(_INSERT_SQL), params)
        return new_id
    except Exception as exc:  # never fail the recommendation on an audit-write error
        log.warning(
            "record_ai_recommendation failed feature=%s rec=%s: %s",
            feature, recommendation_id, exc,
        )
        return None
