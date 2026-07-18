# ReloPass — Gap Analysis & Build Spec

**Audience:** Claude Code (implementation), Romain Lecomte (owner)
**Status:** Definitive spec — closes the 7 gaps identified in the live-product audit of relopass.com against the ReloPass vision and the Audos demo.
**Prime directive for the implementer:** This product's entire value is *being reliably, verifiably right about one corridor at a time*. Content is **informational, sourced, and NOT counsel-assured**. France is the binding legal jurisdiction (Loi 71-1130): the engine surfaces sourced, situation-specific requirements — it never issues bespoke legal or tax advice in ReloPass's own voice. Anything that crosses into advice must render as "route to a regulated professional."

---

## 0. How to read this document

- **Canonical requirement shape** (used everywhere): every requirement carries five fields —
  `requirement` · `responsible_party` · `timing` (relative to the case anchor) · `feasibility_flag` · `source` (authoritative link).
- **Case anchor** is either a *future move date* (forward planning) or a *past departure date* (retrospective triage). The engine must support both. See Gap 3.
- Each gap below is written as an independent work package: **Rationale → Data model → UI/Screens → API → Acceptance criteria → Test cases.** They can be implemented in the order listed; Gaps 3 and 4 are engine-level and should land before Gap 1 content is authored so the corridor can use the new states.
- **Determinism is a hard requirement.** Given identical inputs, the requirement set and ordering must be identical across runs. The LLM explains; it never decides what requirements appear.

---

## 1. EXECUTIVE SUMMARY — the gap between what ReloPass demos and what it does today

ReloPass demos as a three-layer global-mobility operating system — an Employee layer that walks a relocating person through a personalized roadmap, an HR-ops command center that turns a policy document into enforceable benefit rules and tracks spend and risk, and an Admin layer that orchestrates content and audits AI decisions. The demo narrative promises the relief moment the whole product is built around: *"this thing knows things I don't"* — it surfaces the week-seven ambush in week one.

The live product today is a scaffold of that story, not the story itself. The screens exist across all three layers, but the substance that makes them trustworthy is thin or absent in seven specific places:

1. **The only real corridor is FR→NO.** The live product has no NO→FR corridor, even though a real person is mid-move on it and pulling the build. The engine can't produce a roadmap for the exact case we're trying to validate.
2. **Spend is demoed but not captured.** "Mobility Spend" in the command center and "cost-overrun" in Risk are display shells with no underlying per-case actuals, so they can never compare real spend against a policy cap.
3. **The engine assumes the future.** It can flag a window that is *about to* close, but not one that has *already* closed. For a mover who has already left the origin country, that means it silently misses exactly the ambushes it exists to catch — and it has no positive "confirmed: nothing required" state, so "nothing to do" reads as a blank rather than reassurance.
4. **Obligations get orphaned.** The responsible-party model is HR / employee / both. When a move is unsupported (no HR in the loop) but the *employer* still has structural obligations — as in the live NO→FR case — those obligations belong to no one and disappear from the roadmap.
5. **The second core anchor doesn't exist.** Estimate Review — entitlement vs. selection vs. out-of-pocket, shown *before* a vendor is committed — is described as a pillar and is not built.
6. **Test data pollutes the product.** `testco.com`, `emp_run_*` cases, and "Route not set" artifacts are visible in live views; there is no clean reference case to demo against.
7. **The employee journey is unverified end-to-end.** Case linking, roadmap rendering, `nothing_to_do` states, and notifications have never been walked through as one continuous flow, so it's unknown where the journey breaks.

**Bottom line:** the demo sells a *system of record that is reliably right*; the live product is a set of correct-looking surfaces that are not yet wired to real, correct, current data. This spec closes that gap for one real corridor (NO→FR) end-to-end, and upgrades the engine (retrospective flagging, employer-absent obligations, estimate review, spend capture) so the same closure repeats for every future corridor as a data-authoring job, not a rebuild.

---

## 2. CURRENT-STATE INVENTORY — what is genuinely built across the three layers

> This inventory reflects what the live product presents as built surfaces. Items marked **shell** render but are not backed by real, per-case data; items marked **built** carry real behavior. The implementer should verify each against the actual codebase before extending it and correct this inventory where reality differs.

