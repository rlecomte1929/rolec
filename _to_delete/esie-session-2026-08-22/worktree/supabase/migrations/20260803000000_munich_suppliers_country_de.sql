-- AIQ-1328a — correct Munich vendors mis-tagged country 'US' to 'DE'.
--
-- The admin vendor catalog (/admin/suppliers) showed 12 real Munich vendors
-- (Bogenhausen/Haidhausen/Schwabing/Maxvorstadt/Pasing/Sendling Housing + 6
-- Munich international schools) with country_code='US', so HR filtering by
-- Germany missed them. Data lives in public.supplier_service_capabilities
-- (city_name, country_code) — NOT public.suppliers (no city/country columns).
--
-- Scoped strictly to Munich: the other ~20 non-Munich US rows, plus SG/NO, are
-- untouched. Idempotent (re-run matches 0 rows). Applied out-of-band via MCP;
-- ledger reconciled at this version.

UPDATE public.supplier_service_capabilities
SET country_code = 'DE'
WHERE city_name = 'Munich' AND country_code = 'US';
