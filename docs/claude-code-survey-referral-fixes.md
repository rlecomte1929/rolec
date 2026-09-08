# Claude Code — survey referral capture: move it up + allow multiple

Paste from repo root. Base off current `main`. **Own branch off `main`: `feat/survey-referral-multi`. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md`.

Two changes to the test-drive survey, from live GTM feedback. Referrals are the warm-intro engine, and today the form loses them: it's one-referral-only and buried at the bottom, so anyone who drops off gives none and anyone who knows three gives one.

## Files
- Form: `frontend/src/pages/public/TestDriveSurveyPage.tsx` (+ its test `TestDriveSurveyPage.test.tsx`)
- Payload type: `frontend/src/api/testDrive.ts` (`referral_name/company_role/contact/consent`, `pilot_interest`)
- Write route: `backend/app/routers/test_drive.py` (inserts `survey_responses`)
- Admin read (counts "intro"): `backend/app/routers/admin_test_drive.py` (uses `referral_name IS NOT NULL`)
- Tests: `backend/tests/test_test_drive_referral.py`, `test_test_drive_survey.py`

---

## Change 1 — Move the referral question up (frontend only, easy)
In `TestDriveSurveyPage.tsx`, render the referral block **immediately after the pilot-interest question** ("Would you or your company want to be an early customer?"). The buy signal and the referral ask belong together, and it survives mid-survey drop-off. Pure reorder — no logic change.

## Change 2 — Allow multiple referrals ("add another")
Let a respondent add 1..N referrals, each with name / company-role / contact / consent, via an "Add another" button (start with 1 empty block; cap at ~5).

**Data model — do the backward-compatible thing:**
1. **Migration (follow `CLAUDE.md` migration discipline — commit an idempotent file in `supabase/migrations/`, do NOT apply directly):** add a JSONB column to the existing table:
   ```sql
   ALTER TABLE public.survey_responses ADD COLUMN IF NOT EXISTS referrals jsonb DEFAULT '[]'::jsonb;
   ```
   `survey_responses` already exists with its policies, so this is **not** a new-table RLS gate — no new policy needed. (Confirm the table's existing RLS still covers the new column; it does, since RLS is table-level.)
2. **Keep the legacy `referral_name/company_role/contact/consent` columns and KEEP WRITING THE FIRST referral into them.** Two live readers depend on them: the admin panel's "intro" count (`admin_test_drive.py`) **and** a scheduled Cowork alert that reads `referral_name/contact/consent` to surface warm leads to Romain daily. Do not drop or rename them. Store the full list in `referrals` (JSONB), mirror `referrals[0]` into the legacy columns.
3. **Backend** (`test_drive.py`): accept an optional `referrals: [{name, company_role, contact, consent}]` array in the survey payload; write it to the `referrals` column and mirror the first entry to the legacy columns. If only the legacy single fields are sent (old clients), wrap them into a 1-element `referrals` array. Mask/validate nothing that would block submit — a survey must never 500 on an optional field.
4. **Frontend** (`testDrive.ts` + form): add `referrals?: Referral[]` to the payload; render the repeatable block; on submit send the array (and, for safety, also populate the legacy single fields from `referrals[0]` so a stale backend still captures one).

## Acceptance
1. Referral block renders directly under the pilot-interest question.
2. "Add another" adds referral rows (up to the cap); each persists.
3. A submitted survey with 3 referrals → `survey_responses.referrals` has 3 entries **and** the legacy `referral_name/contact/consent` hold the first one (admin count + the daily alert still work).
4. Old-shape payload (single referral, no array) still succeeds and lands in both `referrals` and the legacy columns.
5. Empty referrals → submit still succeeds; `referrals = []`.
6. `cd frontend && npx tsc --noEmit` + `npm run build` clean; `cd backend && pytest -k test_drive` green; update the referral test for the array shape.

## Hard rules
- Branch `feat/survey-referral-multi` off `main`, own PR. Never `fix/td-qa-services-batch-0719`, never push `main`.
- Migration = committed idempotent file only; never `apply_migration` to prod (CLAUDE.md).
- Any router change → register in BOTH `backend/main.py` and `backend/app/main.py` (this route already exists — just extend it; verify with the routes check).
- Do NOT drop/rename the legacy `referral_*` columns — a live daily alert reads them.

## Report
branch · SHA · PR · migration filename · payload shape before/after · legacy columns still mirrored (proof) · 3-referral test + old-shape test green · tsc/build/pytest output.