### Employee layer
- **Intake wizard** — built. Collects employee profile and move parameters; entry point to the case.
- **Roadmap** — built (single-corridor). Renders a sequence of requirements for the FR→NO corridor. Does not yet support NO→FR, retrospective anchors, or the positive `nothing_to_do` state.
- **Tasks** — built. Actionable items derived from the roadmap.
- **Dossier** — built. Document/record container for the case.
- **Services** — built. Vendor/service surfacing.
- **Benefit comparison** — partial. Compares benefit options; not yet connected to a pre-commitment Estimate Review (see Gap 5).
- **Immigration Q&A** — built (LLM-assisted, explanation-only). Must remain explanation-only; never a requirements source.

### HR-ops layer
- **Command center** — built (dashboard shell). "Mobility Spend" tile is a **shell** — no real actuals (see Gap 2).
- **Company profile** — built.
- **Policy module** — built. Turns policy into structured benefit rules; the substrate Estimate Review must read from (Gap 5).
- **Risk** — built (shell for cost-overrun). Cost-overrun signal has no spend data behind it (see Gap 2).
- **Service providers** — built.
- **Preferred suppliers** — built.
- **AI-decisions audit** — built. Records/introspects engine and LLM decisions; must capture new engine states (Gaps 3, 4).
- **Requirements** — built (FR→NO). The corridor knowledge surface; target of Gap 1 authoring and Gaps 3/4 engine states.

### Admin layer
- **Feedback / work console** — built. Content orchestration + feedback triage; where corridor authoring, data hygiene (Gap 6), and reference-case seeding are operated.

---

## 3. THE 7 GAPS

---

### GAP 1 — Author the NO→FR corridor into the live requirements/roadmap engine

**Rationale.** A real person is relocating Oslo→Paris right now — a French national (also NO/SE citizen), keeping his Norwegian employer, already physically departed Norway, staying temporarily at his parents. He is pulling corridor #2 exactly as the demand-pull strategy intends, and NO→FR is the cheapest next build (reuses 40–60% of the FR→NO mapping). Authoring it does two jobs at once: it produces the roadmap that validates the product for this live case, and it stress-tests whether the FR→NO schema survives the reverse direction. This is the *authoring* stage only — sellability requires later lawyer sign-off (assurance); nothing here is counsel-assured.

**Corridor definition.**
- `corridor_id`: `NO_FR`
- `origin`: Norway (EEA, **not** EU customs union — load-bearing)
- `destination`: France (binding jurisdiction)
- `profile` for the reference/validation case: `citizenship: [FR, NO, SE]` (FR is operative for entry), `employment: retains_origin_employer`, `support: unsupported` (no HR in the loop), `anchor: past_departure_date`, `interim_housing: temporary_hosted` (staying with parents).

#### 1.1 Data-model changes

Add corridor content as versioned, source-linked rows (PostgreSQL-backed, Git-versioned knowledge base — per the moat strategy).

```
Table: corridor
  corridor_id            text PK            -- 'NO_FR'
  origin_country         text              -- ISO-2, 'NO'
  destination_country    text              -- 'FR'
  status                 enum(authoring, assured, retired)  -- 'authoring'
  is_customs_union_origin boolean          -- false for NO -> triggers customs phase
  version                int
  authored_at            timestamptz
  assured_at             timestamptz null   -- set only on lawyer sign-off

Table: requirement (canonical five fields + engine metadata)
  requirement_id         text PK
  corridor_id            text FK -> corridor
  phase                  enum(origin_exit, cross_border_employment, destination_establishment, goods_vehicle_customs)
  sequence               int                -- deterministic ordering key
  title                  text
  description            text
  responsible_party      enum(employee, employer, both, hr, employer_absent, none)  -- see Gap 4
  timing_rule            jsonb              -- { anchor: 'departure'|'move', offset_days, window_days, direction: 'before'|'after' }
  feasibility_default    enum(green, amber, red, nothing_to_do)  -- computed at runtime; this is the fallback
  is_non_obvious         boolean            -- drives visual "trap" flag
  source_url             text               -- authoritative link
  source_verified_at     timestamptz null   -- null while DRAFT/needs-verification
  applies_if             jsonb              -- profile predicate, e.g. { employment: 'retains_origin_employer' }
  depends_on             text[]             -- requirement_ids that gate this one
```

