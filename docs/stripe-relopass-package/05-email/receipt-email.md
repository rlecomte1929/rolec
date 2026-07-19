# Post-payment confirmation email (expensable receipt)

Sent via the hook-sandbox helper `platform.sendEmail` by whichever hook
confirms the payment first — the lazy verification path inside `case-access`
or the `stripe-case-webhook` hook. Idempotency on
`payment_status != 'paid'` guarantees it is sent **once** per unlock, even if
both paths race or a webhook replays.

Stripe also sends its own payment confirmation independently; this email is
the ReloPass-branded receipt the HR buyer can expense.

## Contract

| Field | Value |
|---|---|
| To | `case_access.customer_email` (collected in the CaseGate form before redirect) |
| Subject | `ReloPass — Roadmap unlocked (receipt enclosed)` |
| Trigger | The row's first transition to `payment_status='paid'` / `access_tier='roadmap'` |

## Body contents

- Confirmation that the full roadmap + vendor shortlist for the case is
  unlocked (France → Norway corridor, case reference `#<case_access.id>`).
- Receipt block:
  - Amount — `€800` one-time (formatted from `amount_cents` / `currency`)
  - Case reference — `#<id>`
  - Company — `billing_company` (if provided)
  - VAT — `billing_vat` (if provided)
- Note that the receipt is expensable as a professional service, and that
  Stripe sends its own payment confirmation separately.

## Why company + VAT are collected before checkout

The platform checkout endpoint (`POST /api/payments/checkout`) has no
custom-field support, so the CaseGate form collects company name and VAT
number **before** the Stripe redirect, stores them on the `case_access` row,
and the email prints them on the receipt. See the reference implementations
in `03-backend/` for the exact HTML assembly.
