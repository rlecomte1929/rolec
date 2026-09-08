# Stripe — portable webhook architecture (Audos **or** Render, switchable)

**Repo:** `rlecomte1929/rolec` · **Supabase:** `nsvefcvpvwwwhuqyuqmp`
**Goal:** run Stripe fulfilment from the Audos hook **or** the FastAPI backend on Render, and switch between them at will — without a code change, a redeploy, or a behaviour difference.
**Autonomy tier:** 🔴 **Red — human gate.** Money, secrets, external service. Never auto-merged.

---

## 1. The principle: one brain, two mouths

The mistake to avoid is implementing fulfilment twice. If the Audos hook and the FastAPI route each contain their own "verify → flip tier → record" logic, they will drift, and you will have two payment systems with subtly different bugs.

**All business logic lives in the repo. The transport is the only thing that varies.**

```
PATH A (default — Render)
  Stripe ──► https://api.relopass.com/api/stripe/webhook
                 └─ verify signature ─► fulfil() ─► DB

PATH B (Audos relay)
  Stripe ──► Audos hook /hooks/<id>
                 └─ forwards RAW body + Stripe-Signature header, unmodified
                      └─► https://api.relopass.com/api/stripe/webhook
                             └─ verify signature ─► fulfil() ─► DB
```

**The Audos hook is a dumb relay.** It does not verify, parse, enrich or interpret anything. It forwards bytes. The ReloPass backend verifies the Stripe signature itself in both paths, so it never has to trust Audos — Audos is convenience infrastructure, not a trusted component.

Consequences, all good:
- Identical code path in both modes → no drift, no double-testing of business rules.
- Audos can disappear tomorrow and payments keep working.
- Switching modes is a **Stripe Dashboard URL change**, not a deploy.

> **Do not** have the Audos hook verify the signature and then call a "trusted" internal endpoint. That makes Audos a security dependency and creates a second endpoint that must be defended. Relay raw bytes; verify once, in the backend.

---

## 2. The switch

| Mode | Stripe Dashboard endpoint URL | Audos hook |
|---|---|---|
| **Render (default)** | `https://api.relopass.com/api/stripe/webhook` | disabled / not registered |
| **Audos relay** | `https://<audos-hook-host>/hooks/<id>` | enabled, relays to the same backend URL |
| **Both (cutover testing)** | register both endpoints | enabled |

Stripe issues a **separate signing secret per registered endpoint**. So `STRIPE_WEBHOOK_SECRET` must accept a **comma-separated list**, and verification tries each in turn. That is what makes "both at once" possible during cutover, and it means switching never requires touching code.

---

## 3. Component 1 — shared fulfilment service (the brain)

`backend/app/services/stripe_fulfillment.py`

```python
def fulfil_stripe_event(db, event: dict) -> dict:
    """Idempotently apply a VERIFIED Stripe event. Never called with an unverified event.

    Returns {"status": "applied"|"duplicate"|"ignored", "case_id": ..., "tier": ...}
    """
```

Requirements:

1. **Idempotency is mandatory.** Stripe retries on any non-2xx, and in "both" mode the same event can arrive twice. Before doing anything, attempt to insert `event["id"]` into `stripe_events` (§6). On conflict → return `{"status": "duplicate"}` and do nothing else. This single guard is what makes the dual-path design safe.
2. Handle `checkout.session.completed` first. Ignore unknown event types with `{"status": "ignored"}` and a 200 — never 4xx an unrecognised event, or Stripe will retry it forever.
3. Read `case_id` from `session.metadata.case_id`. If absent or unknown → log a structured error, return 200, do **not** raise. A 500 here triggers infinite retries.
4. Flip `relocation_cases.access_tier` `free → roadmap | essentials` based on the purchased price/product. The column already exists (`20260719000001_add_payment_to_cases.sql`, CHECK `IN ('free','roadmap','essentials')`).
5. Write the add-on row to `case_addons` where applicable. **Verify this table actually exists in production first** — the migration `20260719000002_create_case_addons.sql` is committed but did not appear in a live table survey. If it is absent, that migration needs applying (operator, out-of-band) before this path works.
6. Never log the raw event body — it contains customer data. Use `safe_log_text()` from `pii_masker.py`.

**This function is the only place tier changes happen.** Nothing else in the codebase writes `access_tier`.

---

## 4. Component 2 — Path A: the FastAPI endpoint

`backend/app/routers/stripe_webhook.py`

```python
@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    raw = await request.body()                     # RAW BYTES — never the parsed JSON
    sig = request.headers.get("Stripe-Signature")
    event = verify_stripe_signature(raw, sig)      # tries each secret in the list
    if event is None:
        raise HTTPException(400, "invalid signature")
    return fulfil_stripe_event(db, event)
```

**Non-negotiables:**

- **Signature verification uses the raw request body.** If FastAPI parses the JSON and you re-serialise it, the bytes change and every signature fails. Read `await request.body()` before anything else touches it.
- Return **200** for duplicates and ignored events. Return **400 only** for a genuinely invalid signature. Any 5xx puts Stripe into retry.
- Rate limiting must **exempt** this route, or Stripe retries will be throttled into failure.
- Timing-safe comparison only. Use the Stripe SDK's `construct_event`; do not hand-roll HMAC.

### 4.1 ⚠️ Register the router in BOTH places

