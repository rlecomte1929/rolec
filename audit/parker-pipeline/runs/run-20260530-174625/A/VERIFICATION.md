# Verification — step A (Cox survival model for case timelines)

_Generated: 2026-05-30T18:13:44+02:00_

## Git state

- Current branch: `audit/parker-step-A-cox-survival`
- Expected branch: `audit/parker-step-A-cox-survival`
- Branch check: ✓ on expected branch

### Diff stats vs base
```
 backend/app/main.py                              |   3 +
 backend/app/routers/predictions.py               |  63 +++
 backend/app/services/case_duration_model.py      | 604 +++++++++++++++++++++++
 backend/requirements.txt                         |   7 +
 backend/scripts/__init__.py                      |   0
 backend/scripts/train_case_duration_model.py     |  70 +++
 backend/tests/test_case_duration_model.py        | 203 ++++++++
 supabase/migrations/20260601020000_ml_models.sql |  51 ++
 8 files changed, 1001 insertions(+)
```

## Migrations

```
supabase/migrations/20260601020000_ml_models.sql
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

- ✓ RESULT.md exists (169 lines)

