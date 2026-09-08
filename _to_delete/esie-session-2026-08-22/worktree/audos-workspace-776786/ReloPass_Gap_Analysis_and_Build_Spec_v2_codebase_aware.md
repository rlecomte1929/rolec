# ReloPass — Gap Analysis & Build Spec (v2, codebase-aware)

**Product:** ReloPass — Case Command
**Stage:** AUTHORING (building verified corridor content + engine capability), **not** ASSURANCE (regulated-lawyer sign-off, which gates sellability separately).
**Corridors in scope:** FR→NO (v0, seeded) and NO→FR (in authoring).
**Regulatory caveat (unchanged from v1):** ReloPass surfaces **sourced, situation-specific information**, never bespoke legal advice in ReloPass's own voice. The binding cross-corridor routing constraint is **France's Loi 71-1130** (consultation juridique = reserved activity). Any output that would cross into an individualised legal *determination* must be rendered as informational + routed to a regulated professional. Nothing in this spec clears the advice line — this is informational software only.

> **Why v2 exists:** v1 (`ReloPass_Gap_Analysis_and_Build_Spec.md`) was written before the UIM foundation cycle tasks landed. Those tasks already shipped a real UIM/EAV schema, a working Rule DSL engine, and a Case Intelligence UI. v1 proposed building several of these from scratch and inventing parallel tables (`corridor`, `corridor_requirement`, `case_requirement_status`). **v2 reconciles every gap against what already exists** so Claude Code extends the real code instead of duplicating it. Each gap now carries a **Codebase reconciliation** subsection classifying it as **ALREADY BUILT**, **PARTIALLY BUILT (extend)**, or **NET-NEW**, and maps every proposed field onto the real UIM tables.

---

## What already exists (do not rebuild)

The following shipped in the UIM foundation cycle. Reuse these; do **not** recreate them.

### Database — UIM / EAV schema
Real tables (PostgreSQL, Git-versioned knowledge base):

| Table | Role |
|---|---|
| `cases` | One row per relocation case (e.g. `GIQ-2024-FR-NO-00001`, Camille Dubois, FR→NO). Holds `move_date`. |
| `case_facts` | EAV rows — per-case attribute/value pairs (e.g. `arrival_date`, employee type, nationality). |
| `pathway_eligibility_rules` | Pathways with a JSONB `condition_tree` evaluated to confirm a case matches a pathway. |
| `obligations` | Canonical requirement definitions (the corridor knowledge). Carries responsible-party, category, flag_message, and the deadline 3-tuple. |
| `obligation_types` | Type/classification lookup for obligations. |
| `obligation_dependencies` | DAG edges between obligations (upstream → downstream). |
| `case_obligations` | Per-case instantiation of obligations with live status + computed due dates. |

### Engine — `apps/case-command/rule-engine.ts` (Deliverable 3)
A working Rule DSL execution engine that:
- Accepts a **Case ID**; loads `case_facts` + the pathway's JSONB `condition_tree`.
- **Evaluates the condition tree** to confirm pathway match.
- **Instantiates `case_obligations`** respecting `obligation_dependencies` DAG edges — blocked obligations start as `'blocked'`, not `'pending'`.
- **Computes `due_date`** from a deadline 3-tuple (`anchor_type` + `offset_days` vs `absolute_date`) anchored to `move_date` or an `arrival_date` CaseFact.
- Resolves `case.*` / `facts.*` / `destination.*` / `nationality.*` paths.
- Is **idempotent** — re-runs preserve completed history.
- Is stress-tested against `GIQ-2024-FR-NO-00001` → produces **6 `case_obligations`** with correct statuses and due dates.

### UI — Case Intelligence layer (Deliverable 4)
`apps/case-command/App.tsx` + `apps/case-command/case-obligations.ts`. The **Obligations tab** already renders:
- Status pills: `pending` / `in progress` / `blocked` / `completed`.
- Due date with red **"Xd overdue"** warning.
- Responsible party, category.
- `flag_message` highlighted in **teal**.
- Full DAG context — a blocked obligation shows **"Waiting on: [upstream]"** with the upstream's live status.
- **Theme tokens:** dark slate `#0b1620` / `#142430`, blue primary `#2a93e0`, teal accent `#38c6de`.

**Rule for Claude Code:** every gap below maps onto these tables, this engine file, and this UI. Do not introduce a parallel schema, a second engine, or a duplicate obligations renderer.

---

## Build Sequence (revised)

