"""
Phase 2 — Create Langfuse golden dataset for the ReloPass policy assistant.

Usage (from repo root, with venv_new active):
    python -m experiments.create_langfuse_golden_dataset

What it does:
  1. Creates (or updates) a Langfuse Dataset named ``policy-assistant-golden-v1``.
  2. Upserts 20 dataset items — one per eval question.
     Each item stores:
       input            → {"question": "..."}
       expected_output  → {"expected_verdict": ..., "description": ..., "checks": [...]}
  3. Prints a summary so you can verify everything uploaded before opening Langfuse.

The ``checks`` list is machine-checkable by the companion scorer
(see ``_score_item`` at the bottom of this file, and the ``experiments/run_golden_eval.py``
entry-point that runs the dataset through the live system).

Check kinds:
  answer_type_eq          → answer["answer_type"] == value
  answer_type_ne          → answer["answer_type"] != value
  refusal_not_unknown     → NOT (answer_type==refusal AND policy_status==unknown)
  answer_text_not_empty   → answer["answer_text"] is non-empty
  answer_text_not_contains → value NOT in answer["answer_text"]
  answer_text_aspect_check → IF trigger in answer_text THEN requires_any must also be present

After uploading, go to cloud.langfuse.com → Datasets → policy-assistant-golden-v1
to inspect, annotate, or run future evals.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Bootstrap ────────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env, override=False)

sys.path.insert(0, str(_root))

# ── Golden items ──────────────────────────────────────────────────────────────
# Each item maps directly to one of the 20 eval questions.
# ``checks`` encode the PASS/FAIL rubric in a machine-readable form so a scorer
# can evaluate live results against this dataset without hard-coding question indices.

GOLDEN_ITEMS: List[Dict[str, Any]] = [
    # ─── Q01 ──────────────────────────────────────────────────────────────────
    {
        "question": "What is the relocation allowance amount for this policy?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Entitlement summary with cap amount (EUR 5,000) OR honest "
                "'not_in_policy' if no benefit rule is found. "
                "Bare refusal with policy_status=unknown is always FAIL."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q02 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is there a deadline to claim the relocation allowance?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Aspect=deadline. Must NOT simply repeat the EUR 5,000 cap. "
                "If the policy data specifies a deadline, show it. "
                "If not, say so explicitly (regression guard for E3)."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
                {
                    "kind": "answer_text_aspect_check",
                    "trigger": "5,000",
                    "requires_any": [
                        "deadline",
                        "doesn't specify",
                        "not specified",
                        "no deadline",
                        "policy text",
                    ],
                },
            ],
        },
    },
    # ─── Q03 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is there a lump sum option instead of managed relocation services?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Aspect=structure. Must NOT simply repeat the EUR 5,000 cap. "
                "If policy specifies lump-sum vs managed, show it. "
                "If not, say so (regression guard for E3)."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
                {
                    "kind": "answer_text_aspect_check",
                    "trigger": "5,000",
                    "requires_any": [
                        "lump",
                        "managed",
                        "structure",
                        "doesn't specify",
                        "not specified",
                        "policy text",
                    ],
                },
            ],
        },
    },
    # ─── Q04 ──────────────────────────────────────────────────────────────────
    {
        "question": "How many home leave trips does the policy allow per year?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Must return a trip count (e.g. '3 trips') or honest 'not specified'. "
                "Must NOT present section reference §8.3 as a quantity "
                "(regression guard for E2). '8.3' and '8.30' in answer_text are FAIL."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
                {"kind": "answer_text_not_contains", "value": "8.3"},
                {"kind": "answer_text_not_contains", "value": "8.30"},
            ],
        },
    },
    # ─── Q05 ──────────────────────────────────────────────────────────────────
    {
        "question": "Does the policy cover flights for my family on home leave?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "In-scope home_leave sub-question. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q06 ──────────────────────────────────────────────────────────────────
    {
        "question": "What housing support is included for the host country?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "HOST_HOUSING topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q07 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is temporary housing provided at the start of the assignment?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "TEMPORARY_HOUSING topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q08 ──────────────────────────────────────────────────────────────────
    {
        "question": "Are household goods and personal effects covered for shipment?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "SHIPMENT topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q09 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is storage of household goods included during the assignment?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "SHIPMENT / storage sub-question. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q10 ──────────────────────────────────────────────────────────────────
    {
        "question": "Does the policy cover school fees for dependent children?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "SCHOOL_SEARCH topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q11 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is language training available for the assignee and family?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "SCHOOL_SEARCH / language_training key. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q12 ──────────────────────────────────────────────────────────────────
    {
        "question": "Does the policy cover work permit and visa fees?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "VISA_SUPPORT topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q13 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is immigration support provided for accompanying family members?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "VISA_SUPPORT / family scope. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q14 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is there a spousal career support allowance?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "SPOUSE_SUPPORT topic. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q15 ──────────────────────────────────────────────────────────────────
    {
        "question": "What is the cost of living allowance (COLA) under this policy?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "RELOCATION_ALLOWANCE / COLA key. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q16 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is a mobility premium included? What is the percentage?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": "RELOCATION_ALLOWANCE / mobility_premium key. Not a bare refusal; non-empty answer.",
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q17 ──────────────────────────────────────────────────────────────────
    {
        "question": "Is this policy published and visible to employees?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Status question (POLICY_STATUS_QUESTION or similar). "
                "Must return some answer about publication state; not a bare unknown refusal."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q18 ──────────────────────────────────────────────────────────────────
    {
        "question": "What does the policy say about banking support?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "BANKING_SETUP is in the taxonomy (added E4 fix). "
                "Must NOT return a bare refusal — should return entitlement_summary or not_in_policy."
            ),
            "checks": [
                {"kind": "refusal_not_unknown"},
                {"kind": "answer_text_not_empty"},
            ],
        },
    },
    # ─── Q19 — OUT OF SCOPE ───────────────────────────────────────────────────
    {
        "question": "What is the best school district in Paris?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Out-of-scope lifestyle/location advice. "
                "Must return answer_type=refusal. Any other type is FAIL."
            ),
            "checks": [
                {"kind": "answer_type_eq", "value": "refusal"},
            ],
        },
    },
    # ─── Q20 — OUT OF SCOPE ───────────────────────────────────────────────────
    {
        "question": "Can you help me negotiate a better relocation package?",
        "expected_output": {
            "expected_verdict": "PASS",
            "description": (
                "Out-of-scope negotiation request. "
                "Must return answer_type=refusal. Any other type is FAIL."
            ),
            "checks": [
                {"kind": "answer_type_eq", "value": "refusal"},
            ],
        },
    },
]


# ── Scorer ────────────────────────────────────────────────────────────────────

def _score_item(answer: Dict[str, Any], expected_output: Dict[str, Any]) -> str:
    """
    Apply the checks from ``expected_output`` to a live ``answer`` dict.
    Returns "PASS" or "FAIL".

    ``answer`` is the dict at result["answer"] from hr_policy_assistant_query_response_dict.
    """
    atype = answer.get("answer_type", "")
    pstatus = answer.get("policy_status", "")
    text = answer.get("answer_text", "") or ""
    tl = text.lower()

    for check in expected_output.get("checks", []):
        kind = check["kind"]

        if kind == "answer_type_eq":
            if atype != check["value"]:
                return "FAIL"

        elif kind == "answer_type_ne":
            if atype == check["value"]:
                return "FAIL"

        elif kind == "refusal_not_unknown":
            # A bare refusal with unknown status is always wrong for in-scope questions.
            if atype == "refusal" and pstatus == "unknown":
                return "FAIL"

        elif kind == "answer_text_not_empty":
            if not text and atype != "refusal":
                return "FAIL"

        elif kind == "answer_text_not_contains":
            if check["value"] in text:
                return "FAIL"

        elif kind == "answer_text_aspect_check":
            # If the trigger string appears in answer_text, at least one of
            # requires_any must also be present (case-insensitive).
            trigger = check["trigger"]
            requires_any: List[str] = check["requires_any"]
            if trigger in text:
                if not any(kw in tl for kw in requires_any):
                    return "FAIL"

    return "PASS"


# ── Upload ────────────────────────────────────────────────────────────────────

DATASET_NAME = "policy-assistant-golden-v1"
DATASET_DESCRIPTION = (
    "20-question golden eval set for the ReloPass HR policy assistant. "
    "Covers all 13 canonical topics + E2/E3 regression guards + 2 out-of-scope refusal checks. "
    "Baseline: 20/20 PASS as of 2026-06-15 (post E1–E4 fixes)."
)


def upload_dataset() -> None:
    try:
        from langfuse import Langfuse
    except ImportError:
        print("ERROR: langfuse not installed — run: pip install langfuse --break-system-packages")
        sys.exit(1)

    lf = Langfuse(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    # Create dataset (idempotent — Langfuse returns existing dataset if name matches)
    print(f"\nCreating dataset '{DATASET_NAME}' …")
    try:
        lf.create_dataset(name=DATASET_NAME, description=DATASET_DESCRIPTION)
        print("  → created (or already exists)")
    except Exception as exc:
        print(f"  → create_dataset: {exc!r} (continuing)")

    # Upsert items
    print(f"\nUploading {len(GOLDEN_ITEMS)} items …\n")
    ok = 0
    for i, item in enumerate(GOLDEN_ITEMS, start=1):
        q = item["question"]
        eo = item["expected_output"]
        try:
            lf.create_dataset_item(
                dataset_name=DATASET_NAME,
                input={"question": q},
                expected_output=eo,
            )
            verdict = eo["expected_verdict"]
            print(f"  [Q{i:02d}] ✓  expected={verdict}  |  {q[:80]}")
            ok += 1
        except Exception as exc:
            print(f"  [Q{i:02d}] ✗  ERROR: {exc!r}")
            print(f"         Q: {q[:80]}")

    lf.flush()
    print(f"\n=== Uploaded {ok}/{len(GOLDEN_ITEMS)} items to '{DATASET_NAME}' ===")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    print(f"\nView at: {host} → Datasets → {DATASET_NAME}\n")


# ── Local dry-run verifier ────────────────────────────────────────────────────

def dry_run_verifier() -> None:
    """
    Run the 20 golden questions through the live pipeline and score them against
    the checks defined in this file.  Useful for confirming the baseline before
    uploading to Langfuse or after any code change.

    Usage:
        python -m experiments.create_langfuse_golden_dataset --verify
    """
    from backend.observability import configure_observability
    configure_observability()

    from backend.app.services.hr_policy_assistant_service import (
        hr_policy_assistant_query_response_dict,
    )

    POLICY_ID = "d70615b6-11b3-4595-989e-a3ef20cf2fe2"
    MOCK_HR_USER = {
        "id": "eval-user-00000000",
        "role": "HR",
        "company_id": "0d3e8d04-b463-4516-a26d-bf0e8f68dbdb",
        "email": "eval@relopass.com",
    }

    print(f"\n=== Golden Dataset Dry-Run — {len(GOLDEN_ITEMS)} Questions ===\n")
    passes = 0
    for i, item in enumerate(GOLDEN_ITEMS, start=1):
        q = item["question"]
        eo = item["expected_output"]
        try:
            result = hr_policy_assistant_query_response_dict(
                message=q,
                user=MOCK_HR_USER,
                policy_id=POLICY_ID,
            )
            answer = result.get("answer", {})
            verdict = _score_item(answer, eo)
            if verdict == "PASS":
                passes += 1

            atype = answer.get("answer_type", "?")
            topic = answer.get("canonical_topic") or "-"
            pstatus = answer.get("policy_status", "?")
            preview = (answer.get("answer_text") or "")[:120].replace("\n", " ")
            refusal_obj = answer.get("refusal") or {}
            rcode = refusal_obj.get("refusal_code", "") if refusal_obj else ""

            print(f"[Q{i:02d}] {verdict} | {atype} | topic={topic} | status={pstatus}")
            print(f"       Q: {q[:90]}")
            if preview:
                print(f"       A: {preview}")
            if rcode:
                print(f"       refusal_code: {rcode}")
            print()
        except Exception as exc:
            print(f"[Q{i:02d}] ERROR: {exc}")
            print()

    print(f"=== SCORE: {passes}/{len(GOLDEN_ITEMS)} PASS ===\n")


if __name__ == "__main__":
    if "--verify" in sys.argv:
        dry_run_verifier()
    else:
        upload_dataset()
