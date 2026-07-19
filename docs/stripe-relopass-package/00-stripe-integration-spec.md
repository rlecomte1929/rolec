# ReloPass Stripe Integration — Full Specification
Version 1.0 | 2026-07-18

## 1. Strategic Context

ReloPass Case Command charges €800 per relocation case (M1 Roadmap + Verified Vendor Shortlist).
The buyer is an HR generalist at an SME. The payment is expensable as a professional service — below most managers' expense authority, no procurement queue.

The gate design is honest: the teaser shows real non-obvious requirements the buyer didn't know existed. The rest is locked. The conversion is driven by genuine value, not manufactured scarcity.

## 2. Pricing Architecture

| Tier | Label | Price | Type | Build status |
|------|-------|-------|------|-------------|
| 0 | Free teaser | €0 | Always shown | Build now |
| 1 | M1 Roadmap + Vendor Shortlist | €800 | One-time, per case | Build now |
| 2 | Essentials (immigration assurance) | €2,000 | One-time, per case | Stub — gated on lawyer sign-off |
| 3 | Starter retainer | €2,500/yr | Annual subscription | Stub |
| 4 | Growth retainer | €5,000/yr | Annual subscription | Stub |

Add-ons (v1+): vendor category unlocks (movers, immigration lawyers, tax advisors, schools, pets) — scaffolded in DB, no UI yet.

## 3. Gate Flow

1. HR generalist opens Case Command → clicks "New case"
2. Enters: employee type (EEA / non-EEA) + target move date
3. Submits → case record created in DB (access_tier: 'free')
4. Teaser renders:
   - Total requirement count + non-obvious count
   - Feasibility badge (clear / amber / red)
   - 2–3 specific non-obvious requirement names (D-number, skattekort, police registration)
   - Locked row: "+N more requirements"
5. Primary CTA: "Unlock full roadmap + vendor list — €800" → POST /checkout → redirect to Stripe
6. Payment completes → Stripe fires checkout.session.completed webhook
7. Webhook writes access_tier: 'roadmap' to case row (server-side only — never trust client)
8. User redirected to ?payment=success → UI refetches access → full roadmap renders
9. Confirmation email sent with receipt link (expensable)

## 4. Database Schema

### relocation_cases (additions)
- payment_status: TEXT DEFAULT 'unpaid' CHECK IN ('unpaid','roadmap_paid','essentials_paid')
- access_tier: TEXT DEFAULT 'free' CHECK IN ('free','roadmap','essentials')
- stripe_payment_intent_id: TEXT
- stripe_session_id: TEXT (written on checkout creation — used to match webhook to case)
- paid_at: TIMESTAMPTZ
- paid_amount_cents: INTEGER
- paid_currency: TEXT DEFAULT 'eur'

### case_addons (new table — stub)
- id: UUID PK
- case_id: UUID FK → relocation_cases
- addon_type: TEXT CHECK IN ('vendor_movers','vendor_immigration','vendor_tax','vendor_schools','vendor_pets')
- payment_status: TEXT DEFAULT 'unpaid'
- stripe_session_id, stripe_payment_intent_id, paid_at, paid_amount_cents, paid_currency
- created_at: TIMESTAMPTZ

## 5. API Endpoints

### POST /api/relopass/cases/:caseId/checkout
- Auth: authenticateDeviceTokenOrJWT
- Body: { tier: 'roadmap' | 'essentials' }
- Creates Stripe Checkout session
- Stripe session params:
  - mode: 'payment'
  - line_items: [{ price: STRIPE_PRICE_ROADMAP_EUR, quantity: 1 }]
  - success_url: APP_URL/case-command/cases/:caseId?payment=success
  - cancel_url: APP_URL/case-command/cases/:caseId?payment=cancelled
  - metadata: { workspaceId, caseId, tier, source: 'relopass_case_command' }
  - billing_address_collection: 'required'
  - custom_fields: company_name (optional), vat_number (optional)
  - invoice_creation: { enabled: true }
  - currency: 'eur'
  - expires_at: now + 30 minutes
- Saves session.id → relocation_cases.stripe_session_id
- Returns: { checkoutUrl, sessionId }

### GET /api/relopass/cases/:caseId/access
- Auth: authenticateDeviceTokenOrJWT
- Returns: { caseId, accessTier, paymentStatus, accountTier, availableAddons }
- accountTier: read from contacts.metadata.planTier for logged-in user

## 6. Webhook Extension

In misc.routes.ts checkout webhook handling, extend the existing
`checkout.session.completed` switch case:

1. Read `session.metadata.source`. If it is not `'relopass_case_command'`,
   fall through to the existing handling — this extension must not disturb
   other products sharing the webhook.
2. If it matches, extract `caseId` and `tier` from `session.metadata`.
3. Update the case row **conditionally**:

```sql
UPDATE relocation_cases
SET access_tier            = $1,   -- 'roadmap' | 'essentials' (from metadata.tier)
    payment_status         = $2,   -- 'roadmap_paid' | 'essentials_paid'
    stripe_payment_intent_id = $3,
    paid_at                = NOW(),
    paid_amount_cents      = $4,   -- session.amount_total
    paid_currency          = $5    -- session.currency
WHERE id = $6                      -- metadata.caseId
  AND stripe_session_id = $7      -- session.id — must match what /checkout stored
  AND payment_status = 'unpaid';  -- idempotency: replayed events are no-ops
```

4. If the UPDATE affected 0 rows, the event is a replay (or the session does
   not belong to that case) — acknowledge with 200 and do nothing else.
