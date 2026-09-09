# Spec — Country-Agnostic Document Data Sheet & Form-Fill System

**Status:** Draft for review · **Author:** Product + full-stack · **Date:** 2026-09-09
**Source of requirement:** Audos task **#132277 "Document DataSheet — Country-Agnostic Rebuild"** (APP AGENT / Cursor, Opus 4.8, Complete), plus the `corridor-authoring-guide.md` Otto deliverable.
**Scope decision (Romain, this session):** the system covers **both** the on-screen agnostic data sheet **and** actual auto-fill of official forms / PDFs from case data.

---

## 0. TL;DR

Audos #132277 built a clean, data-driven **Personal Relocation Data Sheet**: one corridor-agnostic engine that lists the documents/steps an employee needs per corridor, auto-fills each field from case data with strict provenance (intake → passport OCR → prior form → *needs input*), refuses to fill regulated tax/legal/social-security determinations (a "consult a professional" firewall), flags the non-obvious traps, and exports.

**ReloPass already owns ~70% of this machinery** — but fragmented across four overlapping requirement/document models, three value stores, and two corridor systems, with no single unified sheet and no client-side export. This spec is therefore a **consolidation onto one model**, not a greenfield build, plus one genuinely new capability: **LLM-assisted field suggestion** feeding the existing PDF-fill path under the platform's safety gates.

**The one-line thesis:** make the Audos Data Sheet the single read-model that composes ReloPass's existing requirement catalog, corridor step-graphs, and per-field value store into one country-agnostic surface for Employee and HR, and wire it to the PDF-fill engine that already ships.

---

## 1. Why this matters (stakeholder context)

- **Employee**: today a relocating employee sees four different, partly-overlapping views (requirements list, checklist, documents screen, roadmap tracks) and none of them says "here is your D-number application, here is what we already know, here is exactly what you still have to type, here is the filled PDF." The Data Sheet is that single artifact. It is the thing the employee walks into a Skatteetaten / Bürgeramt appointment holding.
- **HR**: HR needs the same sheet with responsible-party and SLA annotations (who does what, by when) and needs to trust that ReloPass never invented a value or overstepped into tax/legal advice.
- **The moat / "why not just use ChatGPT"**: the value is not the list of documents. It is (a) provenance on every field so nothing is guessed, (b) the non-obvious traps a competent HR generalist does not know to check, and (c) the hard refusal to make regulated determinations. This spec preserves all three as first-class, enforced properties.
- **Now**: the corridor catalog is expanding (14 corridors in `corridors/`, more sourced weekly via Otto). Every new corridor currently means touching four frontend models and hand-seeding form mappings. A single agnostic engine turns "add a corridor" into "add data," which is the whole point of #132277.

---

## 2. The unifying model (from the Audos reference implementation)

The reference lives in the repo mirror at `audos-workspace-776786/`. Three files define the model:

- `lib/datasheet-types.ts` — the type model.
- `lib/dataSheetBuilder.ts` — the live-data builder (the fill engine).
- `apps/CorridorDataSheetEngine/App.tsx` — the corridor-agnostic UI (769 lines, design-validated).
- `apps/case-command/datasheet-seed.ts` — the concrete FR→NO + FR→DE data content and golden-case fixture.

### 2.1 Two data layers

| Layer | Reference tables | Role |
|---|---|---|
| **Requirements (corridor-agnostic content)** | `requirement_entities` (process steps: `entity_id`, `corridor`, `step_order`, `name`, `authority`, `official_source_url`, `official_process_note`) + `requirement_facts` (the fields each step needs: `fact_key`, `label`, `category`, `professional_review_required`, `hint`, `guidance`, `sort_order`) | Add a corridor = insert rows. Zero code change. |
| **Case (per person)** | `cases`, `persons`, `person_identities`, `case_facts` (EAV with `source` + `confidence`) | The data that fills the sheet. |

### 2.2 The fill engine (`buildDataSheet`) — the properties to preserve verbatim

