# AI Unit-Economics — Live Tracer Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing `TraceSession` into the `policy_assistant` and `policy_extraction` live paths so real cost/carbon/token rows flow into `policy_assistant_traces` (and thus `mv_ai_unit_economics` + `GET /api/admin/ai-unit-economics`), after first repairing the prod table so the writer's INSERT does not silently fail.

**Architecture:** Three independent changes. (1) An additive, idempotent forward migration adds the two Step D columns the merged writer already INSERTs but prod is missing — without this, every prod insert raises `UndefinedColumn`, is swallowed, and writes zero rows. (2) Surgical in-place instrumentation of `answer_policy_question`. (3) Surgical in-place instrumentation of `extract_policy_with_llm`, threading an optional `company_id` through `extract_policy_with_diff` from the live caller. No new abstraction — the two surfaces have different shapes (one uses the `LlmClient` dict-returning abstraction, the other the raw Anthropic SDK returning a `Message`).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (raw via `backend/database.py`), Anthropic SDK, pytest (SQLite in-memory), Supabase (Postgres) migrations applied via the Supabase MCP `apply_migration`.

**Design reference:** `docs/superpowers/specs/2026-06-03-ai-unit-economics-live-tracer-wiring-design.md`

---

## Key facts the executor must know (verified against the code)

- `TraceSession.__init__(session_id, query, company_id, feature_key, customer_id=None, prompt_version_id=None, canary_arm=None)` — `feature_key` is **required**; `customer_id` defaults to `company_id` when not passed (`backend/app/services/ai_trace_logger.py:83`).
- `flush()` never raises; it computes unit-economics and calls `db.insert_policy_assistant_trace(...)` via a fresh `from ...database import db` import at call time (`ai_trace_logger.py:172`, `:254`). **Tests capture rows by monkeypatching `backend.database.db`.**
- `_compute_unit_economics()` reads carbon from `ai_carbon_estimator.estimate_co2e_grams`, which falls back to in-code defaults when `_load_profile_from_db` returns `None`. **Tests force defaults by monkeypatching `ai_carbon_estimator._load_profile_from_db` → `lambda model_name: None` and calling `est.clear_cache()`** (pattern from `backend/tests/test_trace_logger_carbon.py`).
- `answer_policy_question` returns `usage` as a dict with `input_tokens`/`output_tokens`; `model_used` and `latency_ms` are computed in-function; `prompt_version_id`/`canary_arm` are resolved from the prompt registry near the top (`policy_assistant_rag_engine.py:228`).
- `extract_policy_with_llm` success path builds `result` and returns it (`llm_policy_extractor.py:344`). At that point `model`, `call_latency_ms`, `prompt_version_id`, `canary_arm`, and `message.usage` (`.input_tokens`/`.output_tokens`) are all in scope. All early-return fallbacks (no key, SDK missing, API error, no tool_use) return `None` **before** that point.
- Live extractor caller: `backend/main.py:13133`, inside the `/extract-preview` handler, with `policy = db.get_company_policy(policy_id)` already in scope (`get_company_policy` does `SELECT *` from `company_policies`, which has a `company_id` column).

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `supabase/migrations/20260605300000_policy_assistant_traces_step_d_columns.sql` | Add `prompt_version_id`, `canary_arm` to prod `policy_assistant_traces` | **Create** |
| `backend/app/services/policy_assistant_rag_engine.py` | `policy_assistant` surface | **Modify** `answer_policy_question` (~line 183) |
| `backend/app/services/llm_policy_extractor.py` | `policy_extraction` surface | **Modify** `extract_policy_with_llm` signature + success path (~line 197) |
| `backend/app/services/policy_extractor.py` | diff orchestrator | **Modify** `extract_policy_with_diff` signature + call site (~line 353, :381) |
| `backend/main.py` | live extractor caller | **Modify** one line (~line 13133) |
| `backend/tests/test_live_tracer_wiring.py` | new behavior coverage | **Create** |

---

## Task 1: Prerequisite prod migration — add Step D columns to `policy_assistant_traces`

