# Backend — the three server functions (Audos workspace hooks)

All backend logic runs as **Audos server functions** (workspace hooks): named
sandboxed JavaScript functions registered in the platform's hooks registry
and executed at

```
POST /api/workspaces/workspace-776786/hooks/<hookName>/execute
```

The hooks registry (`GET /api/workspaces/776786/hooks`) holds the
**authoritative deployed code**. The `.hook.js` files in this folder are
reference implementations reconstructed from the as-built spec so the founder
can read, review, and re-register them if needed — re-verify against the
registry (or the in-space Server Hooks tool) before treating any line as
deployed truth.

## Hook 1: `case-checkout` — create the Stripe Checkout session

`POST .../hooks/case-checkout/execute`

Request body (from `components/CaseGate.tsx`):

```json
{
  "caseId": 123,
  "customerEmail": "hr@company.com",
  "company": "ACME GmbH",
  "vat": "DE123456789",
  "successUrl": "<space>?app=case-command&payment=success&caseId=123",
  "cancelUrl": "<space>?app=case-command"
}
```

Behavior:
1. Loads the `case_access` row by `caseId`; rejects if missing or already paid.
2. Creates a one-time Stripe Checkout session via the platform endpoint
   `POST /api/payments/checkout` with the **server-fixed** amount
   `80000` cents / `eur` (the client never sends an amount).
3. Updates the row: `payment_status='pending'`, `stripe_session_id`,
   `amount_cents`, `currency`, `billing_company`, `billing_vat`,
   `customer_email`.
4. Responds `{ url }` — the Stripe-hosted checkout URL the browser redirects to.

## Hook 2: `case-access` — read/create access state (with lazy re-verification)

`POST .../hooks/case-access/execute`

Request body: `{ caseId }` and/or `{ caseKey, create: { employeeType, moveDate, sessionId } }`.

Behavior:
1. Finds the `case_access` row by `caseId` or unique `case_key`; creates the
   free row on first check (`access_tier='free'`, `payment_status='unpaid'`).
2. **Lazy verification:** if the row is `pending` with a
   `stripe_session_id`, it re-checks
   `GET /api/payments/status/:sessionId`; when Stripe reports
   `paymentStatus === 'paid'`, it upgrades the row
   (`access_tier='roadmap'`, `payment_status='paid'`, `paid_at=NOW`) and
   sends the receipt email (see `05-email/receipt-email.md`).
3. Responds `{ caseId, accessTier, paymentStatus, unlockedAt, employeeType, moveDate }`
   — the last two let the frontend restore the case inputs after the Stripe
   redirect.

## Hook 3: `stripe-case-webhook` — forwarded-event confirmation

`POST .../hooks/stripe-case-webhook/execute`

The REAL Stripe webhook terminates at the Audos platform (keys are
platform-managed), so this hook exists for forwarded
`checkout.session.completed` payloads. It **never trusts the payload**:
it extracts the session id, then re-verifies against
`GET /api/payments/status/:sessionId` before writing anything. A forged
"payment succeeded" call therefore cannot unlock a case.

Idempotency: the unlock is deduped on `stripe_session_id` and skipped when
`payment_status` is already `'paid'` — replays and the lazy path in
`case-access` cannot double-send the receipt email.

## Security model (all three hooks)

- Pricing is fixed server-side in `case-checkout`; the client only supplies
  identity and redirect URLs.
- The unlock (`access_tier='roadmap'`) is written **only** after a hook has
  itself confirmed `paymentStatus === 'paid'` from the platform Stripe status
  API.
- `case_access` is written only by these hooks; frontend code treats it as
  read-only.

## Re-registering a hook

Per the `server-functions` integration docs:

```
POST /api/workspaces/776786/hooks
{ "name": "case-checkout", "code": "<contents of case-checkout.hook.js>", "language": "javascript", "enabled": true }
```

Use `PATCH /api/workspaces/776786/hooks/:hookId` to update an existing one.

---

# v1.0 spec hooks: the `relopass-*` server functions (registered 2026-07-19)

The v1.0 spec build (`relopass-payments.routes.ts` + webhook extension)
landed as FOUR additional server functions, registered in the platform hooks
registry alongside the originals above. Reference copies live in this folder
as `relopass-*.hook.js`. `caseId` in all four = `case_access.id` (the sidecar
payment table — `relocation_cases` has no payment columns and WorkspaceDB
tables cannot be ALTERed).

| Hook | Endpoint | Contract |
|---|---|---|
| `relopass-create-case` | `POST /api/workspaces/776786/hooks/relopass-create-case/execute` | `{ corridor, employeeType, moveDate }` → `{ caseId }` |
| `relopass-checkout` | `POST /api/workspaces/776786/hooks/relopass-checkout/execute` | `{ caseId, tier: 'roadmap' \| 'essentials' }` → `{ checkoutUrl, sessionId }` (€800 / €2,000 fixed server-side) |
| `relopass-access` | `GET /api/workspaces/776786/hooks/relopass-access/execute?caseId=<id>` | → `{ caseId, accessTier, paymentStatus, accountTier, availableAddons }` (+ `employeeType`, `moveDate`, `unlockedAt`) |
| `relopass-webhook` | `POST /api/workspaces/776786/hooks/relopass-webhook/execute` | Stripe `checkout.session.completed` receiver — **register this URL in the Stripe Dashboard**. Verifies the `Stripe-Signature` header before any processing (see below). Only processes `metadata.source === 'relopass_case_command'`; never trusts the payload (re-verifies with the platform Stripe status API); idempotent. |

## `relopass-webhook` signature verification (updated 2026-07-19)

The deployed `relopass-webhook` hook now rejects any request that does not
carry a valid-looking `Stripe-Signature` header **before any other
processing** (HTTP 400 `{ "error": "Invalid signature" }`):

- the header must be present and well-formed (`t=<unix timestamp>` plus at
  least one `v1=<64-hex HMAC>` component), and
- the timestamp must be within a 5-minute tolerance window (Stripe's own
  default), which blocks replayed captures.

**Sandbox limitation:** full cryptographic verification with
`stripe.webhooks.constructEvent(rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET)`
is NOT possible inside the Audos hook sandbox — hooks receive only the
parsed JSON body (no raw body bytes to HMAC), have no `crypto` primitives,
no `require`/`import`, and no `process.env` (the `STRIPE_WEBHOOK_SECRET`
workspace secret is not exposed to hook code). The header is therefore
validated structurally and for freshness, and the real security guarantee
remains the second layer: the hook re-verifies the checkout session against
`GET /api/payments/status/:sessionId` before writing anything, so a
forged-but-well-formed request still cannot unlock a case.

Reference implementation: `relopass-webhook.hook.js` in this folder (kept in
sync with the registered hook code).

The frontend consumers are `apps/case-command/CaseGate.tsx` and
`apps/case-command/hooks/useCaseAccess.ts` (wired via
`apps/case-command/CorridorCheck.tsx`). The original `case-checkout` /
`case-access` / `stripe-case-webhook` hooks remain registered but the UI now
calls the `relopass-*` set. The same security model applies: server-side
pricing, unlock written only after server-side Stripe verification, and
lazy re-verification inside `relopass-access` so unlocks land even before
the Stripe Dashboard webhook is registered.
