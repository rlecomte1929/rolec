# AIQ-1414 — Persistent Mobility Coordinator Agent — Architecture & Cost-Model Design

**Status:** 🔴 Red — awaiting human architecture gate · **Priority:** P1 · **Complexity:** Very High · **Product Area:** AI Layer
**Definition of Ready:** was "Needs info" — this document is the info.
**This document is a design + cost model only. No schema, no runtime code has been built.** Per the
ticket's own acceptance criteria, the architecture must be chosen and the per-session cost modeled
*before* any build commit, and production must pass a human gate.

> Decision requested from Romain at the gate: **pick the architecture (Option A vs Option B)** and
> approve moving to the phased build. The feature ships behind a default-**OFF** flag; production
> enablement is a *second*, separate human gate.

---

## 1. Executive summary

AIQ-1414 wants a **single persistent AI thread per relocation** that maintains context across weeks
(visa status, housing approvals, cost updates) — the "AI coordinator" that counters SIRVA's
human concierge at ~1/10th the cost.

The key finding from codebase recon is that **the "context across weeks" already lives in Postgres**
as typed, per-case state, and ReloPass today uses **zero** Claude Managed Agents / server-session /
compaction infrastructure — it is 100% standard Messages API + `tool_use` with prompt caching already
wired. This reframes the build: the persistent thread does **not** require an accruing server-side
session; its "memory" can be the authoritative Postgres state plus a small rolling summary,
re-assembled per call.

Two architectures are modeled below:

