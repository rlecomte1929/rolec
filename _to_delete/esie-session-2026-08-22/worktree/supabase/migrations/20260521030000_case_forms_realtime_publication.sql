-- ============================================================
-- [P1-5B] Add public.case_forms to the supabase_realtime publication
-- Date: 2026-05-21
--
-- Purpose: lets the Dossier & Forms page receive INSERT/UPDATE events
-- when the Trigger Engine (P1-3) creates new case_forms rows or when
-- a form's status/completion advances. Without this, the frontend would
-- need to poll for new rows.
--
-- Safety: the existing RLS policy `case_forms_via_case` still gates which
-- rows each subscriber sees — Realtime respects RLS by default.
--
-- Replica identity is left at default ('d' / primary key) because we only
-- need to identify rows; full-row payloads are not required for the
-- frontend's refetch-on-event handler.
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE public.case_forms;
