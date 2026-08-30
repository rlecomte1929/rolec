-- [AIQ-2094 ST1] hr_company_invites — the admin-gated route for a second HR user
-- into an EXISTING company workspace. Additive only: one new table, no ALTERs.
--
-- WHY THIS EXISTS
--
-- AIQ-2090 (PR #1989) removed the previous route into an existing workspace. Public
-- signup called find_or_create_company_by_name, a LOWER(TRIM(name)) match, so typing a
-- customer's company name on an unauthenticated form linked the new account into their
-- tenant — their cases, their employees, their policies. Signup now always creates its
-- own company (create_company_for_self_serve_signup, backend/db/companies.py:400).
--
-- Safe, but a colleague of an existing HR user now lands in a SEPARATE workspace. This
-- table carries the replacement: an invite an HR user raises for their own company, that
-- a ReloPass admin must approve before it grants anything. Decided 2026-08-30 — no
-- automatic domain matching, every colleague passes an admin review.
--
-- Trust order, enforced by `status`:
--     HR raises (pending_admin) -> admin approves (approved) -> colleague accepts (accepted)
-- The accept path (ST4) honours 'approved' and nothing else, so the gate is not bypassable.
--
-- TYPE CHOICES, forced by what is actually in the database (measured 2026-08-30):
--
--   1. company_id is **uuid** with a real FK to companies(id), which is uuid NOT NULL.
--      Note hr_users.company_id is *text* — that table is text-keyed on all three of
--      id/company_id/profile_id. The drift is real and pre-existing. This table follows
--      the REFERENT (companies.id), because a dangling company_id on a tenant-boundary
--      table is exactly the failure that must not be representable. ST4 casts to text at
--      the hr_users boundary, which is what the surrounding code already does.
--
--   2. invited_by_profile_id / accepted_profile_id are **uuid** FKs to profiles(id),
--      which is uuid. approved_by_admin_id is plain text: admin identity is an
--      allowlist/email concept here, not a profiles FK.
--
-- NO application code reads this table in this PR. The reader lands in ST2 only after an
-- operator has applied this migration and reconciled the ledger — merging does not apply.

CREATE TABLE IF NOT EXISTS public.hr_company_invites (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- The tenant this invite lets someone into. Derived server-side from the inviting HR
  -- user's own profile, never from a request body. FK so it cannot dangle.
  company_id             uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,

  invited_email          text NOT NULL,
  invited_by_profile_id  uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,

  -- pending_admin -> approved -> accepted, or -> rejected / expired / revoked.
  -- ST4 accepts ONLY 'approved'. Any other value is a refusal, never a silent no-op.
  status                 text NOT NULL DEFAULT 'pending_admin'
                           CONSTRAINT hr_company_invites_status_check
                           CHECK (status IN ('pending_admin','approved','rejected',
                                             'accepted','expired','revoked')),

  -- SHA-256 of the raw accept token. The raw token is emailed once and never stored, so
  -- a database leak does not yield working invite links. Same convention as
  -- corridor_attestation_requests.link_token_hash (20261104000000).
  -- NULL until an admin approves — an unapproved invite has no token at all.
  token_hash             text,
  expires_at             timestamptz,

  approved_by_admin_id   text,
  approved_at            timestamptz,
  rejected_reason        text,
  accepted_at            timestamptz,
  accepted_profile_id    uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  revoked_at             timestamptz,

  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

-- The admin review queue: every pending invite across all companies, newest first.
CREATE INDEX IF NOT EXISTS idx_hr_company_invites_status_created
  ON public.hr_company_invites (status, created_at DESC);

-- An HR user listing their own company's invites.
CREATE INDEX IF NOT EXISTS idx_hr_company_invites_company
  ON public.hr_company_invites (company_id, created_at DESC);

-- ST4's accept lookup is by token_hash alone. Partial: only approved invites are
-- addressable by token, so a stale hash from a rejected/revoked row is not even a
-- candidate row.
CREATE INDEX IF NOT EXISTS idx_hr_company_invites_token_hash
  ON public.hr_company_invites (token_hash)
  WHERE token_hash IS NOT NULL;

-- At most ONE live invite per (company, email). Partial unique so that a rejected or
-- expired invite does not block re-inviting the same colleague later. This is the
-- database-level half of ST2's duplicate-pending rejection.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hr_company_invites_live_per_email
  ON public.hr_company_invites (company_id, LOWER(invited_email))
  WHERE status IN ('pending_admin','approved');

COMMENT ON TABLE public.hr_company_invites IS
  '[AIQ-2094] Admin-gated invites letting a second HR user join an existing company '
  'workspace. HR raises (pending_admin), a ReloPass admin approves, the colleague then '
  'accepts. Replaces the typed-company-name join removed by AIQ-2090. No domain matching.';

COMMENT ON COLUMN public.hr_company_invites.company_id IS
  'The tenant granted. Derived from the inviting HR user''s own profile server-side — '
  'NEVER from a request body. A body-supplied company_id is the AIQ-2090 bug.';

COMMENT ON COLUMN public.hr_company_invites.token_hash IS
  'SHA-256 of the accept token; the raw token is emailed once and never stored. NULL '
  'until an admin approves.';

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — deny by default. One explicit service_role policy, REVOKE anon + authenticated.
-- Deliberately NO `authenticated` policy: there is no supabase-js .from('hr_company_invites')
-- path in the frontend — every read and write goes through FastAPI — so a tenant-scoped
-- policy would be dead code. service_role BYPASSES RLS, so the backend is unaffected.
-- A policy-LESS public table trips CLAUDE.md's hard gate and scripts/check_rls_coverage.py.
-- Follows 20261104000000_counsel_attestation_phase1.sql exactly.
-- Replay-safe: DROP POLICY IF EXISTS before CREATE; REVOKE is a no-op when never granted.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'hr_company_invites'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF to_regclass('public.' || t) IS NULL THEN
      RAISE NOTICE 'skipping missing table public.%', t;
      CONTINUE;
    END IF;

    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);

    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I;', t || '_service_role_all', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true);',
      t || '_service_role_all', t
    );

    EXECUTE format('REVOKE ALL ON public.%I FROM anon;', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM authenticated;', t);
  END LOOP;
END $$;
