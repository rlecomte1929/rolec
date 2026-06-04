"""
support.py — SUPPORT-4A + SUPPORT-4B
──────────────────────────────────────────────────────────────────────────────
Endpoints that capture and triage support interactions.

  SUPPORT-4A ingestion:
    POST /api/webhooks/support-email  — Postmark inbound email webhook
    POST /api/support/ticket          — In-app Help button form
    PATCH /api/support/ticket/{id}    — Status update (called by triage)

  SUPPORT-4B triage:
    POST /api/support/triage          — Claude Sonnet AI triage agent
      Input : { ticket_id, content?, user_role?, company_id?, recent_events? }
      Output: { issue_category, root_cause_hypothesis, fix_difficulty,
                suggested_action, draft_reply }
      Also writes triage_result back to support_tickets row.

Supabase trigger fires /api/support/triage automatically on ticket insert via
the support-triage Edge Function (called by pg_net).

Postmark webhook secret: POSTMARK_WEBHOOK_SECRET env var.
──────────────────────────────────────────────────────────────────────────────
"""

import hashlib
import hmac
import json
import os
import re
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel, EmailStr

from ..services.supabase_client import get_supabase_admin_client
from ..services.events_tracker import track

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["support"])

POSTMARK_WEBHOOK_SECRET = os.getenv("POSTMARK_WEBHOOK_SECRET", "")
# SEC-MUT-DRAIN: shared secret for the internal support-automation endpoints
# (triage / auto-reply / status update), invoked by Supabase Edge Function
# triggers rather than end users. Enforced when configured.
SUPPORT_AUTOMATION_SECRET = os.getenv("SUPPORT_AUTOMATION_SECRET", "")

# ─── Quoted reply stripping ────────────────────────────────────────────────────

# Common markers that indicate the start of a quoted reply thread
_QUOTE_MARKERS = [
    # English
    re.compile(r"^-+\s*Original Message\s*-+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^On .+wrote:\s*$", re.MULTILINE),
    re.compile(r"^From:\s+.+\nSent:", re.MULTILINE),
    re.compile(r"^_{3,}", re.MULTILINE),
    # French
    re.compile(r"^De :\s+", re.MULTILINE),
    re.compile(r"^Le .+ a écrit\s*:", re.MULTILINE),
    # Quoted lines (>)
    re.compile(r"^>+\s", re.MULTILINE),
]


def strip_quoted_reply(text: str) -> str:
    """Return only the first (newest) message from an email thread."""
    if not text:
        return text

    # Find the earliest match of any quote marker
    earliest_pos = len(text)
    for pattern in _QUOTE_MARKERS:
        match = pattern.search(text)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    return text[:earliest_pos].strip()


# ─── Postmark webhook secret verification ─────────────────────────────────────

def verify_postmark_secret(secret: Optional[str] = Header(None, alias="X-Postmark-Inbound-Secret")) -> None:
    """Reject requests that don't include the correct webhook secret."""
    if not POSTMARK_WEBHOOK_SECRET:
        # Secret not configured — allow all (dev mode)
        return
    if secret != POSTMARK_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid Postmark webhook secret")


def verify_support_automation_secret(
    secret: Optional[str] = Header(None, alias="X-Support-Automation-Secret"),
) -> None:
    """Gate the internal support-automation endpoints (triage / auto-reply /
    status update). They are invoked by Supabase Edge Function triggers, not by
    end users, so they authenticate with a shared secret rather than a session
    token. Enforced only when SUPPORT_AUTOMATION_SECRET is configured (so the
    flow keeps working until the secret + trigger header are provisioned)."""
    if not SUPPORT_AUTOMATION_SECRET:
        return
    if secret != SUPPORT_AUTOMATION_SECRET:
        raise HTTPException(status_code=401, detail="Invalid support automation secret")


# ─── Postmark inbound email webhook ───────────────────────────────────────────