```python
# backend/app/main.py
app.include_router(stripe_webhook.router)

# backend/main.py  — imports ~line 130, registrations ~line 710
from .app.routers import stripe_webhook as stripe_webhook_router
app.include_router(stripe_webhook_router.router)
```

Render boots `uvicorn backend.main:app`. A router registered only in the modular app **returns 405 in production** — this has caused three incidents. Verify before pushing:

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'stripe' in r.path))"
```
An empty list means it is dead on arrival.

---

## 5. Component 3 — Path B: the Audos relay

Keep it under ~20 lines. It must:

1. Accept the Stripe POST.
2. Forward to `https://api.relopass.com/api/stripe/webhook`:
   - the **raw body, byte-for-byte unmodified** — no JSON parse, no re-encode, no whitespace change, no charset conversion. Any mutation breaks signature verification downstream;
   - the `Stripe-Signature` header verbatim;
   - `Content-Type: application/json`.
3. Return the backend's status code to Stripe unchanged, so Stripe's retry logic keeps working end to end.
4. Add nothing, log no bodies, store nothing.

**Latency budget:** Stripe's default signature tolerance is 300 seconds, so a relay hop is comfortably inside it. But if the relay ever queues or batches, verification will start failing — relay synchronously or not at all.

**The existing hook (`/hooks/7db312e6…`) currently does its own verification.** Strip that out and reduce it to a relay, otherwise the logic exists in two places and §1 is defeated.

---

## 6. Idempotency table (migration required — 🔴 Red)

`supabase/migrations/<timestamp>_stripe_events.sql`

```sql
CREATE TABLE IF NOT EXISTS public.stripe_events (
  event_id     text PRIMARY KEY,
  type         text NOT NULL,
  received_at  timestamptz NOT NULL DEFAULT now(),
  case_id      text,
  status       text NOT NULL DEFAULT 'applied'
);

ALTER TABLE public.stripe_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service role manages stripe events"
  ON public.stripe_events FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

REVOKE ALL ON public.stripe_events FROM anon;
```

The anon key ships in the frontend bundle and Supabase exposes `public` via PostgREST — a table without RLS is readable by any unauthenticated visitor. This caused **SEC-002** (8 tables, GDPR-scope PII). No customer or frontend role ever needs to read this table.

**Migration discipline:** commit the file with idempotent DDL. **Never apply it to production yourself**, never write to `supabase_migrations.schema_migrations`. The operator applies out-of-band and reconciles the ledger.

---

## 7. Environment variables

| Var | Where | Notes |
|---|---|---|
| `STRIPE_SECRET_KEY` | Render backend | Never in the frontend, never committed |
| `STRIPE_WEBHOOK_SECRET` | Render backend | **Comma-separated list** — one secret per registered Stripe endpoint |
| `RELOPASS_STRIPE_ENABLED` | Render backend | Kill switch: when false the endpoint 503s and fulfils nothing |

The Audos relay needs **no Stripe secrets at all** — it never verifies anything. If the relay is holding a signing secret today, remove it; that is the tell that it is doing more than relaying.

---

## 8. Test plan (all must pass before enabling live keys)

Use the Stripe CLI against a local backend:

| # | Test | Expected |
|---|---|---|
| 1 | `stripe trigger checkout.session.completed` → Path A | `access_tier` flips, `stripe_events` row written |
| 2 | **Replay the same event** | `{"status":"duplicate"}`, **200**, tier unchanged, no second `case_addons` row |
| 3 | Tampered body, valid-looking signature | **400**, nothing mutated |
| 4 | Unknown event type | **200**, `{"status":"ignored"}` |
| 5 | Missing `metadata.case_id` | **200**, structured error logged, no crash, no retry storm |
| 6 | Same event via Path A **and** Path B | Exactly **one** tier flip |
| 7 | Relay with a mutated body (re-serialised JSON) | **400** — proves the relay must not touch bytes |
| 8 | Paid surface requested at `access_tier='free'` | **402/403 server-side**, not a frontend-only hide |
| 9 | `RELOPASS_STRIPE_ENABLED=false` | 503, nothing fulfilled |
| 10 | Route registration check (§4.1) | Non-empty list |

Test 6 is the one that proves the portable design is safe. Do not skip it.

---

## 9. Cutover runbook

**To Render (default):**
1. Confirm §8 passes in test mode.
2. Add the Render endpoint in the Stripe Dashboard; add its signing secret to `STRIPE_WEBHOOK_SECRET`.
3. Send one test event; confirm a `stripe_events` row.
4. Remove the Audos endpoint from Stripe (or disable the hook).

**To Audos relay:**
1. Add the Audos hook URL as a Stripe endpoint; append its signing secret to the list.
2. Confirm the relay forwards raw bytes (test 7).
3. Send one test event through the relay; confirm one `stripe_events` row.
4. Remove the Render endpoint from Stripe if running relay-only.

**Rollback in either direction:** change the endpoint URL in the Stripe Dashboard. No deploy. That is the whole point.

---

## 10. Hard prohibitions

- **No agent executes a payment, refund, or transfer.** Ever. Test-mode triggers only.
- **No card data touches your infrastructure** — Stripe Checkout hosted pages only, never a custom card form.
- **Never commit a live key.** If one is committed, rotate it in Stripe before anything else.
- **The gate is enforced server-side.** Hiding a button in React is not a paywall.
- **Never log raw event bodies.**
- Live keys are enabled only after §8 passes end to end, by a human, deliberately.
