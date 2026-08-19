# AIQ-2012 — the crawl scheduler works. Seven cron gates were never set.

**Audited:** 2026-08-19

The task asked whether the crawl scheduler runs on a cadence, and expected one of two answers:
wire a runner, or declare crawling manual-by-design. The truth is a third thing.

**A runner exists, is correct, and fires daily. It has been skipping silently since it was
created, because one repo variable was never set.** And it is not alone.

---

## 1. The crawl scheduler is not broken

Everything it needs is built:

| piece | state |
|---|---|
| `.github/workflows/crawl-scheduler.yml` | exists, `cron: "0 3 * * *"` |
| workflow actually firing | **yes** — 8 consecutive daily runs Aug 12–19 |
| `POST /api/crons/process-crawl-schedules` | exists (`crons.py:270`), `_verify_cron_secret`-guarded, per-schedule job locks, never raises on a single failure |
| `secrets.CRON_SECRET` | **configured** (2026-07-07) |
| `vars.CRAWL_CRON_ENABLED` | **NOT SET** |
| `vars.CRAWL_API_BASE` | **NOT SET** |

Every one of those 8 runs completed with conclusion **`skipped`**. The job carried
`if: ${{ vars.CRAWL_CRON_ENABLED == 'true' }}`, so with the variable unset the entire job
never ran.

Meanwhile the three schedules have been **due for two months**:

```
auto-tier::tier-1-critical   next_run_at 2026-06-18   last_run_at NULL
auto-tier::tier-1-stable     next_run_at 2026-06-22   last_run_at NULL
auto-tier::tier-2            next_run_at 2026-07-01   last_run_at NULL
```

3 job runs exist; **0** carry a `schedule_id`. Every crawl to date was manual.

## 2. The real finding: a skipped cron is indistinguishable from a working one

In the Actions UI a skipped job shows as **completed**. There is no badge, no warning, no
difference in colour between "ran and succeeded" and "did nothing for two months".

So this is not a crawl-scheduler bug. It is a class. Auditing every `*_CRON_ENABLED` gate
against the repo's actual variables:

| workflow | gate variable | value |
|---|---|---|
| compliance-daily | `COMPLIANCE_CRON_ENABLED` | `true` |
| outbox-dispatch | `OUTBOX_DISPATCH_CRON_ENABLED` | `true` |
| reliability-recompute-daily | `RELIABILITY_CRON_ENABLED` | `true` |
| vendor-metric-snapshot-daily | `VENDOR_SNAPSHOT_CRON_ENABLED` | `true` |
| autopilot-nightly | `AUTOPILOT_CRON_ENABLED` | `false` (deliberate) |
| **case-health-scan** | `CASE_HEALTH_CRON_ENABLED` | **NOT SET** |
| **catalog-promotion** | `CATALOG_PROMOTION_CRON_ENABLED` | **NOT SET** |
| **coordinator-proactive-scan** | `COORDINATOR_PROACTIVE_CRON_ENABLED` | **NOT SET** |
| **crawl-scheduler** | `CRAWL_CRON_ENABLED` | **NOT SET** |
| **hr-mobility-briefing** | `HR_BRIEFING_CRON_ENABLED` | **NOT SET** |
| **roadmap-review-notify** | `ROADMAP_REVIEW_NOTIFY_CRON_ENABLED` | **NOT SET** |
| **weekly-mobility-status** | `WEEKLY_MOBILITY_CRON_ENABLED` | **NOT SET** |

**Seven of twelve scheduled jobs fire and do nothing.** Note the distinction that matters:
`autopilot-nightly` is `false` — someone decided. The other seven have *no variable at all*,
which is indistinguishable from "nobody ever finished wiring it".

I am not guessing which of those seven are deliberate. That is a decision, not a deduction.

## 3. What this change does

`crawl-scheduler.yml` only. The gate moves from the **job** to the **step**, so the job always
runs and reports its own state:

- disabled → a `::warning` annotation and a run-summary block saying the scheduler is off and
  schedules are accumulating;
- enabled but missing `API_BASE`/`CRON_SECRET` → now a hard **error** instead of `exit 0`. A cron
  that is switched on but misconfigured should fail, not report success.

The behaviour when properly enabled is unchanged.

## 4. What it deliberately does not do

**It does not set `CRAWL_CRON_ENABLED`.** That is an operator action, and it must not happen yet:

> Enabling the cadence today would crawl the **current** `sources.json` — the eight newcomer
> portals, not the legal sources rules cite (PR #1888, unmerged) — and would store every
> bot-block interstitial as a parsed document (PR #1887, unmerged). It would actively add
> poisoned rows.

**Order of operations:** merge and deploy **#1887** (bot-block detection) and **#1888** (crawl
targeting), then set `CRAWL_CRON_ENABLED=true` and `CRAWL_API_BASE=https://api.relopass.com`.

It also does not touch the other six unset gates. Each needs a yes/no from someone who knows
whether that job is wanted.

---

### Evidence index

| claim | check |
|---|---|
| workflow fires daily, always skipped | `gh run list --workflow=crawl-scheduler.yml` → 8× `completed/skipped` |
| gate variable unset | `gh variable list` — no `CRAWL_CRON_ENABLED` row |
| `CRON_SECRET` present | `gh secret list` → configured 2026-07-07 |
| schedules 2 months overdue | `SELECT name, next_run_at, last_run_at FROM crawl_schedules` |
| no job run links to a schedule | `SELECT count(*) FROM crawl_job_runs WHERE schedule_id IS NOT NULL` → 0 |
| seven gates unset | each workflow's `vars.*_CRON_ENABLED` cross-checked against `gh variable list` |
