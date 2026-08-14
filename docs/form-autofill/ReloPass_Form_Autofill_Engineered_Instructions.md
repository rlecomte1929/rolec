# ReloPass — Form Auto-Fill & Translation: Engineered Build Instructions

> **For:** Claude Code, executing against the `rolec` production repo (FastAPI + React + Supabase).
> **Feature:** "Original form in the system → prefill from data the user already gave → translate (both directions) → register the result in the system."
> **Author's rule this obeys:** per `ReloPass_Audos_Setup_Brief.md`, forms + PII + document extraction are 🔴 Red — they live in **`rolec` production**, never in Audos. Audos may *call* `api.relopass.com` but never owns this. This work is a `rolec` feature branch → PR → Render deploy.
> **Corridor design:** corridor-agnostic engine; **France → Norway seeded first** as the proving dataset (matches the Phase-1 accuracy gate).

---

## 0. How to use this document

This is a **four-phase engineered instruction**, not a one-shot task. Execute strictly in order. **Phase A is a discovery/evaluation pass whose only output is a written `FINDINGS.md`** — do not write feature code in Phase A. Phases B–E are build phases, each with its own verify gate. Do not advance a phase until the prior phase's *verify* passes.

The author explicitly asked for: **goals → spec → plan → metrics → validation**. They are §1, §4, §5, §6, §7 respectively. Read §2 (current state) and §3 (root-cause hypotheses) first — they are what Phase A must confirm or refute before any code is written.

---

## 1. Goals & non-goals

### 1.1 Primary goal
A relocating employee (or their HR) opens a required document in the dossier and can, in one action:
1. **See the real, official blank form** stored in the system (not a synthetic stand-in).
2. Be **offered a prefill** built from data they already provided (intake, passport OCR, prior forms), with every field showing its **source and confidence** and nothing silently invented.
3. **Read the form in English** when the official form is in another language (comprehension), and have their **answers rendered in the form's official language** for submission (both directions).
4. **Register** the finished prefilled document back into the case as a first-class dossier artifact (versioned, auditable, downloadable), advancing the form's status.

### 1.2 Success in one sentence
> For the FR→Norway corridor, an employee can go from "here is the list of documents I need" to "here is my police/EEA-registration and tax-card form, pre-filled from what I already told ReloPass, readable in English, and saved to my case" **without re-typing data they already gave**, and every pre-filled value is traceable to its source.

### 1.3 Non-goals (do NOT build these now)
- No new LLM/OCR **provider** wiring in Audos (🔴 Red — stays server-side, PII-masked).
- No auto-**submission** to any government portal. We prefill + register; the human submits.
- No corridor content authoring beyond FR→Norway (seed FR→NO; design generic).
- No net-new global state manager, no speculative "configurability" (CLAUDE.md Karpathy §2/§3: surgical, minimal).
- Do not claim any EU AI Act status anywhere in copy (CLAUDE.md hard gate).

---

## 2. Current state — what already exists (confirmed by code read)

The platform is **~70% built and disconnected at the seams.** Two parallel prefill systems exist and neither delivers the end-to-end experience:

**System 1 — Dossier structured field-values (P2-1).**
- `backend/app/services/prefill_engine.py` → `run_prefill(case_form_id, case_uuid)` fills `case_form_field_values` from case context. Source priority is coded as: **(1) structured profile, (2) contract/employment — BUILT**; **(3) previously-approved forms, (4) authority lookups, (5) AI inference — marked FUTURE / not implemented.**
- Runs from `trigger_engine.py` on CaseForm creation. Respects `overridden=true` (never clobbers user edits). Sets `completion_pct` and advances status `not_started → auto_filled`, then notifies the employee.
- Frontend: `frontend/src/features/platform-v2/dossier/` — `DossierScreen.tsx`, `CaseFormCard.tsx`, `OriginalPdfDrawer.tsx`, `pages/employee/FormEditorPage.tsx`, `api/dossier.ts`, `api/formEditor.ts`.

