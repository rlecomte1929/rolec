# ReloPass — Platform Roadmap & Contributor Handoff

**Repo:** `rlecomte1929/rolec` · **Owner:** Romain Lecomte
**Status date:** 2026-07-19 · **Audience:** external engineers / agencies / AI coding agents picking up work
**Supersedes:** the 30-item Audos roadmap (2026-07-19). See §1 for why ~12 of those 30 items should not be built.

This document is self-contained. You should be able to pick up any P0 item and start without asking a question.

---

## 0. How to read this document

Every item carries a **verification status**. This matters more than the priority:

| Tag | Meaning |
|---|---|
| ✅ **VERIFIED DONE** | Confirmed present and working in the live build or codebase on 2026-07-19. **Do not rebuild.** |
| 🟢 **VERIFIED PRESENT — needs QA** | Code exists and is wired. Unknown whether it works end-to-end. Test before writing any new code. |
| 🟠 **VERIFIED PARTIAL** | Some of it exists; the gap is stated precisely. Extend, don't restart. |
| 🔴 **VERIFIED ABSENT** | Confirmed no implementation. Genuine build work. |
| ❓ **UNVERIFIED** | Claimed but not confirmed by inspection. **Reproduce it before you fix it.** |

> **The single most expensive mistake available on this project right now is rebuilding something that already works.** The prior roadmap contained four P0/P1 items that were already fixed and five more resting on false premises. Read §1 before you read anything else.

---

## 1. Do not build these — already done (with evidence)

| Prior item | Claim | Reality (verified 2026-07-19) |
|---|---|---|
| F16 — Services binds to a phantom case | P0 build | ✅ **DONE** (AIQ-1612). Verified live: Services opens on the same case id as intake. |
| F15 — "destination missing" dead-end | P0 build | ✅ **DONE** (AIQ-1613). Verified live: no block, flow advances. |
| F10 — roadmap renders in-session | P1 build | ✅ **DONE** (AIQ-1614). Verified live: "Roadmap validated", 16 tasks across 5 phases, in-session. |
| F1 — credential email truncation | P1 build | ✅ **DONE** (AIQ-1622). Full emails render wrapped. *(The "persistent codes" half is still open — see P1-6.)* |
| #9 — "RFQ process non-functional, build it" | **P0 build** | 🟢 **BUILT, FULL STACK.** Routers `hr_rfq.py`, `supplier_rfq.py`, `employee_quotes.py`; services `rfq_brief.py`, `rfq_evaluation_service.py`, `rfq_recipient_mapping.py`, `supplier_link_dispatch.py`, `supplier_jwt.py`; pages `ServicesRfqNew.tsx`, `QuoteRfqDetail.tsx`, `QuoteRequestPage.tsx`, `SupplierQuotePage.tsx`; 6 migrations; 6 test files incl. payer-validation and email-injection hardening. **This is a QA task, not a build task.** |
| #10 — "verified vendor directory absent" | P1 build | 🟠 **3 of 5 categories seeded** (`seed_suppliers.py`): movers 10, living_areas 38, schools 32 = 80 rows. Missing only **immigration** and **tax**. |
| #15 — "replace LLM-as-source-of-truth with a deterministic rule engine" | P1 build | ✅ **ALREADY DETERMINISTIC.** `roadmap_builder.py::derive_roadmap` is the production source of truth — no LLM — and is what `cases_read.py`, `cases.py`, `specialist_review.py`, `test_drive.py` and `case_plan_delivery.py` call. `requirement_evaluation_service.py` docstring: *"deterministic MVP evaluator (no AI)"*. The LLM path (`roadmap_generator.py`) is a separate RAG route, already gated by `roadmap_confidence_gate.py`. **The premise of this item is false.** |
| #16 — `responsible_party` tagging | P1 build | ✅ **DONE.** Required field on every step (`loader.py:509`), authored in all 9 pathway YAMLs, resolved by `responsibility.py:33`, persisted and surfaced in `hr_case_detail.py`. |
| #21 — employer-owned / employer-absent state | P2 build | ✅ **DONE.** `EMPLOYER_ABSENT` constant at `responsibility.py:30`; employer-owned steps degrade automatically when no employer is engaged. |
| #20 — retrospective / already-elapsed flagging | P2 build | 🟠 **Overdue is done.** `relocation_plan_view_service.py` computes per-task `is_overdue` + aggregate `overdue_tasks`; plus `case_delay_monitor.py`, `roadmap_staleness.py`, `milestone_reminders.py`. Forward-looking feasibility is the real gap → see **P1-3**. |
| #22 — corridor-agnostic data model | P2 build | ✅ **DONE.** Corridors are authored YAML under `/corridors/`, loaded by `relopass/corridors/loader.py` with a strict versioned schema. Adding a corridor is a data job today. |
| #23 — author the NO→FR reverse corridor | P2 build | ✅ **ALREADY AUTHORED.** `corridors/NO_FR/pathways/RETURNING_EEA_CITIZEN_2026/v1.yaml`, with its own test (`test_corridor_no_fr.py`). **9 corridors exist**, all with `corridor.yaml`: IN_DE, DE_NO, ES_NL, FR_CH, FR_DE, FR_ES, FR_NL, FR_NO, NO_FR. |
| #14 — vendor performance capture | P3 build | 🟠 Partly present: `hr_vendor_performance.py`, `vendor_metric_snapshot_service.py`, `provider_ratings.py`. Verify before extending. |

