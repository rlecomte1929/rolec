# ReloPass — Gap Analysis & Build Spec

**Audience:** Claude Code (implementation), Romain Lecomte (review)
**Purpose:** Close the gap between what ReloPass *demos* and what it *does today*, and author the NO→FR corridor against a real validation case.
**Status of this document:** Definitive build spec. Every corridor content item inside it is **DRAFT — informational, source-verification pending, NOT counsel-assured.** France is the binding jurisdiction (Loi 71-1130); ReloPass sits on the information/software side and must never render bespoke legal or tax advice in its own voice.
**Scope note:** The brief promised **7 gaps**; only **6** were specified. Gaps 1–6 are fully spec'd below. **Gap 7 is reserved** (see final section) pending Romain's input — candidate is immigration Q&A / advice-line regulatory routing.

---

## 1. EXECUTIVE SUMMARY — the demo-vs-reality gap

ReloPass demos as a three-layer global-mobility platform (Employee / HR-ops / Admin) with a corridor knowledge engine, cost governance, and an entitlement-vs-selection Estimate Review. In practice, the live product at relopass.com is a **generic, forward-looking, buyer-centric shell** with several load-bearing pieces either absent or non-functional:

1. **The engine has no NO→FR corridor.** The one corridor with a real person pulling it — a French/NO/SE national self-relocating Oslo→Paris while keeping his Norwegian employer, already physically departed — cannot be run. The demo implies "any corridor"; the product delivers none for this case.
2. **Cost governance is theatre.** Risk "cost-overrun" and the command-center "Mobility Spend" tiles render, but no spend is ever captured, so there are no actuals to compare against policy caps. The numbers are placeholders.
3. **The engine only reasons forward.** It assumes a future move date and produces lead-time countdowns. It cannot triage a move that already happened — cannot flag an elapsed window as *red-because-late*, and has no positive `nothing_to_do` state, so "confirmed: nothing required" renders as an empty/ambiguous blank.
4. **Obligations get orphaned.** Responsible party is limited to HR / employee / both. In an unsupported move, employer-owned obligations (A1/Reg. 883/2004, URSSAF/Art. 21, PE risk) have no owner in the model, so they silently disappear instead of being surfaced as unowned-but-real.
5. **Estimate Review — the second core anchor — does not exist as a real screen.** There is no place an employee sees entitlement vs selection vs out-of-pocket *before* committing to a vendor.
6. **The data is dirty.** Test fixtures (`testco.com`, `emp_run_*`, "Route not set") are visible in the live product, undermining credibility in exactly the demo path a prospect walks.

The through-line: **ReloPass demos the vision and ships the scaffold.** This spec closes the six specified gaps so the product does, for one real case, what it claims to do for all cases — and hardens the engine (retrospective flagging, employer-absent ownership) so the NO→FR authoring doubles as the schema stress-test that proves the FR→NO template survives the reverse direction.

**Guardrails that sit above every gap below:**
- **Regulatory line:** informational, sourced, situation-specific requirements only. Anything crossing into a personalised legal/tax *determination* is flagged and routed to a regulated professional — never authored as advice in ReloPass's voice. This is compelled in France (Loi 71-1130) and applied conservatively for Norway.
- **Built vs planned honesty:** this spec builds real features. Where an item depends on something not yet built, it is marked as a dependency, not assumed present.
- **Validation-case boundary:** the NO→FR case validates corridor knowledge, the cross-border-employment layer, the `nothing_to_do` rendering, and the customs trap. It does **not** validate the B2B buyer, pricing, or the HR layer (there is no company paying and no HR generalist in the loop). Do not let it leak into the financial model.

---

## 2. CURRENT-STATE INVENTORY — what is genuinely built across the three layers

Per the audit of relopass.com. "Built" = renders and functions with real data. "Shell" = renders but backed by placeholder/no data. "Absent" = not present.

