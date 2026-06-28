# Finish Epic C (accessibility) via Conductor — dispatch guide

This folder is the **self-contained brief** for finishing Epic C: drive the remaining accessibility lint
rules to **0** across `frontend/src` and re-promote each `warn` → `error` in `frontend/eslint.config.js`,
so any new accessibility violation fails CI from then on.

- `SHARED.md` — the system brief every agent must read first (Definition of Done, setup, hard-won gotchas,
  fix patterns, the entities script).
- `CONTENT-TASKS.md` — the **7 content tasks** (parallel-safe; disjoint files).
- `REPROMOTION-TASKS.md` — the **3 re-promotion tasks** (sequential; gated).

## Current state (2026-06-27)
Already done + locked to `error`: `label-has-associated-control`, `no-redundant-roles`,
`interactive-supports-focus`, `aria-role`, `no-noninteractive-element-to-interactive-role`. Remaining:
`no-clickable-div` (~42 elements non-deferred + 66 in the 3 deferred files), `no-unescaped-entities` (~62),
`no-autofocus` (1, inside HrTeamList). The `click-events` / `no-static` / `no-noninteractive` ride-alongs
clear automatically as `no-clickable-div` is fixed (same elements).

## How to dispatch (what YOU paste into Conductor)
**Wave 1 — create 7 Conductor agents, one per content task, and paste this one line into each** (swap the
task id): 

> Read `docs/epic-c/SHARED.md` in full, then execute **TASK ENT** exactly as specified in
> `docs/epic-c/CONTENT-TASKS.md`. Obey the Definition of Done in SHARED.md. Stay strictly within TASK ENT's
> file scope. Report the PR number and before/after rule count when done.

Repeat with `TASK CLK-1`, `TASK CLK-2`, `TASK CLK-3`, `TASK DEF-1`, `TASK DEF-2`, `TASK DEF-3`.
All 7 run in parallel safely (each works in its own git worktree on disjoint files).

**During Wave 1:**
- `ENT`, `CLK-1`, `CLK-2`, `CLK-3` self-merge on green.
- `DEF-1`, `DEF-2`, `DEF-3` open a PR but **must NOT auto-merge** — you (or a Playwright run) browser-verify
  keyboard + layout first, then merge. These are interactive tables / mobile nav / the policy-builder canvas.

**Wave 2 — re-promotions (sequential, you trigger each after its gate):** paste, one at a time:

> Read `docs/epic-c/SHARED.md` and `docs/epic-c/REPROMOTION-TASKS.md`, then execute **R-ENT** exactly.

Order + gates: **R-ENT** (after ENT merged) → **R-AUTOFOCUS** (after DEF-1 merged) → **R-CLICK** (after all
6 clickable PRs — CLK-1/2/3 + DEF-1/2/3 — are merged). R-CLICK is the final lock-in.

## §E — Epic C "DONE" — how to measure overall success (run after R-CLICK merges)
```
# 1. every a11y rule + entities reads 'error' in the LINT-3-close block (zero 'warn'):
grep -nE "jsx-a11y|no-clickable-div|no-unescaped-entities" frontend/eslint.config.js
# 2. the codebase is clean:
npx eslint src        # 0 errors
```
Then: confirm all PRs merged to `main`; `GET /health` on prod green after Render redeploys; update memory
`project_lint_warn_backlog_epics.md` (Epic C → DONE) and close the Notion Accessibility epic.

At that point accessibility is enforced by the blocking CI gate.
