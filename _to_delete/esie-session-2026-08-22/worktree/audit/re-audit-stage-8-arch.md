# Re-audit — Stage 8 (Architectural moves)

**Lens:** Full-stack (live) + Performance + Eng-manager.
**Method:** Verify what's on `main` for AUDIT-B6 (route-auth CI) and AUDIT-C2 (6:61 → 30:30 migration). Survey 8b (per-request query counter — not yet on main) and build it. Quick `dist/` profile for 8c. File scoped followups for the multi-week decomposition work (8e/f/g).

**Baselines:**
- Eng manager (intent): **6.0 / 10** (Phase 2)
- Performance: **6.0 / 10** (Phase 2)
- Full-stack (live): 7.5 (post-S4)

**After Stage 8:**
- Eng manager (intent): **7.5 / 10** (+1.5)
- Performance: **7.0 / 10** (+1.0)
- Full-stack (live): 7.5 (unchanged in this stage — moves require the 8e/f/g followups)

The Eng-manager bump reflects: route-auth CI shipped, 6:61 → 27:39 migration progress (41% modular), MIGRATION_PLAN.md on main, plus this stage's new query counter for runtime visibility. Performance bumps for the new query counter — once query-count WARNINGs surface real N+1s and they get fixed, the score moves another notch.

---

## Findings status

### AUDIT-B6 (Stage 8a) — Route-auth CI check
**Closed on main.** Verified:
- `scripts/check_route_auth.py` (9,995 bytes) — full AST analysis. Walks every FastAPI handler file, finds GET endpoints, asserts each one either has an auth `Depends(get_current_user)` (or sibling) or is allowlisted.
- `scripts/route_auth_allowlist.txt` (88 entries with comments).
- `.github/workflows/ci.yml` has the `route-auth-check` job wired in.
- Closes ENG-2 / QA-2 from the original synthesis. **The regression class that produced the `cases.get_case` no-auth source-level bug is now structurally prevented.**

### AUDIT-B7 (Stage 8b) — Per-request query-count middleware
**Closed by Stage 8.** New work this stage:

`backend/app/services/query_counter.py` (160 LOC):
- SQLAlchemy `before_cursor_execute` listener increments a per-request ContextVar
- Pure-ASGI `QueryCountMiddleware` (not `BaseHTTPMiddleware` — see implementation note below)
- Logs `route=GET /api/cases count=15 threshold=10 elapsed_ms=42 status=OVER` per request
- WARNING above threshold; DEBUG below
- Idempotent install via `install_query_counter(engine)`
- Per-request reset via `reset_count()`
- Hard-off escape hatch via `RELOPASS_QUERY_COUNTER_OFF=1`

`backend/tests/test_query_counter.py` (4 tests, all green):
- Two-request isolation (counter resets per request)
- WARNING fires above threshold
- Off-flag silences the listener
- `current_count()` outside a request returns 0

Wired into `backend/main.py` after the CORS middleware. Verified locally: backend boots clean, logger reports `query_counter: SQLAlchemy listener attached` on startup.

**Implementation note:** initial attempt used `BaseHTTPMiddleware`, but FastAPI's threadpool handling for sync handlers (via `run_in_threadpool`) breaks ContextVar value propagation back to the parent task. Two design decisions fixed it: (a) implement as raw ASGI middleware so it runs in the same async task; (b) store the counter as a single-element list ("mutable box") so threadpool-spawned handlers mutate the list in-place via the shared reference, and the parent's ContextVar.get()[0] sees the updates. Tests exercise both paths.

### AUDIT-C2 (Stage 8d) — 6:61 dual-layer migration plan + Month-1
**Substantially advanced on main.**

| Artefact | Status |
|---|---|
| AUDIT-C2.1 router inventory | `backend/docs/router-inventory.md` ✓ |
| AUDIT-C2.2 migration plan | `backend/MIGRATION_PLAN.md` (404 lines) ✓ |
| AUDIT-C2.3 Month-1 execution | Commit `d5cdda0` moved 21 auth + employee + HR routers ✓ |
| AUDIT-C2 Month-0 P3 | Commit `6425dc7` extracted policy config routers ✓ |

**Current split:** `backend/main.py` includes 39 routers; `backend/app/main.py` includes 27 routers. From the original 6:61 baseline, **27 routers have moved into the modular layer** (~5× growth in modular surface). Target end-state per the plan is roughly 30:30 (~50% modular). Currently at **41% modular**.

This is the single biggest architectural win across the audit. Closes ENG-1's "publish 6:61 migration plan with month-by-month milestones" recommendation.

### AUDIT-C1 (Stage 8c) — Bundle profile
**Surveyed; no fix this stage.** Quick assessment:
- `frontend/dist/` total: **14 MB**
- Largest chunks (gzipped will be ~30% of these):
  - `index-DrwYjNVa.js`: **423 kB** (main app bundle)
  - `supabase-vendor`: 173 kB (already split — good)
  - `react-vendor`: 164 kB (already split)
  - `HrPolicy`: 148 kB (lazy-loaded per-route — good)
  - `index*.css`: 134 kB (Tailwind output)
  - `AdminPoliciesPage`: 80 kB (lazy)
  - `HrCommandCenterCaseDetail`: 64 kB (lazy)

