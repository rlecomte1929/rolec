# Overnight run — summary — 2026-06-03

Autonomous overnight run against the MVP critical path (`audit/mvp-3-week-plan-2026-06-02.md`)
and the Notion AI Work Queue. No PRs were merged (merging is left for human review). No prod
writes were made. All work shipped as branches/PRs or recorded as verification findings.

---

## Headline findings (read these first)

### 1. MVG-6D — the #1 MVP gate — is LIVE and contract-consistent ✅
The plan's biggest open unknown ("MVG-6D current state — needs verification today", §5 Q3)
is **green at the code/contract level**:

- `POST /api/hr/immigration/cases` (create) — `immigration_status.py:263`
- `GET /api/hr/immigration/cases/{id}` — `immigration_status.py:336`
- `GET /api/employee/cases/{case_id}/immigration` — `immigration_status.py:359`
- milestones GET/POST/PATCH (status timeline) — `immigration_status.py:54–157`

All registered in **both** `backend/main.py:696` and `backend/app/main.py:100`, and confirmed
present in the prod app route table (`from backend.main import app`).

Frontend ↔ backend contract verified field-by-field on the create path:
- Screen 1 `ImmigrationCaseCreatePage.tsx:130` → all 7 body fields match `ImmigrationCaseCreate`.
- permit_type enum matches exactly on both sides: `eu_blue_card, work_permit, skilled_worker_visa, eea_registration, other`.
- Screen 2 `ImmigrationChecklistPage.tsx:99` and Screen 3 `ImmigrationCasePage.tsx:89` paths match.

**Still needed (not safe to do autonomously):** a real HR-create → employee-upload → HR-monitor
write-cycle smoke on prod, per corridor (DE/FR/GB). That requires prod writes — left for a
supervised session.

### 2. PR #235 is MVP-critical, not just hygiene — prioritize its merge ⚠️
PR #235 (open, CI-clean) restores 17 routers that are **currently returning 405 in production**.
Four of them back live, frontend-called MVP surfaces (verified absent from the prod route table
on `main`, and each is called by a frontend `api.*` wrapper):

| Router | Dead endpoint (405 today) | Frontend caller | MVP impact |
|---|---|---|---|
| `marketplace` | `GET /api/employee/assignments/{id}/marketplace` | `src/api/marketplace.ts:42` | **Employee service selection — plan §1 step 5** |
| `hr_analytics` | `GET /api/hr/policy-compliance-matrix` | `src/api/hrAnalytics.ts:65` | HR command center |
| `relocation_profile` | `GET/PUT /api/employee/cases/{id}/relocation-profile` | `src/api/relocationProfile.ts:115` | Employee profile |
| `advisors` | `POST /api/advisors/match` | `src/api/advisors.ts:49` | Immigration advisor matching |

Root cause: the "AUDIT-C2.3 Month-1 → moved to backend/app/main.py" comments in `backend/main.py`
are wrong — the modular `app/` app is **not mounted** into `backend/main.py`, so a router
registered only there is never served (the documented CLAUDE.md footgun). PR #235 re-adds the
`include_router` calls. **Recommend merging #235 first** — it un-breaks the employee
service-selection step the MVP demo depends on.

---

## PR status (updated 2026-06-03 — post user-authorized merge session)

### Merged to main this session
- **#235** — restore 17 unregistered routers (405 fix). **MERGED** (`4a8629a5`) after resolving a
  `backend/main.py` conflict (kept both main's 9 Parker routers and #235's 3 restored policy
  routers). All 4 MVP-critical routes verified present (marketplace, policy-compliance-matrix,
  relocation-profile, advisors/match); router-registration check + full CI green. **This un-breaks
  the employee service-selection step the MVP demo depends on.**
- **#236**, **#237** — already merged earlier (04:36–04:37): `canonical_policy_facts_tier`
  replay-safe guard and AIQ-225 Policy & Benefits Summary tab.

### Open
- **#238** (NEW) — `fix(migrations): guard friction_analysis constraint for replay order`.
  Drains the *next* Supabase Preview landmine after #236: `20260523020000` ALTERs
  `public.daily_summaries` but that table is created by the later-sorted `20260524000001` → fresh
  replay aborts with 42P01. Guarded on `to_regclass` (#236 pattern). Prod-verified safe (table
  present, CHECK already has `friction_analysis`, migration name absent from
  `schema_migrations`). Awaiting Preview result — may go green or simply advance to the deferred
  `_remote_stub` wall (`20260531010000`), which is post-MVP per plan §2.
- **#233** (AIQ-633 specialist-review page) — **CONFLICTS RESOLVED + MERGEABLE; held pending #238.**
  Merged `origin/main` (commit `9d4cea5`); two additive conflicts resolved (kept both sides).
  Confirmed it contains #236's fix. All real gates pass (backend, frontend, tsc, 6 vitest,
  Cloudflare, Vercel). **Only red check is Supabase Preview** — and it is a *pre-existing,
  unrelated* main replay-ordering bug (the friction/`daily_summaries` landmine #238 fixes), NOT a
  feature defect. **Correction to earlier park diagnosis** (was wrong): the broken
  `20260427100000_exception_requests.sql` migration is already removed by the merge. Per user
  decision, fixing the replay bug (#238) comes first, then #233 merges. Correction comment:
  [issuecomment-4609159208](https://github.com/rlecomte1929/rolec/pull/233#issuecomment-4609159208).
- **#229** — parked earlier; Supabase Preview gated on the deferred `_remote_stub` backfill.
  Merge decision is human's, on strength of passing GitHub Actions gates.

---

## Flagged follow-ups (not filed as tasks)
- AIQ-225 omits a policy-document footer link — the `/api/policy/summary` contract carries no
  doc URL field. Add the field server-side if HR wants the source doc linked from the summary.
- `test_policy_summary` has an expired-banner date-logic assertion bug on `main` (pre-existing).
- 9 `exception_requests_router` test failures on `main` (pre-existing).

## Notes on the work queue
Notion semantic search can't filter by `Status`, and the freshest-edited entries (2026-06-02
timestamps) were a bulk re-index of already-Done/Archived tasks (P9-2, P2-3, AIQ-633, AIQ-680
all Done/Archived). No clearly-unblocked "Ready for AI" frontend task was identifiable without
a status-filtered view — worth opening a saved "Ready for AI" view in Notion for the next run.
