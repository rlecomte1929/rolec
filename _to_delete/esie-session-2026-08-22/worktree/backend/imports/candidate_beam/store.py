"""Persistence for candidate beam runs and their ranked items.

Raw SQL over a caller-owned Connection, mirroring `backend/imports/otto/executor.py`. No
ORM model: `candidate_beam_*` is authoring-layer storage that only this package and its
admin router touch, and adding it to `app/models.py` would put it in the import graph of
every serving engine for no benefit.

The three writers exist because a beam run is resumable, not atomic. `create_run` opens it,
`record_pass` lands ONE pass at a time, and `persist_candidates` closes it. A run that
crashed after four of five passes keeps those four and retries only the fifth — which is
the entire reason the pipeline is shaped as separate calls rather than one long request.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

log = logging.getLogger(__name__)

RUN_GENERATING = "generating"
RUN_PENDING_REVIEW = "pending_review"
RUN_FAILED = "failed"

MIN_PASSES = 2
MAX_PASSES = 7

#: Ranking-derived columns. Re-finalizing refreshes exactly these and nothing else — see
#: `persist_candidates`.
_RANKING_COLUMNS = (
    "rank",
    "pass_frequency",
    "passes_total",
    "confidence_band",
    "flagged",
    "source_missing",
    "title",
    "official_guidance",
    "actual_reality",
    "action_required",
    "source",
    "category",
    "variants",
)


def _is_postgres(conn: Any) -> bool:
    try:
        return conn.dialect.name == "postgresql"
    except Exception:  # a test double with no dialect — bare binds are right for SQLite
        return False


def _json_bind(conn: Any, param: str) -> str:
    """`CAST(:p AS jsonb)` on Postgres, bare `:p` on SQLite.

    The house convention (`_jsonb_bind` in immigration_intake_profile). psycopg2 cannot
    adapt a Python dict, and the backend test lane runs SQLite where the column is TEXT, so
    the split has to be explicit at the call site rather than hidden in a helper that
    guesses.
    """
    return f"CAST(:{param} AS jsonb)" if _is_postgres(conn) else f":{param}"


def _uuid_bind(conn: Any, param: str) -> str:
    return f"CAST(:{param} AS uuid)" if _is_postgres(conn) else f":{param}"


def _now(conn: Any) -> str:
    """`now()` on Postgres, `CURRENT_TIMESTAMP` on SQLite.

    Not cosmetic: the backend test lane runs SQLite, which has no `now()`, so every UPDATE
    here would raise OperationalError under test while working in production — the exact
    split that makes a bug invisible until it ships.
    """
    return "now()" if _is_postgres(conn) else "CURRENT_TIMESTAMP"


def candidate_uid_for(title: str) -> str:
    """A stable id for a candidate, derived from its representative title.

    Stable across re-finalize is the requirement: rank changes when a later pass shifts the
    agreement counts, so keying on rank would make every rebuild look like a new set of
    candidates and orphan the human verdicts attached to the old ones. The title is what a
    reviewer recognises, so it is what identity follows.
    """
    digest = hashlib.sha256((title or "").strip().lower().encode("utf-8")).hexdigest()
    return f"cb-{digest[:16]}"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_run(
    conn: Any,
    *,
    corridor: str,
    employee_type: str,
    passes_requested: int,
    context: Optional[str] = None,
    origin_country: Optional[str] = None,
    dest_country: Optional[str] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    created_by: Optional[str] = None,
) -> str:
    """Open a run in `generating`. Returns its id.

    The clamp is re-asserted here even though the schema CHECK enforces it, because a
    ValueError naming the bound is a better answer than a constraint violation from three
    layers down.
    """
    if not MIN_PASSES <= passes_requested <= MAX_PASSES:
        raise ValueError(
            f"passes_requested must be between {MIN_PASSES} and {MAX_PASSES}, got {passes_requested}"
        )

    run_id = str(uuid.uuid4())
    conn.execute(
        text(
            f"""
            INSERT INTO public.candidate_beam_runs
                (id, corridor, origin_country, dest_country, employee_type, context,
                 passes_requested, passes_completed, llm_provider, llm_model, status,
                 pass_outputs, pass_meta, candidate_count, created_by)
            VALUES
                ({_uuid_bind(conn, 'id')}, :corridor, :origin_country, :dest_country,
                 :employee_type, :context, :passes_requested, 0, :llm_provider, :llm_model,
                 :status, {_json_bind(conn, 'pass_outputs')}, {_json_bind(conn, 'pass_meta')},
                 0, :created_by)
            """
        ),
        {
            "id": run_id,
            "corridor": corridor,
            "origin_country": origin_country,
            "dest_country": dest_country,
            "employee_type": employee_type,
            "context": context,
            "passes_requested": passes_requested,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "status": RUN_GENERATING,
            "pass_outputs": json.dumps([]),
            "pass_meta": json.dumps([]),
            "created_by": created_by,
        },
    )
    return run_id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def _loads(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value if isinstance(value, list) else [value]
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def load_run(conn: Any, run_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            f"""
            SELECT id, corridor, origin_country, dest_country, employee_type, context,
                   passes_requested, passes_completed, llm_provider, llm_model, status,
                   error, pass_outputs, pass_meta, candidate_count, created_by
              FROM public.candidate_beam_runs
             WHERE id = {_uuid_bind(conn, 'run_id')}
            """
        ),
        {"run_id": run_id},
    ).mappings().first()
    if row is None:
        return None
    run = dict(row)
    run["pass_outputs"] = _loads(run.get("pass_outputs"))
    run["pass_meta"] = _loads(run.get("pass_meta"))
    return run


def completed_pass_numbers(run: Dict[str, Any]) -> List[int]:
    """Pass numbers that actually SUCCEEDED — the ones finalize may rank."""
    return sorted(
        {
            int(m.get("pass"))
            for m in run.get("pass_meta") or []
            if m.get("ok") and m.get("pass") is not None
        }
    )


def next_pass_number(run: Dict[str, Any]) -> Optional[int]:
    """The lowest slot not yet successfully completed, or None when the run is full.

    Lowest-first rather than next-after-the-highest, so a run whose pass 2 failed retries
    pass 2 on resume instead of skipping ahead and leaving a permanent hole.
    """
    done = set(completed_pass_numbers(run))
    for number in range(1, int(run.get("passes_requested") or 0) + 1):
        if number not in done:
            return number
    return None


# ---------------------------------------------------------------------------
# Record one pass
# ---------------------------------------------------------------------------


def record_pass(
    conn: Any,
    *,
    run_id: str,
    pass_number: int,
    framing: str,
    items: Sequence[Dict[str, Any]],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Land ONE pass, replacing any previous attempt at that slot.

    Replace rather than append: a retried pass must not leave the failed attempt's entry
    behind, or `passes_completed` and the ranking input would both double-count a slot that
    ran twice. The failed attempt is not lost — its error is carried forward in the
    replacement's meta under `previous_error`, so the resume history stays visible without
    corrupting the counts.
    """
    run = load_run(conn, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")

    prior_meta = {int(m["pass"]): m for m in run["pass_meta"] if m.get("pass") is not None}
    previous = prior_meta.get(pass_number)
    if previous is not None and previous.get("error") and not meta.get("previous_error"):
        meta = {**meta, "previous_error": previous.get("error")}

    outputs = [o for o in run["pass_outputs"] if o.get("pass") != pass_number]
    metas = [m for m in run["pass_meta"] if m.get("pass") != pass_number]

    if meta.get("ok"):
        outputs.append({"pass": pass_number, "framing": framing, "items": list(items)})
    metas.append({**meta, "pass": pass_number, "framing": framing})

    outputs.sort(key=lambda o: o.get("pass", 0))
    metas.sort(key=lambda m: m.get("pass", 0))
    completed = len({m["pass"] for m in metas if m.get("ok")})

    conn.execute(
        text(
            f"""
            UPDATE public.candidate_beam_runs
               SET pass_outputs = {_json_bind(conn, 'pass_outputs')},
                   pass_meta = {_json_bind(conn, 'pass_meta')},
                   passes_completed = :passes_completed,
                   updated_at = {_now(conn)}
             WHERE id = {_uuid_bind(conn, 'run_id')}
            """
        ),
        {
            "pass_outputs": json.dumps(outputs),
            "pass_meta": json.dumps(metas),
            "passes_completed": completed,
            "run_id": run_id,
        },
    )
    return {"passes_completed": completed, "pass_outputs": outputs, "pass_meta": metas}


def mark_failed(conn: Any, *, run_id: str, error: str) -> None:
    """A run that cannot continue. Kept as an audit row, never deleted."""
    conn.execute(
        text(
            f"""
            UPDATE public.candidate_beam_runs
               SET status = :status, error = :error, updated_at = {_now(conn)}
             WHERE id = {_uuid_bind(conn, 'run_id')}
            """
        ),
        {"status": RUN_FAILED, "error": error[:2000], "run_id": run_id},
    )


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------


_UPSERT_ITEM_PG = """
    INSERT INTO public.candidate_beam_items
        (run_id, candidate_uid, rank, pass_frequency, passes_total, confidence_band,
         flagged, source_missing, title, official_guidance, actual_reality,
         action_required, source, category, variants, status)
    VALUES
        (CAST(:run_id AS uuid), :candidate_uid, :rank, :pass_frequency, :passes_total,
         :confidence_band, :flagged, :source_missing, :title, :official_guidance,
         :actual_reality, :action_required, :source, :category,
         CAST(:variants AS jsonb), 'pending_review')
    ON CONFLICT (run_id, candidate_uid) DO UPDATE SET
        rank = EXCLUDED.rank,
        pass_frequency = EXCLUDED.pass_frequency,
        passes_total = EXCLUDED.passes_total,
        confidence_band = EXCLUDED.confidence_band,
        flagged = EXCLUDED.flagged,
        source_missing = EXCLUDED.source_missing,
        title = EXCLUDED.title,
        official_guidance = EXCLUDED.official_guidance,
        actual_reality = EXCLUDED.actual_reality,
        action_required = EXCLUDED.action_required,
        source = EXCLUDED.source,
        category = EXCLUDED.category,
        variants = EXCLUDED.variants,
        updated_at = now()
"""

_UPSERT_ITEM_SQLITE = _UPSERT_ITEM_PG.replace("CAST(:run_id AS uuid)", ":run_id").replace(
    "CAST(:variants AS jsonb)", ":variants"
).replace("now()", "CURRENT_TIMESTAMP")


def persist_candidates(
    conn: Any,
    *,
    run_id: str,
    candidates: Sequence[Dict[str, Any]],
    passes_total: int,
) -> int:
    """Write the ranked candidates and close the run.

    **A re-finalize refreshes the ranking and never the verdict.** The upsert touches only
    the ranking-derived columns; `status`, `review_note`, `reviewed_by` and every import
    audit column are left exactly as they were. Rebuilding after a late pass must not
    silently un-approve what a human already judged, and it must not reset an item that has
    already been imported — the schema's freeze depends on those columns surviving.

    Items that no longer appear in a rebuild are left in place rather than deleted, because
    deleting one that a human already approved or imported would destroy the audit trail
    the import columns exist to keep.
    """
    sql = text(_UPSERT_ITEM_PG if _is_postgres(conn) else _UPSERT_ITEM_SQLITE)
    written = 0

    for candidate in candidates:
        title = str(candidate.get("title") or "").strip()
        if not title:
            continue
        conn.execute(
            sql,
            {
                "run_id": run_id,
                "candidate_uid": candidate.get("candidate_uid") or candidate_uid_for(title),
                "rank": candidate.get("rank"),
                "pass_frequency": candidate.get("pass_frequency"),
                "passes_total": candidate.get("passes_total") or passes_total,
                "confidence_band": candidate.get("confidence_band"),
                "flagged": bool(candidate.get("flagged")),
                "source_missing": bool(candidate.get("source_missing")),
                "title": title,
                "official_guidance": candidate.get("official_guidance"),
                "actual_reality": candidate.get("actual_reality"),
                "action_required": candidate.get("action_required"),
                "source": candidate.get("source"),
                "category": candidate.get("category"),
                "variants": json.dumps(candidate.get("variants") or []),
            },
        )
        written += 1

    conn.execute(
        text(
            f"""
            UPDATE public.candidate_beam_runs
               SET status = :status, candidate_count = :candidate_count, updated_at = {_now(conn)}
             WHERE id = {_uuid_bind(conn, 'run_id')}
            """
        ),
        {"status": RUN_PENDING_REVIEW, "candidate_count": written, "run_id": run_id},
    )
    return written
