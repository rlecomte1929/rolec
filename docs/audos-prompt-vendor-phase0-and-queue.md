# Audos brief — store topology, queue decisions, and Vendor Phase 0

**Context date:** 2026-07-19 · **Repo:** `rlecomte1929/rolec` · **Supabase project:** `nsvefcvpvwwwhuqyuqmp`
**Decides:** vendor canonical store · RFQ store-of-record (Option A) · queue actions · Vendor Phase 0 scope
**Unchanged:** `docs/audos-prompt-p0-1-round3.md` — both Track A gates still stand.

---

## 0. Store topology — read this first; everything else depends on it

You were right that two stores exist and that `relopass_vendors` lives in WorkspaceDB. The prior brief said flatly that it "does not exist" — that was checked against Supabase only and stated too broadly. Correction accepted.

**But one premise in your reconciliation is wrong, and it changes Phase 0.** You wrote that case data (`relocation_cases`, `case_access`, `case_addons`) lives in WorkspaceDB while canonical `suppliers` lives in Supabase, making a cross-store FK. Production says otherwise:

| Table (Supabase, live) | Rows |
|---|---|
| `relocation_cases` | **496** |
| `rfqs` | **9** |
| `rfq_recipients` | **17** |
| `suppliers` | **17** |

**Cases, RFQs and suppliers are all in Supabase, together, with live production data.** There is no cross-store FK in the deployed system.

### 0.1 The operating rule

**ReloPass production is Supabase. Full stop.**
- `DATABASE_URL` points at the Supabase pooler (transaction mode, port 6543).
- Render boots `uvicorn backend.main:app` against it.
- Every table the product reads or writes at runtime is in Supabase.

