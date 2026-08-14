# Personal Relocation Data Sheet — Build Notes & Eval Results

> Stand-in for the PR description requested in the build spec. This workspace
> is edited through the Audos bridge (no GitHub repository is attached to this
> task run), so the deliverable is a **draft workspace change for Romain to
> review in App Studio**, not a git branch/PR. Nothing was published or
> deployed.

## What was built

A per-case, corridor-agnostic **Personal Relocation Data Sheet** inside the
Case Command app (new **Data Sheet** header tab), backed by a requirements DB
and the live case data model.

| Piece | Location |
|---|---|
| Requirements DB | New WorkspaceDB tables `requirement_entities` (corridor steps) + `requirement_facts` (per-step fields, with `category` + `professional_review_required` consult flags) |
| Seed fixture (≡ `supabase/seed-*.sql`) | `apps/case-command/datasheet-seed.ts` — idempotent loader keyed on unique `entity_id` / `fact_uid` / `case_reference`; seeds FR-NO (5 steps, 37 field rows), FR-DE eval fixture (3 steps, 10 field rows), and the golden case `FR-NO-2026-0081` |
| Type model | `lib/datasheet-types.ts` (`FieldSource`, `DataSheetFieldValue`, `DataSheetSection`, `PersonalRelocationDataSheet`) |
| Builder service | `lib/dataSheetBuilder.ts` — `buildDataSheet(caseId, corridor)`, `listDataSheetCases()`, `saveDataSheetFieldValue()` |
| UI | `apps/case-command/PersonalRelocationDataSheet.tsx`, wired into `apps/case-command/App.tsx` |

### Pre-fill / provenance logic (per field)

1. Field classified **CONSULT PROFESSIONAL** first (`professional_review_required`,
   `category` ∈ {tax, legal, social_security}, or the fallback fact-key list
   `tax_residency_status`, `social_security_determination`, `shadow_payroll`,
   `employer_contribution_rate`) → guidance text only, **no value lookup ever runs**.
2. Intake: `case_facts` rows with source `user_input` / `hr_system` /
   `authority_response`, then structured intake columns (`persons`,
   `person_identities`, `cases`) → badge `intake`, confidence 1.0.
3. Passport OCR: `case_facts` rows with source `document_parse` → badge
   `passport-ocr`, stored confidence (0.9 in the fixture, shown in the cell).
4. Prior form: facts from earlier cases of the same person (newest prior case
   wins) → badge `prior-form`, confidence 0.8.
5. Nothing found → blank + `NEEDS INPUT` with hint; inline edit saves a
   `user_input` case fact and the badge flips to `intake` on rebuild.
6. `case_facts` rows with source `inference` are **ignored** — inferred values
   are never presented as provided data.

Steps present in the requirements DB with no authored field list render a
single NEEDS INPUT placeholder row — fields are never invented.

## Eval results

### (a) FR→NO golden case (`FR-NO-2026-0081`, Jean Lefebvre)

- **All 5 sections render from the requirements DB** (D-Number, EEA
  Registration Police/UDI, Tax Card/Skattekort, Folkeregister, A1 Certificate)
  — zero hardcoded sections in the component.
- **Source tags**: intake ← person/case columns + `hr_system`/`user_input`
  facts (name, nationality, employer, org number, salary, move date, purpose);
  passport-ocr ← `document_parse` facts (date of birth, passport number,
  passport expiry — intentionally absent from intake in the fixture);
  prior-form ← facts on prior case `FR-NO-2023-0012` (home country address,
  civil status).
- **Auto-population**: 31 of 37 non-consult field rows resolve from
  intake+OCR+prior = **84% ≥ 70%**. The remaining 6 rows are genuine gaps
  (Norwegian address ×4 sections, employer confirmation letter, French
  employer name) and all show `NEEDS INPUT` with hints.
- **0 consult-professional fields auto-filled** — consult classification runs
  before any value lookup, so the 4 consult rows (tax residency, social
  security determination, shadow payroll, employer contribution rate) can
  never carry a value even when matching case data exists.
- **0 fabricated values** — every rendered value traces to a `cases`/`persons`/
  `person_identities` column or a `case_facts` row; the only transformation is
  deterministic date formatting and days→months unit annotation on
  `expected_duration_days`.

### (b) Second corridor — FR→DE

FR→DE step/field data did not exist, so the seed includes the required DB
fixture (3 steps — Anmeldung, Steuer-ID, statutory health insurance — with 10
field rows incl. one consult-professional tax-residency row). Selecting
corridor **FR → DE** in the Data Sheet view renders these sections **with no
code changes** — the component reads steps/fields purely from
`requirement_entities`/`requirement_facts` filtered by the corridor code.
German-specific fields (`german_address`, `insurance_provider`) have no case
data and correctly render as `NEEDS INPUT`; shared identity/employment keys
pre-fill from the same case data model.

### (c) Provenance audit

- No auto-fill of consult-professional: enforced structurally in
  `buildDataSheet` (classification precedes value resolution) and again in
  `saveDataSheetFieldValue` (rejects consult fact keys).
- No fabricated values: the builder has no default/derived value path — the
  only outputs are verbatim stored values or `null`.
- Every unmapped gap = NEEDS INPUT: the resolver's terminal branch; also
  covers steps with unauthored field lists via the placeholder row.

## Verification status & limitations

- All files passed the Audos bridge's publish-safety syntax gate on write.
  The change is a **draft** — it has not been published, so the seed loader
  (which runs in the app at first open of the Data Sheet tab) and the visual
  checks above are verified by construction/code review, not by a live
  browser run. Screenshots (full + sparse mode) could not be captured in this
  environment for the same reason — review via the draft preview link.
- Export PDF is a print-based placeholder (`window.print()`): no FormTemplate
  / PDF-overlay engine exists in this workspace to wire to. PDF-fill remains a
  downstream render step consuming the same data-sheet values.
- Guardrails respected: no hooks touched (relopass-create-case / checkout /
  access / webhook untouched), no vendor-research or prerender files touched,
  no form auto-submission anywhere, no legal/tax/SS determinations — consult
  items carry guidance text only.
