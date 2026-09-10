# Build Plan — Form-Fill Integration (corridor knowledge → filled PDF)

**Status:** proposal · **Owner:** TBD · **Companion spec:** [`docs/specs/agnostic-datasheet-and-form-fill.md`](../specs/agnostic-datasheet-and-form-fill.md)
**Verified against code:** 2026-09-10 (post wave-5 corridor-content; supersedes the spec's 2026-09-09 gap analysis, which predates several landed pieces)

## 0. The user story we are integrating toward

> A user opens a form they must fill for their corridor. ReloPass **shows the original
> form on the page**, **auto-fills the fields it already knows** from the case data,
> **leaves the rest (and the regulated fields) to the user**, and **produces a filled
> PDF on request**.

The point of this plan is not to build these parts from scratch — most exist — but to
**wire them into one flow** for *any* corridor. The plan is organised around the
**seams** between components, because that is where the work actually is.

---

## 1. Integration map — what exists vs. what joins them

There are three horizontal layers already in the codebase and one join key that must
tie them together. The build is the **glue**, not the layers.

```
 KNOWLEDGE  corridor-content/*.ndjson (31 corridors, harvested)   ─┐
            requirement_items (dest×purpose, approved)             │  "which forms, which fields,
            corridors/<ID>/pathways/*.yaml (ordering, deadlines)   │   guidance, non-obvious, deadlines"
                                                                    │
   ── join key: fact_key ───────────────────────────────────────── ┤ ← THE SEAM (must become canonical)
                                                                    │
   VALUE    case_form_field_values (value + provenance)             │  "the answer for each field,
            prefill_engine.run_prefill()  (never invents)           │   filled from case data"
            case data: wizard_cases + imm_employee_profiles + OCR   │
                                                                    │
   FORM/PDF form_templates + form_field_mappings (per-form)         │  "the actual PDF + where each
            form_prefill_service.generate_prefilled_pdf (AcroForm)  │   field goes on it"
            cases_read._generate_filled_pdf (coordinate overlay)    │
            data_sheet_pdf.render_data_sheet (from-scratch sheet)  ─┘
                          │
                          ▼
        data_sheet_service.build_data_sheet() ─► GET /api/cases/{id}/datasheet
                          │                        PATCH .../fields/{id} (write-back)
                          ▼                        GET .../datasheet/pdf
        frontend/src/features/datasheet/ (DataSheetView, useDataSheet, CSV export)
```

### 1.1 Already built (verified — reuse, do not rebuild)

| Component | File / route | What it does |
|---|---|---|
| Serve read-model | `services/data_sheet_service.py::build_data_sheet()` | Composes the sheet DTO from the layers |
| Corridor-content fallback | `data_sheet_service.py::_build_from_corridor_content()` | Read-only preview from harvested NDJSON (`preview=true`) |
| Loader | `services/corridor_content.py` | Reads `data/corridor-content/<ISO>.ndjson` |
| Serve endpoint | `routers/data_sheet.py` — `GET /api/cases/{id}/datasheet` | audience / lang / mode params → `DataSheetDTO` |
| **Write-back** | `routers/data_sheet.py` — `PATCH .../datasheet/fields/{id}` | User field edit persisted |
| Sheet PDF export | `routers/data_sheet.py` — `GET .../datasheet/pdf` → `datasheet_export.build_datasheet_pdf` | From-scratch print sheet |
| Value resolution | `services/prefill_engine.py::run_prefill(case_form_id, case_uuid)` | Fills `case_form_field_values` from a source ladder; **never invents**, respects `overridden` |
| AcroForm fill | `services/form_prefill_service.py::generate_prefilled_pdf(...)` | pypdf field-name fill of the real gov PDF |
| Overlay fill | `routers/cases_read.py::_generate_filled_pdf(...)` | reportlab draw + pypdf merge by coordinates |
| From-scratch sheet | `services/data_sheet_pdf.py::render_data_sheet(...)` | Print-grade sheet for no-AcroForm corridors |
| Form tables | `migrations/20260521000000_dossier_forms_core.sql` (+ sections, provenance, mappings-seed) | `form_templates`, `case_forms`, `case_form_field_values`, `form_field_mappings` |
| Reference corridor | `migrations/20261015000000_seed_frno_data_sheet.sql` | FR→NO fully seeded (template + mapping + fields) |
| Frontend view | `frontend/src/features/datasheet/` — `DataSheetView.tsx`, `DataSheetFieldRow.tsx`, `useDataSheet.ts`, `datasheetCsv.ts` | Structured sheet + client CSV export |
| Extraction | `ocr_passport_extractor`, Mistral OCR, `rce.*` | Feeds the value store |

### 1.2 The real gap — five integration builds

| # | Missing piece | Why it blocks the user story | Seam it lives on |
|---|---|---|---|
| **A** | **Per-corridor fillable form templates + field mappings** | Only FR→NO is seeded. A harvested corridor has the *knowledge* but no uploaded gov PDF and no field→`fact_key` map, so it can produce the *sheet* PDF but **not a filled copy of the actual form**. | KNOWLEDGE ↔ FORM/PDF |
| **B** | **Canonical `fact_key` dictionary + guaranteed write-back consistency** | `fact_key` strings drift per source (`employer_name`/`employerName`/`company_name`), silently breaking every join. Without one governed vocabulary, "answer once, fill everywhere" is best-effort, not structural. | the join key itself |
| **C** | **"Original form on the page" UI** | Today's `DataSheetView` renders a *structured* sheet, not the actual form image with fields overlaid. The user asked specifically to *see the form* and fill it in place. | FORM/PDF ↔ frontend |
| **D** | **Upgrade harvested corridors from read-only preview → interactive fill** | `_build_from_corridor_content` returns `preview=true` with no editable values or PDF button, because a harvested corridor has no `case_forms`/mapping/template. Needs a defined upgrade path (and graceful fallback). | KNOWLEDGE ↔ VALUE ↔ FORM |
| **E** | **LLM-assisted field suggestion (gated, optional)** | Free-text fields (an uploaded letter) can't be filled from structured data; a reviewable AI suggestion covers them — but must stay off the serve path. | authoring layer only |

---

## 2. The integration spine: one canonical `fact_key` (Build B first)

Everything else hangs off this. Do it first.

**Problem.** The harvested corridor-content already emits a `fact_key` per record
(`kennismigrant_residence_permit`, `pl.pesel_number`, …), `form_field_mappings` carries
its own `vault_field_path`, and `case_form_field_values` keys on yet another string.
Three vocabularies, no enforced join.

**Build.** A single **fact dictionary** — one governed definition per `fact_key`:
`label`, `category`, `professional_review_required: bool`, `canonical_source_path`
(which vault / `case_facts` field the value comes from), optional `format`/validation.
Ship first as a **checked-in seed** (non-PII reference data, peer to `requirement_items`),
promote to a small RLS'd table only when query-time filtering is needed.

**Integration actions (the seams this closes):**
1. **Seed from what we already harvested.** Extract the distinct `fact_key`s from the
   31 `data/corridor-content/*.ndjson` files + the existing `form_field_mappings` seed,
   dedupe/normalise (collapse `employer_name`/`employerName`), and write the dictionary.
   This is a mechanical script over data we own — the harvest directly feeds it.
2. **Resolve through it.** `prefill_engine` and `form_field_mappings.vault_field_path`
   both resolve a value *through* the dictionary's `canonical_source_path`, so a value
   captured once fills every form that references the same `fact_key`.
3. **Write-back to canonical.** The existing `PATCH .../datasheet/fields/{id}` must
   persist a confirmed `needs_input` answer to the **canonical store** (`case_facts` /
   vault, `source: user_input`) — not only that form's `case_form_field_values` row —
   so the next form, the roadmap, and the HR dossier read the same value. Verify the
   current PATCH already does this; if it only writes the per-form row, extend it.
4. **Firewall in the dictionary.** `professional_review_required: true` keys are refused
   at both serve and fill and rendered as blank-with-guidance in the UI and the PDF.

**Acceptance:** a value entered on one form's sheet renders as `intake`/`user_input`
(not `needs_input`) on the next form for the same case, with zero re-entry.

---

## 3. The data build: per-corridor templates + mappings (Build A)

This is what turns a *harvested corridor* into a *fillable form*, and it is the biggest
lift because it is per-form data acquisition, not code.

**Integration actions:**
1. **Worklist from the harvest.** The corridor-content `form_name` field is the
   authoritative list of which forms each corridor needs. Generate a backlog:
   `(country_iso, form_name, authority, source_url)` per distinct form across the 31
   corridors — the harvest *is* the acquisition worklist.
2. **Acquire + register.** For each form: fetch the official PDF, upload to the
   `form-templates` bucket, register a `form_templates` row (country, authority,
   sections, trigger_rules), and declare its `fields[]`.
3. **Map fields to `fact_key`.** For AcroForm PDFs, map the PDF field name →
   `fact_key`. For flattened PDFs (the common case — `ACROFORM-FEASIBILITY-DE-FR.md`
   found 4/5 French PDFs flattened), place coordinates (`pdf_x`, `pdf_y`, `pdf_page`)
   via the admin mapper. **Every mapped field references a `fact_key` from Build B** —
   this is the seam that connects the form to case values.
4. **Authoring surface.** The employee-facing overlay component from the spec
   (`PdfCoordinateMapper.tsx`) is **not yet in the repo** — build the admin mapping UI
   (or confirm where mapping is done today) so adding a corridor's forms is a guided
   data task, not code.
5. **Fallback wired in.** Where a corridor has no fillable government AcroForm,
   `data_sheet_pdf.render_data_sheet` (already built) is the default export — a
   print-grade *filled sheet* stands in for a filled form. Make that selection automatic
   in the download path (AcroForm → overlay → from-scratch sheet, in that order).

**Acceptance:** for a newly-mapped corridor, `generate_prefilled_pdf` (or the overlay)
returns a filled copy of the real government form; unmapped corridors fall back to the
sheet PDF with no error.

---

## 4. The surface: show the form + fill it in place (Builds C & D)

**C — original form on the page.** Today's `DataSheetView` is a structured list. Add a
**form-view mode** that renders the actual PDF (pdf.js) with the prefilled/editable
fields **overlaid on the form image** at their mapped coordinates:
- Prefilled fields show the value + a **provenance badge** (`intake` / `passport_ocr` /
  `prior_form`), and are editable (edit → write-back).
- `needs_input` fields are empty and focusable.
- `professional_review_required` fields render **locked, blank, with the guidance text**
  (the consult-professional firewall, visible on the form).
- A **"Download filled PDF"** button calls the existing export path
  (`api/formEditor.ts` → `form_prefill_service` / overlay / sheet fallback).

**D — upgrade harvested corridors.** Define the path from read-only preview to
interactive fill:
- When a case exists on a corridor that now has a template + mapping (Build A),
  `build_data_sheet` returns the **interactive** DTO (values via `prefill_engine`,
  `preview=false`) instead of `_build_from_corridor_content`'s preview.
- When only corridor-content knowledge exists (no template/case-form yet), keep the
  **read-only preview** — it is the graceful fallback, and the harvest data is exactly
  what populates it. The UI must render both states from the same `DataSheetDTO`
  (preview → no editable fields / no fill button; interactive → full).

**Acceptance:** a mapped corridor shows the real form with green prefilled fields and a
working "Download filled PDF"; an unmapped harvested corridor still shows the
informational sheet (no dead buttons).

---

## 5. Gated AI-assist (Build E — optional, last)

For fields not resolvable from structured data, an **authoring-layer** LLM step may
*suggest* a value. Non-negotiables (from spec §8.4 / §9):
- Runs **outside** every `SERVING_ROOT`; nothing on the serve path imports it (verified
  by `scripts/check_serving_llm_isolation.py`).
- Free-text passes through `pii_masker.mask_pii` before the prompt; via the
  `policy_assistant_llm_client.py` chokepoint on `llm_client`.
- Writes `case_form_field_values` with `filled_by='ai'`, `ai_confidence`,
  `reviewed=false` — surfaced as "AI suggestion — please check", never auto-accepted,
  **never** for `professional_review_required` keys.

---

## 6. Phased delivery (integration-ordered)

Each phase is independently shippable and leaves the system working.

| Phase | Deliverable | Integrates |
|---|---|---|
| **0 — Spine** | Fact dictionary seeded from the 31 corridors + existing mappings; `prefill_engine` + write-back resolve through it; firewall keys flagged. | Build B |
| **1 — Fill for seeded corridors** | Verify FR→NO end-to-end through the new spine; confirm serve DTO, PATCH write-back-to-canonical, and PDF download all use `fact_key`. Ship the form-view UI (C) behind a flag against FR→NO. | B + C on the known-good corridor |
| **2 — Template/mapping at scale** | Admin authoring surface; per-corridor template acquisition + mapping from the harvest worklist; automatic AcroForm→overlay→sheet fallback in the download path. | Build A |
| **3 — Upgrade harvested corridors** | `build_data_sheet` promotes a corridor from preview → interactive once mapped; UI renders both states; graceful fallback. | Build D |
| **4 — AI-assist** | Gated suggestion write action, isolation-verified. | Build E |

---

## 7. Hard gates (do not violate — from spec §9)

1. **Serving/LLM isolation** — the datasheet serve path stays LLM-free; AI-assist not
   import-reachable from any `SERVING_ROOT`. `scripts/check_serving_llm_isolation.py`.
2. **PII masking** — `mask_pii` before any OpenAI/Anthropic prompt; `safe_log_text` for logs.
3. **RLS** on any new `public` table (the fact dictionary, if promoted): enable RLS +
   tenant policy + `REVOKE ALL FROM anon` in the same migration.
4. **Dual router registration** — `data_sheet.py` (and any new router) registered in
   **both** `backend/app/main.py` and `backend/main.py`; verify the route resolves before push.
5. **Never invent** — `prefill_engine` fills only from real sources; a field it cannot
   source stays `needs_input`; a `professional_review_required` field stays blank.
6. **Candidate-grade data** — corridor-content is `lawyer_verified=false`; the fill path
   must not present it as legally verified.
7. **Migration discipline** — one idempotent file, timestamp above both repo and prod
   ledger max; never `supabase db push`.

---

## 8. Integration hazards (where this breaks if unmanaged)

- **`fact_key` drift** — the single biggest risk; the dictionary (Build B) is the whole
  mitigation. Do it first or every later join is best-effort.
- **Flattened government PDFs** — most gov forms have no AcroForm; the from-scratch
  sheet fallback (already built) must be the automatic default, not an afterthought.
- **`relocation_cases` column drift** — the builder's raw-SQL fallback reads
  `origin_country_code`/`dest_country_code` (only after ALTER `20260728000000`); prefer
  `wizard_cases` + `caseDetails`, treat the corridor as resolved data.
- **Consult-professional leakage** — the firewall is one invariant enforced in **three**
  places (serve, fill, UI); a miss in any one ships a regulated auto-fill (a legal
  liability). Test all three.
- **Preview vs. interactive DTO** — both must render from one `DataSheetDTO` shape or the
  UI forks; keep `preview` a first-class field the frontend switches on.
- **405 dual-registration** — a new router registered only in `app/main.py` 404s/405s in
  prod (Render boots `backend.main:app`).

---

## 9. Concrete first PR (Phase 0)

Smallest change that establishes the spine and is independently valuable:

1. `scripts/build_fact_dictionary.py` — reads all `data/corridor-content/*.ndjson` +
   the `form_field_mappings` seed, emits `data/fact-dictionary.json`
   (`fact_key → {label, category, professional_review_required, canonical_source_path}`),
   deduped/normalised, `lawyer_verified=false` provenance preserved.
2. A loader + a test asserting: every corridor-content `fact_key` resolves to exactly one
   dictionary entry; no two entries collide on meaning; `professional_review_required`
   keys are present for the known regulated set (tax residency, PE, immigration
   eligibility).
3. Wire `prefill_engine` to consult the dictionary's `canonical_source_path` (no
   behaviour change yet for seeded forms — just the indirection), keeping the serving
   isolation gate green.

No schema change (checked-in JSON), no PII, no serve-path LLM — merges cleanly and
unblocks Phases 1–3.

---

## 10. Where the corridor-content harvest fits

The harvest (waves 1–6, 32 corridors) is **not** the form-fill feature — but it is the
**knowledge input the integration runs on**: it seeds the fact dictionary (§2), it *is*
the per-corridor form-acquisition worklist (§3), and it is the read-only fallback the UI
shows before a corridor is mapped (§4/D). Continuing the harvest widens coverage of the
knowledge layer; Builds A–D turn that knowledge into filled forms.
