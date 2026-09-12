# ADR-003: Access-pattern structures for serving and corridors

**Status:** Accepted
**Date:** 2026-09-12
**Authors:** AI (CS50 Lec 5 grounding)
**Supersedes:** (none)
**Related:** [`docs/plans/cs50-lec5-ds-proposals-grounded-2026-09-12.json`](../../docs/plans/cs50-lec5-ds-proposals-grounded-2026-09-12.json), [`docs/corridors/README.md`](../../docs/corridors/README.md), [`docs/specs/requirements-engine-consolidation.md`](../../docs/specs/requirements-engine-consolidation.md)

---

## Context

CS50 Lecture 5's useful claim is not "use a trie / BST / linked list." It is: **the dominant operation dictates the structure.** ReloPass has four distinct access patterns. Mapping them to lecture structures that do not exist here (WorkspaceDB `requirement_facts`, Node.js `Map`, Redis hashes, `next_step_id` lists) would invent schema and runtime the product does not run.

This ADR records the mapping to what already serves.

## Decision

Pick the structure per **dominant operation**. Never force a flat list onto a graph, and never force a lecture structure onto an operation the graph is not.

| Access pattern | Dominant operation | Structure in ReloPass | Not this |
|---|---|---|---|
| Fetch-by-key | Load approved catalog rows for one destination × purpose | Indexed Postgres: `public.requirement_items` btree `(country_code, purpose, review_status)` via `crud.list_requirements`. Entry-visa checklist is a **separate** engine: `immigration_requirements` keyed corridor × visa_type. | In-memory Node/Redis hash keyed `{corridor}:{employee_type}:{fact_key}`. Table `requirement_facts` is not the served catalog. |
| Ordered traversal | Emit a case timeline in legal order | YAML DAG: `CorridorStep.prerequisite_step_ids` → Kahn in `scheduler._topological_order` / loader `_reject_prerequisite_cycles` at **load** time → `rce.steps` | Application sort of a flat array; a singly-linked `next_step_id` list |
| Dependency resolution | Insert a late step; refuse cycles; shift downstream dates | Same DAG. Insert = add a node + edges in pathway YAML. Diamond deps (IE→ES empadronamiento → NIE → housing) need multiple parents. | Linked list (cannot encode two parents) |
| Prefix discovery | Autocomplete / all corridors from origin FR | Linear scan of `corridor_registry.list_corridors()` (~13 YAML profiles, in-memory `_CACHE` dict keyed `ORIGIN_DEST`) | Trie. Revisit only if ~120 **served** corridors exist |
| Branching | EU vs third-country (and STA/family filters) | Data: pathway YAML `eligibility_logic.branches` (cited, `requires_all`, `verdict_on_pass`). Remaining code: `rules_engine.apply_rules`. `evaluate(corridor, case)` is still out of scope. | Binary search tree / `decision_nodes` table. Eligibility is not ordered-search. |

### Demand-pull (no over-allocation)

A corridor profile is a git directory `corridors/<ID>/`, not a DB row. New profiles must name a real anchoring case (`corridor.anchor`). Existing profiles are grandfathered. Served facts still fail closed: `requirements_builder` reads only `review_status = 'approved'`. Do not pre-create empty `requirement_items` for an unverified corridor, and do not add `anchor_case_id NOT NULL` to a table that is not the source of truth.

## Consequences

- Serving engines stay deterministic over curated, cited rows. A cache in front of `list_requirements` is allowed only after a measured p95 — it is a time–space trade-off, not a missing data structure.
- Cycle detection stays at **load**, not at serve (AIQ-1953).
- Follow-on (not this ADR): wire `evaluate(corridor, case)` and show the taken YAML branch in the HR UI.
- Lecture-derived proposal files must include a `grounding` object after a repo pass so names like `kg_corridors` / `requirement_facts` cannot be treated as schema.

## One-line rule

**Pick per dominant operation, not per familiarity, and not per the lecture's example type.**