1. **Author NO→FR into the existing engine and confirm it renders in the existing Obligations tab.** (Gap 1) — this is a content + rules authoring job against `pathway_eligibility_rules` / `obligations` / `obligation_types` / `obligation_dependencies`, plus a seeded NO→FR case, NOT new infrastructure. Success = a NO→FR case runs through `rule-engine.ts` and shows correct obligations, due dates, and DAG context in `App.tsx`.
2. **Extend the engine's status model** for retrospective + positive states (Gap 3) — `red_late`, `confirmed`/`nothing_to_do`, past-dated anchors.
3. **Add `employer_absent` handling** (Gap 4) — responsible-party value + `employer_engaged` flag on `cases`, resolved in `rule-engine.ts`.
4. **Spend tracking** (Gap 2, net-new) against `cases` / `case_obligations`.
5. **Estimate Review** (Gap 5, net-new) against `cases` / `case_obligations`.
6. **Data hygiene / seed** (Gap 6, net-new) — canonicalise seed data across both corridors.
7. **End-to-end verification** (Gap 7, net-new) — deterministic-output regression across both corridors.

---

## Gap 1 — NO→FR corridor

**What v1 proposed:** new `corridor` and `corridor_requirement` tables holding 21 NO→FR requirement records across phases A (exit), B (employment), C (establishment), D (customs).

**Codebase reconciliation: NET-NEW CONTENT, NOT NEW SCHEMA.** The corridor knowledge model already exists. NO→FR is an **authoring** job into existing tables, following the exact shape of the seeded FR→NO Camille case (`GIQ-2024-FR-NO-00001`).

**Kill these proposed tables:**
- ❌ `corridor` → the corridor is identified by the pathway + case direction; no dedicated table needed. Direction/corridor is expressed via `pathway_eligibility_rules.condition_tree` (matching on `destination.*` and origin facts) and case fields.
- ❌ `corridor_requirement` → every requirement is an `obligations` row (canonical definition) instantiated per-case as `case_obligations`.

**Field mapping (v1 proposed column → existing column):**

| v1 `corridor_requirement` field | Maps onto |
|---|---|
| `phase` (A/B/C/D) | `obligations.category` (or `obligation_types` classification) — reuse the existing category field; add phase labels as category values (`exit`, `employment`, `establishment`, `customs`). |
| `requirement_name` / `description` | `obligations` name/description fields. |
| `responsible_party` | `obligations` responsible-party field (`employer` / `employee` / `both` — plus `employer_absent`, see Gap 4). |
| `non_obvious` flag + copy | `obligations.flag_message` (rendered teal in the Obligations tab). |
| deadline / timing | `obligations` deadline 3-tuple (`anchor_type` + `offset_days` vs `absolute_date`). NO→FR anchors on NO **exit** paperwork and FR **arrival_date** CaseFact. |
| dependency ("blocked until X done") | `obligation_dependencies` DAG edge (upstream obligation id → this obligation id). |
| corridor eligibility ("applies to NO→FR, EEA national") | a `pathway_eligibility_rules` row with a JSONB `condition_tree`. |

**Authoring content (keep the 21 records, express as rows):**
- **Phase A — NO exit:** deregistration from Folkeregisteret, tax exit / final skattemelding trigger, `flyttemelding` (moving notice), NO customs export / transfer-of-residence paperwork (gates the FR customs import relief — DAG edge into Phase D).
- **Phase B — employment / cross-border:** where the mover **keeps a Norwegian employer**, EEA Reg. 883/2004 shifts social security to France → resurfaces **employer** obligations the company may not know it has (this is exactly the NO→FR validation-case learning). Author these as `responsible_party = employer` (or `employer_absent`, Gap 4).
- **Phase C — FR establishment:** for a French national entering France, immigration is **trivial** → author as `nothing_to_do` / `confirmed` positive state (Gap 3), NOT an omitted requirement. Includes FR residence registration realities, French tax residency onset, social security affiliation (CPAM), bank/admin setup.
- **Phase D — FR customs:** household goods + vehicle import from Norway = a **customs import event** (EEA-is-not-EU trap). Transfer-of-residence relief is **gated on NO exit paperwork** → DAG edge from the Phase A NO customs-export obligation.

**Seed a NO→FR case** mirroring the Camille shape: a `cases` row (new case id, e.g. `GIQ-2024-NO-FR-00001`), `case_facts` (nationality = FR/NO/SE citizen, `arrival_date` in France, retains NO employer, already departed NO), and a matching pathway. This is also the **schema stress-test** that the FR→NO template survives the reverse direction (see Gap 3 and Gap 4 — the two structural gaps this case surfaced).

