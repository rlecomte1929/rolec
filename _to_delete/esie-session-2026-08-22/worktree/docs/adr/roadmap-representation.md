# ADR: Roadmap representation & AI-plan persistence

- **Status:** Proposed (W1-1, BureauAI-audit remediation)
- **Date:** 2026-06-10
- **Deciders:** Romain (ratify)
- **Related:** AIQ-800 (roadmap projection), BureauAI evaluation (`docs/BUREAUAI_EVALUATION.md`,
  `docs/RELOPASS_RAG_ARCHITECTURE_AUDIT.md`), W1-2/W1-3 (this wave).

## Context

The RAG audit and codebase audit both flag a **roadmap-representation schism** as the #1
structural debt:

- `public.roadmap_tracks` / `public.roadmap_steps` exist (platform-redesign schema,
  `20260520000000_platform_redesign_schema.sql`, FK → `public.cases`) but **nothing writes them**.
- The **live** employee/HR roadmap is **projected at read time from `case_forms`**
  (`roadmap_projection.project_tracks`, served by `cases_read.get_case_roadmap_tracks`) — the
  AIQ-800 "Option B" decision. The persisted tables are effectively dead.
- The **AI roadmap generator** (`roadmap_generator.generate(...)`) returns a dict that is
  **never persisted**. So no generated plan is reproducible, auditable, diffable, or
  version-comparable — and a regeneration silently replaces what the employee saw.

Two different problems are easy to conflate:
1. **How the live roadmap UI is fed** (projection vs materialized tables).
2. **Whether AI-generated plans are durably recorded** (reproducibility/audit).

BureauAI's `AgentPlan` graph is a clean *contract* for (2); it is not a reason to change (1).

## Decision

1. **Keep Option-B projection as the live read path.** Do **not** resurrect or start writing
   `roadmap_tracks` / `roadmap_steps`. The projection from `case_forms` remains the source of the
   employee/HR roadmap view. Reviving the dormant tables would create a second, divergent
   representation and reintroduce the schism we are trying to close.

2. **Persist every AI-generated roadmap as an immutable plan version** (implemented in W1-2):
   new `case_plans` + `plan_versions(plan_json, prompt_version_id, retrieval_run_id, model, …)`
   keyed to `public.cases` (via `canonical_case_bridge()`). `plan_json` stores the full generated
   roadmap using BureauAI's `AgentPlan`-shaped contract as the design reference. Versions are
   append-only; a regeneration writes a new version rather than overwriting.

3. **Record the retrieval that produced each plan** (W1-3): `retrieval_runs` +
   `retrieval_run_chunks`, linked from `plan_versions.retrieval_run_id`, so any shown plan can be
   traced to its sources and replayed by evals.

## Consequences

- **Positive:** reproducibility/audit/versioning without disturbing the working UI; the dead
  tables stay dead (a later, separate decision can retire them); plan history enables diffing and
  "why did this change" answers; foundations for HR provenance (W2-5) and eval replay (W3-4).
- **Negative / accepted:** `roadmap_tracks`/`roadmap_steps` remain in the schema unused (cosmetic
  debt; out of scope here). The projection and the persisted `plan_json` are two views of the
  roadmap — the projection is canonical for *display*, `plan_versions` is canonical for *the AI
  output of record*. They must not be wired to silently overwrite each other.

## Alternatives considered

- **Option A — materialize into `roadmap_tracks`/`roadmap_steps`.** Rejected: writes tables the
  live read path ignores (would need a parallel cutover of `cases_read`), higher blast radius, and
  doesn't itself give versioning/provenance.
- **Do nothing.** Rejected: leaves AI plans unrecorded and unauditable — the exact gap the audit
  calls out.