1. **Join on `fact_key`.** Each requirement field carries a `fact_key` (`passport_number`, `norwegian_address`, `employer_name`, …). The builder resolves that key against case data. One captured value fills the same field across every step that needs it.
2. **Provenance resolution order:** structured intake / intake `case_facts` → `passport_ocr` (`document_parse`) → `prior_form` (facts from a prior case of the same person) → else **`needs_input`** (blank). `inference`-sourced facts are deliberately ignored — the sheet never surfaces a computed value as if it were provided.
3. **Never invent a value.** An unmapped field is returned blank with `source: needs_input` and a hint. This is the trust invariant.
4. **Consult-professional firewall.** A field is classified consult-professional **before any value lookup** when `professional_review_required === true` or `category ∈ {tax, legal, social_security}`. These fields *can never carry a value* — they render `guidance` only. In the FR→NO seed this covers `tax_residency_status`, `employer_contribution_rate`, `social_security_determination`, `shadow_payroll`.
5. **Completion math + edit persistence.** `completion_pct` and `needs_input_count` computed over non-consult fields; user edits to a `needs_input` field persist as a new `case_fact` (`source: user_input`) so they render as `intake` next build. Consult-professional keys are rejected at the write path too.

### 2.3 The UI model (`CorridorDataSheetEngine`)

Corridor-agnostic component driven by a typed config. Concepts to carry into ReloPass:

- **`MovementBasis`**: `EEA_FREE_MOVEMENT | THIRD_COUNTRY_PERMIT | BILATERAL` (drives the header + which steps show).
- **`Channel`** per step: `online-portal | in-person-appointment | fillable-pdf | automatic | employer-owned`. Note **`fillable-pdf` is already in the model** — it is the hook for the PDF-fill capability.
- **`ResponsibleParty`**: `employee | employer | both`, plus `slaNote` and `employerActionNote` (HR view only).
- **Source badges**: `intake`, `passport-ocr`, `prior-form`, `NEEDS INPUT`, `CONSULT PROFESSIONAL`.
- **Regulatory banners**: `moat-fact` (the non-obvious traps) and `warning` (hard deadlines, e.g. "skattekort before first payroll or 50% emergency withholding").
- **Toggles**: Employee/HR view, EN/local language, full/sparse data mode; per-section progress; print/export.

This is the target shape for the ReloPass DataSheet component.

---

## 3. Current state in ReloPass (verified 2026-09-09)

The build is largely **reuse**. The problem is fragmentation. Everything below was verified against the worktree.

### 3.1 Requirement / document data — FOUR overlapping models (the core problem)

| # | Model / DTO | Endpoint | Backing | Rendered by | Carries |
|---|---|---|---|---|---|
| 1 | `RequirementItemDTO` | `GET /api/cases/{id}/requirements` | `requirement_items` via `requirements_builder` + `rules_engine` | `components/requirements/RequirementList.tsx`, `features/platform-v2/dossier/DestinationRequirements.tsx` | pillar, title, **free-text `timing`**, `nonObvious`, citations, `verificationStatus`, `attestationStatus`, `legalReviewPending` |
| 2 | `ChecklistItem` / `ChecklistView` | `GET/POST /api/cases/{id}/requirements/checklist` | server-persisted completion | `features/cases/VisaChecklistCard.tsx` (only in `HrAssignmentReview`) | checkbox state, pillar, `timing`, `nonObvious`, progress |
| 3 | `DocumentItem` / `DocStatus` | `GET /api/cases/{id}/documents` | documents pipeline | `features/platform-v2/documents/DocumentsScreen.tsx` | `DocStatus` (`required…waived`), **typed `submission_deadline`/`expiry_date` (currently null-fed)**, urgency logic |
| 4 | `RoadmapV2Step` | `GET /api/cases/{id}/roadmap/tracks` | corridor step-graph | `features/platform-v2/roadmap/RoadmapScreen.tsx` + `CorridorAdvisories.tsx` | **typed `due_date` (+ `is_suggested`)**, `non_obvious`+note, `confidence_level`, `source_url`/`excerpt`, `doc_count`, `owner` |

Four shapes for one concept. Deadlines are free text in (1)/(2) and typed dates in (3)/(4). The DataSheet must pick or merge one canonical read-model — see §6.

### 3.2 Value / profile stores — THREE