### Employee layer
| Surface | State | Notes |
|---|---|---|
| Intake wizard | Built | Captures employee type + move date; forward-anchored only. |
| Roadmap | Built (shell for NO→FR) | Renders for existing corridor(s); no NO→FR content. |
| Tasks | Built | Task list derived from roadmap items. |
| Dossier | Built | Document store per case. |
| Services | Shell | Vendor/service surface; not the focus of v0. |
| Benefit comparison | Shell | Precursor to Estimate Review but not the entitlement-vs-selection-vs-out-of-pocket screen. |
| Immigration Q&A | Shell | LLM-backed Q&A; regulatory routing not enforced (candidate Gap 7). |

### HR-ops layer
| Surface | State | Notes |
|---|---|---|
| Command center | Shell | Includes a "Mobility Spend" tile with no real actuals feed. |
| Company profile | Built | Company metadata. |
| Policy module | Built | Policy-as-structured-data; benefit caps exist as fields. |
| Risk | Shell | "Cost-overrun" risk has no spend to evaluate against caps. |
| Service providers | Built | Directory of providers. |
| Preferred suppliers | Built | Company-scoped supplier preferences. |
| AI-decisions audit | Built | Log of AI-surfaced decisions. |
| Requirements | Built (engine) | The corridor requirement engine; forward-only, HR/employee/both ownership only. |

### Admin layer
| Surface | State | Notes |
|---|---|---|
| Feedback / work console | Built | Admin orchestration surface (owned by Romain). |

**Engine limitations that Gaps 1/3/4 depend on:** (a) requirement ownership enum lacks an employer-absent state; (b) anchor is a future move date with no retrospective/elapsed handling; (c) no first-class `nothing_to_do` positive state; (d) no spend/actuals data model.

---

## 3. THE GAPS

Each gap below carries: **rationale**, **feature description**, **data-model changes**, **UI / screens**, **API endpoints**, **acceptance criteria**, **test cases**. Field conventions for corridor content are the canonical five: `requirement`, `responsible_party`, `timing` (relative to anchor), `feasibility_flag`, `source_url`.

---

### GAP 1 — Author the NO→FR corridor into the live engine

**Rationale.** A real person is pulling NO→FR (French/NO/SE citizen, self-relocating Oslo→Paris, retains Norwegian employer, already departed, at parents temporarily). It is the cheapest next corridor (reuses ~40–60% of FR mapping) and doubles as the stress-test proving the FR→NO template survives reversal. Today the corridor does not exist in the engine, so the case cannot be run at all.

**Feature description.** Author NO→FR as a populated, corridor-agnostic data instance against the existing requirement engine — no bespoke code per corridor; a corridor is a data-authoring job. Four phases: (A) Norway exit admin; (B) cross-border employment & social security; (C) light France establishment for a returning citizen; (D) household-goods + vehicle customs trap (Norway is EEA but **not** in the EU customs union). Each item carries the canonical five fields. Items reference **D = departure date (in the past)** as anchor — this depends on Gap 3 (retrospective flagging) and Gap 4 (employer-absent ownership) being implemented.

**Data-model changes.**
- `corridors` row: `{ id, origin_country: 'NO', dest_country: 'FR', direction: 'NO->FR', status: 'authoring', assurance_state: 'draft_unverified', reuse_source_corridor: 'FR->NO' }`.
- `corridor_profiles`: profile keys for this corridor include `citizen_of_destination` (French national), `retains_foreign_employer` (bool), `already_departed` (bool). The engine keys requirements on `(corridor_id, profile)`.
- `requirements` rows (one per item below) with columns:
  `id, corridor_id, phase (A|B|C|D), title, requirement_text, responsible_party (enum incl. employer_absent — Gap 4), timing_rule (JSON: {relative_to:'departure', offset_days, window_days}), feasibility_flag (computed — Gap 3), source_url, source_verified (bool, default false), non_obvious (bool), advice_route (bool — true = route to regulated professional, render info-only), depends_on (requirement_id[])`.

