-- [AIQ-1674] catalog_destination_requests: user-id columns uuid -> text
--
-- BUG: `requested_by` (uuid NOT NULL) and `resolved_by` (uuid) store app-level ReloPass
-- user ids, but this hybrid-auth system has LEGACY TEXT ids for some accounts. When an HR
-- user with a legacy-text id submits the "request a new destination" flow, the endpoint
-- (scrape_safety.open_destination_request, via POST /api/hr/catalog/populate-destination-with-ai)
-- INSERTs their text id into the uuid column and PostgreSQL raises
--   22P02 invalid input syntax for type uuid
-- The origin 500 has its CORS headers stripped by Cloudflare, so the browser reports a
-- network-level status-0 / "access to server" error and the request is never recorded.
-- Reproduced on prod (rolled back): requested_by='seed-hr-testingapril' -> 22P02.
--
-- FIX: migrate the user-id columns to text, mirroring the established pattern used for
-- notifications.user_id and hr_supplier_submissions user-id columns. `company_id` stays uuid
-- (companies.id is uuid; the cdr_update_hr_or_admin RLS policy compares company_id) — companies
-- are never legacy-text, so only the user-id columns need widening.
--
-- SAFETY: no FK constraints exist on this table; no RLS policy references requested_by /
-- resolved_by (only company_id, unchanged); existing values are uuids, so uuid::text is lossless.
-- Idempotent: each ALTER only runs while the column is still uuid, so re-applying is a no-op.

DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'catalog_destination_requests'
          AND column_name = 'requested_by') = 'uuid' THEN
    ALTER TABLE public.catalog_destination_requests
      ALTER COLUMN requested_by TYPE text USING requested_by::text;
  END IF;

  IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'catalog_destination_requests'
          AND column_name = 'resolved_by') = 'uuid' THEN
    ALTER TABLE public.catalog_destination_requests
      ALTER COLUMN resolved_by TYPE text USING resolved_by::text;
  END IF;
END $$;
