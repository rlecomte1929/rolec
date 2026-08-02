# AI-decision audit-trail coverage audit (AIQ-1694 · Subtask 1)

_Generated 2026-07-26. Read-only analysis — no code/schema change in this subtask._

Purpose: before extending `ai_decisions` (AIQ-1694), map which AI-recommendation paths already
log and which don't, and pin the exact schema delta — so the migration (Subtask 2), the write
helper (Subtask 3), and the wiring (Subtask 4) execute against facts, not guesses. This document
**is** the parent's criterion 5 ("extend the existing `ai_decisions` table, don't duplicate").

**No regulatory/compliance-status claim is proposed anywhere.** This is engineering/observability
hardening that supports the existing verifiable controls (human review, decision logging, PII
masking). Per `docs/compliance/AIQ-1487_eu_ai_act_assessment.md` our AI is limited-risk.

---

## 1. Current state (what exists)

### `ai_decisions` table — migration `20260527000000_ai_decisions_human_oversight.sql`
Columns: `id, created_at, updated_at, actor_id, company_id, feature, recommendation_id,
ai_output (JSONB), decision, reason, outcome`. RLS enabled with company-scoped policies.

- `ai_output` = the AI recommendation **as shown to the overseer**.
- `decision` / `reason` / `outcome` = the **human** accept / override / reject.
- **There is no column for the INPUT context that produced the recommendation.** ← gap (a).

### Write path — `backend/app/routers/ai_decisions.py`
- `POST /api/ai/decisions` (`create_ai_decision`, line 123): the **only** INSERT site in the whole
  codebase (verified: `grep "INSERT INTO ai_decisions"` → this file only). It fires **when a human
  acts**, not when the AI produces the recommendation.
- `GET /api/ai/decisions` (`list_ai_decisions`, line 219): company-scoped read view.

### Separate system — `backend/app/services/ai_trace_logger.py`
Per-request trace for the **Policy Assistant** pipeline (`policy_assistant_traces` table): model,
tokens, latency, PII-safe (query hashed, never stored raw). Used by `policy_assistant_rag_engine`,
`coordinator_agent`, `llm_policy_extractor`, `rag_roadmap`, `autopilot_*`, `feedback_to_gold`,
`hr_analytics`, `ai_replay_store`. This gives **observability** for those paths, but it is not the
**decision audit** and does not link a human accept/override/reject.

---

## 2. Coverage matrix — recommendation surfaces

Scope = **AI outputs presented to a human overseer who can accept / override / reject** (the
Art. 14 human-in-the-loop surfaces). Internal LLM utilities that produce derived data (not an
overseer-facing recommendation) are out of scope for the decision audit — see §4.

| Recommendation surface | File | Writes `ai_decisions`? | Has `ai_trace`? | Verdict |
|---|---|---|---|---|
| Supplier recommendations (movers/banks/schools/…) | `backend/app/recommendations/engine.py` (`recommend`, returns at `:380`) | ❌ (0 writes) | ❌ | **UNCOVERED** — no production record; a human override would have nowhere linked to write input/output |
| Roadmap / relocation plan | `backend/app/services/roadmap_generator.py` | ❌ (0) | ❌ | **UNCOVERED** (HR review gate exists in UI, but no decision record) |
| Mobility coordinator | `backend/app/services/coordinator_agent.py` | ❌ (0) | ✅ trace | **PARTIAL** — traced for observability, but no decision audit |
| Exception / precedent insight | `backend/app/services/precedent_insight_service.py` | ❌ at production; only mints the `recommendation_id` (line 151) so a **human action** can link (feature `exception_insight`) | ❌ | **PARTIAL** — human decision can be captured, but the produced input/output is not |
| Dossier suggestions | `backend/app/services/dossier_suggestion_service.py` | ❌ (0) | ❌ | **UNCOVERED** |
| Policy Assistant answer | `backend/app/services/policy_assistant_rag_engine.py` | ❌ | ✅ full trace (model+tokens) | **TRACE-COVERED** — it's a grounded/cited answer, not a curate-list; lowest priority for `ai_decisions` (already observable) |

**Bottom line:** the write side is **human-action-only**. Every recommendation surface is missing a
**production-time** record linking the (masked) input + the model output. The human-decision half
already exists via `POST /api/ai/decisions`.

---

## 3. Uncovered paths to wire (input for Subtask 4)

Wire `record_ai_recommendation()` (Subtask 3) at production time in, in priority order:
1. `recommendations/engine.py` — `recommend()`, just before the `RecommendationResponse` return
   (`:380`). Feature key e.g. `supplier_reco:<category>`. Highest value (most overseer overrides).
2. `services/roadmap_generator.py` — when a roadmap/plan is generated. Feature `roadmap`.
3. `services/coordinator_agent.py` — when the coordinator emits a recommendation/action. Feature
   `coordinator`. (Already traced; add the decision record.)
4. `services/precedent_insight_service.py` — write the produced input/output at generation, so the
   existing human-action link is complete. Feature `exception_insight`.
5. `services/dossier_suggestion_service.py` — feature `dossier_suggestion`.

Policy Assistant is deferred (trace-covered; revisit only if a decision surface is added).

---

## 4. Out of scope (internal LLM utilities — not overseer recommendations)

Not decision surfaces; produce derived data, extraction, verification, or embeddings. Some already
carry `ai_trace`. Do **not** wire these to `ai_decisions`:
`factual_verifier`, `immigration_answer_verifier`, `immigration_contradiction_detector`,
`ocr_passport_extractor` / `receipt_field_extractor` / `requirement_fact_extractor`,
`llm_policy_extractor` / `policy_canonical_extraction` / `policy_assistant_embedder`,
`catalog_scraper`, `prospect_enrichment_service`, `rce_entity_resolution_ai`, `city_activities_service`,
`briefing`, `feedback_triage` / `feedback_task_engineer`, `setup_help_engine`, `nl_policy_builder`,
`work_item_planner`.

---

## 5. Agreed schema delta (input for Subtask 2)

Add to `ai_decisions` (additive, nullable — no backfill; existing RLS inherited):

| Column | Type | Purpose |
|---|---|---|
| `input_context` | `JSONB` | The **PII-masked** input that produced the recommendation (criteria/case fields). Masked at write via `mask_pii` (Subtask 3). |
| `model_name` | `TEXT` | The model/provider that produced it (e.g. `claude-haiku-4-5`), or `rule-based` for the recs engine. |
| `produced_at` | `TIMESTAMPTZ` | When the recommendation was produced (distinct from `created_at` of a human action). |

**Write model (recommended):** production-time **INSERT** with `decision = 'produced'` (a new
sentinel, keyed by `feature` + `recommendation_id`), which the existing `POST /api/ai/decisions`
then **UPDATEs** to the human decision (accept/override/reject) — or inserts a second row if the
UI's contract is simpler to keep. Subtask 3 should upsert on `(feature, recommendation_id)` so the
produced row and the human decision converge on ONE record. Confirm the UI's create-vs-update
expectation when building Subtask 3; keep the `POST` endpoint's external contract unchanged.

**Do not** create a new table — this extends `ai_decisions`, satisfying criterion 5.
