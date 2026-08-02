-- [AIQ-1676] Remove supplier_service_capabilities rows still tagged service_category='living_areas'.
--
-- Since the AIQ-1652 rework, 'living_areas' is ADVISORY-only — it renders from static/geo data and
-- must have ZERO rows in the suppliers/capabilities tables. cleanup_la_supplier_shells
-- (20261001000000) removed ~38 neighbourhood-as-supplier shells but keyed on the 'la-' id prefix;
-- two rows use plain UUIDs and escaped:
--   NestFinders Europe  (supplier 6236220c-b96a-4e9b-88ba-dcbf4d6ff862, capability 0722c954…)
--   BerlinReloc GmbH    (supplier a1e80a3f-3049-48a8-80d3-b50d25f9b68a, capability 08d971c6…)
--
-- Both are platform_vetting_status='rejected' SYNTHETIC demo-seed vendors ("Synthetic demo-seed
-- vendor; not a verified real provider"), country_code NULL — the same junk class as the shells
-- the earlier cleanup deleted. We DELETE rather than re-map: re-tagging rejected demo seeds into a
-- real category (housing_agencies) would pollute it. Keyed on service_category (not the 'la-'
-- prefix) so any future straggler is caught too. Idempotent: re-running deletes 0 rows.

DELETE FROM public.supplier_service_capabilities
WHERE service_category = 'living_areas';