5. If the UPDATE affected 1 row, send the confirmation email
   (see section 8) — the `payment_status = 'unpaid'` guard above doubles as
   the email idempotency guard: replays can never re-send it.
6. Always return 200 to Stripe once the event has been durably handled;
   return 5xx only on transient failures you want Stripe to retry.

**CRITICAL:** `access_tier` is ONLY ever written by this webhook — never from
the client, never from the /checkout endpoint. A forged "payment succeeded"
call from the browser cannot unlock a case.

Reference implementation: `03-backend/webhook-extension.ts`.

## 7. Frontend Components

### hooks/useCaseAccess.ts

- Calls `GET /api/relopass/cases/:caseId/access` on mount (and whenever
  `caseId` changes).
- Detects `?payment=success` in the URL: refetches after 1.5 s (webhook lag),
  then strips the param from the URL with `history.replaceState`.
- Exposes `{ access, loading, error, refetch, hasFullAccess }` where
  `hasFullAccess` is true when `accessTier !== 'free'` OR the account tier is
  a retainer (`starter` / `growth`).
- Never writes access state — read-only mirror of the server.

### CaseGate.tsx

- Renders `children` (the full roadmap) untouched when `hasFullAccess`.
- When `accessTier === 'free'`:
  - Teaser card: total requirement count, non-obvious count, feasibility badge.
  - 2–3 real non-obvious requirement previews, verbatim (D-number,
    skattekort timing, police registration).
  - Blurred remainder with a "+N more requirements locked" pill.
  - Primary CTA "Unlock full roadmap + vendor list — €800": calls
    `POST /checkout`, then redirects to `checkoutUrl`. In an iframe, redirect
    `window.top` (fall back to `window.location` on cross-origin errors).
  - Secondary CTA "Essentials — €2,000" rendered greyed out and disabled
    (stub — pending lawyer sign-off).
- Never flips access client-side: after the Stripe redirect it simply
  re-reads the server state (via useCaseAccess) until it reports paid.

### case-command-App-updated.tsx

- Wires the gate into Case Command: after the case is created (employee type
  + move date submitted), the results panel renders inside
  `<CaseGate caseId={...}>…full roadmap…</CaseGate>`.
- The teaser data (counts, preview items, feasibility) comes from the same
  rule-engine output as the full roadmap — the gate only controls how much
  of it is visible.

Reference implementations: `04-frontend/hooks/useCaseAccess.ts`,
`04-frontend/CaseGate.tsx`, `04-frontend/case-command-App-updated.tsx`.

## 8. Confirmation Email

Sent by the webhook handler (section 6) after the first — and only the
first — transition to a paid status.

| Field | Value |
|---|---|
| To | Checkout customer email (`session.customer_details.email`) |
| Subject | `ReloPass — Your roadmap is unlocked (receipt enclosed)` |
| Trigger | The row's first transition to `payment_status = 'roadmap_paid'` |

Body contents:
- Confirmation that the full roadmap + vendor shortlist for the case is
  unlocked (corridor + case reference).
- Direct link back to the case (`APP_URL/case-command/cases/:caseId`).
- Receipt block: amount, case reference, company name + VAT number (from the
  checkout custom fields), and the Stripe hosted invoice link
  (`invoice.hosted_invoice_url` — available because the checkout session is
  created with `invoice_creation: { enabled: true }`).
- Note that the receipt is expensable as a professional service and that
  Stripe sends its own payment confirmation separately.

Idempotency: guaranteed by the conditional UPDATE in section 6 — the email
fires only when the row actually transitioned, so webhook replays cannot
double-send.

Reference implementation: `05-email/case-payment-confirmation.ts`.

## 9. Environment Variables

See `06-env/.env.example`. Required:

| Var | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Server-side Stripe API key (`sk_test_…` then `sk_live_…`) |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for the webhook endpoint (`whsec_…`) |
| `STRIPE_PRICE_ROADMAP_EUR` | Price ID for the €800 roadmap unlock |
| `STRIPE_PRICE_ESSENTIALS_EUR` | Price ID for the €2,000 Essentials tier (stub — create the product, do not wire the CTA) |
| `APP_URL` | Public origin used to build success/cancel URLs |

Create the products in the Stripe Dashboard in **test mode** first; switch
the two price IDs to their live-mode equivalents only at go-live (step 12 of
the build sequence).

## 10. Test Plan (Stripe test mode)

1. Create a case → teaser renders, roadmap blurred, CTA shows €800.
2. Click CTA → redirected to Stripe Checkout; company name + VAT number
   custom fields present; session expires after 30 minutes.
3. Pay with `4242 4242 4242 4242` (any future expiry, any CVC).
4. Redirect lands on `?payment=success` → within ~2 s the full roadmap
   renders (webhook + refetch).
5. Reload the page → case still unlocked (access is server-side, per case).
6. Confirmation email received exactly once, with hosted invoice link.
7. Replay the webhook event from the Stripe Dashboard → no state change, no
   second email.
8. Call `POST /checkout` for the already-paid case → 400 "already unlocked".
9. Attempt to unlock by calling the access endpoint with a forged body →
   access unchanged (endpoint is read-only).

---

> Provenance note (2026-07-19): the source instruction that delivered this
> specification was truncated mid-way through section 6 ("In misc.routes.ts
> checkout…"). Sections 6–10 above were reconstructed from the surviving
> package materials (the v1.0 package README build sequence, the pre-build
> spec copy in the ReloPass workspace, and the as-built reference
> implementations) so the package is complete and internally consistent.