- Every NO→FR row seeds with `source_verified_at = null` (DRAFT / needs-source-verification) and `status = authoring`.
- `applies_if` lets one corridor serve multiple profiles deterministically (e.g. vehicle import only if `owns_vehicle: true`).
- `depends_on` encodes gating dependencies (e.g. proof-of-address gates CPAM and bank).

#### 1.2 The four-phase content to author (seed rows)

All items DRAFT / needs-source-verification. `RP` = responsible_party. Non-obvious traps marked ⚠.

**Phase A — Norway exit admin** (`origin_exit`) — reusable for anyone leaving Norway
- **A1** Report move abroad to Folkeregisteret (*flytting til utlandet*, via Skatteetaten). RP: employee. Timing: within ~8 days of departure (**verify**). ⚠ retrospective red if elapsed. src: skatteetaten.no
- **A2** Preserve BankID before deregistration. RP: employee. Timing: before A1 takes effect. ⚠ sequencing trap — deregistration can disable BankID still needed to file exit-year return. src: bank + skatteetaten.no
- **A3** Norwegian tax-residence cessation + exit-year return (+ possible *utflyttingsskatt* on latent share gains). RP: employee. Timing: spans departure → following tax year. src: skatteetaten.no/utflytting
- **A4** Cancel/settle *skattekort* + final settlement. RP: employee. Timing: around departure. src: skatteetaten.no
- **A5** End folketrygden (National Insurance) membership. RP: both (employee + employer input). Timing: around departure; must align with B1. ⚠ gap/overlap trap. src: nav.no / folketrygdloven
- **A6** End HELFO cover; handle EHIC. RP: employee. Timing: around departure. ⚠ ties to C1 coverage gap. src: helfo.no
- **A7** Preserve accrued NO pension rights (folketrygd preserved via EEA; private/occupational handled separately). RP: employee. Timing: no hard deadline. src: nav.no + EEA rules
- **A8** Notify NAV of any active benefits (*barnetrygd* etc.). RP: employee. Timing: around departure. `applies_if` receives benefits. src: nav.no
- **A9** Close/transition banking, insurance, lease, utilities; mail forwarding. RP: employee. Timing: around departure. Note: keep one NO bank account open until exit-year refund clears. src: —

**Phase B — Cross-border employment & social security** (`cross_border_employment`) — the heavy non-obvious layer
- **B1** Determine applicable social-security legislation (A1 / Reg. 883/2004). RP: both (employee + employer). Timing: before first French-resident payroll month. ⚠ default outcome = **France**, not Norway (permanent relocation = place-of-work rule; not a posting, no A1 exemption). Linchpin. src: nav.no + EEA coordination
- **B2** Norwegian employer's French social-contribution obligation: employer registers with **URSSAF** (*service firmes étrangères*) **OR** uses the **Art. 21, Reg. 987/2009** arrangement (employee remits on employer's behalf). RP: **employer_absent** (fallback employee). Timing: from first French-resident work month. ⚠ employer almost certainly unaware. src: urssaf.fr
- **B3** Permanent-establishment (PE) risk for the employer. RP: **employer_absent**. Timing: ongoing. ⚠ **information-only — route to employer's own tax advisor; ReloPass does NOT issue this as advice**. src: FR–NO tax treaty
- **B4** Governing labour law for work performed in France under a NO contract (Rome I / mandatory French provisions). RP: both. Timing: ongoing. ⚠ information-only, route to professional. src: —
- **B5** Income-tax split & treaty relief (FR-resident income for work in France taxable in France; treaty prevents double taxation in split year). RP: employee. Timing: first French declaration cycle. src: FR–NO treaty; impots.gouv.fr
- **B6** French withholding (*prélèvement à la source*) setup once B1/B2 resolve. RP: both. Timing: after B2. `depends_on: [B2]`. src: impots.gouv.fr

