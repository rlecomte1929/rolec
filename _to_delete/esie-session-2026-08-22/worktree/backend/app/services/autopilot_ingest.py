"""autopilot_ingest.py — Phase 1: nightly feedback → dedup → engineered Notion task.

Queries product-stream feedback directly (bypassing the 500-row admin list), clusters it by the
error **fingerprint** in `client_context` (free, deterministic dedup — the #1 cost lever against a
duplicate-heavy friends campaign), picks one representative per cluster, and dispatches it to the
AI Work Queue via the existing `engineer_task` + `create_work_queue_task`.

Every run is gated by the governor (kill-switch + monthly budget), capped per night, emits funnel
events, and each `engineer_task` call is cost-traced (`feature_key='autopilot.dispatch'`) so the
budget meter actually sees autopilot spend. `dry_run=True` does everything EXCEPT the LLM call,
the Notion write, and the DB mutation — so the full path can be exercised on staging for free.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db import SessionLocal
from . import autopilot_events as ev
from . import notion_work_queue as nwq
from .ai_trace_logger import TraceSession
from .autopilot_governor import gate, nightly_cap, stage_feature_key
from .feedback_task_engineer import (
    _FAILED_REQUEST_LIMIT,
    engineer_task,
    extract_confirmed_signals,
    format_diagnostics,
    score_task,
    status_from_complexity,
)
from .feedback_triage import classify

log = logging.getLogger(__name__)

_HARD_QUERY_CAP = 1000   # safety ceiling on rows pulled per run before dedup
_DISPATCH_MODEL = "claude-sonnet-4-6"


# ── candidate query ──────────────────────────────────────────────────────────

def _query_candidates(session: Any, lookback_hours: int) -> List[Dict[str, Any]]:
    """Product-stream feedback not yet dispatched or dismissed, newest first. Direct DB read
    (bypasses the 500-row admin list). Portable SQL (SQLite dev + Postgres)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    rows = session.execute(
        text(
            "SELECT CAST(f.id AS TEXT) AS id, f.message, f.category, f.page_url, "
            "       f.reporter_name, f.client_context "
            "FROM feedback f "
            "LEFT JOIN feedback_status fs "
            "  ON fs.stream = 'product' AND fs.source_id = CAST(f.id AS TEXT) "
            "WHERE (fs.dispatch_status IS NULL OR fs.dispatch_status <> 'dispatched') "
            "  AND fs.dismissed_at IS NULL "
            "  AND f.created_at >= :since "
            "ORDER BY f.created_at DESC "
            "LIMIT :cap"
        ),
        {"since": since, "cap": _HARD_QUERY_CAP},
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r[0], "message": r[1] or "", "category": r[2] or "bug",
            "page_url": r[3], "reporter_name": r[4], "client_context": _parse_ctx(r[5]),
        })
    return out


def _parse_ctx(raw: Any) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


# ── dedup ────────────────────────────────────────────────────────────────────

def dedup_key(row: Dict[str, Any]) -> str:
    """Deterministic cluster key. Prefer the error fingerprint (message+failing-frame hash) so
    every re-report of the same bug collapses to one; fall back to (category, page/route) when a
    row carries no diagnostics."""
    ctx = row.get("client_context") or {}
    for err in (ctx.get("recentErrors") or []):
        fp = err.get("fingerprint")
        if fp:
            return f"fp:{fp}"
    route = (ctx.get("route") or row.get("page_url") or "").split("?")[0]
    return "attr:" + hashlib.sha256(f"{row.get('category')}|{route}".encode()).hexdigest()[:16]