@router.post(
    "/webhooks/support-email",
    status_code=200,
    dependencies=[Depends(verify_postmark_secret)],
    summary="Postmark inbound email → support_tickets",
)
async def inbound_email_webhook(request: Request):
    """
    Receives inbound email from Postmark, strips quoted replies, and inserts
    a support_ticket row. Fires support_ticket.created event.

    Postmark inbound JSON shape (abbreviated):
      {
        "MessageID": "...",
        "FromFull": { "Email": "user@company.com", "Name": "Alice" },
        "Subject": "Help with...",
        "TextBody": "...",
        "HtmlBody": "<html>...",
        "StrippedTextReply": "...",  -- Postmark's own stripping (may be empty)
      }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract fields from Postmark payload
    message_id: str = payload.get("MessageID", "")
    from_full: dict = payload.get("FromFull", {})
    from_email: str = from_full.get("Email", "")
    from_name: str = from_full.get("Name", "")
    subject: str = payload.get("Subject", "")
    text_body: str = payload.get("TextBody", "") or ""
    html_body: str = payload.get("HtmlBody", "") or ""

    # Prefer Postmark's StrippedTextReply, fall back to our own stripping
    stripped = payload.get("StrippedTextReply", "").strip()
    raw_content = stripped if stripped else strip_quoted_reply(text_body)

    if not raw_content:
        raw_content = text_body[:5000]  # Fallback: take first 5000 chars

    supabase = get_supabase_admin_client()

    # Deduplicate via MessageID
    if message_id:
        existing = supabase.table("support_tickets") \
            .select("id") \
            .eq("postmark_message_id", message_id) \
            .maybe_single() \
            .execute()
        if existing.data:
            logger.info("support/inbound-email: duplicate message_id=%s — skipping", message_id)
            return {"ok": True, "duplicate": True}

    # Insert ticket
    row = {
        "source": "email",
        "subject": subject[:500] if subject else None,
        "raw_content": raw_content[:10000],
        "html_content": html_body[:20000] if html_body else None,
        "from_email": from_email,
        "from_name": from_name,
        "postmark_message_id": message_id or None,
        "status": "new",
        # company_id and user_id may be populated later by triage (SUPPORT-4B)
        # based on from_email → user lookup
    }

    result = supabase.table("support_tickets").insert(row).execute()
    ticket_id = result.data[0]["id"] if result.data else None

    # Fire support_ticket.created event
    if ticket_id:
        track(
            "support_ticket.created",
            entity_type="support_ticket",
            entity_id=ticket_id,
            properties={
                "source": "email",
                "from_email": from_email,
                "subject": subject[:200] if subject else "",
            },
        )

    logger.info("support/inbound-email: ticket_id=%s created (from=%s)", ticket_id, from_email)
    return {"ok": True, "ticket_id": ticket_id}


# ─── In-app Help button form ───────────────────────────────────────────────────

class InAppTicketRequest(BaseModel):
    content: str
    subject: Optional[str] = None
    # Populated from auth context by the frontend; backend validates
    user_id: Optional[str] = None
    company_id: Optional[str] = None


@router.post(
    "/support/ticket",
    status_code=201,
    summary="In-app Help form → support_tickets",
)
async def create_in_app_ticket(
    body: InAppTicketRequest,
    request: Request,
):
    """
    In-app Help button form. The frontend POSTs the form content + auth context.
    company_id is required for logged-in HR users; optional for employee portal.
    """
    raw_content = body.content.strip()
    if not raw_content:
        raise HTTPException(status_code=422, detail="content must not be empty")

    supabase = get_supabase_admin_client()

    row = {
        "source": "in-app",
        "subject": body.subject[:500] if body.subject else None,
        "raw_content": raw_content[:10000],
        "user_id": body.user_id,
        "company_id": body.company_id,
        "status": "new",
    }

    result = supabase.table("support_tickets").insert(row).execute()
    ticket_id = result.data[0]["id"] if result.data else None

    # Fire support_ticket.created event
    if ticket_id:
        track(
            "support_ticket.created",
            entity_type="support_ticket",
            entity_id=ticket_id,
            session_id=body.user_id or "anonymous",
            user_id=body.user_id,
            company_id=body.company_id,
            properties={
                "source": "in-app",
                "subject": body.subject or "",
            },
        )

    logger.info("support/in-app: ticket_id=%s created (user=%s)", ticket_id, body.user_id)
    return {"ok": True, "ticket_id": ticket_id}


# ─── Ticket status endpoint (for triage to update) ────────────────────────────

class TicketStatusUpdate(BaseModel):
    status: str
    triage_result: Optional[dict] = None
    resolution_notes: Optional[str] = None


@router.patch(
    "/support/ticket/{ticket_id}",
    status_code=200,
    dependencies=[Depends(verify_support_automation_secret)],
    summary="Update support ticket status (called by SUPPORT-4B triage)",
)
async def update_ticket_status(ticket_id: str, body: TicketStatusUpdate):
    """Internal endpoint used by the SUPPORT-4B triage Edge Function."""
    valid_statuses = {"new", "triaged", "resolved", "escalated", "crisis_escalated"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")

    supabase = get_supabase_admin_client()
    update = {"status": body.status}
    if body.triage_result:
        update["triage_result"] = body.triage_result
    if body.resolution_notes:
        update["resolution_notes"] = body.resolution_notes

    supabase.table("support_tickets").update(update).eq("id", ticket_id).execute()
    return {"ok": True, "ticket_id": ticket_id, "status": body.status}


# ─── SUPPORT-4B: AI triage agent ──────────────────────────────────────────────

# Minimal ReloPass domain summary used when BRAIN-3D Company Brain is unavailable
_RELOPASS_FALLBACK_CONTEXT = """
ReloPass is a B2B SaaS platform that automates employee relocation for HR teams.
Core features: relocation case management, supplier marketplace, employee wizard,
policy management, AI-driven supplier matching, document handling, and multi-country
compliance support. Users are HR managers, mobility admins, and relocating employees.
Pricing is subscription-based (invoiced to companies). The product is in early commercial
stage targeting mid-market and enterprise customers.
""".strip()

_TRIAGE_SYSTEM = """
You are the ReloPass support triage AI. Your job is to classify incoming support tickets
and route them correctly so the right team/tool handles each issue.