**System 2 — IMM-11 real-PDF AcroForm prefill.**
- `backend/app/services/form_prefill_service.py` → `generate_prefilled_pdf(form_id, case_id, profile)`: downloads a blank AcroForm from Storage bucket `form-templates`, fills it via `pypdf` using `form_field_mappings` (with `format_rule`, `exact_match_required`, `max_length`), writes to bucket `case-documents` at `{case_id}/prefilled/{form_id}.pdf`, returns a signed URL + a per-field **fill report** (`filled` / `blank_missing_data` / `warning`).
- Router `backend/app/routers/immigration_forms.py`: `GET /api/hr/cases/{case_id}/immigration/available-forms` + `POST /api/hr/cases/{case_id}/immigration/generate-form`.
- **Templates are synthetic** — `build_synthetic_acroform()` + `scripts/seed_immigration_form_templates.py` generate stand-ins; only `DE_blue_card_v2024` and `FR_cerfa_14571_v2024` are seeded (`migrations/20260605800000_imm11_form_field_mappings_seed.sql`). **No real government PDFs; no Norway mappings.**

**Original blank-form endpoint (P2-4).**
- `backend/app/routers/case_form_pdf.py` → `GET /api/cases/{case_id}/forms/{form_id}/original` signs `form_templates.original_pdf_url` from bucket `form-templates`. **Documented empty-state: Norway seed templates (P1-4) have no PDF attached → returns `signed_url=null`.** `OriginalPdfDrawer.tsx` renders the empty state.

**Ad-hoc documents (P4-3).** `backend/app/routers/case_forms_adhoc.py` — HR attaches a custom PDF (`is_adhoc=true`, bucket `case-forms`). This is the existing pattern for **registering a document into a case** — reuse its shape.

**Translation (Parker-I).** `backend/app/services/translation_service.py` + `routers/translation.py` → `POST /api/translate` (DeepL/NLLB, sha256 cache in `translation_cache`, cost trace, 503-degrades-to-original). **Fully built but NOT wired into the form flow anywhere.**

**Document upload + OCR/extraction.** `routers/immigration_documents.py` (list works: `GET /api/immigration/cases/{case_id}/documents`), `services/document_extraction_queue.py`, `ocr_passport_extractor.py`, `PassportOCRFlow.tsx`, the `rce_*` extraction pipeline. This is the "form extraction tool" the author references — extracted values are a **prefill source** we are under-using.

**Relevant tables / migrations:** `case_forms`, `form_templates` (+ `original_pdf_url`, `source_url`, `verification_status`), `case_form_field_values`, `form_field_mappings`, `case_form_documents` (`20260607020000`), `immigration_documents`, `translation_cache` (`20260601100000`). Storage buckets: `form-templates` (blank), `case-documents` (`{case_id}/prefilled/...`), `case-forms` (dossier + adhoc PDFs).

## 3. Root-cause hypotheses (Phase A must confirm/refute each)

- **H1 — The real PDF prefill path is invisible to users.** `generate-form` / `available-forms` have **zero frontend callers** (confirmed: no grep hits in `frontend/src`). The backend can fill a real AcroForm, but no UI invokes it. *This is the likely #1 reason "auto-fill isn't working" from the user's chair.*
- **H2 — There are no real forms in the system for the live corridor.** Norway `original_pdf_url` is null; IMM-11 templates are synthetic and only DE/FR. So even where UI exists, there is nothing real to fill or show.
- **H3 — Two prefill systems don't converge.** The dossier field-value editor (System 1) and the AcroForm PDF (System 2) are unaware of each other; a value the employee confirms in the field editor is not rendered onto the official PDF.
- **H4 — "Use the data I already gave" is under-sourced.** `prefill_engine` reads intake profile/contract only. Passport-OCR extractions and prior approved forms (source 3) are available in the system but not fed in.
- **H5 — Translation is never offered** in the form context, despite a working endpoint.

Phase A produces a `FINDINGS.md` that marks each of H1–H5 **CONFIRMED / PARTIAL / REFUTED** with file+line evidence, and reconciles this document's claims against the actual code (this doc was written from a point-in-time read — trust the live repo over this doc where they differ, and note the delta).

---

## 4. Spec — the feature, precisely

