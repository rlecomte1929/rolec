# Performance Audit Kit

This folder holds the plain-English performance roadmap and the local audit tooling for ReloPass.

## What To Run

From the repo root:

```bash
./venv/bin/python scripts/perf_audit.py
```

To save a report:

```bash
./venv/bin/python scripts/perf_audit.py --write docs/performance/CURRENT_AUDIT.md
```

To get JSON instead of Markdown:

```bash
./venv/bin/python scripts/perf_audit.py --format json
```

## What It Measures

- Backend startup/import cost using Python import-time profiling.
- Relocation-plan assembly speed using a synthetic local benchmark.
- Policy pipeline observability readiness from local analytics tables when available.
- Frontend route-loading shape from `frontend/src/App.tsx`.
- Admin and database hotspot candidates from the main backend query modules.

## What It Does Not Measure Yet

- Production request latency.
- Real browser bundle timings from a full frontend build.
- Real policy upload throughput in production or staging.
- Query plans from Postgres or Supabase.

Those still need environment-specific follow-up, but this audit is enough to keep prioritization grounded in code and local baselines.
