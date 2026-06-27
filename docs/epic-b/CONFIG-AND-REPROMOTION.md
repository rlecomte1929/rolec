# Epic B — CONFIG + RE-PROMOTION TASKS

> Read `docs/epic-b/SHARED.md` first. These edit `frontend/eslint.config.js`. TASK RELAX-TESTS is done FIRST
> (it shrinks the backlog). The RE-PROMOTIONS are the FINAL wave — sequential, one per family, each gated on
> that family being 0 across ALL `src`.

## TASK RELAX-TESTS — do FIRST (tiny config PR; removes ~50 violations from the gate)
Test files legitimately use `any` mocks, so the type-safety rules add little value there. In
`frontend/eslint.config.js` there is already a test-file override block (matches
`src/**/*.test.{ts,tsx}` + `src/**/__tests__/**`, currently turning off `no-console`/`no-unused-vars`/
`unbound-method`). Add the 8 type-safety rules to that block as `'off'`:
```js
'@typescript-eslint/no-unsafe-member-access': 'off',
'@typescript-eslint/no-unsafe-assignment': 'off',
'@typescript-eslint/no-unsafe-call': 'off',
'@typescript-eslint/no-unsafe-return': 'off',
'@typescript-eslint/no-unsafe-argument': 'off',
'@typescript-eslint/no-explicit-any': 'off',
'@typescript-eslint/no-base-to-string': 'off',
'@typescript-eslint/restrict-template-expressions': 'off',
```
VERIFY `npx eslint src` = 0 errors + build + tests. Commit `chore(lint): relax type-safety rules in test files`.
(If the user prefers to TYPE tests instead of relaxing, skip this and fold test files into the area tasks.)

## RE-PROMOTION procedure (identical for each; run ONE AT A TIME, never parallel)
1. Worktree off `origin/main` + `npm ci`. Branch `fix/epic-b-r-<rule>`.
2. In the LINT-3-close block of `frontend/eslint.config.js`, flip the target rule(s) `'warn'` → `'error'`.
3. **VERIFY `npx eslint src` = 0 errors** (proves the family is truly drained — if not 0, the gate isn't met;
   STOP and report which files still violate). Then build + tests green.
4. Commit `fix(types): re-promote <rule> to error (Epic B)`, PR, merge.

## RE-PROMOTIONS (FINAL wave; each GATED on that family = 0 across all `src`, measured with the §B command)
- **R-EXPLICIT-ANY** [gate: `no-explicit-any` = 0]: flip `@typescript-eslint/no-explicit-any` → error.
- **R-BASE-TO-STRING** [gate: `no-base-to-string` = 0 AND `restrict-template-expressions` = 0]: flip
  `@typescript-eslint/no-base-to-string` and `@typescript-eslint/restrict-template-expressions` → error.
- **R-UNSAFE** [gate: ALL FIVE = 0: `no-unsafe-member-access`, `no-unsafe-assignment`, `no-unsafe-call`,
  `no-unsafe-return`, `no-unsafe-argument`]: flip all five → error together (they co-occur on the same
  untyped values, so they reach 0 together).

## Epic B DONE (run after R-UNSAFE merges)
```
grep -nE "@typescript-eslint/(no-unsafe|no-explicit-any|no-base-to-string|restrict-template)" frontend/eslint.config.js
# in the LINT-3-close block every one reads 'error' (zero 'warn'); the test-file override may keep them 'off'
npx eslint src   # 0 errors
```
Then update memory `project_lint_warn_backlog_epics.md` (Epic B → DONE) and close the Notion TS-type-safety epic.
All three LINT warn-backlog epics (Async-safety, Accessibility, TS type-safety) are then complete.
