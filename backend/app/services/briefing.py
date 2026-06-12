"""[FRIDAY-005 · AIQ-648] Employee relocation-briefing service.

A single Claude Sonnet 4.6 call ingests the full corporate mobility policy (1M-token
context, GA — no chunking, no RAG) and returns a personalised, citation-grounded
one-page briefing for one employee.

The ``SYSTEM_PROMPT`` and ``build_user_prompt`` below are the **source of truth** and
are kept byte-identical with the spike at ``outputs/friday_005_policy_ingestion_spike.py``.
If you change one, change both.

Sync (not async): the HR routers in this codebase are sync, and the policy-assistant's
existing ``AnthropicClient`` is sync; matching that avoids an ``asyncio.run`` round-trip
inside a threadpool-run handler.

NOTE on PII / data governance: unlike the policy-assistant (which masks PII before
egress), this endpoint intentionally sends the employee's real name + the full policy
to Anthropic — masking would defeat the personalisation. Employee PII + policy text
therefore cross the Anthropic API boundary (30-day retention). Flagged for review.
"""
from __future__ import annotations

import time
from typing import Any, Dict

# Sonnet 4.6: $3 / $15 per 1M tokens (input / output).
MODEL = "claude-sonnet-4-6"
PRICE_INPUT = 3.0 / 1_000_000
PRICE_OUTPUT = 15.0 / 1_000_000
MAX_TOKENS = 2000  # a one-page briefing is ~700-900 tokens; headroom for citations


class BriefingError(RuntimeError):
    """Raised when the Anthropic call fails — the route maps this to a 502."""


# ── Prompts (SOURCE OF TRUTH — keep byte-identical with the FRIDAY-005 spike) ──
SYSTEM_PROMPT = (
    "You are ReloPass's relocation policy briefing assistant. You write a short, "
    "personalised relocation briefing for one employee, grounded ENTIRELY in the "
    "corporate mobility policy document provided.\n\n"
    "Hard rules — follow every one:\n"
    "1. CITE EVERYTHING. Every factual claim (an allowance, a cap, an eligibility "
    "rule, a deadline, a benefit) MUST end with a citation to the exact policy "
    "location in the form [Policy §X.Y] (use the section/clause numbering that "
    "appears in the document; if a clause has no number, cite its heading, e.g. "
    "[Policy — \"Temporary Accommodation\"]).\n"
    "2. NEVER invent. If the policy does not address something relevant to this "
    "employee, say so explicitly: \"The policy does not specify ...\" — do NOT "
    "guess, infer a market norm, or fill the gap from general knowledge.\n"
    "3. PERSONALISE to THIS employee using the details provided (grade, assignment "
    "type, route, dependants, dates). Surface only the policy provisions that apply "
    "to them; skip provisions for other grades/assignment types.\n"
    "4. ONE PAGE. Be concise and skimmable. Use short sections with headings. No "
    "preamble, no sign-off, no \"as an AI\" language.\n"
    "5. Plain, warm, professional tone — you are speaking to the employee directly."
)


def build_user_prompt(policy_text: str, employee: Dict[str, Any]) -> str:
    """Assemble the user turn: full policy document + this employee's details.

    ``employee`` keys: name, grade, assignment_type, home_country, destination,
    departure_date, dependants. Missing values are rendered "not provided" so the
    model treats them as gaps rather than inventing.
    """
    def field(key: str) -> str:
        val = employee.get(key)
        return str(val) if val not in (None, "", []) else "not provided"

    details = (
        f"- Name: {field('name')}\n"
        f"- Grade / band: {field('grade')}\n"
        f"- Assignment type: {field('assignment_type')}\n"
        f"- Home country: {field('home_country')}\n"
        f"- Destination: {field('destination')}\n"
        f"- Departure date: {field('departure_date')}\n"
        f"- Dependants: {field('dependants')}"
    )
    return (
        "Here is the full corporate mobility policy document. Read all of it.\n\n"
        "<policy_document>\n"
        f"{policy_text}\n"
        "</policy_document>\n\n"
        "Here are the details of the employee to brief:\n\n"
        f"<employee>\n{details}\n</employee>\n\n"
        "Write the one-page, citation-grounded relocation briefing for this "
        "employee now, following every rule in your instructions. Every factual "
        "claim must carry a [Policy §X.Y] citation traceable to the document above."
    )


def _cost_usd(usage: Any) -> float:
    return round(usage.input_tokens * PRICE_INPUT + usage.output_tokens * PRICE_OUTPUT, 4)


def generate_employee_briefing(policy_text: str, employee: Dict[str, Any]) -> Dict[str, Any]:
    """One Sonnet 4.6 call → ``{briefing, cost_usd, latency_ms, model}``.

    Raises ``BriefingError`` on any Anthropic SDK/API failure (the route maps it to
    a 502 without leaking a stack trace).
    """
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise BriefingError("anthropic SDK not installed") from exc

    t0 = time.perf_counter()
    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env (raises if unset)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0.2,  # low temperature for citation fidelity
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(policy_text, employee)}],
        )
    except Exception as exc:  # APIError, AuthenticationError, RateLimitError, etc.
        raise BriefingError(str(exc)) from exc

    latency_ms = int((time.perf_counter() - t0) * 1000)
    briefing = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return {
        "briefing": briefing,
        "cost_usd": _cost_usd(resp.usage),
        "latency_ms": latency_ms,
        "model": MODEL,
    }
