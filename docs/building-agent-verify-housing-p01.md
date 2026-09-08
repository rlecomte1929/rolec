# Building-agent job — verify + REBASE `feat/housing-neighborhood-p01` (do NOT merge as-is)

**Paste to Claude Code / the building agent. Base off current `main`.**

---

## 0. 🛑 STOP — this branch cannot be merged directly

Cowork verified the branch state before you touch it:

```
merge-base with main:  787c3400  (2026-07-01)
main is AHEAD of that base by:  415 commits
branch's own work:  5 commits (Phase 0–3 recs)
```

**A direct merge would DELETE `payment.py`, `geocoding.py`, `test_drive.py`, the staged-provisioning fixture, `geocoding_service.py`, and the test-drive email/notification services** — reverting ~3 weeks of shipped work, because the branch predates all of it.

**Do NOT `git merge feat/housing-neighborhood-p01`. Do NOT open a PR from it as-is.**

The 5 commits must be **cherry-picked onto a fresh branch off current `main`**, then verified there. That is this job.

## 1. The 5 commits to rescue

```
da6e4057  feat(recs): real commute for living-areas via geocoded neighborhoods (Phase 1)
e9589818  feat(recs): unify office address to intake + geocode for real commute (Phase 0)
2c6c90be  test(recs): commute-accuracy harness + road_factor sweep (Phase 1 metric)
7cc8ffc1  feat(recs): neighborhood map for housing recommendations (Phase 2)
8d383652  feat(recs): schools layer scoped to neighborhoods (Phase 3)
```

⚠️ **Geoapify geocoding already shipped on main** (AIQ-1661, `5db12846`). Phase 0's "geocode for real commute" may **overlap or conflict** with what's already there. Reconcile — do not re-introduce Nominatim or a second geocoding path.

## 2. Steps

1. **New branch off current `main`:** `feat/housing-neighborhood-p01-rebased`.
2. **Cherry-pick the 5 commits in order** (oldest first: e9589818 → da6e4057 → 2c6c90be → 7cc8ffc1 → 8d383652). Resolve conflicts against current `main` — expect them in the geocoding/commute area.
3. **Drop or adapt anything already on main.** If Phase 0/1 geocoding duplicates AIQ-1661, keep main's version and rebase the Phase 1 commute logic on top of it. Report what you dropped and why.
4. If a commit's value is fully superseded by main, **say so and skip it** — don't force-carry dead code.

## 3. Verification gate — run all, report actual output

| Check | Command | Report |
|---|---|---|
| Type-check | `cd frontend && npx tsc --noEmit` | pass/fail + errors |
| Backend tests | `cd backend && pytest` | pass/fail count |
| Root-cause proving test | `cd backend && pytest backend/tests/test_living_areas_zero_fix.py` | **explicit pass/fail** |
| Commute accuracy | `python backend/scripts/commute_accuracy_eval.py` (or `scripts/commute_accuracy_eval.py`) | the metric it prints |
| Frontend build | `cd frontend && npm run build` | pass/fail |
| Compliance guard | `python scripts/check_compliance_claims.py` | pass/fail |
| Migration drift | `python scripts/check_migration_drift.py` | pass/fail — **the branch adds NO migrations of its own; confirm it doesn't reintroduce any main already has** |
| Route dump | `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'recommend' in r.path or 'geocod' in r.path))"` | the list — confirm nothing 405s |

## 4. Acceptance-criteria table

Map **each acceptance bullet from the AIQ-1652 v2 brief** (you have it; Cowork does not) → PASS / FAIL / UNVERIFIED + one line of evidence. This is the section only you can produce.

## 5. Integration check vs `feat/test-drive-vendor-seeding`

Both touch the recs path. Confirm the rebased branch doesn't conflict with the vendor-seeding work already on main (the `company_vendor_selections` filter + AIQ-1651 seeding). One targeted check: does a staged `shortlist_ready` session still populate recommendations after your changes? (Cowork can run that live if you give the go.)

## 6. Report

```
REBASE
  New branch: feat/housing-neighborhood-p01-rebased  off main@____
  Cherry-picked: __/5   Skipped (superseded): ____   Conflicts resolved in: ____
  Geoapify overlap with AIQ-1661 handled how: ____

GATE (actual output, not adjectives)
  tsc: ____   pytest: ____   test_living_areas_zero_fix.py: PASS/FAIL
  commute_accuracy_eval: ____   npm build: ____
  compliance guard: ____   migration drift: ____   route dump: ____

ACCEPTANCE TABLE: [attach — one row per v2 brief bullet]

INTEGRATION vs vendor-seeding: ____

BLOCKED / NEEDS DECISION: ____
```

## 7. Hard rules

- **Never merge the stale branch. Cherry-pick onto fresh `main` only.**
- Do NOT use `fix/td-qa-services-batch-0719`.
- Any router change → register in BOTH `backend/main.py` and `backend/app/main.py`.
- No `apply_migration` to prod; the branch shouldn't need any migration at all — flag if it does.
- A task is not done without a commit SHA on the new branch. No SHA = BLOCKED.

---

**Bottom line for Romain:** the "merge or hold" question was a trap — the branch is 415 commits stale and a direct merge reverts the whole launch surface. The real job is a clean rebase of 5 commits + a green gate. Once you have the SHA and a green board, the merge is a normal PR.
