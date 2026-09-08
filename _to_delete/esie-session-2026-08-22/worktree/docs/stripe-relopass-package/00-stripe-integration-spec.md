# Stripe Payment Integration — Case Command (AS BUILT, v0)

> NOTE: Otto's build instruction referenced a pre-written spec at this path,
> but the file did not exist in the workspace when the integration was built
> (2026-07-18). This document is the **as-built record** of what was actually
> implemented, adapted to the Audos platform. Treat it as the source of truth
> for v1 work (add-ons, Essentials tier).

## What it does

Case Command's **Corridor check** view (France → Norway) is gated Tier 0 → Tier 1:

- **Tier 0 (free):** the HR generalist enters employee type + move date. The
  deterministic rule engine (`apps/case-command/rule-engine.ts`) computes the
  full requirement sequence, but only a TEASER renders: total requirement
  count, 2–3 real non-obvious requirements verbatim (D-number, skattekort
  timing, police registration), the rest blurred.
- **Tier 1 (€800 one-time):** "Unlock your full roadmap + vendor shortlist —
  €800" → Stripe Checkout (platform Stripe integration, currency EUR) → on
  return the full roadmap renders and the case stays unlocked across reloads.
- **Tier 2 (€2,000 "Immigration assurance"):** visible in the gate as a
  greyed-out "coming soon" row. Scaffolded only — no checkout wired.

## Platform adaptations (why this differs from the original Node/Postgres spec)

| Original spec | As built on Audos |
|---|---|
| `ALTER TABLE relocation_cases ADD access_tier/payment_status/...` | WorkspaceDB has no column-add tool, so payment state lives in a sidecar table **`case_access`** (FK `case_id` → `relocation_cases.id`, one row per corridor-check case). |
| `POST /api/payments/case-checkout` | Server function **`case-checkout`** (`POST /api/workspaces/workspace-776786/hooks/case-checkout/execute`). Creates the Stripe session via the platform `/api/payments/checkout` (amount 80000 cents EUR — authoritative server-side), sets `payment_status='pending'`, stores `stripe_session_id` + billing company/VAT. Returns `{ url }`. |
| `GET /api/payments/case-access?caseId=` | Server function **`case-access`** (same execute pattern). Returns `{ caseId, accessTier, paymentStatus, unlockedAt }` (+ `employeeType`, `moveDate` for post-redirect restore). Creates the free row on first check. |
| `POST /api/payments/webhook` extension | The REAL Stripe webhook terminates at the platform (platform-managed keys), so server-side confirmation is done by **re-verifying the checkout session against `/api/payments/status/:sessionId`**: lazily inside `case-access` on every read, and in the **`stripe-case-webhook`** server function (accepts forwarded `checkout.session.completed` payloads but NEVER trusts them — it always re-verifies with Stripe). Idempotent: dedup on `stripe_session_id` + `payment_status != 'paid'`. |
| `.env` with `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_*` | No `.env` on Audos; Stripe keys are platform-managed and sessions are priced by cents amount, not price IDs. Display-side mirror constants live in `lib/pricing.ts` (`PRICE_ROADMAP_CENTS=80000`, `PRICE_ESSENTIALS_CENTS=200000` scaffold). Authoritative amount is in the `case-checkout` hook — keep both in sync. |
| Checkout collects company name + VAT | The platform checkout endpoint has no custom-field support, so company + VAT are collected in the CaseGate form BEFORE redirect, stored on `case_access`, and printed on the emailed receipt. |
| Confirmation email w/ receipt | Sent via `platform.sendEmail` from the confirming hook (subject "ReloPass — Roadmap unlocked (receipt enclosed)"), including amount, case reference, company, VAT. Stripe also sends its own payment confirmation. |

## Data model (WorkspaceDB)

- **`case_access`** — one row per corridor-check case. Key columns:
  `case_key` (unique, `frno|<sessionId>|<employeeType>|<moveDate>`),
  `employee_type`, `move_date`, `access_tier` ('free'|'roadmap'|'essentials'),
  `payment_status` ('unpaid'|'pending'|'paid'|'refunded'), `stripe_session_id`,
  `stripe_payment_intent_id`, `amount_cents`, `currency`, `billing_company`,
  `billing_vat`, `customer_email`, `paid_at`. Written ONLY by the hooks —
  treat as read-only from app code.
- **`case_addons`** — v1 scaffold, empty, no logic: `case_id`,
  `case_access_id`, `addon_type` ('movers'|'immigration_lawyers'|
  'tax_advisors'|'schools'|'pets'), `stripe_session_id`, `payment_status`,
  `paid_at`.

## Frontend

- **`components/CaseGate.tsx`** — the gate. Fetches access on mount, renders
  teaser (headline, verbatim previews, blurred children, €800 CTA + receipt
  line, greyed Essentials row) or children when `accessTier >= 'roadmap'`.
  Post-redirect it polls access (~30s) until server-side verification
  confirms. Never flips access client-side.
- **`apps/case-command/CorridorCheck.tsx`** — the two-input checker + full
  roadmap renderer, wrapped in CaseGate. Restores the last check from
  localStorage and from `?payment=success&caseId=N` after Stripe returns
  (success URL: `<space>?app=case-command&payment=success&caseId=N`).
- **`apps/case-command/App.tsx`** — additive header toggle: Cases | Corridor
  check. Defaults to Corridor check when landing on a payment redirect.
- **`lib/pricing.ts`** — tier prices, `tierAtLeast()` helper.

## Security model

The client is never trusted: pricing is fixed inside `case-checkout`
(server-side), and the unlock is written only after a hook confirms
`paymentStatus === 'paid'` from the platform Stripe status API. A forged
"payment succeeded" call cannot unlock a case (verified in testing). The
teaser blur is presentational — the rule engine ships in the client bundle,
so the roadmap content is deterrence-gated, not cryptographically secret
(same as the original spec's blur approach).

## Out of scope in v0 (unchanged from the instruction)

- Tier 2 Essentials checkout, subscription tiers, add-on category pricing
  (movers/schools/…), changes to the existing cases dashboard, landing page.
