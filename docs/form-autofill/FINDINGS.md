# Phase A — FINDINGS: Form Auto-Fill & Translation

> **Status:** Discovery/evaluation pass. **No feature code written.** This is the gate output for the engineered instructions in `docs/form-autofill/ReloPass_Form_Autofill_Engineered_Instructions.md`.
> **Method:** Static code + migration read of the live `rolec` tree (branch `docs/form-autofill-spec`). **The test suites named in §7 were NOT run in this pass** — they are listed as commands for the executing agent to run before Phase B. Every claim below carries a file/line or migration citation; trust the live repo over the spec doc where they differ.
> **Bottom line:** the feature is ~70% built and disconnected — but two *accuracy* problems (F1, F2) outrank the wiring gaps and must be resolved with Romain before any Phase-B seeding.

---

## 1. Hypothesis verdicts (H1–H5)

| # | Hypothesis | Verdict | Evidence |
|---|------------|---------|----------|
| **H1** | Real-PDF prefill path is invisible to users | **CONFIRMED** | `grep -rc "generate-form\|available-forms" frontend/src` → `:0` in **every** file. The endpoints `GET/POST …/immigration/available-forms` \| `…/generate-form` (`backend/app/routers/immigration_forms.py:63,84`) have **zero** frontend callers. Backend can fill a real AcroForm; nothing in the UI ever asks it to. |
| **H2** | No real forms in the system for the live corridor | **CONFIRMED (worse than stated)** | `supabase/migrations/20260521010000_seed_norway_form_templates.sql` header: *"original_pdf_url is NULL on all 8."* No migration ever SETs `original_pdf_url` for a NO row. IMM-11 templates are synthetic (`build_synthetic_acroform`, `form_prefill_service.py:393`). **And** `form_field_mappings` is seeded for `blue_card` (1) + `cerfa` (1) only — **zero Norway mappings** (`20260605800000_imm11_form_field_mappings_seed.sql`) → `get_available_forms('NO', …)` returns `[]`. |
| **H3** | The two prefill systems don't converge | **CONFIRMED** | System 1 writes `case_form_field_values` (`prefill_engine.py`); System 2 fills an AcroForm from `form_field_mappings` + vault profile (`form_prefill_service.py`). They share no context builder and no storage/registration path. A value confirmed in the dossier editor is never rendered onto the official PDF. |
| **H4** | "Use data I already gave" is under-sourced | **CONFIRMED** | `prefill_engine.py:8-12` lists sources 3 (previously-approved forms), 4 (authority lookups), 5 (AI inference) as literal `(future:)` stubs. Only intake profile + contract are wired (`_build_context`). Passport-OCR extractions (`document_extraction_queue`, `ocr_passport_extractor`) exist in the system but are **not** fed into prefill. |
| **H5** | Translation never offered in the form flow | **CONFIRMED** | `/api/translate` is fully built (`translation_service.py`, `routers/translation.py`), but the dossier/form UI has no call: only 1 lexical hit in `OriginalPdfDrawer.tsx` and it is a CSS `translate()`/word, not an API call (1-line confirm during Phase D). `api/dossier.ts`, `FormEditorPage.tsx` → 0 hits. |

All five confirmed. H1 is the direct cause of "the auto-filling part isn't working" from the user's chair; H2 means even the paths that exist have nothing real to act on.

---

## 2. ⚠️ Accuracy findings that outrank the wiring (author decision required)

**F1 — The seeded Norway forms are the WRONG corridor.**
The 8 NO templates are the **third-country / skilled-worker** path — `UTL-2011 · Work permit (skilled worker)`, trigger `visa_type:"skilled_worker"` (`20260521010000_…`). But the live corridor is **France → Norway for a French (EEA) citizen**, and `ReloPass_FR-NO_Requirements_DRAFT.md` is explicit: *"Norway is EEA but not EU, so free movement applies — start work immediately, **no work permit**."* A UTL-2011 work-permit form does not apply to this employee. **Seeding PDFs onto the existing NO templates would prefill the wrong forms.** The actual FR→NO (EEA) requirement set is:

| # | Requirement | Authority | Timing | Fillable artifact? |
|---|-------------|-----------|--------|--------------------|
| 1 | Tax deduction card (**skattekort**) | Skatteetaten | before first payroll (else 50% withholding) | **Portal/appointment**, not a downloadable AcroForm; employer retrieves electronically |
| 2 | **D-number** (temporary ID, stay < 6 mo) | Skatteetaten/UDI | on arrival, **in-person ID appointment** | Issued at appointment; data-sheet, not a fill-and-submit PDF |
| 3 | **Police registration certificate** (EU/EEA) | politiet / UDI | within 3 months of arrival | **UDI online portal** application (registration ≠ UTL-2011) |
| 4 | **A1 social-security certificate** | **France / URSSAF — NOT Norway** | before/at posting | French-side action → **ADVICE/ROUTE**, out of a destination-only engine |
| 5 | National identity number (**fødselsnummer**, stay ≥ 6 mo) | Skatteetaten / folkeregister | report a move | Portal move-report |
| 6 | Passport / EEA ID card | — | evidence for #3 | Existing document (upload, not fill) |

