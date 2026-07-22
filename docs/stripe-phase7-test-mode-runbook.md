# Stripe — Phase 7 test-mode verification runbook + go-live gate

**Autonomy:** 🔴 **Red — human gate.** This runbook is run by a **human** in **Stripe TEST MODE**.
No agent enables live keys, runs a real charge, or applies migrations to prod. The end state of
this runbook is "test-mode green + DPA confirmed"; the *last* two steps (sign DPA, enable live keys)
are deliberate human actions.

Maps 1:1 to the 10-test plan in `docs/stripe-portable-webhook-spec.md` §8. Each test below is tagged:

- **[AUTO]** — run by `scripts/stripe_test_mode_smoke.py` (locally-signed, no Stripe CLI, no real card).
- **[CLI]** — run manually with the Stripe CLI (`stripe trigger` / `stripe listen` / `stripe events resend`).
- **[CHECK]** — a one-line command or env change.
- **[DEFERRED]** — Path B (the Audos relay) is not built yet (only Path A shipped); these validate at
  relay-cutover time. The *property* that makes them safe (idempotency, raw-byte verification) is
  covered by tests #2 and #3, so the design is not unprotected in the meantime.

---

## 0. Prerequisites (all in TEST MODE, never prod)

1. **A non-prod database.** Point the backend at a **local or staging** Postgres — **never** the prod
   project (`nsvefcvpvwwwhuqyuqmp`). The smoke script refuses a prod API base-url; you must also make
   sure `DATABASE_URL` is not prod.
2. **Apply the Phase-1 migrations to that test DB** so `relocation_cases.access_tier`, `case_addons`,
   and `stripe_events` exist:
   ```bash
   # against the TEST/STAGING db only
   supabase db push        # or apply supabase/migrations/2026071900000{1,2,3}_*.sql by hand
   ```
   > Go-live note (prod, later): these files carry `20260719…` timestamps, which are **below** the prod
   > ledger max. Before applying to prod, bump them above the ledger max, or apply out-of-band via
   > `execute_sql` + reconcile the ledger (see `CLAUDE.md` → *Ledger reconciliation*). Do **not** `supabase
   > db push` them to prod as-is — they would replay out of order.
3. **A test-mode Stripe account** + the Stripe CLI (`stripe login`).
4. **Env for the backend** (test mode):
   ```bash
   export RELOPASS_STRIPE_ENABLED=true
   export STRIPE_SECRET_KEY=sk_test_...          # TEST key
   export APP_BASE_URL=http://localhost:3000
   # STRIPE_WEBHOOK_SECRET is printed by `stripe listen` in step 5 — set it, then restart the backend.
   ```
5. **Start the webhook forwarder** (Path A) and copy the signing secret it prints:
   ```bash
   stripe listen --forward-to localhost:8000/api/stripe/webhook
   # → "Ready! Your webhook signing secret is whsec_xxx"
   export STRIPE_WEBHOOK_SECRET=whsec_xxx        # comma-separated list supported; one value here
   ```
   Restart `uvicorn backend.main:app --reload --port 8000` so it picks up the secret.
6. **A disposable test case.** Pick (or create) a `relocation_cases` row in the test DB and note its
   `id` — this is the `case_id` the fulfilment flips. It will end at `access_tier='roadmap'`; reset it
   to `'free'` afterwards.

---

## 1. Automated smoke checks — `scripts/stripe_test_mode_smoke.py`

Runs the deterministic webhook tests with locally-signed events (it holds a `STRIPE_WEBHOOK_SECRET`
value, so it can forge valid + invalid signatures). No Stripe CLI, no real card.

```bash
# non-mutating subset (#3 tampered, #4 unknown-type, #5 missing-case_id):
python scripts/stripe_test_mode_smoke.py \
  --base-url http://localhost:8000 --webhook-secret "$STRIPE_WEBHOOK_SECRET"

# add the mutating happy-path (#1 applied) + (#2 duplicate) against a disposable case:
python scripts/stripe_test_mode_smoke.py \
  --base-url http://localhost:8000 --webhook-secret "$STRIPE_WEBHOOK_SECRET" \
  --case-id <disposable_relocation_cases_id>
```

