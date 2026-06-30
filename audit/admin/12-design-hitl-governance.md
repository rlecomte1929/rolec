# D-HITL/Governance — admin AI-governance control panel

**Closes:** C-01, C-02, C-03, H-01, H-02, H-03 (+ supports the July-1 gate flip). **Goal (G2/G5):** behavior-shaping AI levers are visible, adjustable in-app with guardrails, gated for critical changes, and reversible (kill-switch) — instead of invisible env vars and silent auto-mutations.

## Problem
Everything that shapes AI behavior is env/code only and invisible to the admin:
- Flags: `POLICY_RAG_GROUNDEDNESS_GATE` (+ `_MIN_SCORE`), `POLICY_RAG_RERANK`, `SUPPLIER_LEARNED_WEIGHTS` — env, default OFF, flip = redeploy.
- Weights: `recommendations/weights.py::WEIGHTS` (code literal); learned overrides written only by an offline CLI.
- Thresholds: `rag_eval_reports.py` `MetricSpec` constants.
- Auto-mutation: source-reliability recompute runs **daily off rejected AI feedback with no approval** (`source_reliability_service.py` + `reliability-recompute-daily` cron).

## Design
1. **Config store + resolver (M):** a `platform_settings` table (`key, value_json, updated_by, updated_at`, RLS admin-write/service-read) read by a resolver that the existing code consults with **env → DB → default** precedence (so today's env behavior is the fallback; no behavior change until an admin sets a value). Replace the direct `os.environ.get` reads in the gate/rerank/weights resolvers with `get_setting(...)`.
2. **AI-controls panel (C-01/H-02, M):** admin UI to view + toggle the flags and set `min_score`, each change **gated** (confirm + reason) and **audited** (`audit_logs`, `new_value.event='ai_setting_changed'`). This is what lets the groundedness gate be flipped *from the app* (with the gate-impact number shown inline — see O-02/O-04) instead of env+redeploy.
3. **Kill-switches (H-03, S):** a prominent per-feature "disable now" for each AI path (gate, rerank, learned-weights, LLM answering) that forces the safe default immediately.
4. **Weights & thresholds (C-02/C-03, M):** read-only display of current `WEIGHTS` + learned overrides + `MetricSpec` thresholds; gated edit for thresholds and a gated per-segment weight override (writing `supplier_ranking_weights` via an endpoint instead of CLI-only).
5. **Gate the daily reliability recompute (H-01, M):** change `reliability-recompute-daily` from auto-apply to **propose → admin review/approve** (a diff of source-trust deltas in the admin panel), or at minimum a kill-switch + an audit row per recompute. No silent trust mutation.

## Safeguards
Every change audited with actor + reason; every lever has a documented safe default; kill-switches force the default with one click; changes are reversible. Pairs with the observability work (show gate-impact / weight-drift / eval-vs-threshold next to each control).

## Reuse
`services/policy_assistant_rag_engine.py` (gate read), `services/policy_chunk_retriever.py` + `policy_rerank.py` (rerank read), `recommendations/weights.py` + `ranking_weights_store.py`, `rag_eval_reports.py` (thresholds), `source_reliability_service.py`, `backend/eval/gate_impact.py` + `scripts/eval_gate_impact.py` (inline impact), `audit_logs` (id-less `new_value.event` pattern), `admin_prompts.py` (a working precedent for an admin-editable AI knob).

## Acceptance metrics
AI levers controllable in-app: 0 → ≥3 flags + min_score + thresholds. Every change audited (test). Kill-switch forces safe default (test). Source-reliability recompute no longer auto-mutates without approval/kill-switch. Env precedence preserved so default behavior is unchanged until an admin acts.