**Authored content (DRAFT — every `source_verified=false`):**

*Phase A — Norway exit admin (reusable core for anyone leaving Norway)*
- **A1 Report move abroad to Folkeregisteret** (*flytting til utlandet*, via Skatteetaten) · him · within ~8 days of departure (VERIFY exact window) · red-because-late if D+8 elapsed · skatteetaten.no · non_obvious=false
- **A2 Preserve BankID before deregistration** · him · before A1 takes effect · sequencing trap · verify (bank + Skatteetaten) · non_obvious=true
- **A3 Tax-residence cessation + exit-year return + possible exit tax** (*utflyttingsskatt* on latent share gains) · him · spans D → following tax year · amber · skatteetaten.no · advice_route=true (personalised tax determination)
- **A4 Cancel/settle skattekort + final settlement** · him · ~D · amber · skatteetaten.no
- **A5 End folketrygden membership** · him (+ employer input) · ~D, must align with B1 · red (time-sensitive) · NAV/folketrygdloven
- **A6 End HELFO cover; handle EHIC** · him · ~D · amber (see C1 gap trap) · helfo.no
- **A7 Preserve accrued NO pension rights** · him · no hard deadline · green · NAV + EEA rules
- **A8 Notify NAV of active benefits** (barnetrygd etc., if any) · him · ~D · amber (conditional) · nav.no
- **A9 Close/transition banking, insurance, lease, utilities; keep ≥1 NO bank account until exit-year refund clears** · him · ~D · green · —

