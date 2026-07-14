-- [AIQ-1529] Deduplicate service_catalog_items: collapse UUID-keyed duplicate rows
-- into their m-N canonical twins, then add a UNIQUE index to prevent recurrence.
--
-- WHY
-- ---
-- The seed ran twice: first without explicit ids (creating uuid-keyed rows), then
-- passing dataset ids ('m-1'..'m-10') as external_id into NEW rows for the same names.
-- Result: 10 movers each have TWO catalog items — one with external_id='m-N' (used by
-- the recommendation engine) and one with external_id=<supplier-uuid> (dead weight).
-- HR is ticking both entries in /hr/vendor-curation, believing them to be different vendors.
--
-- THE external_id TRAP (learned in AIQ-1520):
-- The recommendation engine resolves rec.item_id → service_catalog_items.external_id.
-- Deleting an m-N item would silently hide that vendor from all employee recommendations.
-- CANONICAL = the m-N item. DELETE only the uuid-keyed twin.
--
-- MEASURED ON 2026-07-14 (prod):
--   service_catalog_items:                   82 rows, 10 duplicate (category,name) pairs
--   company_vendor_selections (selected=true): 20 rows, 0 pointing at uuid-keyed items
--   FK tables referencing service_catalog_items: company_vendor_selections.master_item_id only
--
-- SAFETY PROPERTIES
-- -----------------
-- 1. Guarded: RAISES if any to-be-deleted row has no canonical m-N twin.
-- 2. Reassigns company_vendor_selections.master_item_id before deleting (no-op in prod
--    today; kept for safety in case prod drifts between authoring and apply time).
-- 3. Guard 2: RAISES if any FK reference remains after reassignment.
-- 4. Idempotent: re-running finds 0 duplicates and skips all deletes; index is IF NOT EXISTS.

BEGIN;

-- ── Step 1: identify UUID-keyed duplicates and their canonical m-N twins ──────
CREATE TEMP TABLE _dupe_catalog ON COMMIT DROP AS
WITH dup_names AS (
    SELECT category, lower(trim(name)) AS norm_name
    FROM public.service_catalog_items
    GROUP BY category, lower(trim(name))
    HAVING count(*) > 1
),
uuid_dups AS (
    SELECT dup.id, dup.external_id, dup.name, dup.category
    FROM public.service_catalog_items dup
    JOIN dup_names d ON lower(trim(dup.name)) = d.norm_name AND dup.category = d.category
    -- UUID-keyed rows: external_id does NOT match the 'm-N' dataset pattern
    WHERE dup.external_id NOT LIKE 'm-%'
)
SELECT
    ud.id            AS dup_id,
    ud.external_id   AS dup_external_id,
    ud.name          AS dup_name,
    ud.category      AS dup_category,
    -- Resolve canonical m-N twin by (category, normalised name)
    (SELECT c.id FROM public.service_catalog_items c
     WHERE c.category = ud.category
       AND lower(trim(c.name)) = lower(trim(ud.name))
       AND c.external_id LIKE 'm-%'
     LIMIT 1)        AS canonical_id
FROM uuid_dups ud;

-- ── Guard 1: every to-be-deleted row must resolve to an m-N canonical twin ───
DO $$
DECLARE bad_count int;
BEGIN
    SELECT count(*) INTO bad_count FROM _dupe_catalog WHERE canonical_id IS NULL;
    IF bad_count > 0 THEN
        RAISE EXCEPTION
            '[AIQ-1529] Aborting: % duplicate service_catalog_items row(s) have no m-N '
            'canonical twin — cannot deduplicate safely. Manual review required.',
            bad_count;
    END IF;
END $$;

-- ── Idempotency check: skip everything if there are no duplicates ─────────────
DO $$
DECLARE dup_count int;
BEGIN
    SELECT count(*) INTO dup_count FROM _dupe_catalog;
    IF dup_count = 0 THEN
        RAISE NOTICE '[AIQ-1529] No duplicate catalog items found — migration is a no-op.';
    END IF;
END $$;

-- ── Step 2a: if a CVS row points at a UUID item AND the same company already has a CVS
--    row pointing at the canonical item, DELETE the UUID CVS row (can't reassign — would
--    violate uniqueness).
DELETE FROM public.company_vendor_selections cvs
USING _dupe_catalog dc
WHERE cvs.master_item_id = dc.dup_id
  AND EXISTS (
      SELECT 1 FROM public.company_vendor_selections existing
      WHERE existing.master_item_id = dc.canonical_id
        AND existing.company_id     = cvs.company_id
        AND existing.category       = cvs.category
  );

-- ── Step 2b: reassign remaining CVS rows pointing at UUID items → canonical ───
UPDATE public.company_vendor_selections cvs
SET master_item_id = dc.canonical_id
FROM _dupe_catalog dc
WHERE cvs.master_item_id = dc.dup_id;

-- ── Guard 2: no CVS row may still reference a to-be-deleted item ──────────────
DO $$
DECLARE blocked int;
BEGIN
    SELECT count(*) INTO blocked
    FROM _dupe_catalog dc
    WHERE EXISTS (
        SELECT 1 FROM public.company_vendor_selections x
        WHERE x.master_item_id = dc.dup_id
    );
    IF blocked > 0 THEN
        RAISE EXCEPTION
            '[AIQ-1529] Aborting: % to-be-deleted catalog item(s) still referenced by '
            'company_vendor_selections after reassignment attempt. Manual review required.',
            blocked;
    END IF;
END $$;

-- ── Step 3: delete the UUID-keyed duplicates ─────────────────────────────────
DELETE FROM public.service_catalog_items
WHERE id IN (SELECT dup_id FROM _dupe_catalog);

-- ── Step 4: UNIQUE index — prevents the seed-twice bug from recurring ─────────
CREATE UNIQUE INDEX IF NOT EXISTS uq_service_catalog_items_category_name_ci
    ON public.service_catalog_items (category, lower(trim(name)));

-- ── Sanity counts for the commit log ─────────────────────────────────────────
DO $$
DECLARE
    remaining_dups   int;
    catalog_count    int;
    selected_count   int;
BEGIN
    SELECT count(*) INTO remaining_dups
    FROM (
        SELECT category, lower(trim(name))
        FROM public.service_catalog_items
        GROUP BY 1, 2
        HAVING count(*) > 1
    ) d;

    SELECT count(*) INTO catalog_count FROM public.service_catalog_items;
    SELECT count(*) INTO selected_count FROM public.company_vendor_selections WHERE selected = true;

    RAISE NOTICE '[AIQ-1529] After: catalog=%, selected_true=%, remaining_dup_pairs=%',
        catalog_count, selected_count, remaining_dups;

    IF remaining_dups > 0 THEN
        RAISE EXCEPTION '[AIQ-1529] Aborting: % duplicate pairs remain after migration — unexpected state.', remaining_dups;
    END IF;
END $$;

COMMIT;