ReloPass context:
{domain_context}

Classification rules (apply strictly):
1. issue_category:
   - "bug"            — something is broken, an error occurred, data is wrong
   - "ux_confusion"   — user doesn't understand how to use a feature (product works but is confusing)
   - "policy_question"— question about HR/relocation policies or regulatory compliance
   - "billing"        — anything about payment, invoices, subscription, pricing, refunds
   - "feature_request"— user wants a capability that doesn't exist yet
   - "other"          — none of the above

2. fix_difficulty (for bugs only; for non-bugs estimate effort to resolve):
   - "trivial" — UI glitch, copy error, simple config change
   - "low"     — isolated bug, single file fix, clear root cause
   - "medium"  — multi-component issue, unclear root cause, needs investigation
   - "high"    — data corruption, security-adjacent, major feature broken

3. suggested_action:
   - "auto_fix"    — trivial/low bug that the autofix pipeline can attempt (coding fix)
   - "notion_task" — medium/high bug or feature request needing human dev attention
   - "ai_reply"    — ux_confusion, policy_question, or feature_request with a clear AI answer
   - "escalate"    — ALWAYS for billing; also for anything involving data loss, security, legal

   CRITICAL: billing issue_category MUST always map to suggested_action "escalate".

4. draft_reply: A concise, empathetic response in ReloPass brand voice (professional but warm,
   no jargon, first person plural "we"). Acknowledge the issue, state next steps. Max 120 words.

