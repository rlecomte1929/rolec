-- AIQ-1521 — supplier magic-link: let a supplier answer an RFQ WITHOUT an account.
--
-- WHY NOT AN ACCOUNT
-- ------------------
-- The existing supplier-facing write path (POST /api/vendor/rfqs/{id}/quotes) is guarded by
-- require_vendor, which resolves the caller through public.vendor_users. That table has NEVER
-- had a single INSERT. Suppliers will not create accounts to give us a price — so that route is
-- structurally unreachable and we do not reuse it.
--
-- WHY rfq_recipients IS THE INVITE LEDGER (no new table)
-- -----------------------------------------------------
-- One RFQ goes to N suppliers, and rfq_recipients ALREADY is exactly that row: one per supplier
-- per RFQ. It already carries the lifecycle we want —
--     CHECK (status IN ('sent','viewed','replied','declined'))
-- — which is precisely the funnel this risk spike measures: did they open it, did they quote.
-- So the invite lives on the recipient row rather than in a parallel supplier_invites table.
--
-- SECURITY — why the token hash is stored even though the JWT is self-sufficient
-- ----------------------------------------------------------------------------
-- The provider magic-link (provider_jwt.py) is a STATELESS JWT: verify never touches the DB, so
-- `revoked_at` is honoured only at redemption and a revoked token keeps working for its full
-- 7-day life. Submitting a quote is a FINANCIAL write, so we do not copy that. require_supplier_jwt
-- looks the recipient row up by sha256(token) on EVERY request and enforces:
--     revoked_at IS NULL, expires_at > now(), and single-submission.
-- The raw token is never stored.

BEGIN;

ALTER TABLE public.rfq_recipients
  ADD COLUMN IF NOT EXISTS token_hash        text,        -- sha256 of the magic-link token
  ADD COLUMN IF NOT EXISTS invited_email     text,        -- where the link was actually sent
  ADD COLUMN IF NOT EXISTS invited_at        timestamptz,
  ADD COLUMN IF NOT EXISTS expires_at        timestamptz,
  ADD COLUMN IF NOT EXISTS first_viewed_at   timestamptz, -- they opened the link  -> status 'viewed'
  ADD COLUMN IF NOT EXISTS quote_submitted_at timestamptz,-- they gave a price     -> status 'replied'
  ADD COLUMN IF NOT EXISTS revoked_at        timestamptz;

-- The token is the lookup key on every supplier request; it must be indexed and unique.
CREATE UNIQUE INDEX IF NOT EXISTS idx_rfq_recipients_token_hash
  ON public.rfq_recipients (token_hash)
  WHERE token_hash IS NOT NULL;

COMMENT ON COLUMN public.rfq_recipients.token_hash IS
  'AIQ-1521: sha256 of the supplier magic-link token. Looked up on EVERY supplier request so revocation and single-submission are actually enforced — unlike the stateless provider JWT, where revoked_at is only honoured at redemption.';
COMMENT ON COLUMN public.rfq_recipients.invited_email IS
  'AIQ-1521: the address the magic link was sent to. suppliers.contact_email is NULL for all 90 suppliers, so the address is supplied explicitly when the link is sent.';

COMMIT;
