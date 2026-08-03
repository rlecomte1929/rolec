-- Multi-referral capture on the test-drive survey.
--
-- The survey used to take exactly ONE referral, so a tester who knew three people gave one.
-- `referrals` holds the full list: [{name, company_role, contact, consent}, ...].
--
-- Backward-compatible by design — the legacy scalar columns (referral_name /
-- referral_company_role / referral_contact / referral_consent) are KEPT and the API keeps
-- mirroring referrals[0] into them, because two live readers still depend on them:
--   * the admin panel's "intro" count (admin_test_drive.py → referral_name IS NOT NULL), and
--   * a scheduled Cowork alert that reads referral_name/contact/consent to surface warm leads.
-- Do not drop or rename them.
--
-- Additive column only. survey_responses already has admin-read RLS + `REVOKE ALL … FROM anon`
-- (from TD-1, 20260830000000); RLS is table-level, so the new column inherits that coverage —
-- this is NOT a new-table gate and needs no new policy. The array's shape is validated in the
-- API layer, so no DB CHECK is added here.
ALTER TABLE public.survey_responses
    ADD COLUMN IF NOT EXISTS referrals jsonb DEFAULT '[]'::jsonb;