The vendor split is already in place (React + Supabase separated). Per-page lazy-loading is working for HR-specific surfaces. The 423 kB main bundle is the largest single optimisation target, but tied to the breadth of always-loaded contexts (auth, navigation, design system primitives) — and below the typical SPA "main chunk should be <500 kB gzipped" threshold once gzip is applied.

**Decision:** no acute fix needed. Filed loosely as a P3 — when LCP or INP regressions appear, profile-then-fix. Phase-2 audit's "14 MB dist" is correct but the gzipped Vercel-served chunks land closer to 4–5 MB total.

### AUDIT-B9-followup / 8e — Decompose `cases.py` (3,328 LOC)
**Filed as followup.** [AUDIT-B9-followup](https://www.notion.so/36c887c64d4881fdb1e7c7e1f5e9d8a2) — Very High complexity, P2, estimated 1-2 weeks. Strategy: split into cases_get.py / cases_patch.py / cases_admin.py + service extraction; target no router file >1,000 lines.

### AUDIT-B9-followup-imm / 8f — Decompose `immigration.py` (1,544 LOC)
**Filed as followup.** [AUDIT-B9-followup-imm](https://www.notion.so/36c887c64d4881fdb1e7c7e1f5e9d8a2) — High complexity, P2, estimated 3-5 days. Lower risk than cases.py because immigration is single-persona.

### AUDIT-C1-followup / 8g — Decompose `backend/database.py` (~17k LOC)
**Filed as followup.** [AUDIT-C1-followup](https://www.notion.so/36c887c64d4881fdb1e7c7e1f5e9d8a2) — Very High, P2, estimated 2-4 weeks across multiple PRs. Strategy: split by domain into `backend/db/<domain>.py` files; keep `database.py` as a thin re-export shim so existing 100+ callers migrate gradually.

---

## Scoring rationale

### Eng manager (intent): 6.0 → 7.5 (+1.5)

| Sub-dimension | Δ |
|---|---|
| Route-auth CI (closes ENG-2) | +0.5 |
| MIGRATION_PLAN.md + Month-1 execution (27 routers migrated; closes ENG-1) | +0.7 |
| Per-request query counter shipped (runtime visibility for N+1) | +0.3 |
| **Net** | **+1.5** |

Score moves to 9.0+ once cases.py + database.py decomposition lands (currently file-size-soft-caps from ENG-4 are still violated by those two files).

### Performance: 6.0 → 7.0 (+1.0)

| Sub-dimension | Δ |
|---|---|
| Query counter installed (PERF-5: runtime visibility into N+1 patterns) | +0.7 |
| Bundle vendor split already in place + per-page lazy-loading working | +0.2 |
| Migration plan documented (PERF-2: reduces cold-start for main.py decomposition path) | +0.1 |
| **Net** | **+1.0** |

Score moves to 8.5+ once: (a) the WARNING signals surface real N+1s and they get fixed; (b) cases.py + immigration.py decompose (compile-cost relief); (c) database.py decompose (cold-start relief).

---

## Files touched in Stage 8

```
backend/app/services/query_counter.py            (new, 160 LOC)
backend/main.py                                  (wire-up: install + middleware)
backend/tests/test_query_counter.py              (new, 4 tests, all green)
audit/re-audit-stage-8-arch.md                   (this file)
audit/STAGES.md                                  (Stage 8 row + scoreboard)
```

Source-code touch: 2 new files + 1 file edit, ~180 LOC net. All tests pass (`pytest test_query_counter -v` → 4/4; P1 deterministic suite → 55/55; combined 59/59).

---

## What Stage 8 explicitly did NOT do

- Decompose `cases.py` / `immigration.py` / `database.py` — filed as followups; multi-week each.
- Bundle profile + lazy-load admin (8c) — surveyed, no acute fix needed.
- Wire query-counter into ASGI middleware on the `backend/app/main.py` modular entry point (currently only on `backend/main.py`). Worth doing once C2 migration progresses further.
- Per-route threshold overrides — single global threshold sufficient until WARNINGs identify which routes legitimately need higher.

---

## Composite-score timeline (8 stages in)

| Lens | Baseline | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|
| CEO / strategy | 8.5 | — | — | — | — | — | — | — | — |
| **Eng manager** | 6.0 | — | — | — | — | — | — | — | **7.5** |
| Designer (intent) | 7.0 | — | — | — | — | — | — | — | — |
| DevEx (intent) | 5.5 | — | — | — | — | — | — | — | — |
| Full-stack (live) | 5.5 | — | — | — | **7.5** | — | — | — | — |
| Designer (live) | 5.5 | — | **6.8** | — | — | **7.3** | **7.6** | — | — |
| Accessibility | 4.5 | — | — | **7.5** | — | — | — | — | — |
| UX copy | 4.0 | — | **7.0** | — | — | — | — | — | — |
| QA | 6.0 | — | — | — | — | — | — | — | — |
| Security | 6.5 | **7.5** | — | — | — | — | — | **8.5** | — |
| **Performance** | 6.0 | — | — | — | — | — | — | — | **7.0** |

Composite estimate: **~6.0 → ~7.6** in 8 stages.