### 4.1 Data model additions
Prefer extending existing tables over new ones. If new tables are required, each **must** ship RLS + ≥1 tenant-scoped policy + `REVOKE ALL … FROM anon` in the same migration (CLAUDE.md hard gate).

1. **`form_templates`** — ensure every seeded FR→NO template carries: `original_pdf_url` (real blank PDF key), `source_url` (official gov source), `source_language` (e.g. `nb` for Norwegian), `verification_status`. A template with a null `original_pdf_url` is **not shippable** for this feature.
2. **`form_field_mappings`** — corridor-agnostic already (`corridor_to`, `visa_type`, `vault_field_path`, `format_rule`, `exact_match_required`, `max_length`). Seed the FR→NO forms here. Add an optional `field_language`/`translate_value` flag where a value must be emitted in the form's official language.
3. **Prefill provenance** — `case_form_field_values` already has `filled_by` + `ai_confidence`. Add (or confirm) a **`source`** descriptor per value (`intake_profile` / `contract` / `passport_ocr` / `prior_form` / `manual`) so the UI can show "where each value came from." If a column doesn't exist, store it inside the existing JSON/audit path rather than a risky schema change — Phase A decides.
4. **Registered prefilled document** — reuse `case_form_documents` (+ the `case-documents` bucket `{case_id}/prefilled/{form_id}.pdf` that `form_prefill_service` already writes). The "register" step inserts a `case_form_documents` row linking the generated PDF version to the CaseForm, with a `doc_kind='prefilled'` and the fill-report snapshot.

### 4.2 Prefill sources ("data the user already provided") — ordered
Extend `prefill_engine._build_context` to assemble, highest-trust first:
1. **Confirmed dossier field-values** the employee already reviewed (`overridden=true` wins over everything — never overwrite).
2. **Structured intake** — profile + contract + banking + `case_dependents` (already built).
3. **Passport / ID OCR extractions** — pull from the immigration-documents extraction results (`document_extraction_queue` / `ocr_result`) for this case. This is source (4)/H4 — wire it in, PII-masked, decrypt passport only at fill time (see `immigration_forms._decrypt_passport`).
4. **Previously approved forms** for the same person (source (3), currently FUTURE) — values from an approved CaseForm flow into a new one. Implement the read; it's the highest-leverage "don't retype" win.
5. Leave authority-lookup (Brønnøysund) and AI-inference stubs as explicit TODOs — do not build now (§1.3).

Every resolved value keeps a `source` + `confidence`. **Never invent a value.** A field with no source is `blank_missing_data`, shown to the user as an empty field to complete — not guessed.

### 4.3 The prefill "proposal" UX (both systems converge)
On a CaseForm that has a real template:
- Show the **official blank PDF** (existing `OriginalPdfDrawer`, now non-empty).
- Show a **"Pre-fill from your ReloPass data"** action. It calls the (now corridor-generic) generate endpoint, returns the **fill report + a preview** of the filled PDF, and lists each field as *filled (source X)* / *needs your input* / *verify — special characters* (the `exact_match_required` warning path already exists).
- The employee **reviews and confirms**; confirmation writes the values through the dossier field-value path (so `overridden`/provenance stay coherent) and **registers** the generated PDF as a `case_form_documents` row. Status advances (`auto_filled` → `in_progress`/`ready` per existing state machine). Emit the existing prefill audit event.

