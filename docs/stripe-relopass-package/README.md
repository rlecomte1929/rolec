# ReloPass — Stripe Integration Package
**Version:** 1.0 | **Date:** 2026-07-18 | **Status:** Ready for implementation

## What This Implements
Tier 0 → Tier 1 gate inside Case Command:
- Free teaser shows partial results (requirement count, feasibility flag, 2–3 non-obvious item names)
- Rest gated behind €800 Stripe Checkout (one-time, per case)
- Webhook unlocks full access server-side after payment
- Expensable receipt (company name + VAT number) issued automatically by Stripe
- Add-on table scaffolded (empty) for future vendor category unlocks

## Build Sequence

| Step | File | What it does |
|------|------|-------------|
| 1 | migration_add_payment_to_cases.sql | Add payment columns to relocation_cases |
| 2 | migration_create_case_addons.sql | Create case_addons table |
| 3 | .env.example | Set all Stripe environment variables |
| 4 | Create Stripe products in Dashboard (test mode) | Get Price IDs for env vars |
| 5 | relopass-payments.routes.ts | Add /checkout + /access endpoints |
| 6 | webhook-extension.ts | Extend webhook for checkout.session.completed |
| 7 | hooks/useCaseAccess.ts | Access-tier hook |
| 8 | CaseGate.tsx | Build paywall component |
| 9 | case-command-App-updated.tsx | Wire gate into Case Command |
| 10 | Test full flow in Stripe test mode | Card: 4242 4242 4242 4242 |
| 11 | case-payment-confirmation.ts | Send confirmation + receipt link |
| 12 | Switch to live Stripe price IDs | Go live |

## Quality Gates — Do Not Skip
- [ ] Vendor list verified (≥5 per category in /docs/vendor-directory-fr-no.md)
- [ ] End-to-end flow tested in Stripe test mode before switching to live keys

## Pricing Architecture

| Tier | Price | Type | Status |
|------|-------|------|--------|
| 0 — Free teaser | €0 | Always shown | Build now |
| 1 — M1 Roadmap + Vendor List | €800 | One-time per case | Build now |
| 2 — Essentials (immigration) | €2,000 | One-time per case | Stub — requires lawyer sign-off |
| 3 — Starter retainer | €2,500/yr | Annual subscription | Stub |
| 4 — Growth retainer | €5,000/yr | Annual subscription | Stub |

## Key Design Decisions
1. Access is per-case, not per-account
2. Gate fires after case creation, before full results are shown
3. Never trust the client — access_tier written only by webhook
4. Expensable by design — VAT number + company name collected at checkout
5. Add-ons scaffolded in DB, not built — build after 5 real cases
6. €2,000 Essentials tier is always greyed out / disabled — not functional until lawyer sign-off
