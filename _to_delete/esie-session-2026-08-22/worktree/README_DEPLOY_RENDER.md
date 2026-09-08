# Deploy on Render

## Backend — Web Service (Python)

| Setting        | Value                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------ |
| Runtime        | Python                                                                                           |
| Build Command  | `pip install -r backend/requirements.txt`                                                        |
| Start Command  | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_CONCURRENCY:-4} --proxy-headers` |
| Python Version | Controlled by `.python-version` (3.11.7)                                                         |

> The `--workers` flag is required. Without it, Uvicorn runs a single worker and concurrent requests queue serially behind any slow handler (policy extraction, login hashing, LLM calls). Tune `WEB_CONCURRENCY` to the Render instance's CPU count (default 4).

### Environment Variables

| Variable       | Required | Example                                              |
| -------------- | -------- | ---------------------------------------------------- |
| `DATABASE_URL` | Yes      | `postgresql://user:pass@host:5432/dbname`            |
| `CORS_ORIGINS` | Optional | `https://relopass.com,https://www.relopass.com`      |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Recommended | Same as policy storage; also used to **mirror ReloPass users into Supabase Auth** on login/register (so the frontend can refresh Supabase tokens). |
| `DISABLE_SUPABASE_AUTH_SYNC` | Optional | Set to `1` only if you must disable that mirroring. Auto-enabled when `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` are absent. |
| `SUPABASE_AUTH_SYNC_TIMEOUT_SECONDS` | Optional | Wallclock cap per Supabase admin call from the background sync (default `5`). Lower if Supabase is consistently slow and you'd rather drop syncs than queue them. |
| `AUTH_SUPABASE_SYNC_MAX_WORKERS` | Optional | Background pool size for the post-login Supabase sync (default `4`). |
| `AUTH_PERF_DEBUG` | Optional | Set to `1` to emit structured JSON timing logs for `/api/auth/login` and `/api/auth/register` — useful when diagnosing "Request timed out" on login. |
| `DISABLE_STARTUP_SEED` | Optional | Set to `1` to skip wizard demo cases and supplier JSON seeding entirely. |
| `PREDICTIONS_ENABLED` | Optional (canary, default off) | Set to `1`/`true` to enable `GET /api/cases/{case_id}/predicted-duration` (Cox case-duration estimate). |
| `PROCESSING_TIME_ENABLED` | Optional (canary, default off) | Set to `1`/`true` to enable `GET /api/cases/{case_id}/processing-time` (P2-04 corridor processing-time estimate) and the **Processing time** card on the HR Estimate page (`/hr/cases/:caseId/estimate`). Until set, the endpoint 404s and the card renders nothing (safe dark-ship). |

> **Feature-flag canaries.** `PREDICTIONS_ENABLED` and `PROCESSING_TIME_ENABLED` are dark-ship flags that default **off**, so the predictive surfaces stay hidden until you flip them per-environment. To ramp processing-time estimates: set `PROCESSING_TIME_ENABLED=true` on the Render Web Service, redeploy, then open `/hr/cases/:caseId/estimate` for a case on a seeded corridor (e.g. IN→DE) and confirm the Processing-time card appears.

> **Diagnosing slow logins.** Hit `GET /api/health/supabase` (add `?probe=1` to issue a live admin call bounded by `SUPABASE_AUTH_SYNC_TIMEOUT_SECONDS`). The response indicates whether the Supabase Auth admin API is reachable from the Render worker; degraded status with `reason: probe_timeout` points at network/keys before the request even reaches login.

- If `DATABASE_URL` is not set, the backend falls back to local SQLite (`relopass.db`).
- **Supabase Session Pooler** (required): Use the pooler connection string, not the direct connection.
  - Go to Supabase → Project Settings → Database → Connection string → **URI** (Session mode)
  - Host format: `aws-1-eu-west-1.pooler.supabase.com`, port `6543` (or `5432` depending on pooler type)
  - Username format: `postgres.<project_ref>` (e.g. `postgres.nsvefcvpvwwwhuqyuqmp`), NOT plain `postgres`