| Store | Table | Contents | Provenance |
|---|---|---|---|
| Intake | `wizard_cases.draft_json` (+ columns `target_move_date`, `dest_country`, `purpose`) | employee name, employee type/`assignmentType`, family, profile | implicit |
| Immigration vault | `imm_employee_profiles` | passport OCR + self/HR-entered identity fields | **`field_sources` JSONB** (`ocr | self_entered | hr_provided`; hr_provided never overwritten by OCR) |
| Per-form values | `case_form_field_values` | per-field value for a `case_form` | **`filled_by ∈ {ai,system,employee,specialist,hr}`, `ai_confidence`, `reviewed`, `overridden`** |

`case_form_field_values` is the closest match to the Audos per-field provenance model and is the correct canonical value store for the Data Sheet (see §7).

### 3.3 Corridor / step systems — TWO, not merged

- **Destination-only requirement serving.** `requirements_builder.compute_case_requirements(case_id)` reads `wizard_cases`, resolves destination + purpose, fetches `requirement_items` filtered by `country_code` + `purpose` + `review_status = 'approved'`, then applies `rules_engine.apply_rules` for nationality/assignment-type gating. **Keyed by destination only** — origin is echoed but does not affect results. `requirement_items.id` is `varchar`, not uuid. Nationality classes: `OWN_NATIONAL | EU_EEA | THIRD_COUNTRY`, unknown fails safe to `THIRD_COUNTRY`.
- **Origin×destination step-graphs.** `corridors/<ID>/pathways/<PATHWAY>/vN.yaml` (14 corridors) carry a rich `step_graph`: `step_id`, `responsible_party`, `expected_duration_days`, `prerequisite_step_ids`, `non_obvious`(+note), `time_window_*`, `deadline_trigger`, `cite`. Loaded by `corridor_registry.load_corridor_profile`. This is exactly the step ordering/timing model the Data Sheet needs, and it is **not** currently joined to the requirement catalog.

### 3.4 Fill + PDF — EXISTS (this is the big de-risk)

- **Value resolution:** `backend/app/services/prefill_engine.py::run_prefill(case_form_id, case_uuid)` populates `case_form_field_values` with a source-priority ladder `intake_profile (0.99) → contract → banking → passport_ocr (0.9) → prior_form (0.95)`. **Never invents; never overrides `overridden=true`** (AIQ-1755). Called by `trigger_engine` on CaseForm creation. This is ReloPass's `buildDataSheet` equivalent — it already implements properties #1–#3 from §2.2.
- **PDF strategy A (AcroForm):** `form_prefill_service.generate_prefilled_pdf(form_id, case_id, employee_profile)` — pypdf field-name fill via `form_field_mappings`, template from `form-templates` bucket, output to `case-documents/{case_id}/prefilled/{form_id}.pdf`. Raises `TemplateNotFillableError` on flattened PDFs.
- **PDF strategy B (coordinate overlay):** `cases_read.py::_generate_filled_pdf` — reportlab draw + pypdf merge, coordinates in `form_templates.fields[].{pdf_x,pdf_y,pdf_page}`. Admin mapping UI `PdfCoordinateMapper.tsx`. Route `GET /api/cases/{id}/forms/{formId}/pdf`.
- **From-scratch sheet PDF:** `data_sheet_pdf.py::render_data_sheet` (template code `RP-NO-DATASHEET`) for no-AcroForm corridors like FR→NO — already the print-quality Data Sheet, just not wired to a rich on-screen view.
- **Backing tables** (`20260521000000_dossier_forms_core.sql`): `form_templates` (fields jsonb, sections, authority, country, trigger_rules), `case_forms` (per-case instance, status, completion_pct, deadline), `case_form_field_values` (above), `dossier_packages` (bundle export).
- **Deps present:** `reportlab>=4.0`, `pypdf>=4.0`.

### 3.5 Extraction — EXISTS (live)

- Passport OCR: `ocr_passport_extractor.extract_passport` → `llm_client.complete` (gpt-4o vision), MRZ ICAO-9303 validated → vault `imm_employee_profiles` with `field_sources`.
- General OCR: Mistral (`mistral_ocr_client`, `/api/ocr/process` → `document_ocr_results`).
- Certificates (marriage/birth/diploma/tax): `rce.*` engine.

### 3.6 Safety rails (hard constraints, §9)

