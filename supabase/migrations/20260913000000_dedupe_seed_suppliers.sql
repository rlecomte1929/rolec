-- [AIQ-1511] Deduplicate the supplier registry and prevent recurrence.
--
-- WHY
-- ---
-- A user reported duplicates in the "Add preferred supplier" list on
-- /hr/preferred-suppliers. Verified: public.suppliers held 100 active rows with 100
-- distinct ids but only 90 distinct names. Ten movers existed twice — once with a
-- UUID id, once with the recommendation-dataset id 'm-1'..'m-10'
-- (backend/app/recommendations/datasets/movers.json), created 42 minutes apart on
-- 2026-03-13. Root cause: create_supplier() takes an optional explicit id
-- (supplier_registry.py) and there was no UNIQUE constraint on name and no
-- duplicate-name guard, so seeding the registry twice — once without ids, once
-- passing item_id — inserted both batches.
--
-- WHAT
-- ----
-- 1. Delete the 'm-%' twin of every duplicated name, plus its satellite rows.
-- 2. Add a case-insensitive UNIQUE index on suppliers.name so it cannot recur.
--
-- SAFETY
-- ------
-- The delete is GUARDED, never blind. A row is only removed when a canonical twin
-- exists AND nothing user-generated references it (company_preferred_suppliers,
-- assignment_outcomes, provider_ratings). At authoring time that reference count is
-- 0 for every 'm-%' row — the single existing preference points at the UUID twin —
-- so no FK reassignment is required. The guard is what PROVES that at apply time
-- instead of assuming it: if prod has drifted and a duplicate has acquired real
-- references, the migration raises and aborts rather than destroying data.
--
-- Idempotent: re-running finds no duplicates and is a no-op.

BEGIN;

-- Duplicate set: for each name with >1 row, the 'm-%' seed row is the one to drop and
-- the other (older, UUID-keyed) row is canonical.
CREATE TEMP TABLE _dupe_suppliers ON COMMIT DROP AS
WITH dup_names AS (
    SELECT lower(trim(name)) AS norm_name
    FROM public.suppliers
    GROUP BY lower(trim(name))
    HAVING count(*) > 1
)
SELECT s.id, s.name
FROM public.suppliers s
JOIN dup_names d ON lower(trim(s.name)) = d.norm_name
WHERE s.id LIKE 'm-%'
  -- Only ever drop a row that still has a surviving twin under the same name.
  AND EXISTS (
      SELECT 1 FROM public.suppliers c
      WHERE lower(trim(c.name)) = lower(trim(s.name))
        AND c.id <> s.id
        AND c.id NOT LIKE 'm-%'
  );

-- Guard: refuse to delete anything a human/tenant actually points at.
DO $$
DECLARE
    blocked int;
BEGIN
    SELECT count(*) INTO blocked
    FROM _dupe_suppliers d
    WHERE EXISTS (SELECT 1 FROM public.company_preferred_suppliers x WHERE x.supplier_id = d.id)
       OR EXISTS (SELECT 1 FROM public.assignment_outcomes        x WHERE x.supplier_id = d.id)
       OR EXISTS (SELECT 1 FROM public.provider_ratings           x WHERE x.supplier_id = d.id);

    IF blocked > 0 THEN
        RAISE EXCEPTION
            '[AIQ-1511] Aborting: % duplicate supplier row(s) are referenced by company_preferred_suppliers / assignment_outcomes / provider_ratings. Reassign those references to the canonical supplier before re-running.',
            blocked;
    END IF;
END $$;

-- Satellites first (FK children), then the supplier rows themselves.
DELETE FROM public.vendor_metric_snapshots       WHERE supplier_id IN (SELECT id FROM _dupe_suppliers);
DELETE FROM public.supplier_scoring_metadata     WHERE supplier_id IN (SELECT id FROM _dupe_suppliers);
DELETE FROM public.supplier_service_capabilities WHERE supplier_id IN (SELECT id FROM _dupe_suppliers);
DELETE FROM public.suppliers                     WHERE id          IN (SELECT id FROM _dupe_suppliers);

-- Prevent recurrence. Must come AFTER the dedupe or it fails on the existing rows.
-- Case- and whitespace-insensitive: 'Crown Relocations' and ' crown relocations ' are
-- the same supplier in a global registry.
CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_name_ci
    ON public.suppliers (lower(trim(name)));

COMMIT;
