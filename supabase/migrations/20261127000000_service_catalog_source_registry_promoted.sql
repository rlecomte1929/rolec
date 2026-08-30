-- AIQ-2095: allow 'registry_promoted' in service_catalog_items.source.
--
-- PR #2125 added 'registry_promoted' to the app-level VALID_SOURCES
-- (backend/app/services/service_catalog.py) so that supplier_registry.approve_capability
-- forges a linked catalog master when a capability is approved — the missing "last link"
-- that makes an approved supplier reachable by an employee. But it shipped NO migration,
-- and prod's service_catalog_items_source_check only allowed
-- ('scraper','manual','seed','hr_promoted'). Every registry-promoted insert therefore
-- violated the CHECK (SQLSTATE 23514); because the hook is best-effort (try/except),
-- the failure was swallowed and no master was ever created — the fix was a silent no-op
-- in production.
--
-- This reconciles the out-of-band hotfix applied to prod (2026-08-30) that expanded the
-- constraint. Idempotent (DROP IF EXISTS + ADD), additive, and never invalidates an
-- existing row (all existing rows already carry one of the original four values).

ALTER TABLE public.service_catalog_items
  DROP CONSTRAINT IF EXISTS service_catalog_items_source_check;

ALTER TABLE public.service_catalog_items
  ADD CONSTRAINT service_catalog_items_source_check
  CHECK (source = ANY (ARRAY['scraper'::text, 'manual'::text, 'seed'::text, 'hr_promoted'::text, 'registry_promoted'::text]));
