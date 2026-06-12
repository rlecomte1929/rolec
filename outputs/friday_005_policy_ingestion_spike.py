"""FRIDAY-005 · 1M-context policy ingestion spike (Claude Sonnet 4.6)  [AIQ-648]

Reconstructed 2026-06-11. The original Cowork "spike" (per AIQ-648 execution
notes) was never committed and never run live ("No API key in Cowork sandbox").
This is the real, runnable artifact: it ingests a full corporate mobility policy
via Claude Sonnet 4.6 (1M-token context, GA) and generates a personalised,
citation-grounded one-page briefing for a single employee — with measured
latency, token cost, and an optional hallucination spot-check.

The SYSTEM_PROMPT and build_user_prompt() below are the *source of truth* that
the production endpoint (backend/app/services/briefing.py) reuses verbatim.

Run it:
    export ANTHROPIC_API_KEY=sk-ant-...
    python outputs/friday_005_policy_ingestion_spike.py path/to/policy.pdf

Validation targets (AIQ-648): latency < 60s for an 80K-token policy,
cost < $2 per briefing, and 5/5 cited facts traceable to the source.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any, Dict, Optional

# Sonnet 4.6: 1M context (GA), $3 / $15 per 1M tokens (input / output).
MODEL = "claude-sonnet-4-6"
PRICE_INPUT = 3.0 / 1_000_000   # USD per input token
PRICE_OUTPUT = 15.0 / 1_000_000  # USD per output token
MAX_TOKENS = 2000                # a one-page briefing is ~700-900 tokens; headroom for citations

# ── Prompts (SOURCE OF TRUTH — kept byte-identical in backend/app/services/briefing.py) ──
#
# Design (from AIQ-648): citation-first, graceful uncertainty, one-page constraint.
# These three are the hallucination guards — every factual claim must carry a
# [Policy §X.Y] citation traceable to the source text, the model must say "the
# policy does not specify" rather than invent, and the output is bounded to one
# page so it stays skimmable for the employee.

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

    `employee` keys: name, grade, assignment_type, home_country, destination,
    departure_date, dependants. Missing values are passed through as "not provided"
    so the model treats them as gaps rather than inventing.
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


SPOT_CHECK_SYSTEM = (
    "You are a strict fact-checker. You are given a corporate mobility policy and a "
    "briefing generated from it. For each [Policy §X.Y] citation in the briefing, "
    "verify that the cited claim is actually supported by the policy text. Respond "
    "with JSON: {\"checked\": int, \"verified\": int, \"failures\": [\"...\"]}. A failure "
    "is any claim whose citation does not match the source or that the policy does "
    "not actually state."
)


def _cost_usd(usage: Any) -> float:
    return round(usage.input_tokens * PRICE_INPUT + usage.output_tokens * PRICE_OUTPUT, 4)


async def generate_employee_briefing(policy_text: str, employee: Dict[str, Any]) -> Dict[str, Any]:
    """Single Sonnet 4.6 call → personalised, cited briefing. Returns the same
    shape the production service returns: {briefing, cost_usd, latency_ms, model}."""
    from anthropic import AsyncAnthropic  # imported lazily so the file imports without the SDK

    client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    t0 = time.perf_counter()
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.2,  # low temp for citation fidelity
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(policy_text, employee)}],
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    briefing = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "briefing": briefing,
        "cost_usd": _cost_usd(resp.usage),
        "latency_ms": latency_ms,
        "model": MODEL,
    }


async def spot_check(policy_text: str, briefing: str) -> Dict[str, Any]:
    """Second verification call (spike-only — the endpoint deliberately skips this).
    Returns {checked, verified, failures}."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=1000,
        temperature=0.0,
        system=SPOT_CHECK_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"<policy_document>\n{policy_text}\n</policy_document>\n\n"
                f"<briefing>\n{briefing}\n</briefing>\n\nVerify every citation. Respond with JSON only."
            ),
        }],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except Exception:
        return {"checked": None, "verified": None, "failures": ["could not parse verifier JSON", text[:200]]}


def _pdf_to_text(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


# Sample employee for a manual run (Manager LTA Berlin — matches the AIQ-648 spot-check persona).
SAMPLE_EMPLOYEE = {
    "name": "Priya Sharma",
    "grade": "Manager",
    "assignment_type": "Long-term assignment (LTA)",
    "home_country": "United Kingdom",
    "destination": "Germany (Berlin)",
    "departure_date": "2026-09-01",
    "dependants": "Spouse + 1 child",
}


async def _main(pdf_path: str) -> None:
    policy_text = _pdf_to_text(pdf_path)
    print(f"Policy: {len(policy_text):,} chars (~{len(policy_text)//4:,} tokens) from {pdf_path}\n")
    result = await generate_employee_briefing(policy_text, SAMPLE_EMPLOYEE)
    print(result["briefing"])
    print("\n" + "=" * 60)
    print(f"model={result['model']}  latency={result['latency_ms']}ms  cost=${result['cost_usd']}")
    check = await spot_check(policy_text, result["briefing"])
    print(f"spot-check: {check}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python friday_005_policy_ingestion_spike.py path/to/policy.pdf", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_main(sys.argv[1]))
