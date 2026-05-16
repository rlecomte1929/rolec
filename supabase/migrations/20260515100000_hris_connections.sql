-- =============================================================================
-- AIQ-72 (AIQ-33-D): HRIS connections + Personio sync log
-- Creates two tables needed for the ReloPass → Personio case status sync.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- hris_connections
-- One row per connected HRIS workspace (Personio, Workday, etc.).
-- Tokens are AES-256-GCM encrypted at rest using HRIS_TOKEN_ENCRYPTION_KEY.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.hris_connections (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id          text NOT NULL,             -- FK → companies.id
  provider            text NOT NULL DEFAULT 'personio'
                        CHECK (provider IN ('personio', 'workday', 'sap')),
  -- Encrypted OAuth tokens (hex-encoded ciphertext).
  -- Use HRIS_TOKEN_ENCRYPTION_KEY env var in Edge Function to decrypt.
  access_token_enc    text,
  refresh_token_enc   text,
  token_expiry        timestamptz,
  -- Personio-specific: base URL (partner accounts differ), client IDs
  base_url            text NOT NULL DEFAULT 'https://api.personio.de',
  client_id           text,
  -- JSON field-mapping overrides.
  -- Default maps: relocation_status, relocation_case_url, estimated_completion_date
  -- Schema: { "relocation_status": "<personio_field_id>", ... }
  field_mappings      jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Connection health
  status              text NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'disconnected', 'error')),
  last_sync_at        timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  -- One active connection per company per provider
  UNIQUE (company_id, provider)
);

-- Trigger to keep updated_at current
CREATE OR REPLACE FUNCTION public.fn_hris_connections_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_hris_connections_updated_at ON public.hris_connections;
CREATE TRIGGER trg_hris_connections_updated_at
  BEFORE UPDATE ON public.hris_connections
  FOR EACH ROW EXECUTE FUNCTION public.fn_hris_connections_updated_at();

-- RLS: HR users can only see their own company's connection (read-only).
-- Writes go through the Edge Function using service role.
ALTER TABLE public.hris_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "hr_can_read_own_connection"
  ON public.hris_connections FOR SELECT
  TO authenticated
  USING (
    company_id IN (
      SELECT company_id FROM public.hr_users
      WHERE user_id = (SELECT auth.uid())
    )
  );

-- ---------------------------------------------------------------------------
-- personio_sync_log
-- Append-only audit trail of every sync attempt (success or failure).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.personio_sync_log (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id               text NOT NULL,            -- relocation_cases.id
  company_id            text,                     -- for easy filtering
  employee_email        text,                     -- email used for Personio lookup
  personio_employee_id  bigint,                   -- Personio numeric employee ID (null if lookup failed)
  direction             text NOT NULL DEFAULT 'relopass_to_personio'
                          CHECK (direction IN ('relopass_to_personio', 'personio_to_relopass')),
  -- Status values: success | skip | warn | error | retry
  sync_status           text NOT NULL,
  new_case_status       text,                     -- relocation_cases.status value that triggered the sync
  fields_updated        jsonb,                    -- fields actually written to Personio
  error_message         text,                     -- human-readable error if sync_status != 'success'
  personio_response     jsonb,                    -- raw Personio API response (truncated to 2KB)
  synced_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_personio_sync_log_case_id
  ON public.personio_sync_log (case_id, synced_at DESC);

CREATE INDEX IF NOT EXISTS idx_personio_sync_log_status
  ON public.personio_sync_log (sync_status, synced_at DESC);

-- RLS: HR users can read their own company's sync log. Inserts via service role only.
ALTER TABLE public.personio_sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "hr_can_read_own_sync_log"
  ON public.personio_sync_log FOR SELECT
  TO authenticated
  USING (
    company_id IN (
      SELECT company_id FROM public.hr_users
      WHERE user_id = (SELECT auth.uid())
    )
  );

-- ---------------------------------------------------------------------------
-- Enable pg_net extension (required for trigger → Edge Function HTTP calls)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT SELECT ON public.hris_connections TO authenticated;
GRANT SELECT ON public.personio_sync_log TO authenticated;
GRANT ALL ON public.hris_connections TO service_role;
GRANT ALL ON public.personio_sync_log TO service_role;
