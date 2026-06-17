# Authenticated latency harness (PERF-1 / AIQ-1014)

`scripts/perf_authed_harness.py` is the production-safe authenticated latency
instrument the rest of AIQ-1014 depends on. Unlike `scripts/perf_audit.py` (local
/ static), it logs in as real personas against a deployed environment, hits the
**actual core authenticated endpoint set** (curated from
`frontend/src/api/client.ts`), and reports warm latency separately from the first
(cold) request — so infra latency (Render cold-start) can be told apart from
app/DB latency.

## Usage

```bash
python scripts/perf_authed_harness.py                 # table, all personas
python scripts/perf_authed_harness.py --json          # machine-readable
python scripts/perf_authed_harness.py --persona employee --samples 20
python scripts/perf_authed_harness.py --assert        # CI/budget gate: non-zero exit on breach
python scripts/perf_authed_harness.py --cold-only      # characterise cold-start (PERF-2)
```

Budgets: `--p95-budget-ms` (default 2000) and `--max-budget-ms` (default 3000)
are asserted only against **warm 2xx** samples, so a one-off cold-start spike
neither masks nor fails the steady-state number.

### Credentials (never commit secrets)

Defaults are the shared demo/seed accounts. Override via env:
`PERF_ADMIN_ID/PERF_ADMIN_PW`, `PERF_HR_ID/PERF_HR_PW`, `PERF_EMP_ID/PERF_EMP_PW`,
and `PERF_BASE_URL`. For CI (PERF-4) supply these via GitHub repo secrets (set in
the web UI — `gh secret set` from a no-TTY shell silently sets empty).

## Two gotchas the harness handles (found during PERF-1 recon, 2026-06-17)

1. **Cloudflare blocks the default agent.** `Python-urllib/*` gets a 403 from the
   Cloudflare WAF in front of `api.relopass.com`; a normal browser User-Agent gets
   through. The harness sends a browser UA (override with `PERF_USER_AGENT`).
   Measuring with the default agent would time a WAF block, not the app.
2. **slowapi rate limits punish rapid sampling.** Firing N requests back-to-back
   trips per-route `429`s (some admin routes are especially tight). The harness
   paces samples with `--delay-ms` (default 250) and reports a `rate_limited`
   (`rl=`) count per endpoint so 429s are visible, never averaged into latency.

## Baseline finding (2026-06-17, prod `api.relopass.com`, warm)

A captured run is in `authed_harness_baseline_2026-06-17.json`. Headline numbers
(warm p95):

| Persona  | Endpoint                              | warm p95 |
|----------|---------------------------------------|----------|
| admin    | /api/admin/people                     | ~0.9s    |
| hr       | /api/hr/cases                         | ~0.6s    |
| hr       | /api/hr/policy-config/templates       | ~2.1s ⚠️ |
| employee | /api/employee/assignments/overview    | ~1.9s    |
| employee | /api/employee/policy/caps             | ~2.7s ⚠️ |

**Interpretation (hand-off to PERF-2):**
- **Warm steady-state is ~0.6–2.7s, not 7.7s.** The 7.7s observed in the
  2026-06-13 audit does **not** reproduce warm → it is most likely **cold-start**
  (Render spin-up) or a specific heavy request under specific data. PERF-2 must
  measure cold-start explicitly (`--cold-only` against a freshly-idle service) and
  confirm the Render plan / spin-down behaviour before any code change.
- **There are nonetheless two genuine warm bottlenecks over the 2s budget:**
  `employee /api/employee/policy/caps` and `hr /api/hr/policy-config/templates`.
  These are concrete PERF-3 targets regardless of the cold-start question — start
  the server-timing (auth/handler/DB) split there.

> Numbers vary run-to-run (shared prod, rate limits); treat them as directional,
> and always re-run the same harness before/after a fix rather than comparing to
> this table.
