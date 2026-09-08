# Expert Review — Performance

**Reviewer lens:** Site reliability / performance engineer. Targeting B2B SaaS sensible defaults — sub-200ms typical API, <500KB initial JS chunk, no obvious N+1 patterns.
**Method:** Static analysis (file sizes, dependency graph hints) + runtime probes against `localhost:8000`. Full Lighthouse / Web Vitals run requires the production frontend served through Render, deferred to Phase 3.

**Composite score: 6.0 / 10**

What would make it a 10:
- All routers <500 lines (so per-route compilation + import path stays fast)
- Frontend initial JS chunk <500KB gzipped
- No N+1 query patterns in the top-10 most-called endpoints
- Connection-pool sized + monitored
- LCP <2.5s on the employee dashboard

---

## P0 findings

### PERF-1 — `database.py` is 17,137 lines
**Evidence:** `wc -l backend/database.py = 17137`
**Why P0 perf:** Every backend Python process imports this module at startup. Python's import system parses + compiles the entire file even if only a few helpers are used. On Render with `--workers 4`, that's 4× the parse cost on every cold start. It also means:
- Code-reviewer attention is fragmented (you can't `grep` cleanly).
- Type checkers + tools work harder.
- Any one engineer can't hold its mental model.

**Fix direction:** Decompose by domain (case-related queries → `backend/db/cases.py`, policy queries → `backend/db/policies.py`, etc.). Target <1,500 lines per file. This is also a maintainability concern but the startup-time impact is real.

### PERF-2 — `backend/main.py` is 14,031 lines with 61 included routers and inline route handlers
**Evidence:** `wc -l backend/main.py = 14031`. `grep include_router = 61`. Direct `@app.get` route handlers count is in the hundreds (sampled lines 2892–9122).
**Why P0:** Same import-time concern as PERF-1. Compounded by FastAPI building its route table from a giant single file — every cold start re-resolves all those `@app.get` decorators sequentially.
**Fix direction:** The ENG-1 migration (move routes from root `main.py` into modular `app/routers/`) directly addresses this. The 6:61 ratio is the constraint.

---

## P1 findings

### PERF-3 — Frontend `dist/` is 14MB
**Evidence:** `du -sh frontend/dist = 14M`
**Why P1:** This is the unzipped build output, not the network-shipped bundle, but 14MB suggests the gzipped initial chunk is also large. Risk: long Time-to-Interactive on slower networks, especially for the employee persona (often on mobile data in transit).
**Fix direction:**
- Run `npx vite build --mode production` then check `dist/assets/index-*.js` size. Target <500KB gzipped.
- Verify the Vite vendor split (CLAUDE.md mentions React, Supabase, Axios as separate chunks) is actually working — check that the chunks are independent (no overlap in graph).
- Lazy-load admin pages (admin users are few; their bundle shouldn't bloat the employee path).

### PERF-4 — Large React component files
**Top 5 by LOC:**
- `frontend/src/api/client.ts` — **3,714 lines** — every API call goes here; large but understandable
- `frontend/src/types/relopass-api-contracts.ts` — 1,542 lines — type definitions, OK
- `frontend/src/features/platform-v2/intake/EmployeeIntakePage.tsx` — **1,439 lines** — single page component is huge
- `frontend/src/features/platform-v2/policy-builder/HrPolicyBuilderV2Page.tsx` — 1,383 lines
- `frontend/src/features/timeline/RelocationTimeline.tsx` — 1,171 lines

**Why P1:** Large React components re-render in larger blast radii on state changes. They're also harder for the Vite tree-shaker to optimize.
**Fix:** Decompose the page components into per-step / per-section subcomponents with `React.memo` where appropriate.

### PERF-5 — N+1 risk in `cases.py` and `immigration.py`
**Evidence:** `cases.py` 3,328 lines, `immigration.py` 1,544 lines. The full-stack agent noted 294 `.execute()` / `.query()` calls across 37 routers. Without query-batching at the service layer, the typical "list of cases + per-case provider status + per-case task count" pattern is a classic N+1.
**Why P1:** A list endpoint returning 25 cases with per-case provider fan-out can easily hit 75+ queries. Per-query latency on Supabase pooler is ~10–30ms; that's a 1–2s page load on the HR command center.
**Fix:** Add per-endpoint query counter (logging middleware), set a soft threshold (≤10 queries/request), alert in dev when exceeded.

### PERF-6 — Connection pool sized at 5+10 (CLAUDE.md)
**Evidence:** CLAUDE.md: "pool params (size=5, overflow=10, recycle=280s)"
**Why P1:** On a single Render instance with 4 uvicorn workers, that's effectively 4×15 = 60 connections to Supabase. Pooler limit on Supabase Pro is 60 (default). Risk: at 4–5 concurrent users doing heavy work, the pool exhausts and requests block.
**Fix:** Either bump pooler limit on Supabase or reduce `--workers 4` to `--workers 2` and lean on async I/O.

---

## P2 findings

| # | Finding | Evidence |
|---|---|---|
| PERF-7 | `policy_storage_diag` startup step takes 588ms | log: `startup_step=policy_storage_diag status=done elapsed_ms=588` — every cold start pays this. Acceptable, but worth checking if it's needed on every boot. |
| PERF-8 | `ensure_initialized` takes 4.16s + fails (see SEC-1) | This is the longest startup step, AND it's failing. Fix doubles as perf win. |
| PERF-9 | `backend/services/policy_config_matrix_service.py` 1,509 LOC | Likely heavy import; profile if invoked per-request. |
| PERF-10 | 280 migrations | Migration apply is one-time per environment but ageing migrations slow new-environment provisioning. Consider squashing post-stable. |
| PERF-11 | OpenAI passport OCR has no timeout (SEC-5 + P1-6 in fullstack audit) | Worst-case: hung request blocks a uvicorn worker for minutes. |

## Endpoint latency baseline (local, single user)

| Endpoint | HTTP | p50 | Notes |
|---|---|---|---|
| `GET /health` | 200 | **3.7ms** | Excellent |
| `GET /openapi.json` | 200 | 250ms | Acceptable — OpenAPI spec generation across 60+ routers |
| `GET /docs` | 200 | 0.9ms | HTML serve |
| `GET /api/cases/test-nonexistent` | 401 | 1.0ms | Auth check is fast (no DB hit) |
| `POST /api/auth/login` (422 — no body) | 422 | 1.5ms | Validation only |

**Caveat:** Local single-user measurement. Production latency on Render (with cold-start and connection pool contention) is the real question — not captured here.

## What this pass DID NOT cover

- Lighthouse / Web Vitals (LCP, CLS, INP) — requires production frontend
- Bundle size analysis (`source-map-explorer` or similar against built dist/)
- Load testing (k6, locust, etc.)
- DB query plan analysis on the real Supabase instance (EXPLAIN ANALYZE on top-10 endpoints)
- Render cold-start timing
- Edge / CDN coverage

## Recommended next perf actions

1. **Profile the dist bundle** (PERF-3) — `npx source-map-explorer` to see what's eating the 14MB.
2. **Add a per-request query-count log** (PERF-5) — single middleware, instant N+1 visibility.
3. **Fix `ensure_initialized`** (PERF-8 = SEC-1) — kills two birds.
4. **Decompose `database.py` + `main.py`** (PERF-1, PERF-2) — long-term, but every domain extracted is a perf win.
5. **Decide on `--workers` count** (PERF-6) given Supabase pooler limit.
6. **Add LCP/INP collection** in the frontend (e.g., `web-vitals` library reporting to a simple endpoint) — visibility before optimization.