- **Serving/LLM isolation gate.** `scripts/check_serving_llm_isolation.py`: five `SERVING_ROOTS` (`requirements_builder`, `rules_engine`, `requirement_evaluation_service`, `immigration_requirement_service`, `hr_policy_resolver`) must never import an LLM gateway/SDK, even transitively or via a lazy import.
- **PII masking.** `pii_masker.mask_pii` must wrap any user free-text before an OpenAI/Anthropic prompt. Extraction transports (`ocr_passport_extractor`) are the documented exemption (PII is in the image; masking corrupts grounding).
- **LLM gateway.** `llm_client.py` (`complete`/`claude_complete`) is the only sanctioned path; add new calls via the `policy_assistant_llm_client.py` pattern (mask at the chokepoint).

---

## 4. Gap analysis — exists vs. build

| Capability | Status | Where |
|---|---|---|
| Per-corridor requirement catalog | ✅ EXISTS | `requirement_items` (dest×purpose) |
| Corridor step ordering / prerequisites / deadline triggers | ✅ EXISTS | `corridors/<ID>/pathways/*.yaml` |
| Per-field value store with provenance | ✅ EXISTS | `case_form_field_values` (`filled_by`, `ai_confidence`, `reviewed`) |
| Value resolution ladder (never invents) | ✅ EXISTS | `prefill_engine.run_prefill` |
| Case data (move date, employee type, name, corridor) | ✅ EXISTS | `wizard_cases` + `imm_employee_profiles` + `api/caseDetails.ts` |
| PDF fill (AcroForm + coordinate overlay) | ✅ EXISTS | `form_prefill_service`, `cases_read._generate_filled_pdf` |
| Passport / doc extraction | ✅ EXISTS | `ocr_passport_extractor`, Mistral, `rce.*` |
| **One country-agnostic Data Sheet read-model** | ❌ BUILD | new serving endpoint composing §3.1 models |
| **Consult-professional firewall as an enforced field property** | ⚠️ PARTIAL | prefill never invents, but no `professional_review_required` flag/UI |
| **On-screen Data Sheet UI** (sections by authority, provenance badges, sparse mode, EN/local, employee/HR) | ❌ BUILD | no `DataSheet` component exists (grep: 0 hits) |
| **Client-side CSV export of the sheet** | ❌ BUILD | only admin/server CSV today |
| **Auto-generated form mappings for a NEW corridor** | ❌ BUILD | `form_field_mappings`/coordinates are hand-seeded per form |
| **Structured field extraction beyond passport + receipts** | ❌ BUILD | `ocr.py` returns `extracted_fields={}` for most types |
| **LLM-assisted field suggestion** (writes `filled_by='ai'` + review) | ❌ BUILD | net-new, must stay off serving path |

---

## 5. The mapping: Audos concept → ReloPass reality

This table is the heart of the consolidation. It is what a reviewer should scrutinise.

| Audos Data Sheet concept | ReloPass equivalent (exists) | Action |
|---|---|---|
| `requirement_entities` (step: authority, source_url, process_note, order) | `form_templates` (authority, country, category, sections) + `corridors/<ID>/pathways/*.yaml` `step_graph` (`responsible_party`, `prerequisite_step_ids`, `deadline_trigger`, `cite`) + `requirement_items` (title, `timing`, `non_obvious`, citations) | Compose into one step read-model; corridor YAML = ordering/timing, requirement_items = catalog/citations |
| `requirement_facts` (field: `fact_key`, label, category, `professional_review_required`, hint, guidance) | `form_templates.fields[]` (FieldDefinition) + `form_field_mappings` (`vault_field_path`) | Add `professional_review_required` + `category` + a stable `fact_key` join key to the field model |
| Field value + provenance (`intake→ocr→prior→needs_input`) | `case_form_field_values` (`value`, `filled_by`, `source`, `ai_confidence`, `reviewed`, `overridden`) + `prefill_engine.run_prefill` ladder | **Reuse as-is**; add consult-professional pre-classification |
| Consult-professional firewall | prefill never invents, but no explicit field flag | **Build:** field-level `professional_review_required`, enforced in serve + fill + UI |
| Non-obvious / moat banners | `requirement_items.non_obvious` + `RoadmapV2Step.non_obvious_note` + `CorridorAdvisories.tsx` | Reuse; surface as banners in the sheet |
| Auto-fill from case data | `wizard_cases`, `imm_employee_profiles`, `caseDetails` API | Reuse; `fact_key` ↔ `vault_field_path` alignment |
| `fillable-pdf` channel | `form_prefill_service` (AcroForm) + `cases_read` overlay | Reuse; auto-map new corridors (§8.3) |
| Export (print) | `.ics` export exists; server form-PDF exists; **no client CSV of sheet** | Build client CSV (Blob); reuse PDF |
| Corridor / case picker | `SelectedCaseContext` + `EmployeeAssignmentContext` + `caseDetails` | Reuse |

