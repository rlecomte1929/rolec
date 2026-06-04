# Runbook — Live AI EEA Roadmap (P2-01)

Operational runbook for the live AI EEA roadmap (France → Norway first). Covers
the **rollback** procedure and the **error-rate monitoring** required by the
P2-01 Technical Constraints ("Monitor error rate. Rollback plan documented.").

This is an operator document — every command here is runnable without a deploy.

## What the flag controls

The live AI roadmap is gated by a **DB-backed feature flag** (P2-01a), not an
env var, so it toggles with no redeploy:

| Object | Role |
|---|---|
| `public.feature_flags` (key = `live_eea_roadmap`) | Master on/off switch (`enabled`) |
| `public.feature_flag_accounts` (flag_key = `live_eea_roadmap`) | Per-account allowlist (selected test accounts) |
| `backend/app/services/feature_flags.py` · `is_flag_enabled_for()` | `enabled` **AND** account on the allowlist |
| `backend/app/routers/cases_read.py` · `get_case_roadmap()` | The gate: when eligible → `ai_roadmap_eligible`, confidence gating (P2-01b), staleness warnings (P2-01c) |

Migration: `supabase/migrations/20260606000000_feature_flags.sql`. The flag ships
**disabled**; go-live (P2-01g) enables it and adds the allowlist rows.

The flag is read from the DB on **every** request (no in-process cache), so any
change below takes effect on the next request — no redeploy, no restart.

## Rollback

Apply via the Supabase MCP (`execute_sql`) — `supabase db push` is blocked by
migration drift in this project, so use the MCP/SQL editor for these data
changes.

**1. Kill switch (disable for everyone) — fastest, preferred:**

```sql
UPDATE public.feature_flags
   SET enabled = false, updated_at = now()
 WHERE key = 'live_eea_roadmap';
```

`enabled = false` makes `is_flag_enabled_for()` return false for all accounts
regardless of the allowlist. `get_case_roadmap()` immediately reverts to the
plain deterministic `derive_roadmap()` output (no `ai_roadmap_eligible`, no
gating, no staleness annotations).

**2. Targeted (remove a single test account):**

```sql
DELETE FROM public.feature_flag_accounts
 WHERE flag_key = 'live_eea_roadmap' AND account_id = '<auth-uid>';
```

**3. Full purge of the allowlist (keep the flag row):**

```sql
DELETE FROM public.feature_flag_accounts WHERE flag_key = 'live_eea_roadmap';
```

> The flag-off path is **byte-identical to pre-launch behaviour** — if errors
> persist after the kill switch, they are not caused by this feature; escalate
> to a normal incident investigation rather than re-toggling.

## Error-rate monitoring

Watch these during any canary / allowlist expansion. Source: Render service
metrics + backend logs; the pipeline also writes a `TraceSession` audit trail.

| Signal | Where | Threshold → action |
|---|---|---|
| **5xx rate** on `GET /api/cases/{case_id}/roadmap` | Render metrics / logs | > **2%** over a 10-min window (baseline ≈ 0) → **kill switch** |
| **RULE_NOT_FOUND rate** on the AI path (lights up with P2-01e) | pipeline `TraceSession` / logs | > **20%** of eligible requests → investigate corridor coverage; kill switch if user-facing |
| **p95 latency** of the roadmap endpoint | Render metrics | sustained p95 > **8s** (AI path adds LLM latency) → consider kill switch |

## Verify the rollback

After the kill switch, confirm with an allowlisted test account:

1. `GET /api/cases/{case_id}/roadmap` no longer contains `ai_roadmap_eligible`,
   `requires_specialist_review`, `withheld_steps`, or `has_stale_sources` — it
   returns the deterministic roadmap shape.
2. The endpoint 5xx rate returns to baseline within one monitoring window.

## Decision owner

Romain (or the on-call engineer) makes the go / kill-switch call. Re-enable only
after the triggering issue is root-caused and fixed.