**F2 — Norway is portal-first; the IMM-11 "fill a blank AcroForm → return a PDF" model may not fit.**
Items 1–5 are digital-portal or in-person processes, not paper CERFA/Blue-Card-style AcroForms. The IMM-11 pipeline was designed around German Blue Card / French CERFA **paper** forms. For FR→NO the realistic deliverable is a **"prefilled personal data sheet"** (all the values the employee already gave, in one reviewable sheet, English + Norwegian) that they carry to the D-number appointment and copy into the UDI/Skatteetaten portals — *not* a submit-ready government PDF. **Decision needed:** (a) reframe the FR→NO deliverable as a data-sheet, or (b) restrict AcroForm-PDF prefill to corridors that actually use fillable PDFs (DE/FR) and treat NO separately.

**F3 — Some requirements must NOT be auto-filled.** The requirements docs tag tax-residency status, the A1 determination, and employer-duty rows as **ADVICE/ROUTE → "MUST route to a named regulated professional, not answered in the product's own voice."** The prefill UI must exclude these from "fillable forms" and hand them to the advice-line, never prefill an answer. This intersects the CLAUDE.md limited-risk / no-status-claim posture.

---

## 3. Spec reconciliation — where the instructions doc must be corrected

The engineered doc was written from a point-in-time read; the schema is tighter than assumed:

- **`case_form_field_values` has no `source` column.** Actual columns: `filled_by` (CHECK `ai|system|employee|specialist|hr`), `ai_confidence`, `reviewed`, `overridden` (`20260521000000_dossier_forms_core.sql`). Recording granular provenance (`intake` vs `passport_ocr` vs `prior_form`) needs **a migration** (new nullable `source text` column) — `filled_by` is CHECK-locked and cannot absorb it. *(Doc §4.1.3 said "add or confirm"; confirmed: it must be added.)*
- **`form_templates` has no `source_language`.** It has `verification_status` (default `representative`; `20260612000000`) and `source_url` (`20260606120000`). The "show in English" toggle (doc §4.4) needs a `source_language` column → migration.
- **`case_form_documents` has no `doc_kind` / fill-report column.** Actual: `id, case_form_id, case_id, file_name, storage_path (case-documents bucket), content_type, size_bytes, uploaded_by, timestamps` (`20260607020000`). The registration step (doc §4.5) needs either added columns (`doc_kind`, `fill_report jsonb`) or the report stored via the existing audit path. → migration or audit-only.
- **NO templates are `verification_status='representative'`**, i.e. explicitly *not* verified — consistent with the docs' "do not ship as gospel until Romain signs off."

