-- F3 hardening: make the relopass_api RLS second-barrier robust to a malformed
-- company GUC.
--
-- The retriever (policy_chunk_retriever.py) runs as the non-superuser relopass_api
-- role and sets app.current_company_id from the authenticated user's resolved
-- company. The policy pac_select_relopass_api cast that GUC straight to uuid:
--     company_id = (NULLIF(current_setting('app.current_company_id', true), ''))::uuid
-- A user whose resolved company_id is a non-UUID legacy slug (e.g. the demo HR
-- account "seed-emp-testingapril") made that cast raise
-- invalid_text_representation -> 500, instead of simply matching no rows. (The
-- superuser fallback bypasses RLS so the cast never ran, masking this.)
--
-- Fix: route the GUC through a safe_uuid() helper that catches the cast failure
-- and returns NULL, so a malformed company GUC yields 0 rows, never an error.
-- Tenant scoping for real UUID companies is unchanged.

CREATE OR REPLACE FUNCTION public.safe_uuid(t text) RETURNS uuid
  LANGUAGE plpgsql IMMUTABLE AS $$
  BEGIN
    RETURN t::uuid;
  EXCEPTION WHEN others THEN
    RETURN NULL;
  END
$$;

GRANT EXECUTE ON FUNCTION public.safe_uuid(text) TO relopass_api;

ALTER POLICY pac_select_relopass_api ON public.policy_assistant_chunks
  USING (company_id = public.safe_uuid(current_setting('app.current_company_id', true)));