def cluster(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group rows by dedup_key → clusters, each with a representative (richest diagnostics)."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(dedup_key(r), []).append(r)

    def _diag_richness(r: Dict[str, Any]) -> int:
        ctx = r.get("client_context") or {}
        return len(ctx.get("recentErrors") or []) + len(ctx.get("recentFailedRequests") or [])

    clusters: List[Dict[str, Any]] = []
    for key, members in groups.items():
        rep = max(members, key=_diag_richness)
        clusters.append({"key": key, "representative": rep, "size": len(members),
                         "member_ids": [m["id"] for m in members]})
    return clusters


# ── diagnostics → task inputs ────────────────────────────────────────────────

def build_failure_evidence(row: Dict[str, Any], cluster_size: int) -> str:
    """The reproducible signal for the Notion task's Failure Evidence + the fix validation loop."""
    ctx = row.get("client_context") or {}
    lines: List[str] = [f"Reported {cluster_size}× (deduped). Route: {ctx.get('route') or row.get('page_url') or '?'}."]
    for err in (ctx.get("recentErrors") or [])[:3]:
        lines.append(f"Failing function: {err.get('failingFrame') or '?'} | {err.get('message') or ''} "
                     f"(fingerprint {err.get('fingerprint') or '?'})")
    for fr in (ctx.get("recentFailedRequests") or [])[:_FAILED_REQUEST_LIMIT]:
        lines.append(f"Failed request: {fr.get('method')} {fr.get('path')} → {fr.get('status')} "
                     f"· req {fr.get('requestId')}")
    if ctx.get("appVersion"):
        lines.append(f"Build: {ctx.get('appVersion')}")
    return "\n".join(lines)


def _est_tokens(*parts: str) -> int:
    return max(1, sum(len(p or "") for p in parts) // 4)


# ── dispatch one representative ──────────────────────────────────────────────

def _dispatch_one(session: Any, rep: Dict[str, Any], size: int, *, dry_run: bool) -> Dict[str, Any]:
    cls = classify(rep.get("message") or "", rep.get("category") or "bug")
    failure_evidence = build_failure_evidence(rep, size)
    admin_context = (
        f"[Autopilot] {size} similar report(s) clustered by error fingerprint.\n{failure_evidence}"
    )
    context_links = f"https://relopass.com/admin/feedback (feedback_id={rep['id']}, cluster={dedup_key(rep)})"

    if dry_run:
        return {"feedback_id": rep["id"], "dry_run": True, "cluster_size": size,
                "severity": cls.get("severity"), "area": cls.get("area")}

    # Cost-trace the one billable call so the governor's budget meter sees it.
    tracer = TraceSession(session_id=rep["id"], query=(rep.get("message") or ""),
                          company_id="autopilot", feature_key=stage_feature_key("dispatch"))
    t0 = time.time()
    try:
        task = engineer_task(
            text=rep.get("message"), category=rep.get("category") or "bug",
            page_url=rep.get("page_url"), severity=cls.get("severity"), area=cls.get("area"),
            has_screenshot=False, reporter_name=rep.get("reporter_name"), admin_context=admin_context,
            diagnostics=format_diagnostics(rep.get("client_context")),
        )
    finally:
        tracer.record_llm_call(
            model=_DISPATCH_MODEL,
            input_tokens=_est_tokens(admin_context, rep.get("message") or ""),
            output_tokens=2000,   # engineer_task caps output at max_tokens=2000
            latency_ms=int((time.time() - t0) * 1000),
        )
        tracer.flush()

    # ── Eval gate (AIQ-1567) ──────────────────────────────────────────────────
    # The manual path (admin_feedback.dispatch/create) has always scored the task before
    # writing to Notion and 422s the admin when it fails. This path never did — so the
    # nightly run (up to AUTOPILOT_MAX_DISPATCH_PER_NIGHT tasks) wrote unscored specs
    # straight into the queue, with nobody in the loop to notice. That is the lane most
    # in need of the gate, not least.
    #
    # There is no admin to 422 here, so a failing task is skipped rather than dispatched,
    # and the reason is returned for the run log. Skipping is the safe default: the
    # feedback row keeps its status and the next run can retry it. Dispatching a spec we
    # know is unsound would put a false premise in front of an executor at 03:00.
    signals = extract_confirmed_signals(rep.get("client_context"))
    eval_result = score_task(task, confirmed_signals=signals, user_text=rep.get("message") or "")
    if not eval_result["passed"]:
        log.warning(
            "autopilot dispatch skipped (feedback_id=%s): task failed the eval gate "
            "(score=%s) — %s",
            rep["id"], eval_result["score"], "; ".join(eval_result["issues"]) or "no issues listed",
        )
        return {
            "feedback_id": rep["id"],
            "dispatched": False,
            "skipped_reason": "eval_gate_failed",
            "eval": eval_result,
            "cluster_size": size,
        }

    url = nwq.create_work_queue_task(task, failure_evidence=failure_evidence, context_links=context_links)
    now = datetime.utcnow().isoformat()
    page_id = nwq.page_id_from_ref(url) or ""
    notion_task_id = re.sub(r"[^0-9a-f]", "", page_id.lower())  # dashless-lower 32hex join key
    tier = task.get("autonomy_tier") or None
    session.execute(
        text(
            "INSERT INTO feedback_status "
            "(stream, source_id, status, dispatch_ref, dispatch_status, dispatched_at, notion_task_id, autonomy_tier, updated_at) "
            "VALUES ('product', :id, 'new', :ref, 'dispatched', :now, :ntid, :tier, :now) "
            "ON CONFLICT (stream, source_id) DO UPDATE SET "
            "  dispatch_ref = excluded.dispatch_ref, dispatch_status = 'dispatched', "
            "  dispatched_at = :now, notion_task_id = excluded.notion_task_id, "
            "  autonomy_tier = excluded.autonomy_tier, updated_at = :now"
        ),
        {"id": rep["id"], "ref": url, "now": now, "ntid": notion_task_id, "tier": tier},
    )
    ev.emit(ev.TASK_DISPATCHED, entity_id=rep["id"],
            properties={"cluster_size": size, "complexity": task.get("complexity"),
                        "layer": task.get("layer"), "status": status_from_complexity(task.get("complexity")),
                        "notion_url": url})
    return {"feedback_id": rep["id"], "notion_url": url, "cluster_size": size,
            "complexity": task.get("complexity")}


# ── orchestrator ─────────────────────────────────────────────────────────────

def run_ingest(*, dry_run: bool = False, lookback_hours: int = 24, session: Any = None) -> Dict[str, Any]:
    """Nightly ingest+dedup+dispatch. Governor-gated, per-night capped. Never raises on a single
    item — one bad dispatch is logged and skipped so the run completes."""
    decision = gate("dispatch", session=session)
    if not decision.allowed:
        ev.emit(ev.RUN_HALTED, properties={"stage": "dispatch", "reason": decision.reason})
        return {"halted": True, "reason": decision.reason, "dispatched": 0}

    own = session is None
    s = session or SessionLocal()
    ev.emit(ev.RUN_STARTED, properties={"dry_run": dry_run, "lookback_hours": lookback_hours})
    try:
        rows = _query_candidates(s, lookback_hours)
        ev.emit(ev.FEEDBACK_INGESTED, properties={"count": len(rows)})
        clusters = cluster(rows)
        ev.emit(ev.FEEDBACK_DEDUPED, properties={"raw": len(rows), "unique": len(clusters)})

        cap = nightly_cap("dispatch")
        # Largest clusters first (most-reported bugs get fixed first), then dispatch up to the cap.
        clusters.sort(key=lambda c: c["size"], reverse=True)
        results: List[Dict[str, Any]] = []
        for c in clusters[:cap]:
            try:
                results.append(_dispatch_one(s, c["representative"], c["size"], dry_run=dry_run))
            except Exception as exc:  # noqa: BLE001 — never let one item abort the nightly run
                log.warning("autopilot ingest: dispatch failed for cluster %s: %s", c["key"], exc)
                results.append({"feedback_id": c["representative"]["id"], "error": str(exc)})
        if own and not dry_run:
            s.commit()
        return {
            "halted": False, "dry_run": dry_run,
            "raw": len(rows), "unique_clusters": len(clusters), "cap": cap,
            "dispatched": sum(1 for r in results if r.get("notion_url")),
            "planned": sum(1 for r in results if r.get("dry_run")),
            "errors": sum(1 for r in results if r.get("error")),
            "results": results,
            "budget_remaining_usd": round(decision.remaining_usd, 4),
        }
    finally:
        if own:
            s.close()