**Phase C — France establishment** (`destination_establishment`) — deliberately light (French citizen = right of return)
- **C0** Establish *justificatif de domicile*: since hosted temporarily — **attestation d'hébergement** from parent + parent's proof of address + proof of relationship. RP: employee. Timing: as early as possible. ⚠ **gating dependency** — `depends_on` for C1, C5, D2. src: service-public.fr
- **C1** Register with CPAM (via PUMA / as worker; S1 handoff from HELFO if applicable) for cover + *carte vitale*. RP: employee. Timing: within weeks of arrival. ⚠ **coverage-gap trap** between A6 (HELFO ends) and C1 (CPAM starts). `depends_on: [A6]`. src: ameli.fr
- **C2** Immigration / right to enter & reside. RP: none. Timing: n/a. ✅ **nothing_to_do** — French citizen, no visa/permit/registration. src: —
- **C3** Address / population registration. RP: none. Timing: n/a. ✅ **nothing_to_do** — France has no mandatory citizen address registry. src: —
- **C4** French tax registration (declare arrival, obtain *numéro fiscal*, first-year declaration). RP: employee. Timing: first declaration window after arrival. src: impots.gouv.fr
- **C5** Open a French bank account (salary, CPAM reimbursements, admin). RP: employee. Timing: early. `depends_on: [C0]`. src: —

**Phase D — Household goods & vehicle customs** (`goods_vehicle_customs`) — the EEA-is-not-EU-customs-union trap
- **D1** Household-goods import with transfer-of-residence relief (*franchise de déménagement*). RP: employee. Timing: relief generally claimed within 12 months of establishing FR residence (**verify**). ⚠ **Norway is EEA but NOT EU customs union** — goods are a customs import, not free circulation. Relief requires proof of >12 months prior NO residence + >6 months prior ownership; Phase A exit paperwork is the evidence that unlocks it. src: douane.gouv.fr
- **D2** Vehicle import (`applies_if owns_vehicle`). RP: employee. Timing: register within French deadline after arrival (**verify**). ⚠ customs clearance + possible VAT (waivable under relief), *quitus fiscal*, COC/conformity, then *carte grise* via ANTS. `depends_on: [C0]`. src: douane.gouv.fr + ants.gouv.fr

#### 1.3 UI / screens
- **Requirements (HR-ops)**: NO→FR appears as a selectable corridor; four phases render as grouped, ordered sections; non-obvious items carry a visible "trap" badge; DRAFT items carry a "needs source verification" badge and a visible `authoring` (not `assured`) corridor status banner.
- **Roadmap (Employee)**: renders the same requirement set for the case profile, ordered by `sequence`, phase-grouped, with per-item feasibility flag, responsible-party chip, timing text, and source link.

#### 1.4 API
- `GET /api/corridors` → list with status.
- `GET /api/corridors/NO_FR/requirements?profile=<profileId>` → deterministic, ordered requirement set with `applies_if` filtering applied.
- `POST /api/corridors/NO_FR/requirements` (admin) → author/update a requirement row (writes to Git-versioned KB).
- `PATCH /api/corridors/NO_FR/requirements/:id` (admin) → set `source_verified_at`, edit fields.

#### 1.5 Acceptance criteria
- Selecting NO→FR for the reference profile returns **all** Phase A–D items that pass `applies_if`, grouped by phase, ordered by `sequence`, identically across 10 consecutive runs (no LLM variance).
- Every item exposes all five canonical fields; DRAFT items show `source_verified_at = null` and a verification badge.
- `is_customs_union_origin = false` causes Phase D to render; a hypothetical EU-origin corridor with `true` would suppress it.
- C2 and C3 render as positive `nothing_to_do` (see Gap 3), not blanks.
- B2/B3 render with `employer_absent` responsible party (see Gap 4), not dropped.
- Corridor banner shows `authoring` and the product nowhere presents NO→FR as assured/sellable.

#### 1.6 Test cases
- **T1.1** Determinism: request requirements 10× → identical JSON (order + membership).
- **T1.2** Profile filter: `owns_vehicle: false` → D2 absent; `true` → D2 present.
- **T1.3** Dependency integrity: C1 lists `depends_on A6`; C5/D2 list `depends_on C0`; B6 lists `depends_on B2`.
- **T1.4** Customs toggle: flipping `is_customs_union_origin` suppresses/re-adds Phase D.
- **T1.5** Source discipline: any item with `source_verified_at = null` renders a verification badge and is excluded from any "assured" export.

---

### GAP 2 — Per-case spend / cost tracking (make Risk cost-overrun and command-center Mobility Spend real)

