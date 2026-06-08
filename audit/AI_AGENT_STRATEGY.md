# AI Agent Strategy — committed decisions

This is the decision record for ReloPass's AI stack (trace/eval substrate, embedding
model, PII framework, etc.). The AI Work Queue's "Decide and commit …" tasks
(AI-W1.x) record their outcome **here, in §5**, with a date and a contingency, so the
downstream build tasks can proceed against a fixed choice.

Sections §1–§4 (landscape, flywheels, tool survey) live in the companion analysis
`audit/AI_TOOLS_AND_FLYWHEEL.md`; this file is the durable, dated **decision log**.

---

## §5 — Committed decisions

| # | Decision | Choice | Date | Owner | Contingency / revisit-if |
|---|---|---|---|---|---|
| D1 | Trace / eval substrate (AI-W1.1 / AIQ-571) | **Langfuse EU Cloud** | 2026-06-08 | Romain | Migrate to self-hosted Langfuse if monthly cost exceeds the agreed ceiling at Cohort-2 trace volume, or if EU-residency terms change. |
| D2 | Embedding model (AI-W1.2 / AIQ-572) | _pending — bench BGE-M3 vs Cohere v3 (Bedrock FRA) on the 200-name fixture before committing_ | — | Romain | — |

### D1 — Trace / eval substrate: Langfuse EU Cloud

**Decision (2026-06-08):** commit to **Langfuse EU Cloud** as the single trace/eval
substrate. All `agent_runs` / LLM calls flow through it (Flywheels 1 + 3).

**Why:** EU data residency (host `https://cloud.langfuse.com`), open data model
(exportable — low lock-in), OpenTelemetry-compatible, low setup effort vs self-host.
Reverses the earlier Weave recommendation (dropped: US-default region, reported
production latency, proprietary format). Supersedes the optional LangSmith forwarding
(P5-8) as the committed substrate.

**Wiring (this repo):** `backend/app/services/llm_tracing.py` records every
`llm_client` call as a Langfuse *generation*, **fail-soft and env-gated** — active only
when `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are set; a silent no-op otherwise, so
it never breaks or slows an LLM call. Host defaults to the EU region; override with
`LANGFUSE_HOST`. Dependency: `langfuse>=2.0,<3.0` (requirements.txt).

**Provisioning (operator):** keys are set in Render env (dev + prod); the DPA is
reviewed + filed. Verify with a single `llm_client` call and confirm the generation
appears in the Langfuse dashboard.

**Contingency:** if EU-Cloud cost exceeds the agreed €/month ceiling at Cohort-2
volume, migrate to self-hosted Langfuse (same SDK + data model → low-friction).
