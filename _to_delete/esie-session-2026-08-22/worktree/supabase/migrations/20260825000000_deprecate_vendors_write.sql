-- =============================================================================
-- Supplier Catalog GAP 6: deprecate direct writes to public.vendors
--
-- suppliers + supplier_service_capabilities (System A) is the source of truth for
-- the supplier catalog. public.vendors (redesign schema, ~8 demo rows) is retained
-- read-only for the RFQ vendor-name join (db/vendors.validate_vendor_ids) and the
-- legacy HR "Service providers" list. Its rows are migrated into suppliers by
-- backend/scripts/migrate_vendors_to_suppliers.py.
--
-- Defense-in-depth: ensure the `authenticated` role cannot write vendors. On prod
-- `authenticated` already holds no table grants (writes go through the admin-role
-- RLS policy vendors_admin_write / the service_role backend), so this REVOKE is a
-- no-op that documents and locks the intent. SELECT is left intact. Idempotent.
-- =============================================================================

BEGIN;

REVOKE INSERT, UPDATE, DELETE ON public.vendors FROM authenticated;

COMMENT ON TABLE public.vendors IS
  'DEPRECATED for writes. Source of truth is public.suppliers + supplier_service_capabilities (System A). Retained read-only for RFQ vendor-name resolution and the legacy HR service-providers list. See docs/supplier-systems-state.md.';

COMMIT;
