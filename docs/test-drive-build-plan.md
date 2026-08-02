# ReloPass Test-Drive — end-to-end build plan

**Owner:** Romain Lecomte · **Status:** Draft v1 · 2026-07-04
**Companion docs:** `beta-test-campaign-spec.md` (strategy + corridors), `test-drive-copy.md` (page + survey copy), `test-drive-invitation-message.md` (outreach).
**Goal of this doc:** turn the approved concept into a concrete, sequenced build — the process a tester moves through, and the tools required, mapped to what already exists in the repo vs what's net-new.

---

## 0. Principle: reuse first

Almost every piece you described already has a home in the codebase. The net-new work is small and specific. Reuse map at a glance:

| Capability you described | Already exists | Net-new |
|--------------------------|----------------|---------|
| Instructions + videos page | `GetStartedPage` + `PublicLayout` + `routes.ts` pattern | `/test-drive` route + content + video embeds |
| Login/password for both profiles | `/api/auth/register`, assignment-claim flow, `is_test` flag | one provisioning endpoint that creates **both** accounts + seeds + assigns corridor |
| HR creates company / assigns case | Full HR command center + assignment flow | nothing — this is the tester's task |
| Roadmap + vendor selection with cost | Employee journey, `vendor_curation`, recommendations engine | completion **detection** on that state |
| "Test complete" → survey | — | completion screen + `survey_responses` table + endpoint |
| Email to romain.lecomte@relopass.com | **Resend** path: `assignment_invite_email.py` → `_resend_send` (`RESEND_API_KEY`/`EMAIL_FROM`) | one notification composer |
| Thank-you email to tester | same Resend path | one thank-you composer |
| Admin dashboard | `AdminFeedback.tsx` pattern, `admin_prospects.py`, prospect CSV export | one results + contacts dashboard |
| Feedback widget + screenshots | `FeedbackWidget.tsx` + `feedback` table | campaign/corridor/segment tags |

**Net-new build = 2 tables, 1 provisioning endpoint, 1 survey endpoint, 2 email composers, 1 public page, 1 admin dashboard, 1 video pipeline.** That's it.

---

## 1. The tester lifecycle (the process, end to end)

Nine stages. Each names the system that drives it.

1. **Invite.** Romain sends the short message (`test-drive-invitation-message.md`) → link to `/test-drive`. Segment (`internal`/`prospect`) tagged at send.
2. **Instructions.** Tester lands on `/test-drive`: value prop, ~20-min estimate, sample-data reassurance, 3 short clips, assigned corridor.
3. **Provision.** Tester enters first name → one call generates **two** accounts (`HR-{name}-{suffix}`, `EMP-{name}-{suffix}`), both `is_test=true`, seeded, corridor pre-attached. Page shows both credential sets.
4. **HR steps.** Tester logs in as HR → creates the company → creates/assigns a case to the `EMP-*` employee, using the **assigned corridor's origin→destination** (the page tells them which).
5. **Employee steps.** Tester logs in as the employee → completes intake → reaches the roadmap → selects first vendor(s)/supplier(s) with an estimated cost.
6. **Completion.** When roadmap is in place **and** ≥1 vendor is selected with an estimated cost, the "I've completed my test" state unlocks → tester confirms.
7. **Survey.** Completion screen → 7 questions incl. testimonial, pilot interest, and intro (`test-drive-copy.md`).
8. **Fan-out (on submit).** (a) store `survey_responses`; (b) email Romain at romain.lecomte@relopass.com (incl. pilot-interest + testimonial + referral); (c) send tester the thank-you email; (d) if an intro was given, create a `prospect_candidates` row; (e) if pilot interest = Yes/Maybe, flag the tester's own row as a warm pilot lead.
9. **Review.** Romain opens the Admin → Test-Drive dashboard: the headline-numbers scorecard + funnel, results by corridor/segment, pilot leads, testimonials, and a contact list to action.

```
Invite → /test-drive → Provision (2 accounts) → HR: company + assign case
      → Employee: intake → roadmap → vendor+cost → Complete → Survey
      → [store · notify Romain · thank tester · referral→pipeline] → Admin dashboard
```