**Net effect:** roughly 12 of the prior 30 items are done, partially done, or false-premise. Budget accordingly.

---

## 2. Non-negotiable repo rules (read before your first commit)

These are hard gates. Violating any of them ships a production incident. They are enforced by CI and by review.

### 2.1 Routers must be registered in TWO places
Render boots `uvicorn backend.main:app`. A router registered only in `backend/app/main.py` **returns 405 in production**. This has caused three incidents (AI-002 v2 → hotfix `5d796c2`; AIQ-567 and AIQ-568 rejected pre-merge).

```python
# 1. create backend/app/routers/<name>.py
# 2. register in backend/app/main.py
# 3. ALSO register in backend/main.py (imports ~line 130, registrations ~line 710):
from .app.routers import <name> as <name>_router
app.include_router(<name>_router.router)
```
Verify before pushing:
```bash
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if '<your-prefix>' in r.path))"
```

Tests mounting the prod app must import auth deps from `backend.app.auth_deps` — there is a second `get_current_user` in `backend/main.py`, and `dependency_overrides` keyed to the wrong one silently never fires.

### 2.2 Every new `public` table needs three things
Supabase exposes `public` via PostgREST and the anon key ships in the frontend bundle. A table without RLS is world-readable. This already caused **SEC-002** (8 tables, GDPR-scope PII exposure).

```sql
ALTER TABLE public.<t> ENABLE ROW LEVEL SECURITY;
CREATE POLICY "<name>" ON public.<t> FOR SELECT USING (/* tenant scoping */);
REVOKE ALL ON public.<t> FROM anon;
```
Canonical pattern reference: the `case_milestones` policies.

### 2.3 Migration discipline
Never apply a migration to production yourself and never insert into `supabase_migrations.schema_migrations`. Commit `supabase/migrations/<timestamp>_<name>.sql` with idempotent DDL, open a PR; the operator applies out-of-band and reconciles the ledger. CI's `migration-drift` check is read-only and never applies.

### 2.4 PII must be masked before any LLM call
Any user-supplied text reaching OpenAI or Anthropic must pass through `backend/app/services/pii_masker.py::mask_pii()` first (phone, IBAN, passport, SSN/D-number, national ID, email). Follow the `policy_assistant_llm_client.py` pattern. Never log raw user input — use `safe_log_text()`. New sub-processors go in `docs/security/PRIV-004_sub-processor_register.md`.

