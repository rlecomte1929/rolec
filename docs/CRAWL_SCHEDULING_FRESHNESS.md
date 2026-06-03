# Crawl Scheduling and Freshness Monitoring (Backend)

Backend operational layer for ReloPass content freshness: scheduled crawls, change detection, freshness metrics, and admin dashboard APIs.

## Overview

- **No auto-publish**: All flows respect staging → admin review → live.
- **Admin-only**: All endpoints require admin authentication.
- **External cron**: Use `POST /api/admin/crawl/process-due` or `scripts/process_crawl_schedules.py` for scheduled runs.

## Database (Migration)

Migration: `supabase/migrations/20260311000000_crawl_scheduling_freshness.sql`

### Tables

| Table | Purpose |
|-------|---------|
| `crawl_schedules` | Recurring crawl plans (cron or interval) |
| `crawl_job_runs` | Tracks each run (scheduled or manual) |
| `document_change_events` | Detected document changes per run |
| `freshness_snapshots` | Aggregated freshness metrics |
| `freshness_alerts` | Optional actionable alerts |

### Schedule Fields

- `schedule_type`: `cron` | `interval`
- `schedule_expression`: cron string (e.g. `0 2 * * *`) or interval hours (e.g. `24`)
- `source_scope_type`: `source`, `country`, `city`, `domain_group`, `tier`
- `source_scope_ref`, `country_code`, `city_name`, `content_domain`
- `crawl_tier`: `tier-1-critical`, `tier-1-stable`, `tier-2` (per-tier schedules only)

## Per-tier cron config (AIQ-689 / P2-02a)

Tiers are the primary scheduling dimension. `backend/app/services/crawl_tier_config.py`
defines three tiers and maps source-registry `trust_tier` values (T0–T3) onto them:

| Tier | trust_tier | Cadence | Cron (UTC) |
|------|-----------|---------|------------|
| `tier-1-critical` | T0 | daily | `0 2 * * *` |
| `tier-1-stable` | T1 | weekly (Mon) | `0 3 * * 1` |
| `tier-2` | T2, T3 | monthly (1st) | `0 4 1 * *` |

Unknown/missing `trust_tier` falls back to `tier-2` (slowest, but still crawled).

`sync_tier_schedules()` idempotently seeds one `crawl_schedules` row per tier
(keyed by the deterministic name `auto-tier::<tier>`) and repairs cron/tier drift.
It is called automatically at the top of `scripts/process_crawl_schedules.py`, and is
also exposed as `POST /api/admin/crawl/sync-tier-schedules`. A scheduled `tier` run
crawls only the sources whose `trust_tier` maps to that tier.

## API Endpoints (Admin-only)

### Freshness

- `GET /api/admin/freshness/overview` — Summary metrics
- `GET /api/admin/freshness/countries` — Freshness by country
- `GET /api/admin/freshness/cities` — Freshness by city
- `GET /api/admin/freshness/sources` — Per-source freshness
- `POST /api/admin/freshness/refresh` — Recompute freshness snapshot

### Crawl Schedules

- `POST /api/admin/crawl/sync-tier-schedules` — Seed/repair per-tier schedules (idempotent)
- `GET /api/admin/crawl/schedules` — List schedules
- `GET /api/admin/crawl/schedules/due` — Due schedules
- `GET /api/admin/crawl/schedules/{id}` — Schedule detail
- `POST /api/admin/crawl/schedules` — Create schedule
- `PUT /api/admin/crawl/schedules/{id}` — Update schedule
- `POST /api/admin/crawl/schedules/{id}/pause` — Pause
- `POST /api/admin/crawl/schedules/{id}/resume` — Resume
- `POST /api/admin/crawl/schedules/{id}/trigger` — Set next run to now
- `POST /api/admin/crawl/process-due` — Process all due schedules (call from cron)
- `POST /api/admin/crawl/trigger` — Manual crawl (body: `source_name`, `country_code`, `city_name`, `content_domain`)

### Job Runs

- `GET /api/admin/crawl/job-runs` — List job runs
- `GET /api/admin/crawl/job-runs/{id}` — Job run detail

### Change Detection

- `GET /api/admin/changes/documents` — Document change events
- `GET /api/admin/changes/documents/{id}` — Change detail
- `GET /api/admin/changes/live-stale-resources` — Stale live resources
- `GET /api/admin/changes/live-stale-events` — Expired/stale events

## Services

### crawl_scheduler_service

- `list_schedules`, `get_schedule`, `get_due_schedules`
- `create_schedule`, `update_schedule`, `pause_schedule`, `resume_schedule`
- `trigger_schedule_now`
- `process_due_schedules()` — Run all due schedules
- `run_crawl_for_scope()` — Execute pipeline for scope

### change_detection_service

- `run_change_detection_for_crawl_run(crawl_run_id, job_run_id)` — Compare docs to previous versions
- `list_document_changes`, `get_document_change`

### freshness_service

- `compute_source_freshness()` — fresh | warning | stale | overdue | error
- `get_source_freshness_signals()`, `get_freshness_overview()`
- `get_stale_live_resources()`, `get_stale_live_events()`
- `refresh_freshness_metrics()` — Persist snapshot

## Cron Setup

```bash
# Every 15 minutes
*/15 * * * * cd /path/to/rolec && python scripts/process_crawl_schedules.py
```

Or call the API:

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.relopass.com/api/admin/crawl/process-due
```

### 7-day live verification (AIQ-689 validation criterion)

The validation criterion is "scheduler runs on schedule for 7 days without missed
executions; logs verify timing." Steps for the reviewer:

1. Deploy and ensure the cron (`*/15 * * * * python scripts/process_crawl_schedules.py`)
   is registered (or schedule `POST /api/admin/crawl/process-due`).
2. Seed the tier schedules once: `POST /api/admin/crawl/sync-tier-schedules`
   (the cron script also calls `sync_tier_schedules()` on every tick).
3. Over the next 7 days, confirm via `GET /api/admin/crawl/job-runs?schedule_id=<tier>`:
   - `tier-1-critical`: ~7 succeeded runs (one per day at ~02:00 UTC)
   - `tier-1-stable`: ~1 run (Monday ~03:00 UTC)
   - `tier-2`: ~1 run if the 1st of a month falls in the window, else 0
4. Verify each schedule's `last_run_at` / `next_run_at` advance by the expected
   cadence and that no day is skipped (no gap > cadence in `started_at` timestamps).

## Assumptions

1. Source config (JSON) defines sources; `content_domain` maps to default cadence (events=1d, transport=2d, admin_essentials=7d, etc.).
2. Change detection uses `content_hash` from `crawled_source_documents`; compare by (source_name, final_url).
3. Live resource staleness: `updated_at` older than 180 days.
4. Event staleness: `start_datetime` in the past.
5. No APScheduler in-process; external cron or manual triggers.

## Next Steps

1. Admin freshness monitoring dashboard frontend
2. Schedule management UI
3. Alerts triage UI
4. Review queue integration from freshness signals
