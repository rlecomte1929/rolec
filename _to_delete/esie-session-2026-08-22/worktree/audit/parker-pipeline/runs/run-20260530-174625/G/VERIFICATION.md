# Verification — step G (Carbon + per-customer AI unit economics)

_Generated: 2026-05-30T20:49:32+02:00_

## Git state

- Current branch: `audit/parker-step-H-conjoint`
- Expected branch: `audit/parker-step-G-carbon-tco`
- Branch check: ⚠ on a different branch (this is OK if step opened a PR and you've already switched away)

### Diff stats vs base
```
 .../runs/run-20260530-174625/H/PLAN.md             | 158 ++++++++++
 .../runs/run-20260530-174625/H/RESULT.md           | 169 +++++++++++
 backend/app/main.py                                |   2 +
 backend/app/routers/conjoint.py                    | 201 +++++++++++++
 backend/app/services/conjoint_repo.py              | 305 +++++++++++++++++++
 backend/app/services/conjoint_service.py           | 322 +++++++++++++++++++++
 backend/requirements.txt                           |   4 +
 backend/tests/test_conjoint_router.py              | 179 ++++++++++++
 backend/tests/test_conjoint_service.py             | 138 +++++++++
 supabase/migrations/20260601090000_conjoint.sql    | 132 +++++++++
 10 files changed, 1610 insertions(+)
```

## Migrations

```
supabase/migrations/20260601090000_conjoint.sql
```

## Backend tests (pytest)

```
./audit/parker-pipeline/pipeline.sh: line 387: pytest: command not found
[pytest failed or not run]
```

## Frontend type-check (tsc --noEmit)

```
```

## RESULT.md presence

- ✗ RESULT.md is MISSING. Step is not finished — Claude Code must write it before completion.