Return ONLY valid JSON matching this schema (no markdown fences):
{
  "issue_category": "<bug|ux_confusion|policy_question|billing|feature_request|other>",
  "root_cause_hypothesis": "<one clear sentence>",
  "fix_difficulty": "<trivial|low|medium|high>",
  "suggested_action": "<auto_fix|notion_task|ai_reply|escalate>",
  "draft_reply": "<plain text reply to send to the user>"
}
""".strip()

VALID_CATEGORIES = {"bug", "ux_confusion", "policy_question", "billing", "feature_request", "other"}
VALID_DIFFICULTIES = {"trivial", "low", "medium", "high"}
VALID_ACTIONS = {"auto_fix", "notion_task", "ai_reply", "escalate"}


class TriageRequest(BaseModel):
    ticket_id: str
    # If omitted the endpoint fetches content from the DB
    content: Optional[str] = None
    subject: Optional[str] = None
    user_role: Optional[str] = "unknown"
    company_id: Optional[str] = None
    recent_events: Optional[List[Dict[str, Any]]] = []


class TriageResult(BaseModel):
    issue_category: str
    root_cause_hypothesis: str
    fix_difficulty: str
    suggested_action: str
    draft_reply: str


def _fetch_company_brain_context() -> str:
    """
    Attempt to load Company Brain context from BRAIN-3D (Notion overview page).
    Falls back to the hardcoded ReloPass summary if unavailable.
    BRAIN-3D page ID sourced from NOTION_BRAIN_PAGE env var.
    """
    try:
        notion_token = os.getenv("NOTION_TOKEN", "")
        brain_page_id = os.getenv("NOTION_BRAIN_PAGE", "")
        if not notion_token or not brain_page_id:
            return _RELOPASS_FALLBACK_CONTEXT

        import urllib.request
        req = urllib.request.Request(
            f"https://api.notion.com/v1/blocks/{brain_page_id}/children?page_size=10",
            headers={
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
            },
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())

        texts: List[str] = []
        for block in data.get("results", [])[:5]:
            rt = (
                block.get("paragraph", {}).get("rich_text", [])
                or block.get("callout", {}).get("rich_text", [])
                or []
            )
            for chunk in rt:
                texts.append(chunk.get("plain_text", ""))
        combined = " ".join(texts).strip()
        return combined if len(combined) > 100 else _RELOPASS_FALLBACK_CONTEXT
    except Exception as exc:
        logger.debug("company-brain fetch skipped: %s", exc)
        return _RELOPASS_FALLBACK_CONTEXT


def _call_triage_model(content: str, subject: Optional[str], user_role: str,
                       company_id: Optional[str], recent_events: List[Dict],
                       domain_context: str) -> Dict[str, Any]:
    """Call Claude Sonnet and return the parsed triage result dict."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)

    user_message_parts = []
    if subject:
        user_message_parts.append(f"Subject: {subject}")
    user_message_parts.append(f"User role: {user_role or 'unknown'}")
    if company_id:
        user_message_parts.append(f"Company ID: {company_id}")
    if recent_events:
        events_summary = "; ".join(
            f"{e.get('event_type', '?')} at {e.get('created_at', '?')}"
            for e in recent_events[:5]
        )
        user_message_parts.append(f"Recent user events: {events_summary}")
    user_message_parts.append(f"\nTicket content:\n{content[:3000]}")

    system_prompt = _TRIAGE_SYSTEM.format(domain_context=domain_context)

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        system=system_prompt,
        messages=[{"role": "user", "content": "\n".join(user_message_parts)}],
        max_tokens=512,
        temperature=0.1,
    )

    raw = ""
    for block in (resp.content or []):
        if getattr(block, "type", "") == "text":
            raw += getattr(block, "text", "")
    raw = raw.strip()

    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    result = json.loads(raw)

    # Validate and enforce billing → escalate rule
    if result.get("issue_category") not in VALID_CATEGORIES:
        result["issue_category"] = "other"
    if result.get("fix_difficulty") not in VALID_DIFFICULTIES:
        result["fix_difficulty"] = "medium"
    if result.get("suggested_action") not in VALID_ACTIONS:
        result["suggested_action"] = "escalate"
    if result.get("issue_category") == "billing":
        result["suggested_action"] = "escalate"

    return result


