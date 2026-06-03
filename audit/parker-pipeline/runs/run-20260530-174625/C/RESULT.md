# Step C RESULT — Cluster-relative supplier tiering

_Run: run-20260530-174625 | Branch: audit/parker-step-C-cluster-tiering_

## Summary

Supplier tier badges were assigned with **absolute** cutoffs (`>=85 BEST_MATCH`,
`>=70 GOOD_FIT`, `>=50 OK`, else `WEAK`) by `BasePlugin.tier()`. In a thin market every
supplier can collapse into one tier, so the badge stops discriminating. Step C makes
tiering **cluster-relative**: within a (category, country) cell, suppliers are clustered
by their feature profile (KMeans, K∈[2,6] chosen by silhouette), and each supplier is
tiered by its **percentile inside its own cluster** — top 15% BEST_MATCH, next 35%
GOOD_FIT, next 35% OK, bottom 15% WEAK. Thin cells (<8 clustered suppliers) and
not-yet-refreshed cells fall back to the original absolute thresholds, so nothing
degrades. A new module-level `engine.tier(...)` dispatches between the two paths; the four
existing `plugin.tier()` call sites now route through it. Thresholds are precomputed by a
CLI refresh job into a new RLS-scoped `supplier_cluster_cache` table; the engine loads the
latest cell best-effort per request. sklearn/scipy are imported lazily so the
recommendations package still imports without the ML stack.

## Files changed

```
 backend/app/recommendations/engine.py              | 140 ++++++++++-
 backend/app/recommendations/tiering.py             | 279 +++++++++++++++++++++
 backend/requirements.txt                           |   5 +
 backend/scripts/refresh_supplier_clusters.py       | 104 ++++++++
 backend/tests/test_cluster_tiering.py              | 168 +++++++++++++
 supabase/migrations/20260601040000_supplier_cluster_cache.sql | 58 +++++
 6 files changed, 750 insertions(+), 4 deletions(-)
```
(diff vs pipeline base SHA `81d98bc8`, not `main` — see "Branch base".)

## Tests added

`backend/tests/test_cluster_tiering.py` — guarded by `pytest.importorskip("sklearn")`:
- `test_deterministic_seed` — same fixture clustered twice → identical labels/k/silhouette
  (fixed `random_state=42`, `n_init=10`).
- `test_nan_features_excluded` — supplier with a missing feature → label `-1`, excluded
  from the fit; all others clustered.
- `test_under_8_falls_back` — `engine.tier` with a 5-supplier cell → absolute thresholds
  (72 → GOOD_FIT) and `cluster_tiering_fallback_total` increments.
- `test_no_cache_uses_plugin_fallback` — no cache → absolute (90 → BEST_MATCH), counter
  bumps.
- `test_tier_monotonicity_within_cluster` — within a cluster, higher score never yields a
  lower tier.
- `test_top_suppliers_best_match` — top-cutoff score → BEST_MATCH; mid → OK.
- `test_cluster_promotes_good_fit_to_best_match` — **acceptance**: a 30-supplier (banks,
  BE) cell where the top budget bank (norm score 75 = absolute GOOD_FIT) is promoted to
  BEST_MATCH because it tops its own cluster (cluster p85≈72); also asserts the 30-supplier
  cluster compute runs **<5s**.
- `test_tier_with_cluster_context_unknown_cluster_raises` — unknown cluster id raises
  `KeyError` so the caller falls back.

## Test result

- New suite: **8 passed in ~1.4s** (`.venv` with scikit-learn 1.6.1).
- CI deterministic subset (`test_admin_form_templates_router`, `test_trigger_engine`,
  `test_case_dossier_forms`): **55 passed**.
- Regression check — tier/recommendation suites (`test_employee_tiers`,
  `test_service_comparison_engine`, `test_employee_recommendations_filter`): **35 passed**
  (tier label behavior unchanged when no cache is present).
- Import-safety: `engine` + `tiering` import cleanly **without** scikit-learn (verified
  against `backend/.venv`, which lacks it); the new suite **skips cleanly** there
  (`1 skipped`). The bare-`pytest` verify step won't error on an ML-less machine.
- Route-auth audit (`scripts/check_route_auth.py`): **passed** (12 GET routes; Step C adds
  no routes).
- `tsc --noEmit`: not run locally — **no frontend changes** (tier enum values unchanged →
  UI impact None).

## Migration applied?

- File: `supabase/migrations/20260601040000_supplier_cluster_cache.sql`
- **Not yet applied** to remote (left for review → merge → apply via MCP
  `apply_migration`; per repo memory `supabase db push` is blocked by history drift).
- RLS posture — table `supplier_cluster_cache`:
  - RLS enabled: **yes** (`enable row level security`).
  - Policies: `supplier_cluster_cache_read` (SELECT, `authenticated`, `using (true)` —
    tiering metadata is non-PII: no supplier names, no employee data);
    `supplier_cluster_cache_admin_write` (ALL, `authenticated`, USING/WITH CHECK
    `public.is_admin()`); `supplier_cluster_cache_service` (ALL, `service_role`).
  - `REVOKE ALL ON public.supplier_cluster_cache FROM anon`: **yes**.
  - Idempotent guards (`if not exists`, `drop policy if exists`) + rollback block.

## New routes

- None. Tiering is computed inside the existing recommendation engine; no new HTTP surface.

## New tables / schema changes

- `public.supplier_cluster_cache` — `id uuid pk default gen_random_uuid()`,
  `service_category text not null`, `country_iso2 char(2) not null`, `cluster_id int`,
  `cluster_size int`, `k_selected int`, `silhouette numeric`, `thresholds_json jsonb`,
  `supplier_ids_json jsonb`, `computed_at timestamptz not null default now()`. Index on
  `(service_category, country_iso2, computed_at desc)` ("latest cell wins"). One row holds
  the whole cell; `thresholds_json`/`supplier_ids_json` are keyed by cluster id.

