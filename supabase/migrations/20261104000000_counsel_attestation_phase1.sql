-- Counsel Attestation, Phase 1 — additive only.
--
-- Lets a ReloPass admin ask an external legal firm to review a corridor's legal-compliance
-- checklist over a tokenized link, and stores the sign-off as durable, immutable proof.
--
-- Attestation is an ORTHOGONAL axis to verification_status, not a fifth value crammed into
-- it. `verification_status` stays the founder/corpus ladder (representative →
-- corpus_grounded → verified); `attestation_status` carries the counsel axis (none →
-- requested → attested → stale). That preserves the `verified` signal and makes staleness
-- representable. Sellable = verification_status='verified' AND attestation_status='attested'.
--
-- TWO DEVIATIONS FROM THE PHASE-1 SPEC, both forced by what is actually in the database.
-- Recorded here because the next reader will otherwise "fix" them back:
--
--   1. `corridor_attestation_items.requirement_item_id` is **varchar, not uuid**.
--      `requirement_items.id` is `character varying` (all 84 values happen to be
--      UUID-shaped, but the COLUMN is varchar). A uuid FK against it fails outright:
--        42804: foreign key constraint cannot be implemented
--        DETAIL: Key columns "requirement_item_id" and "id" are of incompatible types:
--                uuid and character varying.
--      Verified by running the spec's DDL in a rolled-back transaction, 2026-08-16.
--      Retyping requirement_items.id would be a type change on a populated table with
--      existing FKs — forbidden by the additive-only rule. So the FK matches the referent.
--
--   2. Each table gets an explicit **service_role policy + REVOKE anon**, where the spec
--      said "no policies at all". Same end state — anon and authenticated get nothing, all
--      access is mediated by the FastAPI backend — but a policy-LESS public table trips
--      CLAUDE.md's hard gate and scripts/check_rls_coverage.py, whose allowlist is drained
--      to 0 and treats 0 as its floor. Follows 20261028000000_ror_tables_rls.sql exactly.
--      service_role BYPASSES RLS, so the backend's access is unchanged either way.
--
-- guard: column-read-ok this migration is applied to production by the operator BEFORE the
-- PR is merged (psql -f + `supabase migration repair --status applied 20261104000000`).
-- The readers are additionally getattr/.get-defaulted and degrade to NULL rather than
-- raising. Do NOT merge the PR until the apply is confirmed.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1) The request / envelope: one per corridor attestation ask.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.corridor_attestation_requests (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  country_code           varchar NOT NULL,                 -- served corridor key, e.g. 'NORWAY'
  purpose                varchar NOT NULL DEFAULT 'employment',
  scope                  text    NOT NULL DEFAULT 'legal',
  title                  text,
  status                 text    NOT NULL DEFAULT 'draft', -- draft|sent|in_review|changes_requested|signed|revoked|superseded
  requested_by           text    NOT NULL,                 -- admin user id/email
  reviewer_org           text,
  reviewer_name          text,
  reviewer_email         text,
  reviewer_credential    text,                             -- bar / registration number
  -- SHA-256 of the raw token. The raw token is returned to the admin exactly once at
  -- creation and never stored, so a database leak does not yield working review links.
  link_token_hash        text,
  token_expires_at       timestamptz,
  content_snapshot_hash  text    NOT NULL,                 -- sha256 of the canonical checklist JSON
  content_snapshot_json  jsonb   NOT NULL,                 -- exact items+claims+sources sent for review
  disclaimer_version     text,
  sent_at                timestamptz,
  completed_at           timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2) One row per requirement item in the envelope; carries the reviewer's decision.
