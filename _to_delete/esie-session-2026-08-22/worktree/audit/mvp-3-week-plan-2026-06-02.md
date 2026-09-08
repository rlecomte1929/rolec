# MVP 3-week ship plan — first paying customer (2026-06-02)

**Ship target:** ~2026-06-22 (3 weeks).
**Scope (confirmed):** First paying customer end-to-end · HR + Employee personas · DE + FR + GB corridors.
**Discipline:** strict-need only. Everything not on the critical path is deferred to post-MVP, including most of the audit follow-up backlog that's currently open.

---

## "Shipped" — operational definition

The customer-facing case lifecycle must complete reliably on prod for at least one paid case:

1. HR buyer signs a contract + pays (invoice OK; full Stripe self-serve NOT required for MVP — see §4).
2. HR self-configures company, policy tiers, and a first case in-product (manual onboarding touches are acceptable).
3. Employee receives invite, logs in, completes intake (W1) for destination ∈ {DE, FR, GB}.
4. Employee sees Estimate Review (W2) with policy cap vs spend, personal-cost callout.
5. Employee selects services; immigration workflow runs (HR creates case → employee uploads documents → HR monitors timeline).
6. Case progresses through the 6-stage immigration pipeline at least to `submitted` for ONE corridor (DE chosen as primary; FR + GB must not blow up).
7. HR sees a complete, accurate case history + status timeline.
8. Romain (manual support) can answer any customer question without prod read-only access fights.

Anything beyond this is post-MVP.

---

## §1 — Critical path (must-haves)

These items are **strictly required** to ship. They are organized by where they currently stand.

### A. Immigration workflow — the biggest open feature gate

| ID | What | Status (per Notion) | Risk |
|----|----|----|----|
| MVG-6A | HR — Create Immigration Case form | UI built | Need verification on prod |
| MVG-6B | Employee — Document Checklist view | UI built | Hard-coded doc lists per permit type; verify DE/FR/GB coverage |
| MVG-6C | HR — Status Timeline (6-stage pipeline) | UI built | Verify timeline events fire correctly |
| MVG-6D | Backend — POST/GET endpoints | **THE GATE — all 3 UIs call this** | If unfinished, MVP-6 isn't shippable |

**Action (Week 1):** verify MVG-6D landing state on `main`; if not complete, this is the highest-leverage backend work. Land it, smoke each endpoint, run a full HR-create → Employee-upload → HR-monitor cycle on prod for each corridor.

### B. End-to-end case flow — verify the existing surfaces hold up

The pieces exist but were built across many PRs. They need a single end-to-end smoke on prod, not just unit tests.