### 2.5 Never claim an EU AI Act status in shipped copy
No "EU AI Act Ready", "compliant", "certified", and never describe the AI as **high-risk**. Our own assessment (`docs/compliance/AIQ-1487_eu_ai_act_assessment.md`) found it **limited-risk**. Describe what controls *do* (human review, decision logging, citation, PII masking); claim no status. CI enforces via `scripts/check_compliance_claims.py`.

### 2.6 Build hygiene
`git config core.hooksPath .githooks` once per clone. `main` auto-deploys to Render, so every commit on `main` must build. Run `cd frontend && npx tsc --noEmit` before every PR — type-check is strict.

### 2.7 Design system
Read `DESIGN.md` before any visual change. Navy `#0b2b43` + teal `#1f8e8b` accent, Inter + JetBrains Mono, 8px grid, `frontend/src/components/antigravity/` component library. **There is no purple in the brand.** Use `navy-*` / `accent-*` Tailwind classes or `--rp-*` vars, never hex literals. The word **"journey"** is brand-forbidden in test-drive and marketing copy.

---

## 3. The corrected roadmap

### P0 — blocks the paid journey or the core product assertion

| ID | Item | Status | Est. |
|---|---|---|---|
| **P0-1** | Policy resolution → over-cap → Policy Exception → HR notification, proven end-to-end | 🟠 Partial — root cause identified, see §4.1 | M |
| **P0-2** | Stripe per-move payment gate | 🔴 Absent — spec complete, zero code | L |
| **P0-3** | QA the existing RFQ loop end-to-end and fix what's broken | 🟢 Built, unverified | M |

### P1 — required for a trustworthy v0

| ID | Item | Status | Est. |
|---|---|---|---|
| **P1-1** | Seed immigration + tax supplier categories (completes the €800 deliverable) | 🟠 3 of 5 categories | S |
| **P1-2** | Quote intake + side-by-side comparison surface for HR | ❓ Verify against `rfq_evaluation_service.py` first | M |
| **P1-3** | Forward feasibility: lead-time backward pass → amber/red timeline flags | 🔴 Absent (overdue exists; achievability does not) | L |
| **P1-4** | Non-EEA + move date < 6 weeks → critical permit warning surfaced top-of-roadmap | 🔴 Absent (instance of P1-3) | M |
| **P1-5** | Country autocomplete appends and cannot be cleared — first-time-user blocker | 🔴 Confirmed live bug | S |
| **P1-6** | Credentials persist (currently one-time reveal; a lost password killed a QA run) | 🟠 Reveal fixed, persistence not | S |
| **P1-7** | Currency defaults to USD; should default to destination currency (NOK for Oslo) | 🔴 Confirmed live bug | S |
| **P1-8** | Durable segmented test harness + run log | 🟠 Spec exists (`audos-…-run003.md`); no harness | M |

### P2 — depth and expansion

| ID | Item | Status |
|---|---|---|
| P2-1 | Service-request status tracking (requested → quoted → selected) | ❓ Verify |
| P2-2 | Audit the 6 thinner corridors (DE_NO, ES_NL, FR_CH, FR_DE, FR_ES, FR_NL) for step-count and depth vs the FR_NO/NO_FR reference pair | 🟠 |
| P2-3 | Per-corridor `assurance_status` / lawyer sign-off gate — never sell an unreviewed corridor | 🔴 |
| P2-4 | Non-obvious flags surfaced inline (D-number, skattekort-before-first-paycheck, EEA≠EU) | ❓ Verify against FR_NO YAML — may already be authored |
| P2-5 | Case system-of-record + audit trail | 🔴 |
| P2-6 | HR publish spinner hangs on success (F7) | ❓ Marked fixed (AIQ-1615/1616), reported broken by Audos — **reproduce before touching** |
| P2-7 | Intake "Continue" hidden behind the legal footer | ❓ Not reproduced in manual QA — confirm first |
| P2-8 | Capture tester segment at session start (currently NULL for every dropout) | 🔴 |

### P3 — sequenced last (data effects)

| ID | Item | Status |
|---|---|---|
| P3-1 | Rule-change alerts (between-move value; tests the churn hypothesis) | 🔴 |
| P3-2 | Vendor performance benchmarks | 🟠 Capture partly exists |
| P3-3 | Move Roadmaps as v1 output — only after Case Command is trustworthy | 🔴 |