### 4.4 Translation — both directions
- **Comprehension (form → English):** when `form_templates.source_language != 'en'`, offer "Show in English." Translate **field labels/instructions** (not the person's PII values) via `POST /api/translate` (`domain='ui'`, cached). Degrade to original text on 503. Never send raw PII field *values* to translation for the comprehension view.
- **Submission (answers → official language):** for fields flagged `translate_value`, render the employee's value into the form's official language for the *submitted* PDF. This may contain PII → it must go through `mask_pii` semantics per CLAUDE.md; prefer **not** translating identity fields (names, passport numbers, dates, IBAN stay verbatim — translating them is wrong and dangerous). In practice `translate_value` applies to free-text/categorical fields (marital status, job title, address descriptors), never to identifiers. Phase A + the author decide the exact per-field list; default is **verbatim** unless explicitly flagged.
- All translation is **cached** (`translation_cache`) and **cost-traced** (already implemented) so this doesn't blow the AI budget.

### 4.5 Registration into the system ("register them")
"Register" = the prefilled, reviewed document becomes a durable, auditable case artifact:
- PDF stored at the existing `{case_id}/prefilled/{form_id}.pdf` key (versioned — keep prior versions, don't hard-overwrite the audit trail).
- A `case_form_documents` row links it to the CaseForm with the fill-report snapshot + `source` provenance + generating user.
- An `audit_logs` entry (reuse `prefill_engine._insert_prefill_audit` convention: `entity_type='case_form'`, `new_value.event='prefill'`).
- The document appears in the dossier list and is eligible for a `DossierPackage`, exactly like ad-hoc docs do today.

---

## 5. Plan — phased, each with a verify gate

> Register **every new/changed router in BOTH `backend/main.py` AND `backend/app/main.py`** (CLAUDE.md hard rule — a router in `app/main.py` only returns 405 in prod). Verify with:
> `python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'immigration' in r.path or 'forms' in r.path))"`
> Tests that mount the prod app must import auth deps from `backend.app.auth_deps`.

**Phase A — Evaluate ("where are we today").** *No feature code.*
- Read the modules in §2, run the existing tests (`cd backend && pytest -k "prefill or form or extraction or translation"`; `cd frontend && npx vitest run dossier`), and enumerate which endpoints have frontend callers.
- Produce `docs/form-autofill/FINDINGS.md`: H1–H5 verdicts with evidence, a corrected "current state" delta vs this doc, the exact list of FR→NO forms in scope (D-number registration, tax card / *skattekort*, police/EEA registration — confirm against the FR-NO requirements docs in repo root), and which of those have a real official PDF obtainable.
- **Verify:** `FINDINGS.md` exists, every hypothesis is marked, and the FR→NO form list is agreed. **Gate: author sign-off before Phase B** (this is a 🔴 accuracy-critical corridor).

**Phase B — Real forms in the system (data layer).**
- Obtain/attach the real blank official PDFs for the FR→NO scope; upload to `form-templates`; set `original_pdf_url`, `source_url`, `source_language`, `verification_status` on each `form_templates` row via a **committed migration** (never MCP-applied; §CLAUDE.md migration discipline). Map their AcroForm fields into `form_field_mappings` (corridor_to=`NO`).
- **Verify:** `GET /api/cases/{id}/forms/{form_id}/original` returns a non-null `signed_url` for each FR→NO form; `get_available_forms('NO', visa_type)` returns them; a unit test replaces the synthetic-template assumption for NO.

**Phase C — Prefill sourcing + convergence (backend).**
- Extend `prefill_engine._build_context` with passport-OCR and prior-approved-form sources (§4.2), each tagged with `source`+`confidence`.
- Make the generate-form path corridor-generic (drop the `visa_type="blue_card"` DE default; derive corridor/visa from the case) and have it consume the **same** resolved context as the dossier field-values so System 1 and System 2 agree (H3).
- **Verify:** `pytest` — new tests: (a) a case with passport OCR prefills passport fields from OCR with `source='passport_ocr'`; (b) an approved prior form donates values to a new form; (c) `overridden=true` values are never overwritten; (d) fill report marks unsourced fields `blank_missing_data` (no invented values).

**Phase D — Prefill proposal + translation UX (frontend).**
- Wire `CaseFormCard`/`FormEditorPage` to call available-forms + generate-form, render the fill report + PDF preview, and the confirm→register action (§4.3).
- Add "Show in English" on non-English templates via `api/translation.ts` (§4.4), degrade-on-503.
- **Verify:** `cd frontend && npx tsc --noEmit` clean; vitest for the new card states; a manual/E2E pass on a FR→NO case shows blank form → prefill proposal → English toggle → confirm → registered doc.

**Phase E — Register + audit + metrics.**
- Implement the registration write (`case_form_documents` + audit + versioned storage) and emit the metrics events in §6.
- **Verify:** after confirm, the doc appears in the dossier list, is downloadable, has an audit row, and the metric counters increment. Full regression: `relopass-e2e-test` targeted run on the dossier/immigration flows.

---

## 6. Metrics — how we know it works (instrument these)

**North-star:** *retype-avoidance rate* = share of form fields auto-filled from existing data and accepted by the user without edit. Target ≥ **70%** of identity/employment fields on FR→NO forms.

Track (log a structured event per generate, like the translation trace):
- **Prefill coverage** = `filled / total` fields per form (from the existing fill report). Target median ≥ 0.7.
- **Source mix** — % of filled fields by source (intake / OCR / prior-form). Proves H4 was addressed.
- **Override rate** = % of prefilled values the user changes. High override on a field = a bad mapping or wrong source → feedback into `form_field_mappings`. Target < 15% on identity fields.
- **Accuracy (the Phase-1 gate)** — on a golden FR→NO fixture, **0 incorrect values** written to identifier fields (passport, D-number, dates). This is pass/fail, not a percentage.
- **Time-to-first-form** — case-created → first registered prefilled doc.
- **Translation** — cache-hit rate + cost per form (already traced); target cache-hit > 80% after warm-up.
- **Funnel** — offered → previewed → confirmed → registered (drop-off per step).

---

## 7. Validation process — before anything ships

1. **Golden fixture, human-verified.** Build one FR→NO case with fully known correct answers (extend the existing `ReloPass_Fixture_NO-FR.md` / FR-NO requirement docs). Assert every prefilled identifier field is exactly correct. **One wrong fact fails the gate** — in a compliance product, accuracy is criterion #1 (Audos brief §5).
2. **No-invention test.** A field with no backing data must render blank, never guessed. Automated + reviewed.
3. **Provenance visible.** Every prefilled value in the UI shows its source; a reviewer can trace each to intake/OCR/prior-form.
4. **PII discipline.** Confirm no raw PII leaves the platform: translation of *values* is verbatim-by-default; any LLM/translation call carrying user text is `mask_pii`'d; passport decrypt happens only at fill time. Grep the diff for new outbound calls.
5. **Security gates.** Any new `public` table has RLS + policy + `REVOKE anon`. Any new route is registered in **both** main files and access-scoped to the case (employee/HR/admin) exactly like the existing routers. Verified by the route-list one-liner + a 404-on-foreign-case test.
6. **Build hygiene.** `tsc --noEmit` clean, `pytest` green, frontend build green (pre-push hook). Feature branch → PR → CI → merge → Render.
7. **Author validation.** Domain-accuracy sign-off by Romain on the FR→NO golden case is the final gate. Nothing is "done" without it (Audos brief §5.3).

---

## 8. Guardrails (non-negotiable, from CLAUDE.md + Audos brief)
- **Stays in `rolec`.** No part of this is built in Audos; Audos may only call the resulting public/authless endpoints (there are none here — all are case-scoped/PII), so realistically **no Audos surface for this feature.**
- **Migrations:** committed files only; never `apply_migration` to prod from the agent; new `public` table ⇒ RLS + policy + `REVOKE anon`.
- **Dual router registration** in `backend/main.py` **and** `backend/app/main.py`.
- **PII masking** before any LLM/translation call that could carry personal data; never log raw user input (`safe_log_text`).
- **No EU AI Act compliance claims** in any copy. Describe controls, claim no status.
- **Surgical changes** (Karpathy): touch only what the feature needs; match existing patterns (reuse ad-hoc/registration + prefill-audit conventions rather than inventing new ones).
- **Deterministic first.** The prefill engine stays rule-based/source-driven; AI inference is an explicit, deferred TODO, not part of this build.

---

## 9. First message to paste into Claude Code
> Execute `docs/form-autofill/FINDINGS.md` first (Phase A of the Form Auto-Fill engineered instructions): read `prefill_engine.py`, `form_prefill_service.py`, `immigration_forms.py`, `case_form_pdf.py`, `case_forms_adhoc.py`, `translation_service.py` and the dossier frontend; run the prefill/form/translation tests; and confirm or refute hypotheses H1–H5 with file+line evidence. Do not write feature code yet. Output `FINDINGS.md` and stop for my sign-off, then propose the Phase-B migration for the FR→Norway real forms.
