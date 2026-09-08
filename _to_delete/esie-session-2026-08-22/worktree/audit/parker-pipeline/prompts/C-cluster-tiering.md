## Task body — step C

**UI impact:** None. The tier label values (BEST_MATCH/GOOD_FIT/OK/WEAK) are
unchanged, so frontend is unaffected.

Re-engineer the recommendation engine so BEST_MATCH / GOOD_FIT / OK / WEAK tiers are
derived from per-cluster percentiles instead of absolute thresholds (currently
85/70/50). Today, a strong supplier in a thin market gets unfairly demoted — this
is mis-calibrated tiering and HR buyers in small markets notice.

### Prerequisites from prior steps
_None — C is independent._

### Source material
- `backend/app/recommendations/engine.py` — the current scoring + tiering function.
- `backend/app/services/supplier_registry.py` — how suppliers are loaded.
- `backend/app/recommendations/plugins/banks.py` — a representative plugin to read
  the scoring contract.
- `audit/parker-framework-audit.md` section 2 (W15) and section 4, Prompt C.

### Concrete deliverables

1. Add `scikit-learn>=1.3` and `scipy>=1.11` to `backend/requirements.txt` if not
   already there.
2. Create `backend/app/recommendations/tiering.py`:
   - `cluster_suppliers(suppliers, category, country_iso2) -> ClusterAssignment` —
     KMeans with K∈[2,6] selected by silhouette score; returns cluster id per
     supplier plus the silhouette.
   - `tier_with_cluster_context(score, cluster_id, thresholds_per_cluster) -> Tier`
     — returns BEST_MATCH/GOOD_FIT/OK/WEAK based on the per-cluster empirical
     quantiles of the heuristic score (top 15% = BEST_MATCH, next 35% = GOOD_FIT,
     next 35% = OK, bottom 15% = WEAK).
   - `compute_cluster_cache(category, country_iso2) -> dict` — runs the clustering,
     computes per-cluster thresholds, returns the cache payload.
3. Create migration `supabase/migrations/<timestamp>_supplier_cluster_cache.sql`:
   - Table `supplier_cluster_cache(id uuid pk, service_category text, country_iso2
     char(2), cluster_id int, cluster_size int, k_selected int, silhouette numeric,
     thresholds_json jsonb, supplier_ids_json jsonb, computed_at timestamptz)`.
   - Unique on `(service_category, country_iso2, computed_at desc)`.
   - **RLS enabled**. SELECT for authenticated; INSERT/UPDATE for admins only.
     `REVOKE ALL ... FROM anon`.
4. Modify `backend/app/recommendations/engine.py`:
   - `tier(score)` → `tier(score, *, category=None, country_iso2=None)`.
   - When `category` and `country_iso2` are present **and** the cell has ≥ 8
     suppliers in cache, dispatch to `tiering.tier_with_cluster_context`.
   - Otherwise, keep the existing 85/70/50 fallback.
5. Add a scheduled refresh:
   - CLI: `python -m backend.scripts.refresh_supplier_clusters [--category X] [--country Y]`.
   - Suggest a cron entry in `audit/parker-pipeline/runs/<RUN_ID>/C/RESULT.md` for
     Romain to wire up (do not auto-create cron — that's a deploy decision).
6. Observability:
   - Log per-(category, country) cluster K, silhouette score, and supplier count to
     `ai_trace_logger.py` under `feature_key='cluster_tiering_refresh'`.
   - Add metric `cluster_tiering_fallback_total` (Prometheus-style counter) for
     cells that fell back to absolute thresholds because n < 8.
7. Tests in `backend/tests/test_cluster_tiering.py`:
   - Deterministic seed: same suppliers → same clusters → same thresholds.
   - <8 suppliers: falls back to absolute thresholds.
   - Known top-3 supplier in a fixture cluster is tiered BEST_MATCH.
   - Tier monotonicity: higher score within a cluster → no worse tier.

### Design notes
- Use `StandardScaler` before KMeans. Suppliers with NaN features are excluded from
  clustering and tiered with the fallback path.
- Plugin scoring contracts MUST NOT change. The only thing that changes is the
  `engine.tier()` signature, with backward-compatible defaults.
- Cache TTL: do not expire automatically. Refresh is explicit (CLI). The
  `computed_at` column lets readers detect staleness.

### Out of scope
- Re-tiering historical recommendations. New requests use the new tiering; past
  recommendations stay as written.
- Frontend tier badges. The label values are unchanged so frontend is unaffected.

### Acceptance criteria
- pytest passes; tsc passes (no frontend changes).
- Migration applies cleanly.
- For a fixture with 30 suppliers in (banks, BE), at least one supplier moves from
  GOOD_FIT (absolute) to BEST_MATCH (cluster-relative) — assert this in a test.
- `refresh_supplier_clusters` CLI completes for a synthetic seed in < 5 seconds.
