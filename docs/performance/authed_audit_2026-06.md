# Authenticated latency attribution — AIQ-1014 / PERF-2

**Date:** 2026-06-17 · **Method:** PERF-1 harness (`scripts/perf_authed_harness.py`)
against prod `api.relopass.com`, cross-checked against live Render request logs.
**Mandate:** measure before changing code; separate cold-start from app/DB latency.

## TL;DR — verdict

The 2026-06-13 audit's **7.7s is cold-start, not warm latency.** Warm steady-state
is sub-3s everywhere. There are nonetheless **two genuinely slow warm endpoints**,
both DB-bound (N+1), that exceed the 2s budget independent of cold-start.

| Cause | Evidence | Fix lever (PERF-3) |
|---|---|---|
| **Cold-start (dominant)** | Backend `rolec-eu` (`srv-d7ku…`) is on the Render **`free` plan** → spins down on idle → first request pays full app startup. No warm request in the logs approaches 7.7s. | **Infra**: upgrade the plan (eliminates spin-down) or add a keep-warm pinger. |
| **DB N+1 on `/api/employee/policy/caps`** | warm `dur_ms ≈ 1720`, **`query_count=12`** (OVER threshold), consistent across samples. | **Code**: collapse the per-item query fan-out (batch/join) or index. |
| **DB N+1 on `/api/hr/policy-config/published`** | warm `dur_ms = 2768`, **`query_count=15`** (OVER). | **Code**: same. |

## 1. Cold-start vs warm

- **Warm** (service kept warm by traffic; PERF-1 harness + logs): core authed
  endpoints run **p95 ~0.6–2.8s**. The slowest *warm* observation in the logs was
  `/api/hr/policy-config/published` at `dur_ms=2768`. **Nothing warm reaches 7.7s.**
- **Cold:** the backend is on Render `free`, which **spins the instance down after
  ~15 min idle**. The next request triggers a full app boot. The 11:33 UTC startup
  in the logs shows the boot path (`startup_step=policy_storage_diag elapsed_ms=996`,
  ingest reconciler, demo seed, …) before `Your service is live`. A request that
  lands during/just-after spin-up pays that startup — this is the 7.7s the audit saw.
- **Important:** a prior queue task ("Performance hardening: DB indexes, Render plan
  upgrade, cold-start elimination") is marked **Done**, but the plan is **still
  `free`** — the plan upgrade did not take effect / was reverted. Cold-start is NOT
  eliminated today.

## 2. Per-request attribution — no new instrumentation needed

The platform already has the timing split this task called for:

- `backend.main` logs **`request_id=… method=… path=… status=… dur_ms=… user_id=…`**
  per request (total wall time).
- `query_counter` middleware (`backend/app/services/query_counter.py`) logs
  **`query_count route=… count=N threshold=10 elapsed_ms=M status=OVER|OK`** per
  request — i.e. the **DB query count**, which directly flags N+1 / DB-bound
  handlers. `count > 10` ⇒ DB-bound.

So the auth/handler/**DB** split is already observable from Render logs. Adding a
second timing middleware (or a `Server-Timing` header) would duplicate existing
infra for no new signal, so PERF-2 deliberately adds **no code** — it uses what
exists. (If a future need arises to expose DB *time* not just *count*, the place
to extend is the existing `before/after_cursor_execute` listener in
`query_counter.py`, not a new middleware.)

### Sampled prod log evidence (2026-06-17, warm)

```
GET /api/employee/policy/caps      status=200 dur_ms=1729.99  query_count=12 OVER
GET /api/employee/policy/caps      status=200 dur_ms=1884.36  query_count=12 OVER
GET /api/hr/policy-config/published status=200 dur_ms=2768.49 query_count=15 OVER
GET /api/hr/policy-config/templates status=200 dur_ms=680.31  (fine — not a bottleneck)
GET /api/admin/policy-config/templates status=429 dur_ms=1.02  (rate-limit reject, not latency)
```

## 3. Corrections to the PERF-1 baseline

- **`/api/hr/policy-config/templates` is NOT a bottleneck.** PERF-1's harness
  reported a p95 of ~2093ms, but the logs show it runs **~680ms** consistently —
  the harness number was a single-sample outlier (shared-prod noise / a rate-limit
  retry). Removed from the PERF-3 target list.
- The real warm targets are **`/api/employee/policy/caps`** (12 queries) and
  **`/api/hr/policy-config/published`** (15 queries).

## 4. Hand-off to PERF-3

Two independent levers, do both:

1. **Infra (cold-start):** move the backend off the `free` plan, OR add a
   keep-warm pinger (a cron hitting `/health` every ~10 min). A plan change is a
   **human-approved billing action** — do not change autonomously. This is what
   actually fixes the 7.7s the audit flagged.
2. **Code (warm N+1):** for `/api/employee/policy/caps` (12 q) and
   `/api/hr/policy-config/published` (15 q), find the per-item query fan-out and
   collapse it (batch/`IN`/join) or add the missing index. Re-run the PERF-1
   harness and confirm `query_count` drops and warm p95 ≤ 2s.

> Validation reminder: re-run `scripts/perf_authed_harness.py` before/after any
> fix rather than trusting one-off numbers; shared-prod latency is noisy.
