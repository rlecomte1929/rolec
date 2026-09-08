# Environment & keys — why there is no `.env`

The original Node/Postgres spec called for a `.env` file with:

```
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ROADMAP=price_...
STRIPE_PRICE_ESSENTIALS=price_...
```

**None of these exist in this codebase, by design.** Audos spaces have no
`.env` mechanism, and the platform Stripe integration works differently:

| Spec env var | Audos equivalent |
|---|---|
| `STRIPE_SECRET_KEY` | Platform-managed. Hooks call the platform endpoints (`/api/payments/checkout`, `/api/payments/status/:sessionId`) which hold the keys server-side. No key ever touches workspace code. |
| `STRIPE_WEBHOOK_SECRET` | Platform-managed. The real Stripe webhook terminates at the Audos platform. The workspace-level `stripe-case-webhook` hook never validates a Stripe signature — instead it re-verifies every session against the status API, which is strictly safer for forwarded payloads. |
| `STRIPE_PRICE_ROADMAP` | Sessions are priced by **amount in cents**, not Stripe price IDs. The authoritative amount `80000` (€800) is hardcoded in the `case-checkout` hook; the display mirror is `PRICE_ROADMAP_CENTS` in `lib/pricing.ts`. |
| `STRIPE_PRICE_ESSENTIALS` | Scaffold only: `PRICE_ESSENTIALS_CENTS = 200000` (€2,000) in `lib/pricing.ts`. No checkout wired in v0. |

## Payment modes

The workspace runs on the platform Stripe integration, which supports two
modes (see the `stripe-payments` integration docs):

1. **Platform mode (default)** — payments settle through the platform's
   Stripe account; works with zero setup.
2. **Connect mode** — the founder connects their own Stripe account under
   Wallet → "Accept Payments"; payments then settle directly to their bank
   account (platform fee applies).

Switching modes requires **no code change** in this integration — the same
`/api/payments/*` endpoints route to whichever mode is active.

## Keeping prices in sync

When pricing changes, update BOTH places or the UI will advertise a
different price than checkout charges:

1. The hardcoded amount inside the `case-checkout` server function
   (authoritative — what Stripe actually charges).
2. `PRICE_ROADMAP_CENTS` in `lib/pricing.ts` (what the UI displays).