- If the URI starts with `postgres://`, the backend auto-converts it to `postgresql://`.
- If the host is a Supabase pooler (`pooler.supabase.com`) and the URI has no `sslmode`, the backend auto-appends `?sslmode=require` (required to fix "SSL connection has been closed unexpectedly").
- **Important:** Do NOT link a Render-managed Postgres database to this service. That would inject a `DATABASE_URL` with user `postgres` and override your Supabase string. Set `DATABASE_URL` manually in Environment Variables.

### Database Initialization

No Alembic or pre-deploy command needed. On every startup, the backend:

1. Runs `CREATE TABLE IF NOT EXISTS` for all legacy tables (users, sessions, assignments, etc.)
2. Runs `Base.metadata.create_all()` for all SQLAlchemy tables (wizard cases, country profiles, etc.)

Both steps are idempotent and safe to run on every boot.

Demo wizard cases and supplier rows from bundled JSON are seeded **in the background** after the process starts listening, so Render’s port health check is not blocked by long DB seed work.

### Manual migration (Option B)

If you disable runtime DDL in production, apply required schema changes manually:

```bash
psql "$DATABASE_URL" -f backend/sql/render_case_services.sql
```

Optional performance indexes for slow assignment lookups:

```bash
psql "$DATABASE_URL" -f backend/sql/render_performance_indexes.sql
```

### Verify Deployment

```bash
curl https://api.relopass.com/health
```

Expected:
```json
{"status": "ok", "service": "ReloPass API", "version": "1.0.0", "timestamp": "..."}
```

Look for these log lines in Render:
```
INFO:backend.main:Startup DB config: db_config: scheme=postgresql user=postgres.XXXX host=... port=6543 ...
INFO:backend.database:DB schema ensured (legacy tables)
INFO:backend.main:Initializing database schemas...
INFO:backend.app.db:DB schema ensured (SQLAlchemy tables)
INFO:backend.main:Demo/supplier seed scheduled in background after listen (Render-safe).
INFO:backend.main:Startup complete.
INFO:backend.main:Background: seeding demo cases…
```

**Validate DATABASE_URL on startup:** The first log line shows parsed DB config (password masked). For Supabase pooler:
- `user` must be `postgres.<project_ref>`, not `postgres`
- `host` should contain `pooler.supabase.com`
- `sslmode=present` (or `require`) is expected

---

## Frontend — Static Site

| Setting           | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Build Command     | `npm --prefix frontend ci && npm --prefix frontend run build`      |
| Publish Directory | `frontend/dist`                                                    |
| Node Version      | Controlled by `.nvmrc` (20.18.1)                                   |

### Environment Variables

| Variable       | Required | Value                          |
| -------------- | -------- | ------------------------------ |
| `VITE_API_URL` | Yes      | `https://api.relopass.com`     |

### SPA routing & security headers — `render.yaml` (Render Blueprint)

Frontend hosting config lives in the repo-root **`render.yaml`** (adopted as a Render
Blueprint), NOT in the dashboard or Netlify-style files:
- **SPA rewrite:** `routes: [{ type: rewrite, source: /*, destination: /index.html }]` — every
  route serves `index.html`.
- **Security headers (SEC-005):** the 6 headers (Content-Security-Policy, Strict-Transport-Security,
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) are declared under
  the static site's `headers:`.

**Why `render.yaml` and not `_headers`/`_redirects`:** Render does **not** honor a Netlify-style
`_headers` file (it serves it as a static asset), and once any dashboard rule exists Render stops
applying the file-based `_redirects` rewrite. Keeping routing **and** headers together in
`render.yaml` stops them drifting apart — a 2026-06-08 incident: adding headers in the dashboard
silently disabled the `_redirects` SPA rewrite and 404'd every deep link. The old
`frontend/public/_headers` and `_redirects` files were therefore removed.

**Deep-link safety net:** `frontend/public/404.html` + `frontend/public/404-redirect.js` restore the
requested route via `?__redirect=` (consumed by `App.tsx`'s `QueryRedirect`) if the rewrite is ever
missing. The redirect logic is an **external** script (not inline) because the CSP is
`script-src 'self'` with no `'unsafe-inline'` — an inline script would be blocked.

---

## Connect Frontend ↔ Backend

1. Set `VITE_API_URL` in Render Static Site → Environment Variables
2. Set `CORS_ORIGINS` in Render Web Service → Environment Variables (include the frontend domain)
3. Set `DATABASE_URL` in Render Web Service → Environment Variables (Supabase connection string)
4. Redeploy both services
