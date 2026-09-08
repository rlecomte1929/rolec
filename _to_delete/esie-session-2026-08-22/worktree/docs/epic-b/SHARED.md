# Epic B — SHARED brief (READ THIS FULLY before doing any task)

You are an autonomous engineer working on **Epic B (TS type-safety)** of the ReloPass frontend lint
cleanup. Repo `rlecomte1929/rolec`; frontend in `frontend/` (Vite + React + TypeScript). The epic drives
the TypeScript type-safety lint families to **0** across `frontend/src` and re-promotes each `warn` →
`error` in `frontend/eslint.config.js` so CI enforces them. **You own ONE slice** — see your TASK. Do only that.

The 8 target rules (all currently `warn`): `@typescript-eslint/` `no-unsafe-member-access`,
`no-unsafe-assignment`, `no-unsafe-call`, `no-unsafe-return`, `no-unsafe-argument`, `no-explicit-any`,
`no-base-to-string`, `restrict-template-expressions`.

## ⚠️ This is type refactoring, not mechanical edits
Typing surfaces **real `tsc` errors** (genuine type mismatches). So:
- **`npx tsc --noEmit` = 0 is the critical, non-negotiable gate.** Never commit with tsc errors.
- **REUSE the codebase's existing domain types** — do NOT invent shapes. Look in `features/<domain>/types.ts`,
  `features/policy/types.ts`, `features/policy-config/types.ts`, `types/relopass-api-contracts.ts`, and the
  types the file already declares/imports.
- **Type-only — no behavior change.** You are annotating + narrowing, not changing logic.

## NON-NEGOTIABLE DEFINITION OF DONE (all must hold before reporting success)
1. The **8 target rules = 0** across the files in your scope (measure with the command in your task).
2. **`npx tsc --noEmit` = 0 errors.**
3. `npm run build` succeeds.
4. `npx vitest run` = all pass (~1224 tests; you introduced NO new failures).
5. A PR is open, the **"Frontend (build, types, lint, unit)"** check is green, and (unless your task says
   otherwise) it is squash-merged.
6. You changed ONLY files in your scope. (Re-promotion / config tasks also touch `eslint.config.js`.)

> NOTE: `npx eslint src` staying "0 errors" does NOT measure your progress — these rules are still `warn`.
> Your real progress measure is your area's **target-rule count → 0** (per the task command) + tsc = 0.

## ENVIRONMENT & SETUP
- DEDICATED worktree (agents race HEAD):
  `git fetch origin main && git worktree add /tmp/wt-$TASK origin/main && cd /tmp/wt-$TASK/frontend && npm ci`
  Use **`npm ci`** (not `npm install` — drifts versions, fakes ~380 test failures; a symlinked node_modules
  fakes "cannot find zod/@tanstack" tsc errors). Branch: `git checkout -b fix/epic-b-$TASK`.
- Blocking CI = "Frontend (build, types, lint, unit)". Vercel/Cloudflare/Supabase-Preview = noise; never wait.
- NEVER `git stash`. NEVER `git checkout main` (stale) — use `git reset --hard origin/main`.
- Before pushing: `git fetch origin main && git merge origin/main`, then re-run `tsc --noEmit` (0) — other
  agents may have landed conflicting types.

## HARD RULES (each has cost hours on this project)
1. Commit messages (commitlint): type ∈ {feat fix chore docs style refactor perf test build ci revert}.
   Use **`fix(types): …`** (or `refactor(types): …`). **Subject must be lowercase** (no Sentence/Pascal case),
   **≤100 chars**, AND **every body line ≤100 chars**. Bad message aborts the commit (tree intact) → recommit.
   Use ASCII `-`.
2. **Measure eslint via a FILE, never a stream pipe to node** (it races/under-reports):
   `npx eslint <path> --format json > /tmp/x.json 2>/dev/null` then read with node `require('/tmp/x.json')`.
3. Push with `git push --no-verify`. The commit-msg hook still runs.
4. PR via REST if `gh pr create` 401s: `gh api -X POST repos/rlecomte1929/rolec/pulls -f title=… -f head=…
   -f base=main -f body=…`; poll `gh pr checks <n>` until Frontend=pass; `gh pr merge <n> --squash`.

## TYPING PATTERNS (proven on the earlier B1–B19 chunks)
- **`: any` annotations** on callbacks / state / params: replace with the real type, or often just **delete
  `: any`** and let TS infer from a typed source. e.g. `useState<any>(null)` → `useState<LocalType | null>(null)`.
- **`catch (err: any)`** → `catch (err)` (err is `unknown`), then narrow where you use it:
  `const e = err as { response?: { status?: number; data?: { detail?: unknown } }; message?: string };`
  (reuse the existing `getApiErrorMessage` / `formatApiDetail` / `getClientTransportErrorMessage` helpers in
  `src/utils/apiDetail.ts` — they already take `unknown`).
- **Loose API result used in a component** (`no-unsafe-member-access`/`assignment`): cast it to a local/domain
  type at the boundary: `const x = (await someAPI.get()) as { items?: Foo[] };` then read typed fields.
- **`no-base-to-string`** (a value stringifies to `[object Object]`): type the stringified field as
  `string`/`number`, or extract a typed helper `const toStr = (d: unknown): string => …`. Don't `String(anyVal)`.
- **`no-explicit-any`**: replace each explicit `any` with the real type, `unknown`, or a precise local shape.
- **client.ts** (`api.X('/…').then(r=>r.data)` returns `any`): add the generic `api.X<T>('/…')` when the
  return type is known — many methods already DECLARE `: Promise<T>` and just need the generic (see the merged
  `adminFormTemplatesAPI`). Otherwise `<unknown>` for action methods + `{ items: T[]; total? }` wrappers for
  list readers; consumers narrow once. Apply to the TARGETED method/line-range only (a global replace once hit
  other readers).
- **Supabase chains** typed `any`: import `import type { SupabaseClient } from '@supabase/supabase-js'` and
  type the lazy `getSupabase()` helper's return (see the merged `assistant_router.ts` / `retrieve_policy.ts`).

## PER-FILE RITUAL → that file's 8-rule count = 0, then `tsc --noEmit` = 0. PER PR → tsc 0 + build + vitest green.

## REPORT WHEN DONE: PR number + merge status, before/after count of the 8 rules in your area, and any value
you intentionally left as `unknown`/cast (with the reason).