**Rationale.** Both surfaces demo as if they compare real spend to a policy cap; today they have no actuals behind them, so they can neither warn nor report. Per-case spend capture makes cost-overrun a real signal and Mobility Spend a real aggregate. (Note: for the live NO→FR validation case there is no company and no policy cap — spend capture must degrade gracefully to "tracked, no cap" rather than assume a cap exists.)

#### 2.1 Data-model changes
```
Table: case_spend_entry
  entry_id          text PK
  case_id           text FK
  category          enum(immigration, housing, shipping, vehicle, tax_advisory, travel, other)
  description       text
  amount            numeric(12,2)
  currency          text            -- 'NOK','EUR'; store native
  amount_eur        numeric(12,2)   -- normalized for aggregation
  fx_rate           numeric(12,6)   -- rate used; EUR/NOK base ~11.5
  incurred_on       date
  vendor_id         text null
  policy_line_id    text null       -- links to policy benefit rule if applicable
  created_by        text
  created_at        timestamptz

Table: policy_cap  (read from existing policy module where present)
  policy_line_id    text PK
  case_id           text FK
  category          enum(...)
  cap_amount_eur    numeric(12,2) null   -- null => no cap (unsupported move)
```

- Derived view `case_spend_summary(case_id)`: `actual_eur` per category + total, `cap_eur` per category + total, `variance_eur`, `overrun_flag boolean` (true only when a cap exists and actual > cap).

#### 2.2 UI / screens
- **Command center → Mobility Spend**: real aggregate across cases (sum `amount_eur`), per-corridor and per-case breakdown, "no cap set" state rendered explicitly (not €0).
- **Risk → cost-overrun**: per-case actual vs. cap with variance; overrun badge only when cap exists and is exceeded; "tracked, no cap" state when `cap_amount_eur` is null.
- **Case detail**: spend entry list + "add spend" form (amount, currency, category, date, optional vendor/policy line).

#### 2.3 API
- `POST /api/cases/:caseId/spend` → create entry (server computes `amount_eur`, `fx_rate`).
- `GET /api/cases/:caseId/spend` → entries + `case_spend_summary`.
- `GET /api/spend/summary?corridor=NO_FR` → aggregate for command center.

#### 2.4 Acceptance criteria
- Adding a NOK entry stores native amount + normalized `amount_eur` using a recorded `fx_rate`.
- Mobility Spend total equals the sum of `amount_eur` across all entries; adding an entry updates it.
- Cost-overrun badge appears **only** when a cap exists and actual > cap; when cap is null, the case shows "tracked, no cap" and never a false overrun.
- Removing all cases yields €0 / empty, never demo placeholder numbers.

#### 2.5 Test cases
- **T2.1** FX normalization: 10,000 NOK at rate 11.5 → 869.57 EUR (±0.01).
- **T2.2** Overrun true: cap €5,000, actuals €5,001 → overrun_flag true.
- **T2.3** No-cap path: cap null, actuals €9,999 → overrun_flag false, "tracked, no cap" shown.
- **T2.4** Aggregation: 3 entries across 2 cases → Mobility Spend = sum of the three `amount_eur`.

---

### GAP 3 — Retrospective flagging + first-class `nothing_to_do` positive state

**Rationale.** The engine can only reason about a future move date, so for a mover who has already departed (the live case) it cannot flag windows that have already closed — the exact ambush it exists to catch. Separately, "nothing to do" currently reads as an absence; for a returning citizen (C2, C3) the product must affirmatively say *"confirmed: nothing required"* so the user trusts the silence.

#### 3.1 Data-model / engine changes
- `case.anchor`: `{ type: 'move' | 'departure', date: date, in_past: boolean }`.
- Feasibility computation runs against `now` vs `timing_rule` resolved on the anchor:
  - Window fully in the future with comfortable lead → `green`.
  - Window open but tight (within `window_days`) → `amber`.
  - Window **already elapsed** (anchor in past, deadline passed) → `red_late` (new value; "red-because-late").
  - Requirement with `responsible_party = none` and `feasibility_default = nothing_to_do` → `nothing_to_do` (terminal positive state; never computed to red/amber).
- Extend `feasibility_flag` enum to: `green, amber, red, red_late, nothing_to_do`.
- Each computed flag carries `reason` text (e.g. "Folkeregisteret notification window (~8 days) elapsed 12 days ago") for the AI-decisions audit.