---

## 4. Full specs for the P0 set

### 4.1 · P0-1 — Policy resolution → over-cap → Policy Exception → HR notification

**Goals.** A test-drive HR user sets a housing cap; the employee selects a housing option above it; an over-cap indication appears; a Policy Exception is created; HR is notified in-app. This is the highest-value unproven product assertion — it has failed to complete across RUN 001, 002 and 003.

**Spec — what is actually wrong.** Three prior diagnoses were wrong; here is the verified chain.

1. ❌ *"Policy/services taxonomy mismatch"* — **false**. The bridge shipped (AIQ-1611).
2. ❌ *"The seeded default policy has no caps"* — **false**. `policy_config_benefits` contains `host_housing_cap`, covered, at 5500 / 3800 / 2400 EUR by seniority.
3. ✅ **True cause:** `resolved_assignment_policies` is empty for test-drive cases — **0 of 31**, versus **2 of 2** for real cases. The Services page reads *resolved* benefits, so every card renders "No policy rule for this category".

**Why it's empty — two candidate mechanisms, both confirmed in code:**

- **Resolution is lazy, not eager.** The only write path to `resolved_assignment_policies` is `policy_resolution.py::resolve_policy_for_assignment` → `upsert_resolved_assignment_policy` (line 677). It is **not** called by `unified_assignment_creation.py::run_assignment_post_creation_hooks`, which runs only five hooks (contact link, mobility case link, case person, passport doc, welcome message). Resolution fires only on a cache-miss read at `backend/main.py:7634`, `:7689`, `:9951`, and `policy_service_comparison.py:323`.
- **The test-drive policy seed fails silently.** `test_drive.py::_seed_default_published_policy` (line 210, called line 313) is best-effort and swallows exceptions at lines 229–232. If it fails, resolution later finds nothing and logs `"policy_resolution: no published policy for any of companies %s"` (`policy_resolution.py:758`) — a warning, not an error.

Note that `backend/main.py:9951` wraps the employee-side resolution in a try/except that only logs a warning, so a failure there degrades to an empty policy view with no user-visible signal.

**Plan.**
1. **Diagnose before fixing.** On a fresh test-drive session, query: does a published `policy_configs` row exist for the test company? → If NO, the seed is failing: instrument lines 229–232 and find out why. If YES, resolution is not being triggered or is failing: check the `policy_resolution.py:758` warning in logs.
2. **Make resolution eager.** Add `resolve_policy_for_assignment` as a sixth hook in `run_assignment_post_creation_hooks`. Keep the lazy read path as a fallback — belt and braces.
3. **Stop swallowing failures.** The seed at `test_drive.py:229–232` and the read at `main.py:9955` must emit a structured error, not a warning. A silent policy failure is indistinguishable from "this company has no policy".
4. **Add a visible degraded state.** "Policy comparison unavailable" ≠ "No policy rule for this category". The current copy asserts a business fact that isn't known to be true.
5. Re-run RUN 003 Segment B step B16.

**Metrics.**
- `resolved_assignment_policies` coverage for test-drive cases: **0 of 31 → ≥ 95%**.
- Time from assignment creation to a resolved row: unbounded → **< 2s**, at creation.
- RUN 003 B16 branch: BLOCKED → **PASS**.
- Silent policy failures: currently unbounded → **0** (every failure emits a structured error).

**Validation.**
- `pytest backend/tests/test_policy_resolution.py` plus a new test asserting a resolved row exists immediately after `create_assignment_with_contact_and_invites`, with **no intervening read**.
- A test asserting the test-drive seed failure path raises/logs an error rather than passing silently.
- Manual: provision test-drive → HR assigns → **without opening any policy screen**, confirm the resolved row exists.
- E2E: RUN 003 §B16–B17 and §C3–C4 reach PASS.

**Autonomy tier:** 🟡 Yellow (no schema change, no auth boundary). Escalates to 🔴 Red if a migration turns out to be needed.

