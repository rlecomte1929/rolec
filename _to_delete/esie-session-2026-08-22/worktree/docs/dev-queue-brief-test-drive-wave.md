# Dev-queue brief — three tasks before the cohort wave

**For:** a single Claude Code session (repo mounted) · **Date:** 2026-07-06
**Queue:** AI Work Queue · DB `3bc887c64d4880898188fcf2dc3edc1b`
**All three tasks are 🟡 Yellow** — no Red gates, no plan-approval pauses. Each self-validates against its Test Command, lands in Human Review, and `review-validator` closes it out.

---

## Context (read once, applies to all three)

The ReloPass test-drive campaign is **built and live in prod**: schema applied (`test_sessions`, `survey_responses`, `funnel_events`, RLS on), provisioning endpoint, `/test-drive` page, survey, completion detection, referral→prospect pipeline, funnel events, admin dashboard at `/admin/test-drive`, and the three explainer videos. The canary flag `RELOPASS_TEST_DRIVE_ENABLED=1` is set. Romain is about to run **tester-zero** himself, then invite ~25 people (20 friends + 5 prospects) with **one plain link**.

These three tasks are what stands between tester-zero and sending that link.

**House rules that apply here:**
- **No new routers** in any of these three → the `backend/main.py` + `backend/app/main.py` dual-registration rule does **not** apply. (All three extend existing routers/services.)
- **No new tables.** Reuse `feedback`, `feedback_status`, `test_sessions`.
- Import auth deps from `backend.app.auth_deps`.
- Frontend: antigravity components + `DESIGN.md` tokens (navy/accent; no purple). `npx tsc --noEmit` must be clean.
- Every task ends with its own git commit (dev-queue Phase 7). `npm run build` must pass before push (pre-push hook).

---

## Task 1 — TD-13 · Auto-assign corridor on provision 🔴 **WAVE BLOCKER**

**Notion:** https://app.notion.com/p/395887c64d488196bc77ce99a7d82485 · P0 · Layer API

**Why first:** Romain will send **one plain link** (`relopass.com/test-drive`) to the whole cohort. Today a plain link hard-defaults every tester to Paris→Oslo (`FR_NO`), so the other four corridors would get **zero** coverage. Until this ships, the wave can't go out.

**Do:** make `corridor_id` optional in `POST /api/test-drive/provision`; when absent, auto-assign one of the six locked corridors (`FR_NO`, `IN_DE`, `GB_US`, `NL_SG`, `ES_AE`, `ES_IE`) by weighted round-robin favouring Tier-A (~30% FR_NO, ~30% IN_DE, ~10% each Tier-B), computed from current per-corridor counts in `test_sessions` (pick the one furthest below target share). Return the assigned corridor so the page can render it. Frontend: when the URL has no `?corridor=`, omit `corridor_id` and render what the backend returns instead of hard-defaulting to `FR_NO`. **Keep `?corridor=` as an explicit override.**

**Files:** `backend/app/routers/test_drive.py`, `frontend/src/pages/public/testDriveContent.ts` + `TestDrivePage.tsx`
**Test:** `cd backend && pytest tests/test_test_drive_provision.py -q`

---

## Task 2 — TD-12 · Rework completion emails (drop auto thank-you → mailto)

**Notion:** https://app.notion.com/p/395887c64d4881748083c03b02040119 · P1 · Layer API

**Why:** Resend quota is limited, and the platform currently sends **two** emails per completion — a notify to Romain *and* a thank-you to the tester sent **as** Romain. He wants the thank-you to genuinely come from his own mailbox.

**Do:** in `backend/app/services/test_drive_emails.py`, **remove** the thank-you Resend send (`render_thank_you_email` + its `_resend_send` call). **Keep** the single notify-to-Romain send, and enrich it with the tester's email plus a **`mailto:` deep link** that opens his mail client with the thank-you pre-filled. Add the same "Send thank-you" mailto button per completed row in `AdminTestDrive.tsx` / `TestDriveTab.tsx`. Net: 2 Resend sends → 1.