---

## 6. Target architecture

### 6.1 Principle

Do **not** add a fifth requirement model. Add one **read-model** — the Data Sheet — that composes the existing three canonical sources deterministically:

```
requirement_items (dest×purpose, approved)   ──┐   what is required + non_obvious + citations + timing
corridors/<ID>/pathways step_graph           ──┼─► DataSheet read-model ─► on-screen sheet + CSV + PDF
case_form_field_values (+ prefill_engine)    ──┘   the fields, their values, and provenance
```

- **Step list & ordering** come from the corridor `step_graph` (origin×dest aware, has prerequisites + deadline triggers), falling back to `requirement_items` pillars where a corridor has no authored pathway yet.
- **Per-step required fields + values + provenance** come from `case_forms` / `case_form_field_values`, filled by `prefill_engine`.
- **Citations, non-obvious, attestation/verification badges, free-text timing** come from `requirement_items`.

### 6.2 Serving path & the isolation gate

The Data Sheet **serve** endpoint is deterministic and **must not import any LLM module** in its request path. It is a composition over already-reviewed data (requirement_items are human-approved; `case_form_field_values` are prefilled deterministically). It should live in a new module (e.g. `backend/app/services/data_sheet_service.py`) that is **not** added to `SERVING_ROOTS` but is still LLM-free by construction. LLM-assisted suggestion (§8.4) is a **separate write action**, not part of serve.

### 6.3 New endpoint

```
GET /api/cases/{case_id}/datasheet?audience=employee|hr&lang=en|local&mode=full|sparse
→ DataSheetDTO {
    caseRef, employeeName, corridor, corridorLabel, movementBasis, generatedAt,
    completionPct, needsInputCount,
    banners: [{ type: 'moat-fact'|'warning', text }],
    sections: [{
      stepId, authority, sourceUrl, processNote, channels[], order,
      responsibleParty, slaNote, deadline{ date?, isSuggested, isHard },
      fields: [{
        factKey, label, category, source /* intake|passport_ocr|prior_form|needs_input|consult_professional */,
        value|null, confidence, hint?, guidance?, requiresOriginal?, employerActionNote?
      }]
    }],
    consultProfessional: [{ topic, reason }]
  }
```

Register in **both** `backend/app/main.py` and `backend/main.py` (the 405 dual-registration rule). Field-value edits reuse the existing `case_form_field_values` write path; a `PATCH .../datasheet/fields/{fieldId}` (or the existing checklist/field endpoints) persists a `needs_input → employee` transition, rejecting consult-professional keys server-side.

### 6.4 Frontend

- New feature module `frontend/src/features/datasheet/` with `DataSheetView.tsx` (the agnostic engine), `DataSheetSection.tsx`, `SourceBadge.tsx`, `ConsultProfessionalPanel.tsx`, `RegulatoryBanners.tsx`, plus `useDataSheet(caseId)` calling a new `api/datasheet.ts` wrapper.
- Built from **antigravity** primitives (`Card`, `Badge`, `Alert`, `ProgressBar`, `Tabs`, `StatusPill`, `Input`, `Button`). Do not spin up a third primitive set — reconcile toward antigravity (platform-v2 already forked its own; flag noted, out of scope to migrate here).
- Mounts on `pages/employee/EmployeeCaseRoadmapPage.tsx` (employee) and `pages/hr/HrCaseDossierPage.tsx` (HR, `audience="hr"` with responsible-party + SLA columns). Case + corridor + move date + name come from `api/caseDetails.ts` (`getCaseDetailsByAssignmentId`).
- **Provenance badges** exactly mirror §2.3. **Non-obvious** rendered as amber banners (reuse `CorridorAdvisories` semantics). **CSV export** is client-side `Blob`/`URL.createObjectURL` (columns: `Step,Authority,Field,Value,Source,Deadline,ResponsibleParty,NonObvious`); filename `relopass-{corridor}-datasheet-{YYYY-MM-DD}.csv`. **PDF** reuses `api/formEditor.ts::downloadPdf` → the server fill endpoints.

