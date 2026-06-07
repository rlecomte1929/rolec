# Anthropic / Claude API Credit Audit — June 2026

**Task:** AIQ-827 (DIGEST-1) · **Date:** 2026-06-07 · **Trigger:** Anthropic's June 15, 2026 billing split (Agent SDK / Claude Code / agent workloads move off flat-rate subscription onto a separate metered credit pool; 12–175× effective price increase per unoptimized agent workload).

**Companion data:** [`anthropic_credit_audit_2026-06.csv`](./anthropic_credit_audit_2026-06.csv) — per-call-site table.

---

## TL;DR — the headline finding

> **ReloPass product runtime has ZERO exposure to the June 15 agent-credit-pool split.**

Every Claude call in the codebase uses the **standard Messages API with an API key** (`anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(...)`). There is **no Claude Agent SDK, `ClaudeSDKClient`, or `claude_agent_sdk`** usage anywhere in `backend/` or `frontend/`. Standard API-key billing is already metered at API rates and is **not** what the June 15 change re-prices.

**The only thing affected by June 15 is developer tooling** — the team's use of **Claude Code** (including this dev-queue automation). That is an internal dev-cost line, not product COGS, and should be tracked against the new Pro/Max credit pool separately.

**Action required before June 15: none for product.** Recommended (cost hygiene, not deadline-driven): turn on prompt caching + Haiku downgrades (below) — they cut burn ~40–60% whenever pilot traffic starts.

---

## Inventory — every Claude call site

9 live call paths, all **standard Messages API**, model **`claude-sonnet-4-6`** (with `claude-haiku-4-5` already wired as a fallback in the policy-assistant client). Full per-call detail (tokens, volume, cost) is in the CSV.

| # | Call site | File | API type | Agent SDK? |
|---|---|---|---|---|
| 1 | Policy Assistant RAG (workhorse) | `policy_assistant_llm_client.py:98` | Messages API | No |
| 2 | Factual verifier | `factual_verifier.py` (→ #1) | Messages API | No |
| 3 | Roadmap generator | `roadmap_generator.py` (→ #1) | Messages API | No |
| 4 | Immigration answer engine | `immigration_answer_engine.py:34` (→ #1) | Messages API | No |
| 5 | RAG pipeline | `rag_pipeline.py` (→ #1) | Messages API | No |
| 6 | OCR passport extraction | `ocr_passport_extractor.py:328` → `llm_client.claude_complete` | Messages API + tools | No |
| 7 | Policy document extraction | `llm_policy_extractor.py:294` | Messages API + tools | No |
| 8 | Analytics NL query | `analytics_query.py:169` | Messages API | No |
| 9 | Support ticket triage | `support.py:433` | Messages API | No |

Items 2–5 route through the **`policy_assistant_llm_client.LlmClient`** workhorse (#1) — the single highest-volume path (user-facing chat). #6 routes through the canonical **`llm_client.claude_complete`** async wrapper.

**Not a live caller:** `backend/relopass/llm/router.py` (the `gpt-4o-mini → claude-3-7-sonnet` field-extraction escalation table) is referenced only by `ai_trace_logger.py` for its `usd_cost` helper — it is config/cost metadata, not an active API path.

---

## Burn estimate

`agent_runs` (the in-repo per-call token/cost log written by `ai_trace_logger`) is **currently empty (0 rows)** — the platform is pre-pilot, so there is no empirical usage yet. The CSV figures are therefore a **clearly-labeled pilot-scale estimate** using per-call token sizes read from the prompts/`max_tokens` and assumed monthly call volumes.

- **Pilot-scale estimate: ≈ $25 / month** (all Sonnet, no optimizations).
- Pricing source: the in-repo table in `policy_assistant_llm_client.py` — Sonnet $3/$15 per Mtok, Haiku $0.80/$4 per Mtok.

> **Authoritative number once pilot traffic flows:** query `public.agent_runs` (`sum(cost_usd)`, `sum(input_tokens)`, `sum(output_tokens)` grouped by `model`, `node_type`). **Prerequisite:** confirm the 9 call sites actually write to `agent_runs` — it is empty today, which overlaps with queued task **AIQ-589** ("verify classifier traces appear in Langfuse and `agent_runs`"). Until that is wired, there is no empirical burn signal.

---

## Optimization opportunities (additive; ~40–60% burn reduction)

None are deadline-driven (no Agent SDK exposure), but all are cheap wins before scale:

1. **Prompt caching — HIGHEST value, currently unused.** `grep` finds **no `cache_control`** anywhere. The RAG/immigration/roadmap paths resend large, stable system prompts + retrieved corpora on every call. Marking the system block (and stable retrieved context) with `cache_control: ephemeral` drops cached-input reads to ~0.1× input price. Biggest impact on #1, #4, #7.
2. **Batch API — unused.** Non-interactive paths (#7 policy-doc extraction, #6 OCR, #2 factual verification) tolerate async and qualify for the **50% Batch discount**.
3. **Haiku downgrade — partially wired.** #8 (analytics NL) and #9 (support triage, already capped at `max_tokens=512`) are simple classification/summarization → move default to `claude-haiku-4-5` (~3.75× cheaper). #1 already has a Haiku fallback; consider Haiku-first with Sonnet escalation for low-complexity questions.
4. **De-dup overlap.** #5 (`rag_pipeline`) and #1 (policy assistant) overlap; confirm they aren't double-calling on the same request.

---

## Recommendation for the June 15 deadline

| Question | Answer |
|---|---|
| Does product runtime hit the 12–175× agent re-pricing? | **No** — 0 Agent SDK call sites; all standard Messages API. |
| Anything that *must* change before June 15? | **No product change required.** |
| What *is* affected? | **Claude Code dev usage** (incl. this automation) → moves to the Pro/Max credit pool. Track separately as a dev-cost line. |
| Best cost hygiene before pilot scale? | Prompt caching (#1) + Batch (#2) + Haiku downgrades (#3). |
| Where will the real number come from? | `public.agent_runs` once it's wired (AIQ-589) and pilot traffic starts. |