- HR command center (Stage 1–8 work — assumed working; recent #213 fix restored Provider Coordination panel).
- Employee intake wizard W1 (Stage 2 copy + statusLabel shipped via PR #119).
- Estimate Review W2 / PackageSummary (Stage 5 substantially closed via PR #124).
- Case assignment + assignment review (recent hotfix #190 fixed an active prod 500 — assignment surface has been fragile).
- Document upload + OCR pipeline (Stage 7 LLM hardening shipped via #196; passport extractor uses the wrapper).

**Action (Week 1–2):** run the `relopass-e2e-test` skill against prod and triage. Anything P0/P1 that breaks a step in §1.A above MUST be fixed before ship; anything else defers.

### C. Multi-corridor reliability

DE only just got migration-reconciled today (entry 10 in the drift inventory). FR + GB seeds were already passing replay but have not been recently exercised end-to-end.

**Action (Week 1):** synthetic case per corridor (DE, FR, GB), employee completes intake → estimate → starts immigration workflow. Any corridor that breaks: triage + fix or descope the corridor.

### D. Active prod findings — fix before ship

| Finding | Source | Impact | Required action |
|----|----|----|----|
| `hr_analytics` ambiguous dual-layer state | `audit/dual-layer-audit-followup.md` | May be silently 405 for HR | Investigate Week 1; fix if real |
| ~21 routers in dual-layer allowlist | PR #214 + `scripts/router_registration_allowlist.txt` | Debt list; some may surface as 405s | Audit each route for prod 405; fix the ones HR/employee touch |
| CI gap: RLS migration type checks | `audit/ci-gap-rls-migration-types.md` | Future migrations slip through (caused #194) | Wire migration apply against a real DB in CI — Week 2 |

### E. Billing + contract — the single biggest unsurfaced gap

Per Notion: **"BACKLOG · Stripe billing integration — Still backlog. Do not block..."**

Full Stripe self-serve is out of scope. The strict-need version for one paying customer:

1. A signed contract (DocuSign or similar) outside the product. 1–2 days of legal/admin.
2. A manual invoice flow: Stripe payment link emailed to the customer, marked paid in a CRM (Notion/spreadsheet OK). No subscription mgmt, no in-product billing UI.
3. A receipt/billing record stored against the company (Notion row OK for first customer — productize in v1.1).

**Action (Week 1, parallel to engineering):** stand up contract template + Stripe payment link + lightweight CRM row. ~2 days of non-engineering work.

### F. Customer onboarding playbook

For the first paying customer, manual touch is acceptable. The playbook captures the steps so the second customer is faster.

**Action (Week 2):** write a one-page playbook: pre-sale checklist → contract → invoice → company setup → first case → handover. Romain does the manual touches for customer #1.

### G. Demo + sales materials

`MVP-10 · Full demo run-through + record walkthrough video` is in the queue. This is the sales-enablement asset.

**Action (Week 2):** record the demo against the synthetic DE case from §1.C. Tighten until it lands.

---

## §2 — Hard-cut defer list (NOT in MVP)

Be ruthless. These are real work but they don't gate first paying customer.

**Audit follow-ups (most can wait):**
- A1-followup (deeper `init_db` DDL guard) · A3-followup (RLS allowlist triage) · A9-followup (155-file services tree migration) · B2-followup (174 raw HTML migration) · B5-followup (7 direct LLM call sites) · AUDIT-CUSTDISC (Stage 9 customer discovery wave) · brand-site rewrite · provider portal UX (C7) · all of Tier C.

**Migration replayability tail:**
- `audit/preview-red-tail-drainage-plan.md` entries 15/16/17 (uuid=text, orphans, invalid syntax) — **non-blocking for prod**; only blocks fresh-replay/Preview. Defer until post-MVP.

**Stale PRs:**
- #176 (Parker policy-gap adapter) · #209 (Parker integration A–J) · #189 + #183 (blocked on C1-08 `rce.contradictions`) · #195 (PDF coord mapper — already merged) — none of these block the customer flow. Resolve post-ship.

**Feature work:**
- Admin CMS productization · Stripe self-serve · Subscription/usage-based billing · AI assistant deep features · Multi-language i18n · Provider portal UX completion · Webhook signature verification (SEC-8) · OpenAPI spec publication.

**Polish:**
- P2/P3 items from every expert lens in `audit/02-expert-*.md` · skip-link / live regions / autocomplete (A11Y P2) · ECB FX date stamping + multiplier transparency (Stage 5 P2 follow-ups).

---

## §3 — Week-by-week execution

### Week 1 (Jun 2–8) — Feature gate + corridor verification

- **MVG-6D backend verification + completion** (highest leverage). Run a real HR-create → Employee-upload → HR-status cycle on prod.
- **Multi-corridor smoke:** synthetic case per DE, FR, GB through intake → estimate → immigration kickoff. Fix or descope any broken corridor.
- **`hr_analytics` triage + fix** if confirmed broken.
- **Contract + Stripe payment link** stood up (non-engineering work, parallel).
- **First-customer outreach** if not already in motion (this is the bottleneck for "first paying customer" — engineering can be perfect and ship nothing if no one is signing).

**Exit criterion:** one synthetic case per corridor reaches `submitted` on prod without manual SQL intervention.

### Week 2 (Jun 9–15) — End-to-end hardening + sales prep

- **Full E2E test campaign** (`relopass-test-campaign` skill). Score the platform. Triage everything P0/P1 against the §1.A–D criteria.
- **Fix all P0 bugs surfaced.** P1 bugs: fix if they touch the critical path; defer otherwise.
- **MVP-10 demo recording** — record against the DE corridor.
- **Customer onboarding playbook** drafted.
- **CI gate for RLS migrations** wired (closes the `ci-gap-rls-migration-types.md` risk).
- **Begin parallel work** on whichever §1.D dual-layer prod findings remain.

**Exit criterion:** test campaign score ≥ green-ish (define threshold per `relopass-test-campaign` skill); demo records cleanly first take; playbook signed off.

### Week 3 (Jun 16–22) — Pre-sale checks + ship

- **Final E2E pass** + comparison against Week 2 baseline. No new P0 introduced.
- **Document/OCR reliability check** (passport extractor, contract extractor C1-05c) — at least 5 real docs per corridor.
- **Synthetic prod customer case** end-to-end from contract → invoice → company setup → first case → completion (one full dress rehearsal).
- **Customer #1 contract signed + invoice issued.**
- **Customer #1 onboarded** (manual touches OK).
- **Customer #1 case live** — milestone for MVP shipped.

**Exit criterion:** customer #1 has logged in, paid, and at least one employee case has been created with no platform-side regression in the post-deploy 48h.

---

## §4 — Risks + mitigation

| Risk | Likelihood | Impact | Mitigation |
|----|----|----|----|
| No first customer identified by Week 2 | High if unknown today | Ships product, no paying customer = no shipped MVP | If no LOI/intent today: outreach is the bottleneck, not engineering. Identify before Week 2. |
| Stripe billing absent | Confirmed (backlog) | High if MVP definition shifts | Lightweight invoice + payment link bypasses this for customer #1; productize post-MVP |
| MVG-6D backend incomplete | Unknown | Hard gate (3 UIs call it) | Week 1 priority; if missing, redirect all eng effort here |
| FR/GB corridor brittleness | Moderate (DE just stabilized today) | Could force corridor descope | Week 1 smoke; descope to DE-only if FR/GB fail and don't recover by Week 2 |
| New P0 bug surfaces in Week 3 | Moderate | Slip ship date | Reserve 2 days slack in Week 3; explicit go/no-go on Wednesday Jun 17 |
| Dual-layer routers cause 405s during customer demo | Low-moderate | Embarrassing, recoverable | Audit during Week 1 §1.D action |
| Customer support overload after ship | Moderate | Reputation hit | Playbook (§1.F) + Romain on-call for 2 weeks post-ship |

---

## §5 — Open questions / assumptions to verify

1. **Is the first paying customer identified?** If yes, what's their corridor and timeline? If no, sales is the bottleneck — engineering capacity reallocates to outreach support, not features.
2. **Does the first customer require a specific integration** (SSO, HRIS sync, etc.)? If yes, scope it now or descope.
3. **MVG-6D current state** — needs verification today (Week 1 day 1).
4. **Contract template + invoice flow** — does this exist or needs to be built from scratch?
5. **Romain's bandwidth** — engineering + sales + support solo? Or is there sales/CS help?

If any of (1)/(2) shift, this plan changes materially. Treat answers as gating inputs to Week 1 day 1.

---

## §6 — What I'd say in one paragraph

The MVP is shippable in 3 weeks if (a) MVG-6D is completed or close-to-completed, (b) DE/FR/GB corridors all hold up in an end-to-end smoke, and (c) a first paying customer is identified or in active outreach. Engineering is in good shape — the audit hygiene work is done (Tier A closed, composite 7.4/10), the migration baseline is reconciled (today's milestone), and Stage 5 Estimate Review is on main. The biggest non-engineering gap is contract + invoice, which is a 2-day lightweight build, not a Stripe productization. The deferred list (Tier B/C follow-ups, Preview-red tail, Parker, all P2/P3 polish) stays deferred; ship clean, then drain. Hardest single risk is having no customer to actually pay; if that's not in motion, fix that this week before any more engineering.