## Configuration / env vars added

- None. No feature flag — the engine reads `supplier_cluster_cache` best-effort and falls
  back to absolute thresholds whenever a cell is absent or thin, so the feature dark-ships
  itself: it only activates for a (category, country) once the refresh CLI has populated a
  cell with ≥8 suppliers.

## New dependencies

- `scikit-learn>=1.3`, `scipy>=1.11` (in `backend/requirements.txt`). Imported **lazily**
  inside `tiering.py`, so importing the recommendations package never requires them; tests
  `importorskip("sklearn")`.

## Observability

- Structured JSON line per refreshed cell via the stdlib logger
  (`log.info("cluster_tiering_refresh %s", json.dumps({category, country, k_selected,
  silhouette, supplier_count}))`), matching `ai_trace_logger`'s logging style.
- Process counter `cluster_tiering_fallback_total` (in `tiering.py`, read via
  `tiering.fallback_total()`), incremented every time `engine.tier` falls back to absolute
  thresholds. The CLI prints it in its summary.

## CLI / operations

- `python -m backend.scripts.refresh_supplier_clusters [--category X] [--country YY]` —
  iterates the (category, country) cells (or just the filtered one), recomputes clusters +
  thresholds, and writes one new `supplier_cluster_cache` row per cell. One bad cell logs
  and is skipped without aborting the run.
- **Suggested schedule (not auto-created):** daily off-peak cron —
  `0 3 * * *  python -m backend.scripts.refresh_supplier_clusters`.

## UI changes summary

- New routes added: none.
- New components added: none.
- Existing antigravity components reused: n/a.
- UI-PROPOSAL.md status: not required (UI impact None — the tier label *values*
  (`best_match`/`good_fit`/`ok`/`weak`) are unchanged; only which supplier earns which
  badge shifts).

## Deviations from the original audit prompt

1. **`engine.tier()` is new, not a modified existing function.** The section-4 sketch said
   "modify engine.py `tier(score)`", but the codebase had no `engine.tier()` — it called
   `plugin.tier(norm_score)` at four sites (`engine.py:115/138/248/263`). Step C adds a
   module-level `engine.tier(score, *, category, country_iso2, supplier_id, cache, plugin)`
   that wraps cluster dispatch + absolute fallback, and repoints those four sites at it.
2. **Refresh observability uses structured stdlib logging + a counter, not
   `ai_trace_logger`.** `ai_trace_logger.TraceSession` is request-scoped — it requires
   `session_id`/`query`/`company_id` and hashes a "query" — which is the wrong shape for a
   batch refresh job. Step C emits the same `log.info(..., json.dumps(...))` structured
   line the trace module uses, plus the `cluster_tiering_fallback_total` counter.
3. **Per-supplier cluster lookup from a cached cell, not live re-clustering per request.**
   Clustering runs in the CLI/cron; the engine just loads the latest cell and maps each
   supplier id to its cluster's thresholds. Keeps the request path cheap and deterministic.

## Branch base (important for the PR)

Cut from the pipeline base SHA `81d98bc8` (tip of
`feature/sec-004-rate-limit-coverage`), **independent** of steps A and B (does not stack on
their commits). The PR targets **`feature/sec-004-rate-limit-coverage`** so its diff shows
only the Parker-C changes.

## What downstream steps will need from this step

- **Tiering entry point:** `backend.app.recommendations.engine.tier(score, *, category,
  country_iso2, supplier_id, cache, plugin)` — cluster-relative when `cache` covers the
  cell (≥8 suppliers), else absolute/plugin fallback. `cache` is a dict
  `{cluster_size, thresholds_json, supplier_ids_json}` (a `supplier_cluster_cache` row).
- **Pure clustering core:** `tiering.cluster_suppliers(suppliers, category, country_iso2)
  -> ClusterAssignment(labels, k_selected, silhouette, cluster_sizes)` and
  `tiering.tier_with_cluster_context(score, cluster_id, thresholds_per_cluster) -> Tier`.
  Both DB-free.
- **Cache builder:** `tiering.compute_cluster_cache(category, country_iso2, session?) ->
  row dict | None` (None = thin cell). Reuses `supplier_registry.search_by_service_destination`
  + the category plugin's `score`/`normalize`.
- **Cache table:** `public.supplier_cluster_cache` — latest `computed_at` per
  (service_category, country_iso2) wins. Refresh via the CLI; any later admin UI to inspect
  tiers should read the latest row per cell.
- **Feature vector:** clustering uses `[rating, rating_count, confidence,
  availability_rank]`; suppliers missing any are excluded (label `-1`). Extend
  `tiering._feature_vector` to add features.

## Known gaps / follow-ups

- **No cron is created** — the refresh CLI must be scheduled (suggested daily) or the cache
  goes stale; until a cell is refreshed, that (category, country) uses absolute thresholds.
- **No admin UI** to view/trigger cluster refresh or inspect per-cluster thresholds — CLI
  only for now.
- **Feature set is fixed** (`rating, rating_count, confidence, availability`). Price/SLA/
  preferred-partner signals are candidates for a richer feature vector later.
- **`cluster_id`/`cluster_size` summary columns** on the row are coarse (whole-cell
  totals); the per-cluster detail lives in `thresholds_json`/`supplier_ids_json`. A future
  normalized layout (one row per cluster) could replace the JSON blobs if querying by
  cluster becomes common.
- **Cache TTL never auto-expires** by design ("latest wins"); a stale cell is only
  corrected by re-running the refresh.
