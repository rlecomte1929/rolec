-- AUDIT-3 / AIQ-1127: consolidate the audit trail. Backfill the 554 clean mutation
-- rows from the orphaned legacy public.audit_log into the canonical audit_logs
-- (Option A — mutations only; the 2,919 READ access events and 9 malformed rows
-- with non-uuid/null targets are intentionally NOT copied), then drop the legacy
-- table. Pre-launch test data; verified on a rollback-tx before applying (added
-- exactly 554, CREATE->insert + event preserved). No writers (AUDIT-2 #806) and
-- no readers target audit_log. No new table -> 3-part RLS gate N/A.
-- Idempotent: the to_regclass guard makes a re-run a no-op once dropped.
DO $$
DECLARE _uuid_re text := '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
BEGIN
  IF to_regclass('public.audit_log') IS NULL THEN
    RAISE NOTICE 'audit_log already absent -- nothing to do';
    RETURN;
  END IF;

  INSERT INTO public.audit_logs
    (id, entity_type, entity_id, action_type, old_value_json, new_value_json, actor_type, actor_id, created_at)
  SELECT
    gen_random_uuid(),
    COALESCE(NULLIF(target_type, ''), 'unknown'),
    target_id::uuid,
    CASE WHEN upper(action_type) = 'CREATE' THEN 'insert'
         WHEN upper(action_type) IN ('DELETE','DESTROY','PURGE') THEN 'delete'
         ELSE 'update' END,
    NULL::jsonb,
    COALESCE(NULLIF(metadata_json, '')::jsonb, '{}'::jsonb)
      || CASE WHEN reason IS NOT NULL AND reason <> '' THEN jsonb_build_object('reason', reason) ELSE '{}'::jsonb END
      || jsonb_build_object('event', action_type),
    'human',
    CASE WHEN actor_user_id ~* _uuid_re THEN actor_user_id::uuid ELSE NULL END,
    created_at::timestamptz
  FROM public.audit_log
  WHERE upper(action_type) <> 'READ' AND target_id ~* _uuid_re;

  DROP TABLE public.audit_log;
END $$;
