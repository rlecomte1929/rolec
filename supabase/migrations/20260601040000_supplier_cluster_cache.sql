-- [Parker-C] Cluster-relative supplier tiering cache.
--
-- One row per (service_category, country_iso2) refresh holds the whole cell:
-- thresholds_json and supplier_ids_json are keyed by cluster_id. Reads take the
-- latest row (computed_at desc). Tiering metadata is non-PII (no supplier names,
-- no employee data) — readable by any authenticated user; writes are admin/CLI only.
--
-- Cache never auto-expires: "latest computed_at wins". Refresh is explicit via
-- `python -m backend.scripts.refresh_supplier_clusters`.

create table if not exists public.supplier_cluster_cache (
    id uuid primary key default gen_random_uuid(),
    service_category text not null,
    country_iso2 char(2) not null,
    cluster_id int,
    cluster_size int,
    k_selected int,
    silhouette numeric,
    thresholds_json jsonb,
    supplier_ids_json jsonb,
    computed_at timestamptz not null default now()
);

create index if not exists supplier_cluster_cache_cell_latest_idx
    on public.supplier_cluster_cache (service_category, country_iso2, computed_at desc);

-- ── RLS (CLAUDE.md hard gate) ──────────────────────────────────────────────
alter table public.supplier_cluster_cache enable row level security;

-- Read: any authenticated user (tiering metadata only, non-PII).
drop policy if exists supplier_cluster_cache_read on public.supplier_cluster_cache;
create policy supplier_cluster_cache_read on public.supplier_cluster_cache
    for select to authenticated
    using (true);

-- Write: admins only (the refresh job runs as an admin/service principal).
drop policy if exists supplier_cluster_cache_admin_write on public.supplier_cluster_cache;
create policy supplier_cluster_cache_admin_write on public.supplier_cluster_cache
    for all to authenticated
    using (public.is_admin())
    with check (public.is_admin());

-- service_role bypasses RLS but keep an explicit ALL policy for clarity.
drop policy if exists supplier_cluster_cache_service on public.supplier_cluster_cache;
create policy supplier_cluster_cache_service on public.supplier_cluster_cache
    for all to service_role
    using (true)
    with check (true);

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
revoke all on public.supplier_cluster_cache from anon;

-- ── Rollback ───────────────────────────────────────────────────────────────
-- drop policy if exists supplier_cluster_cache_read on public.supplier_cluster_cache;
-- drop policy if exists supplier_cluster_cache_admin_write on public.supplier_cluster_cache;
-- drop policy if exists supplier_cluster_cache_service on public.supplier_cluster_cache;
-- drop index if exists public.supplier_cluster_cache_cell_latest_idx;
-- drop table if exists public.supplier_cluster_cache;