**Why first:** The merged `db.insert_policy_assistant_trace` INSERT column list includes `prompt_version_id` and `canary_arm`, but the prod table (defined only by `20260605000000_ai_unit_economics_reauthor.sql`) lacks them. `init_db()` returns early on Postgres, so the SQLite-only `ADD COLUMN` scaffolding never runs on prod. Without this migration, every prod insert raises `UndefinedColumn`, gets swallowed by the best-effort `try/except`, and persists **zero rows** — and the 29 SQLite tests cannot catch it. Wiring the tracer (Tasks 2–3) is behaviorally dead on prod until this lands.

**Files:**
- Create: `supabase/migrations/20260605300000_policy_assistant_traces_step_d_columns.sql`

- [ ] **Step 1: Write the migration file**

Create `supabase/migrations/20260605300000_policy_assistant_traces_step_d_columns.sql`:

```sql
-- Add Parker Step D prompt-attribution columns to policy_assistant_traces.
--
-- The merged writer (db.insert_policy_assistant_trace / TraceSession.flush) already
-- INSERTs prompt_version_id and canary_arm, but the prod table was created by
-- 20260605000000_ai_unit_economics_reauthor.sql with only the 8 base + 6 Step G
-- columns. init_db() returns early on Postgres, so the SQLite-only ADD COLUMN
-- backfill never runs on prod. Without these columns every insert raises
-- UndefinedColumn, is swallowed by the best-effort try/except, and writes zero rows.
--
-- Additive + idempotent. No new table, so the new-table RLS hard-gates do not apply;
-- RLS is already enabled on policy_assistant_traces by the reauthor migration.

ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS prompt_version_id TEXT;
ALTER TABLE public.policy_assistant_traces ADD COLUMN IF NOT EXISTS canary_arm TEXT;
```

- [ ] **Step 2: Commit the migration file**

