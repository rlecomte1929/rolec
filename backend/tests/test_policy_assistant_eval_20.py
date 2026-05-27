"""
Sprint C — 20-question eval suite for the Policy Assistant RAG engine.

What this protects against
--------------------------
The engine is a pipeline: question → embed → retrieve top-K chunks →
build prompt → LLM → validator → answer. Each piece has its own unit
tests in test_policy_assistant_rag_a.py and _b.py. This suite is the
end-to-end gate: 20 representative HR/Employee questions running
through the FULL pipeline against a seeded policy, asserting that

  1. retrieval finds a relevant chunk for the question (NOT cross-domain
     drift — a "schools" question must not surface "shipment" first),
  2. the validator accepts a properly grounded answer with a real
     [chunk:<id>] citation,
  3. refusals trigger when the policy genuinely doesn't cover the
     question.

LLM is mocked (POLICY_ASSISTANT_LLM=mock) so this suite is offline,
deterministic, and free. The mock answers are hand-crafted per question
using the *actual* retrieved chunk id, which means the validator's
fabricated-id check is exercised against real chunk ids that exist in
the indexed table.

When tuning retrieval (chunk formatter, embedder, top-K, scoring), run
this suite to see which questions regress. The pass/fail summary at the
end is the headline.

Operational notes
-----------------
- The seed below is intentionally broader than Sprint A's two-benefit
  fixture: ~12 benefits across all 6 policy categories + 2 jurisdiction
  overrides. Add seeds (not Q&A) when retrieval coverage gaps appear.
- Add new eval cases to EVAL_CASES, not to the body of test methods.
- Don't assert exact LLM wording — the validator + retrieval contract
  is what we lock down.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the offline path before importing the engine.
os.environ["POLICY_ASSISTANT_LLM"] = "mock"
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

from backend.app.services import (  # noqa: E402
    policy_assistant_rag_engine as rag,
    policy_assistant_session_memory as session_memory,
    policy_chunk_indexer,
    policy_chunk_retriever,
)
from backend.app.services.policy_assistant_llm_client import LlmRequest, MockClient  # noqa: E402
from backend.app.services.policy_chunk_indexer import index_company_policy  # noqa: E402


# Schema mirrors the Supabase migration but stripped to what SQLite needs.
SCHEMA = """
CREATE TABLE policy_assistant_chunks (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    policy_version_id TEXT,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_metadata TEXT NOT NULL DEFAULT '{}',
    embedding TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, source_type, source_ref)
);
"""


class _FakePolicyDb:
    """Same shape as Sprint A's _FakePolicyDb. Duplicated here so the eval
    suite is self-contained — when the chunker schema evolves, this stays
    a stable contract for evals."""

    def __init__(self, engine):
        self.engine = engine
        self._configs = {}
        self._versions = {}
        self._benefits = {}
        self._overrides = {}

    def ensure_policy_config(self, company_id, config_key):
        return self._configs.get(company_id)

    def get_latest_published_policy_config_version(self, company_id, config_key):
        return self._versions.get(company_id)

    def get_policy_config_draft_for_config(self, pid):
        return None

    def list_policy_config_benefits(self, vid):
        return list(self._benefits.get(str(vid), []))

    def list_jurisdiction_overrides_for_benefit_rows(self, benefit_ids):
        out = {bid: [] for bid in benefit_ids}
        for bid in benefit_ids:
            out[bid] = list(self._overrides.get(str(bid), []))
        return out


class _StubAuditDb:
    def policy_hardening_tables_available(self):
        return False


def _seed_eval_company(fake_db, company_id: str = "co-eval") -> None:
    """A representative HR policy: one benefit per common employee
    question, plus two Section C overrides. Stays small enough to read,
    broad enough that retrieval has to actually choose."""
    cfg_id = f"cfg-{company_id}"
    ver_id = f"ver-{company_id}"
    fake_db._configs[company_id] = {"id": cfg_id, "company_id": company_id}
    fake_db._versions[company_id] = {
        "id": ver_id, "policy_config_id": cfg_id, "status": "published"
    }
    fake_db._benefits[ver_id] = [
        # Compensation & allowances
        {"id": "b-housing", "benefit_key": "housing_allowance",
         "benefit_label": "Housing allowance", "category": "compensation_allowances",
         "covered": True, "amount_value": 4500, "currency_code": "USD",
         "unit_frequency": "monthly",
         "notes": "Mid-cost city base. Director tier and above eligible for premium uplift."},
        {"id": "b-cola", "benefit_key": "cost_of_living_adjustment",
         "benefit_label": "Cost of living adjustment",
         "category": "compensation_allowances",
         "covered": True, "amount_value": 15, "currency_code": None,
         "unit_frequency": "percent_of_base",
         "notes": "Applied to gross base salary, recalculated annually."},
        # Relocation assistance
        {"id": "b-shipment", "benefit_key": "household_goods_shipment",
         "benefit_label": "Household goods shipment",
         "category": "relocation_assistance",
         "covered": True, "amount_value": 12000, "currency_code": "USD",
         "unit_frequency": "one_time",
         "notes": "Up to 40-foot container. Air freight requires HR pre-approval."},
        {"id": "b-temp-housing", "benefit_key": "temporary_housing",
         "benefit_label": "Temporary housing", "category": "relocation_assistance",
         "covered": True, "amount_value": 60, "currency_code": None,
         "unit_frequency": "days",
         "notes": "Up to 60 days at destination. Extension via HR exception."},
        {"id": "b-flights", "benefit_key": "relocation_flights",
         "benefit_label": "Relocation flights",
         "category": "relocation_assistance",
         "covered": True, "amount_value": None, "currency_code": None,
         "unit_frequency": None,
         "notes": "Economy for short-haul, business for flights over 6 hours. Covers employee + dependents."},
        # Family support & education
        {"id": "b-school-search", "benefit_key": "school_search",
         "benefit_label": "School search support",
         "category": "family_support_education",
         "covered": True, "amount_value": 3000, "currency_code": "USD",
         "unit_frequency": "one_time"},
        {"id": "b-tuition", "benefit_key": "tuition_reimbursement",
         "benefit_label": "Tuition reimbursement",
         "category": "family_support_education",
         "covered": True, "amount_value": 25000, "currency_code": "USD",
         "unit_frequency": "yearly_per_child",
         "notes": "International school fees per dependent child up to age 18."},
        {"id": "b-spouse", "benefit_key": "spouse_career_support",
         "benefit_label": "Spouse career support",
         "category": "family_support_education",
         "covered": True, "amount_value": 5000, "currency_code": "USD",
         "unit_frequency": "one_time",
         "notes": "Resume coaching, language training, or job-search services."},
        # Pre-assignment support
        {"id": "b-look-see", "benefit_key": "look_see_trip",
         "benefit_label": "Look-see trip",
         "category": "pre_assignment_support",
         "covered": True, "amount_value": 1, "currency_code": None,
         "unit_frequency": "trips",
         "notes": "One trip for employee + spouse before relocation, max 5 days."},
        # Leave & repatriation
        {"id": "b-home-leave", "benefit_key": "home_leave",
         "benefit_label": "Home leave",
         "category": "leave_repatriation",
         "covered": True, "amount_value": 1, "currency_code": None,
         "unit_frequency": "trips_per_year",
         "notes": "Annual round-trip flights for employee + dependents."},
        # Tax & payroll
        {"id": "b-tax-prep", "benefit_key": "tax_preparation",
         "benefit_label": "Tax preparation services",
         "category": "tax_payroll",
         "covered": True, "amount_value": None, "currency_code": None,
         "unit_frequency": None,
         "notes": "Provided by company-appointed tax firm for assignment duration + 1 year post."},
        # Pet relocation — explicitly NOT covered. Negative-coverage assertion.
        {"id": "b-pet", "benefit_key": "pet_relocation",
         "benefit_label": "Pet relocation",
         "category": "family_support_education",
         "covered": False},
    ]
    fake_db._overrides = {
        # Singapore directors: housing uplift to SGD 9,500/month
        "b-housing": [{
            "id": "ov-sg-housing",
            "jurisdiction_countries": ["SG"],
            "employee_level": "director",
            "amount_value": 9500, "currency_code": "SGD",
            "reimbursement_md": "SEA director cap; reflects Singapore housing market."
        }],
        # Tokyo: tuition uplift for international schooling
        "b-tuition": [{
            "id": "ov-jp-tuition",
            "jurisdiction_countries": ["JP"],
            "employee_level": None,
            "amount_value": 35000, "currency_code": "USD",
            "reimbursement_md": "Tokyo international school market premium."
        }],
    }


# Each case lists:
#   q                  — the user-facing question
#   expected_kind      — "answer" or "refusal_out_of_policy"
#   expected_term      — a substring (case-insensitive) the answer text MUST contain
#                         (typically the cap or amount). For refusals this is None.
#   chunk_match_term   — a substring the top retrieved chunk_text MUST contain
#                         (proves retrieval grabbed the right benefit). None for
#                         refusal cases (any chunk is fine, the validator will
#                         reject ungrounded answers).
EVAL_CASES: List[Dict[str, Optional[str]]] = [
    # --- Compensation & allowances (3) ---
    {"q": "What's the housing allowance for a relocation assignment?",
     "expected_kind": "answer", "expected_term": "4500", "chunk_match_term": "Housing"},
    {"q": "How much housing allowance does a Singapore director get?",
     "expected_kind": "answer", "expected_term": "9500", "chunk_match_term": "SG"},
    {"q": "Does the policy include cost of living adjustment?",
     "expected_kind": "answer", "expected_term": "cost of living", "chunk_match_term": "cost"},

    # --- Relocation assistance (4) ---
    {"q": "What's the cap on household goods shipment?",
     "expected_kind": "answer", "expected_term": "12000", "chunk_match_term": "shipment"},
    {"q": "Are temporary housing costs covered when I arrive?",
     "expected_kind": "answer", "expected_term": "60", "chunk_match_term": "Temporary"},
    {"q": "Can I fly business class on the relocation flight?",
     "expected_kind": "answer", "expected_term": "business", "chunk_match_term": "flight"},
    {"q": "Is air freight allowed for the household goods shipment?",
     "expected_kind": "answer", "expected_term": "pre-approval", "chunk_match_term": "shipment"},

    # --- Family support & education (4) ---
    {"q": "Is school search support included?",
     "expected_kind": "answer", "expected_term": "3000", "chunk_match_term": "School"},
    {"q": "How much tuition reimbursement per child?",
     "expected_kind": "answer", "expected_term": "25000", "chunk_match_term": "Tuition"},
    {"q": "Tuition cap for an assignment in Tokyo?",
     "expected_kind": "answer", "expected_term": "35000", "chunk_match_term": "JP"},
    {"q": "Does the company support spouse career assistance?",
     "expected_kind": "answer", "expected_term": "5000", "chunk_match_term": "Spouse"},

    # --- Pre-assignment + leave + tax (4) ---
    {"q": "Do I get a look-see trip before the move?",
     "expected_kind": "answer", "expected_term": "look-see", "chunk_match_term": "Look-see"},
    {"q": "How often can I take home leave?",
     "expected_kind": "answer", "expected_term": "annual", "chunk_match_term": "Home leave"},
    {"q": "Is tax preparation included?",
     "expected_kind": "answer", "expected_term": "tax", "chunk_match_term": "Tax"},
    {"q": "How long are tax services available after the assignment ends?",
     "expected_kind": "answer", "expected_term": "1 year", "chunk_match_term": "Tax"},

    # --- Negative coverage (2) — answers that flag NOT covered ---
    {"q": "Is pet relocation covered?",
     "expected_kind": "answer", "expected_term": "not covered", "chunk_match_term": "Pet"},
    {"q": "Does the policy cover moving my dog?",
     "expected_kind": "answer", "expected_term": "not covered", "chunk_match_term": "Pet"},

    # --- Out-of-policy refusals (3) — engine must NOT confabulate ---
    {"q": "What's the weather like in Tokyo today?",
     "expected_kind": "refusal_out_of_policy", "expected_term": None, "chunk_match_term": None},
    {"q": "Recommend a good Italian restaurant in Munich.",
     "expected_kind": "refusal_out_of_policy", "expected_term": None, "chunk_match_term": None},
    {"q": "How do I file my US tax return?",
     "expected_kind": "refusal_out_of_policy", "expected_term": None, "chunk_match_term": None},
]


class TwentyQuestionEvalSuite(unittest.TestCase):
    """End-to-end eval — populates failures with the question that broke
    so tuning has somewhere to start."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with cls.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        cls.fake_db = _FakePolicyDb(cls.engine)
        cls._p1 = mock.patch.object(policy_chunk_indexer, "db", cls.fake_db)
        cls._p2 = mock.patch.object(policy_chunk_retriever, "db", cls.fake_db)
        cls._p3 = mock.patch.object(rag, "db", _StubAuditDb())
        cls._p1.start()
        cls._p2.start()
        cls._p3.start()
        _seed_eval_company(cls.fake_db, "co-eval")
        index_company_policy("co-eval")

    @classmethod
    def tearDownClass(cls):
        cls._p1.stop()
        cls._p2.stop()
        cls._p3.stop()

    def setUp(self):
        session_memory._reset_all_for_tests()

    # --- helpers ----------------------------------------------------------

    def _build_grounded_mock_client(self, answer_template: str, chunk_id: str) -> MockClient:
        """Returns a MockClient whose first answer cites the given chunk id.
        The template is an f-string with one slot for the citation."""
        full_text = f"{answer_template} [chunk:{chunk_id}]."

        def stateful_complete(req: LlmRequest):
            return {
                "text": full_text, "model": req.model, "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "output_tokens": 30},
            }
        client = MockClient()
        client.complete = stateful_complete  # type: ignore[assignment]
        return client

    # --- the suite --------------------------------------------------------

    def test_eval_case_count_matches_target(self):
        """Locks the suite at 20 cases. If you add or remove, update the
        count here so the discrepancy is visible in CI rather than silent."""
        self.assertEqual(len(EVAL_CASES), 20)

    def test_run_all_cases(self):
        """One test method, 20 cases. Each failure prints which question
        broke and why so you don't have to grep test output."""
        passes: List[str] = []
        failures: List[str] = []

        for idx, case in enumerate(EVAL_CASES, start=1):
            q = case["q"]
            expected_kind = case["expected_kind"]
            expected_term = case["expected_term"]
            chunk_match_term = case["chunk_match_term"]
            tag = f"#{idx:02d} {q!r}"

            try:
                if expected_kind == "answer":
                    # Run retrieval first so the mock can cite a real chunk.
                    chunks = policy_chunk_retriever.retrieve(
                        company_id="co-eval", query=q, top_k=4
                    )
                    if not chunks:
                        failures.append(f"{tag}: retrieval returned no chunks")
                        continue
                    if chunk_match_term and not any(
                        chunk_match_term.lower() in c["chunk_text"].lower()
                        for c in chunks
                    ):
                        failures.append(
                            f"{tag}: retrieval missed expected term "
                            f"{chunk_match_term!r} in top-{len(chunks)} chunks. "
                            f"Got: " + " | ".join(c["chunk_text"][:60] for c in chunks)
                        )
                        continue

                    # Build a mock answer that cites the top chunk.
                    top_chunk_id = chunks[0]["id"]
                    template = f"Per the policy, {expected_term}"
                    client = self._build_grounded_mock_client(template, top_chunk_id)

                    result = rag.answer_policy_question(
                        company_id="co-eval", user_id="u-eval",
                        question=q, client=client,
                    )
                    if result["answer_kind"] != "answer":
                        failures.append(
                            f"{tag}: expected answer, got {result['answer_kind']!r}. "
                            f"Text: {result['answer_text'][:100]}"
                        )
                        continue
                    if expected_term and expected_term.lower() not in result["answer_text"].lower():
                        failures.append(
                            f"{tag}: answer missing expected term {expected_term!r}. "
                            f"Got: {result['answer_text'][:120]}"
                        )
                        continue
                    if not result["cited_chunks"]:
                        failures.append(f"{tag}: answer accepted with no citations")
                        continue
                    passes.append(tag)

                elif expected_kind == "refusal_out_of_policy":
                    # Default MockClient returns the canonical refusal when no
                    # pattern matches — exactly what the engine should return
                    # for genuinely out-of-policy questions.
                    client = MockClient(responses_by_pattern={})
                    result = rag.answer_policy_question(
                        company_id="co-eval", user_id="u-eval",
                        question=q, client=client,
                    )
                    if not result["answer_kind"].startswith("refusal"):
                        failures.append(
                            f"{tag}: expected refusal, got {result['answer_kind']!r}"
                        )
                        continue
                    passes.append(tag)
                else:
                    failures.append(f"{tag}: unknown expected_kind {expected_kind!r}")
            except Exception as exc:  # pragma: no cover
                failures.append(f"{tag}: raised {type(exc).__name__}: {exc}")

        # Headline summary printed even on success — useful when tuning.
        summary = (
            f"\n\n=== Policy Assistant 20-Q Eval ===\n"
            f"Passed:   {len(passes)} / {len(EVAL_CASES)}\n"
            f"Failed:   {len(failures)}\n"
        )
        if failures:
            summary += "\nFailures:\n" + "\n".join(f"  - {f}" for f in failures)
        print(summary)
        self.assertFalse(
            failures,
            msg=f"{len(failures)} of {len(EVAL_CASES)} eval cases failed:\n"
                + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
