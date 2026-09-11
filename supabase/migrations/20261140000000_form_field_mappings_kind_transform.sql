-- Additive columns for data-driven field shapes (form-onboarding Phase 1a). No re-key, no new table.
-- field_kind: text | date_part | single_radio | checkbox_option (default text -> existing rows unchanged).
-- transform_spec: typed successor to open format_rule strings + the radio code->export map.
-- NOTHING reads these columns in the PR that adds them (check_column_read_before_apply gate).
ALTER TABLE public.form_field_mappings
  ADD COLUMN IF NOT EXISTS field_kind    TEXT NOT NULL DEFAULT 'text',
  ADD COLUMN IF NOT EXISTS transform_spec JSONB;
