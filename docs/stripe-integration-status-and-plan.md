# Stripe integration — status & go-live plan

**Status:** 🔴 Red (money + GDPR). **Not functional / not deployed.** Assessment as of 2026-07-22.
**Locked design decisions:** portable-ready fulfilment brain, wire **Path A** (direct Stripe→Render)
first; the Audos relay stays a later config change (no rebuild). **Go-live is human-gated** — no agent
enables live keys.

This is an assessment + sequenced plan. It reflects three parallel code reviews (backend, frontend,
spec/compliance) reconciled against the authoritative spec `docs/stripe-portable-webhook-spec.md` and the
as-built package `docs/stripe-relopass-package/`.

---

## 1. Current state (verified)

### What exists
- **Checkout endpoint** — `backend/app/routers/payment.py` (currently untracked; **not registered** in
  either `backend/main.py` or `backend/app/main.py`, so it 404s in prod). Creates a Stripe Checkout
  session via hand-rolled `requests` (no Stripe SDK). Price is fixed **server-side** at €800 = 80000c
  EUR (`ROADMAP_AMOUNT_CENTS`), so the client cannot forge the amount. Auth is present and correct:
  `require_hr_or_employee` + `require_assignment_visibility` (both live on `origin/main`). Reads
  `STRIPE_SECRET_KEY`, `APP_BASE_URL`. Metadata carries `assignmentId` / `tier` / `source`.
- **Paywall UI** — `frontend/src/features/employee-journey/RoadmapPaywallGate.tsx` +
  `frontend/src/utils/paymentStatus.ts` (both untracked, **wired into nothing** — the roadmap pages and
  feature-flag file are unchanged from `main`). The €800 copy matches the backend.
- **Parked migrations** — on branch `feat/stripe-payments` (commit `c7401c14`, "do not merge"): adds
  `relocation_cases` payment/`access_tier` columns and a `case_addons` table. **`case_addons` ships with
  NO RLS** (violates the repo hard gate). Not on `main`, not applied to prod.
- **Specs (good)** — `docs/stripe-portable-webhook-spec.md` (authoritative portable design) and the
  as-built `docs/stripe-relopass-package/`.

### What's missing (the make-or-break pieces)
- **No webhook, no fulfilment brain, no idempotency** — `stripe_webhook.py`, `stripe_fulfillment.py`,
  and a `stripe_events` table are all absent. A completed Stripe payment is **never observed
  server-side**.
- **No server-side entitlement / gate** — the "unlock" is a **client-side localStorage flag**
  (`paymentStatus.ts`, self-labeled "TEST PHASE ONLY"), set from a `?payment=success` URL param. Anyone
  can set the flag or visit the URL to unlock €800 of value for free. No backend code checks payment
  state before serving a roadmap.
- **No tests.** `.env.example` documents **no** Stripe vars; `STRIPE_WEBHOOK_SECRET` isn't referenced
  anywhere in code.
- **Git scatter + hazard** — the work spans `feat/stripe-payment-checkout` (paywall commit),
  `feat/stripe-payments` (migrations), and untracked files on the working branch. The shared checkout's
  HEAD has been observed flipping mid-work (cross-branch race) — do future work in an isolated worktree.

### Compliance blockers
- **Stripe not in PRIV-004** sub-processor register → add a row, **sign the Stripe DPA**, document the
  US-transfer mechanism (SCC/DPF), and record the data flows (email/billing via hosted Checkout; card
  data never touches ReloPass infra). GDPR Art. 28.
- **RLS** required on every new payment table (`stripe_events`, `case_addons`, any `case_access`):
  `ENABLE ROW LEVEL SECURITY` + a policy + `REVOKE ALL … FROM anon`. The parked `case_addons` violates
  this.
- **Copy honesty** at €800 — "Receipt issued automatically" (no receipt path exists yet) and "verified
  vendors" (the `verified` flag isn't actually used as a filter; unverified suppliers are live). The
  automated compliance-claims guard itself is NOT tripped, but these are substantiation risks.