**Audos WorkspaceDB is your working environment, not a second production store.** `relopass_vendors` sitting empty there (from task #83885) is a sandbox artifact. Nothing the deployed application does will ever read it.

### 0.2 What this forbids

**No Phase 0 table may be created in WorkspaceDB.** Any table the product needs lands in **Supabase, via a committed migration file**, applied out-of-band by the operator. Building vendor tables in WorkspaceDB would produce a shadow catalog the app never reads — the failure mode is silent and would not surface until someone asks why the vendor list is empty in production.

If you believe a specific artifact genuinely belongs in WorkspaceDB, say which and why, and stop for confirmation.

---

## 1. Queue — explicit decisions per job

| Job | Action | Reason |
|---|---|---|
| **#84574** | **DO NOT CANCEL** | **This is Track A** — the P0-1 recommend-only job carrying the Step 0 recommendation, the persistence design, the Stripe §4 answer and the `hr_user_id` finding. You listed it as Track A one message ago and then offered it for cancellation as "another rolec Cursor job". Cancelling it discards the work everything is waiting on. |
| #84567 | Already COMPLETE — no action | Committed the Stripe docs + 2 migrations; `main` head verified unchanged. |
| #84573 | Cancelled ✅ — correct | Straight re-commit of #84567's files. |
| **#84571** | **Let it finish** | You caught a real contradiction and your instinct was right. The cancel recommendation assumed it was queued; now that it's running, the "don't kill a running job mid-lock" principle applies. Overlap with Track A costs duplicated effort at worst — cheaper than an interrupted commit. |
| #84586 | Leave it | Platform bug (server-functions hook sandbox), unrelated to this work. |

**Priority once the lock frees: #84574 (Track A).**

---

## 2. Option A — APPROVED, with the reasoning corrected

**Decision: yes, the RFQ engine's store-of-record is the Supabase backend.**

But this is **ratification, not migration**. Per §0, the RFQ engine already runs there — 9 live RFQs, 17 recipients, alongside `relocation_cases` (496) and `suppliers` (17), with routers (`hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`), services, and six applied migrations. **Do not plan a move, a port, or a cross-store bridge.** There is nothing to relocate. Approving Option A means: keep building where the code and data already are.

---

## 3. Vendor canonical store — DECIDED

**`suppliers` (Supabase) is canonical.** Evidence: 17 rows, **89 code references**, plus a built-out satellite ecosystem — `supplier_service_capabilities` (97), `supplier_cluster_cache` (95), `supplier_scoring_metadata` (90), `company_preferred_suppliers`, `hr_supplier_submissions`, `supplier_ranking_weights`.

**Deprecate across both stores** — half a deprecation guarantees someone repopulates the other half:

1. **Supabase `vendors`** — exists, 20 columns, **0 rows**, zero code references. Retire it. If dropping needs a migration, commit the file; do not apply it yourself.
2. **WorkspaceDB `relopass_vendors`** — empty, 22 columns, created by task #83885. Drop it.
3. **WorkspaceDB `vendors`** — 8 legacy GlobeIQ rows. Decide explicitly: migrate the 8 into Supabase `suppliers`, or archive and drop. **Do not leave it as a third live catalog.** Report which you recommend and why; if migrating, treat it as a data task with a documented mapping.
4. **Never create a table named `relopass_vendors` in Supabase.** The name is retired.

---

## 4. Vendor Phase 0 — scope

### 4.1 The seed gap comes first
The seed datasets in `backend/app/recommendations/datasets/` hold **80** suppliers (movers 10, living_areas 38, schools 32). Production `suppliers` has **17 rows**. **The seed has never fully run in production.**

This precedes any new table work. Before adding categories, establish:
- Why only 17 of 80 landed — partial run, failure, or filtering by design?
- Whether `seed_suppliers.py` is safe to re-run idempotently against production.
- What the true per-category counts are today.

The "5 verified vendors per category" deliverable is further away than the dataset files imply. Report the real numbers before proposing work.

### 4.2 Missing categories
`immigration` and `tax` are unseeded — 3 of 5 categories exist. These are the two most relevant to a corridor product. Scope what sourcing them requires; do not invent supplier records.

### 4.3 The 9 pending Norway suppliers
These sit behind your approval gate. Keep them there. Present them for Romain's review with source and verification status per supplier. **Do not auto-approve.**

### 4.4 Hard gates for any new table
Any new `public` table in Supabase requires **all three**, or it fails review:

```sql
ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;
CREATE POLICY "<name>" ON public.<t> FOR SELECT USING (/* tenant scoping */);
REVOKE ALL ON public.<t> FROM anon;
```

The anon key ships in the frontend bundle and Supabase exposes `public` via PostgREST — a table without RLS is readable by any unauthenticated visitor. This caused **SEC-002** (8 tables, GDPR-scope PII). Canonical pattern: the `case_milestones` policies.

**Migrations:** commit `supabase/migrations/<timestamp>_<name>.sql` with idempotent DDL. Never apply to production, never write to `supabase_migrations.schema_migrations`. Any migration is 🔴 **Red — human-gated**.

**Branch:** cut a dedicated branch off `main` for Phase 0 (e.g. `feat/vendor-phase-0`). Do not add it to `fix/td-qa-services-batch-0719`, which is already carrying unrelated Stripe docs and migrations.

---

## 5. Track B — confirmed, you execute

Browser-driven, no code lock, independent of the Cursor queue. Run it now.

1. Provision **5** fresh test-drive sessions, clean context each, at
   `https://relopass.com/test-drive?campaign=qa-p0-1&corridor=FR_NO`
2. Record each first-name label so sessions are identifiable.
3. For each, determine whether the company ended with a **published** policy-config version.
4. Report a clean **n/5** from these five sessions only.

**Do not inherit the 15/15 figure.** It was observational and unverifiable — the `hr_user_id` ↔ `profiles.id` join returns zero matches, so those 15 could not be linked to sessions.

**Interpretation:**
- **5/5** → seed is healthy; close that line. The persistence design becomes the sole critical path.
- **0–4/5** → intermittent. Capture the **actual exception text** from the swallow at `backend/app/routers/test_drive.py:229–232`. Do not guess.

**Cleanup:** report every `qa-p0-1` artifact for purging. Never touch `insead-2026`.

**RUN 003 B16**, if run, is labelled `PRE-MERGE BASELINE (main @ 1f2e4593)` — `3f9ed63a` is undeployed, so production reads old code and "No policy rule" there is expected, not a regression.

---

## 6. Still open — unchanged from the prior brief

- **Track A gate 1** — AIQ-1631 reconciliation. Four overlapping attempts, three already on `main` (`c765c4d2`, `bef49ab7`, `03d4b18e`, `38e53704`) plus `fix/f14-shared-taxonomy`. Recommend a direction; **stop**.
- **Track A gate 2** — persistence design A/B/C. `policy_id` is `uuid NOT NULL`; a colon-bearing string cannot be written to it, so FK relaxation alone does not help. Romain's preference is **C**. Recommend; **stop**.
- **Task #84515 / Stripe §4** — still unanswered. No Stripe code exists in `backend/app/`, `backend/main.py` or `frontend/src/`; the only match in the application is a CSS comment. Re-committing `docs/stripe-relopass-package/` does not change this — those are TypeScript spec artifacts in `docs/`, imported by nothing. Confirm the file path(s) written, or state plainly that #84515 is spec-only.

```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if any(k in r.path for k in ('stripe','payment','webhook'))))"
```
An empty list means the webhook is not live.

---

## 7. Report format

```
STORE TOPOLOGY
  Confirmed: no Phase 0 artifact created in WorkspaceDB ____
  WorkspaceDB vendors (8 legacy rows) recommendation: migrate / archive ____

QUEUE
  #84574 Track A: NOT cancelled ____ | started? ____
  #84571: finished ____

VENDOR PHASE 0
  Seed gap — actual prod counts per category: ____
  Why 17 of 80 landed: ____
  seed_suppliers.py idempotent-safe to re-run? ____
  Deprecation: Supabase vendors ____ | WorkspaceDB relopass_vendors ____ | WorkspaceDB vendors ____
  Norway 9 — presented for approval, NOT auto-approved ____
  Branch: ____

TRACK B
  Seed rate: ___/5  (campaign qa-p0-1, corridor FR_NO)
  If <5/5 — actual exception text: ____
  Artifacts to purge: ____

TRACK A (when it returns)
  Step 0: ____ | Persistence rec: ____ | [STOPPED for approval]

TASK #84515
  File path(s): ____ | Route live? ____ | Spec-only? ____
```

**Sequencing:** Track B starts now. Track A takes the lock as soon as it frees. Vendor Phase 0 begins with the §4.1 seed-gap measurement — no new tables until the real counts are known.