- **Option A — Full Claude Managed Agents** (the ticket's literal wording): one persistent Anthropic
  server session + container per relocation.
- **Option B — Stateful-Messages over Postgres** ("the memory is Postgres"): no server session; a
  per-relocation state row (rolling summary + recent turns) + a freshly-assembled context snapshot →
  one prompt-cached Messages call.

**Recommendation: Option B.** It delivers the same product UX ("one thread per relocation, context
across weeks") at **~1/10th the cost** (≈ **$1.20/relocation** vs Option A's **~$2–$5+ plus
unconfirmed per-session container cost**), with **bounded, predictable** per-interaction cost
regardless of relocation age, reusing all existing infrastructure, no beta operational surface, and
one-flag rollback. Managed Agents is retained as a documented future option only if a true
server-hosted tool-execution sandbox (autonomous code execution / browsing per relocation) is later
required — which a context-tracking coordinator does not need. Romain makes the final call at the gate.

---

## 2. Problem & product goal

- **Goal:** from offer-letter to settled-in, one AI thread tracks a relocation and can answer/act with
  full context at any point, without a human re-explaining state.
- **Strategic objective (ticket):** "same UX at ~1/10th the cost" vs a human single-point-of-coordination.
- **Hard constraints (ticket):** built on Claude; **PII masked via `pii_masker` before any LLM payload**
  (GDPR Art. 28/44); **model persistent-session pricing before committing architecture**; feature-flag
  gated (disable to roll back, no schema impact); **human gate before production**.
- **Out of scope here:** the 90-second superagent *demo* (tracked separately as #1413). This is the
  production build design.

---

## 3. Key finding — most "context across weeks" is already persisted

ReloPass already stores the evolving state of a relocation as **typed per-case rows**, read through a
deterministic assembler. A coordinator should **read this state**, not re-derive it in a chat log.

| Context the ticket names | Already persisted? | Where |
|---|---|---|
| **Cost updates** | ✅ first-class | `case_assignments.budget_limit/budget_estimated`, `rce.costs` (typed categories + payer), `case_budget_lines` |
| **Visa status** | ◑ inferred (no single `visa_status` column) | `roadmap_tracks(track_key='visa')`, `case_milestones`, `case_requirement_evaluations`, `immigration_cases.status` |
| **Housing approvals** | ◑ inferred (not a scalar flag) | `roadmap_tracks('settle'/'family')`, `case_milestones`, `rce.costs('HOUSING_VENDOR')` |

Supporting infrastructure already in place:

- **Read seam:** `backend/app/services/case_context_service.py` (`CaseContextService`) — deterministic
  assembly of the mobility-graph snapshot (cases, people, documents, policy rules, requirements,
  requirement evaluations). *"No AI."* This is what the coordinator reads each call.
- **Event spine (chronology to summarize):** `public.case_events` (immutable, `payload jsonb`,
  insert-only-as-self RLS), `case_notes` (HR free-text narrative), `rce.roadmap_audit_log`
  (append-only AI/specialist provenance), milestone transitions.
- **Existing per-case AI precedent:** `roadmap_generator.py` runs a one-shot LLM pass and **persists
  derived state back as structured rows** (`persist_generated_milestones` → `case_milestones`). The
  coordinator follows the same "read structured state → reason → write structured rows" shape, adding
  only a bounded rolling summary for conversational continuity.

**Consequence:** the only genuinely missing piece is a **durable, bounded conversational memory** per
relocation. Everything else (state, events, cost accounting, PII masking, flags) already exists.

---

## 4. Option A — Full Claude Managed Agents

**Design.** One Managed Agent (Coordinator persona, model, tools) created once; one **Session per
relocation** started at case creation and kept alive for the relocation's life (~12 weeks). Anthropic
runs the agent loop and hosts a per-session container; ReloPass exposes case state to the agent via
custom tools (or an MCP server) that read Postgres. Mid-session tool/instruction updates are supported.

**Cost model.**
- *Inference tokens grow with session age.* A session accumulates conversation + tool-result history.
  Even with server-side compaction (triggers around ~150K tokens), each turn re-processes the
  compacted prefix, so effective per-interaction input drifts upward (~5K early → 20–40K pre-compaction)
  over the relocation's life. Rough inference: **~$2–$5+ per relocation** on `claude-sonnet-4-6`.
- *Per-session infrastructure.* A container/session held open for ~12 weeks per relocation is a
  standing footprint. Managed Agents session/container pricing is **not a simple published per-token
  number** and must be confirmed directly with Anthropic before committing — so today this option
  **cannot cleanly satisfy the ticket's "model pricing before committing" gate.**
- *Operational surface (all net-new to ReloPass):* environments, session lifecycle (create / idle /
  archive / cleanup at scale), SSE event streaming, webhooks, custom-tool or MCP wiring to Postgres.
  Managed Agents is beta and **first-party API only** (not available on Bedrock/Vertex).

**Risk.** This is precisely the "session cost management gets complex at scale" risk the ticket flags,
compounded by unconfirmed per-session pricing and a large new operational surface.

**When Option A is the right call (future):** if the coordinator must *autonomously execute code,
browse, or run tools in a sandbox* per relocation (beyond reading ReloPass state and drafting
messages). A context-tracking + drafting coordinator does not need this.

---

## 5. Option B — Stateful-Messages over Postgres (RECOMMENDED)

**Design.** No server-side session. Per relocation:

1. A durable **coordinator-state row** (`ai_coordinator_sessions`, §10) holds:
   - `rolling_summary` — an LLM-maintained ≤ ~800-token narrative of the relocation's state and open
     threads,
   - `recent_turns` — the last N = 4–6 verbatim conversational turns,
   - `last_event_cursor` — the newest `case_events` timestamp/id folded into the summary.
2. On each interaction, assemble the prompt from:
   - the **prompt-cached** coordinator system/persona + `tool_use` schema (`cache_control: ephemeral`,
     already the pattern in `llm_client.py`),
   - a fresh **`CaseContextService`** snapshot (current typed state),
   - the `rolling_summary`,
   - **new `case_events`/`case_notes` since `last_event_cursor`**,
   - the user's turn — **all user/free-text content `mask_pii()`-ed** (§8).
3. One `claude-sonnet-4-6` Messages call with `tool_use` for structured actions (e.g. draft a message,
   flag a milestone, request a document). Derived state is persisted back as **structured rows**
   (roadmap_generator precedent), not left in a transcript.
4. Update `recent_turns`; when it exceeds N (or new events exceed M), **fold** into `rolling_summary`
   with a cheap Haiku call (§7).

**Why it's cheap and safe:** the per-interaction context is **bounded** (rolling summary + current DB
state = O(constant)), *independent of how long the relocation has been running* — the property that
eliminates the cost-explosion risk. It reuses ReloPass's entire existing stack; the only new persistent
state is one additive table.

**Cost model.** Assumptions: ~50 interactions/relocation over ~12 weeks; `claude-sonnet-4-6` $3/$15 per
1M; `claude-haiku-4-5` $0.80/$4 per 1M; system prefix prompt-cached (~0.1× read).

Per-interaction token budget (Option B):

| Component | Input tokens | Notes |
|---|---:|---|
| System/persona + tool schema | ~1,500 | prompt-cached → ~0.1× after first call |
| `CaseContextService` snapshot (masked, compact) | ~2,000 | changes across calls → mostly full price |
| Rolling summary | ~800 | bounded |
| New events since cursor | ~700 | bounded by fold threshold |
| User turn (masked) | ~200 | |
| **Input total** | **~5,200** | ~1,500 cache-read + ~3,700 full price |
| Output | ~800 | |

- Input cost ≈ (3,700 × $3 + 1,500 × $0.30) / 1e6 ≈ **$0.0116**
- Output cost ≈ 800 × $15 / 1e6 ≈ **$0.012**
- Summary fold (~every 5 interactions, Haiku, ~4K in / 0.5K out ≈ $0.0052) amortized ≈ **$0.001**/interaction
- **≈ $0.024 per interaction**
- **≈ $1.20 per relocation** (50 interactions). Routing routine turns to Haiku → **$0.70–$1.00**.
- **At 1,000 concurrent relocations ≈ ~$400/month** — linear and predictable.

---

## 6. Cost & risk comparison

| Dimension | Option A — Managed Agents | Option B — Stateful-Messages (recommended) |
|---|---|---|
| Per relocation (inference) | ~$2–$5+ (grows with session age) | **~$1.20** ($0.70–$1.00 with Haiku routing) |
| Per-session infra | Container held ~12 wks; **pricing unconfirmed** | **None** (stateless calls) |
| Cost predictability | Low (accruing context + infra TBD) | **High** (bounded per-interaction) |
| At 1,000 relocations | inference + standing container fleet | **~$400/mo**, linear |
| New operational surface | environments, sessions, SSE, webhooks, MCP/tools, archival (beta) | **None** — reuses Messages + caching + one table |
| Platform availability | first-party API only | first-party / Bedrock / Vertex (unchanged) |
| Satisfies "model pricing before commit" today | ✗ (infra price unconfirmed) | ✓ |
| Rollback | tear down sessions/agents | **flag OFF** (table inert) |
| Delivers the product UX | ✓ | ✓ |

---

## 7. TTL + summarization strategy (criterion #3)

- **Bounded conversational memory (rolling summary).** Keep the last N = 4–6 turns verbatim. When turns
  > N, or new `case_events` since `last_event_cursor` > M (≈ 8–10), **fold** the older turns + new
  events into an updated ≤ ~800-token `rolling_summary` via a cheap `claude-haiku-4-5` call:
  *"Given the prior summary and these new turns/events, produce an updated ≤800-token summary of this
  relocation's status and open threads."* This keeps per-interaction input O(constant).
- **State-freshness TTL.** Reuse `backend/app/services/staleness.py` `is_stale(last_updated, tier, now)`
  (`tier1_critical=30d`, `tier1_stable=60d`, `tier2=90d`, env-overridable). Refresh the cached
  `CaseContextService` snapshot / cited sources when stale so the coordinator never drifts from
  authoritative DB state.
- **Session lifecycle.** The state row is `active` while the relocation is; on `case_outcomes` terminal
  (`APPROVED`/`REJECTED`/`WITHDRAWN`) or `case_assignments.archived_at`, set `status='closed'`, freeze
  the summary, stop folds. Mirrors the `interview_sessions` lifecycle-timestamp pattern.
- **Cost circuit-breaker (optional).** Per-relocation monthly token budget tracked via `TraceSession`;
  on breach, downgrade routine turns to Haiku or pause proactive updates.

---

## 8. PII masking (criterion #4 — hard gate)

Every user-authored turn **and** any injected free-text (`case_notes` bodies, extracted document text)
passes through `backend/app/services/pii_masker.py` `mask_pii()` **before** it enters the Messages
payload. `mask_pii` is idempotent and redacts person names, email, IBAN, SSN/D-number/national ID,
passport, phone, and generic IDs. Structured typed fields (statuses, dates, amounts) are non-personal
and may pass as-is; **names/emails embedded in free-text are masked**. The system/persona template is
authored by us and is **not** masked. This mirrors the enforced pattern in
`policy_assistant_llm_client.py` (mask the user message, not the system). Never log raw input — use
`safe_log_text()`.

---

## 9. Feature flag, telemetry, rollback

- **Feature flag (criterion #5 support).** Gate the whole feature behind `RELOPASS_AI_COORDINATOR_ENABLED`
  resolved via `backend/app/services/feature_flags.py` `resolve_flag(key, env_default=False)` (DB flag →
  same-named env var → default **OFF**), mirroring the `RELOPASS_POLICY_LLM_DISABLED` kill-switch in
  `backend/core/llm_flags.py`. **Production stays OFF** until the second human gate. Disabling the flag
  is a full rollback — the additive table simply goes inert.
- **Telemetry / runtime cost validation (criterion #2, ongoing).** Wrap each interaction in
  `ai_trace_logger.TraceSession(feature_key="ai_coordinator", customer_id=<company>,
  session_id=<relocation_id>)`; call `record_llm_call(model, input_tokens, output_tokens, latency_ms)`
  with the SDK usage (including cache tokens); `flush()`. Cost is priced automatically via
  `relopass/llm/router.usd_cost` + `costs.yaml`, carbon via `ai_carbon_estimator`, and the existing
  `ai_unit_economics` rollup (`mv_ai_unit_economics`) gives **real per-relocation / per-customer cost**
  — this validates or corrects §5's model on pilot traffic **before** prod enablement. No new cost
  plumbing.

---

## 10. State schema (Phase 2 — one additive table)

Transplant the proven `interview_sessions` pattern (JSONB state + `SELECT … FOR UPDATE` + RLS + audit):

```sql
-- ai_coordinator_sessions — one durable coordinator memory row per relocation.
CREATE TABLE public.ai_coordinator_sessions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid NOT NULL,          -- anchor: the HR-surface relocation case
  employee_id       uuid,                    -- assignee (nullable pre-assignment)
  company_id        text NOT NULL,           -- tenant scope
  rolling_summary   text NOT NULL DEFAULT '',
  recent_turns      jsonb NOT NULL DEFAULT '[]'::jsonb,
  last_event_cursor timestamptz,             -- newest case_events folded into the summary
  model             text NOT NULL DEFAULT 'claude-sonnet-4-6',
  status            text NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed')),
  started_at        timestamptz NOT NULL DEFAULT now(),
  last_active_at    timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id)
);
ALTER TABLE public.ai_coordinator_sessions ENABLE ROW LEVEL SECURITY;      -- hard gate
REVOKE ALL ON public.ai_coordinator_sessions FROM anon;                    -- hard gate
-- RLS: employee owns their row (employee_id = auth.uid()); HR SELECT via case_assignments;
--      is_admin() full. (Model on case_milestones / interview_sessions policies.)
```

Writes take a row lock (`SELECT … FOR UPDATE`) and emit a canonical audit-log row (per the
`interview_sessions` service pattern). This is the **only** schema change, additive, and it follows the
CLAUDE.md hard migration gates (ENABLE RLS + policy + REVOKE anon) and migration-ledger discipline.

---

## 11. Phased build (AFTER the architecture gate — not done in this task)

- **Phase 0 (this deliverable):** design doc + cost model → **human gate on architecture.** No code.
- **Phase 1:** `CoordinatorContextBuilder` (read-only) — `CaseContextService` + event spine → masked,
  bounded context blob. Behind OFF flag, **no LLM egress**, unit-tested. (Proves the "read state, not
  chat log" thesis and the masking.)
- **Phase 2:** `ai_coordinator_sessions` migration + single-turn coordinator (masked, prompt-cached,
  `tool_use`) + rolling-summary fold + `TraceSession` telemetry. Flag OFF. Dual-registered router.
- **Phase 3:** persistence + event-triggered proactive updates + staleness refresh + cost
  circuit-breaker.
- **Phase 4:** minimal per-case coordinator-thread UI (reuse case-detail surfaces).
- **Phase 5:** pilot on seed cases → measure real per-relocation cost via `ai_unit_economics` →
  validate the model → **human gate #2** → enable the prod flag.

---

## 12. Open questions for the gate

1. **Architecture: Option A or Option B?** (Recommendation: B.)
2. **Coordinator model:** `claude-sonnet-4-6` for reasoning + `claude-haiku-4-5` for folds/routine
   turns? (Fable-5 is parked for cost.) Confirm the reasoning tier.
3. **Proactive vs reactive:** does the coordinator only respond to user turns, or also proactively
   surface updates on `case_events` (e.g. "your visa milestone just completed")? Proactive raises value
   *and* cost — the §5 estimate assumes a modest proactive cadence within the ~50-interaction budget.
4. **Anchor id:** confirm `case_id` (HR-surface relocation case) as the per-thread anchor given the
   documented case-table schism.
5. **Who talks to it:** employee, HR, or both (RLS already supports both). Affects UI scope (Phase 4).

---

## 13. Acceptance-criteria mapping

| Criterion | Addressed by |
|---|---|
| #1 Single session tracks an assignee across interactions without context loss | §5 (state row + rolling summary + CaseContextService) |
| #2 Per-session API cost modeled + documented before build commit | §5–§6 (model) + §9 (runtime validation via `ai_unit_economics`) |
| #3 TTL + summarization strategy defined | §7 |
| #4 PII masked via `pii_masker` before any LLM payload | §8 |
| #5 Human gate passed before production enablement | this gate + flag default-OFF + Phase-5 gate #2 |

---

## 14. References (reused files, `origin/main`)

- `backend/app/services/case_context_service.py` — deterministic state read seam
- `backend/app/routers/immigration_intake_interview.py` + `backend/app/services/immigration_service.py`
  + `supabase/migrations/20260518120000_immigration_core_tables.sql` (`interview_sessions`) — durable
  per-case JSONB-state pattern to transplant
- `backend/app/services/pii_masker.py` — `mask_pii()` / `safe_log_text()`
- `backend/app/services/llm_client.py`, `backend/app/services/policy_assistant_llm_client.py` — Messages
  API surface + prompt caching (`cache_control: ephemeral`)
- `backend/app/services/staleness.py` — `is_stale(last_updated, tier, now)` TTL primitive
- `backend/app/services/feature_flags.py` (`resolve_flag`) + `backend/core/llm_flags.py` — flag/kill-switch
- `backend/app/services/ai_trace_logger.py` (`TraceSession`), `ai_carbon_estimator.py`,
  `ai_unit_economics.py`, `relopass/llm/router.py` (`usd_cost`), `relopass/llm/costs.yaml` — cost telemetry
- `backend/app/services/roadmap_generator.py` — precedent: LLM reads state, persists structured rows
- Event spine: `case_events` (`20260321000000_case_events_phase1.sql`), `case_notes`
  (`20260701000000_case_notes.sql`), `rce.roadmap_audit_log`
