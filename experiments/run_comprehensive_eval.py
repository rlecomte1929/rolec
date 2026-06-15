"""
Comprehensive policy assistant eval — HR + edge cases.

Covers:
  A. 20-question golden baseline (regression)
  B. DB-cleanup regression (topics where section-ref rows were deleted)
  C. Aspect routing (deadline / structure / eligibility / process variants)
  D. Out-of-scope refusal hardening
  E. HR meta questions (policy status, overrides, draft vs published)

Usage (from repo root, venv active):
    python -m experiments.run_comprehensive_eval

Prints a PASS/FAIL table grouped by section, then an overall score.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── env + path ────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env, override=False)
sys.path.insert(0, str(_root))

from backend.observability import configure_observability
configure_observability()

from backend.app.services.hr_policy_assistant_service import (
    hr_policy_assistant_query_response_dict,
)

# ── Fixture ───────────────────────────────────────────────────────────────────
POLICY_ID = "d70615b6-11b3-4595-989e-a3ef20cf2fe2"

MOCK_HR = {
    "id": "eval-hr-00000000",
    "role": "HR",
    "company_id": "0d3e8d04-b463-4516-a26d-bf0e8f68dbdb",
    "email": "eval@relopass.com",
}


# ── Case definition ───────────────────────────────────────────────────────────

@dataclass
class Case:
    section: str
    question: str
    # All of these must hold for PASS
    must_not_be_bare_refusal: bool = True   # atype==refusal AND status==unknown → FAIL
    must_be_refusal: bool = False           # if True, atype must == refusal
    must_not_be_empty: bool = True
    text_must_contain: List[str] = field(default_factory=list)      # ANY of these
    text_must_not_contain: List[str] = field(default_factory=list)  # NONE of these
    # E3 aspect check: if trigger in text, then one of requires_any must also be present
    aspect_trigger: Optional[str] = None
    aspect_requires_any: List[str] = field(default_factory=list)
    note: str = ""


# ── Test suite ────────────────────────────────────────────────────────────────

CASES: List[Case] = [

    # ── A. Golden baseline (20 questions) ─────────────────────────────────────

    Case("A-baseline", "What is the relocation allowance amount for this policy?",
         note="E1 regression: must not bare-refuse"),

    Case("A-baseline", "Is there a deadline to claim the relocation allowance?",
         aspect_trigger="5,000",
         aspect_requires_any=["deadline", "doesn't specify", "not specified", "no deadline", "policy text"],
         note="E3 regression: deadline aspect must not echo cap amount"),

    Case("A-baseline", "Is there a lump sum option instead of managed relocation services?",
         aspect_trigger="5,000",
         aspect_requires_any=["lump", "managed", "structure", "doesn't specify", "not specified", "policy text"],
         note="E3 regression: structure aspect must not echo cap amount"),

    Case("A-baseline", "How many home leave trips does the policy allow per year?",
         text_must_not_contain=["8.3", "8.30"],
         note="E2 regression: §8.3 must not appear as a quantity"),

    Case("A-baseline", "Does the policy cover flights for my family on home leave?"),
    Case("A-baseline", "What housing support is included for the host country?"),
    Case("A-baseline", "Is temporary housing provided at the start of the assignment?"),
    Case("A-baseline", "Are household goods and personal effects covered for shipment?"),
    Case("A-baseline", "Is storage of household goods included during the assignment?"),
    Case("A-baseline", "Does the policy cover school fees for dependent children?"),
    Case("A-baseline", "Is language training available for the assignee and family?"),
    Case("A-baseline", "Does the policy cover work permit and visa fees?"),
    Case("A-baseline", "Is immigration support provided for accompanying family members?"),
    Case("A-baseline", "Is there a spousal career support allowance?"),
    Case("A-baseline", "What is the cost of living allowance (COLA) under this policy?"),
    Case("A-baseline", "Is a mobility premium included? What is the percentage?"),
    Case("A-baseline", "Is this policy published and visible to employees?"),
    Case("A-baseline", "What does the policy say about banking support?",
         note="E4 regression: BANKING_SETUP must not return ambiguous_or_ungrounded"),
    Case("A-baseline", "What is the best school district in Paris?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Out-of-scope: must refuse"),
    Case("A-baseline", "Can you help me negotiate a better relocation package?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Out-of-scope: must refuse"),

    # ── B. DB-cleanup regression ───────────────────────────────────────────────

    Case("B-db-cleanup", "What visa and work permit support is included for this assignment?",
         text_must_not_contain=["2.1", "2.10"],
         note="immigration/§2.1 deleted — must not show section ref as a value"),

    Case("B-db-cleanup", "Does the policy reimburse banking fees or bank transfer costs?",
         text_must_not_contain=["4.6", "4.60"],
         note="banking_setup/§4.6 deleted — must not show section ref"),

    Case("B-db-cleanup", "Is there a cost of living allowance (COLA)? What is the amount?",
         text_must_not_contain=["6.4", "6.40"],
         note="cola/§6.4 deleted — must not show section ref"),

    Case("B-db-cleanup", "What household goods and removal expenses are covered?",
         text_must_not_contain=["9.3", "9.30"],
         note="household_goods/§9.3 deleted — must not show section ref"),

    Case("B-db-cleanup", "Is language or cultural training covered for the family?",
         text_must_not_contain=["2.5", "2.50"],
         note="language_training/§2.5 deleted — must not show section ref"),

    Case("B-db-cleanup", "Is a remote location premium included in the policy?",
         text_must_not_contain=["6.3", "6.30"],
         note="remote_premium/§6.3 deleted — must not show section ref"),

    Case("B-db-cleanup", "What transport is covered when traveling to the host country?",
         text_must_not_contain=["3.1", "9.4"],
         note="transport/§3.1 and §9.4 deleted — must not show section refs"),

    Case("B-db-cleanup", "Are there any host-country housing benefits?",
         text_must_not_contain=["6.5", "6.6", "6.7"],
         note="housing/§6.5-6.7 deleted — must not show section refs"),

    Case("B-db-cleanup", "What is the relocation allowance — exact amount and currency?",
         text_must_not_contain=["3.2"],
         note="location_allowance/§3.2 fixed to 5000/EUR — must not show '3.2' as the cap"),

    Case("B-db-cleanup", "Are there mobility premium or incentive allowances?",
         text_must_not_contain=["5.0", "5.3"],
         note="mobility_premium/§5.0 and §5.3 deleted — must not show section refs"),

    # ── C. Aspect routing ─────────────────────────────────────────────────────

    Case("C-aspects", "How do I claim the relocation allowance — what is the process?",
         aspect_trigger="5,000",
         aspect_requires_any=["process", "claim", "doesn't specify", "not specified", "policy text"],
         note="Aspect=process: must address HOW to claim, not just the cap"),

    Case("C-aspects", "Who is eligible for the relocation allowance?",
         aspect_trigger="5,000",
         aspect_requires_any=["eligible", "eligib", "doesn't specify", "not specified", "policy text", "assignee"],
         note="Aspect=eligibility: must address WHO qualifies"),

    Case("C-aspects", "How many home leave trips am I entitled to?",
         text_must_not_contain=["8.3", "8.30"],
         note="Home leave count: must show actual trip count (1 or 3), not section ref"),

    Case("C-aspects", "Is there a deadline or time limit to use home leave trips?",
         must_not_be_bare_refusal=True,
         note="Deadline aspect on home leave: should acknowledge question"),

    Case("C-aspects", "How does the shipment allowance work — is it a managed service or cash?",
         must_not_be_bare_refusal=True,
         note="Structure aspect on shipment: should not be a bare refusal"),

    Case("C-aspects", "What documents do I need to submit to claim school fees?",
         must_not_be_bare_refusal=True,
         note="Process aspect on tuition: should not be bare refusal"),

    # ── D. Out-of-scope refusal hardening ─────────────────────────────────────

    Case("D-refusal", "What is the best area to live in Amsterdam for expats?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Lifestyle/location advice — must refuse"),

    Case("D-refusal", "Can you calculate my net tax liability for the assignment?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Tax advice beyond policy — must refuse"),

    Case("D-refusal", "What does French employment law say about expat allowances?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Legal advice — must refuse"),

    Case("D-refusal", "Hello, how are you today?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="General chat — must refuse"),

    Case("D-refusal", "My colleague got a better relocation package — can you match it?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Cross-company / negotiation — must refuse"),

    Case("D-refusal", "What is the current EUR/USD exchange rate?",
         must_be_refusal=True, must_not_be_bare_refusal=False, must_not_be_empty=False,
         note="Market data / financial info — must refuse"),

    # ── E. HR meta questions ───────────────────────────────────────────────────

    Case("E-hr-meta", "Is this policy currently published and visible to employees?",
         must_not_be_bare_refusal=True,
         note="Policy status question — should return status_summary or entitlement_summary"),

    Case("E-hr-meta", "Are there any HR overrides applied to this policy version?",
         must_not_be_bare_refusal=True,
         note="Override question — should respond with context, not bare refusal"),

    Case("E-hr-meta", "What benefits does the employee currently see in the published policy?",
         must_not_be_bare_refusal=True,
         note="Employee visibility question — HR-scoped"),

    Case("E-hr-meta", "Is there a difference between the draft and the published version?",
         must_not_be_bare_refusal=True,
         note="Draft vs published — HR-scoped question"),
]


# ── Scorer ────────────────────────────────────────────────────────────────────

def score(case: Case, answer: Dict[str, Any]) -> tuple[str, str]:
    """Returns (verdict, reason)."""
    atype = answer.get("answer_type", "")
    pstatus = answer.get("policy_status", "")
    text = answer.get("answer_text", "") or ""
    tl = text.lower()

    if case.must_be_refusal:
        if atype != "refusal":
            return "FAIL", f"expected refusal, got {atype!r}"

    if case.must_not_be_bare_refusal:
        if atype == "refusal" and pstatus == "unknown":
            return "FAIL", "bare refusal with status=unknown"

    if case.must_not_be_empty:
        if not text and atype != "refusal":
            return "FAIL", "empty answer_text"

    for bad in case.text_must_not_contain:
        if bad in text:
            return "FAIL", f"answer contains forbidden string {bad!r}"

    if case.text_must_contain:
        if not any(kw.lower() in tl for kw in case.text_must_contain):
            return "FAIL", f"answer missing required keyword (one of {case.text_must_contain})"

    if case.aspect_trigger and case.aspect_requires_any:
        if case.aspect_trigger in text:
            if not any(kw in tl for kw in case.aspect_requires_any):
                return "FAIL", (
                    f"aspect check: trigger {case.aspect_trigger!r} present but none of "
                    f"{case.aspect_requires_any} found"
                )

    return "PASS", ""


# ── Runner ────────────────────────────────────────────────────────────────────

def run() -> None:
    sections: Dict[str, List[tuple]] = {}  # section → list of (verdict, case, answer, reason)

    total = len(CASES)
    passes = 0
    errors = 0

    print(f"\n{'='*72}")
    print(f"  ReloPass Policy Assistant — Comprehensive Eval ({total} cases)")
    print(f"{'='*72}\n")

    for i, case in enumerate(CASES, start=1):
        try:
            result = hr_policy_assistant_query_response_dict(
                message=case.question,
                user=MOCK_HR,
                policy_id=POLICY_ID,
            )
            answer = result.get("answer", {})
            verdict, reason = score(case, answer)
        except Exception as exc:
            verdict, reason = "ERROR", str(exc)[:120]
            answer = {}

        if verdict == "PASS":
            passes += 1
        elif verdict == "ERROR":
            errors += 1

        sections.setdefault(case.section, []).append((verdict, case, answer, reason))

    # ── Print results by section ──────────────────────────────────────────────
    for section, rows in sections.items():
        sec_pass = sum(1 for v, *_ in rows if v == "PASS")
        print(f"\n── {section} ({sec_pass}/{len(rows)}) {'✓' if sec_pass == len(rows) else '✗'}")
        for verdict, case, answer, reason in rows:
            icon = "✓" if verdict == "PASS" else ("⚠" if verdict == "ERROR" else "✗")
            atype = answer.get("answer_type", "?") if answer else "?"
            topic = answer.get("canonical_topic") or "-"
            preview = (answer.get("answer_text") or "")[:90].replace("\n", " ")
            q_short = case.question[:70]
            refusal_obj = answer.get("refusal") or {}
            rcode = (refusal_obj.get("refusal_code") or "") if refusal_obj else ""

            print(f"  [{icon}] {verdict:<4}  Q: {q_short}")
            if case.note:
                print(f"              note: {case.note}")
            print(f"              → {atype} | topic={topic}")
            if preview:
                print(f"              A: {preview}")
            if rcode:
                print(f"              refusal_code: {rcode}")
            if reason:
                print(f"              FAIL reason: {reason}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  SCORE: {passes}/{total} PASS  |  {total-passes-errors} FAIL  |  {errors} ERROR")
    print(f"{'='*72}\n")

    by_section = {
        s: sum(1 for v, *_ in rows if v == "PASS") / len(rows) * 100
        for s, rows in sections.items()
    }
    for s, pct in by_section.items():
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {s:<20} {bar} {pct:.0f}%")
    print()


if __name__ == "__main__":
    run()
