# AIQ-1976 — the timeline is already dynamic, and the JSON endpoint already exists

**Phase 2.5 falsification, 2026-08-19.** Premise: **Partial.** Outcome: **no code.**

The task asks to (a) expose corridor requirements as versioned JSON, and (b) render the
compliance timeline from it so new corridors need no hand-written markup. Two of its three
claims are already satisfied in `main`. The third is real, but it is a different change in a
different file than the task describes, and it runs into a documented design boundary.

---

## Claim 1 — "expose corridor requirements as versioned, cacheable JSON (corridor × employee-type → requirements[])"

**Already exists.** `GET /api/public/corridor-requirements?from=&to=&employee_type=` is live:

```
keys:          corridor, employee_type, purpose, nationality_class, requirements,
               waived_for_assignment_type, coverage_note, disclaimer, generated_at
per-item keys: key, label, description, timing, non_obvious, category, source
```

Probed ES→IE on 2026-08-19: **14 items, 14/14 carrying a non-empty `source` URL.** It is exactly
the corridor × employee-type → requirements[] shape the Expected Output describes, and it
already carries the source links.

## Claim 2 — "new corridors require hand-written markup"

**Refuted.**

| component | lines | hardcoded corridor/country strings |
|---|--:|--:|
| `frontend/src/features/timeline/RelocationTimeline.tsx` | 1175 | **0** |
| `frontend/src/features/timeline/RelocationTaskTracker.tsx` | 582 | **0** |

`RelocationTimeline`'s own header states its data source: `GET /api/relocation-plans/{id}/view`,
with *"Phase grouping: from API phases (not milestone_type prefix inference)"* — a decision
recorded as approved on 2026-05-13 under AIQ-3-C / AIQ-3-D. `CaseTimeline.tsx` is a four-line
backward-compatible re-export.

A new corridor requires no markup today. There is also no component named "compliance timeline"
anywhere in the repo — the term does not appear in the codebase.

## Claim 3 — "each timeline item shows status + source link"

**Confirmed gap — but not where the task points.**

- The timeline renders **no** source link (no `source_url` / `href` per item).
- `/api/relocation-plans/{id}/view` carries **no** source field at all.

The task's `Files to Touch` names *"backend/app/routers/ (corridor JSON resource)"*. That resource
is not the problem — it already has sources. The timeline consumes a **different** endpoint, and
that one is the one missing provenance.

And the bridge between them is deliberately narrow.
`relocation_plan_view_service` calls `enrich_milestones_with_requirements`
(`roadmap_requirement_copy.py:137`), whose contract says:

> "Only `title` and `description` are ever touched. status / owner / target_date [...]"

That restriction is not an oversight. The same module documents why milestone rows are fragile:
`persist_generated_milestones` deletes every milestone except `source="service"`, so a
`source="requirement"` row would be wiped by the next AI regeneration. Widening the enrichment to
carry citations means engaging with that, not just adding a field.

## Why no code was written

Implementing claim 3 under this task would mean:

1. extending the plan-view DTO with a source/citation field,
2. widening `enrich_milestones_with_requirements` past a boundary its own docstring draws,
3. rendering it in a 1175-line component,

— all on a task whose stated premise ("new corridors need hand-written markup") is false, and
whose named target file is already correct. That is a different, narrower piece of work and it
deserves its own brief, with the regeneration hazard understood up front.

Per the dev-queue standard: a task whose premise is refuted is complete when the disproof is
recorded. Inventing a substitute problem so the task ships code is the failure mode this step
exists to prevent.

## Recommendation

1. **Close AIQ-1976** as already-satisfied for claims 1 and 2.
2. **Open a narrow follow-up** for claim 3: *"Carry requirement provenance onto relocation-plan
   timeline items"* — scoped to the plan-view DTO + `roadmap_requirement_copy`, with the
   `persist_generated_milestones` wipe hazard named in its constraints.

---

### Evidence index (all 2026-08-19)

| claim | check |
|---|---|
| corridor JSON exists with per-item source | live GET, 14 items, 14/14 sourced |
| timeline has no hardcoded corridor markup | `grep -c` on both components → 0 |
| timeline data source | `RelocationTimeline.tsx` header, `/api/relocation-plans/{id}/view` |
| timeline renders no source link | grep for `source_url\|href` → none |
| plan-view carries no source | grep on `relocation_plan_view_service.py` → none |
| enrichment is title/description only | `roadmap_requirement_copy.py:145` |
| no "compliance timeline" component | repo-wide grep → no match |
