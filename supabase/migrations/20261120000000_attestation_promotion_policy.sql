-- ============================================================
-- corridor_attestation_requests: how an attestation gets published, and whether it
-- may advance review_status
-- ============================================================
--
-- WHAT THIS IS FOR. Today publishing an attestation is always a second, manual admin act:
-- counsel signs (`POST /api/public/attestations/{token}/sign`, which writes ONLY a
-- signature row), and an admin separately calls `POST /api/admin/attestations/{id}/promote`
-- — the only path in the codebase that writes `requirement_items.attestation_status =
-- 'attested'`. That is the two-key rule, and it is deliberate.
--
-- Some envelopes will not want a second key. A corridor whose whole point is "counsel
-- signs, it goes live" should be able to say so AT CREATION TIME, on the record, rather
-- than by an admin remembering to click promote. These two columns record that intent:
--
--   promotion_policy        'manual'       — today's behaviour: signing publishes nothing.
--                           'auto_on_sign' — signing also runs the promotion.
--   advance_review_status   false          — today's behaviour: promotion touches only the
--                                            attestation columns.
--                           true           — the promotion may also advance the item's
--                                            review_status.
--
-- WHAT THIS MIGRATION DOES NOT DO — read this before reviewing the defaults. **Nothing
-- reads either column yet.** No code path in `backend/` references `promotion_policy` or
-- `advance_review_status` as of this migration; they are wired up in ATT-2.2 (accepted on
-- create) and ATT-2.4 (honoured on sign). This file is purely additive so that the schema
-- change and the behaviour change land in separate, separately-reviewable PRs — the
-- behaviour change is the one that can publish legal content to a mover, and it deserves
-- its own review rather than riding in on a migration.
--
-- WHY THE DEFAULTS ARE THE CONSERVATIVE ONES. `'manual'` and `false` reproduce exactly what
-- every existing row does today, so backfilling is a no-op and an un-migrated reader sees
-- no change. A default of `'auto_on_sign'` would silently convert every existing request
-- into a self-publishing one the moment ATT-2.4 lands — which is the failure mode this
-- whole feature exists to prevent.
--
-- WHY A CHECK CONSTRAINT RATHER THAN AN ENUM. `corridor_attestation_requests.status` and
-- `.scope` are both plain `text` with the vocabulary enforced in the application, and a
-- Postgres enum needs its own migration to gain a value. A CHECK is the same guarantee at
-- the boundary that matters — a typo'd policy cannot be written — without that ceremony,
-- and it matches the table's existing style.
--
-- NO NEW TABLE, so CLAUDE.md's three gates (ENABLE RLS + policy + REVOKE anon) do not
-- apply — this is an ALTER on an existing table whose RLS posture is unchanged
-- (`corridor_attestation_requests` already has RLS enabled and a policy). Stated
-- explicitly so a reviewer applying that gate does not go looking.
--
-- ORDERING. Stamped above BOTH the repo max (20261119000000) and the production ledger max
-- (20261116000000), per CLAUDE.md "Choosing a migration timestamp". Note 20261117000000
-- through 20261119000000 are committed but NOT yet applied; this migration depends on none
-- of them and may be applied before or after.
--
-- IDEMPOTENT. `ADD COLUMN IF NOT EXISTS`, and the constraint is added only when absent
-- (`ADD CONSTRAINT` has no `IF NOT EXISTS` form for CHECK, hence the guard).
--
-- PROBE (run after applying; expect every existing row manual/false, and 0 violations):
--   SELECT promotion_policy, advance_review_status, count(*)
--     FROM public.corridor_attestation_requests
--    GROUP BY 1, 2;
--
-- ROLLBACK (down):
--   ALTER TABLE public.corridor_attestation_requests
--     DROP CONSTRAINT IF EXISTS ck_cap_promotion_policy;
--   ALTER TABLE public.corridor_attestation_requests
--     DROP COLUMN IF EXISTS promotion_policy,
--     DROP COLUMN IF EXISTS advance_review_status;
-- ============================================================

ALTER TABLE public.corridor_attestation_requests
  ADD COLUMN IF NOT EXISTS promotion_policy text NOT NULL DEFAULT 'manual';

ALTER TABLE public.corridor_attestation_requests
  ADD COLUMN IF NOT EXISTS advance_review_status boolean NOT NULL DEFAULT false;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'public.corridor_attestation_requests'::regclass
       AND conname  = 'ck_cap_promotion_policy'
  ) THEN
    ALTER TABLE public.corridor_attestation_requests
      ADD CONSTRAINT ck_cap_promotion_policy
      CHECK (promotion_policy IN ('manual', 'auto_on_sign'));
  END IF;
END $$;

COMMENT ON COLUMN public.corridor_attestation_requests.promotion_policy IS
  'How this attestation reaches requirement_items. ''manual'' (default) preserves the '
  'two-key rule: signing writes a signature only, and an admin must call /promote. '
  '''auto_on_sign'' lets the signature itself trigger promotion. Read by ATT-2.4; no code '
  'reads it as of this migration.';

COMMENT ON COLUMN public.corridor_attestation_requests.advance_review_status IS
  'Whether promoting this attestation may also advance requirement_items.review_status. '
  'false (default) means promotion touches only the attestation columns, which is what '
  'promote_attestation does today. Read by ATT-2.4; no code reads it as of this migration.';
