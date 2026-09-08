-- AIQ-1328 follow-up — drop the 2 orphan test suppliers.
--
-- After AIQ-1328b deleted their malformed capability rows, the two TEST
-- suppliers ('testsupplier', 'Supplier Test') remained in public.suppliers with
-- 0 capabilities (status='inactive'). They are test artifacts that shouldn't be
-- in the catalog. Their only FK references were 2 rows in
-- supplier_scoring_metadata (also test artifacts) — delete those first to satisfy
-- the FK, then the suppliers.
--
-- Surgical delete by explicit id. Idempotent. Applied out-of-band via MCP;
-- ledger reconciled at this version. (A 3rd, differently-named 'test' supplier is
-- intentionally left untouched — out of scope.)

DELETE FROM public.supplier_scoring_metadata
WHERE supplier_id IN (
  '7c1d7551-a7a1-4184-b0e2-11f8ceee1fae',
  'e78c5a25-3a10-4e57-9ba4-d5be44ae7bf0'
);

DELETE FROM public.suppliers
WHERE id IN (
  '7c1d7551-a7a1-4184-b0e2-11f8ceee1fae',  -- testsupplier
  'e78c5a25-3a10-4e57-9ba4-d5be44ae7bf0'   -- Supplier Test
);
