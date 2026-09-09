# Multi-Country Datasheet Export — Methodology & Rebuild Context

> **What this is.** A fetch-once context bundle for a future Claude Code / Cursor session that
> will build ReloPass's country-agnostic **Personal Relocation Data Sheet** (the interactive,
> exportable "datasheet"). It fuses two things a single agent rarely sees together:
> (1) the **validated UX and methodology** that already exists in the Audos workspace
> (`audos-workspace-776786/`), and (2) **ReloPass's real production backend** that already
> renders a data sheet today. The job is to bring the workspace UX onto the production stack —
> **extend, don't duplicate.**
>
> - **Origin:** Audos "Multi-Country Datasheet Export Methodology" chat with Otto (workspace
>   `d0c29613-9cb5-4652-9c6a-494eeed352e5`), 2026-09-09.
> - **Author of this doc:** repo agent (Claude Code), reading the real workspace + product files.
> - **Status:** context/spec only — no production code was changed to produce it.

---

## 0. The one instruction that matters

**ReloPass ALREADY ships a data-sheet engine, and the Audos workspace ALREADY contains a
validated data-driven version of the prototype.** Do **not** build a new standalone app or a
new corridor data store. The rebuild is a *port of proven UX onto an existing backend*, plus a
repeatable authoring methodology for adding corridors.

Concretely, before writing code the implementing session MUST read:
- ReloPass product: `backend/app/services/data_sheet_pdf.py`, `backend/app/routers/cases_read.py`
  (data-sheet render + dossier export), `docs/form-autofill/FINDINGS.md` (the definitive
  current-state audit of the two form systems).
- Audos workspace (all in this repo under `audos-workspace-776786/`): `apps/FRNODataSheet/App.tsx`,
  `apps/CorridorDataSheetEngine/App.tsx`, `lib/dataSheetBuilder.ts`, `lib/datasheet-types.ts`,
  `apps/case-command/PersonalRelocationDataSheet.tsx`, `apps/case-command/datasheet-seed.ts`,
  `apps/case-command/rule-engine.ts`.

Your repo history has repeatedly paid for building a parallel system when one already existed
("the corridor engine already existed four times"). This datasheet has the same trap: there are
**already three generations of it in the workspace and a live one in production.** See §7
(anti-patterns) and §8 (source index) before starting.

---

## 1. What the user asked for (verbatim)

From the Audos chat, opening the "Multi-Country Datasheet Export Methodology" task with Otto:

> "I would like you to produce an exportable version of the Datasheet prototype that cursor could
> reproduce in ReloPass. I like the functionalities and the way it is built up. Build this to
> accomodate any country document requirement so that it is not limited to only norway. I approve
> the set up but let's be mindful that this will need to cover more than one country. Build a
> methodology so that for a given country and given series of requirements, this model can be
> rebuilt, adapted and filled automatically."
>
> "act as a product manager with full stack developer skills to fetch all necessary information
> and rebuild it through use of claude code and cursor."

**Decoded into requirements:**
1. Reproduce the FR→NO datasheet **functionality and layout** the user validated.
2. Make it **country-agnostic** — driven by data, not hardcoded to Norway.
3. Provide a **methodology**: given `(country/corridor, set of requirements)`, the sheet can be
   **rebuilt, adapted, and auto-filled**.
4. Ship it **exportable**.
5. Do it inside **ReloPass** (not as a throwaway Audos app).

**Decision taken with the product owner (2026-09-09):** frame the rebuild as *extending
ReloPass's existing data-sheet engine (System 1)*, not as a standalone port. Otto's staged Cursor
task (which proposed a new `apps/DocumentDataSheet/` + JSON files + localStorage) is **left staged
but NOT run** — it was written blind to the production backend (Otto could not read the private
repo) and would have created a fourth parallel implementation.

---

## 2. What already exists — Audos workspace side (the UX + methodology)

The workspace (`audos-workspace-776786/`, mirrored into this repo) holds a **three-stage
evolution** of the datasheet. All three are real files you can read now.

### 2.1 Stage 1 — the throwaway prototype (the thing the user "likes")
`audos-workspace-776786/apps/FRNODataSheet/App.tsx` (501 lines). Header literally says
*"THROWAWAY UX PROTOTYPE … hardcoded mock data, zero API calls."* This is the design the user
validated. Its shape:

