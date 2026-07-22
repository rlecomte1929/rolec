-- Ledger reconciliation (prod-as-oracle). This version was applied to prod out-of-band
-- via MCP and had no repo file, which fails the migration-drift check and `db push` for
-- everyone. SQL recovered verbatim from supabase_migrations.schema_migrations.statements,
-- wrapped with an existence guard so a fresh Preview replay is idempotent.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vendors'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'vendors_legacy'
  ) THEN
    ALTER TABLE public.vendors RENAME TO vendors_legacy;
  END IF;
END $$;
