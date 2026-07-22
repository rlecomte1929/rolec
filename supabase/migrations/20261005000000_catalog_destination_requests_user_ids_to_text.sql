-- Fix: HR cannot submit a new-destination request to admin (AIQ-1674).
--
-- POST /api/hr/catalog/populate-destination-with-ai, for an off-allowlist destination, calls
-- scrape_safety.open_destination_request which INSERTs into public.catalog_destination_requests.
-- `requested_by` was uuid NOT NULL, but the backend writes the app-level HR id, which is legacy
-- TEXT for some accounts (e.g. 'seed-hr-testingapril'). The insert failed with
-- '22P02 invalid input syntax for type uuid'; Cloudflare then stripped the origin 500's CORS
-- headers, so the browser reported a network-level "access to server" error and nothing was
-- submitted. Verified on prod (rolled back): a legacy-text INSERT raised 22P02 before this change
-- and succeeded after it. 2 of 1451 public.users rows carry non-uuid ids, so it is reachable.
--
-- Mirrors the established repo pattern for legacy-text user-id columns
-- (20260930000000_notifications_user_id_text; hr_supplier_submissions). `company_id` stays uuid
-- (companies.id is uuid; the cdr_update_hr_or_admin policy scopes on company_id, unchanged). The
-- table has NO foreign-key constraints, and the RLS policies (cdr_insert_hr_or_employee,
-- cdr_update_hr_or_admin) do NOT reference requested_by/resolved_by (verified on prod), so no
-- policy change is required and the cast is lossless. requested_by keeps its NOT NULL (the caller
-- always passes an id); resolved_by stays nullable.
--
-- Idempotent / replay-safe: ALTER ... TYPE text is a no-op once the column is already text.

ALTER TABLE public.catalog_destination_requests
  ALTER COLUMN requested_by TYPE text USING requested_by::text;

ALTER TABLE public.catalog_destination_requests
  ALTER COLUMN resolved_by TYPE text USING resolved_by::text;