---

### 4.2 · P0-2 — Stripe per-move payment gate

**Goals.** A customer pays per move and the case unlocks the paid tier. No revenue is possible until this ships.

**Spec — verified state.**
- 🔴 **Zero Stripe code in `backend/`.** A repo-wide grep returns one false positive ("urgency stripes" in `relocation_plan_view_schemas.py:67`).
- 🔴 **`POST /api/relopass/cases` does not exist.** The `/api/relopass` prefix does not exist at all.
- 🔴 **No webhook handler.** The only Stripe webhook is TypeScript reference code at `docs/stripe-relopass-package/03-backend/webhook-extension.ts` and `relopass-payments.routes.ts` — **spec artifacts in a Python backend, not wired to anything.**
- ✅ **The DB is ready.** `20260719000001_add_payment_to_cases.sql` adds `access_tier TEXT NOT NULL DEFAULT 'free' CHECK IN ('free','roadmap','essentials')` + index on `relocation_cases`; `20260719000002_create_case_addons.sql` creates `case_addons`. **No code reads or writes `access_tier`** — it appears only in migrations and docs.

So: the data model is applied and the spec is fully written. Everything between them is missing. **Port the TypeScript reference to Python — do not re-architect it.**

**Plan.**
1. `POST /api/relopass/cases` — create a case at `access_tier='free'`. Register in **both** `backend/main.py` and `backend/app/main.py` (§2.1).
2. Checkout session creation, priced per move, `case_id` in metadata.
3. Webhook handler: verify the Stripe signature, handle `checkout.session.completed`, flip `access_tier` `free → roadmap|essentials`. **Must be idempotent** — Stripe retries.
4. Enforce the gate on read: the roadmap/essentials surfaces check `access_tier` server-side. Never gate in the frontend alone.
5. `case_addons` write path for add-on purchases.
6. Secrets via env only (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`). Never commit keys; never log the payload raw.

**Metrics.** Successful checkout → `access_tier` flip within 5s, ≥99%. Duplicate webhook deliveries produce exactly one flip. Zero paid surfaces reachable at `access_tier='free'`.

**Validation.** Stripe CLI replay against a local webhook, including a **duplicate delivery** and an **invalid-signature** case. `pytest` covering the idempotency path. A test asserting a `free` case receives 402/403 on a paid surface. Manual test-mode purchase end-to-end.

**Autonomy tier:** 🔴 **Red — full human gate.** Money movement + secrets + external service. Never auto-merge.

---

### 4.3 · P0-3 — QA the existing RFQ loop

**Goals.** Establish what actually works in the RFQ layer before anyone writes new RFQ code. It was previously reported non-functional; it is in fact fully built, so the first deliverable is a truthful defect list, not a rebuild.

**Spec — what exists.** HR/employee creates an RFQ (`hr_rfq.py`, `ServicesRfqNew.tsx`) → recipients resolved (`rfq_recipient_mapping.py`) → magic link dispatched (`supplier_link_dispatch.py`, `supplier_jwt.py`) → supplier responds on a public page (`SupplierQuotePage.tsx`, `supplier_rfq.py`) → quotes evaluated (`rfq_evaluation_service.py`) → employee views (`employee_quotes.py`, `QuoteRequestPage.tsx`). Six migrations; existing tests cover payer validation, email injection, magic links, dispatch.

**Plan.**
1. Run the existing suite: `cd backend && pytest -k rfq` and `-k supplier`. Record failures.
2. Walk the loop manually on a test-drive case, on corridor **FR_NO**, campaign `qa-rfq-01` (never `insead-2026`).
3. For each break, record: layer (UI / API / data), reproduction, and whether it blocks the loop or degrades it.
4. **Security-review the magic link specifically** — it is an unauthenticated public surface. Confirm token expiry, single-use or scoped reuse, and that a supplier token cannot read another supplier's quote or any case PII beyond the brief.
5. Only then propose fixes.

**Metrics.** RFQ loop completion rate manual: unknown → measured. `pytest -k rfq` pass rate: unknown → 100%. Magic-link security findings: unknown → enumerated with severity.

**Validation.** A written defect list with reproductions, each filed to the Notion AI Work Queue with Layer + Autonomy Tier. Any cross-supplier data access finding is 🔴 Red and stops the release.

**Autonomy tier:** 🟢 Green for the QA pass; findings inherit their own tiers.

---

## 5. Edge-case suite to author

Author these as regression guards — several protect fixes that already shipped and could silently regress.

| # | Scenario | Guards |
|---|---|---|
| 1 | Non-EEA national, move date 3 weeks out | P1-4 critical permit warning fires top-of-roadmap |
| 2 | Over-cap selection with **no** mapped service | Fails loud, not a silent `no_cap_for_benefit_in_context` |
| 3 | Assignment created, **no policy screen ever opened** | **P0-1 core guard** — eager resolution, not lazy |
| 4 | Test-drive policy seed forced to fail | Emits a structured error, not a swallowed warning |
| 5 | Intake submitted with destination blank | Graceful prompt, not the F15 dead-end (regression guard) |
| 6 | HR publishes a policy twice rapidly | No 409, no stuck spinner (F7 regression guard) |
| 7 | Requirement with a move date in the past | Flags "already missed" rather than hiding it |
| 8 | Seniority cap boundary — Manager vs IC at the exact threshold | Off-by-one in cap comparison |
| 9 | Two concurrent cases, same employee | Case binding stays correct (F16 regression guard) |
| 10 | Stripe webhook delivered twice | Exactly one `access_tier` flip (P0-2) |
| 11 | Stripe webhook with an invalid signature | Rejected, nothing mutated |
| 12 | Paid surface requested at `access_tier='free'` | Server-side 402/403, not a frontend-only hide |
| 13 | Supplier magic-link token used after expiry | Rejected |
| 14 | Supplier token A requests quote B | Denied — cross-tenant guard |
| 15 | Country field: type into the pre-filled Nationality | Reproduces P1-5; must not become unrecoverable |
| 16 | Corridor with no authored content | Honest early-coverage state, not a thin roadmap presented as complete |

---

## 6. Decisions still needed from Romain

1. **Sequencing P0-2 vs P0-3.** Stripe unlocks revenue; the RFQ QA protects a feature you already paid to build. My read: run P0-3 first — it is one to two days of QA and may reveal that a headline feature is already shippable, which changes the pitch. Stripe is the larger, riskier build.
2. **What "done" means for P1-3 feasibility.** Full backward-pass scheduling with per-requirement lead times is a substantial engine change. A narrower version — flag only the non-EEA-under-6-weeks case (P1-4) — captures most of the demo value at a fraction of the cost.
3. **Corridor depth vs breadth.** Nine corridors exist but only FR_NO / NO_FR / IN_DE have dedicated tests. Deepening three beats thinning nine, if the sales motion is corridor-specific.
4. **P2-6 and P2-7** are marked fixed in our records but reported broken by Audos. Someone should reproduce both before either is scheduled.

---

## 7. Working conventions for contributors

- **System of record** is the Notion AI Work Queue (DB `3bc887c6-4d48-8089-8188-fcf2dc3edc1b`). Status flows `Needs Decomposition → Ready for AI → AI in Progress → Human Review → Done`.
- **Autonomy tiers:** 🟢 Green auto-advances · 🟡 Yellow self-validates with a 15% audit sample · 🔴 Red requires a human gate — always for migrations, RLS/auth/secrets, money, and external sends.
- **Branches:** `audit/stage-N-<slug>` for audit remediation; feature branches otherwise. One PR per stage.
- **Never test against the `insead-2026` campaign** — it is the live cohort dataset and has been contaminated and purged twice. Use a `qa-*` campaign and purge after.
- **Pin the corridor** in any QA run (`&corridor=FR_NO`). Randomised corridors made RUN 001 and RUN 002 incomparable.
- Every task should state its own **Goals → Spec → Plan → Metrics → Validation** before implementation starts.
