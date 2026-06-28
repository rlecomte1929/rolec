-- AIQ-1328b — remove test-supplier capability rows polluting the catalog filter.
--
-- Two rows in public.supplier_service_capabilities had a malformed country_code
-- ('U') and a NULL, both city_name=NULL, both 'movers', and both owned by TEST
-- suppliers ('testsupplier' / 'Supplier Test'). The 'U' surfaced in the admin
-- /suppliers country filter, which is DB-derived (DISTINCT country_code), so
-- deleting these rows clears the stray entry — no frontend change needed.
--
-- Surgical delete by explicit id (no risk to real vendor rows). The 2 orphan
-- parent test suppliers in public.suppliers are left for a separate hygiene pass.
-- Idempotent. Applied out-of-band via MCP; ledger reconciled at this version.

DELETE FROM public.supplier_service_capabilities
WHERE id IN (
  'fdb38968-03f9-4802-9b12-969c8ca9f992',  -- country_code='U',  testsupplier
  'b7f35966-a5a8-46a9-b623-ef6e132d02fe'   -- country_code=NULL, Supplier Test
);
