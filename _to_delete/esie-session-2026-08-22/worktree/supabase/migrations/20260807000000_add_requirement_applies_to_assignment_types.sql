-- AIQ-1349 follow-up — data-driven requirement applicability by assignment type.
--
-- Lets a requirement declare which assignment types it applies to, so the
-- requirements engine can filter per case WITHOUT hardcoded title heuristics.
-- Semantics: NULL / absent ⇒ applies to ALL assignment types (back-compat).
-- A JSON array (e.g. '["LTA","PERMANENT"]') ⇒ applies ONLY to those types; the
-- requirement is dropped for a case whose assignment_type is not listed.
--
-- Stored as TEXT JSON to match the existing _json columns on this table
-- (required_fields_json, citations_json) and stay SQLite-test-compatible.
-- requirement_items already has RLS; a new column needs no new policy. Idempotent.

ALTER TABLE public.requirement_items
  ADD COLUMN IF NOT EXISTS applies_to_assignment_types_json text;
