# ReloPass Workflow Configuration & Repair Guide

**Last Updated:** 2026-08-31  
**Status:** 950 failing workflow runs — root cause: missing secrets and disabled feature flags

---

## Executive Summary

Your CI/CD pipeline has **systematic configuration gaps**, not code bugs. The workflows are gated behind feature flags and secrets that need to be configured in GitHub Settings. Once enabled, the 950 failing runs should resolve to either:
- ✅ **Success** (infrastructure healthy)
- 🔵 **Skipped** (intentionally disabled)
- ⚠️ **Genuine failures** (actual bugs to fix)

This guide walks you through the **full setup** in order.

---

## Phase 1: Add Repository Secrets

**Location:** Repository Settings → Secrets and variables → Actions → Secrets

### 1. `CRON_SECRET`
**Purpose:** Authorizes cron jobs (`/api/crons/*` endpoints)  
**Why it matters:** Multiple jobs POST to protected endpoints and need Bearer token auth

**Steps:**
1. Go to Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `CRON_SECRET`
4. Value: Generate a strong random string (32+ characters):
   ```bash
   # On Mac/Linux:
   openssl rand -hex 16
   # Output example: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
   ```
5. Click **Add secret**

**Then configure your API** to accept this same value as the `Authorization: Bearer <CRON_SECRET>` header on these endpoints:
- `POST /api/crons/dispatch-outbox`
- `POST /api/crons/snapshot-vendor-metrics`
- `POST /api/crons/corridor-deadline-sweep`

---

### 2. `DATABASE_URL` (Read-Only)
**Purpose:** RLS audits, migration checks, vendor snapshots  
**Why it matters:** Guards that check schema/RLS policy health need to query prod without write access

**Steps:**
1. On your Supabase project, create a **read-only role**:
   ```sql
   -- In Supabase SQL Editor, as postgres (admin):
   CREATE ROLE ci_readonly NOINHERIT LOGIN PASSWORD 'strong-random-password';
   GRANT USAGE ON SCHEMA public, rce TO ci_readonly;
   GRANT SELECT ON ALL TABLES IN SCHEMA public, rce TO ci_readonly;
   GRANT SELECT ON pg_tables, pg_policies TO ci_readonly;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ci_readonly;
   ```

2. Construct the connection string:
   ```
   postgresql://ci_readonly:<password>@<supabase-db-host>:<port>/postgres?sslmode=require
   ```
   (Find `<supabase-db-host>` and `<port>` in Supabase Settings → Database → Connection string)

3. Add to GitHub:
   - Name: `DATABASE_URL`
   - Value: `postgresql://ci_readonly:...` (paste the full connection string)

---

### 3. `OPENAI_API_KEY`
**Purpose:** Re-indexing corridor embeddings, immigration corpus chunking  
**Why it matters:** Semantic search relies on real OpenAI vectors (not fallback hashes)

**Steps:**
1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Add to GitHub:
   - Name: `OPENAI_API_KEY`
   - Value: `sk-...` (your key)

---

### 4. `SLACK_WEBHOOK_URL` (Optional)
**Purpose:** Post calibration reports to Slack  
**Only needed if:** You want monthly calibration summaries in Slack

**Steps:**
1. Create a Slack incoming webhook: https://api.slack.com/messaging/webhooks
2. Add to GitHub:
   - Name: `SLACK_WEBHOOK_URL`
   - Value: `https://hooks.slack.com/services/...`

---

## Phase 2: Add Repository Variables

**Location:** Repository Settings → Secrets and variables → Actions → Variables

These are **feature flags** — they gate workflows so misconfigured ones don't run.

### 1. `OUTBOX_DISPATCH_CRON_ENABLED`
```
Name:  OUTBOX_DISPATCH_CRON_ENABLED
Value: true
```
**Effect:** Enables email delivery from `notification_outbox` table (runs every hour)

---

### 2. `OUTBOX_DISPATCH_API_BASE`
```
Name:  OUTBOX_DISPATCH_API_BASE
Value: https://api.relopass.com
```
**Note:** Adjust to your actual API domain if different

---

### 3. `CORRIDOR_DEADLINE_SWEEP_ENABLED`
```
Name:  CORRIDOR_DEADLINE_SWEEP_ENABLED
Value: true
```
**Effect:** Enables daily 06:00 UTC corridor deadline alert sweep

---

### 4. `CORRIDOR_DEADLINE_SWEEP_API_BASE`
```
Name:  CORRIDOR_DEADLINE_SWEEP_API_BASE
Value: https://api.relopass.com
```

---

### 5. `VENDOR_SNAPSHOT_CRON_ENABLED`
```
Name:  VENDOR_SNAPSHOT_CRON_ENABLED
Value: true
```
**Effect:** Enables daily 05:30 UTC vendor metric snapshots (for Vendor Performance dashboard)

---

### 6. `VENDOR_SNAPSHOT_API_BASE`
```
Name:  VENDOR_SNAPSHOT_API_BASE
Value: https://api.relopass.com
```

---

### 7. `RLS_COVERAGE_DATABASE_URL_SET`
```
Name:  RLS_COVERAGE_DATABASE_URL_SET
Value: true
```
**Effect:** Enables RLS/storage/migration guards (only runs when this is `true` AND `DATABASE_URL` secret exists)

---

### 8. `CALIBRATION_SLACK_ENABLED` (Optional)
```
Name:  CALIBRATION_SLACK_ENABLED
Value: true
```
**Only if:** You added `SLACK_WEBHOOK_URL` and want the monthly calibration report posted to Slack

---