#### 3.2 UI / screens
- **Roadmap / Requirements**: `red_late` renders distinctly from `red` (e.g. "Overdue — window closed" vs "Critical — act now") with the elapsed-days reason.
- `nothing_to_do` renders as a positive confirmed chip (check + "Confirmed: nothing required for you") — visually reassuring, not greyed-out/empty.
- Retrospective cases surface a top-of-roadmap **triage summary**: count of `red_late` items first.

#### 3.3 API
- Requirement responses include `feasibility_flag`, `reason`, and `anchor_context` ({type, date, in_past, days_from_anchor}).
- `GET /api/cases/:caseId/triage` → ordered list, `red_late` first, then `red`, `amber`, `green`, with `nothing_to_do` grouped as "confirmed clear."

#### 3.4 Acceptance criteria
- With a past departure anchor, A1 (8-day window) where departure was >8 days ago computes `red_late` with an elapsed-days reason.
- C2/C3 always compute `nothing_to_do` regardless of anchor and never appear as red/amber.
- Triage summary lists `red_late` before all other states.
- AI-decisions audit records the `reason` for each computed flag.

#### 3.5 Test cases
- **T3.1** Departure = today − 12 days, A1 window 8 days → `red_late`, reason cites elapsed days.
- **T3.2** Departure = today + 30 days, A1 → `green`.
- **T3.3** Departure = today + 5 days, A1 window 8 days → `amber`.
- **T3.4** C2/C3 under both past and future anchors → `nothing_to_do` both times.
- **T3.5** Determinism: same anchor + profile → identical flags across 10 runs.

---

### GAP 4 — Responsible-party state: `employer_owned / employer_absent`

**Rationale.** In the live case the employer has real, structural obligations (B1, B2, B3) but is not in the loop — the move is "unsupported." Today's HR/employee/both model has nowhere to put these, so they get orphaned: the HR layer being empty does **not** move its obligations onto the employee. The engine must surface them as employer-owned even when no employer is participating.