### Verdict
An **early scaffold** — the front door (checkout-session creation) with everything behind it missing, and
the only "gate" is client-trusted. Safe today *only* because it's unreachable (unmounted + unwired). It
must not go live until the server-side fulfilment + gate + compliance items below exist.

---

## 2. Go-live plan (phased; portable-ready brain + Path A; each phase ≈ one PR)

**Phase 0 — Stabilise the WIP (first, low-risk).** Consolidate all scattered Stripe WIP onto one clean
branch **in an isolated git worktree** (avoids the shared-checkout race); keep `main` pristine. Add the
Stripe env vars to `.env.example`. Nothing deploys.

**Phase 1 — Data layer (migrations + RLS).** Rework the parked migrations: `relocation_cases.access_tier`
+ payment columns; `case_addons` **with RLS + service-role policy + REVOKE anon**; a new **`stripe_events`**
idempotency table (RLS'd). Committed idempotent DDL; applied out-of-band per migration discipline; ledger
reconciled (a `case_addons` env-drift reconcile is likely). Reuse the RLS pattern shown in the spec.

**Phase 2 — Fulfilment brain (portable, transport-agnostic).**
`backend/app/services/stripe_fulfillment.py` → `fulfil_stripe_event(db, event)`: insert `event.id` into
`stripe_events` first (idempotency); handle `checkout.session.completed` only (all other event types →
"ignored", never 4xx); flip `access_tier` and write `case_addons`; **never 500** on missing
`metadata.case_id` (log via `safe_log_text` + return 200). This is the single place tier changes happen.

**Phase 3 — Webhook, Path A.** `backend/app/routers/stripe_webhook.py` → `POST /api/stripe/webhook`:
verify the signature on **raw bytes** (`construct_event`); `STRIPE_WEBHOOK_SECRET` as a comma-separated
list (lets the Audos relay be added later with no rebuild); `RELOPASS_STRIPE_ENABLED` kill-switch (503
when off). **Register in BOTH** `backend/main.py` and `backend/app/main.py`; verify with the route-dump
one-liner.

**Phase 4 — Server-side gate (replace client trust).** `GET /api/payment/status/:caseId` reading
`access_tier`; the roadmap-serving path checks it server-side; replace the `paymentStatus.ts` localStorage
read with this API; wire `RoadmapPaywallGate` into `EmployeeCaseRoadmapPage` **behind a feature flag
(default off)**. Reconcile `assignmentId` vs `case_id` (the spec keys on `case_id`).

**Phase 5 — Checkout hardening.** Register `payment.py`; keep the auth + server-side pricing; add the
kill-switch; ensure `metadata.case_id` is set so the webhook can resolve the case.

**Phase 6 — Compliance.** PRIV-004: add Stripe + sign the DPA + document the transfer mechanism and data
flows. Fix copy: "Receipt issued automatically" only once the receipt path ships; "verified vendors" only
once the `verified` filter is actually applied (or soften the wording).

**Phase 7 — Test + go-live gate (human).** Run the spec's **10-test plan in TEST MODE** (the
idempotency/duplicate tests are load-bearing). Then a **human** signs the DPA and enables **live** Stripe
keys — no agent enables live keys.

---

## 3. Verification
Per phase: dual-registration route-dump; `scripts/check_migration_drift.py` + `scripts/check_rls_coverage.py`
green after the migrations; unit tests + the spec's integration tests (especially idempotency/duplicate).
End-to-end in test mode: a real test-card checkout → webhook → `access_tier` flips → the server-gated
roadmap unlocks; forging `?payment=success` or a localStorage flag does **nothing** server-side. No live
keys until the human gate.

## 4. References
- `docs/stripe-portable-webhook-spec.md` — authoritative portable-webhook design.
- `docs/stripe-relopass-package/` — as-built Audos package (schema, receipt-email contract).
- `docs/audos-prompt-stripe-portable.md` — execution brief.
- `docs/security/PRIV-004_sub-processor_register.md` — sub-processor register (add Stripe here).
- Root `CLAUDE.md` — migration discipline, RLS hard gate, dual-router registration, PII masking.