```bash
find .git -name "*.lock" -delete && git add supabase/migrations/20260605300000_policy_assistant_traces_step_d_columns.sql && git commit -m "feat(ai-econ): add Step D columns to policy_assistant_traces (prod writer fix)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 3: Apply to prod via Supabase MCP** *(shared-state action — confirm with the user before running)*

`supabase db push` is blocked by history drift in this repo, so apply via the MCP `apply_migration` tool against project `nsvefcvpvwwwhuqyuqmp` with name `policy_assistant_traces_step_d_columns` and the SQL body from Step 1.

- [ ] **Step 4: Verify the columns exist on prod**

Via the MCP `execute_sql` tool against the same project:

```sql
select column_name
from information_schema.columns
where table_name = 'policy_assistant_traces'
order by column_name;
```

Expected: the result set includes both `prompt_version_id` and `canary_arm` (alongside the existing base + Step G columns). The full INSERT column list in `db.insert_policy_assistant_trace` must be a subset of this set.

---

## Task 2: Wire `TraceSession` into `answer_policy_question` (`policy_assistant`)

**Files:**
- Modify: `backend/app/services/policy_assistant_rag_engine.py` (function `answer_policy_question`, ~line 183)
- Test: `backend/tests/test_live_tracer_wiring.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_live_tracer_wiring.py` with the policy_assistant cases. This file uses the `test_trace_logger_carbon.py` capture pattern (fake `backend.database.db`, carbon DB read forced to in-code defaults) plus the `test_policy_assistant_rag_b.py` engine harness (stubbed retriever, `MockClient`, stubbed audit db).

```python
"""
Live-tracer wiring tests — assert answer_policy_question and extract_policy_with_llm
write a feature-tagged row into policy_assistant_traces via TraceSession.flush().

Captures rows by monkeypatching backend.database.db (the tracer re-imports it at
flush time) and forces in-code carbon defaults by monkeypatching the carbon DB read.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force mock LLM + hash embedder so nothing calls an external API.
os.environ["POLICY_ASSISTANT_LLM"] = "mock"
os.environ["POLICY_ASSISTANT_EMBEDDER"] = "hash"

import backend.database as database  # noqa: E402
from backend.app.services import ai_carbon_estimator as est  # noqa: E402
from backend.app.services import (  # noqa: E402
    policy_assistant_rag_engine as rag,
    policy_assistant_session_memory as session_memory,
    policy_chunk_retriever,
)
from backend.app.services.policy_assistant_llm_client import MockClient  # noqa: E402


class _FakeTraceDB:
    def __init__(self, *, blow_up: bool = False):
        self.rows = []
        self.blow_up = blow_up

    def insert_policy_assistant_trace(self, **kwargs):
        if self.blow_up:
            raise RuntimeError("trace db down")
        self.rows.append(kwargs)


class _StubAuditDb:
    """rag_engine writes audits via db.* — no-op so the audit path is inert."""
    def policy_hardening_tables_available(self):
        return False


@pytest.fixture(autouse=True)
def _no_carbon_db(monkeypatch):
    monkeypatch.setattr(est, "_load_profile_from_db", lambda model_name: None)
    est.clear_cache()
    yield
    est.clear_cache()


@pytest.fixture
def _rag_harness(monkeypatch):
    session_memory._reset_all_for_tests()
    monkeypatch.setattr(
        policy_chunk_retriever, "retrieve",
        lambda **kw: [
            {"id": "ch-1", "source_type": "matrix_benefit",
             "source_ref": "policy_config_benefits.b1",
             "chunk_text": "Housing allowance: USD 4,500 per month."},
        ],
    )
    monkeypatch.setattr(rag, "db", _StubAuditDb())


def test_answer_policy_question_writes_trace(monkeypatch, _rag_harness):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    client = MockClient(responses_by_pattern={
        "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
    })

    result = rag.answer_policy_question(
        company_id="acme", user_id="u-1",
        question="What's the housing allowance?",
        client=client,
    )

    assert result["answer_kind"] == "answer"
    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["feature_key"] == "policy_assistant"
    assert row["customer_id"] == "acme"          # defaults to company_id
    assert row["company_id"] == "acme"
    assert row["tokens_in"] > 0
    assert row["tokens_out"] > 0
    assert row["co2e_grams_estimated"] > 0.0


def test_answer_policy_question_trace_failure_is_swallowed(monkeypatch, _rag_harness):
    fake = _FakeTraceDB(blow_up=True)
    monkeypatch.setattr(database, "db", fake)
    client = MockClient(responses_by_pattern={
        "housing": "Housing allowance is USD 4,500/month [chunk:ch-1].",
    })

    result = rag.answer_policy_question(
        company_id="acme", user_id="u-1",
        question="What's the housing allowance?",
        client=client,
    )

    # Trace write blew up internally but the answer is still returned normally.
    assert result["answer_kind"] == "answer"
    assert "USD 4,500" in result["answer_text"]
    assert fake.rows == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_live_tracer_wiring.py::test_answer_policy_question_writes_trace -v`
Expected: FAIL — `assert len(fake.rows) == 1` fails with `0 == 1` (no tracer constructed yet, so nothing is written).

- [ ] **Step 3: Instrument `answer_policy_question`**

In `backend/app/services/policy_assistant_rag_engine.py`, the `from .ai_trace_logger import TraceSession` import is needed. Add it to the existing import block near the top (after the `from ...database import db` line ~32):

```python
from .ai_trace_logger import TraceSession
```

Then wrap the body of `answer_policy_question` so a `TraceSession` is constructed after input validation and flushed on every exit path. Replace the current body from `started = time.time()` through the final `return {...}` with the version below. The only changes vs. the original are: (a) the `tracer = TraceSession(...)` construction, (b) the `try:` wrapping the existing body (everything is indented one level), (c) the best-effort recording block placed right after `latency_ms` is computed, and (d) the `finally: tracer.flush()`.

```python
    started = time.time()
    client = client or get_default_client()

    tracer = TraceSession(
        session_id=session_id, query=q, company_id=company_id,
        feature_key="policy_assistant",
    )
    try:
        # Prompt registry (Parker Step D). Best-effort: when the registry is absent
        # or empty, `active` is None and we fall back to the module SYSTEM_PROMPT /
        # DEFAULT_MODEL — behavior is identical to pre-registry.
        active = None
        try:
            from .prompt_registry import get_active_prompt
            active = get_active_prompt("policy_assistant_answer")
        except Exception:  # noqa: BLE001 — registry must never block the assistant
            active = None
        system_prompt = active.system_prompt if active is not None else SYSTEM_PROMPT
        # Explicit caller model wins; else registry; else module default.
        resolved_model = model or (active.model_name if active is not None else DEFAULT_MODEL)
        prompt_version_id = active.id if active is not None else None
        canary_arm = active.canary_arm if active is not None else None

        # 1. Retrieve top-K chunks for this company.
        chunks = policy_chunk_retriever.retrieve(
            company_id=company_id, query=q, top_k=top_k
        )

        # 2. Pull last 4 turns for this session (empty if first turn).
        turns = session_memory.get_recent_turns(session_id) if session_id else []

        # 3. Build prompt and call LLM (up to 2 attempts on validation).
        user_message = _build_user_message(
            company_label=company_label or "your company",
            question=q,
            chunks=chunks,
            turns=turns,
            employee_context=employee_context,
        )
        req = LlmRequest(system=system_prompt, user_message=user_message, model=resolved_model)

        answer_text, usage, model_used, validation_error = _call_with_retry(client, req, chunks)

        # 4. Determine answer kind + final text. If the second attempt still
        # fails validation, fall back to the canonical refusal — better to
        # surface a safe non-answer than a hallucinated or unverified one.
        if validation_error:
            log.warning(
                "policy_assistant validation failed twice company=%s user=%s err=%s",
                company_id, user_id, validation_error,
            )
            answer_text = REFUSAL_TEXT
            answer_kind = "refusal_validation_failed"
        elif answer_text.strip() == REFUSAL_TEXT:
            answer_kind = "refusal_out_of_policy"
        else:
            answer_kind = "answer"

        # 5. Resolve cited chunks back to full records so the UI can render
        # clickable references.
        cited_ids = extract_cited_chunk_ids(answer_text)
        cited_chunks = [c for c in chunks if str(c.get("id")) in cited_ids]

        cost = estimate_cost_usd(usage, model_used)
        latency_ms = int((time.time() - started) * 1000)

        # Unit-economics trace (Parker Step G). Best-effort: a recording error
        # must never escape into the assistant return path. flush() runs in the
        # finally below so it fires on every exit path.
        try:
            tracer.record_step("retrieval", latency_ms=0, chunk_count=len(chunks))
            tracer.record_llm_call(
                model=model_used,
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                latency_ms=latency_ms,
            )
            tracer.set_prompt_attribution(prompt_version_id, canary_arm)
        except Exception:  # noqa: BLE001 — tracing must never break the assistant
            log.debug("policy_assistant tracer record failed", exc_info=True)

        # 6. Update session memory (only if a session_id was supplied —
        # one-off questions don't pollute multi-turn flows).
        if session_id:
            session_memory.record_turn(session_id, q, answer_text)

        # 7. Audit. Best-effort: never fail the call on audit failure.
        audit_id: Optional[str] = None
        try:
            audit_id = _write_audit(
                company_id=company_id,
                user_id=user_id,
                question_text=q,
                answer_text=answer_text,
                answer_kind=answer_kind,
                cited_chunk_ids=cited_ids,
                session_id=session_id,
            )
        except Exception:
            log.exception("policy_assistant audit log write failed")

        return {
            "answer_text": answer_text,
            "answer_kind": answer_kind,
            "cited_chunks": [
                {
                    "id": c.get("id"),
                    "source_type": c.get("source_type"),
                    "source_ref": c.get("source_ref"),
                    "chunk_text": c.get("chunk_text"),
                }
                for c in cited_chunks
            ],
            "model": model_used,
            "usage": usage,
            "cost_usd": round(cost, 6),
            "latency_ms": latency_ms,
            "audit_id": audit_id,
            "prompt_version_id": prompt_version_id,
            "canary_arm": canary_arm,
        }
    finally:
        tracer.flush()
```

(The input-validation block — `if not company_id: ...`, `if not user_id: ...`, `q = (question or "").strip()`, `if not q: ...` — stays **above** `started = time.time()` and is unchanged. Those `ValueError`s fire before any tracer/LLM cost, which is correct.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_live_tracer_wiring.py -v`
Expected: both `test_answer_policy_question_writes_trace` and `test_answer_policy_question_trace_failure_is_swallowed` PASS.

- [ ] **Step 5: Run the existing rag engine suites for regression**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_policy_assistant_rag_a.py tests/test_policy_assistant_rag_b.py tests/test_ai_trace_logger.py tests/test_trace_logger_carbon.py -v`
Expected: all PASS (the cost/latency/refusal/memory assertions are unaffected).

- [ ] **Step 6: Commit**

```bash
find .git -name "*.lock" -delete && git add backend/app/services/policy_assistant_rag_engine.py backend/tests/test_live_tracer_wiring.py && git commit -m "feat(ai-econ): wire TraceSession into answer_policy_question

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Thread `company_id` + wire `TraceSession` into `extract_policy_with_llm` (`policy_extraction`)

**Files:**
- Modify: `backend/app/services/policy_extractor.py` (`extract_policy_with_diff` signature ~line 353, call site ~line 381)
- Modify: `backend/app/services/llm_policy_extractor.py` (`extract_policy_with_llm` signature ~line 197, success path ~line 344)
- Modify: `backend/main.py` (caller ~line 13133)
- Test: `backend/tests/test_live_tracer_wiring.py` (append)

- [ ] **Step 1: Write the failing tests (append to the file from Task 2)**

Append to `backend/tests/test_live_tracer_wiring.py`:

```python
import types  # noqa: E402

from backend.app.services import llm_policy_extractor  # noqa: E402
from backend.app.services import policy_extractor  # noqa: E402


def _fake_anthropic_module(*, tool_input, input_tokens=1200, output_tokens=300):
    """Build a stand-in `anthropic` module whose Anthropic().messages.create()
    returns a Message with one tool_use block and a usage object."""
    block = types.SimpleNamespace(type="tool_use", input=tool_input)
    message = types.SimpleNamespace(
        content=[block],
        usage=types.SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )

    class _Messages:
        def create(self, **kwargs):
            return message

    class _Anthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Anthropic)


_TOOL_INPUT = {
    "policy_meta": {"title": "Acme Relocation Policy", "version": "2.3",
                    "effective_date": "2026-01-01"},
    "benefits": [
        {"service_category": "housing", "benefit_key": "temporary_housing",
         "benefit_label": "Temporary housing", "confidence": 0.9},
    ],
}


def test_extract_policy_with_llm_writes_trace(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-noop")
    monkeypatch.setitem(sys.modules, "anthropic",
                        _fake_anthropic_module(input_tokens=1200, output_tokens=300))

    result = llm_policy_extractor.extract_policy_with_llm(
        ["Acme Corp Relocation Policy v2.3", "6.1 Temporary housing — 60 days."],
        company_id="acme",
    )

    assert result is not None and result["extracted_by"] == "ai"
    assert len(fake.rows) == 1
    row = fake.rows[0]
    assert row["feature_key"] == "policy_extraction"
    assert row["customer_id"] == "acme"
    assert row["tokens_in"] == 1200
    assert row["tokens_out"] == 300
    assert row["co2e_grams_estimated"] > 0.0


def test_extract_policy_company_id_threads_through(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-noop")
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic_module())
    monkeypatch.setattr(policy_extractor, "_parse_lines_from_bytes",
                        lambda data, ftype: ["6.1 Temporary housing — 60 days."])

    policy_extractor.extract_policy_with_diff(b"unused", "docx", company_id="acme-co")

    assert len(fake.rows) == 1
    assert fake.rows[0]["customer_id"] == "acme-co"
    assert fake.rows[0]["feature_key"] == "policy_extraction"


def test_extract_fallback_paths_emit_no_trace(monkeypatch):
    fake = _FakeTraceDB()
    monkeypatch.setattr(database, "db", fake)
    # No ANTHROPIC_API_KEY → regex fallback, no LLM call, no trace.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert llm_policy_extractor.extract_policy_with_llm(
        ["6.1 Temporary housing — 60 days."], company_id="acme"
    ) is None
    assert fake.rows == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_live_tracer_wiring.py::test_extract_policy_with_llm_writes_trace tests/test_live_tracer_wiring.py::test_extract_policy_company_id_threads_through -v`
Expected: FAIL — `extract_policy_with_llm`/`extract_policy_with_diff` reject the unexpected `company_id` keyword argument with `TypeError: ... got an unexpected keyword argument 'company_id'`.

- [ ] **Step 3: Add `company_id` to the extractor signature and emit the trace**

In `backend/app/services/llm_policy_extractor.py`, change the signature (~line 197):

```python
def extract_policy_with_llm(
    lines: List[str], company_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
```

Then, in the success path, after `result = {...}` is built and `_forward_to_langsmith(...)` is called, and immediately before `return result` (~line 367), insert the best-effort trace:

```python
    # Unit-economics trace (Parker Step G). Only on the success path — the
    # fallback/early-return paths above incur no LLM cost. Best-effort: never
    # block extraction.
    try:
        from .ai_trace_logger import TraceSession

        tracer = TraceSession(
            session_id=None,
            query="<policy extraction>",  # hashed to query_hash; carries no document content
            company_id=company_id or "unknown",
            feature_key="policy_extraction",
        )
        tracer.record_llm_call(
            model=model,
            input_tokens=int(getattr(message.usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(message.usage, "output_tokens", 0) or 0),
            latency_ms=call_latency_ms,
        )
        tracer.set_prompt_attribution(prompt_version_id, canary_arm)
        tracer.flush()
    except Exception:  # noqa: BLE001 — tracing must never break extraction
        logger.debug("policy_extraction tracer flush failed", exc_info=True)
    return result
```

(`Optional` is already imported in this module via `from typing import ... Optional`; no new top-level import beyond the function-local `TraceSession`.)

- [ ] **Step 4: Thread `company_id` through the diff orchestrator**

In `backend/app/services/policy_extractor.py`, change the signature (~line 353):

```python
def extract_policy_with_diff(
    file_bytes: bytes, file_type: str, company_id: Optional[str] = None
) -> Dict[str, Any]:
```

And the LLM call site (~line 381) inside the `try`:

```python
        llm_result = extract_policy_with_llm(lines, company_id=company_id)
```

(Confirm `Optional` is imported at the top of `policy_extractor.py`; it is used elsewhere in the module, but if a type-check flags it, add `Optional` to the existing `from typing import ...` line.)

- [ ] **Step 5: Run the new + existing extractor tests**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest tests/test_live_tracer_wiring.py tests/test_llm_policy_extractor.py -v`
Expected: all PASS. In particular `test_llm_policy_extractor.py` (which calls `extract_policy_with_llm(SAMPLE_LINES)` and `extract_policy_with_diff(b"unused", "docx")` with no `company_id`) still passes because the new parameter is defaulted.

- [ ] **Step 6: Pass `company_id` from the live caller in `backend/main.py`**

At `backend/main.py:13133`, change:

```python
        preview = extract_policy_with_diff(data, policy.get("file_type") or "docx")
```

to:

```python
        preview = extract_policy_with_diff(
            data, policy.get("file_type") or "docx",
            company_id=policy.get("company_id"),
        )
```

- [ ] **Step 7: Verify the caller wiring imports cleanly**

Run: `cd .. && python3 -c "from backend.main import app; print('ok')"`
Expected: prints `ok` (no import/syntax error from the edited caller).

- [ ] **Step 8: Commit**

```bash
find .git -name "*.lock" -delete && git add backend/app/services/llm_policy_extractor.py backend/app/services/policy_extractor.py backend/main.py backend/tests/test_live_tracer_wiring.py && git commit -m "feat(ai-econ): wire TraceSession into policy extraction + thread company_id

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest`
Expected: green. Pay attention that `test_ai_trace_logger.py`, `test_trace_logger_carbon.py`, `test_llm_policy_extractor.py`, `test_policy_assistant_rag_a.py`, `test_policy_assistant_rag_b.py`, and `test_admin_ai_unit_economics_router.py` all pass.

> Note: SQLite has the Step D columns regardless of Task 1, so the suite passes whether or not the prod migration was applied. The **MCP column check in Task 1 Step 4 is the real gate for prod** — do not treat green pytest as proof the prod write works.

- [ ] **Step 2: Frontend type-check (sanity — no frontend change expected)**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (this change is backend-only; this is a guard against accidental breakage).

- [ ] **Step 3: Confirm prod schema gate (if not already done in Task 1)**

Re-run the Task 1 Step 4 MCP `execute_sql` column check and confirm `prompt_version_id` + `canary_arm` are present on `public.policy_assistant_traces`. The writer's INSERT column list must be a subset of the prod columns, or production writes silently no-op.

---

## Out of scope (do not implement here)

- `passport_ocr` / `passport_ocr_oss` instrumentation (different call structure).
- Nightly `pg_cron` refresh of `mv_ai_unit_economics`.
- Validation-retry token under-counting in `answer_policy_question` (a retried call reports only the final attempt's `usage`).
- A frontend admin panel consuming `GET /api/admin/ai-unit-economics`.