#### 4.1 Data-model changes
- Extend `requirement.responsible_party` enum to include `employer_absent` (employer-owned, employer not participating) alongside existing `employee, employer, both, hr, none`.
- Add `case.employer_engaged boolean`. When false, requirements with `responsible_party in (employer, both)` that are employer-portioned render with an `employer_absent` treatment (surfaced + attributed to employer, with a fallback-actor note where the employee can act on the employer's behalf — e.g. B2 Art. 21).

#### 4.2 UI / screens
- Responsible-party chip renders a distinct **"Employer — not engaged"** style for `employer_absent`, with copy: "This is your employer's obligation. They may not know it exists. [why this matters]".
- Where a legal fallback exists (B2 Art. 21), show a secondary line: "You may be able to act on the employer's behalf."
- These items are **never hidden** just because `employer_engaged = false`.

#### 4.3 API
- Requirement responses include `responsible_party` (with `employer_absent`) and `fallback_actor` where defined.
- `GET /api/cases/:caseId/orphaned-obligations` → all `employer_absent` items for the case (the "surfaced, not orphaned" view).

#### 4.4 Acceptance criteria
- With `employer_engaged = false`, B1/B2/B3 appear with `employer_absent` treatment and are present in the roadmap and in `orphaned-obligations`.
- B2 shows the Art. 21 fallback-actor note; B3 shows information-only "route to advisor" and is not actionable-as-advice.
- Setting `employer_engaged = true` re-attributes B1/B2 to `employer`/`both` without dropping them.

#### 4.5 Test cases
- **T4.1** Unsupported case → `orphaned-obligations` returns B1, B2, B3.
- **T4.2** B2 carries `fallback_actor = employee` + Art. 21 note.
- **T4.3** B3 flagged information-only, route-to-professional, not marked actionable.
- **T4.4** Toggle `employer_engaged` true → B1/B2 reattributed, still present.

---

### GAP 5 — Estimate Review screen (the second core anchor)

**Rationale.** Estimate Review — showing the employee entitlement vs. their current selection vs. projected out-of-pocket, *before* committing to any vendor — is one of the two product pillars and does not exist live. It reads from the policy module (benefit rules) and vendor/service pricing and makes the money consequence legible before commitment.

#### 5.1 Data-model changes
```
Table: estimate
  estimate_id     text PK
  case_id         text FK
  status          enum(draft, reviewed, committed)
  created_at      timestamptz

Table: estimate_line
  line_id         text PK
  estimate_id     text FK
  benefit_category enum(...)         -- maps to policy rule category
  entitlement_eur numeric(12,2)      -- from policy_cap / benefit rule (0 if none)
  selected_option_id text null       -- chosen service/vendor option
  selected_cost_eur  numeric(12,2)   -- price of selection
  out_of_pocket_eur  numeric(12,2)   -- max(selected_cost - entitlement, 0)
```
- For the unsupported validation case (no policy), `entitlement_eur = 0` for all lines → out-of-pocket = full selected cost. The screen must handle "no entitlements" gracefully (it becomes a personal cost planner).

#### 5.2 UI / screens
- **Estimate Review (Employee)**: three-column per benefit category — **Entitled** | **Selected** | **Out of pocket** — with totals row; a clear "before you commit" framing; a **Commit** action that transitions status to `committed` (which is the point after which spend actuals in Gap 2 begin).
- Empty-entitlement state renders "No company entitlement — this is your personal estimate."

#### 5.3 API
- `POST /api/cases/:caseId/estimate` → create draft from policy + selections.
- `GET /api/cases/:caseId/estimate` → lines + totals (entitled, selected, out-of-pocket).
- `PATCH /api/estimate/:id/lines/:lineId` → change selection; recompute out-of-pocket.
- `POST /api/estimate/:id/commit` → set `committed`.

#### 5.4 Acceptance criteria
- Out-of-pocket per line = `max(selected_cost - entitlement, 0)`; totals sum correctly.
- With no policy, all entitlements = 0 and out-of-pocket = full selected cost; screen shows the personal-estimate state.
- Estimate is viewable and adjustable **before** commit; commit is an explicit, reversible-until-committed step.

#### 5.5 Test cases
- **T5.1** Entitlement €3,000, selection €4,200 → out-of-pocket €1,200.
- **T5.2** Entitlement €5,000, selection €3,000 → out-of-pocket €0 (never negative).
- **T5.3** No policy → all entitlements €0, out-of-pocket = selection totals, personal-estimate copy shown.
- **T5.4** Changing a selection recomputes that line + totals without page reload state loss.

---

### GAP 6 — Data hygiene: hide/archive test cases + seed one clean reference case

**Rationale.** `testco.com`, `emp_run_*` cases, and "Route not set" artifacts appear in live views, undermining the "reliably right / system of record" credibility the product sells. There must be a clean reference case to demo and validate against.

#### 6.1 Data-model changes
- Add `is_test boolean default false` and `archived_at timestamptz null` to `company`, `case`, and `employee` tables.
- Backfill: mark `is_test = true` where domain = `testco.com`, `case_id LIKE 'emp_run_%'`, or corridor/route is unset ("Route not set").

#### 6.2 UI / screens
- All live list/dashboard queries default to `is_test = false AND archived_at IS NULL`.
- Admin work console gains a "Show test/archived" toggle (off by default) and an archive action.
- Seed one **clean reference case**: the NO→FR validation case (French/NO/SE national, Oslo→Paris, retains NO employer, departed, hosted temporarily) as a non-test, fully-populated case using the Gap 1 corridor. Explicitly tagged as a **validation case, not a paying B2B customer** in a `case.classification` field (`validation | paying | test`) so it never contaminates financial reporting/aggregates.

#### 6.3 API
- `PATCH /api/cases/:id/archive`, `PATCH /api/cases/:id/flag-test`.
- All list endpoints accept `?includeTest=false` (default) / `true`.

#### 6.4 Acceptance criteria
- Default live views show zero `testco.com` / `emp_run_*` / "Route not set" artifacts.
- The seeded NO→FR reference case appears as a clean, non-test `validation` case with a full four-phase roadmap.
- Spend/Mobility aggregates exclude `is_test = true` and `classification = validation` from paying-customer metrics.

#### 6.5 Test cases
- **T6.1** Default case list → no test artifacts present.
- **T6.2** Toggle "Show test/archived" → test cases reappear.
- **T6.3** Reference case present, `classification = validation`, four phases render.
- **T6.4** Revenue/paying aggregates exclude the validation case.

---

### GAP 7 — Employee-journey verification end-to-end

**Rationale.** Case linking, roadmap rendering, `nothing_to_do` states, and notifications have never been exercised as one continuous flow, so it is unknown where the journey breaks. This gap is a verification harness + fixes for whatever it surfaces, run against the clean reference case from Gap 6 and the corridor from Gap 1.

#### 7.1 Scope of the end-to-end path
1. Intake wizard creates employee + case, links to company (or "no company" for the unsupported case).
2. Case links to corridor `NO_FR` and profile; roadmap renders all applicable requirements (Gap 1) with correct flags (Gap 3) and responsible-party states (Gap 4).
3. `nothing_to_do` items (C2, C3) render as positive confirmations.
4. Triage summary lists `red_late` items first for the past-departure anchor.
5. Notifications fire correctly and reduce (not add to) anxiety: each notification maps to a real requirement/flag, uses the calm employee-track tone, and never double-fires or fires for `nothing_to_do` items.
6. Estimate Review (Gap 5) reachable and consistent with the case.

#### 7.2 Data-model / instrumentation
- Add a lightweight `journey_event` log (`case_id`, `step`, `status`, `timestamp`, `detail`) to trace each stage and assert continuity.
- Notification records must carry `requirement_id` (nullable) so every employee-facing message is traceable to a cause; reject notifications with no cause in the employee track.

#### 7.3 UI / screens
- No new screens; this is verification. Fixes land in existing Employee-layer screens (roadmap, tasks, dossier, notifications) as defects are found.

#### 7.4 API
- `GET /api/cases/:caseId/journey` → ordered `journey_event` trace for QA.
- Existing endpoints from Gaps 1/3/4/5 are exercised; no new business endpoints.

#### 7.5 Acceptance criteria
- A single reference case can be walked intake → roadmap → tasks → estimate → notifications with no broken link, no empty-state-where-content-expected, and no `nothing_to_do` item mis-rendered as blank.
- Every employee-track notification maps to a `requirement_id` and a real flag; none fire for `nothing_to_do`; none double-fire.
- `red_late` items appear at the top of the employee's triage view for the past-departure anchor.
- Journey trace shows all six stages `status = ok` for the reference case.

#### 7.6 Test cases
- **T7.1** Intake → case created, linked to `NO_FR`, roadmap non-empty.
- **T7.2** C2/C3 render positive `nothing_to_do` in the employee UI (not blank).
- **T7.3** Notification audit: every sent notification has a non-null `requirement_id` and calm-tone copy; zero notifications for `nothing_to_do` items.
- **T7.4** Past-departure anchor → triage view shows `red_late` (A1, A5, B1) first.
- **T7.5** Journey trace endpoint returns six stages, all `ok`, for the reference case.
- **T7.6** No-company path: unsupported case completes the journey with `employer_absent` obligations visible (Gap 4) and Estimate Review in personal-estimate mode (Gap 5).

---

## 4. Cross-cutting non-negotiables (apply to every gap)

1. **Determinism over LLM variance.** Requirement membership and ordering are engine-computed; the LLM only explains. Definition of done: identical inputs → identical structured output across 10 consecutive runs.
2. **Source discipline.** Every requirement carries a `source_url`; DRAFT items (`source_verified_at = null`) are visibly flagged and excluded from any "assured" surface. The corridor stays `authoring` until lawyer sign-off flips it to `assured` — nothing here is sellable on the strength of this spec alone.
3. **Advice line.** Information-only for anything crossing into legal/tax advice (B3, B4): render "route to a regulated professional," never advice in ReloPass's voice. France (Loi 71-1130) is the binding jurisdiction.
4. **Two tones, never conflated.** HR-track surfaces = operational/ROI/credible. Employee-track surfaces = calm/specific/human, anxiety-reducing. Notifications especially (Gap 7).
5. **Validation-case integrity.** The NO→FR reference case is `classification = validation`, never counted as a paying customer in any financial aggregate.

## 5. Suggested build order
1. **Gap 3** (engine: retrospective flags + `nothing_to_do`) and **Gap 4** (employer_absent) — engine states the corridor depends on.
2. **Gap 1** (author NO→FR using the new states).
3. **Gap 6** (data hygiene + seed the clean reference case).
4. **Gap 2** (spend capture) and **Gap 5** (Estimate Review).
5. **Gap 7** (end-to-end verification against the reference case) — last, as it exercises all the above.