@router.post(
    "/support/triage",
    status_code=200,
    response_model=TriageResult,
    dependencies=[Depends(verify_support_automation_secret)],
    summary="AI triage agent — classify and route a support ticket (SUPPORT-4B)",
)
async def triage_ticket(body: TriageRequest):
    """
    Classifies a support ticket using Claude Sonnet and writes the result back
    to support_tickets.triage_result. Called directly or by the Supabase trigger.
    """
    supabase = get_supabase_admin_client()

    # Load ticket from DB if content not supplied
    content = body.content
    subject = body.subject
    company_id = body.company_id
    if not content:
        ticket_row = (
            supabase.table("support_tickets")
            .select("raw_content, subject, company_id, status")
            .eq("id", body.ticket_id)
            .maybe_single()
            .execute()
        )
        if not ticket_row.data:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found")
        content = ticket_row.data.get("raw_content", "")
        subject = subject or ticket_row.data.get("subject")
        company_id = company_id or ticket_row.data.get("company_id")
        if ticket_row.data.get("status") not in ("new", "triaged"):
            logger.info("support/triage: ticket %s already at status=%s — skipping",
                        body.ticket_id, ticket_row.data.get("status"))

    if not content:
        raise HTTPException(status_code=422, detail="Ticket content is empty")

    # Load Company Brain context (BRAIN-3D, with fallback)
    domain_context = _fetch_company_brain_context()

    # Call triage model
    try:
        result = _call_triage_model(
            content=content,
            subject=subject,
            user_role=body.user_role or "unknown",
            company_id=company_id,
            recent_events=body.recent_events or [],
            domain_context=domain_context,
        )
    except json.JSONDecodeError as exc:
        logger.error("support/triage: JSON parse error: %s", exc)
        raise HTTPException(status_code=502, detail="Triage model returned invalid JSON")
    except Exception as exc:
        logger.error("support/triage: model call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Triage model error: {exc}")

    # Write triage_result back to support_tickets
    supabase.table("support_tickets").update({
        "triage_result": result,
        "status": "triaged",
    }).eq("id", body.ticket_id).execute()

    # Fire analytics event
    track(
        "support_ticket.triaged",
        entity_type="support_ticket",
        entity_id=body.ticket_id,
        company_id=company_id,
        properties={
            "issue_category": result.get("issue_category"),
            "suggested_action": result.get("suggested_action"),
            "fix_difficulty": result.get("fix_difficulty"),
        },
    )

    logger.info(
        "support/triage: ticket=%s category=%s action=%s difficulty=%s",
        body.ticket_id, result.get("issue_category"),
        result.get("suggested_action"), result.get("fix_difficulty"),
    )
    return TriageResult(**result)


# ─── SUPPORT-4D: auto-reply sender ────────────────────────────────────────────

POSTMARK_API_URL = "https://api.postmarkapp.com/email"
SUPPORT_FROM_EMAIL = os.getenv("SUPPORT_EMAIL_FROM", "support@relopass.com")

_BRAND_VOICE_JARGON = ["ping me", "syncing", "looping in", "circling back", "touch base"]

_TEMPLATE_SUBJECTS = {
    "bug_acknowledged":       "We've received your report — our team is on it",
    "policy_question":        "Re: Your relocation policy question",
    "feature_noted":          "Thanks for your suggestion — we've noted it",
    "billing_escalated":      "Your billing enquiry has been escalated",
    "general_acknowledgment": "We've received your message",
}

