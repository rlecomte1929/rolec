# Verification — step J (NLG variety (data-to-text, frame-based, extractive))

_Generated: 2026-05-30T21:34:14+02:00_

## Git state

- Current branch: `audit/parker-step-J-nlg-variety`
- Expected branch: `audit/parker-step-J-nlg-variety`
- Branch check: ✓ on expected branch

### Diff stats vs base
```
 .../runs/run-20260530-174625/J/PLAN.md             |  97 ++++++++++++
 .../runs/run-20260530-174625/J/RESULT.md           | 158 +++++++++++++++++++
 backend/app/main.py                                |   2 +
 backend/app/routers/nlg.py                         | 170 +++++++++++++++++++++
 backend/app/services/nlg/__init__.py               |  34 +++++
 backend/app/services/nlg/data_to_text.py           | 128 ++++++++++++++++
 backend/app/services/nlg/extractive_summarizer.py  | 121 +++++++++++++++
 backend/app/services/nlg/frame_based.py            | 141 +++++++++++++++++
 backend/tests/test_nlg_data_to_text.py             |  96 ++++++++++++
 backend/tests/test_nlg_extractive.py               |  72 +++++++++
 backend/tests/test_nlg_frame_based.py              | 114 ++++++++++++++
 backend/tests/test_nlg_router.py                   | 118 ++++++++++++++
 frontend/src/api/nlg.ts                            |  26 ++++
 .../MobilityControlCenterV2Page.tsx                |  22 +++
 .../features/policy/HrPolicyReviewWorkspace.tsx    |  23 +++
 15 files changed, 1322 insertions(+)
```

## Migrations

```
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

- ✓ RESULT.md exists (158 lines)