**Acceptance criteria:**
1. A NO→FR case runs through `rule-engine.ts` with **zero engine code changes** for the happy path (content-only), producing `case_obligations` covering all four phases.
2. The Obligations tab (`App.tsx`) renders the NO→FR obligations with correct status pills, due dates, responsible party, category, teal `flag_message`, and DAG "Waiting on:" context — using existing theme tokens.
3. No `corridor` or `corridor_requirement` table exists in the schema after this work.
4. The Phase D customs obligation shows a DAG dependency on the Phase A NO customs-export obligation.

**Test cases:**
- **T1.1:** Seed NO→FR case, run engine → assert obligation count and that each has a resolved `due_date` anchored to `arrival_date` or NO exit anchor.
- **T1.2:** Assert the customs-import obligation is `'blocked'` until the NO customs-export obligation is `'completed'` (DAG edge live in UI).
- **T1.3:** Assert `pathway_eligibility_rules.condition_tree` correctly matches the NO→FR EEA-national pathway and rejects a mismatched pathway.
- **T1.4:** Render check — screenshot/DOM assert the NO→FR case in the Obligations tab shows teal flag_message on the customs (EEA-not-EU) item.

---

## Gap 2 — Spend tracking

**What v1 proposed:** a spend/expense capture surface tied to the active case (aligned to the €150/employee/month expense-management revenue stream in the business model).

**Codebase reconciliation: NET-NEW**, but reference real tables — do not invent a case abstraction. Spend attaches to the existing `cases` row (and optionally to a `case_obligations` row when a cost is tied to a specific requirement, e.g. a permit fee).

**Design:**
- New table `case_spend` (or `case_expenses`): `id`, `case_id` (FK → `cases`), `case_obligation_id` (nullable FK → `case_obligations`), `amount`, `currency` (EUR/NOK — model handles EUR/NOK exposure), `category`, `incurred_on`, `responsible_party`, `note`.
- Surface in `apps/case-command/` as a **Spend tab** sibling to the Obligations tab, reusing the existing theme tokens (`#0b1620` / `#142430`, blue `#2a93e0`, teal `#38c6de`).
- Read-only rollup per case; no billing logic in v0 (per-move pricing, no subscription billing).

**Acceptance criteria:**
1. Spend rows persist against a `cases` id and optionally link to a `case_obligations` id.
2. Spend tab totals per case and per currency; no FX conversion invented (display both currencies distinctly).
3. Zero coupling to the rule engine's determinism — spend never alters obligation status or due dates.

**Test cases:**
- **T2.1:** Add spend linked to a case only → appears in case rollup.
- **T2.2:** Add spend linked to a specific `case_obligations` id → appears under that obligation and in the rollup.
- **T2.3:** Mixed EUR + NOK spend → totals shown per currency, not summed across currencies.

---

## Gap 3 — Retrospective flagging + `nothing_to_do`

**What v1 proposed:** a parallel `case_requirement_status` table to track per-case requirement state, plus retrospective ("already missed") flagging and a "no action needed" state.

**Codebase reconciliation: PARTIALLY BUILT (EXTEND the engine).** The engine already has `anchor_type` + `offset_days` deadline logic and a `'blocked'` status; `case_obligations` already holds per-case status. **Do NOT create `case_requirement_status`** — extend `case_obligations` and the status enum instead.

