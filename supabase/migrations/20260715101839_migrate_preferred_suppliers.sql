-- [AIQ-1531] S3 · Migrate the 2 company_preferred_suppliers rows honestly, then write-deprecate.
--
-- company_preferred_suppliers was a soft "+15 ranking boost" pool that consolidation retires in
-- favour of company_vendor_selections (CVS — the hard visibility gate + display_order intent).
-- S2 (#1486) already repointed the boost at CVS, so nothing reads this table any more. Two rows
-- remain, and NEITHER migrates mechanically:
--
--   1. Transworld Relocation (company 256e5f41, supplier 2876243d-bb7a-4df1-8a30-93e1003073a7,
--      movers, priority_rank 10). Post-S1 dedupe it maps to EXACTLY ONE catalog item
--      (service_catalog_items 58823e8d-b634-45b6-bdb4-9ffde395c9a7). It is NOT currently curated
--      for its company, so its old +15 preference was inert (the hard gate hid it). We migrate it
--      into CVS as selected=true to REALISE HR's expressed preference — Transworld becomes a
--      curated, visible mover for 256e5f41 (approved decision, 2026-07-15). display_order carries
--      priority_rank (10). No customer data in prod, so no live employee is surprised.
--
--   2. Arabian Ranches (supplier 'la-du4', company 7cb00c1c, filed as movers, priority_rank 5)
--      maps to ZERO catalog items — a LIVING-AREAS supplier mis-filed under movers. DROPPED, not
--      re-homed: we do not guess a category for a mis-filed vendor. A data correction, not loss.
--
-- Then write-deprecate the table (REVOKE writes from `authenticated` + COMMENT). NOTE this REVOKE
-- is a REAL revocation: 20260824000000_company_preferred_suppliers_hr_rls.sql granted authenticated
-- INSERT/UPDATE/DELETE. SELECT is left intact (matches the vendors deprecation precedent). The
-- backend writes via the service-role DATABASE_URL connection, so it is unaffected. The table is
-- NOT dropped — honesty pattern (retain for audit), mirroring 20260825000000_deprecate_vendors_write.

BEGIN;

-- (1) GUARD — hard-abort if S1 catalog dedupe is not applied (Transworld must map to exactly 1 item).
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM public.service_catalog_items
   WHERE supplier_id = '2876243d-bb7a-4df1-8a30-93e1003073a7' AND category = 'movers';
  IF n <> 1 THEN
    RAISE EXCEPTION 'S1 dedupe not applied — Transworld maps to % movers catalog items (expected 1); aborting', n;
  END IF;
END $$;

-- (2) Migrate Transworld into curation (selected + ranked). Idempotent via NOT EXISTS — the
--     partial unique index has destination_city in its key, and NULLs are distinct, so ON CONFLICT
--     would not catch a re-run here; the explicit guard does.
INSERT INTO public.company_vendor_selections (company_id, category, master_item_id, selected, display_order)
SELECT '256e5f41-5abe-47ee-aa73-f8862c63ad27', 'movers', '58823e8d-b634-45b6-bdb4-9ffde395c9a7', true, 10
WHERE NOT EXISTS (
  SELECT 1 FROM public.company_vendor_selections
   WHERE company_id = '256e5f41-5abe-47ee-aa73-f8862c63ad27'
     AND master_item_id = '58823e8d-b634-45b6-bdb4-9ffde395c9a7'
);

-- (3) Retire both source rows.
--     Transworld: migrated out (its data now lives in CVS; content preserved in this comment for
--       rollback → company 256e5f41, supplier 2876243d…, movers, priority_rank 10).
--     Arabian Ranches (la-du4): DROPPED — living-areas supplier incorrectly filed as movers with
--       no service_catalog_items match; not a data loss, a data correction.
DELETE FROM public.company_preferred_suppliers
 WHERE (company_id = '256e5f41-5abe-47ee-aa73-f8862c63ad27' AND supplier_id = '2876243d-bb7a-4df1-8a30-93e1003073a7')
    OR (company_id = '7cb00c1c-4934-4b38-8c98-6c8b8187464e' AND supplier_id = 'la-du4');

-- (4) Write-deprecate the table (real revocation — see header). SELECT left intact.
REVOKE INSERT, UPDATE, DELETE ON public.company_preferred_suppliers FROM authenticated;

COMMENT ON TABLE public.company_preferred_suppliers IS
  'DEPRECATED — use company_vendor_selections (HR curation). Rows migrated + write access removed 2026-07-15 by AIQ-1531. Retained read-only for audit; not dropped. Dropped supplier la-du4 (Arabian Ranches): living-areas supplier mis-filed as movers, no catalog match — a data correction.';

COMMIT;