Every one of these migrations must ship RLS + policy + `REVOKE ALL … FROM anon` if it creates a table (none create tables here — all are `ALTER … ADD COLUMN`, so no new RLS needed, but confirm the parent table's policies already cover the new column).

---

## 4. What already works (don't rebuild)

- Document **listing** + upload + OCR queue: `immigration_documents.py`, `document_extraction_queue.py`, `PassportOCRFlow.tsx` — functional; OCR output is an unused prefill source (H4).
- **Structured prefill** from intake profile/contract, with `overridden` protection, completion %, `not_started→auto_filled`, and employee notify: `prefill_engine.py` — solid foundation to extend, not replace.
- **Translation** (DeepL/NLLB, sha256 cache, cost trace, 503-degrade): `translation_service.py` — ready to wire, no new provider work.
- **Registration pattern**: `case_forms_adhoc.py` (`is_adhoc`, bucket upload, signed URL, SAVEPOINT-isolated audit event) is the canonical shape to reuse for registering prefilled docs.

---

## 5. Recommended Phase-B adjustment (supersedes doc §5 Phase B)

1. **Resolve F1/F2/F3 with Romain first** (§2) — decide the FR→NO deliverable (data-sheet vs PDF) and the correct EEA form set **before** obtaining any PDFs. This is the accuracy gate; it is not optional.
2. Only then: seed the *correct* FR→NO artifacts + `form_field_mappings` (`corridor_to='NO'`), and either attach real PDFs (if any exist as fillable forms) or generate the data-sheet template.
3. Ship the three `ADD COLUMN` migrations (§3) as committed files (never MCP-applied); reconcile the ledger per CLAUDE.md.

---

## 6. Open decisions for sign-off (blocks Phase B)

1. **F1/F2** — FR→NO deliverable: prefilled **data-sheet** (recommended, matches Norway's portal-first reality) **or** submit-ready PDF? Restrict AcroForm-PDF prefill to DE/FR?
2. **F3** — confirm the ADVICE/ROUTE exclusion list (tax residency, A1, employer duty) is never prefilled.
3. **Translation of values** — confirm identifiers (name, passport, D-number, dates, IBAN) stay **verbatim**; only free-text/categorical fields (marital status, job title) may be language-rendered.
4. **Provenance granularity** — approve the `case_form_field_values.source` column (vs. leaving provenance at `filled_by='ai'` granularity only).

---

## 7. Tests to run before Phase B (not run in this pass)

```bash
# Backend — the prefill / form / extraction / translation surface
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest -q \
  -k "prefill or form_prefill or imm11 or immigration_forms or case_dossier_forms or \
      case_form or translation or extraction or ask_once_intake_prefill"

# Route registration gate (must list the immigration-forms + case-form-pdf routes)
python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'immigration' in r.path or 'forms' in r.path))"

# Frontend — dossier form UI
cd frontend && npx vitest run dossier && npx tsc --noEmit
```

Record pass/fail + the route-list output at the top of Phase B; a red suite here means the baseline is broken independent of this feature and must be triaged first.

---

*Prepared by Claude (Cowork) — static analysis pass. Hand to Romain for the §6 decisions, then proceed to Phase B.*

---

## Appendix A — UX prototype validation (Audos / Otto, 30 Jul 2026)

> The Phase-A findings were shared with Otto in the Audos workspace (ReloPass 776786) as a **planning/prototyping** hand-off — no production code, per the two-system rule. Otto built a throwaway UX prototype and gave an explicit verdict on the open §6 decisions. This appendix records that so the data-sheet model is validated before Phase B, and so we can give Audos structured feedback. **Nothing here is production wiring** — the build lands in `rolec`.

**Prototype:** `frno-data-sheet-prototype` (Audos mini-app, `apps/FRNODataSheet/App.tsx`), a "Personal Relocation Data Sheet" for **Case FR-NO-2026-0081 · France → Norway**. Zero API calls, no backend, no DB — design validation only. Verified rendering live (screenshots on file).

### A.1 Decision on §6.1 (data-sheet vs. submit-ready PDF): **DATA-SHEET, unambiguously.**
Otto's verdict, independently reasoned against the FINDINGS: *there is no AcroForm/fillable-PDF path for the primary EEA corridor steps.* The one candidate that looked like a "PDF moment" — the **EEA registration certificate** — is an **output the police issue, not an input form**. What can actually be pre-filled is the **UDI online application** the employee completes *before* booking the in-person police appointment. Conclusion: the prefilled **data-sheet** is the correct production model for FR→NO; restrict any AcroForm-PDF prefill to corridors that genuinely use fillable paper forms (DE/FR). This **confirms F1 and F2.**

### A.2 Decision on §6.2/§6.3 (route-to-professional + verbatim identifiers): confirmed, and expanded.
- **Five** determinations are flagged **CONSULT PROFESSIONAL** (amber badge, *never* pre-populated), routed to a regulated advisor: (1) tax-residency status, (2) A1 / totalization determination, (3) contract classification (secondment vs. local hire), (4) shadow-payroll requirement, (5) permanent-establishment (PE) risk. That is the two we specified plus three Otto judged necessary — accept all five for the production spec.
- **Verbatim identifiers verified in the running prototype:** the EN⇄NO toggle switches **labels only** — "Full legal name" → "Fullt juridisk navn" — while the **value stays verbatim** ("Sophie Leblanc" unchanged) and the source badge (`passport-OCR`) persists. This is exactly the FINDINGS rule that names, passport numbers, D-number, and dates are never translated.

### A.3 New refinement to fold into the Phase-B spec
Otto surfaced a correctness point not in the original FINDINGS: **the D-number and skattekort (tax card) applications on Skatteetaten can be completed in a single session.** The prototype shows them as separate sections for clarity, but the **production build should present them as one portal visit when timed together** — it saves the employee a second in-person appointment. Add this to §5 (Phase-B) as a UX/sequencing requirement.

### A.4 Prototype UX inventory (as built, for Audos feedback)
Source-badge system (intake / passport-OCR / prior-form / **NEEDS INPUT** inline click-to-edit / **CONSULT PROFESSIONAL**), amber regulatory banner, EN/NO label toggle (labels switch, values don't), per-section progress dots that green as required inputs are filled, per-authority timing tooltips with portal URLs (e.g. `skatteetaten.no/en/forms/d-number`), footer badge legend, and a floating **Print / Export** button (shows a "PDF export available in the production build" toast + triggers the browser print dialog with print CSS that hides interactive chrome).

### A.5 Housekeeping flagged during the session (not part of this feature)
- Otto kicked off a second prototype build (Job #91031) after the first — two prototype iterations now exist in the Audos "ReloPass Norway Data-Sheet Prototype" thread; reconcile/keep one.
- Otto noted two unrelated Cursor jobs (#86257, #86205) on a `feat/housing-…-neighborhood-p01` branch are sitting as **unpublished drafts** in the Audos space — worth clearing before the next Publish.

*Appendix prepared by Claude (Cowork) — Audos prototype validation, 30 Jul 2026. Prototype is UX-only; production implementation remains a `rolec` Phase-B task.*
