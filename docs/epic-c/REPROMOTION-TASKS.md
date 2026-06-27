# Epic C — RE-PROMOTION TASKS (Wave 2 — SEQUENTIAL, run one at a time)

> Read `docs/epic-c/SHARED.md` first. These tasks flip a rule from `'warn'` to `'error'` in the
> "LINT-3-close" block of `frontend/eslint.config.js`. They ALL edit the same file, so **never run two in
> parallel**, and each may run **only after its gate is met** (the rule is already 0 on merged `main`).

## Procedure (identical for each)
1. Worktree off `origin/main` + `npm ci` (per SHARED). Branch `fix/epic-c-<r>`.
2. In `frontend/eslint.config.js`, change the target rule(s) from `'warn'` to `'error'`.
3. **VERIFY** `npx eslint src` = **0 errors** (this proves the rule is truly drained — if it isn't 0, the
   gate wasn't met; STOP and report). Then `npm run build` + `npx vitest run` green.
4. Commit `fix(a11y): re-promote <rule> to error (Epic C)`, PR, merge.

## R-ENT  — gate: TASK ENT merged AND `react/no-unescaped-entities` = 0 on main
Flip `'react/no-unescaped-entities': 'warn'` → `'error'`.

## R-AUTOFOCUS  — gate: DEF-1 merged AND `jsx-a11y/no-autofocus` = 0 on main
Flip `'jsx-a11y/no-autofocus': 'warn'` → `'error'`.

## R-CLICK  — gate: CLK-1, CLK-2, CLK-3 AND DEF-1, DEF-2, DEF-3 all merged, AND all four rules below = 0 on main
Flip ALL FOUR together → `'error'`:
- `local/no-clickable-div`
- `jsx-a11y/click-events-have-key-events`
- `jsx-a11y/no-static-element-interactions`
- `jsx-a11y/no-noninteractive-element-interactions`

(They fire on the same elements, so they reach 0 together once the clickable sweep + deferred trio are merged.)

## After R-CLICK merges → Epic C is DONE. Run the §E checklist in `docs/epic-c/README.md`.
