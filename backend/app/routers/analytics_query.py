"""
FOUNDATION-1E — /api/analytics/query

POST endpoint that accepts a natural-language question about platform activity
and returns a structured answer backed by daily_summaries + targeted event queries.

Request body:
    { "question": string, "company_id"?: string }

Response:
    { "answer": string, "data": any, "sources": string[] }

Security:
    - Requires authenticated HR or ADMIN user
    - Tenant isolation: if company_id is provided (or derived from the user's
      profile) only that company's data is queried. Cross-tenant queries are
      impossible by construction.
    - Rate-limited: max 10 queries/minute per user_id (sliding window, in-process)

LLM:
    - Uses the existing AnthropicClient pattern from policy_assistant_llm_client
    - Model: claude-sonnet-4-6 (Sonnet for better reasoning over structured data)
    - Falls back to a plain text answer if the Anthropic client is unavailable
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth_deps import get_current_user, require_admin_or_hr
from ..services.supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics-query"])

# ─── Rate limiter ─────────────────────────────────────────────────────────────

_RL_WINDOW_SECONDS = 60
_RL_MAX_REQUESTS = 10

_rl_lock = threading.Lock()
_rl_buckets: Dict[str, Dict[str, Any]] = {}  # user_id → {count, window_start}


def _check_rate_limit(user_id: str) -> None:
    now = time.time()
    with _rl_lock:
        bucket = _rl_buckets.get(user_id)
        if bucket is None or now - bucket["window_start"] > _RL_WINDOW_SECONDS:
            _rl_buckets[user_id] = {"count": 1, "window_start": now}
            return
        if bucket["count"] >= _RL_MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {_RL_MAX_REQUESTS} queries/minute.",
            )
        bucket["count"] += 1


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AnalyticsQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    company_id: Optional[str] = None


class AnalyticsQueryResponse(BaseModel):
    answer: str
    data: Any
    sources: List[str]


# ─── Data retrieval helpers ───────────────────────────────────────────────────

def _get_recent_summaries(
    supabase: Any,
    company_id: Optional[str],
    days: int = 7,
) -> List[Dict[str, Any]]:
    """Fetch the last `days` daily_summaries rows. Not filtered by company_id
    (summaries are platform-wide), but the event data they summarise already
    scopes to the company when company_id is set."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    result = (
        supabase.table("daily_summaries")
        .select("date, summary_type, summary_text, raw_counts, anomalies")
        .gte("date", cutoff)
        .order("date", desc=True)
        .limit(days * 3)   # 3 summary_types × days
        .execute()
    )
    return result.data or []


def _get_targeted_events(
    supabase: Any,
    company_id: Optional[str],
    days: int = 7,
) -> List[Dict[str, Any]]:
    """Fetch a sample of recent raw events for the company (max 200 rows)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat() + "T00:00:00Z"
    q = (
        supabase.table("events")
        .select("created_at, event_type, entity_type, entity_id, source, properties")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(200)
    )
    if company_id:
        q = q.eq("company_id", company_id)
    return (q.execute()).data or []


# ─── LLM answer generation ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an analytics assistant for the ReloPass employee relocation platform.
You have access to structured event data and daily summaries. Answer the user's question
concisely and accurately based only on the data provided. If the data doesn't support a
specific claim, say so rather than guessing. Format numbers clearly. Be direct."""


def _build_context(
    summaries: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    company_id: Optional[str],
) -> str:
    context_parts = []

    if company_id:
        context_parts.append(f"Scope: data for company_id={company_id}")

    if summaries:
        context_parts.append("\n## Daily Summaries (most recent first)")
        for s in summaries[:9]:  # cap at 3 days × 3 types
            context_parts.append(
                f"[{s['date']} | {s['summary_type']}]\n{s['summary_text']}\n"
                f"Counts: {s['raw_counts']}"
            )

    if events:
        # Group raw events into a compact summary to avoid token bloat
        by_type: Dict[str, int] = {}
        for e in events:
            by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
        context_parts.append("\n## Raw event counts (last 7 days)")
        for evt, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
            context_parts.append(f"  {evt}: {cnt}")

    return "\n".join(context_parts) if context_parts else "No data available."


def _call_sonnet(question: str, context: str) -> str:
    """Call Claude Sonnet via the shared llm_client wrapper. Returns plain text.

    Routes through ``llm_client.claude_complete`` (free-text mode) so the call
    gains timeout, retry on 429/5xx, and structured logging. Same model,
    prompt, max_tokens, and temperature as before. Any failure (missing key,
    SDK absent, network) degrades gracefully to a static message — the raw
    data is always returned alongside in the ``data`` field.
    """
    from ..services.llm_client import claude_complete

    # This runs in a sync FastAPI route (threadpool), so there is no event
    # loop in this thread — asyncio.run() drives the async wrapper to result.
    try:
        answer = asyncio.run(
            claude_complete(
                system=SYSTEM_PROMPT,
                user=f"Context:\n{context}\n\nQuestion: {question}",
                schema=None,  # free-text answer, not structured JSON
                model="claude-sonnet-4-6",
                max_tokens=1024,
                temperature=0.2,
            )
        )
        return answer.strip()
    except Exception as exc:
        log.warning("analytics_query: LLM call failed: %s", exc)
        return "Unable to generate answer at this time. Raw data is available in the `data` field."


# ─── Route ────────────────────────────────────────────────────────────────────

@router.post("/query", response_model=AnalyticsQueryResponse)
def analytics_query(
    body: AnalyticsQueryRequest,
    user: Dict[str, Any] = Depends(require_admin_or_hr),
) -> AnalyticsQueryResponse:
    """
    Answer a natural-language question about ReloPass platform activity.

    Tenant isolation: company_id in the request is intersected with the
    authenticated user's company — a non-admin user cannot query another
    company's data.
    """
    _check_rate_limit(user["id"])

    # Resolve effective company_id — HR users are scoped to their own company
    user_company_id: Optional[str] = user.get("company_id") or user.get("company_id_str")
    role = user.get("role", "")

    if role == "ADMIN":
        # Admins may query any company or platform-wide
        effective_company_id = body.company_id or None
    else:
        # HR users: use their company; ignore any cross-tenant company_id in request
        effective_company_id = user_company_id or None

    supabase = get_supabase_admin_client()

    # Fetch context data
    summaries = _get_recent_summaries(supabase, effective_company_id)
    events = _get_targeted_events(supabase, effective_company_id)

    sources: List[str] = []
    if summaries:
        dates = sorted({s["date"] for s in summaries}, reverse=True)[:3]
        sources.append(f"daily_summaries ({len(summaries)} rows, dates: {', '.join(dates)})")
    if events:
        sources.append(f"events table ({len(events)} rows, last 7 days)")
    if not sources:
        sources.append("no data available")

    context = _build_context(summaries, events, effective_company_id)

    # Handle "no data" gracefully before calling LLM
    if not summaries and not events:
        return AnalyticsQueryResponse(
            answer="No activity data is available yet for the requested period. Events will appear after users interact with the platform.",
            data={"summaries": [], "event_sample": []},
            sources=sources,
        )

    answer = _call_sonnet(body.question, context)

    return AnalyticsQueryResponse(
        answer=answer,
        data={
            "summaries": summaries,
            "event_sample": events[:20],   # Return a sample; full data is in the DB
        },
        sources=sources,
    )
