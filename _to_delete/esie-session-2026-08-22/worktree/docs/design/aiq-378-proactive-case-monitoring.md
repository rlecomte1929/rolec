# AIQ-378 — Proactive immigration case-monitoring loop ("Claude Dreaming")

**Status:** Design / decomposition (parent is `Needs Decomposition`, gated on the P6-1 pilot).
**Priority:** P1 · **Product Area:** AI Layer · **Complexity:** High (as an epic).

> **Hard gate (from the task's own Technical Constraints):** *"Post-pilot only — needs
> real case history to be useful. Do not build before first pilot case is live."* The
> P6-1 pilot has not run and the relevant tables are empty (0 specialist reviews, <20
> closed cases). This document **decomposes** the epic so it is ready to execute once
> the pilot is live; it does not authorize building before then.

---

## 1. What it is

A nightly background loop that reviews **active** immigration cases, flags the ones
**behind their expected schedule**, and surfaces a proactive HR alert the next morning
naming **which case**, **what stage**, and a **suggested action** (an auto-drafted
reminder). The strategic objective is the AI moat: proactive intelligence vs. the
competition's reactive chatbots.

## 2. Key design decision — no unverified SDK on the critical path

The task nominally "requires Claude Managed Agents SDK + 'Dreaming' (May 2026)". That
capability is **not assumed** for the MVP and is **not on the critical path**. The
entire validation criterion is deliverable with primitives that **already exist in the
repo today** — most landed in the P3-02 source-monitoring work:

| Need | Existing primitive (on `main`) |
|---|---|
| Scheduled trigger | `backend/app/routers/crons.py` (`process_crawl_schedules` is the template; `_verify_cron_secret` guard) + a daily GitHub Actions workflow (`crawl-scheduler.yml` pattern) |
| Aggregate active-case signal → deduped admin alert | `case_staleness_alert.py` (the exact analog) + `ops_notification_service.create_or_update_notification` / `_build_dedupe_key` |
| Slack + email delivery | `monitoring_alerts.py` (P3-02c) |
| Active-case + milestone/expected-date data | `cases_read.py`, `hr_case_detail.py`, `immigration_status.py` (`status = 'active'`) |

**"Dreaming / Managed Agents" is scoped as a later *enhancement* to the suggested-action
draft step (subtask c), not a requirement for the MVP.** It will only be adopted once the
exact feature shape is verified against current Anthropic docs.

## 3. Architecture (MVP, deterministic)

```
[daily GH workflow]
   └─ POST /api/crons/case-health-scan   (CRON_SECRET-guarded, route-auth allowlisted)
        └─ case_delay_monitor.scan_active_cases()        # subtask (a) — read-only signal
             ├─ for each active case: compute days_behind vs expected milestone date
             └─ returns flagged[] = {case_id, stage, expected_date, days_behind, severity}
        └─ for each flagged case:                        # subtask (b) — dispatch
             ├─ suggested = build_suggested_action(case) # subtask (c) — template (MVP) / LLM (enh.)
             ├─ ops_notification_service.create_or_update_notification(
             │      type="case_behind_schedule", dedupe_key=case_id, ...)   # deduped, one per case
             └─ monitoring_alerts.dispatch(...)          # Slack + email (best-effort)
[HR surface]                                             # subtask (d)
   └─ "Case health" panel: flagged cases + suggested actions (read from ops_notifications)
```

Design rules carried from `case_staleness_alert.py`:
- **Read-only + inert without data.** Zero active cases → zero alerts. Safe to ship dormant.
- **Deduped, best-effort alerts.** One open notification per case; alert failures never
  break the scan (mirrors `dead_link_service` / `monitoring_alerts`).
- **MVP manual-then-cron.** Land the service behind an admin endpoint first
  (`POST /api/admin/cases/health-scan/run`), then schedule it — same path P2-08e and
  P1-08d took. `TODO [AIQ-378-b]` marks the scheduler hook.
- **Honest signals only.** "days_behind" is computed from real milestone/expected-date
  data; no fabricated ETAs. If a case has no expected date, it is not flagged.

## 4. Decomposition — atomic subtasks

> Sequence: **a → b → (c, d)**; **e** is the post-pilot gate. Subtasks a–d are
> *data-safe to build dormant* but remain **gated by the parent's "post-pilot" constraint** —
> file them as `Backlog`, promote to `Ready for AI` when the team starts the epic.

### (a) Case-delay signal service — Backend, Medium
- **Expected output:** `backend/app/services/case_delay_monitor.py` — `scan_active_cases()`
  returning flagged cases `{case_id, stage, expected_date, days_behind, severity}` for every
  active case past its expected milestone date. Pure/read-only; mirrors `case_staleness_alert.py`.
  Configurable `CASE_DELAY_WARN_DAYS` (default e.g. 3) via env, clamped.
- **Validation:** unit tests over fixture cases (on-time → not flagged; N days late → flagged
  with correct `days_behind`; no expected date → not flagged); returns `[]` on an empty/active-less DB.
- **Depends on:** the case milestone/expected-date model (confirm the exact column during recon).

### (b) Nightly scan cron + alert dispatch — Backend, Medium · depends on (a)
- **Expected output:** `POST /api/crons/case-health-scan` in `crons.py` (CRON_SECRET inline guard,
  added to `scripts/route_auth_allowlist.txt`); `.github/workflows/case-health-scan.yml` (daily,
  gated behind a repo var). Calls (a), creates a deduped `ops_notification` (`type="case_behind_schedule"`,
  dedupe key = case_id) per flagged case, and dispatches Slack/email via `monitoring_alerts`. Also a
  manual `POST /api/admin/cases/health-scan/run` for staging.
- **Validation:** `test_cron_case_health_scan.py` — secret enforcement (503/401/200); a seeded
  behind-schedule case produces exactly one ops_notification; re-run dedupes (no duplicate).
- **Deploy:** reuse `CRON_SECRET`; add `CASE_HEALTH_CRON_ENABLED` repo var.

### (c) Suggested-action / auto-draft reminder — Backend/AI, Medium · depends on (a)
- **Expected output (MVP):** `build_suggested_action(case)` — a deterministic, per-stage suggested
  action + a templated draft reminder string, attached to the alert payload.
- **Enhancement (separate, later):** swap the template for an LLM-drafted reminder (Claude API),
  and — only if/when the feature shape is verified — a Managed-Agents/"Dreaming" delivery. Gated
  behind a flag; never fabricates case facts (drafts only from real case fields).
- **Validation:** template produces a stage-appropriate action for each stage; LLM path (if built)
  is flagged off by default and unit-tested with a mocked client.

### (d) HR surface for flagged cases — Frontend, Medium · depends on (b)
- **Expected output:** a "Case health" panel surfacing behind-schedule cases + suggested actions,
  reading from the `case_behind_schedule` ops_notifications. Natural home: the HR policy dashboard
  (`/hr/policy-dashboard`, AIQ-239, just shipped) or the admin review queue. `RequireHrRoute`-gated.
- **Validation:** panel lists flagged cases with stage + days_behind + suggested action; empty state
  when none; tsc + build clean.

### (e) Post-pilot end-to-end validation — Research, **Blocked on P6-1** · depends on (a)-(d)
- **Expected output:** run the full loop against **real pilot cases**; confirm the parent
  Validation Criteria: *"Agent runs on schedule. Cases behind on expected dates trigger a proactive
  HR alert next morning with: which case, what stage, suggested action."*
- **Blocker:** needs the P6-1 pilot live + real case history. This is the epic's true `Done` gate.

## 5. Open decisions for the team
1. **Expected-date source of truth** — confirm which field/table holds a case's expected milestone
   date (candidates: `case_milestones`, `immigration_status`, a per-stage SLA). Subtask (a) keys off this.
2. **"Dreaming / Managed Agents"** — confirm the current Anthropic feature shape before adopting it
   in (c); the MVP ships without it. Treat as an enhancement spike, not a dependency.
3. **Alert cadence / severity tiers** — single nightly digest vs. per-case alerts; warn vs. critical
   thresholds (`days_behind`).

## 6. Why this respects the gate
Nothing here builds the loop before the pilot. The deliverable is the **plan**: a design + 5
ready-to-execute subtasks grounded in existing primitives, so that the moment the first pilot case
is live, execution is mechanical (a → b → c/d → e) with no unverified-SDK risk on the critical path.