## Phase 3: Verify API Readiness

Before enabling cron workflows, ensure your API is ready:

### Health Check
```bash
curl -s https://api.relopass.com/health | jq .
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "...",
  "timestamp": "..."
}
```

If this fails, the cron workflows will fail even with correct config.

---

### API Endpoints Required
These must be implemented and accept `Authorization: Bearer <CRON_SECRET>`:

| Endpoint | Method | Purpose | Cron Job |
|----------|--------|---------|----------|
| `/api/crons/dispatch-outbox` | POST | Deliver pending emails | Notification outbox dispatch (hourly) |
| `/api/crons/snapshot-vendor-metrics` | POST | Record vendor perf snapshots | Daily vendor-metric snapshot (05:30 UTC) |
| `/api/crons/corridor-deadline-sweep` | POST | Generate corridor alerts | Corridor deadline sweep (06:00 UTC) |

---

## Phase 4: Infrastructure Checks

### Database Health
```bash
# Test the read-only role connection:
psql "postgresql://ci_readonly:<password>@<host>:<port>/postgres?sslmode=require" -c "SELECT COUNT(*) FROM information_schema.tables;"
```

Should return the table count without errors.

### Edge Functions
Verify Supabase Edge Functions are deployed:
```bash
curl -s https://<project-ref>.supabase.co/functions/v1/dispatch-outbox \
  -H "Authorization: Bearer <ANON_KEY>"
```

---

## Phase 5: Workflow Behavior After Setup

### Expected Results by Workflow

| Workflow | Before | After |
|----------|--------|-------|
| **Outbox dispatch** | ❌ Fails (missing vars) | ✅ Success (if API healthy) or 🔵 Skipped (no pending emails) |
| **Vendor metrics** | ❌ Fails | ✅ Success (if API healthy) or 🔵 Skipped (disabled) |
| **Corridor sweep** | ❌ Fails | ✅ Success or 🔵 Skipped |
| **Perf budget** | ❌ Fails (instance sleeping) | ⚠️ May still fail if API cold; check `/health` response time |
| **Weekly briefings** | ❌ Fails | ⚠️ Depends on Edge Functions being deployed |
| **Otto import** | ❌ Fails | ⚠️ Depends on Otto service connectivity |
| **RLS/migration guards** | 🔵 Skipped (no secret) | ✅ Success (runs on PRs with migrations) |
| **CI (PRs)** | 🔵 Skipped (no frontend/backend changes) or ✅ Success | No change (frontend/backend tests already working) |

---

## Troubleshooting

### "API_BASE or CRON_SECRET not configured; skipping"
**Cause:** Variables or secrets are missing  
**Fix:** Re-check Phase 1 & 2 above

### "curl: (7) Failed to connect to api.relopass.com"
**Cause:** API unreachable (cold instance, DNS issue, or service down)  
**Fix:** 
1. Check `https://api.relopass.com/health` manually
2. If it's a Render instance, wake it from the Render dashboard
3. Check the Render deploy log for errors

### "psql: error: connection to server at..."
**Cause:** Read-only role doesn't exist or password wrong  
**Fix:** Re-run the SQL commands in Phase 1 step 2

### "OPENAI_API_KEY is not set"
**Cause:** Secret not added  
**Fix:** Add `OPENAI_API_KEY` under Secrets (Phase 1, step 3)

---

## Implementation Checklist

Use this to track your progress:

- [ ] **Secrets Added:**
  - [ ] `CRON_SECRET` 
  - [ ] `DATABASE_URL` (read-only role created in Supabase)
  - [ ] `OPENAI_API_KEY`
  - [ ] `SLACK_WEBHOOK_URL` (optional)

- [ ] **Variables Added:**
  - [ ] `OUTBOX_DISPATCH_CRON_ENABLED=true`
  - [ ] `OUTBOX_DISPATCH_API_BASE`
  - [ ] `CORRIDOR_DEADLINE_SWEEP_ENABLED=true`
  - [ ] `CORRIDOR_DEADLINE_SWEEP_API_BASE`
  - [ ] `VENDOR_SNAPSHOT_CRON_ENABLED=true`
  - [ ] `VENDOR_SNAPSHOT_API_BASE`
  - [ ] `RLS_COVERAGE_DATABASE_URL_SET=true`
  - [ ] `CALIBRATION_SLACK_ENABLED` (optional)

- [ ] **Infrastructure Verified:**
  - [ ] `https://api.relopass.com/health` responds
  - [ ] Database read-only role works
  - [ ] Edge Functions deployed

- [ ] **Test:**
  - [ ] Manually trigger a cron workflow (e.g., `outbox-dispatch`) via workflow_dispatch
  - [ ] Check the workflow run log for success or meaningful errors
  - [ ] Review the run summary to confirm the job executed (not skipped)

---

## Next Steps

1. **Add all secrets & variables** using the checklist above
2. **Verify API health** before running workflows
3. **Manually trigger one cron job** to test (e.g., workflow_dispatch on `outbox-dispatch.yml`)
4. **Monitor the next scheduled runs** (e.g., 07:00 UTC for outbox)
5. **If issues persist**, share the workflow run log and we'll debug further

Once this is done, the workflow failure rate should drop significantly. Any remaining failures will be **genuine infrastructure issues** (API down, DB connectivity, etc.) rather than missing config.

---

## References

- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GitHub Actions Variables](https://docs.github.com/en/actions/learn-github-actions/variables)
- [Supabase Auth Roles](https://supabase.com/docs/guides/auth#manage-user-roles)
- [OpenAI API Keys](https://platform.openai.com/api-keys)