_TEMPLATE_CLOSINGS = {
    "bug_acknowledged":
        "We'll keep you updated as we make progress. You don't need to take any action.",
    "policy_question":
        "If you have any follow-up questions, simply reply to this email and we'll be happy to help.",
    "feature_noted":
        "We share all product suggestions with our team and take them seriously when planning new features.",
    "billing_escalated":
        "Our team will be in touch within one business day with a full response.",
    "general_acknowledgment":
        "We aim to respond to all enquiries within one business day.",
}


def _select_template_category(issue_category: str, suggested_action: str) -> str:
    if suggested_action == "escalate" or issue_category == "billing":
        return "billing_escalated"
    if issue_category == "feature_request":
        return "feature_noted"
    if issue_category == "policy_question":
        return "policy_question"
    if issue_category in ("bug", "ux_confusion"):
        return "bug_acknowledged"
    return "general_acknowledgment"


def _validate_brand_voice(text: str) -> tuple[bool, List[str], str]:
    """Returns (passed, issues, sanitised_text)."""
    issues = []
    sanitised = text.strip()

    # Unfilled placeholders
    if re.search(r"\{\{[^}]+\}\}", sanitised) or re.search(r"\[PLACEHOLDER\]", sanitised, re.IGNORECASE):
        issues.append("Contains unfilled placeholder text")
        sanitised = re.sub(r"\{\{[^}]+\}\}", "", sanitised)
        sanitised = re.sub(r"\[PLACEHOLDER\]", "", sanitised, flags=re.IGNORECASE).strip()

    # Jargon
    for jargon in _BRAND_VOICE_JARGON:
        if jargon.lower() in sanitised.lower():
            issues.append(f'Contains informal jargon: "{jargon}"')

    # First-person plural
    if len(sanitised) > 50 and not re.search(r"\bwe\b|\bour\b", sanitised, re.IGNORECASE):
        issues.append("Missing first-person plural voice (we/our)")

    # Length
    word_count = len(sanitised.split())
    if word_count < 15:
        issues.append(f"Reply too short ({word_count} words)")
    if word_count > 200:
        issues.append(f"Reply too long ({word_count} words)")

    return len(issues) == 0, issues, sanitised


def _build_email_body(category: str, greeting: str, context_note: str, body: str) -> str:
    closing = _TEMPLATE_CLOSINGS.get(category, _TEMPLATE_CLOSINGS["general_acknowledgment"])
    parts = [greeting]
    if context_note:
        parts.append(context_note)
    parts.extend([body, "", closing, "", "Best regards,", "The ReloPass Team", SUPPORT_FROM_EMAIL])
    return "\n".join(parts)


class ReplyRequest(BaseModel):
    ticket_id: str
    # Optional overrides — if not supplied, loaded from DB
    to_email: Optional[str] = None
    draft_reply: Optional[str] = None
    issue_category: Optional[str] = None
    suggested_action: Optional[str] = None
    original_subject: Optional[str] = None
    recipient_name: Optional[str] = None


