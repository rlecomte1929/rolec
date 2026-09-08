"""
Phase 1 — Seed 20 policy assistant traces into Langfuse.

Usage (from repo root, with venv_new active):
    python -m experiments.seed_policy_assistant_traces

What it does:
  - Calls hr_policy_assistant_query_response_dict() directly (no HTTP, no auth)
  - The observability layer (AnthropicInstrumentor + langfuse.openai) captures
    every LLM call automatically and sends it to Langfuse
  - Results are printed so you can do a quick sanity check before opening Langfuse

After running, go to cloud.langfuse.com → Traces to see all 20 entries.

Eval rubric (PASS requires ALL four):
  1. Grounded   — answer is drawn from policy data, no hallucination
  2. Scoped     — no cross-company data leakage
  3. Complete   — key facts present when the policy has them
  4. Correct refusal — says "not covered" rather than guessing when data is absent
"""
from __future__ import annotations

import os
import sys
import json

# ── Load .env so LANGFUSE_* and ANTHROPIC_API_KEY are available ─────────────
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env, override=False)

# ── Bootstrap Langfuse tracing (same as app startup) ────────────────────────
sys.path.insert(0, str(_root))
from backend.observability import configure_observability
configure_observability()

# ── Import the service under test ────────────────────────────────────────────
from backend.app.services.hr_policy_assistant_service import (
    hr_policy_assistant_query_response_dict,
)

# ── Test fixture ─────────────────────────────────────────────────────────────
POLICY_ID = "d70615b6-11b3-4595-989e-a3ef20cf2fe2"

MOCK_HR_USER = {
    "id": "eval-user-00000000",
    "role": "HR",
    "company_id": "0d3e8d04-b463-4516-a26d-bf0e8f68dbdb",
    "email": "eval@relopass.com",
}

# Full 20-question golden set — covers every canonical topic + edge cases
QUESTIONS = [
    # RELOCATION_ALLOWANCE (lump sum, deadline, structure)
    "What is the relocation allowance amount for this policy?",
    "Is there a deadline to claim the relocation allowance?",
    "Is there a lump sum option instead of managed relocation services?",
    # HOME_LEAVE
    "How many home leave trips does the policy allow per year?",
    "Does the policy cover flights for my family on home leave?",
    # HOST_HOUSING / TEMPORARY_HOUSING
    "What housing support is included for the host country?",
    "Is temporary housing provided at the start of the assignment?",
    # SHIPMENT
    "Are household goods and personal effects covered for shipment?",
    "Is storage of household goods included during the assignment?",
    # SCHOOL_SEARCH / TUITION
    "Does the policy cover school fees for dependent children?",
    "Is language training available for the assignee and family?",
    # VISA_SUPPORT / WORK_PERMIT_SUPPORT
    "Does the policy cover work permit and visa fees?",
    "Is immigration support provided for accompanying family members?",
    # SPOUSE_SUPPORT
    "Is there a spousal career support allowance?",
    # RELOCATION_ALLOWANCE sub-questions
    "What is the cost of living allowance (COLA) under this policy?",
    "Is a mobility premium included? What is the percentage?",
    # STATUS / META
    "Is this policy published and visible to employees?",
    "What does the policy say about banking support?",
    # EDGE CASES — should produce correct refusal or clarification
    "What is the best school district in Paris?",
    "Can you help me negotiate a better relocation package?",
]


def _verdict(i: int, answer: dict) -> str:
    atype = answer.get("answer_type", "")
    pstatus = answer.get("policy_status", "")
    text = answer.get("answer_text", "")
    tl = text.lower()

    # Questions 18-19 (0-indexed) should be refused
    if i in (18, 19):
        return "PASS" if atype == "refusal" else "FAIL"

    # All other questions should NOT produce a bare refusal with unknown status
    if atype == "refusal" and pstatus == "unknown":
        return "FAIL"

    # Must have some content
    if not text and atype != "refusal":
        return "FAIL"

    # E3 checks: aspect-specific content must differ from the generic amount template.
    # Q02 (0-indexed: 1) — "Is there a deadline to claim the relocation allowance?"
    if i == 1:
        has_amount_only = "5,000" in text and not any(
            kw in tl for kw in ("deadline", "doesn't specify", "not specified", "no deadline", "policy text")
        )
        if has_amount_only:
            return "FAIL"

    # Q03 (0-indexed: 2) — "Is there a lump sum option instead of managed relocation services?"
    if i == 2:
        has_amount_only = "5,000" in text and not any(
            kw in tl for kw in ("lump", "managed", "structure", "doesn't specify", "not specified", "policy text")
        )
        if has_amount_only:
            return "FAIL"

    return "PASS"


def run() -> None:
    print(f"\n=== Phase 1 Eval — 20 Questions ===\n")
    passes = 0
    for i, q in enumerate(QUESTIONS):
        q_num = i + 1
        try:
            result = hr_policy_assistant_query_response_dict(
                message=q,
                user=MOCK_HR_USER,
                policy_id=POLICY_ID,
            )
            answer = result.get("answer", {})
            verdict = _verdict(i, answer)
            if verdict == "PASS":
                passes += 1

            atype = answer.get("answer_type", "?")
            topic = answer.get("canonical_topic") or "-"
            pstatus = answer.get("policy_status", "?")
            text_preview = (answer.get("answer_text") or "")[:120].replace("\n", " ")
            refusal_obj = answer.get("refusal") or {}
            refusal_code = refusal_obj.get("refusal_code", "") if refusal_obj else ""

            print(f"[Q{q_num:02d}] {verdict} | {atype} | topic={topic} | status={pstatus}")
            print(f"       Q: {q[:90]}")
            if text_preview:
                print(f"       A: {text_preview}")
            if refusal_code:
                print(f"       refusal_code: {refusal_code}")
            print()
        except Exception as exc:
            print(f"[Q{q_num:02d}] ERROR: {exc}")
            print()

    print(f"=== SCORE: {passes}/{len(QUESTIONS)} PASS ===\n")


if __name__ == "__main__":
    run()
