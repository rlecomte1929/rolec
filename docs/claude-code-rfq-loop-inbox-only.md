# Claude Code — RFQ HR-side loop, INBOX-ONLY dispatch

Paste from repo root. Base off current `main`.

**Founder decision:** ship the full RFQ loop so it feels live from the HR + supplier inbox/UI, but **suppress the actual Resend email send** (protect the free Resend quota). Email egress becomes a later config flip, not a rewrite. Nothing about the UX is faked — only the outbound email is held.

---

## ⚠️ Two corrections to the brief you may have been handed

1. **Branch: use a NEW dedicated branch off `main`, e.g. `feat/rfq-hr-loop-inbox`.** Do **NOT** use `fix/td-qa-services-batch-0719` — it carries ~40 duplicate doc commits and unrelated migrations and is unreviewable. Every clean fix this cycle went on its own branch off `main`; keep that.
2. **The taxonomy relabel is NOT a "Cowork DB" job** — it's a committed migration (already filed separately). Ignore it here.

## Reuse what exists — do NOT rebuild

Cowork verified the infra you need is already present. Build on it:

- **Inbox/notification system:** `frontend/src/features/platform-v2/inbox/InboxV2Page.tsx`, `NotificationsBell.tsx`, and the **`notification_outbox`** table + `notification_outbox_dispatch.py` consumer. The outbox is your dispatch-mode seam.
- **The Resend gate already exists.** `notification_outbox_dispatch.py::run_outbox_dispatch_cron` is the ONLY path that hands an address to Resend, and it's already gated by a recipient allowlist (`_recipient_allowed`) **and** by the cron flag `OUTBOX_DISPATCH_CRON_ENABLED` (currently unset → **no email is sent today**). So "inbox-only" is largely the *current* state — the work is to make the loop functional while keeping that egress closed.
- **Supplier magic-link infra:** `supplier_rfq.py` (`require_supplier_link`, token hashing, expiry). M1/M2/M3 audited it as sound — **reuse it, do not rebuild.**

## Established state (do NOT re-litigate — DB-verified)

- Employee RFQ write is **perfect**: `rfqs`=1 (status `sent`), `rfq_items`, `rfq_recipients`=6, correct `case_id`, canonical model.
- **Broken:** (a) no HR surface reads `rfqs` — the HR endpoint (`hr_rfq.py::list_rfqs`) reads the **orphaned** `rfq_requests`; the coordination panel reads a provider table. (b) `rfq_recipients.token_hash` = **0/6** — no tokens minted, nothing dispatched.

---

## BUILD — 4 parts, one branch, atomic where sensible

### Part 1 — HR read path (the core fix)
Point the HR RFQ surfaces at the **canonical `rfqs` / `rfq_items` / `rfq_recipients`**, keyed on the real `case_id`:
- `hr_rfq.py::list_rfqs` (GET `/api/hr/rfq-requests`) currently reads `rfq_requests` → repoint to `rfqs`. Either retire the orphaned reader or repoint it; no HR surface should read the dead model.
- The **Provider Coordination panel** (`GET /api/hr/cases/{id}/providers`, `hr_coordination.py`) reads a provider table — surface the RFQ's 6 recipients with status, or add an RFQ view the panel links to.
- **Acceptance:** the 6 vendors the employee picked render for HR with status, on the real case.

### Part 2 — Token minting on dispatch
On HR dispatch, mint `rfq_recipients.token_hash` per recipient and generate the supplier magic link via the **existing** `supplier_rfq` link infra.
- **Acceptance:** after dispatch, `token_hash` is populated 6/6; each supplier link resolves via `require_supplier_link`.

### Part 3 — Dispatch mode: `inbox` (default) vs `email` (later)
Add a dispatch mode. **Default `inbox`.**
- **`inbox` mode:** enqueue the RFQ notification to the in-app inbox (`notification_outbox` row + inbox surface) and **surface the working magic link in that inbox record**. The supplier opens the link from the inbox and can submit a quote — full UX, zero email egress. **Do NOT call Resend.**
- **`email` mode (future):** identical, plus the Resend send. The flip is the only change to go live on email.
- **Simplest correct implementation:** the `notification_outbox` consumer already refuses to send unless `OUTBOX_DISPATCH_CRON_ENABLED` is set and the recipient is allowlisted. So enqueuing to the outbox in `inbox` mode, while leaving the cron flag unset, gives you inbox-visible-but-not-emailed **for free**. Add an explicit `dispatch_mode` column/field so the intent is legible and the future flip is one config change — don't rely solely on the cron flag being unset.
- **Acceptance:** in `inbox` mode, a dispatch produces an inbox record with a working link and makes **zero Resend calls** (assert Resend is not invoked in the test).

### Part 4 — RFQ confirmation copy (⭐ was a separate P1 — now resolvable to TRUE)
`ServicesRfqNew.tsx:346` says *"your HR team can see the providers you picked and will follow up."* Once Part 1 lands, **this becomes true.** Update the copy to match the now-real capability (HR can see it), and update the test assertion in `__tests__/ServicesRfqNew.send.test.tsx:~149`. If you'd rather ship the honesty fix first as its own PR, that's fine — but with Part 1 done, the strong copy is finally accurate.

---

## GATE — all green before merge
- `cd frontend && npx tsc --noEmit`
- `cd backend && pytest` (add: HR reads `rfqs`; token_hash minted 6/6; **inbox mode makes no Resend call**)
- `cd frontend && npm run build`
- **e2e loop:** employee submits RFQ → HR sees the 6 vendors with status → HR dispatches → supplier opens the magic link **from the inbox** → supplier submits a quote (amount `1234`) → quote returns to HR. This is Q2/Q3, finally unblocked by inbox mode.
- Route dump (both main files) if any router changed.

## HARD RULES
- Branch off `main`, own PR. **Never `fix/td-qa-services-batch-0719`.** Never push to `main`.
- New router → register in BOTH `backend/main.py` + `backend/app/main.py`.
- **Never set `OUTBOX_DISPATCH_CRON_ENABLED`** — that is the email egress; keeping it unset is what makes inbox-only real.
- Any new `public` column/table → migration committed, applied out-of-band (never `apply_migration`), RLS if a new table.
- Reuse the audited supplier-token security; do not weaken or rebuild it. Do NOT create a 4th RFQ model.

## REPORT
`branch · SHA(s) · PR URL` · HR read path repointed to `rfqs`? · `token_hash` minted (n/6)? · `dispatch_mode` field added, defaults `inbox`? · **Resend confirmed NOT called in inbox mode (test)?** · confirmation copy now accurate? · gate results · **Q2/Q3 e2e pass/fail**.

Once this ships, Q2/Q3 are browser-runnable — the supplier can finally submit a quote through the inbox loop. Cowork will DB-verify: `rfq_recipients.token_hash` 6/6, `quotes`/`quote_lines` on submission, and zero Resend log entries.
