# ReloPass Stripe Integration — Continuation Sections 7–12 (AS RECEIVED, incomplete)

> Editorial note — read before using this document:
>
> 1. **Origin.** On 2026-07-19 Otto handed off an instruction titled "Push ReloPass
>    Stripe Spec — Missing Sections 7–12 to GitHub", asking that the content below be
>    appended to `docs/stripe-relopass-package/00-stripe-integration-spec.md` in the
>    GitHub repo `rlecomte1929/rolec` on branch `fix/td-qa-services-batch-0719`.
>    That push could NOT be performed: this workspace agent has no GitHub credentials
>    or repository checkout, and the repo is not publicly reachable (GitHub API
>    returns 404 — private or nonexistent). The content is preserved here verbatim so
>    it is not lost.
> 2. **Truncated AGAIN.** The instruction promised Sections 7–12, but the transmission
>    cut off mid-sentence in Section 10 (testing step 14: "Verify: 'Payment confirmed'
>    toast appears for"). The remainder of Section 10 and ALL of Sections 11 and 12
>    were never received. This is the second truncation of this spec (the first cut
>    off at the old "9. Confirmation Email" heading — see
>    `00-stripe-integration-spec.md` in this folder).
> 3. **Numbering conflict.** The sibling file `00-stripe-integration-spec.md`
>    (sections 1–6 + brief 7–9 as previously received) numbers its sections
>    differently: its §7 is "Webhook Extension", §8 "Frontend Components",
>    §9 "Confirmation Email". The continuation below uses §7 "Email Confirmation
>    System", §8 "Environment Variables", etc. Reconcile numbering when the full
>    source document is finally obtained.
> 4. **Platform mismatch.** Like the original spec, this content describes a
>    Node/Postgres/.env architecture that does NOT match the Audos as-built
>    implementation (see `../00-stripe-integration-spec.md`, the as-built record).
>    Env vars such as `STRIPE_PRICE_ROADMAP_EUR` and files such as
>    `server/routes/api/case-payment-email.ts` do not exist on this platform.
>
> Everything below this line is the received content, verbatim.

---

## Section 7 — Email Confirmation System

### Purpose
After Stripe's `checkout.session.completed` webhook fires and the case is unlocked, send a transactional email to the buyer confirming access and providing their receipt.

### Trigger
Called from `webhook-extension.ts` → `handleReloPassCasePayment()` after the DB update succeeds. Use the existing idempotency mechanism (`claimSideEffect`) to guard against duplicate sends.

### Recipient
`session.customer_details?.email ?? session.customer_email` — whichever is present.

### Subject line
- Roadmap tier: `Your ReloPass roadmap is unlocked — France → Norway`
- Essentials tier: `Your ReloPass Essentials case is unlocked — France → Norway`

### Email content (both tiers)
1. **Header:** "Your roadmap is unlocked." on dark background
2. **Intro paragraph:** Confirms France → Norway case is ready, full access active
3. **What's unlocked list (5 items):**
   - All requirements in chronological order, anchored to move date
   - Feasibility flags — tight windows and missed deadlines highlighted
   - Non-obvious requirements surfaced inline (D-number, skattekort, police registration)
   - Verified vendor shortlist: movers, immigration lawyers, tax advisors, schools
   - Responsible-party tagging on every item (HR / employee / both)
4. **CTA button:** "Open your case →" linking to `${APP_URL}/case-command/cases/${caseId}`
5. **Billing table:** Product name, amount paid, receipt PDF link (`session.invoice.hosted_invoice_url`)
6. **Footer note:** "This receipt is suitable for expense claims. Company name and VAT number (if provided) appear on the PDF receipt."

### File location
`server/routes/api/case-payment-email.ts` (create if not present)
Export: `sendCasePaymentConfirmationEmail(opts: CasePaymentConfirmationOptions)`

### sendEmail service
Use the workspace's existing `sendEmail` service (import path: `../../services/email`). Do not add a new email library.

---

## Section 8 — Environment Variables

### Required before any testing
All variables below must be present in `.env` before running the integration in test mode. They must NEVER be committed to git.

```
# ReloPass Stripe — one-time payment price IDs
STRIPE_PRICE_ROADMAP_EUR=price_xxx        # €800 — M1 Roadmap + Vendor Shortlist
STRIPE_PRICE_ESSENTIALS_EUR=price_xxx     # €2,000 — Essentials (stub — greyed out in UI)

# Subscription price IDs (stubs — create after 3+ completed cases)
STRIPE_PRICE_STARTER_EUR_YEAR=price_xxx   # €2,500/yr
STRIPE_PRICE_GROWTH_EUR_YEAR=price_xxx    # €5,000/yr

# App URL for Stripe redirect success/cancel URLs
APP_URL=https://relopass.com              # use Audos preview URL in local dev

# Add-on price IDs (v1+ only — do not create until after 5 real cases)
# STRIPE_PRICE_ADDON_MOVERS_EUR=price_xxx
# STRIPE_PRICE_ADDON_IMMIGRATION_EUR=price_xxx
# STRIPE_PRICE_ADDON_TAX_EUR=price_xxx
# STRIPE_PRICE_ADDON_SCHOOLS_EUR=price_xxx
# STRIPE_PRICE_ADDON_PETS_EUR=price_xxx
```

### Platform-managed variables (do NOT duplicate)
The Audos platform already manages `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SIGNING_SECRET`, and `STRIPE_TEST_SECRET_KEY` at the workspace level via `stripeForWorkspace(workspaceId)`. Do not add these to `.env` yourself — adding them a second time can cause key conflicts.

### Where to add new price IDs
Stripe Dashboard (test mode first) → Products → Create product → Add price. Copy the `price_xxx` ID into `.env`. Do not hardcode price IDs in source files — always read from `process.env`.

---

## Section 9 — Stripe Dashboard Setup

### Step-by-step (test mode)
1. Log in to Stripe Dashboard → toggle to **Test mode**
2. Go to **Products** → **+ Add product**
3. Create product: **"ReloPass M1 Roadmap + Vendor Shortlist"**
   - Price: €800.00 EUR, one-time
   - Copy the generated `price_xxx` ID → set as `STRIPE_PRICE_ROADMAP_EUR`
4. Create product: **"ReloPass Essentials — Immigration Assurance"** (stub)
   - Price: €2,000.00 EUR, one-time
   - Copy ID → set as `STRIPE_PRICE_ESSENTIALS_EUR`
   - Note: this price is UI-disabled until lawyer sign-off is complete; creating it now means the env var is set
5. Go to **Developers → Webhooks → Add endpoint**
   - URL: `https://[your-domain]/stripe/webhooks/connect`
   - Events to listen for:
     - `checkout.session.completed`
     - `checkout.session.expired`
     - `invoice.paid`
     - `customer.subscription.deleted`
   - Copy the signing secret → this is already managed by the platform; confirm with the platform team before creating a second webhook endpoint

### Invoice settings (for expensable receipts)
Stripe Dashboard → Settings → Customer portal → Invoice template:
- Add your company name and address
- Enable VAT collection if applicable
- Enable "Send invoice to customer" on payment

### Custom fields (already in code)
The checkout session is created with two custom fields: `company_name` and `vat_number` (both optional). These appear on the Stripe-hosted checkout page and are included on the generated PDF receipt — this is the "expensable" design that removes the procurement barrier for SME buyers.

---

## Section 10 — Testing Guide

### Full happy-path test sequence
1. Start the app locally with `STRIPE_PRICE_ROADMAP_EUR` set to a valid test-mode price ID
2. Open Case Command → click "New case"
3. Select employee type: "EEA national resident in France"
4. Set move date to 8 weeks from today
5. Click "Run Case Command" — case is created in DB with `access_tier = 'free'`
6. Verify: CaseGate renders with teaser (requirement count, non-obvious badges, feasibility flag)
7. Verify: "+N more requirements" locked row is visible
8. Click "Unlock full roadmap + vendor list — €800"
9. Verify: redirected to Stripe Checkout hosted page
10. Enter test card: **4242 4242 4242 4242** · any future expiry · any CVC
11. Optionally enter company name and VAT number in custom fields
12. Complete payment
13. Verify: redirected back to `?payment=success`
14. Verify: "Payment confirmed" toast appears for

> [TRANSMISSION TRUNCATED HERE — 2026-07-19. The source instruction ended
> mid-sentence at step 14 above. The remainder of Section 10, and the entirety of
> Section 11 and Section 12, were never received. Do not treat this document as a
> complete 12-section spec.]
