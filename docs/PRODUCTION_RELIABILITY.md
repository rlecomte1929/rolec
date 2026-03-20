# Production reliability: registration, CORS, and slow buttons

Symptoms often show up together: **registration stuck on “Creating account…”**, **Chrome CORS errors** on `api.relopass.com`, and **multi‑second (or minute‑long) waits** after clicks.

## Step 1 — Separate “real CORS” from “API never answered”

Browsers report **“No `Access-Control-Allow-Origin` header”** when:

1. The **preflight `OPTIONS`** request fails, times out, or is answered by a **proxy/gateway** (502/504) that does not add CORS headers, **or**
2. The API process never responds in time.

So: **fix health and latency first**, then verify CORS.

From your laptop:

```bash
curl -sS https://api.relopass.com/health
```

```bash
curl -sS -D - -o /dev/null -X OPTIONS "https://api.relopass.com/api/auth/register" \
  -H "Origin: https://relopass.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization"
```

You should see **`Access-Control-Allow-Origin`** (or a matching regex) on the OPTIONS response. If you see **502/504** or a long hang, the problem is **Render/Cloudflare/routing**, not the FastAPI CORS list.

## Step 2 — Backend CORS configuration (Render)

The app entrypoint is `uvicorn backend.main:app`. It already allows:

- `https://relopass.com`, `https://www.relopass.com`
- Plus any extra origins from **`CORS_ORIGINS`** (comma-separated), merged in — not replacing production defaults.

In **Render → Web Service → Environment**:

- Set `CORS_ORIGINS` if you use **preview URLs** or another frontend host, e.g.  
  `https://relopass.com,https://www.relopass.com,https://your-preview.onrender.com`
- Optional: `CORS_ORIGIN_REGEX` for subdomains (default already matches `https://*.relopass.com`).

Redeploy the API after changes.

## Step 3 — Reduce “laggy” HR/admin pages (database)

Slow `GET /api/hr/assignments`, `hr-users`, etc. are usually **Postgres + missing indexes** or **cold API instances**.

On Supabase (or any Postgres backing production), apply indexes from the repo when appropriate:

```bash
psql "$DATABASE_URL" -f backend/sql/render_performance_indexes.sql
```

Also avoid **unlinking** a Render-managed Postgres that overwrites `DATABASE_URL` with a non-Supabase URL (see `README_DEPLOY_RENDER.md`).

## Step 4 — Render cold starts

Free/low-tier services **spin down**. The first request after idle can take **tens of seconds**, which feels like a broken registration flow.

Mitigations:

- Upgrade to a plan that **does not sleep**, or
- External **uptime ping** every few minutes to `/health` (only if your policy allows).

## Step 5 — “Multi registration” / duplicate accounts

The auth UI now guards against **double submit** (double-click + Enter). True duplicate protection remains server-side: **same email or username** returns a clear 400.

## Step 6 — Supabase Auth sync (login / register)

The API **provisions Supabase Auth** on successful **`/api/auth/register`** and **`/api/auth/login`** when the user has an **email** and **`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`** are set (same service role used for storage). That lets the browser call `signInWithPassword` without a spurious **400**.

- Set **`DISABLE_SUPABASE_AUTH_SYNC=1`** only if you intentionally run without Supabase Auth.
- Passwords shorter than Supabase’s minimum are **skipped** for sync (ReloPass signup still succeeds).

## Step 7 — SQLAlchemy pool (Postgres)

For PostgreSQL, the backend uses a small connection pool with **`pool_pre_ping`** and **`pool_recycle`** (default **280s**) to avoid stale connections to Supabase. Override if needed:

- `SQLALCHEMY_POOL_SIZE` (default `5`)
- `SQLALCHEMY_MAX_OVERFLOW` (default `10`)
- `SQLALCHEMY_POOL_RECYCLE` (default `280`)

## Frontend / API changes in-repo

- **90s axios timeout** — fails fast instead of hanging ~2 minutes.
- **Clearer messages** for network/CORS/timeouts on the auth page.
- **CORS preflight cache** (`max_age`) on the API — fewer OPTIONS round-trips after the first visit.
- **Cached admin** `GET /api/admin/context` and **`/api/admin/companies`** (short TTL + invalidation on impersonation / company writes) to cut duplicate work when several shells load at once.
- **Admin People** reads **`company_id`** and **`role`** from the URL query once (e.g. `?company_id=…&role=EMPLOYEE`) so the company dropdown matches deep links.

Deploy **both** frontend and backend to see the full effect on `relopass.com`.
