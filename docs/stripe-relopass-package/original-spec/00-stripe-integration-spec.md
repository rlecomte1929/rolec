# ReloPass Stripe Integration — Full Specification
**Version:** 1.0 | **Date:** 2026-07-18

## 1. Business Context

**Product:** ReloPass Case Command — France → Norway corridor
**Pricing model:** Per-case, one-time payment
**V0 price:** €800 — M1 Roadmap + Verified Vendor Shortlist
**Pricing anchor:** Comparable to 2 hours of a human specialist at €200/hr. The buyer's current cost is ~€3,000/case (40hr HR time × €50 + 5hr specialist × €200) with gaps remaining. €800 is cheaper and more complete.
**Expensable by design:** €800 sits below most SME managers' expense authority. Collect company name + VAT number at checkout so it's trivially fileable as a business expense.

## 2. Tier Architecture

| Tier | Price | Type | Gate | Status |
|------|-------|------|------|--------|
| 0 — Free teaser | €0 | Always shown | None | Live |
| 1 — M1 Roadmap + Vendor List | €800 | One-time per case | Stripe Checkout | Build now |
| 2 — Essentials (immigration assurance) | €2,000 | One-time per case | Requires lawyer sign-off | Stub only |
| 3 — Starter retainer | €2,500/yr | Annual subscription | After 3+ cases | Stub only |
| 4 — Growth retainer | €5,000/yr | Annual subscription | After 3+ cases | Stub only |

## 3. Add-On Architecture (V1+ — do not build yet)

After 5 real cases, usage data will show which vendor categories buyers actually use.
Add-ons are per-case upgrades above the base €800 unlock.

| Add-on | Type |
|--------|------|
| vendor_movers | International moving companies |
| vendor_immigration | Immigration lawyers |
| vendor_tax | Cross-border tax advisors |
| vendor_schools | International schools (Oslo area) |
| vendor_pets | Pet relocation specialists |

The `case_addons` table is scaffolded in the DB. No UI, no endpoints until V1.

## 4. Gate Logic

**Where the gate fires:** After the user submits employee type + move date and a case is created. Before the full roadmap renders.

**What the teaser shows (always free):**
- Total requirement count
- Non-obvious item count
- Feasibility badge (clear / amber / red)
- 2–3 specific non-obvious requirement names (D-number, skattekort, police registration)
- "+N more requirements locked" row

**What unlocks at €800:**
- All requirements in chronological order
- Feasibility flags on every item
- Responsible-party tagging (HR / employee / both)
- Verified vendor shortlist (5 per category)

## 5. Database Schema Changes

### relocation_cases additions
- `payment_status`: TEXT, enum('unpaid','roadmap_paid','essentials_paid'), default 'unpaid'
- `access_tier`: TEXT, enum('free','roadmap','essentials'), default 'free'
- `stripe_payment_intent_id`: TEXT, nullable
- `stripe_session_id`: TEXT, nullable (stored on checkout creation for webhook matching)
- `paid_at`: TIMESTAMPTZ, nullable
- `paid_amount_cents`: INTEGER, nullable
- `paid_currency`: TEXT, default 'eur'

### case_addons (new table — stub)
- `id`: UUID PK
- `case_id`: UUID FK → relocation_cases
- `addon_type`: TEXT, enum of 5 vendor types
- `payment_status`: TEXT, enum('unpaid','paid')
- Stripe session/intent fields, paid_at, amounts

## 6. API Endpoints

### POST /api/relopass/cases/:caseId/checkout
Creates a Stripe Checkout session for a given case and tier.
- Auth: required (device token or JWT)
- Body: `{ tier: 'roadmap' | 'essentials' }`
- Validates: case exists, not already at tier
- Creates Stripe session with: custom fields (company_name, vat_number), invoice_creation enabled, 30-min expiry
- Saves session.id to relocation_cases.stripe_session_id
- Returns: `{ checkoutUrl, sessionId }`

### GET /api/relopass/cases/:caseId/access
Returns current access state for a case.
- Auth: required
- Returns: `{ caseId, accessTier, paymentStatus, accountTier, availableAddons }`

## 7. Webhook Extension

Extend existing `checkout.session.completed` switch in misc.routes.ts.
Handler checks `session.metadata.source === 'relopass_case_command'`.
If true: updates relocation_cases (access_tier, payment_status, paid_at, paid_amount_cents) WHERE id = caseId AND stripe_session_id = session.id.
CRITICAL: access_tier is ONLY ever written by this webhook — never from the client.
After DB update: send confirmation email (idempotency-guarded).

## 8. Frontend Components

### useCaseAccess.ts (hook)
- Calls GET /api/relopass/cases/:caseId/access on mount
- Detects ?payment=success: refetches after 1.5s, strips param from URL
- Returns hasFullAccess (true when accessTier !== 'free' OR accountTier is starter/growth)

### CaseGate.tsx (component)
- Only renders when accessTier === 'free'
- Teaser card + preview rows + primary CTA (€800) + secondary CTA (€2,000, greyed out, disabled)
- Primary CTA calls /checkout, redirects to checkoutUrl
- Handles iframe case (window.top redirect)

## 9. Confirmation Email

> [Editorial note — not part of the original text: the source instruction that supplied this document was truncated at the "9. Confirmation Email" heading, so the body of section 9 was never transmitted. The as-built confirmation-email contract is documented in `../05-email/receipt-email.md`.]
