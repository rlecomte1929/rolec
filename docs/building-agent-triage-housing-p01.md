# Building-agent job — TRIAGE `feat/housing-neighborhood-p01` (likely mostly superseded)

**Paste to Claude Code / a repo-connected agent with push credentials. The Audos lane cannot do this — no repo access.**

---

## 0. The finding that reframes this job

Cowork verified two things before you start:

1. The branch is **415 commits behind main** (merge-base `787c3400`, 2026-07-01). A direct merge is PROHIBITED — it would delete `payment.py`, `geocoding.py`, `test_drive.py`, the staged-provisioning fixture, and more. Never `git merge` this branch.
2. **Every file its 5 commits touch already exists on current main and was changed there** — several heavily:

   | File | Branch touches | Main changed since base |
   |---|---|---|
   | `recommendations/geo.py` | ✎ | 3 commits |
   | `recommendations/schools_nearby.py` | ✎ (adds) | **already on main**, 2 commits |
   | `plugins/living_areas.py` | ✎ | 4 commits |
   | `recommendations/engine.py` | ✎ | 2 commits |
   | `recommendations/router.py` | ✎ | 7 commits |
   | `scripts/commute_accuracy_eval.py` | ✎ (adds) | **already on main** |
   | `features/recommendations/HousingNeighborhoodMap.tsx` | ✎ (adds) | **already on main** |

**This strongly suggests the Phase 0–3 work was re-implemented and merged via the PR series (#1600–#1618) while this branch sat stale.** So the likely correct outcome is **abandon the branch**, not rebase it.

## 1. This is a TRIAGE, not a rebase

Do **not** cherry-pick blind. For each of the 5 commits, decide: **already on main (drop) / partially missing (port the delta) / genuinely absent (carry).**

The 5 commits, oldest→newest:
```
e9589818  Phase 0 — unify office address to intake + geocode
da6e4057  Phase 1 — real commute via geocoded neighbourhoods (geo.py, datasets, geocode_datasets.py)
2c6c90be  Phase 1 metric — commute_accuracy_eval.py   ← this file is ALREADY on main
7cc8ffc1  Phase 2 — HousingNeighborhoodMap.tsx         ← this file is ALREADY on main
8d383652  Phase 3 — schools_nearby.py scoped to neighbourhoods  ← this file is ALREADY on main
```

## 2. Steps

1. **Diff each commit's content against current main**, file by file. For each, report: `already-present-identically` / `already-present-different` / `absent`.
   - `git show <commit>:<file>` vs `git show origin/main:<file>` per file.
2. **If a commit is fully present on main → drop it.** Record "superseded by main."
3. **If a commit adds something genuinely missing** (e.g. a Phase-1 commute-accuracy refinement main lacks), branch off current main (`feat/housing-neighborhood-triage`) and port ONLY the missing delta.
4. **If ALL 5 are superseded → recommend abandoning the branch.** Delete it after confirming nothing of value is lost. That is a valid — and likely — outcome.

## 3. Gate — only if something was actually ported

If step 3 produced real changes, run and report:
- `cd frontend && npx tsc --noEmit`
- `cd backend && pytest` (call out `backend/tests/test_living_areas_zero_fix.py` — the H1 root-cause proving test)
- `cd frontend && npm run build`
- `python scripts/check_compliance_claims.py`
- `python scripts/check_migration_drift.py` (branch adds no migrations — confirm)
- route dump: `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'recommend' in r.path))"`

If nothing was ported, the gate is N/A — say so.

## 4. Acceptance table (only you have the v2 brief)

Map each AIQ-1652 v2 acceptance bullet → **already met on main / newly met by port / not met**. Cross-reference: most of AIQ-1652 already shipped (advisory living_areas, housing agencies, shortlist re-rank, preference questions, explainability, multimodal commute, cost-of-living, per-agency coverage, Geoapify). The question is whether this branch adds anything those PRs missed.

## 5. Report

```
TRIAGE — per commit:
  e9589818 (Phase 0): superseded / partial / absent — evidence: ____
  da6e4057 (Phase 1): ____
  2c6c90be (metric):  ____  (commute_accuracy_eval.py already on main)
  7cc8ffc1 (Phase 2): ____  (HousingNeighborhoodMap.tsx already on main)
  8d383652 (Phase 3): ____  (schools_nearby.py already on main)

VERDICT: ABANDON branch (all superseded)  /  PORT delta (branch feat/housing-neighborhood-triage @ SHA ____)

IF PORTED — GATE:
  tsc ____  pytest ____ (test_living_areas_zero_fix.py: ____)  npm build ____
  compliance ____  drift ____  routes ____

ACCEPTANCE: already-met __/__  | newly-met __  | not-met __

BLOCKED / NEEDS DECISION: ____
```

## 6. Hard rules

- **Never merge the stale branch. Diff-triage first; port only genuine deltas onto fresh `main`.**
- Do NOT use `fix/td-qa-services-batch-0719`.
- Router change → register in BOTH `backend/main.py` and `backend/app/main.py`.
- No `apply_migration` to prod.
- A ported change is not done without a commit SHA. **"Abandon — all superseded" is a complete, valid result and needs no SHA.**

---

**Bottom line for Romain:** the branch is almost certainly dead weight — its work appears to already be on main via the merged PR series. The building agent's job is to *confirm that with content diffs* and either abandon it cleanly or port the one or two things (if any) main missed. Either way it's a small, bounded job, not a 415-commit rebase.
