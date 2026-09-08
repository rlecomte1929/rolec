# Audos brief — make Stripe portable (Audos relay ⇄ Render backend)

**Attached spec:** `docs/stripe-portable-webhook-spec.md` — **authoritative.** Read it fully before planning. This cover note only tells you what changes, who executes what, and where the gates are.
**Autonomy tier:** 🔴 **RED — human gate throughout.** Money + secrets + external service. Nothing auto-advances.

---

## 0. The one thing that changes about what you already built

#84515 shipped Stripe signature verification **onto the Audos platform hook** (`/hooks/7db312e6…`). It works — but it makes Audos a **trusted security component** of a payment path, and it forces the fulfilment logic to exist in two places, where it will drift.

**The new design inverts that:**

- The Audos hook becomes a **dumb relay**. It forwards the raw request body and the `Stripe-Signature` header, byte-for-byte, and returns the backend's status code. It verifies nothing, parses nothing, stores nothing, and holds **no Stripe secret**.
- The **FastAPI backend verifies the signature in both paths** and owns all fulfilment logic.

Result: identical code runs whichever path is active, Audos is convenience infrastructure rather than a dependency, and switching between them is a Stripe Dashboard URL change — no code change, no redeploy.

**So: strip verification out of the existing hook.** Do not build a second verification path. Do not have the hook call a "trusted internal" endpoint. §1 and §5 of the spec explain why.

---

## 1. Execution split

| Component | Executor | Notes |
|---|---|---|
| `stripe_fulfillment.py` (fulfilment brain) | **Cursor** — repo | §3 of spec |
| `stripe_webhook.py` (FastAPI endpoint) | **Cursor** — repo | §4; **register in BOTH `backend/main.py` and `backend/app/main.py`** |
| `stripe_events` migration | **Cursor** — repo | §6; **commit the file only, never apply** |
| Tests 1–10 | **Cursor** — repo | §8; Stripe CLI, test mode only |
| Reduce the hook to a relay | **You (Audos)** | §5; ~20 lines, no secrets |
| Stripe Dashboard endpoints + signing secrets | **Romain only** | see §3 |
| Enabling live keys | **Romain only** | after §8 passes |

---

## 2. Sequence — stop at each gate

**Step 0 — prerequisites (verify before writing any code).**
- Does `public.case_addons` exist in Supabase? Migration `20260719000002_create_case_addons.sql` is committed but did **not** appear in a live table survey. Fulfilment writes to it. If absent, it needs applying out-of-band before this works — **report, do not apply.**
- Confirm `relocation_cases.access_tier` exists with CHECK `IN ('free','roadmap','essentials')`.
- Confirm nothing else in the codebase writes `access_tier` (it should be zero today).

Repo/Supabase checks are Cursor's — your DB tools reach WorkspaceDB only and cannot answer these. **Report and stop.**

**Step 1 — build behind a kill switch.** Implement §3, §4, §6 with `RELOPASS_STRIPE_ENABLED=false`. The endpoint 503s and fulfils nothing until Romain flips it. Commit; do not merge to `main`.

**Step 2 — relay.** Reduce the Audos hook to §5. Verify it forwards bytes unmodified (spec test 7 proves this — a re-serialised body must produce a 400 downstream).

**Step 3 — test.** All ten tests in §8, test mode only. **Test 6** (same event through both paths → exactly one tier flip) is the one that validates the portable design. **Test 2** (replay → duplicate, 200, no second write) is the one that prevents double-charging. Neither may be skipped or marked "expected to pass".

**Step 4 — STOP.** Report results. Romain reviews, configures the Stripe Dashboard and secrets himself, and decides when live keys are enabled.

---

## 3. What you must NOT do

- **Never handle, enter, request, generate or store a Stripe key** — secret key, publishable key, or webhook signing secret. If a step needs one, stop and tell Romain what to set and where. Do not ask him to paste it to you.
- **Never execute a payment, refund, capture, or transfer.** Stripe CLI test-mode triggers only.
- **Never enable live keys**, or register a production Stripe endpoint.
- **Never apply the migration.** Commit the file; the operator applies out-of-band; never write to `supabase_migrations.schema_migrations`.
- **No custom card form.** Stripe Checkout hosted pages only — no card data touches your infrastructure.
- **Never merge to `main`.** Feature branch off `main`, e.g. `feat/stripe-portable-webhook`. Do **not** use `fix/td-qa-services-batch-0719` — it is already carrying ~40 duplicate doc commits and unrelated migrations.
- **Never log raw event bodies.** Use `safe_log_text()` from `pii_masker.py`.
- **Do not commit one file per commit.** Use the Git Trees API for a single atomic commit — that pattern produced ~40 duplicate commits twice already.

---

## 4. Evidence required — a claim without these is not accepted

- Route registration proof:
  ```bash
  python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'stripe' in r.path))"
  ```
  An empty list means the endpoint 405s in production.
- Raw output of the §8 test run — all ten, pass/fail each.
- The migration **file path**, plus explicit confirmation it was **not applied**.
- Branch name and full commit SHA.
- For the relay: confirmation it holds **no Stripe secret** and mutates **no bytes**.

Report format: branch · SHA · files changed · tests run with raw output · what is blocked. Three prior reports contained only a repo name and a hash; the work looked like it hadn't happened.

---

## 5. Still open — not part of this task, do not lose

1. **Track B** — 5 sessions on `?campaign=qa-p0-1&corridor=FR_NO`, clean n/5. Never created as a task; deferred four times. It gates RUN 004.
2. **AIQ-1631** — your two runs contradict each other (#84501: aliasing wins; #84574: taxonomy wins) and **both reasoned from a stale 2026-07-16 snapshot** with no access to `3f9ed63a` or `121403c8`. Treat both as **void**. Cowork is settling it from the real diff.
3. **Unverified suppliers are reachable** — confirmed repo-side: `verified` is never used as a query filter in `supplier_registry.py`, `rfq_recipient_mapping.py` or `vendor_curation.py`. The 9 Norway suppliers are `status='active'`, `verified=false` and live. Not pending anything. Do not approve them; a filter decision is Romain's.
4. **Email cron** — `518bf11c` added a 15-minute outbox dispatcher gated behind `vars.OUTBOX_DISPATCH_CRON_ENABLED`. It has **no recipient filter**. Leave that variable unset. A hard `@probe.test`-only guard is required before it is ever enabled, and certainly before the INSEAD cohort.
5. **Persistence design (P0-1)** — Option C still awaiting Romain, and its basis needs re-deriving from the real diff rather than the stale snapshot.

---

## 6. Report

```
STEP 0 — PREREQUISITES
  public.case_addons exists? ____
  access_tier present + CHECK correct? ____
  Anything else writing access_tier? ____
  [STOPPED — awaiting go]

STEP 1-3 — BUILD + TEST
  Branch: ____  SHA: ____
  Route registration output: ____
  Tests 1-10: [raw output]
  Test 2 (replay → duplicate): ____
  Test 6 (both paths → one flip): ____
  Test 7 (mutated body → 400): ____
  Migration file path: ____   Applied? MUST BE NO ____
  Relay holds no Stripe secret? ____   Mutates no bytes? ____

  [STOPPED — Romain configures Stripe Dashboard + secrets and decides on live keys]

BLOCKED / NOT DONE: ____
```
