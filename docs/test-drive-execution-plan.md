# ReloPass Test-Drive — execution plan

**Owner:** Romain · **Status:** Ready to launch · 2026-07-04
**Reads with:** `beta-test-campaign-spec.md` (strategy), `test-drive-build-plan.md` (architecture), `test-drive-copy.md` (page + survey), `test-drive-invitation-message.md` (outreach).
**Purpose:** the operational plan — every build item as an atomic Work Queue task, tiered against the canonical Autonomy rubric, routed to the right skill and environment, sequenced to hit the **15 Jul pilot**.

---

## 0. How execution runs (routing model)

This build is mostly **code**, so it runs where code runs — **Claude Code with the repo mounted**, via the dev-queue / fix-* skills — not unattended from Cowork. The split:

| Work | Environment | Driver |
|------|-------------|--------|
| Notion queue setup, copy, invite, this plan | **Cowork** | `notion-task-executor` / direct Notion MCP |
| All code tasks (migrations, endpoints, page, dashboard) | **Claude Code** (repo mounted) | `relopass-dev-queue` + layer skills |
| Video asset generation | Cowork or Claude Code | Playwright + ffmpeg |
| Queue close-out | Either | `relopass-review-validator` |

**Hard rule (from the rubric):** code is never shipped unattended from Cowork. The 🔴 Red tasks below (migration, provisioning, email) keep the full plan gate **and** human review — you approve the plan before any code is written, and again at review.

**AI Work Queue:** collection `4e2887c6-4d48-82c1-931e-87b09fb5c4ed` · DB `3bc887c64d4880898188fcf2dc3edc1b`.
**Lifecycle:** Needs Decomposition → Ready for AI → AI in Progress → Human Review → Validation → Done.

---

## 1. Tools & skills inventory

**Skills**
- `notion-decomposition` — break this plan into Work Queue tasks (or create directly).
- `relopass-conductor-check` — assess parallel execution once ≥2 Yellow code tasks are ready.
- `relopass-dev-queue` — the 6-phase executor for every code task (recon → plan → build → tsc/pytest → Notion → git commit).
- `relopass-fix-api-bug` / `relopass-fix-ui-bug` / `relopass-fix-isolation-bug` — layer-specific executors (isolation = RLS, always Red).
- `relopass-autopilot` — can clear the 🟢/🟡 lane unattended **after** the Red tasks are approved and merged.
- `relopass-review-validator` — auto-Dones self-validated Yellow, surfaces exceptions + 15% audit.
- `relopass-e2e-test` / `relopass-test-campaign` — full regression before the pilot.
- `relopass-qa-url-verify` — verify `/test-drive` + the admin dashboard render post-deploy.
- `relopass-brand-voice` — already applied to copy; re-run on any new UI strings.

**MCP tools**
- **Notion** — create/query/update Work Queue tasks.
- **Supabase** — `list_tables`, `get_advisors` (verify RLS coverage after the migration), `execute_sql` (read/backfill only); `apply_migration` is the **operator step** you run out-of-band per migration discipline, then reconcile the ledger with the committed file.
- **Resend** (via backend code) — `RESEND_API_KEY` + `EMAIL_FROM`; the existing admin **email smoke-test** endpoint is the preflight.
- **Chrome MCP / Playwright** — video capture + URL QA. **ffmpeg** + a TTS key (OpenAI TTS) for voiceover v2.
- **Git + `no-mistakes` gate** — every code task ends in a commit (dev-queue Phase 7).

**Dev tools:** `npx tsc --noEmit`, `npx vitest`, `pytest`, `uvicorn`, `npm run build` (pre-push hook must pass).

---

## 2. Preflight gate (do before any build) — TD-0

