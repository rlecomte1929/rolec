# Finish Epic B (TS type-safety) via Conductor — dispatch guide

The last and largest LINT warn-backlog epic: drive the 8 TypeScript type-safety rule families to **0** across
`frontend/src` and re-promote each `warn` → `error` in `frontend/eslint.config.js`, so any new untyped data
flow fails CI.

- `SHARED.md` — read-first brief: Definition of Done, setup, gotchas, and the typing patterns.
- `CONTENT-TASKS.md` — the area sweeps (parallel-safe) + the dedicated `client.ts` track.
- `CONFIG-AND-REPROMOTION.md` — the test-relax task (do first) + the gated re-promotions (do last).

## Scope (2026-06-27)
**873 violations / 131 files.** `no-explicit-any` 172, `no-unsafe-member-access` 168, `no-unsafe-return` 166,
`no-base-to-string` 139, `no-unsafe-assignment` 133, `no-unsafe-argument` 69, `restrict-template-expressions`
18, `no-unsafe-call` 8. Concentrated in `api/client.ts` (229), `pages/admin` (118), `features/policy` (91),
`pages/employee` (52), `features/platform-v2` (44), `features/policy-builder` (43, incl. tests),
`components` (~50).

## ⚠️ This epic is bigger and riskier than Epic C
Epic C was mechanical a11y attribute edits (a one-day fan-out). Epic B is **type refactoring** — `tsc` is the
hard gate, agents must reuse existing domain types, and progress is measured by **area count → 0** (the rules
stay `warn`, so `eslint src` 0-errors doesn't move). Realistically this is **several waves over days**, and
the re-promotions only happen once an entire family is 0 — far out. Dispatch in waves and re-measure between.

## How to dispatch (what YOU paste into Conductor)
**Step 0 — TASK RELAX-TESTS first** (shrinks the gate ~50). One agent:
> Read `docs/epic-b/SHARED.md` and `docs/epic-b/CONFIG-AND-REPROMOTION.md`, then execute **TASK RELAX-TESTS**.
Let it merge before measuring area counts.

**Wave 1 — area sweeps, parallel.** Create one agent per area and paste (swap the task name):
> Read `docs/epic-b/SHARED.md` in full, then execute **TASK ADMIN** exactly as specified in
> `docs/epic-b/CONTENT-TASKS.md`. Obey the Definition of Done (especially `tsc --noEmit` = 0). Stay strictly
> within that area's files. Reuse existing domain types — do not invent shapes. Report the PR number and
> before/after count.

Areas: `TASK CLIENT` (dedicated — the only one that can collide; don't run a second client agent),
`TASK ADMIN`, `TASK POLICY`, `TASK EMPLOYEE`, `TASK PLATFORM`, `TASK POLICY-BUILDER`, `TASK COMPONENTS`,
`TASK MISC`. All except CLIENT touch disjoint files → safe in parallel. They self-merge on green.

**Wave 2 — re-promotions, sequential, gated.** Only after a family is 0 across all `src` (measure with the
command in CONTENT-TASKS): run `R-EXPLICIT-ANY`, then `R-BASE-TO-STRING`, then `R-UNSAFE` (each its own agent,
one at a time, since they share `eslint.config.js`). Because the families are large, expect to repeat Wave 1
(more area passes / split the big files) until each family hits 0 before its re-promotion can fire.

## §E — Epic B DONE
```
grep -nE "@typescript-eslint/(no-unsafe|no-explicit-any|no-base-to-string|restrict-template)" frontend/eslint.config.js
npx eslint src   # 0 errors
```
Every target family reads `'error'` in the LINT-3-close block (the test-file override may keep them `'off'`),
and `eslint src` = 0 errors → update memory + close the Notion TS-type-safety epic. That completes all three
LINT warn-backlog epics.