- A `SectionDef` per **issuing authority / process step**; a `FieldDef` per row.
- **5 FR→NO sections:** (1) D-Number (Skatteetaten), (2) EEA Registration (Police/UDI),
  (3) Tax Card / Skattekort, (4) National Register / Folkeregister, (5) A1 Certificate
  (French CPAM/URSSAF).
- **Provenance badge per field** (`BadgeKind`): `intake` · `ocr` (passport-OCR) · `prior`
  (prior-form) · `input` (NEEDS INPUT) · `consult` (CONSULT PROFESSIONAL).
- **Honesty features that are the product's moat:**
  - **CONSULT PROFESSIONAL** fields carry guidance text and **never a value** (tax residency,
    contract type, social-security determination, shadow payroll).
  - **Full vs Sparse data mode** — sparse simulates "intake + OCR captured almost nothing"; every
    non-consult field falls back to NEEDS INPUT. *Missing values are never guessed.*
  - **`sessionGroup`** — D-number + Skattekort are flagged as completable in **one Skatteetaten
    portal session** (a non-obvious sequencing fact).
  - **Info boxes** explaining non-obvious realities (e.g. "the EEA certificate is issued BY the
    police at the appointment — it is not something you pre-fill"; "the A1 is a France-side
    process, not obtainable from any Norwegian authority").
  - Bilingual **EN ↔ NO** toggle; per-section progress dots; inline-edit for NEEDS INPUT rows;
    Print/Export (print-based; toast: "PDF export will be available in the production build").

### 2.2 Stage 2 — the first generalization (corridor-agnostic config)
`audos-workspace-776786/apps/CorridorDataSheetEngine/App.tsx` (769 lines). Also a throwaway
prototype, but it **factors the design into a typed `CorridorConfig`** — this is the closest
existing statement of "the model for any corridor":

- `CorridorConfig`: `corridorId`, `origin`/`destination` (name, countryCode, localLanguage),
  `movement_basis` (`EEA_FREE_MOVEMENT | THIRD_COUNTRY_PERMIT | BILATERAL`),
  `regulatoryBanners` (`moat-fact | warning`), `sections[]`, `consultProfessionalItems[]`.
- `Section`: `title{en,local}`, `authority{name,url}`, `channels[]`
  (`online-portal | in-person-appointment | fillable-pdf | automatic | employer-owned`),
  `portalNote`, `fields[]`.
- `Field`: `label{en,local}`, `value?`, `source`, `requiresOriginal?`,
  **`responsibleParty` (`employee | employer | both`)**, `slaNote?`, `employerActionNote?`.
- New UX over Stage 1: **corridor selector dropdown**, **Employee-view vs HR-view toggle**
  (HR view adds an annotations column: responsible-party chip, SLA, employer action),
  mobile-responsive layout, print CSS (two-column, page-break before CONSULT PROFESSIONAL),
  and an explicit **"UNVERIFIED — REQUIRES ROMAIN SIGN-OFF"** footer.
- Still hardcoded to one config (`CORRIDOR_CONFIGS = [FR_NO_CONFIG]`) with the comment
  *"Future corridors: add the config here — the shell picks it up automatically."*

### 2.3 Stage 3 — the live, data-driven engine (the real precedent to port)
This is the mature version and the one to mirror in ReloPass. It "replaces the mock data of both
prototypes with live case data" (its own header).

- **Types:** `audos-workspace-776786/lib/datasheet-types.ts` (97 lines) —
  `FieldSource` (`intake | passport_ocr | prior_form | needs_input | consult_professional`),
  `DataSheetFieldValue` (fact_key, label_en/no, source, value, **confidence 0–1**, hint,
  guidance, `is_consult_professional`, `is_placeholder`), `DataSheetSection`
  (step_id, step_name_en/no, authority, official_source_url, official_process_note, fields[]),
  `PersonalRelocationDataSheet` (case_ref, employee_name, corridor, corridor_label, locale,
  display_mode `full|sparse`, sections[], **completion_pct**, **needs_input_count**).
- **Builder:** `audos-workspace-776786/lib/dataSheetBuilder.ts` (412 lines) —
  `buildDataSheet(caseId, corridor)`:
  - reads corridor **steps** from `requirement_entities` and **fields** from `requirement_facts`
    (WorkspaceDB tables) — nothing hardcoded;
  - pre-fills each field from the case data model in a **strict provenance order:
    `intake → passport_ocr → prior_form`** (`resolveValue`, lines ~261–271);
  - **classifies CONSULT PROFESSIONAL *before* any value lookup** (`isConsult`, lines ~255–258)
    — driven by `professional_review_required`, `category ∈ {tax, legal, social_security}`, or a
    fallback fact-key list — so these fields can **never** carry a value;
  - **never invents a value**: an unmapped field returns blank with source `needs_input`; a step
    with no authored fields renders a `is_placeholder` NEEDS-INPUT stub instead of fabricated rows;
  - computes `completion_pct` and `needs_input_count` over non-consult fields;
  - `saveDataSheetFieldValue()` persists a user-entered value as a case fact
    (`source = user_input`) and **rejects consult-professional keys** even if called directly.
- **Production view:** `audos-workspace-776786/apps/case-command/PersonalRelocationDataSheet.tsx`
  (604 lines) — case picker + corridor picker, full/**sparse (= gaps only)**, EN/NO, inline-edit
  that persists and rebuilds, per-field provenance badge, "confidence NN% — verify against the
  original document" note when confidence < 1, and Export = browser print (comment:
  *"No PDF overlay engine exists in this workspace yet"*).
- **Seed / data authoring:** `audos-workspace-776786/apps/case-command/datasheet-seed.ts`
  (423 lines) — the workspace's "seed fixture." Loads `requirement_entities` + `requirement_facts`
  **idempotently** (unique `entity_id` / `fact_uid`, existing rows never mutated). It seeds **two
  corridors — FR-NO (5 steps) and FR-DE (3 steps)** — the FR-DE fixture existing specifically to
  prove the engine renders a second corridor **with zero code changes**. It also seeds a golden
  case (`FR-NO-2026-0081`, Jean Lefebvre) exercising every provenance path.

### 2.4 The deadline / obligations engine (separate from the datasheet)
The "auto-fill deadlines from the move date" behaviour the user wants lives in a **different**
module: `audos-workspace-776786/apps/case-command/rule-engine.ts` (1018 lines), the tested,
deterministic engine (consumed by `CorridorCheck.tsx`).

- `runCaseCheck(employeeType, anchorDate, today, corridorId)` → `CaseCheckResult`.
- Deadlines: each `RequirementRule` has `offsetWeeks` relative to an **anchor**
  (`move-date` or `contract-signed`); `actionByDate = anchor + offsetWeeks*7` (UTC-day integer
  math). Feasibility: **red** (window passed) / **amber** (< 7 days) / **green** / **confirmed**
  (a `confirmedClear` "nothing required" relief state).
- Employee-type gating via `appliesTo: 'all' | 'eea' | 'non-eea'`; returning-national is modelled
  as `eea` + `confirmedClear` steps.
- Chronological stable sort by `actionByDate` (authored order as tie-break) — **not** a
  topological sort; prerequisites are conveyed as `dependencyNote` prose + authored offsets.
- Corridors are hand-authored TS constants (`FRANCE_NORWAY_REQUIREMENTS`,
  `SPAIN_IRELAND_REQUIREMENTS`, `NORWAY_FRANCE_REQUIREMENTS`), registered in `CORRIDORS`.

> ⚠️ **The workspace `case-command/` directory contains FOUR non-integrated corridor models**
> (`rule-engine.ts` [canonical], the orphaned `france-norway-corridor.ts`, the standalone
> `case-obligations.ts` DAG resolver, and the datasheet's `requirement_entities`/`requirement_facts`).
> They share **no** type system or data source. Do not treat the workspace as one clean model —
> it is itself a warning about proliferation.

---

## 3. What already exists — ReloPass product side (System 1, LIVE)

ReloPass already renders a data sheet in production. This is the backend to extend. (Definitive
current-state audit: **`docs/form-autofill/FINDINGS.md`** — read it first; it documents that the
repo has **two** form systems and that the AcroForm one is largely disconnected.)

**System 1 — dossier / data-sheet (LIVE, primary):**
- **`form_templates`** — catalog of forms/sheets, one row per `(code, version)`; holds `fields`
  (jsonb), `trigger_rules` (jsonb: corridor identity — origin/destination/visa), `country`,
  `authority_code/name`, `category` (**`'data_sheet'`** for our sheets), and a **`sections`**
  array. Core DDL: `supabase/migrations/20260521000000_dossier_forms_core.sql`; sections added in
  `supabase/migrations/20261026000000_form_templates_sections.sql`.
- **`case_forms`** — per-case instance of a template (status drives the dossier badge).
- **`case_form_field_values`** — per-field value **with provenance** (`source`, `overridden`,
  `original_value`/`corrected_value` for the accuracy loop). This is the production analogue of
  the workspace's `case_facts`.
- **`dossier_packages`** — a named bundle of `case_forms` exported as one PDF (`form_ids` jsonb
  preserves order). **This is the existing multi-form export.**
- **Render:** `backend/app/services/data_sheet_pdf.py` → `render_data_sheet(...)` — sectioned by
  issuing authority, values carry provenance, unanswered fields kept visible as a checklist,
  never claims to be an official form, honours the `sections` layout + localised (EN/`nb`) labels.
  Called from `backend/app/routers/cases_read.py` when a form has no fillable original PDF
  (FR→NO, DE). Dossier bundle pdf/zip export also lives in `cases_read.py` (`_merge_pdfs`,
  cover + divider pages).
- **Prefill:** `backend/app/services/prefill_engine.py` → `run_prefill(...)` — source priority
  **intake_profile → contract → passport_ocr → prior_form** (the *same order* as the workspace
  builder; authority-lookup + AI-inference sources are stubs).
- **Admin authoring:** `backend/app/routers/admin_form_templates.py` — full CRUD for
  `form_templates` (fields, sections, accuracy report).
- **Already-seeded data sheets:** FR→NO (`RP-NO-DATASHEET`) in
  `supabase/migrations/20261015000000_seed_frno_data_sheet.sql`; FR→DE + DE→FR in
  `supabase/migrations/20261027000000_seed_de_fr_data_sheets.sql`. Their headers document *why*
  France's CERFA and Germany's VIDEX force the data-sheet shape over filled PDFs.

**Corridor knowledge & deadlines (production):**
- **`public.requirement_items`** (`backend/app/models.py:100`) — the canonical corridor
  requirements table (origin/destination, `nationality_classes`, `applies_to_*`, `non_obvious`,
  `timing`, `review_status`, citation/serving flags). This is where corridor facts live — the
  workspace's `requirement_entities`/`requirement_facts` are a prototype-local re-invention of it.
- **Corridor pathways:** `corridors/NO_FR/…` and `corridors/ES_IE/…` YAML (petitioning party,
  applicable rules, required documents, versioned pathways).
- **Deadline computation (read-time):** `backend/app/services/roadmap_lead_times.py`
  (bucketed `LEAD_TIME_DAYS`: visa 90 / family 60 / settlement 45 / civil 30) projected by
  `backend/app/services/roadmap_projection.py` (`project_tracks`). Responsible-party trichotomy
  incl. `EMPLOYER_ABSENT`: `backend/relopass/corridors/responsibility.py`.

**System 2 — AcroForm PDF prefill (BUILT, largely DISCONNECTED):** `form_field_mappings` +
`backend/app/services/form_prefill_service.py` + `backend/app/routers/immigration_forms.py`.
Per `FINDINGS.md` it has synthetic templates, only 2 corridors mapped, and no live UI caller.
**Field-tested and mostly rejected** for our corridors (DE has no fillable form; FR has exactly
one). Prefer the data-sheet model. Do not resurrect AcroForm auto-fill without re-reading
`FINDINGS.md` and `docs/form-autofill/ACROFORM-FEASIBILITY-DE-FR.md`.

---

## 4. The mapping — Audos concept → ReloPass System 1

The two stacks are **architecturally convergent**. Build the port against the right-hand column.

| Concept | Audos workspace | ReloPass production (target) |
|---|---|---|
| Corridor steps (per authority) | `requirement_entities` (seed) / `Section` in `CorridorConfig` | `form_templates` rows, `category='data_sheet'`, `sections[]` |
| Field definitions | `requirement_facts` (label, category, `professional_review_required`, hint, guidance) | `form_templates.fields` (jsonb) + per-field flags |
| Per-case field values + provenance | `case_facts` (EAV: source, confidence) | `case_form_field_values` (source, overridden, original/corrected) |
| Prefill resolution order | `buildDataSheet` → intake → passport_ocr → prior_form | `prefill_engine.run_prefill` → intake_profile → contract → passport_ocr → prior_form |
| Sheet assembly | `buildDataSheet(caseId, corridor)` | `run_prefill` + `render_data_sheet` |
| Render / export | `PersonalRelocationDataSheet.tsx` + browser print | `data_sheet_pdf.render_data_sheet` (single) + `dossier_packages` pdf/zip (bundle) |
| Corridor requirement knowledge | `requirement_entities`/`requirement_facts` (prototype-local) | `public.requirement_items` (canonical) + `corridors/*.yaml` |
| Move-date → deadlines | `rule-engine.ts` `offsetWeeks` (per-step) | `roadmap_lead_times` + `roadmap_projection` (bucketed, read-time) |
| Responsible party | `Owner`/`responsibleParty` incl. "Employer (not engaged)" | `backend/relopass/corridors/responsibility.py` incl. `EMPLOYER_ABSENT` |
| Consult-professional guardrail | `is_consult_professional` / `professional_review_required` | same posture; enforce in render + prefill |
| Seed / add a corridor | idempotent `datasheet-seed.ts` | a `supabase/migrations/*_seed_*_data_sheet.sql` (see §5) |

---

## 5. The methodology — build/adapt/fill a datasheet for ANY country

This is the "for a given country and series of requirements, rebuild/adapt/fill automatically"
recipe the user asked for. It combines Otto's authoring methodology with ReloPass's production
conventions.

### 5.1 Data model per corridor (author once)
A corridor datasheet = an ordered list of **process steps** (one per issuing authority/registration)
→ each step has **fields**. Author it as a `form_templates` row with `category='data_sheet'` and a
`sections` array; source the underlying facts from `requirement_items` for that corridor. Each
field needs:
- `fact_key` (stable), `label_en` + localised `label_<lang>`;
- `category` (identity | employment | address | tax | social_security | legal | healthcare | …);
- classification flags: `professional_review_required` (→ CONSULT PROFESSIONAL, never valued),
  `required`, `non_obvious`;
- `hint` (what the employee must enter) and/or `guidance` (what a regulated professional decides);
- optional `responsible_party`, `sla`/`timing`, `authority` + `official_source_url` +
  `official_process_note`, `requires_original`.

### 5.2 Content-generation methodology (Otto's, adapted)
For a new corridor's requirement content:
1. **5-pass LLM generation** — generate the requirement set 5 times from *different* prompt
   framings; take the **union**; any item appearing in **< 3 of 5 passes is flagged for review**
   (low confidence). PII must be masked before any LLM call (`backend/app/services/pii_masker.py`)
   per CLAUDE.md.
2. **Non-obvious framework** — for each "moat" fact, capture the four-part shape:
   `official_guidance` / `actual_reality` / `action_required` / `source`. (This matches the
   `candidate_beam` authoring-pass vocabulary already used for requirement authoring.)
3. **Lawyer / counsel sign-off checklist** before anything is served: cite an official source per
   fact; set `review_status`/verification appropriately; never mark verified/approved without the
   human gate.
4. **Land as candidates, promote through the human gate** — corridor facts enter via the
   Otto → staging → `requirement_items` pipeline (`scripts/import_otto_facts.py`), `status`
   pending/candidate, idempotent on the batch uid, `ON CONFLICT` never overwriting a reviewer's
   decision. See `docs/corridors/README.md` and the CLAUDE.md "Corridor requirement data" +
   "Research batch intake" sections.

### 5.3 Auto-fill (per case, at render time)
Run `prefill_engine.run_prefill` (intake_profile → contract → passport_ocr → prior_form), then
`render_data_sheet`. Invariants, enforced *before* value lookup:
- CONSULT PROFESSIONAL fields never receive a value;
- unmapped fields render as NEEDS INPUT (blank) — **never fabricate**;
- surface `confidence` and let the user correct (writes back to `case_form_field_values`).

### 5.4 Deadlines
Attach `actionByDate` to steps from the **production roadmap engine**
(`roadmap_lead_times` + `roadmap_projection`) using the case move date — do **not** re-implement
the workspace's per-step `offsetWeeks` unless product decides the finer granularity is worth a
schema change. If finer granularity is wanted, that is a deliberate extension to the roadmap
engine, not a new parallel engine.

### 5.5 Adding a corridor = the whole workflow
1. Land/verify the corridor's requirement facts in `requirement_items` (§5.2).
2. Author/seed the `form_templates` data-sheet row (steps + fields + sections) via a
   `supabase/migrations/*_seed_<corridor>_data_sheet.sql` — model it on
   `20261015000000_seed_frno_data_sheet.sql` and `20261027000000_seed_de_fr_data_sheets.sql`.
   Set `verification_status`/`review_status` honestly (representative vs verified).
3. The interactive datasheet UI and PDF export pick it up **with no code change** (data-driven) —
   exactly as the workspace's FR-DE fixture proves for its engine.

---

## 6. The UX / feature spec to reproduce (Employee + HR)

Port these validated features onto the ReloPass frontend (React SPA, `frontend/src/`;
antigravity component system; navy/teal per `DESIGN.md`). Each maps to a data source in §4.

- **Sections grouped by issuing authority**, each with authority name + official URL + a
  process note; ordered by step.
- **Provenance badge per field** (5 sources): intake · passport-OCR · prior-form ·
  **NEEDS INPUT** · **CONSULT PROFESSIONAL**. Show a confidence caption when < 1.
- **Full vs Sparse** view — sparse shows only the gaps (NEEDS INPUT + CONSULT PROFESSIONAL).
- **Bilingual** EN ↔ destination language.
- **Employee view vs HR view** — HR view adds an annotations column: responsible-party chip
  (employee/employer/both/**employer-not-engaged**), SLA, employer-action note.
- **Non-obvious "moat" callouts** (amber) and **regulatory banners** (moat-fact / warning),
  e.g. "D-number + skattekort in one Skatteetaten session"; "skattekort before first payroll or
  50% emergency withholding"; "A1 is a France-side process."
- **CONSULT PROFESSIONAL** items rendered as guidance, never a value; grouped/print page-break.
- **Move-date → computed deadlines** per step (from the roadmap engine).
- **Inline edit** of NEEDS INPUT fields → persists to `case_form_field_values`, re-renders.
- **Export**: PDF via `data_sheet_pdf.render_data_sheet` (single) and `dossier_packages`
  (bundle); optionally a CSV export (Otto's brief asked for CSV — browser-native Blob, no new dep).
- **Honesty footer**: "ReloPass prepares and organises your official process — it never submits
  forms on your behalf and never makes legal/tax/social-security determinations."

---

## 7. Anti-patterns — what NOT to do

- ❌ **Do not build `apps/DocumentDataSheet/` or a new JSON+`registry.ts`+localStorage app.**
  That is Otto's staged brief, written blind to production. It is left staged for reference and
  must not be run. Building it creates a *fourth* datasheet implementation.
- ❌ **Do not create new `requirement_entities` / `requirement_facts` / `corridor`/`corridor_*`
  tables.** Corridor knowledge is `public.requirement_items` (+ `corridors/*.yaml`). Extend it.
- ❌ **Do not re-implement a deadline engine.** Use `roadmap_lead_times` + `roadmap_projection`.
- ❌ **Do not resurrect AcroForm auto-fill** as the primary path — read `FINDINGS.md` first; the
  data-sheet model is the deliberate choice for corridors without a verified fillable form.
- ❌ **Do not let the sheet fabricate a value.** The blank NEEDS-INPUT state and the never-valued
  CONSULT PROFESSIONAL state are the product's whole trust story. A prefilled-but-blank official
  form carried to a consulate is the worst failure available (see the `data_sheet_pdf` history).
- ❌ **Do not make EU-AI-Act / "compliant" claims** anywhere in shipped copy (CLAUDE.md hard gate).
- ⚠️ **If you add any new table**, it needs RLS + a policy + `REVOKE ALL … FROM anon`, and any new
  router must be registered in **both** `backend/main.py` **and** `backend/app/main.py`
  (CLAUDE.md). Serving code must never reach an LLM at request time (serving/LLM isolation gate).

---

## 8. Source index (fetch these)

All paths are relative to the repo root. Workspace files are the **validated design**; product
files are the **backend to extend**; everything below was confirmed present on 2026-09-09.

### Audos workspace — the UX & data-driven precedent
| Path | Role |
|---|---|
| `audos-workspace-776786/apps/FRNODataSheet/App.tsx` | Stage-1 hardcoded FR→NO prototype (the validated design) |
| `audos-workspace-776786/apps/CorridorDataSheetEngine/App.tsx` | Stage-2 corridor-agnostic `CorridorConfig` + Employee/HR views |
| `audos-workspace-776786/lib/datasheet-types.ts` | Stage-3 type model |
| `audos-workspace-776786/lib/dataSheetBuilder.ts` | Stage-3 data-driven builder (`buildDataSheet`) |
| `audos-workspace-776786/apps/case-command/PersonalRelocationDataSheet.tsx` | Stage-3 production view |
| `audos-workspace-776786/apps/case-command/datasheet-seed.ts` | Idempotent seed of `requirement_entities`/`requirement_facts` (FR-NO + FR-DE) + golden case |
| `audos-workspace-776786/apps/case-command/rule-engine.ts` | Deterministic deadline/feasibility engine (move-date → deadlines) |

### ReloPass product — the backend to extend
| Path | Role |
|---|---|
| `docs/form-autofill/FINDINGS.md` | **Read first** — definitive audit of the two form systems |
| `backend/app/services/data_sheet_pdf.py` | `render_data_sheet()` — the live sectioned sheet |
| `backend/app/services/prefill_engine.py` | `run_prefill()` — provenance-ordered auto-fill |
| `backend/app/routers/cases_read.py` | data-sheet render + dossier pdf/zip export |
| `backend/app/routers/admin_form_templates.py` | admin authoring CRUD for `form_templates` |
| `backend/app/models.py:100` | `RequirementItem` (`public.requirement_items`) |
| `backend/app/services/roadmap_lead_times.py`, `roadmap_projection.py` | move-date → deadlines (read-time) |
| `backend/relopass/corridors/responsibility.py` | responsible-party incl. `EMPLOYER_ABSENT` |
| `corridors/NO_FR/…`, `corridors/ES_IE/…` | corridor pathway YAML |
| `supabase/migrations/20260521000000_dossier_forms_core.sql` | `form_templates`/`case_forms`/`case_form_field_values`/`dossier_packages` |
| `supabase/migrations/20261026000000_form_templates_sections.sql` | `sections` array on `form_templates` |
| `supabase/migrations/20261015000000_seed_frno_data_sheet.sql` | seeded FR→NO data sheet (`RP-NO-DATASHEET`) |
| `supabase/migrations/20261027000000_seed_de_fr_data_sheets.sql` | seeded FR→DE + DE→FR data sheets |

---

## 9. Appendix — Otto's staged brief (superseded, kept for reference)

Otto (Audos) staged a Cursor task **"Build Country-Agnostic Document DataSheet System (from FR-NO
prototype)"** on branch `fix/td-qa-services-batch-0719`. Its 7 steps: read the prototype →
`data/corridors/corridor.schema.ts` (TS schema) → `data/corridors/fr-no.json` → `es-ie.json`
skeleton (`lawyerVerified:false`) → `apps/DocumentDataSheet/App.tsx` (corridor selector, move-date
deadline auto-fill, employee-type filter, phase timeline, non-obvious amber callouts, localStorage
status, CSV export) → `data/corridors/registry.ts` → `docs/corridor-authoring-guide.md`
(5-pass generation, union, lawyer sign-off, non-obvious framework).

**Why superseded:** the brief was written *without repo access* (Otto could not fetch the private
repo) and is therefore blind to (a) the workspace's own Stage-3 data-driven engine and (b)
ReloPass System 1. Its JSON-file + localStorage design would create a fourth parallel
implementation. **The two genuinely reusable ideas — the `CorridorConfig`-style schema and the
5-pass/non-obvious authoring methodology — are folded into §5 and §6 above, retargeted onto
`form_templates`/`requirement_items`.** The draft is left staged (not run, not discarded) in the
Audos workspace for reference.