---

## 2. Tools to build

### 2.1 `/test-drive` public page  — *build (small)*
Clone the `GetStartedPage` + `PublicLayout` + `routes.ts` pattern; content in a new `testDriveContent.ts` from `test-drive-copy.md`. Sections: hero, what-we're-testing, how-it-works, about-the-data, videos, corridor label (+ Tier-B note), feedback reminder, provisioning block, start. Public route (`roles: ['PUBLIC']`). Tokenized for `{origin}`/`{destination}`/`{corridor}` so one page serves all six corridors.

### 2.2 Provisioning / credential generator — *build (medium — the core)*
New endpoint, e.g. `POST /api/test-drive/provision`.
- **Input:** first name, corridor_id (assigned by page), tester_segment.
- **Does:** create HR account + employee account (reusing `register`/user-creation), both `is_test=true`; generate random passwords; seed a fake company shell + the employee record so the corridor case is creatable; write a `test_sessions` row tying it together; return **both** username/password sets.
- **Corridor lock:** the case's origin/destination = the assigned corridor. Simplest reliable approach: page instructs HR which countries to pick; optionally pre-seed the case so country selection can't drift. (No per-tenant corridor toggle — that's explicitly out of scope per the spec.)
- **House rules:** rate-limit the endpoint (slowapi; it creates accounts) and campaign-gate it. Register the router in **both** `backend/main.py` **and** `backend/app/main.py` (CLAUDE.md hard rule — skipping `main.py` = 405 in prod). Import auth deps from `backend.app.auth_deps`.
- **UX risk to design for:** the tester juggles **two logins**. Show both credential blocks clearly, label which is HR vs employee, and add a one-line "you'll switch between these" note. Consider a "copy" button per credential.

### 2.3 Completion detection — *build (small)*
Define done = **roadmap generated AND ≥1 vendor/supplier selected with an estimated cost** for the seeded case.
- **Primary trigger:** the "I've completed my test" button (self-declared, simple).
- **Soft validation:** check case state (roadmap exists + vendor selection with cost, via the existing vendor/recommendations services) before accepting; if not reached, nudge ("looks like you haven't picked a vendor yet") but still allow. Avoids false "completed" while not hard-blocking.
- Writes `completed_at` + status on the `test_sessions` row.

### 2.4 Survey page + endpoint — *build (small)*
Completion screen → 7-question survey (`test-drive-copy.md`: overall, friction, problem-fit, one-change, **testimonial + consent**, **pilot interest**, **intro**). `POST /api/test-drive/survey` writes `survey_responses`, captures the testimonial/pilot/referral fields, and fires the fan-out (2.6). Same both-places router registration + auth-dep rules.

### 2.5 Feedback tagging — *build (tiny)*
Add `campaign`, `corridor_id`, `tester_segment` columns to the `feedback` table; have `FeedbackWidget.tsx` stamp them during a test session. Everything else in the widget already works (including screenshot capture via `html2canvas`).

### 2.6 Email fan-out — *build (small, pure reuse of Resend path)*
Two composers, both calling the existing `_resend_send` (never raises; logs when `RESEND_API_KEY` unset):
- **Notify Romain** → `romain.lecomte@relopass.com`: subject like "Test-drive completed — {name} ({corridor})"; body = segment, corridor, company/role, Q1–Q4 answers, **pilot interest (surfaced prominently)**, testimonial, and the referral if present. Set **reply-to** so Romain can act inline.
- **Thank the tester** → their survey email: warm, personal, "from Romain" (set `reply-to: romain.lecomte@relopass.com`). Matches the on-screen thank-you state in `test-drive-copy.md`.
- **Deliverability check (do first):** confirm `RESEND_API_KEY` + `EMAIL_FROM` are set in prod (there's already an admin email smoke-test endpoint), and confirm **romain.lecomte@relopass.com is a live mailbox** (note: `.com` on a different domain than the `noreply@relopass.com` sender — verify it receives).

### 2.7 Referral + pilot leads → pipeline — *build (small, reuses prospect pipeline)*
On survey submit: if Q7 has an intro, create a `prospect_candidates` row (`admin_prospects.py`) with `referred_by = {tester name/email}` + `corridor_id`. If Q6 pilot interest is `Yes`/`Maybe`, flag the **tester's own** row as a warm pilot lead (highest-value outcome — a tester wanting a pilot beats a cold referral). Both flow through the existing enrich → triage → export workflow.

### 2.7b Funnel instrumentation — *build (small, do NOT skip — see spec §6.1)*
The numbers Romain will quote to investors require the **whole funnel**, and top-of-funnel data can't be reconstructed later. Track, at minimum: **invites sent** (from the invite send, tagged by segment), **link clicks** (per-invite token or UTM on the `/test-drive` link), **provisioned** (`test_sessions` created), **completed** (`completed_at`), **surveyed** (`survey_responses`), **intros** and **pilot-interested**. A lightweight event log or counters on `test_sessions` is enough. Without invites-sent + clicks there is no conversion rate — the metric investors probe first.

### 2.8 Admin Test-Drive dashboard — *build (medium, clone AdminFeedback)*
New admin page (`roles` gated to ADMIN, like `AdminFeedback.tsx`). Panels:
- **Headline scorecard (top):** the 3 numbers Romain quotes — testers completed, % problem-fit (`Yes`+`Somewhat`), warm intros + pilot leads generated — plus the funnel (invited → clicked → provisioned → completed → surveyed → intro/pilot). This panel exists so the results are pitch-ready at a glance (spec §6.1).
- **Pilot leads:** testers who answered Q6 `Yes`/`Maybe`, with their company/role and note — the hottest follow-ups.
- **Testimonials:** Q5 responses **with quote consent**, ready to lift into a deck.
- **Results:** completions count, Q1 average, Q3 distribution, Q2/Q4 free-text feed — each **sliceable by corridor and by segment** (so Tier-A vs Tier-B and friend vs prospect are visible). This is how you rank which corridors are demo-ready.
- **Contact list:** referrals captured (name, company/role, how to reach, consent flag, who referred, corridor), with the existing **CSV export**. This is the campaign's primary yield.

### 2.9 Video clips (Playwright + voiceover) — *build (separate sub-project, §4)*
See §4 — it can run in parallel behind placeholders, so it never blocks launch.

---

## 3. Data model (net-new: 2 tables)

Both tables are in `public` → each **must** ship all three security gates or it fails review (CLAUDE.md hard gate): `ENABLE ROW LEVEL SECURITY`, at least one policy (admin-scoped read/write, mirror `feedback`/`ai_decisions` policies), and `REVOKE ALL ... FROM anon`. One idempotent migration file per the migration discipline; applied out-of-band, ledger reconciled.

**`test_sessions`** — ties a tester's two accounts + corridor + status together.
`id · first_name_label · hr_user_id · emp_user_id · hr_username · emp_username · corridor_id · tester_segment · campaign · status (started|completed) · started_at · completed_at`

**`survey_responses`** — one row per submitted survey.
`id · session_id (fk, nullable) · tester_name · tester_email · tester_company_role · tester_sector · corridor_id · tester_segment · campaign · q1_overall (int 1–5) · q2_friction (text) · q3_problem_fit (enum yes|somewhat|no) · q3_why (text) · q4_change (text) · testimonial (text) · testimonial_consent (bool) · pilot_interest (enum yes|maybe|no) · pilot_note (text) · referral_name · referral_company_role · referral_contact · referral_consent (bool) · created_at`

Add lightweight funnel counters/events (invites_sent, clicks) per §2.7b — on `test_sessions` or a small events table. Referral personal data + `Yes`/`Maybe` pilot leads also land in `prospect_candidates` (existing). Feedback stays in `feedback` (existing) + the 3 new tag columns.

---

## 4. The video pipeline (Playwright + voiceover)

You asked for clips generated with Playwright + voiceover. Here's how, plus an honest recommendation on scope.

**How it works:**
1. **Scripted walkthrough.** A Playwright script drives the *real* app through each flow against a seeded test account, and records video (Playwright's built-in `recordVideo` → webm). Three scripts: (a) register/log in with the generated credentials, (b) HR — create company + assign case, (c) employee — intake → roadmap → vendor+cost.
2. **Voiceover.** Write a short narration script per clip; generate audio via a TTS API (OpenAI TTS or ElevenLabs) → mp3.
3. **Mux.** Combine video + audio with `ffmpeg`, trim/pace, add captions, export mp4.
4. **Host.** Drop the mp4s in `frontend/public` (or a bucket) and embed on `/test-drive`.

**Tradeoffs — read before committing:**
- **For:** reproducible and *regeneratable* when the UI changes (big win for an evolving MVP across 6 corridors), consistent, no manual re-recording.
- **Against:** setup + audio-sync effort, TTS can sound robotic, scripts break when selectors change (maintenance).

**Recommendation — stage it, don't over-engineer:**
- **v1 (launch):** silent Playwright screen-capture with **on-screen captions** (no voiceover). Fastest path to a working page; captions are enough for "how to register / basic steps."
- **v2:** add TTS voiceover to the same recordings once flows are stable.
- **Consider a human Loom for the 60-sec overview only** — the warm "why this matters" clip benefits from a real voice; the mechanical how-tos are perfect for Playwright.

This keeps videos off the critical path: ship `/test-drive` with placeholder/caption clips, upgrade them without touching the rest.

---

## 5. Build sequence

| Phase | Deliverable | Notes |
|-------|-------------|-------|
| **0** | Deliverability + mailbox check; confirm `RESEND_API_KEY`, `EMAIL_FROM`, and that romain.lecomte@relopass.com receives | 1 hour; unblocks all email work |
| **1** | `test_sessions` + `survey_responses` migrations (RLS gates) + provisioning endpoint + credential display | the core; register routers in both apps |
| **2** | `/test-drive` page + content + caption-only video placeholders | clones `GetStartedPage` |
| **3** | Completion detection + survey page/endpoint + email fan-out + referral→pipeline | the payoff wiring |
| **4** | Admin Test-Drive dashboard (results + contacts + CSV) | clones `AdminFeedback` |
| **5** | Playwright video pipeline (v1 captions → v2 voiceover) | parallel; never blocks launch |
| **Pilot** | Run all of it with **3 people** (1 Tier-A, 1 Tier-B, 1 free) before inviting the cohort | the provisioning endpoint *will* break on first real run |

---

## 6. Key decisions (need Romain's call)
1. **Time estimate in the invite:** recommended **state "~20 minutes"** (see invitation doc) — confirm.
2. **Video scope:** v1 captions-only now, voiceover later (recommended) — or hold launch for full voiceover?
3. **Corridor case creation:** instruct HR to pick the corridor countries, or pre-seed the case so it can't drift? (Pre-seed is safer; slightly less "HR did it themselves.")
4. **Completion:** self-declared button only, or button + soft state-validation (recommended)?
5. **Tier-B corridors:** still test on fallback now (spec default), or build the 3 configs first?

---

## 7. Risks
- **Two-login friction** (HR↔employee switching) is the biggest UX risk — mitigate with a clear dual-credential display and a "switch profile" note.
- **Email deliverability** — sender is `noreply@relopass.com`; make sure the notify address (`.com`, romain.lecomte) actually receives, and set reply-to on the thank-you so tester replies reach Romain.
- **Referral = third-party PII.** A tester hands you a contact who hasn't consented. Capture minimally (name, company/role, suggested contact), rely on the tester's attribution consent for outreach framing, and when enriching via the prospect pipeline follow the `pii_masker` rule (CLAUDE.md: no raw PII in LLM prompts). Note this in the privacy register if referrals become a standing feature.
- **Test data hygiene** — every account/company `is_test=true` so `test_data_filter.py` keeps them out of prod dashboards; plan a post-campaign wipe.
- **Provisioning abuse** — the endpoint creates accounts; rate-limit + campaign-gate it.

---

## 8. Env vars touched
`RESEND_API_KEY`, `EMAIL_FROM` (email fan-out) · `APP_WEB_BASE_URL` (links) · plus a TTS key (`OPENAI_API_KEY` already present, or ElevenLabs) if/when voiceover is added.