--    Snapshot columns are deliberate duplication: the reviewer signed what they were
--    SHOWN, so the evidence must survive the catalog row being edited afterwards.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.corridor_attestation_items (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id           uuid NOT NULL REFERENCES public.corridor_attestation_requests(id) ON DELETE CASCADE,
  -- varchar, not uuid — see deviation (1) in the header.
  requirement_item_id  varchar NOT NULL REFERENCES public.requirement_items(id),
  item_title           text NOT NULL,
  claim_snapshot       text,
  source_url_snapshot  text,
  evidence_snapshot    text,
  decision             text NOT NULL DEFAULT 'pending', -- pending|approved|amended|rejected
  reviewer_comment     text,
  proposed_amendment   text,
  decided_at           timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3) Immutable, append-only proof of sign-off.
--    Never UPDATE or DELETE a row here. Revocation or re-issue is a NEW row pointing at
--    the prior one via supersedes_signature_id — the chain IS the audit trail, and a
--    mutable signature is not evidence of anything.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.corridor_attestation_signatures (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id              uuid NOT NULL REFERENCES public.corridor_attestation_requests(id),
  signer_name             text NOT NULL,
  signer_email            text NOT NULL,
  signer_org              text,
  signer_credential       text,
  signature_method        text NOT NULL DEFAULT 'typed_name', -- typed_name|uploaded_pdf|esign(future)
  -- MUST equal the request's content_snapshot_hash at signing. If the checklist changed
  -- under the reviewer, the signature would attest to something they never saw.
  signed_content_hash     text NOT NULL,
  signed_payload_json     jsonb NOT NULL,   -- frozen copy of item decisions + claims + sources
  disclaimer_version      text NOT NULL,
  disclaimer_text         text NOT NULL,    -- frozen copy of the exact wording agreed to
  signed_ip               text,
  signed_user_agent       text,
  supersedes_signature_id uuid REFERENCES public.corridor_attestation_signatures(id),
  signed_at               timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4) The orthogonal attestation axis on the served table.
--    All nullable, no defaults that rewrite rows, no backfill → additive.
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.requirement_items ADD COLUMN IF NOT EXISTS attestation_status text;              -- null/none|requested|attested|stale
ALTER TABLE public.requirement_items ADD COLUMN IF NOT EXISTS attested_at timestamptz;
ALTER TABLE public.requirement_items ADD COLUMN IF NOT EXISTS attested_by text;                     -- firm/counsel label
ALTER TABLE public.requirement_items ADD COLUMN IF NOT EXISTS latest_attestation_request_id uuid;   -- soft link, deliberately no FK

COMMENT ON COLUMN public.requirement_items.attestation_status IS
  'Counsel axis, orthogonal to verification_status: NULL/none | requested | attested | stale. '
  'Only the admin /promote endpoint may write ''attested'' — never a machine, never the public token path.';

-- ─────────────────────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_car_country_purpose_status ON public.corridor_attestation_requests(country_code, purpose, status);
-- Partial + UNIQUE: the token hash is the lookup key on every public request, and two live
-- requests must never share one. NULL hashes (draft, not yet tokenized) are exempt.
CREATE UNIQUE INDEX IF NOT EXISTS idx_car_link_token_hash ON public.corridor_attestation_requests(link_token_hash) WHERE link_token_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cai_request ON public.corridor_attestation_items(request_id);
CREATE INDEX IF NOT EXISTS idx_cai_item ON public.corridor_attestation_items(requirement_item_id);
CREATE INDEX IF NOT EXISTS idx_cas_request ON public.corridor_attestation_signatures(request_id);
CREATE INDEX IF NOT EXISTS idx_ri_attestation_status ON public.requirement_items(attestation_status) WHERE attestation_status IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — deny by default. One explicit service_role policy per table, REVOKE anon.
-- Deliberately NO `authenticated` policy: there is no supabase-js .from('corridor_*')
-- path in the frontend, so a tenant-scoped policy would be dead code. The tokenized
-- reviewer never touches PostgREST — every read goes through FastAPI.
-- Replay-safe: DROP POLICY IF EXISTS before CREATE; REVOKE is a no-op when never granted.
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'corridor_attestation_requests',
    'corridor_attestation_items',
    'corridor_attestation_signatures'
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