**Extensions:**
1. **Status enum → add two states** (extend the existing `pending / in_progress / blocked / completed` set):
   - `red_late` — the deadline window is **fully in the past and the obligation is not done**. This is the retrospective flag the NO→FR validation case surfaced (its mover already departed NO). Distinct from the existing amber "Xd overdue" (which flags a *tight or just-passed* window against a *future* move date); `red_late` is for windows that are wholly elapsed.
   - `confirmed` / `nothing_to_do` — a positive state meaning "evaluated, nothing required" (e.g. a French national's FR immigration step). This must **render as a resolved positive**, not be silently omitted — the relief moment depends on the user *seeing* that it was checked.
2. **Allow `anchor_date` in the past** — the engine currently anchors to `move_date` or `arrival_date` assuming a future/near window. Permit past-dated anchors so a case whose mover already departed computes correctly and yields `red_late` where appropriate. This is retrospective flagging: compare each requirement's window (anchor + offset) against **today (2026-07-14)**; wholly-past + not-done → `red_late`.
3. **`case_obligations` columns to add** (not a new table): whatever is needed to carry the resolved retrospective/positive state and the reason — e.g. `resolution_state` and `resolution_note`, or reuse the status column + a `flag_severity` (`amber` | `red` | `none`). Keep it on `case_obligations`.

**UI (extend the existing Obligations tab):**
- `red_late` → red pill + "window elapsed — Xd late" copy (distinct styling from amber "Xd overdue").
- `confirmed` / `nothing_to_do` → a calm positive pill (e.g. teal/green check, "Confirmed — no action needed"), so it reads as *checked*, not missing.

**Acceptance criteria:**
1. No `case_requirement_status` table exists; retrospective + positive state live on `case_obligations`.
2. A past-anchored obligation that is not done evaluates to `red_late` deterministically.
3. A `nothing_to_do` obligation renders as a visible positive in the Obligations tab.
4. Engine remains idempotent — re-running does not flip a `completed` history item to `red_late`.

**Test cases:**
- **T3.1:** NO→FR case with an elapsed Phase A window, not done → `red_late`, red pill "window elapsed".
- **T3.2:** French-national FR immigration step → `nothing_to_do`, positive pill visible.
- **T3.3:** Idempotency — run engine twice on a case with a completed obligation whose window is now past → stays `completed`, does not become `red_late`.
- **T3.4:** A future-dated tight window still yields the existing amber "Xd overdue", proving `red_late` and amber are distinct paths.

---

## Gap 4 — `employer_absent` (orphaned employer obligations)

**What v1 proposed:** logic to handle the case where the employer is not in the loop (the NO→FR validation case: individual self-relocating, retains NO employer, but no HR generalist / company engaged).

**Codebase reconciliation: NET-NEW but small.** The insight from the reverse-corridor stress test: an **empty HR/employer layer must not silently move employer obligations onto the employee** — they are *orphaned* (employer-owned, employer absent), which is a distinct state.

**Design:**
1. **Responsible-party value:** add `employer_absent` as a value in the existing responsible-party field on `obligations` / `case_obligations` (alongside `employer` / `employee` / `both`). This means "employer-owned, employer currently absent from the case."
2. **`cases.employer_engaged`** — a boolean flag on the `cases` table (default `true`). When `false`, the case has no engaged employer/HR layer.
3. **Resolution at generation time in `rule-engine.ts`:** when instantiating `case_obligations`, if `cases.employer_engaged = false`, obligations whose canonical `responsible_party = employer` are stamped `employer_absent` on the case obligation — **not** reassigned to the employee. Deterministic, no LLM.

**UI:** render `employer_absent` obligations with a clear "Employer-owned — no employer engaged" marker (reuse theme tokens), so the user sees these are owned by an absent party rather than theirs to complete or safe to ignore.

**Acceptance criteria:**
1. `employer_absent` is a valid responsible-party value end to end (schema → engine → UI).
2. With `employer_engaged = false`, employer obligations resolve to `employer_absent`, never to `employee`.
3. With `employer_engaged = true`, behaviour is unchanged (regression-safe against the FR→NO Camille case).

**Test cases:**
- **T4.1:** NO→FR validation case (`employer_engaged = false`) → NO-employer social-security/payroll obligations show `employer_absent`.
- **T4.2:** FR→NO Camille case (`employer_engaged = true`) → employer obligations still show `employer`; no regression.
- **T4.3:** Determinism — same inputs, 10 runs, identical responsible-party assignments.

---

## Gap 5 — Estimate Review

**What v1 proposed:** a review step over the generated case estimate (the obligation set + timeline) before it is treated as final, aligned to the milestone pricing (M1 Roadmap / Essentials / Standard / Premium).

**Codebase reconciliation: NET-NEW**, referencing real tables. The "estimate" is the set of `case_obligations` the engine produced for a `cases` row plus their computed due dates — not a new artifact type. Estimate Review is a **view + confirmation layer** over that output, in `apps/case-command/`.

**Design:**
- A **Review** view in `App.tsx` that presents the engine's generated `case_obligations` for a case as a reviewable estimate: full timeline, non-obvious flags, feasibility flags (amber/`red_late`), responsible-party split (incl. `employer_absent`), and any `nothing_to_do` positives.
- A lightweight **review state on `cases`** (e.g. `review_status`: `draft` | `reviewed`) — no parallel table.
- No pricing/billing engine in v0; if a monetary estimate is shown, it maps to the canonical milestone figures (M1 €800; Essentials €2,000 / Standard €3,600 / Premium €5,500 — Track B) as static reference, not computed billing.

**Acceptance criteria:**
1. Review view reads exclusively from `cases` + `case_obligations` (no duplicate estimate store).
2. Marking a case reviewed sets `cases.review_status` and does not mutate obligation determinism.
3. Feasibility + non-obvious flags visible in the review exactly as in the Obligations tab (shared rendering).

**Test cases:**
- **T5.1:** Generate a case → Review view lists all `case_obligations` with flags; `review_status = draft`.
- **T5.2:** Confirm review → `review_status = reviewed`; obligations unchanged.
- **T5.3:** A case containing a `red_late` and a `nothing_to_do` obligation shows both correctly in Review.

---

## Gap 6 — Data hygiene / seed

**Codebase reconciliation: NET-NEW.** Canonicalise seed data across both corridors so the engine's determinism is provable and demos are reproducible. Reference the real tables and the seeded Camille case.

**Design:**
- A single idempotent seed routine that (re)creates: the FR→NO pathway + obligations + dependencies + Camille case (`GIQ-2024-FR-NO-00001`), and the NO→FR pathway + obligations + dependencies + the new NO→FR validation case.
- Enforce referential hygiene: every `obligation_dependencies` edge references existing `obligations`; every `case_obligations` references a valid `cases` + `obligations`; every `pathway_eligibility_rules.condition_tree` references resolvable paths (`case.*` / `facts.*` / `destination.*` / `nationality.*`).
- Idempotent: re-seeding does not duplicate rows or clobber completed `case_obligations` history.

**Acceptance criteria:**
1. Fresh DB → run seed → both corridors present, both cases runnable.
2. Re-running seed is a no-op on existing rows (no duplicates, no history loss).
3. A validator reports zero dangling FKs and zero unresolvable condition_tree paths.

**Test cases:**
- **T6.1:** Seed twice → row counts identical after the second run.
- **T6.2:** FK/path validator passes on both corridors.
- **T6.3:** Camille case still yields its 6 `case_obligations` post-seed (no regression).

---

## Gap 7 — End-to-end verification

**Codebase reconciliation: NET-NEW.** Lock in the **definition of done**: identical inputs → identical structured output across 10 consecutive runs, now across **both** corridors and the new states.

**Design:**
- A verification harness that runs `rule-engine.ts` against each seeded case 10× and asserts byte-stable structured output (which obligations appear, statuses, due dates, responsible parties, flags).
- Cover the new capability: `red_late`, `confirmed`/`nothing_to_do`, past anchors (Gap 3); `employer_absent` (Gap 4); NO→FR content (Gap 1).
- Render-level check that the Obligations tab and Review view display the verified output faithfully (existing theme tokens).

**Acceptance criteria:**
1. 10 consecutive runs per corridor → identical output; no LLM variance in which requirements appear.
2. All new states covered by at least one assertion.
3. CI-style pass/fail summary per corridor.

**Test cases:**
- **T7.1:** FR→NO Camille — 10 runs, diff = empty; 6 obligations stable.
- **T7.2:** NO→FR validation case — 10 runs, diff = empty; includes a `red_late`, a `nothing_to_do`, and an `employer_absent`.
- **T7.3:** Perturb one `case_fact` (e.g. `arrival_date`) → output changes deterministically and consistently across 10 runs.

---

## Summary of table decisions

| v1 proposed | v2 decision |
|---|---|
| `corridor` table | ❌ killed — direction via pathway + case fields |
| `corridor_requirement` table | ❌ killed — use `obligations` + `case_obligations` + `obligation_dependencies` + `pathway_eligibility_rules` |
| `case_requirement_status` table | ❌ killed — extend `case_obligations` (status enum + resolution columns) |
| new engine | ❌ — extend `apps/case-command/rule-engine.ts` |
| new obligations UI | ❌ — extend `apps/case-command/App.tsx` + `case-obligations.ts` |
| `case_spend` (Gap 2) | ✅ net-new, FK → `cases` (+ optional `case_obligations`) |
| `cases.employer_engaged`, `employer_absent` value (Gap 4) | ✅ net-new columns/values on existing tables |
| `cases.review_status` (Gap 5) | ✅ net-new column on existing `cases` |
| seed routine (Gap 6), verification harness (Gap 7) | ✅ net-new tooling over existing tables/engine |

**Stage reminder:** everything above is **authoring**. None of it is sellable until the corresponding corridor clears **lawyer sign-off (assurance)**. NO→FR content authored here awaits France counsel sign-off before it can be offered — consistent with the "never sell a corridor that isn't built *and* assured" rule.