@router.post(
    "/support/reply",
    status_code=200,
    dependencies=[Depends(verify_support_automation_secret)],
    summary="Send auto-reply to ticket submitter (SUPPORT-4D)",
)
async def send_auto_reply(body: ReplyRequest):
    """
    Selects the correct brand-voice template, personalises with the triage
    draft_reply, validates tone, sends via Postmark, and marks ticket 'replied'.
    Called by the support-router when suggested_action is 'ai_reply',
    or directly for any ticket that needs an outbound reply.
    """
    postmark_token = os.getenv("POSTMARK_SERVER_TOKEN", "")
    if not postmark_token:
        raise HTTPException(status_code=500, detail="POSTMARK_SERVER_TOKEN not configured")

    supabase = get_supabase_admin_client()

    # Load ticket from DB if fields not provided
    to_email = body.to_email
    draft_reply = body.draft_reply
    issue_category = body.issue_category or "other"
    suggested_action = body.suggested_action or "ai_reply"
    original_subject = body.original_subject
    recipient_name = body.recipient_name

    if not (to_email and draft_reply):
        ticket_row = (
            supabase.table("support_tickets")
            .select("from_email, from_name, subject, triage_result, source, status")
            .eq("id", body.ticket_id)
            .maybe_single()
            .execute()
        )
        if not ticket_row.data:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_id} not found")
        row = ticket_row.data
        to_email = to_email or row.get("from_email")
        recipient_name = recipient_name or row.get("from_name")
        original_subject = original_subject or row.get("subject")
        triage = row.get("triage_result") or {}
        draft_reply = draft_reply or triage.get("draft_reply", "")
        issue_category = issue_category or triage.get("issue_category", "other")
        suggested_action = suggested_action or triage.get("suggested_action", "ai_reply")

        if row.get("source") == "in-app" and not to_email:
            raise HTTPException(status_code=422, detail="In-app ticket has no email address to reply to")

    if not to_email:
        raise HTTPException(status_code=422, detail="No recipient email address available")
    if not draft_reply:
        raise HTTPException(status_code=422, detail="No draft reply content available")

    # Select template category
    category = _select_template_category(issue_category, suggested_action)

    # Validate brand voice
    passed, issues, sanitised_body = _validate_brand_voice(draft_reply)
    if issues:
        logger.warning("support/reply: brand voice issues for ticket=%s: %s", body.ticket_id, "; ".join(issues))

    # Build email
    greeting = f"Hi {recipient_name}," if (recipient_name and recipient_name != "[user]") else "Hello,"
    context_note = f"Re: {original_subject}" if original_subject else ""
    subject_line = (
        f"Re: {original_subject}" if original_subject
        else _TEMPLATE_SUBJECTS.get(category, "We've received your message")
    )
    text_body = _build_email_body(category, greeting, context_note, sanitised_body)

    # Send via Postmark
    import urllib.request as urlreq
    email_payload = json.dumps({
        "From": SUPPORT_FROM_EMAIL,
        "To": to_email,
        "ReplyTo": SUPPORT_FROM_EMAIL,
        "Subject": subject_line,
        "TextBody": text_body,
        "MessageStream": "outbound",
    }).encode("utf-8")

    req = urlreq.Request(
        POSTMARK_API_URL,
        data=email_payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": postmark_token,
        },
        method="POST",
    )
    try:
        with urlreq.urlopen(req, timeout=8) as resp:
            pm_result = json.loads(resp.read())
            postmark_message_id = pm_result.get("MessageID")
    except Exception as exc:
        logger.error("support/reply: Postmark send failed for ticket=%s: %s", body.ticket_id, exc)
        raise HTTPException(status_code=502, detail=f"Postmark send failed: {exc}")

    # Mark ticket as replied
    supabase.table("support_tickets").update({
        "status": "resolved",
        "resolution_notes": f"Auto-reply sent [{category}] via {SUPPORT_FROM_EMAIL}. Postmark ID: {postmark_message_id}",
    }).eq("id", body.ticket_id).execute()

    # Fire analytics event
    track(
        "support_ticket.replied",
        entity_type="support_ticket",
        entity_id=body.ticket_id,
        properties={
            "category": category,
            "brand_voice_passed": passed,
            "postmark_message_id": postmark_message_id,
        },
    )

    logger.info(
        "support/reply: ticket=%s replied category=%s to=%s postmark_id=%s",
        body.ticket_id, category, to_email, postmark_message_id,
    )
    return {
        "ok": True,
        "ticket_id": body.ticket_id,
        "category": category,
        "to": to_email,
        "subject": subject_line,
        "brand_voice_passed": passed,
        "brand_voice_issues": issues,
        "postmark_message_id": postmark_message_id,
    }
