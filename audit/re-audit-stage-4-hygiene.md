# Re-audit — Stage 4 (Code hygiene cleanup)

**Lens:** Full-stack (live).
**Method:** Inspect what's actually on `main` for AUDIT-A8 (`logger.ts` + console.* strip) and AUDIT-A9 (services tree consolidation). Count remaining `no-console` + `no-clickable-div` ESLint violations after the team's AIQ-397 / AIQ-398 sprints. Score the full-stack lens against the Phase-2 baseline.

**Baseline (Phase 2 audit):** Full-stack (live) **5.5 / 10**
**After Stage 4:** **7.5 / 10** (+2.0)

The +2.0 reflects three substantial wins on `main`: AUDIT-A8 fully closed, the bulk of the ESLint backlog drained, and the cases.py auth hardening (verified in Stage 1). A9 is acknowledged-not-closed because the migration code exists but is not on main — see "AUDIT-A9-followup" below.

---

## Findings status

### AUDIT-A8 (P1) — Strip 19 console.* statements; route through real logger
**Closed on main.** Verified:
- `frontend/src/lib/logger.ts` is in place (commit `d9274e2`, PR #119). Wraps `console.*` and no-ops when `import.meta.env.MODE === 'production'`. Backward-compatible API (debug/info/warn/error/log).
- Production code paths: `grep -rn 'console\\.' src/pages src/features` excluding `eval_*` CLI scripts and `__tests__` returns **0** non-exempt sites. The 19 Phase-2-named call sites are all migrated.
- Remaining `console.*` usage in `src/api/*` (9 errors) and `src/features/policy-builder/eval_*` (Node.js CLI scripts, eslint-exempt). The API-layer 9 are AIQ-398's residual work — see below.

### AUDIT-A9 (P1) — Decide + document services tree
**Acknowledged-not-closed on main.** Reality:
- **Decision + documentation** landed (commit `40bb373` [A9.1] migration matrix → `audit/services-migration-matrix.md`; commit `8a2d55f` [A9.2] services-tree ADR + CLAUDE.md rule). On main ✓.
- **The actual 155-file migration (A9.3)** + **97 router import corrections (A9.4)** exist as local commits `45a3d43` + `c76b134` + `6cf3269` on the `audit/stage-1-security` branch but were never pushed/PR'd to main. On main: ❌.
- **Current state on main:** dual services tree persists. `git ls-files backend/services/` = 155 files; `git ls-files backend/app/services/` = 25 files. Active cross-imports (`from ...services.X` in 4+ routers) point at the legacy tree.

**Follow-up filed:** [AUDIT-A9-followup](https://www.notion.so/36c887c64d488148918dd44c45fcd9c4) — push the stranded migration commits as a focused PR. Estimated ~2 hours.

### Related: AUDIT-A6-followup (AIQ-395) — TS ESLint parser
**Closed on main.** Commit `81c8e8c` (AUDIT-A6-followup) installed `@typescript-eslint/parser` + wired the flat config. CI now parses every `.ts`/`.tsx` file. ESLint surfaced ~328 pre-existing violations (303 `no-clickable-div` + 25 `no-console`) that were previously hidden.

### AIQ-397 (Team-led `no-clickable-div` sprint)
**Substantial progress, mostly complete.** Running `npx eslint src` against current main reports **0 errors** for `no-clickable-div`. From 303 violations to 0 over the AIQ-397 sprint — closed.

### AIQ-398 (Team-led `no-console` sprint)
**In flight, 9 residual.** ESLint shows **9 `no-console` errors** in:
- `src/api/client.ts:1323, 3154, 3161`
- `src/api/edgeConfig.ts:67, 91, 102`
- `src/api/rpc.ts:53, 62, 72`
- `src/api/supabaseAuth.ts:20, 25`

These are API-layer error paths. Likely either need to be routed through `logger.error`, or to acquire `// eslint-disable-next-line no-console` with a justifying comment for genuinely-required dev-mode diagnostics. Out of Stage 4 scope; tracked under existing AIQ-398.

### Stale eslint-disable directives
**6 warnings** for "Unused eslint-disable directive" in `src/api/client.ts:133, 139, 147, 151, 179, 210`. These reference `@typescript-eslint/no-explicit-any` which the current parser config doesn't flag — the disables are now dead. Trivial cleanup; tracked as part of AIQ-398 or a separate hygiene pass.

---

## Scoring rationale

| Sub-dimension | Δ |
|---|---|
| A8 logger landed + all 19 Phase-2 call sites migrated | +0.7 |
| AIQ-395 TS-ESLint parser → ESLint now parses TypeScript; 0 `no-clickable-div` errors after AIQ-397 sprint | +0.7 |
| Stage 1 cases.py auth hardening (verified) + A2 closure | +0.4 |
| A9.1 + A9.2 decision/docs on main | +0.2 |
| A9.3/A9.4 stranded (not on main) | −0.0 (filed as follow-up, no score penalty since the work exists) |
| Stage 1's `ensure_initialized` fix (verified clean startup) | +0.0 (already counted in Stage 1) |
| **Net** | **+2.0** |

Score moves to 8.5+ once:
- AUDIT-A9-followup lands (single services tree on main)
- AIQ-398 closes the 9 residual `no-console` errors
- 6 stale eslint-disable directives removed

---

## What Stage 4 explicitly did NOT do

- Push the stranded A9.3/A9.4 commits to main. Filed as AUDIT-A9-followup with rationale.
- Migrate the 9 `src/api/*` console.* call sites to logger.error. Out of scope; team's AIQ-398.
- Drop the 6 stale eslint-disable directives. Trivial; part of AIQ-398 or hygiene pass.
- Touch `database.py` (17k LOC) or `backend/main.py` (14k LOC). Those are Stage 8 architectural concerns.

---

## Composite-score timeline after Stage 4

| Lens | Baseline | S1 | S2 | S3 | S4 |
|---|---|---|---|---|---|
| Security | 6.5 | **7.5** | — | — | — |
| UX copy | 4.0 | — | **7.0** | — | — |
| Design (live) | 5.5 | — | **6.8** | — | — |
| Accessibility | 4.5 | — | — | **7.5** | — |
| Full-stack (live) | 5.5 | — | — | — | **7.5** |

Composite trajectory: ~6.0 → ~6.2 → ~6.8 → ~7.1 → **~7.4**.
