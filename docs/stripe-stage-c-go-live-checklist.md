# Stripe — Stage C go-live checklist (🔴 human-gated)

The final, deliberate go-live for the roadmap paywall. Runs **after** Stages A + B are green
(server-side chain + RLS + checkout on real Postgres, and the real paywall UI end-to-end).
See `docs/stripe-phase7-test-mode-runbook.md` for the test-mode validation and
`docs/stripe-integration-status-and-plan.md` for the full plan.

**Autonomy:** 🔴 **Red.** Three steps are human-only and no agent performs them:
**confirm the DPA (C1), set live keys (C4), and the go-live decision itself.** An agent may
prepare/verify every step and — on explicit human go — run the additive migration DDL (C3).

**Prod facts (verified 2026-07-22):** migration ledger max `20260926000000`; payment schema
not yet applied; `is_admin()` present. The migration files are timestamped `20260927…` so they
apply in order above the ledger.

---

## C0 — Prep: migrations re-timestamped ✅ (done)
`supabase/migrations/20260927000001/2/3_*.sql` — payment columns, `case_addons` (+RLS),
`stripe_events` (+RLS). Above the ledger max so `supabase db push` / Preview replay in order.

## C1 — Compliance gate (human)
Confirm Stripe's **DPA** (auto-incorporated in the Stripe Services Agreement) and the **SCC**
posture for US transfer. Update `docs/security/PRIV-004_sub-processor_register.md` (v1.8 Stripe
row) from "⬜ Confirm" to confirmed. **Legal precondition for processing real payment PII — an
agent cannot sign it.**

## C2 — Merge PR #1626 (human decision — deploys inert code)
1. CI green: `frontend-build`, `backend-tests`, router-registration guard, `migration-drift`,
   RLS-coverage, compliance-claims.
2. Merge → Render auto-deploys `main`.
3. **Verify it's inert** (all flags still off):
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.relopass.com/api/stripe/webhook
   # → 503 (RELOPASS_STRIPE_ENABLED unset). Checkout also 503; the roadmap gate is a no-op.
   ```

## C3 — Apply the migrations to prod (out-of-band; agent may run on explicit go)
Per `CLAUDE.md` migration discipline: **never** `apply_migration`. Either `supabase db push`,
or run the idempotent DDL via `execute_sql` (MCP) and reconcile the ledger to the filenames.
The DDL is `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` / `DROP POLICY IF EXISTS` —
safe to re-run.

**Verify (run after applying):**
```sql
SELECT
  (SELECT count(*) FROM information_schema.columns
     WHERE table_name='relocation_cases' AND column_name='access_tier') AS access_tier,   -- 1
  (SELECT count(*) FROM information_schema.tables
     WHERE table_schema='public' AND table_name='case_addons')   AS case_addons_tbl,       -- 1
  (SELECT count(*) FROM information_schema.tables
     WHERE table_schema='public' AND table_name='stripe_events') AS stripe_events_tbl,     -- 1
  (SELECT relrowsecurity FROM pg_class WHERE relname='stripe_events') AS stripe_events_rls,-- t
  (SELECT relrowsecurity FROM pg_class WHERE relname='case_addons')  AS case_addons_rls;   -- t
-- anon must have NO grant on either table (REVOKE): expect 0 rows
SELECT table_name, privilege_type FROM information_schema.role_table_grants
 WHERE grantee='anon' AND table_name IN ('stripe_events','case_addons');
```
Then confirm `migration-drift` is clean (ledger reconciled).

## C4 — Set prod env + redeploy (human — Render `rolec-eu`, `srv-d7ku8agjs32c7386fm4g`)
Set on the **service** env:
- `STRIPE_SECRET_KEY=sk_live_…`
- `STRIPE_WEBHOOK_SECRET=whsec_…`  (comma-separated list — one per registered endpoint)
- `RELOPASS_STRIPE_ENABLED=true`

Then **Manual Deploy** — Render env changes don't hot-reload. **An agent will not set live keys.**
✅ Check: `POST /api/stripe/webhook` now returns **400** (bad signature) instead of 503 — i.e.
the kill switch is off and it's verifying signatures.

## C5 — Register the live webhook (human — Stripe Dashboard, LIVE mode)
Developers → Webhooks → Add endpoint → `https://api.relopass.com/api/stripe/webhook`
(event `checkout.session.completed`). Copy its signing secret → append to
`STRIPE_WEBHOOK_SECRET` → redeploy.

## C6 — Smoke the live path (human runs a minimal real transaction / dashboard test-send; agent verifies)
```sql
-- a stripe_events row was written and the case flipped
SELECT event_id, type, case_id, status, received_at FROM stripe_events ORDER BY received_at DESC LIMIT 5;
SELECT id, access_tier, payment_status, paid_amount_cents FROM relocation_cases WHERE access_tier <> 'free' LIMIT 5;
```
Do not proceed to C7 until a real paid flow demonstrably flips a case.

## C7 — Enable the paywall — LAST (human)
- Backend: `RELOPASS_ROADMAP_PAYWALL_ENABLED=true` → redeploy.
- Frontend: `VITE_ENABLE_ROADMAP_PAYWALL=true` → rebuild the static site.

⚠️ This turns the gate on for **all** users at once: every case still at `access_tier='free'`
will 402 on the roadmap until paid. Only flip it after C6 proves the paid→unlock loop works.

---

## Rollback (any time, no code change)
- **Fastest:** `RELOPASS_STRIPE_ENABLED=false` + redeploy → checkout + webhook 503, fully inert.
- **Paywall only:** `RELOPASS_ROADMAP_PAYWALL_ENABLED=false` (+ frontend flag off) → gate no-op,
  everyone reaches their roadmap.
- **Transport:** change / remove the endpoint URL in the Stripe Dashboard (spec §9) — no deploy.

## Hard prohibitions (spec §10)
No agent executes a payment/refund/transfer or enables live keys. No card data touches our
infra (hosted Checkout only). Never commit a live key — rotate in Stripe if one leaks. The gate
is server-side. Never log raw event bodies. Live keys are enabled only after test-mode passes
end-to-end, by a human, deliberately.
