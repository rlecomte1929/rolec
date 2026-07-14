-- [AIQ-1514] Persist the vendors an employee actually shortlisted on a quote request.
--
-- WHY
-- ---
-- The employee shortlists specific vendors on the recommendations page and submits
-- "Send quotation requests". The page promises "you send your requirements to your
-- shortlisted vendors" — but the vendor identity was dropped at the API boundary:
-- ServicesRfqNew.tsx sent only `service_categories` plus a free-text `notes` string
-- ("VendorName: note | VendorName2: note"). public.quote_requests had NO vendor column,
-- so HR never learned which vendors the employee picked. 51 rows already exist with the
-- choice unrecoverable — they keep an empty array; we do not fabricate it.
--
-- WHY jsonb AND NOT AN FK
-- ----------------------
-- The recommendation `item_id` is NOT a stable foreign key. Two shapes flow through it:
--   * master vendors  -> item_id = service_catalog_items.external_id, resolved via
--     find_master_by_external_id(category, item_id). Ambiguous WITHOUT the category.
--   * HR-custom vendors -> item_id = 'hr-custom-<company_vendor_selections.id>', which
--     has no master row at all.
-- So we store the lossless (service_category, item_id, name) triple rather than pretend
-- an FK exists. Shape: [{"service_category": "movers", "item_id": "...", "name": "..."}]
--
-- No new table => the RLS/policy/REVOKE hard gate does not apply. quote_requests already
-- has RLS enabled with 2 policies and no anon SELECT grant (verified in prod).

ALTER TABLE public.quote_requests
    ADD COLUMN IF NOT EXISTS vendors jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN public.quote_requests.vendors IS
    'Vendors the employee shortlisted, as [{service_category, item_id, name}]. item_id is a '
    'recommendation-engine id (service_catalog_items.external_id for master vendors, or '
    'hr-custom-<company_vendor_selections.id>) — meaningful only together with service_category, '
    'which is why this is not a foreign key. Empty array = pre-AIQ-1514 row; the choice was not captured.';