It asserts the webhook's own `{"status": ...}` response, so it needs no DB access. Expected: all
checks `PASS`. Then confirm the side effect once, by hand: the flipped case now reads
`access_tier='roadmap'` (see §3, test #8).

| Spec test | Covered by the script |
|---|---|
| **#1** applied (tier flip) **[AUTO, mutating]** | signed `checkout.session.completed` with `metadata.case_id` + `tier=roadmap` → `{"status":"applied"}` |
| **#2** duplicate replay **[AUTO, mutating]** | re-POST the *same* `event.id` → `{"status":"duplicate"}`, no second flip |
| **#3** tampered body, valid-looking sig **[AUTO]** | signature computed over a *different* body → **400** |
| **#4** unknown event type **[AUTO]** | signed `payment_intent.succeeded` → **200** `{"status":"ignored"}` |
| **#5** missing `metadata.case_id` **[AUTO]** | signed `checkout.session.completed`, no case_id → **200** `{"status":"ignored","reason":"missing_case_id"}` |

---

## 2. Manual Stripe-CLI checks

**#1 — real end-to-end (the highest-fidelity happy path) [CLI].** Prefer this over the scripted #1
at least once, because it exercises the *real* Stripe event shape:
1. Create a checkout session through the product: `POST /api/payment/checkout {assignmentId, tier:'roadmap'}`
   (authenticated as the employee who owns a disposable case). Confirm the response `checkoutUrl` and that
   the session's `metadata.case_id` is the resolved `relocation_cases` id (Phase 5 sets this).
2. Open `checkoutUrl`, pay with test card **4242 4242 4242 4242**, any future expiry / any CVC.
3. Watch the `stripe listen` window: `checkout.session.completed` → forwarded → **200**.
4. Assert: the case flipped to `access_tier='roadmap'`, `payment_status='roadmap_paid'`, and a
   `stripe_events` row exists for that `event.id`.

**#2 — replay the same event [CLI].** `stripe events resend <evt_id>` (the id from step 3) → **200**,
`{"status":"duplicate"}`, tier unchanged, **no** second `case_addons`/`stripe_events` row.

**#4 — unknown type [CLI].** `stripe trigger payment_intent.succeeded` → **200** ignored.

**#5 — missing case_id [CLI].** `stripe trigger checkout.session.completed` (default fixture, no
metadata) → **200**, structured "missing_case_id" log, no crash, no retry storm.

**#6 — same event via Path A *and* Path B [DEFERRED].** The Audos relay is not built (only Path A
shipped). Validate at relay cutover: register both endpoints, send one event, assert **exactly one**
tier flip. The idempotency guard that makes this safe is already proven by **#2**.

**#7 — relay with a mutated (re-serialised) body [DEFERRED].** Relay-dependent. The protective
property — verification on **raw bytes** — is proven by **#3** (any body that doesn't match the
signature is a 400).

---

## 3. Gate + infra checks

**#8 — paid surface at `access_tier='free'` → server-side 402 [CHECK].** This is the Phase-4a gate.
```bash
export RELOPASS_ROADMAP_PAYWALL_ENABLED=true   # restart backend
# a FREE case:
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/cases/<free_case_id>/roadmap          # → 402
# the case you paid in test #1 (roadmap tier):
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/cases/<paid_case_id>/roadmap          # → 200
# and the status endpoint the frontend will read:
curl -s -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/payment/status/<paid_case_id>         # → roadmap_unlocked: true
```
> Leave `RELOPASS_ROADMAP_PAYWALL_ENABLED` **off** in prod until payments are live — on, it 402s every
> still-`free` case (i.e. everyone), which is why it is flag-gated.

**#9 — kill switch [CHECK].** Set `RELOPASS_STRIPE_ENABLED=false`, restart, POST any body to the
webhook → **503**, nothing fulfilled. (Also verify `POST /api/payment/checkout` → 503.)

**#10 — route registration [CHECK].** Non-empty list, from the repo root:
```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'stripe' in r.path or '/api/payment' in r.path))"
# → ['/api/payment/checkout', '/api/payment/status/{case_id}', '/api/stripe/webhook']
```

---

## 4. Go-live cutover (🔴 human only — after §1–§3 are green)

Per spec §9. **No agent performs any step in this section.**

1. **Confirm compliance (PRIV-004).** Sign / confirm Stripe's DPA (auto-incorporated in the Stripe
   Services Agreement) and the SCC posture for US transfer. See
   `docs/security/PRIV-004_sub-processor_register.md` (v1.8 Stripe row + sign-off list).
2. **Apply the Phase-1 migrations to prod** out-of-band (bump timestamps above the ledger max first),
   then reconcile the ledger. Verify `relocation_cases.access_tier`, `case_addons`, `stripe_events`
   exist in prod.
3. **Set prod env** on the Render service (`rolec-eu`): `STRIPE_SECRET_KEY=sk_live_…`,
   `STRIPE_WEBHOOK_SECRET=whsec_live_…` (comma-separated list), `RELOPASS_STRIPE_ENABLED=true`.
   Render env changes need a **manual redeploy** to take effect.
4. **Register the Render webhook** in the Stripe Dashboard → `https://api.relopass.com/api/stripe/webhook`;
   add its signing secret to `STRIPE_WEBHOOK_SECRET`.
5. **Send one live test event** (a real small-value flow or a dashboard test send) → confirm a
   `stripe_events` row + a tier flip on a known case.
6. **Turn on the paywall UI** (Phase 4b) + `RELOPASS_ROADMAP_PAYWALL_ENABLED=true` **only after** a paid
   flow demonstrably unlocks a roadmap end-to-end.

**Rollback (either direction):** change the endpoint URL in the Stripe Dashboard — no deploy. To fully
disable: `RELOPASS_STRIPE_ENABLED=false` + redeploy → webhook + checkout 503.

---

## 5. Hard prohibitions (spec §10 — restated)

- No agent executes a payment, refund, or transfer. Test-mode triggers only.
- No card data touches our infrastructure — Stripe hosted Checkout only.
- Never commit a live key. If one leaks, rotate it in Stripe first.
- The gate is server-side (`assert_roadmap_access`); hiding a button is not a paywall.
- Never log raw event bodies.
- Live keys are enabled only after §1–§3 pass end-to-end, by a human, deliberately.
