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

In misc.routes.ts checkout

> **NOTE (truncated source):** The source instruction for this spec was cut off at this point.
> Section 6 (webhook extension details) and any later sections/files were not received and
> still need to be supplied and committed.