---

## 7. Data model changes

Reuse the existing `form_templates` / `case_forms` / `case_form_field_values` triple. Minimal additive changes:

1. **Field-level consult-professional + join key** on the field model. Either extend `form_templates.fields[]` FieldDefinition with `professional_review_required: bool`, `category: string`, `fact_key: string`, or add a companion `requirement_facts`-style table keyed to templates. Recommendation: extend the jsonb `fields[]` (no migration for existing rows; additive) plus a nullable column for query-time filtering if needed.
2. **`fact_key` alignment.** Ensure `form_field_mappings.vault_field_path` and the DataSheet `factKey` share one vocabulary so a value captured once fills every step. Document the canonical key list (it already exists implicitly: `passport_number`, `given_names`, `family_name`, `date_of_birth`, `nationality`, `employer_name`, `employer_org_number`, `first_work_day`, `norwegian_address`, …).
3. **No new PII columns without RLS.** Any new `public` table (if a companion `requirement_facts` table is chosen over jsonb) MUST ship `ALTER TABLE … ENABLE ROW LEVEL SECURITY`, at least one tenant-scoped policy, and `REVOKE ALL … FROM anon` in the same migration (hard gate, `case_milestones` is the canonical pattern). Prefer extending jsonb precisely to avoid a new table.
4. **Migration discipline.** One idempotent migration file, timestamp above **both** the repo max and the prod ledger max; never `supabase db push`; reconcile the ledger after an out-of-band apply.

**Note on `relocation_cases` drift:** the builder's raw-SQL fallback reads `origin_country_code`/`dest_country_code`, which exist only after ALTER `20260728000000`. If unapplied in an env, the fallback silently returns `(None, None)`. The Data Sheet should prefer `wizard_cases` columns + `caseDetails` and treat the corridor as resolved data, not re-derive it.

---

## 8. Document filling / PDF (the expanded scope)

### 8.1 What already works (reuse)

For any corridor form that has a template + field mapping, filling is done: `prefill_engine.run_prefill` populates `case_form_field_values`, then `form_prefill_service.generate_prefilled_pdf` (AcroForm) or `cases_read._generate_filled_pdf` (coordinate overlay) emits the filled PDF. The Data Sheet's "Download filled PDF" button is a thin call to the existing endpoints.

### 8.2 The consult-professional firewall in the fill path

`prefill_engine` never invents but does not yet *refuse* regulated fields. Add the field-level `professional_review_required` classification so the fill path leaves those blank with `guidance`, matching the on-screen firewall. This is the same invariant enforced in two places (serve + fill).

### 8.3 New-corridor form mapping (the real build)

Today `form_field_mappings` + coordinate maps are hand-seeded per form. For agnostic scale:

- **Authoring surface**: extend the admin `PdfCoordinateMapper.tsx` + `form_field_mappings` CRUD so adding a corridor's forms is a guided data task, not code.
- **Fallback for no-AcroForm corridors**: `render_data_sheet` (RP-NO-DATASHEET) already produces a print-grade sheet PDF; make it the default export whenever a corridor lacks a fillable government AcroForm (matches `ACROFORM-FEASIBILITY-DE-FR.md`: 4 of 5 French PDFs were flattened).

### 8.4 LLM-assisted field suggestion (net-new, gated)

For fields not resolvable from structured data (free-text extraction from an uploaded letter, say), an **authoring-layer** LLM step may *suggest* a value:

- Runs **outside** any `SERVING_ROOT`; nothing on the serve path imports it.
- Free-text input passes through `pii_masker.mask_pii` before the prompt (hard rule); use the `policy_assistant_llm_client.py` chokepoint pattern via `llm_client`.
- Writes to `case_form_field_values` with `filled_by='ai'`, `ai_confidence`, `reviewed=false` — surfaced in the UI as "AI suggestion — please check," never auto-accepted, and never for consult-professional keys.
- This is the *only* place an LLM touches the form system, and it produces reviewable candidates, not served facts. It keeps the "human reviews every AI recommendation" story intact.

---

## 9. Hard gates & constraints (do not violate)