*Phase B — cross-border employment & social security (heavy, non-obvious — he keeps the NO employer)*
- **B1 Determine applicable social-security legislation (A1 / Reg. 883/2004)** · him + Norwegian employer · before first French-resident payroll month (likely already triggered) · red · default outcome = France (place-of-work; permanent relocation, not a posting) · NAV + EEA coordination · non_obvious=true
- **B2 Norwegian employer's French social-contribution obligation** — employer registers with URSSAF (*service firmes étrangères*) OR uses Art. 21 Reg. 987/2009 (employee remits on employer's behalf) · **employer_absent** (fallback: him) · from first FR work month · red · employer almost certainly unaware · urssaf.fr · non_obvious=true
- **B3 Permanent-establishment (PE) risk for the employer** · **employer_absent** · ongoing · info-only, advice_route=true (route to employer's tax advisor; NOT ReloPass voice) · FR–NO tax treaty
- **B4 Governing labour law** (Rome I / mandatory French provisions on work performed in France) · him + employer_absent · ongoing · amber, advice_route=true · —
- **B5 Income-tax split & treaty relief** · him · first FR declaration cycle after D · amber, advice_route=true · FR–NO double-tax treaty; impots.gouv.fr
- **B6 French prélèvement à la source setup** · him + payroll · after B2 · amber (depends on B2) · impots.gouv.fr

*Phase C — France establishment (light: French citizen = right of return)*
- **C0 Establish justificatif de domicile** — attestation d'hébergement from parent + parent's proof of address + proof of relationship · him (+ parent) · ASAP · gating dependency for C1/C5/D2 · service-public.fr · non_obvious=true
- **C1 Register with CPAM** (PUMA / as worker; S1 handoff from HELFO) for carte vitale · him · within weeks of D · red · coverage-gap trap between A6 (HELFO ends) and C1 (CPAM starts) · ameli.fr · depends_on=[A6]
- **C2 Immigration / right to enter & reside** · him · n/a · **nothing_to_do** (positive: "confirmed — nothing required", French citizen) · — · (Gap 3)
- **C3 Address / population registration** · him · n/a · **nothing_to_do** (France has no mandatory citizen address registry) · — · (Gap 3)
- **C4 French tax registration** (declare arrival, numéro fiscal, first-year declaration) · him · first declaration window after D · amber, advice_route=true · impots.gouv.fr
- **C5 Open French bank account** (salary, CPAM reimbursements) · him · early · amber (depends_on C0) · —

*Phase D — household goods & vehicle import (EEA-is-not-EU-customs trap — sharpest proof of thesis)*
- **D1 Household-goods import with transfer-of-residence relief** (*franchise de déménagement*) · him · claim generally within 12 months of establishing FR residence (VERIFY) · amber · Norway in EEA but NOT EU customs union → customs import, not free circulation; relief requires proof of >12mo prior NO residence + >6mo prior ownership; Phase A exit paperwork is the evidence · douane.gouv.fr · non_obvious=true
- **D2 Vehicle import** (if car owned) · him · register within FR deadline post-arrival (VERIFY) · red · customs clearance + possible VAT (waivable under relief), quitus fiscal, COC, then carte grise via ANTS; depends_on C0 · douane.gouv.fr + ants.gouv.fr · non_obvious=true

**API endpoints.**
- `POST /api/corridors` — create corridor (admin).
- `POST /api/corridors/{id}/requirements` — bulk-author requirements (admin).
- `GET /api/corridors/NO-FR/requirements?profile=...` — resolve requirement set for a profile.
- `POST /api/cases/{caseId}/run` — run engine for a case; returns ordered, flagged requirement list.

**Acceptance criteria.**
1. A case with profile `{citizen_of_destination:true, retains_foreign_employer:true, already_departed:true}` returns all Phase A–D items above, ordered by phase then timing.
2. Determinism: identical inputs → identical output across 10 consecutive runs (no LLM variance in *which* requirements appear; LLM used for explanation only).
3. Every item exposes all five canonical fields; `source_verified=false` renders a visible "unverified source" marker.
4. `advice_route=true` items render info-only with a "route to a regulated professional" affordance and no ReloPass-voice determination.
5. Authoring NO→FR required **zero** engine code changes beyond Gaps 3 & 4 (proves corridor = data job).

**Test cases.**
- T1.1 Run case → assert 27 requirements returned across phases A(9)/B(6)/C(6)/D(2)+… and every one has non-null five fields.
- T1.2 Flip `retains_foreign_employer=false` → assert B1–B6 employer items drop or re-own to `him` per rules; assert C/D unchanged.
- T1.3 Flip `citizen_of_destination=false` (non-EEA resident) → assert C2/C3 flip from `nothing_to_do` to real immigration items (guards against hardcoding the positive state).
- T1.4 Snapshot test: 10 runs byte-identical requirement ordering + IDs.

---

### GAP 2 — Per-case spend / cost tracking (make Risk & Mobility Spend real)

**Rationale.** Risk "cost-overrun" and command-center "Mobility Spend" are placeholders. Without captured actuals there is nothing to compare to policy caps, so governance is fiction. This is also the data source that later feeds cost-to-serve modeling.

**Feature description.** Capture spend line items per case, categorised, with amount + currency (EUR/NOK, FX-aware), attach to a policy benefit line where applicable, and compute actuals-vs-cap. Surface aggregates on the command center and drive the Risk cost-overrun rule off real numbers.

**Data-model changes.**
- `case_spend` table: `{ id, case_id, category (enum: shipping, flights, temp_housing, immigration, tax_advice, vehicle, misc), description, amount_minor (int), currency ('EUR'|'NOK'), fx_rate_to_eur, amount_eur_minor (computed), policy_benefit_id (nullable FK), vendor_id (nullable), incurred_at, created_by, source ('manual'|'invoice') }`.
- `policy_benefits` gains `cap_amount_eur_minor` (if not present).
- Materialised view `case_spend_rollup`: per case + per category totals in EUR, plus `cap_utilisation_pct = spend/cap`.

**UI / screens.**
- Employee/HR: "Spend" tab on a case — add line item (amount, currency, category, optional benefit link, optional receipt upload to dossier).
- HR command center: Mobility Spend tile reads `case_spend_rollup` (total EUR, top categories, # cases over cap).
- Risk screen: cost-overrun row per case = `cap_utilisation_pct` with amber ≥ 80%, red ≥ 100%.

**API endpoints.**
- `POST /api/cases/{id}/spend` · `GET /api/cases/{id}/spend` · `PATCH /api/spend/{id}` · `DELETE /api/spend/{id}`.
- `GET /api/companies/{id}/spend-rollup` (command center).
- `GET /api/cases/{id}/risk/cost-overrun`.

**Acceptance criteria.**
1. Adding a NOK line item stores `amount_eur_minor` using a stored `fx_rate_to_eur` (default base 11.5 EUR/NOK, overridable per line).
2. Mobility Spend tile total = sum of case rollups (no placeholder).
3. Cost-overrun flag flips amber at ≥80% and red at ≥100% of the linked benefit cap.
4. Spend with no linked benefit still counts toward case total but not toward any cap utilisation.

**Test cases.**
- T2.1 Add EUR 1,200 shipping against a EUR 1,000 cap → cost-overrun = red, utilisation 120%.
- T2.2 Add NOK 11,500 at rate 11.5 → stored 1,000 EUR.
- T2.3 Delete a line → rollup + risk flag recompute.
- T2.4 Two cases, one over cap → command center "# cases over cap" = 1.

---

### GAP 3 — Retrospective flagging + first-class `nothing_to_do`

**Rationale.** The friend already departed, so the engine must reason *backward*: elapsed windows are red-because-late, not amber-because-tight. And a returning citizen has genuine "nothing required" items — these must render as a reassuring positive, not a blank, or the product looks broken exactly where it should build trust.

**Feature description.** Generalise the anchor to support a past date, add an elapsed-window evaluation, and introduce a `nothing_to_do` feasibility state as a first-class positive ("Confirmed — nothing required").

**Data-model changes.**
- `cases.anchor_type` enum: `future_move_date | past_departure_date`; `cases.anchor_date`.
- `feasibility_flag` enum extended: `green | amber | red | red_late | nothing_to_do`.
- `requirements.timing_rule` interpreted against `anchor_date` regardless of past/future.

**Engine logic.**
- For each requirement with a deadline window `[anchor+offset, anchor+offset+window]`:
  - `today > window_end` → `red_late`.
  - `today within window` and tight (< configurable buffer) → `amber`; else `green`.
  - requirement flagged `nothing_required=true` → `nothing_to_do` (skip date math).

**UI / screens.**
- `red_late` renders distinct from `red` — copy: "This window has likely passed — act now / remediate," with a remediation note where one exists (e.g., A1 late filing).
- `nothing_to_do` renders as a positive checkmark card: "Confirmed — nothing required (French citizen: no visa/permit/registration)." Never a blank row.
- A top-of-case triage banner: count of `red_late` items surfaced first.

**API endpoints.**
- `POST /api/cases` accepts `anchor_type` + `anchor_date`.
- `GET /api/cases/{id}/triage` — items grouped by flag, `red_late` first.

**Acceptance criteria.**
1. With `anchor_type=past_departure_date` and D = today−30, A1 (8-day window) returns `red_late`.
2. C2/C3 return `nothing_to_do` with positive copy, never empty.
3. Switching a case anchor from future to past recomputes all flags without re-authoring content.
4. Triage endpoint orders `red_late` above `amber` above `green`/`nothing_to_do`.

**Test cases.**
- T3.1 D = today−3 → A1 = amber (within ~8-day window). D = today−30 → A1 = red_late.
- T3.2 Assert `nothing_to_do` payload includes `positive_message` and renders a check, not a blank.
- T3.3 Future-anchored FR→NO case still behaves exactly as before (no regression).
- T3.4 Triage ordering snapshot.

---

### GAP 4 — Responsible-party state: `employer_owned / employer_absent`

**Rationale.** In an unsupported move the employer still has obligations (A1/Reg. 883/2004, URSSAF/Art. 21, PE risk) — but nobody is acting on them. The current HR/employee/both enum has no home for these, so they vanish. An empty HR layer must **not** move obligations to the employee; it must surface them as unowned-but-real. This is the key three-layer-architecture finding.

**Feature description.** Add `employer_absent` (and `employer_owned` for the supported case) to the responsible-party enum. Items owned by an absent employer are surfaced in a dedicated "Employer obligations — not currently owned" section, visible to employee and (when present) HR, with an escalation/notify affordance.

**Data-model changes.**
- `responsible_party` enum: `employee | hr | both | employer_owned | employer_absent`.
- Optional `employer_participating` bool on the case; when false, `employer_owned` items render under the `employer_absent` treatment.

**UI / screens.**
- Distinct "Employer obligations" card group with an explicit orphaned-state banner: "These are the company's responsibility. Your company is not currently managing this move — here's what still needs to happen."
- Each item: "Notify employer" action (generates a shareable summary — ties to comms track).

**API endpoints.**
- `GET /api/cases/{id}/requirements?owner=employer_absent`.
- `POST /api/cases/{id}/requirements/{rid}/notify-employer` — returns a shareable brief (no advice in ReloPass voice for `advice_route` items).

**Acceptance criteria.**
1. B1–B4 render under "Employer obligations," never silently dropped and never re-owned to the employee.
2. With `employer_participating=true`, the same items render as `employer_owned` under HR without the orphaned banner.
3. `advice_route=true` employer items (B3 PE risk) render info-only + route-to-advisor.

**Test cases.**
- T4.1 Unsupported case → assert B1–B4 present with `employer_absent` and orphaned banner.
- T4.2 Toggle `employer_participating=true` → banner disappears, ownership = `employer_owned`.
- T4.3 Assert no employer item is ever auto-assigned to `employee`.

---

### GAP 5 — Estimate Review screen (the second core anchor)

**Rationale.** Estimate Review is a named core anchor and does not exist as a real screen. The employee must see entitlement vs selection vs out-of-pocket **before** committing to any vendor — this is where policy-as-data pays off and where employee anxiety is reduced by showing the money truth up front.

**Feature description.** A screen that, per benefit category, shows: **Entitlement** (from policy caps), **Selected** (chosen service/vendor + cost), **Out-of-pocket** (selected − entitlement, floored at 0), and a running total. Gated commitment: the employee confirms the estimate before any vendor booking is triggered.

**Data-model changes.**
- `estimate_lines`: `{ id, case_id, benefit_id, entitlement_eur_minor, selected_vendor_id, selected_cost_eur_minor, out_of_pocket_eur_minor (computed), status ('draft'|'confirmed') }`.
- `estimates`: `{ id, case_id, status, confirmed_at, total_entitlement, total_selected, total_oop }`.
- Vendor commitment blocked unless `estimates.status='confirmed'`.

**UI / screens.**
- Table: rows = benefit categories; columns = Entitlement | Selected (vendor) | Out-of-pocket. Footer totals. Out-of-pocket > 0 highlighted (not alarming — informative).
- Primary action "Confirm estimate" → locks lines, unlocks vendor commitment. Reused spend model (Gap 2) records actuals against confirmed estimate later.

**API endpoints.**
- `GET /api/cases/{id}/estimate` · `PATCH /api/cases/{id}/estimate/lines/{lid}` (select vendor/cost) · `POST /api/cases/{id}/estimate/confirm`.
- Vendor-commit endpoint checks estimate confirmed.

**Acceptance criteria.**
1. Out-of-pocket = max(0, selected − entitlement) per line; totals sum correctly.
2. Vendor commitment is blocked (409) until the estimate is confirmed.
3. Changing a selection before confirmation recomputes out-of-pocket live; after confirmation lines are locked.
4. Zero-entitlement benefit shows full selected cost as out-of-pocket.

**Test cases.**
- T5.1 Entitlement 2,000 / selected 2,500 → OOP 500.
- T5.2 Entitlement 2,000 / selected 1,500 → OOP 0 (not −500).
- T5.3 Attempt vendor commit pre-confirm → 409.
- T5.4 Confirm → lines locked; further PATCH → 423/409.

---

### GAP 6 — Data hygiene: hide/archive test fixtures, seed one clean reference case

**Rationale.** Test data (`testco.com`, `emp_run_*`, "Route not set") is visible in the live product on the exact path a prospect walks. It reads as broken and undermines the credibility the corridor knowledge is supposed to earn.

**Feature description.** Soft-archive (never hard-delete) all test fixtures so they disappear from default views but remain restorable for QA, and seed **one** clean, realistic reference case (the NO→FR validation case, sanitised — real corridor content, no PII) as the canonical demo path.

**Data-model changes.**
- Add `is_test` / `archived_at` to `companies`, `cases`, `employees`.
- Backfill: mark rows matching `email LIKE '%@testco.com'`, `id LIKE 'emp_run_%'`, or status literal `'Route not set'` as `is_test=true`.
- Default list queries filter `WHERE archived_at IS NULL AND is_test=false` unless an explicit `?includeTest=true` (admin only).

**UI / screens.**
- Admin work console gains a "Show archived/test" toggle.
- Seed one reference case: company "Reference SME (NO→FR)", one employee (synthetic, no real PII), NO→FR corridor run, anchor = past departure, showcasing `red_late` + `nothing_to_do` + employer-absent obligations + an Estimate Review with sample entitlements.

**API endpoints.**
- `POST /api/admin/fixtures/archive` (idempotent backfill).
- `POST /api/admin/seed/reference-case`.
- List endpoints honour `is_test`/`archived_at` filters.

**Acceptance criteria.**
1. No `testco.com`, `emp_run_*`, or "Route not set" appears in any non-admin default view.
2. Archived rows remain queryable with `?includeTest=true` (admin) — nothing is destroyed.
3. Exactly one clean reference case exists and renders end-to-end (roadmap → triage → estimate).
4. Re-running the archive job is idempotent (no duplicates, no errors).

**Test cases.**
- T6.1 GET default company list → assert zero rows match test patterns.
- T6.2 GET with `?includeTest=true` as admin → archived rows present.
- T6.3 Seed reference case → assert NO→FR run returns red_late + nothing_to_do + employer_absent items.
- T6.4 Run archive twice → identical result set (idempotent).

---

## GAP 7 — RESERVED (awaiting specification)

The brief promised 7 gaps; only 6 were provided. **Do not invent a seventh.** This section is a placeholder to be filled once Romain specifies it.

**Candidate (Otto's inference, unconfirmed):** *Immigration Q&A / advice-line regulatory routing.* The live Immigration Q&A is LLM-backed and does not enforce the regulatory line. Under Loi 71-1130 (France, binding) any personalised legal/tax *determination* is a reserved activity; ReloPass must classify a query as either **information** (answer with sourced requirements) or **determination** (refuse to advise in its own voice; route to a regulated professional). A build spec would add an atomic `ROUTE` classification on Q&A, an advice-route affordance, and an audit trail in AI-decisions. **This is a candidate only — confirm before building.**

---

## Cross-cutting implementation notes for Claude Code

- **Sequence:** Gap 3 (retrospective + nothing_to_do) and Gap 4 (employer_absent) are prerequisites for Gap 1 authoring to render correctly. Build 3 → 4 → 1, then 2 → 5 → 6.
- **Determinism first:** the requirement engine must be deterministic; LLM is explanation-only. Add the 10-run snapshot test (T1.4) to CI.
- **No advice in ReloPass voice:** enforce `advice_route` rendering globally; it is a compliance constraint, not a UI preference.
- **Source verification:** every authored item ships `source_verified=false` and renders an "unverified" marker until assurance (lawyer sign-off) clears it. Authoring ≠ assurance.
- **FX:** store amounts in minor units; EUR is the reporting currency; base EUR/NOK = 11.5, overridable per line.
