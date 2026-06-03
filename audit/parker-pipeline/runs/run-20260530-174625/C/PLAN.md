# Step C PLAN — Cluster-relative supplier tiering

_Run: run-20260530-174625 | Branch: audit/parker-step-C-cluster-tiering | Base SHA: 81d98bc8_

## Goal

Today every supplier is tiered with **absolute** thresholds (`>=85 BEST_MATCH`,
`>=70 GOOD_FIT`, `>=50 OK`, else `WEAK`) by `BasePlugin.tier()` in
`backend/app/recommendations/plugins/base.py`. In a thin market (e.g. banks in BE) all
suppliers can land in one tier, so the badge stops discriminating. Step C makes tiering
**cluster-relative**: within a (category, country) cell, cluster suppliers on their
feature profile (KMeans, K chosen by silhouette) and tier each supplier by its
**percentile inside its own cluster** (top 15% BEST_MATCH, next 35% GOOD_FIT, next 35%
OK, bottom 15% WEAK). When a cell is too thin (<8 suppliers) we fall back to the existing
absolute thresholds, so behavior never degrades.

Step C is **independent** — no prereqs on steps A/B.

## Ground-truth reconciliation (audit sketch vs. actual code)

The audit prompt's section-4 sketch says "modify engine.py `tier(score)`". **There is no
`engine.tier()` today** — the engine calls `plugin.tier(norm_score)` at four sites
(`engine.py:115`, `:138`, `:248`, `:263`; the first pair in `recommend()`, the second in
`recommend_debug()`). So the real change is: add a module-level `engine.tier(...)` that
wraps cluster dispatch + absolute fallback, and repoint those four call sites at it. This
is **deviation #1** (documented in RESULT).

`category` is a direct param of `recommend()`/`recommend_debug()`; country comes from
`criteria["destination_country"]` (already read at `engine.py:31` and `:190`), normalized
to ISO-2 via `.upper()[:2]` — the same derivation `supplier_registry` uses.

## Concrete deliverables

### 1. Dependencies — `backend/requirements.txt`
Add (neither present on base 81d98bc8; Step A's adds live on A's branch, not here):
```
scikit-learn>=1.3   # [Parker-C] KMeans + silhouette for cluster-relative tiering
scipy>=1.11         # transitive for sklearn; pinned for reproducibility
```
Imported **lazily** inside `tiering.py` functions (not at module top) so importing the
recommendations package never requires sklearn — same import-safety pattern as Parker-B's
PuLP. Tests use `pytest.importorskip("sklearn")`.

### 2. `backend/app/recommendations/tiering.py` (new, pure/DB-free core)
- `@dataclass(frozen=True) ClusterAssignment`: `labels: list[int]` (per input supplier;
  `-1` = excluded for NaN features), `k_selected: int`, `silhouette: float`,
  `cluster_sizes: dict[int, int]`.
- `FEATURE_KEYS` + `_feature_vector(supplier) -> list[float] | None` — extract
  `[rating, rating_count, confidence, availability_numeric]` from the supplier dict
  (`availability_level` high/medium/low → 3/2/1). Returns `None` if any feature missing →
  that supplier is excluded from clustering (label `-1`).
- `cluster_suppliers(suppliers, category, country_iso2) -> ClusterAssignment` — lazy
  `from sklearn.cluster import KMeans; from sklearn.preprocessing import StandardScaler;
  from sklearn.metrics import silhouette_score`. StandardScaler → fit KMeans for K in
  `[2..min(6, n_valid-1)]`, pick K with best silhouette (`random_state=42, n_init=10`).
  Deterministic.
