"""
W1-2 + W1-3 (BureauAI-audit remediation): persist AI-generated roadmaps as
immutable plan versions, optionally with retrieval telemetry.

Design (see docs/adr/roadmap-representation.md):
  - The live roadmap stays a case_forms projection; this module only RECORDS the
    AI-generated roadmap for reproducibility/audit. It never feeds the UI.
  - Called from the roadmap GET path, which regenerates on every read, so writes
    are IDEMPOTENT: a new version is created only when the plan's structural hash
    (corridor + result + step titles) differs from the latest stored version.
  - BEST-EFFORT: any failure is logged and swallowed — persistence must never
    break the roadmap response.

Tables (migration 20260620120000): case_plans, plan_versions, retrieval_runs,
retrieval_run_chunks. case_id FKs public.cases; the roadmap GET path only reaches
here for a case crud.get_case() already loaded, so the FK is satisfied.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger(__name__)


def _structural_hash(plan_json: Dict[str, Any]) -> str:
    """Stable hash over the substantive structure, ignoring volatile presentation
    fields (staleness timestamps, flags) so identical regenerations de-dupe."""
    steps = plan_json.get("steps") or []
    basis = {
        "corridor": plan_json.get("corridor"),
        "result": plan_json.get("result"),
        "pathway_type": plan_json.get("pathway_type"),
        "step_titles": [
            (s.get("title") or s.get("name")) for s in steps if isinstance(s, dict)
        ],
    }
    blob = json.dumps(basis, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _as_uuid(value: Any) -> Optional[str]:
    """Return value if it is a valid UUID string, else None (created_by is a
    uuid column; legacy text ids must not be inserted)."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _persist_retrieval_run(db, case_id: str, corridor: Optional[str], retrieval: Dict[str, Any]) -> Optional[str]:
    """Insert a retrieval_runs row (+ optional per-chunk rows) and return its id."""
    is_pg = db.bind.dialect.name == "postgresql"
    params_expr = "CAST(:params AS jsonb)" if is_pg else ":params"
    run_id = str(uuid.uuid4())
    chunks: List[Dict[str, Any]] = retrieval.get("chunks") or []
    db.execute(
        text(
            f"INSERT INTO retrieval_runs (id, case_id, corridor, query_text, top_k, params, chunk_count) "
            f"VALUES (:id, :c, :corr, :q, :k, {params_expr}, :n)"
        ),
        {
            "id": run_id, "c": case_id, "corr": corridor,
            "q": retrieval.get("query_text"), "k": retrieval.get("top_k"),
            "params": json.dumps(retrieval.get("params") or {}),
            "n": retrieval.get("chunk_count", len(chunks)),
        },
    )
    for rank, ch in enumerate(chunks):
        db.execute(
            text(
                "INSERT INTO retrieval_run_chunks "
                "(id, retrieval_run_id, case_id, chunk_id, rank, raw_score, adjusted_score, trust_tier, freshness, source_url) "
                "VALUES (:id, :rr, :c, :chunk, :rank, :raw, :adj, :tier, :fresh, :url)"
            ),
            {
                "id": str(uuid.uuid4()), "rr": run_id, "c": case_id,
                "chunk": str(ch.get("id") or ch.get("chunk_id") or ""),
                "rank": rank,
                "raw": ch.get("raw_score"), "adj": ch.get("adjusted_score"),
                "tier": ch.get("trust_tier"), "fresh": ch.get("freshness"),
                "url": ch.get("source_url"),
            },
        )
    return run_id


def persist_generated_plan(
    case_id: str,
    plan_json: Dict[str, Any],
    *,
    model: Optional[str] = None,
    prompt_version_id: Optional[str] = None,
    corridor: Optional[str] = None,
    created_by: Any = None,
    retrieval: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Idempotently persist a generated roadmap as an immutable plan version.

    Returns {"created": bool, "version_no": int, "plan_version_id": str|None} or
    None on any failure (best-effort; never raises).
    """
    try:
        plan_hash = _structural_hash(plan_json)
        corridor = corridor or plan_json.get("corridor")
        with SessionLocal() as db:
            is_pg = db.bind.dialect.name == "postgresql"
            pj_expr = "CAST(:pj AS jsonb)" if is_pg else ":pj"

            cp = db.execute(
                text("SELECT id, version_count FROM case_plans WHERE case_id = :c"),
                {"c": case_id},
            ).fetchone()
            if cp is None:
                cp_id = str(uuid.uuid4())
                db.execute(
                    text("INSERT INTO case_plans (id, case_id, version_count) VALUES (:id, :c, 0)"),
                    {"id": cp_id, "c": case_id},
                )
            else:
                cp_id = str(cp[0])

            latest = db.execute(
                text("SELECT plan_hash, version_no FROM plan_versions WHERE case_id = :c "
                     "ORDER BY version_no DESC LIMIT 1"),
                {"c": case_id},
            ).fetchone()
            if latest is not None and latest[0] == plan_hash:
                db.commit()  # persist the case_plans row if it was just created
                return {"created": False, "version_no": int(latest[1]), "plan_version_id": None}

            next_no = (int(latest[1]) + 1) if latest is not None else 1

            retrieval_run_id = _persist_retrieval_run(db, case_id, corridor, retrieval) if retrieval else None

            pv_id = str(uuid.uuid4())
            db.execute(
                text(
                    f"INSERT INTO plan_versions "
                    f"(id, case_plan_id, case_id, version_no, plan_json, plan_hash, model, "
                    f" prompt_version_id, retrieval_run_id, corridor, created_by) "
                    f"VALUES (:id, :cp, :c, :no, {pj_expr}, :h, :model, :pvid, :rr, :corr, :by)"
                ),
                {
                    "id": pv_id, "cp": cp_id, "c": case_id, "no": next_no,
                    "pj": json.dumps(plan_json, default=str), "h": plan_hash,
                    "model": model, "pvid": prompt_version_id, "rr": retrieval_run_id,
                    "corr": corridor, "by": _as_uuid(created_by),
                },
            )
            db.execute(
                text("UPDATE case_plans SET current_version_id = :pv, version_count = :vc, "
                     "updated_at = CURRENT_TIMESTAMP WHERE id = :cp"),
                {"pv": pv_id, "vc": next_no, "cp": cp_id},
            )
            db.commit()
            return {"created": True, "version_no": next_no, "plan_version_id": pv_id}
    except Exception:
        log.exception("persist_generated_plan failed for case %s (non-fatal)", case_id)
        return None