Not a code task; a 30-minute check that unblocks the email work and prevents a dead pilot:
- Confirm `RESEND_API_KEY` + `EMAIL_FROM` are set in prod (run the admin email smoke-test endpoint).
- Confirm **romain.lecomte@relopass.com is a live mailbox that receives** (different address from the `noreply@relopass.com` sender — this is where completion notifications land).
- Confirm `APP_WEB_BASE_URL` = `https://relopass.com`.
- Decide the **branch** for the campaign (e.g. `feat/test-drive-campaign`) so all tasks land together for one PR review.

---

## 3. The work breakdown (atomic Work Queue tasks)

Eleven tasks. Tiers follow the canonical rubric: **Database Migration + RLS + auth + external email = 🔴 Red** (full gate); test-covered frontend/backend at ≤Medium = 🟡 Yellow (self-validate + audit); offline assets = 🟢 Green.

| ID | Task | Layer | Tier | Executor skill | Depends on |
|----|------|-------|------|----------------|-----------|
| **TD-1** | Schema migration — all tables + columns | Migration / Isolation | 🔴 **Red** | `fix-isolation-bug` / dev-queue (Red gate) | — |
| **TD-2** | Provisioning endpoint (dual-account + seed + corridor) | API (auth surface) | 🔴 **Red** | `fix-api-bug` / dev-queue (Red gate) | TD-1 |
| **TD-3** | `/test-drive` page + content + dual-credential UI | UI | 🟡 Yellow | `fix-ui-bug` | TD-2 |
| **TD-4** | Completion detection (roadmap + vendor+cost) | API + UI | 🟡 Yellow | `dev-queue` | TD-2 |
| **TD-5** | Survey page + endpoint (7 Q incl. testimonial/pilot/sector) | UI + API | 🟡 Yellow | `dev-queue` | TD-1, TD-3, TD-4 |
| **TD-6** | Email fan-out — notify Romain + thank tester | API (external send) | 🔴 **Red** | `fix-api-bug` / dev-queue (Red gate) | TD-5 |
| **TD-7** | Referral + pilot → `prospect_candidates` | API | 🟡 Yellow | `fix-api-bug` | TD-5 |
| **TD-8** | Funnel instrumentation (invites, clicks, stage events) | API | 🟡 Yellow | `dev-queue` | TD-1 |
| **TD-9** | Feedback widget campaign/corridor/segment stamp | UI | 🟡 Yellow | `fix-ui-bug` | TD-1 |
| **TD-10** | Admin Test-Drive dashboard (scorecard + funnel + leads + testimonials + CSV) | UI | 🟡 Yellow | `fix-ui-bug` | TD-5, TD-7, TD-8 |
| **TD-11** | Video clips — Playwright capture, v1 captions | Asset | 🟢 Green | Playwright + ffmpeg | (parallel) |

### Task detail (the parts the executor must not miss)

**TD-1 — Schema migration (🔴 Red).** One idempotent migration file covering: `test_sessions`, `survey_responses` (with `tester_company_role`, `tester_sector`, testimonial + consent, pilot_interest + note, referral fields), funnel event/counter storage, and the `campaign`/`corridor_id`/`tester_segment` columns on `feedback`. **Hard gates (CLAUDE.md):** every new `public` table gets `ENABLE ROW LEVEL SECURITY` + ≥1 admin-scoped policy (mirror `feedback`/`ai_decisions`) + `REVOKE ALL … FROM anon`. Migration discipline: commit the file, apply out-of-band, reconcile the ledger. **Validate:** Supabase `get_advisors` shows no RLS warnings; `list_tables` shows both tables; anon cannot select.

**TD-2 — Provisioning endpoint (🔴 Red).** `POST /api/test-drive/provision`: first name + corridor_id + segment → create `HR-{name}-{suffix}` + `EMP-{name}-{suffix}` (reuse `register`/user-creation), both `is_test=true`, seed fake company + employee so the corridor case is creatable, write `test_sessions`, return both credential sets. **House rules:** rate-limit (slowapi) + campaign-gate; **register the router in BOTH `backend/main.py` AND `backend/app/main.py`**; import auth deps from `backend.app.auth_deps`. **Validate:** `pytest` new test; route-presence check `python3 -c "from backend.main import app; print([r.path for r in app.routes if 'test-drive' in r.path])"` shows the route (or it 405s in prod).