1. **Serving/LLM isolation** — the DataSheet serve module must be LLM-free; the AI-suggestion module must not be import-reachable from any `SERVING_ROOT`. Verify with `scripts/check_serving_llm_isolation.py`.
2. **PII masking** — mask before any OpenAI/Anthropic prompt; never log raw user input (`safe_log_text`).
3. **RLS on any new `public` table** — enable RLS + policy + `REVOKE ALL FROM anon`, same migration. Prefer jsonb extension to avoid a new table.
4. **Dual router registration** — new routers registered in `backend/app/main.py` AND `backend/main.py`; verify the route appears via the import check before pushing.
5. **Compliance copy** — no "EU AI Act Ready/compliant/certified"; describe controls (human review, provenance, citations, PII masking), claim no status. `scripts/check_compliance_claims.py` enforces.
6. **Never invent a value; never fill consult-professional** — the two invariants the moat rests on, enforced in serve, fill, and write paths.
7. **Design system** — antigravity + `--rp-*`/`navy-*`/`accent-*` tokens per `DESIGN.md`; no purple/violet brand drift (the reference prototype's hardcoded hex is prototype-only).

---

## 10. Phased delivery plan

Each phase is independently shippable and verifiable. Effort is rough (human-team / AI-assisted).

### Phase 1 — Read-model + serve endpoint (foundation)
- Build `data_sheet_service.py` composing `requirement_items` + corridor `step_graph` + `case_form_field_values`; `GET /api/cases/{id}/datasheet`; `DataSheetDTO`.
- Add field-level `professional_review_required` / `category` / `fact_key` to the field model; enforce the firewall server-side.
- **Verify:** golden FR→NO case returns the 5 steps with correct provenance and consult-professional fields blank; isolation-gate + dual-registration checks pass. (~3–4 d / ~½ d)

### Phase 2 — On-screen Data Sheet UI
- `features/datasheet/` engine (sections by authority, source badges, banners, sparse mode, EN/local, employee/HR views); mount on employee roadmap + HR dossier.
- **Verify:** employee sees the sheet for a real case; HR sees responsible-party/SLA columns; non-obvious banners render; `needs_input` edit persists. (~4–5 d / ~1 d)

### Phase 3 — Export
- Client-side CSV of the sheet; "Download filled PDF" wired to existing fill endpoints; default to `render_data_sheet` for no-AcroForm corridors.
- **Verify:** CSV columns correct + downloads client-side; filled PDF returns for an AcroForm corridor; sheet PDF for FR→NO. (~2 d / ~½ d)

### Phase 4 — Consolidation (retire overlap)
- Point `DestinationRequirements` / `VisaChecklistCard` / `DocumentsScreen` at the unified read-model (or fold them into the Data Sheet), removing dead paths (`RequirementList` `onAction` buttons, legacy `/journey` redirects). Feed the typed-deadline fields (currently null) from `deadline_trigger`.
- **Verify:** one model backs every requirement surface; no regression in the four existing screens. (~3–5 d / ~1 d)

### Phase 5 — Agnostic scale + AI-assist (expanded scope)
- Admin authoring for new-corridor form mappings; per-type structured extraction beyond passport/receipt; LLM-assisted suggestion writing `filled_by='ai'` + review under the gates.
- **Verify:** a brand-new corridor renders a full Data Sheet with fillable PDFs from data alone; AI suggestions appear as reviewable, never for consult-professional. (~1–2 wk / ~2–3 d)

```
Phase 1 (read-model) ─┬─► Phase 2 (UI) ─► Phase 3 (export) ─► Phase 4 (consolidation)
                      └─► Phase 5 (scale + AI-assist)   [can start after Phase 1]
```

---

## 11. Acceptance criteria (system-level)

1. A single `GET /api/cases/{id}/datasheet` returns steps + fields + provenance for any of the 14 corridors with no per-corridor code.
2. Every field shows exactly one source; no field is ever populated by inference; consult-professional fields are always blank with guidance.
3. Employee and HR see the same sheet; HR additionally sees responsible-party + SLA + employer-action notes.
4. Non-obvious traps render as banners; hard deadlines render as warnings.
5. CSV exports client-side; filled PDF returns via the existing fill engine for AcroForm corridors and via `render_data_sheet` otherwise.
6. `scripts/check_serving_llm_isolation.py`, `check_compliance_claims.py`, RLS coverage, and dual-registration checks all pass.
7. Adding a new corridor is a data-only operation (requirement rows + optional pathway + optional form mapping).

---

## 12. Decisions needed (open)

1. **Canonical step source.** Corridor `step_graph` YAML (rich, origin×dest, but only for authored corridors) vs. `requirement_items` pillars (all corridors, dest-only). Recommendation: prefer `step_graph` where present, fall back to pillars. Confirm.
2. **Field model home.** Extend `form_templates.fields[]` jsonb (no new table, no RLS surface) vs. a companion `requirement_facts` table (cleaner queries, needs RLS). Recommendation: jsonb extension first.
3. **Consolidation appetite.** Do we retire the four overlapping frontend models in Phase 4, or run the Data Sheet alongside them first? Recommendation: ship alongside (Phases 1–3), then consolidate.
4. **AI-assist in v1?** Include Phase 5's LLM suggestion now, or ship the deterministic sheet first and add AI-assist once the fill loop is proven? Recommendation: deterministic first.

---

## 13. Out of scope

- Migrating platform-v2's parallel primitive set to antigravity (flagged, separate cleanup).
- Making tax/legal/social-security determinations (permanently out — consult-professional firewall).
- Origin×destination requirement *catalog* merge (the requirement engine stays destination-only; only the Data Sheet read-model is corridor-aware via the step-graph).
- New OCR providers or an AV-scan pipeline (Render can't apt-install clamav; tracked separately).

---

## 14. Key file reference

| Area | Path |
|---|---|
| Reference type model | `audos-workspace-776786/lib/datasheet-types.ts` |
| Reference fill engine | `audos-workspace-776786/lib/dataSheetBuilder.ts` |
| Reference UI | `audos-workspace-776786/apps/CorridorDataSheetEngine/App.tsx` |
| Reference data content | `audos-workspace-776786/apps/case-command/datasheet-seed.ts` |
| Requirement serving | `backend/app/services/requirements_builder.py`, `rules_engine.py` |
| Requirement table | `backend/app/models.py` (`RequirementItem`, id varchar, `review_status`) |
| Corridor step-graphs | `corridors/<ID>/pathways/<PATHWAY>/vN.yaml`, `corridor_registry.py` |
| Value resolution | `backend/app/services/prefill_engine.py` |
| PDF fill (AcroForm) | `backend/app/services/form_prefill_service.py` |
| PDF fill (overlay) | `backend/app/routers/cases_read.py::_generate_filled_pdf` |
| Sheet PDF | `backend/app/services/data_sheet_pdf.py` (`RP-NO-DATASHEET`) |
| Forms tables | `supabase/migrations/20260521000000_dossier_forms_core.sql` |
| Extraction | `backend/app/services/ocr_passport_extractor.py`, `mistral_ocr_client.py` |
| PII / LLM | `backend/app/services/pii_masker.py`, `llm_client.py`, `policy_assistant_llm_client.py` |
| Isolation gate | `scripts/check_serving_llm_isolation.py`, `docs/specs/serving-llm-isolation.md` |
| Requirement UI | `components/requirements/RequirementList.tsx`, `features/platform-v2/dossier/DestinationRequirements.tsx` |
| Roadmap UI | `features/platform-v2/roadmap/RoadmapScreen.tsx`, `CorridorAdvisories.tsx` |
| Checklist / documents | `features/cases/VisaChecklistCard.tsx`, `features/platform-v2/documents/DocumentsScreen.tsx` |
| Case data API | `frontend/src/api/caseDetails.ts`, `api/cases.ts`, `api/roadmapV2.ts` |
| Design system | `frontend/src/components/antigravity/`, `DESIGN.md` |

---

## 15. Glossary

- **Corridor** — a directional origin→destination move (e.g. FR→NO). ReloPass's requirement *catalog* is destination-only; corridor step-graphs are origin×dest.
- **Consult-professional** — a field that is a regulated tax/legal/social-security determination ReloPass refuses to fill; renders guidance only.
- **Provenance / source** — where a field's value came from: `intake`, `passport_ocr`, `prior_form`, `needs_input`, `consult_professional` (+ `ai` suggestion, review-gated).
- **Non-obvious ("moat fact")** — a trap a competent HR generalist does not know to check (e.g. skattekort before first payroll).
- **fact_key** — the stable join key mapping a requirement field to case data so one value fills many steps.