- `tier_with_cluster_context(score, cluster_id, thresholds_per_cluster) -> RecommendationTier`
  — `thresholds_per_cluster[cluster_id] = {"best": p85, "good": p50, "ok": p15}` (score
  cutoffs from that cluster's score distribution). `score>=best→BEST_MATCH`,
  `>=good→GOOD_FIT`, `>=ok→OK`, else `WEAK`. Unknown cluster_id → raise so caller falls
  back.
- `compute_cluster_cache(category, country_iso2, session=None) -> dict` — load suppliers
  via `supplier_registry.search_by_service_destination`, score each with the category
  plugin, run `cluster_suppliers`, compute per-cluster percentile thresholds
  (numpy.percentile at 85/50/15), and return the row payload: `service_category`,
  `country_iso2`, `k_selected`, `silhouette`, `cluster_size` (total clustered),
  `thresholds_json`, `supplier_ids_json` (`{cluster_id: [supplier_id,...]}`),
  `computed_at`.

**Percentile tiering = top 15 / 35 / 35 / 15.** p85 cutoff → top 15% are BEST_MATCH; p50 →
next 35% GOOD_FIT; p15 → next 35% OK; below → bottom 15% WEAK. Matches the prompt's split.

### 3. Migration `supabase/migrations/20260601040000_supplier_cluster_cache.sql`
`public.supplier_cluster_cache(id uuid pk default gen_random_uuid(),
service_category text not null, country_iso2 char(2) not null, cluster_id int,
cluster_size int, k_selected int, silhouette numeric, thresholds_json jsonb,
supplier_ids_json jsonb, computed_at timestamptz not null default now())`. One row per
(category, country) refresh holds the whole cell (thresholds_json/supplier_ids_json keyed
by cluster_id), so `cluster_id`/`cluster_size` at row level are summary columns. Index +
"latest wins" lookup on `(service_category, country_iso2, computed_at desc)`.
**RLS hard gate (CLAUDE.md):** `enable row level security`; SELECT policy for
`authenticated` (tiering metadata is non-PII, readable by any signed-in user); INSERT/UPDATE
restricted to `public.is_admin()` (refresh is an admin/CLI job); `service_role` ALL;
`revoke all ... from anon`. Idempotent guards + rollback block. **Not applied** (left for
review→MCP `apply_migration`).

### 4. `engine.py` tier dispatch
Add module-level:
```python
def tier(score, *, category=None, country_iso2=None, supplier_id=None,
         cache=None, plugin=None) -> RecommendationTier:
```
- If `cache` (a loaded cell) present, total clustered suppliers `>=8`, and `supplier_id`
  maps to a cluster → return `tiering.tier_with_cluster_context(...)`.
- Else increment `cluster_tiering_fallback_total` and fall back to `plugin.tier(score)`
  (preserves any plugin-specific override) or absolute 85/70/50 when no plugin.
- `recommend()`/`recommend_debug()` load the cell **once** (best-effort, never fails the
  request) via a `_load_cluster_cache(category, country_iso2)` helper, then pass it into
  the four `tier(...)` call sites. Plugin `score()`/`normalize()` contracts **unchanged**.

### 5. CLI `backend/scripts/refresh_supplier_clusters.py`
`python -m backend.scripts.refresh_supplier_clusters [--category X] [--country YY]`.
Iterates the (category, country) cells (or just the filtered one), calls
`compute_cluster_cache`, writes a new `supplier_cluster_cache` row per cell. Prints a
summary table. **Suggest** a daily cron in RESULT.md — do not auto-create one.

### 6. Observability
ai_trace_logger's `TraceSession` is **request-scoped** (needs `session_id`/`query`/
`company_id`, hashes a query) — wrong shape for a batch refresh. **Deviation #2:** emit
structured JSON via the stdlib logger in the same `log.info("...", json.dumps(...))` style
the trace module uses — one line per cell with `{category, country, k_selected,
silhouette, supplier_count}` — and keep a process counter `cluster_tiering_fallback_total`
(module-level int in `tiering.py`, exposed via a getter; incremented in `engine.tier`
fallback path).

### 7. Tests `backend/tests/test_cluster_tiering.py` (`importorskip("sklearn")`)
- `test_deterministic_seed` — same fixture clustered twice → identical labels/silhouette.
- `test_under_8_falls_back` — 5-supplier cell → `engine.tier` uses absolute thresholds and
  bumps `cluster_tiering_fallback_total`.
- `test_top3_best_match` — in a clear cluster, the top-percentile suppliers get BEST_MATCH.
- `test_tier_monotonicity` — higher score never yields a lower tier within a cluster.
- `test_nan_features_excluded` — supplier missing `rating` → label `-1`, not clustered.
- **Acceptance:** 30-supplier (banks, BE) fixture where cluster-relative tiering moves
  `>=1` supplier `GOOD_FIT→BEST_MATCH` vs. absolute; assert the CLI cell compute runs
  `<5s`.

## Constraints honored
- **No plugin scoring contract change** — only the tier *label* mapping gains a
  cluster-aware path; tier enum values unchanged → **UI impact: None**.
- **Import-safety** — sklearn/scipy lazy; bare-`pytest` verify skips cleanly without them.
- **RLS hard gate** — new table RLS-enabled, policy'd, anon-revoked.
- **Cache TTL never auto-expires** — "latest computed_at wins"; refresh is explicit (CLI/cron).
- **Do not apply the migration. Do not merge the PR.** PR targets
  `feature/sec-004-rate-limit-coverage`.

## Deviations (carried to RESULT)
1. `engine.tier()` is **new** (the sketch assumed it existed; code uses `plugin.tier()`).
2. Refresh observability uses **structured stdlib logging + a counter**, not
   `ai_trace_logger` (which is request/query-scoped, not batch-job-scoped).