**TD-3 — `/test-drive` page (🟡).** Clone `GetStartedPage` + `PublicLayout`; `testDriveContent.ts` from `test-drive-copy.md`; `roles: ['PUBLIC']`; tokenized `{origin}/{destination}/{corridor}`; Tier-B early-coverage label; **dual-credential display with copy buttons + "you'll switch between these" note** (the two-login UX risk); video embeds (placeholders until TD-11). **Validate:** `tsc --noEmit` + `vitest`; form calls TD-2; both creds shown.

**TD-4 — Completion detection (🟡).** "I've completed my test" unlocks on **roadmap generated AND ≥1 vendor selected with estimated cost** (soft-validate via existing vendor/recommendations services; nudge but don't hard-block); write `completed_at` to `test_sessions`.

**TD-5 — Survey (🟡).** 7 questions per copy; `POST /api/test-drive/survey` writes `survey_responses`; fires fan-out (TD-6) + pipeline (TD-7). Both-apps router registration + `auth_deps`.

**TD-6 — Email fan-out (🔴 Red — external send).** Two composers on the existing `_resend_send`: notify romain.lecomte@relopass.com (segment, corridor, company/role/sector, Q1–Q4, **pilot interest prominent**, testimonial, referral; reply-to set) + thank tester ("from Romain", reply-to romain.lecomte). **Validate:** pytest with `RESEND_API_KEY` unset → status `logged` + correct rendered content.

**TD-7 — Referral + pilot → pipeline (🟡).** Intro → `prospect_candidates` row (`referred_by` + `corridor_id`); pilot `Yes`/`Maybe` → flag tester's own row as warm lead. Reuses `admin_prospects.py`.

**TD-8 — Funnel instrumentation (🟡).** Record invites-sent (tagged by segment), `/test-drive` link clicks (per-invite token / UTM), and stage events (Start, HR-handoff, intake, roadmap, vendor, completed, surveyed). Powers the headline numbers — **do not skip**; top-of-funnel is unrecoverable later.

**TD-9 — Feedback stamp (🟡).** `FeedbackWidget.tsx` stamps `campaign`/`corridor_id`/`tester_segment` during a session (columns from TD-1).

**TD-10 — Admin dashboard (🟡).** Clone `AdminFeedback.tsx`, ADMIN-gated. Panels: headline scorecard + funnel; pilot leads; testimonials (consented); results sliceable by corridor + segment; contact list with CSV export.

**TD-11 — Video clips (🟢).** Playwright drives the seeded flows (register/login, HR create+assign, employee intake→roadmap→vendor), records → captions via ffmpeg → mp4 in `frontend/public`. v2 (post-launch): TTS voiceover. Human Loom for the 60-sec overview only.

---

## 4. Dependency graph + critical path

```
TD-1 (Red) ─┬─ TD-2 (Red) ─┬─ TD-3 ─┐
            │              └─ TD-4 ─┼─ TD-5 ─┬─ TD-6 (Red) ─┐
            ├─ TD-8 ───────────────┘         ├─ TD-7 ───────┼─ TD-10
            └─ TD-9                            └─────────────┘
TD-11 (Green) ───────────────────────────── parallel, embeds into TD-3
```

**Critical path (must be serial):** TD-1 → TD-2 → TD-3/TD-4 → TD-5 → TD-6/TD-7 → TD-10.
**Parallel tracks:** TD-8, TD-9 (after TD-1); TD-11 (anytime).

**Sequencing to 15 Jul (pilot = 3 people):**
- **Day 1–2:** TD-0 preflight → TD-1 (Red gate) → TD-2 (Red gate). These two unblock everything; get the gates done first.
- **Day 3–5:** TD-3, TD-4, TD-8, TD-9 in parallel (Conductor candidates) → TD-5.
- **Day 6–7:** TD-6 (Red gate) + TD-7 → TD-10. TD-11 clips folded in.
- **Day 8 (~13–14 Jul):** `relopass-e2e-test` full regression + `qa-url-verify` on `/test-drive` and the dashboard.
- **15 Jul:** pilot with 3 (1 Tier-A, 1 Tier-B, 1 free). Fix what breaks. Full wave ~18–20 Jul.

---

## 5. Your decision points (the Red gates)

Autopilot/self-validation handles the Yellow + Green lane. **You personally gate exactly three tasks** — each pauses for plan approval before code, and again at review:

1. **TD-1 — the migration + RLS.** Because a missing policy = the SEC-002 GDPR incident. Approve the RLS policies and the anon revoke.
2. **TD-2 — the provisioning endpoint.** Because it creates auth accounts and is a public abuse surface. Approve the rate-limit + campaign-gate + both-apps registration.
3. **TD-6 — the email fan-out.** Because it sends external mail on your behalf. Approve the recipients, from/reply-to, and content.

Everything else (TD-3, 4, 5, 7, 8, 9, 10) is 🟡 Yellow: it self-validates against its Test Command, lands in Human Review, and `review-validator` auto-Dones it unless it's in the ~15% audit sample. TD-11 is 🟢 Green.

---

## 6. Parallelization (Conductor)

Once TD-1 + TD-2 are merged, TD-3 / TD-8 / TD-9 are independent Yellow code tasks touching different files — a clean parallel set. Run `relopass-conductor-check` at that point; if it says "Parallel ⚡", it emits per-agent briefs you paste into Conductor (isolated worktrees). If sequential, dev-queue runs them in order. Don't parallelize TD-1/TD-2 — they're the shared foundation.

---

## 7. Validation & close-out

- **Per task:** dev-queue Phase 5 runs the Test Command + checks each Validation Criterion with evidence; Phase 7 commits through the `no-mistakes` gate.
- **Per Yellow batch:** `review-validator` auto-Dones passed tasks, surfaces exceptions + audit sample.
- **Before the pilot:** `relopass-e2e-test` (regression vs May baseline) + `relopass-qa-url-verify` on the two new URLs. Confirm `npm run build` is clean (pre-push hook).
- **Data hygiene:** every provisioned account/company is `is_test=true`; confirm `test_data_filter.py` keeps them out of prod dashboards; schedule a post-campaign wipe.

---

## 8. Launch checklist (what "go" looks like)
- [ ] TD-0 preflight passed (email receives, env set, branch chosen)
- [ ] TD-1, TD-2, TD-6 Red gates approved and merged
- [ ] Yellow lane (TD-3,4,5,7,8,9,10) Done via dev-queue + review-validator
- [ ] TD-11 clips embedded (captions v1)
- [ ] e2e-test green + `/test-drive` and dashboard QA-verified
- [ ] Corridor assignment (round-robin, Tier-A weighted) wired into provisioning
- [ ] Invitation message finalized; segment tags ready; 48-hour follow-up template drafted
- [ ] Pilot 3 recruited for 15 Jul

---

## 9. How to launch execution

Two clean ways to kick off, in order:

1. **Create the queue** — I create TD-1…TD-11 in the AI Work Queue (Notion) with Layer, Autonomy Tier, Dependencies, Expected Output, Validation Criteria, and a Test Command per task. (Cowork step.)
2. **Build in Claude Code** — open a Claude Code session on the campaign branch and run `relopass-dev-queue`: it auto-selects TD-1 first, pauses for your Red-gate approval, then works down the graph. After TD-1/TD-2, run `relopass-conductor-check` to parallelize the Yellow set. Clear the remaining Yellow lane with `relopass-autopilot` if you want it hands-off.

Say the word and I'll do step 1 now — create all eleven tasks in the queue, correctly tiered and sequenced.
