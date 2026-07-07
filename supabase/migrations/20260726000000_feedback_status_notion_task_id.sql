-- Migration: add notion_task_id to feedback_status
--
-- dispatch_create writes this column after creating the Notion page.
-- Format: dashless, lowercase, 32-hex (the Notion page UUID with hyphens stripped).
-- Used as the join key for the autopilot-event bridge:
--   substr(notion_task_id, 1, 16) == lower(event.entity_id)
--
-- Idempotent: IF NOT EXISTS guard means safe to run twice.

ALTER TABLE public.feedback_status
  ADD COLUMN IF NOT EXISTS notion_task_id text;