Thank-you body (subject *"Thank you — that really helps"*): *"Hi {first name}, thank you for taking the time to test-drive ReloPass. Running through it end to end and telling me what worked and what didn't is exactly what I need before we launch. Your feedback goes straight into what we fix and build next. If anything else comes to mind, just reply — this reaches me directly. Thanks again, Romain"*

**Constraint:** the thank-you must be a **client-side mailto only** — never sent as Romain via Resend. URL-encode the body; keep it short (clients truncate).
**Files:** `backend/app/services/test_drive_emails.py`, `frontend/src/pages/admin/AdminTestDrive.tsx`, `frontend/src/components/admin/TestDriveTab.tsx`
**Test:** `cd backend && pytest tests/test_test_drive_emails.py -q`

---

## Task 3 — Admin: author a new feedback item (manual intake → dispatch-ready)

**Notion:** https://app.notion.com/p/39a887c64d4881a7bc41ea5453be4f72 · P1 · Layer API

**Why:** feedback can only arrive from the tester widget — Romain can't log an issue he spots himself. Everything downstream already exists (dispatch context → `engineer_task` LLM → engineered Notion task with Execution Prompt/Layer/Tier → `/fix` → `feedback_notion_sync` status write-back). **This is the one missing entry point.**

**Do:**
1. `POST /api/admin/feedback` in the **existing** `admin_feedback.py` router (`require_admin`). Writes a `public.feedback` row on the `product` stream, shaped **identically to a widget submission** so all downstream routes work unchanged: `page_url`, `category`, `message`, screenshot, `reporter_*` (default to the admin), and `client_context` (jsonb) carrying steps_to_reproduce / expected / actual / persona / campaign / corridor_id / tester_segment / environment.
2. **In the same call**, upsert `feedback_status` with `dispatch_context` (REQUIRED), `severity`, `area` — because `dispatch/preview` **400s on empty context**. This makes a self-logged item dispatch-ready in one pass.
3. "New feedback" button + form on Feedback & Work → Inbox (`FeedbackTab.tsx`).
4. **Screenshot — both paths required:** (a) **upload** (file picker + drag-drop, png/jpg) as the *primary* path — the screen being reported is usually not the admin console you're on; (b) **capture** via the *same* html2canvas + compression util the tester widget uses. Thumbnail preview with remove/replace. Screenshot optional overall.

**Files:** `backend/app/routers/admin_feedback.py`, `frontend/src/components/admin/FeedbackTab.tsx`, admin feedback API wrapper, backend tests
**Test:** `cd backend && pytest tests/ -k admin_feedback -q && cd ../frontend && npx tsc --noEmit`

---

## How to run it

All three are Yellow, independent (no shared files), and each has a Test Command + Validation Criteria — so they're eligible for the unattended lane.

**Option A — hands-off (recommended):** open Claude Code on a campaign branch and run **`relopass-autopilot`**. It will pick up all three Yellow tasks, execute, self-validate, commit, and park them in Human Review.

**Option B — sequential control:** run **`relopass-dev-queue`** and work TD-13 → TD-12 → Task 3, approving as you go.

**Option C — parallel:** run **`relopass-conductor-check`** first. The three touch disjoint files (`test_drive.py` / `test_drive_emails.py` / `admin_feedback.py`), so it will likely recommend 3 parallel agents in isolated worktrees.

**Order matters only for TD-13** — it's the wave blocker. The other two can land in any order.

---

## Definition of done for this session
- [ ] TD-13 merged **and deployed** (required before the cohort link goes out)
- [ ] TD-12 merged — completion fires exactly one Resend send
- [ ] Feedback authoring module merged — you can log an issue with an uploaded *or* captured screenshot, and dispatch it to Notion in one pass
- [ ] `npm run build` clean · backend pytest green · one commit per task
- [ ] After deploy: re-run tester-zero's provision once to confirm auto-assign returns a corridor
