# OCR coverage-gap analysis — extending the live Mistral pipeline

**Task:** AIQ-1309 (re-scope of the rejected AIQ-1147). **Author:** Claude Code, 2026-06-27.
**Question:** Mistral OCR is already live. Which high-value document flows are *not* yet covered,
and what is the **smallest** path to extend the existing pipeline to them — reusing current tables,
RLS, and UI rather than building net-new plumbing?

> Scope note vs AIQ-1147: that spike asked "should we integrate Mistral OCR" and proposed a new
> `document_ocr_results` table. That premise is **stale** — Mistral is integrated (PR #625, `E-PIPE-OCR`)
> and results already persist in `rce.extracted_fields` + `immigration_documents.ocr_result`. So this
> doc does **not** re-design the integration; it maps the live one and finds the cheapest next extension.

---

## 1. What the live pipeline handles today (end-to-end)

OCR is part of the **immigration / RelocationCaseEngine (rce)** document pipeline. There is no
standalone "OCR service" — it is one stage inside document ingestion.

### 1.1 Engines
| Engine | Used for | Where |
|---|---|---|
| **Mistral Document AI** (`mistral-ocr-latest`, `POST https://api.mistral.ai/v1/ocr`) | All **non-passport** docs (general text OCR) | `backend/app/services/mistral_ocr_client.py:26-65` |
| **GPT-4o vision** | Passports / MRZ ID cards (structured field extraction) | `backend/app/services/ocr_passport_extractor.py:321` |

Mistral is gated on `MISTRAL_API_KEY` and **fail-soft**: unset → returns `""`, never raises
(`mistral_ocr_client.py:45-48`). Images go as `image_url` base64, PDFs as `document_url`
(`:50-55`). Output text is treated as PHI — **never logged** (`:9-12`).

### 1.2 Upload entry points
| Endpoint | Accepts | Routing |
|---|---|---|
| `POST /api/employee/cases/{case_id}/profile/ocr-passport` | JPEG/PNG/WebP, 10 MiB | Hardcoded passport → GPT-4o (`immigration_intake_profile.py:455-579`) |
| `POST /api/immigration/cases/{case_id}/documents` | PDF/PNG/JPEG/WebP/TIFF, 20 MiB | Classify → background extraction (`immigration_documents.py:69-124`) |

The general endpoint kicks off two background tasks: `run_extraction` (BL-OCR.3) and, **if the case
exists in `rce.cases`**, `process_rce_document` (the full pipeline, `rce_pipeline_worker.py:128`).

### 1.3 Classification (filename heuristic — no ML yet)
- **BL-OCR path** `document_extraction_queue.classify_document` (`:44-56`): returns `PASSPORT | CONTRACT | PAYSLIP | OTHER` from filename keywords. Only `PASSPORT` actually extracts here; `CONTRACT`/`PAYSLIP`/`OTHER` are **classified but not field-extracted** ("extractors are separate C1-05 tasks").
- **RCE path** `rce_document_ingest.classify_rce_document_type` (`:47-64`): returns `PASSPORT_TD3 | ID_CARD | MARRIAGE_CERT | BIRTH_CERT | FOSTER_CARE_ORDER | DIPLOMA | TAX_CERT` from filename.

### 1.4 Structured extraction agents (the actual "understanding")
`EXTRACTION_AGENT_REGISTRY` (`backend/relopass/agents/extraction/__init__.py:88-93`) wires exactly **four**:
`MARRIAGE_CERT → MarriageCertAgent`, `BIRTH_CERT → BirthCertAgent`,
`FOSTER_CARE_ORDER → FosterCareOrderAgent`, `ID_CARD → IdCardAgent`.
Passport extraction is a **separate** GPT-4o path (not in this registry). The orchestrator
`run_extraction_for_document` (`rce_extraction_orchestrator.py:53-80`) looks up this registry by
`rce.document_types.code` and raises a clear "no agent for this type" `KeyError` otherwise.

### 1.5 Persistence (NO net-new table needed — these already exist)
| Table | Holds | company_id? | RLS |
|---|---|---|---|
| `rce.extracted_fields` | `field_key, value_raw, value_canonical, confidence, bbox_*` per doc | No | Scoped via `rce.documents → rce.cases` FK (hardened C1-01a) |
| `public.immigration_documents.ocr_result` (JSONB) | BL-OCR direct-path result | No | Scoped via `case_assignments` join (`20260609120000_immigration_documents.sql:75-96`) |
| `public.ocr_shadow_comparisons` | Passport GPT-4o-vs-OSS telemetry only (no PII) | No (case_id corr.) | Admin-only + service role; `REVOKE anon` |

### 1.6 UI surface
`frontend/src/components/case/CaseDocumentsPanel.tsx:235-246` renders `doc.ocr_result` when
`ocr_status='done'` — **already wired for any doc type**, just empty for non-passport today.
Passports additionally get the rich `PassportOCRFlow.tsx` (confidence dots, MRZ validation, conflict
detection) and auto-fill the `imm_employee_profiles` vault.

---

## 2. Gap matrix — receipts / leases / visa-permit

| Target flow | OCR text? | Structured fields? | Coverage | Fits the rce.cases model? | Manual effort saved | Extension effort |
|---|---|---|---|---|---|---|
| **Visa / work-permit** | ✅ (Mistral, if uploaded to immigration case) | ❌ no agent | **PARTIAL** | ✅ native — it *is* an immigration doc | High (expiry/conditions drive roadmap deadlines) | **Low** — reuse everything |
| **Expense receipts** | ⚠️ only as `OTHER` general text | ❌ no agent | **NONE** | ❌ not an immigration doc; no expense/reimbursement domain exists | High *volume*, low per-item | High — needs a new domain |
| **Lease agreements** | ⚠️ only as `OTHER` general text | ❌ no agent | **NONE** | ⚠️ housing-adjacent; only a frontend mock (`DocumentsScreen.tsx:115`), no backend | Medium | High — new type + agent + UI |

**Evidence of absence:** no `RECEIPT`/`EXPENSE`/`LEASE`/`VISA`/`WORK_PERMIT` branch in either classifier
(`document_extraction_queue.py:44-56`, `rce_document_ingest.py:47-64`); "receipt" appears only as
`receipt_ref` (a form-submission reference in `case_write.py`), "lease" only in a frontend mock.

**Why the ranking differs from AIQ-1147's "receipts > leases > visa":** that ordering was by raw
frequency, ignoring fit. Receipts/leases are **not immigration documents** and have no home in
`rce.cases` — wiring them means a new capture domain (expense tracking), new tables, new UI: a feature,
not a pipeline extension. Visa/work-permit is the opposite: the document **already flows through the
live pipeline end-to-end** and is missing only the one stage (a structured agent) that every other
immigration doc type already has.

---

## 3. Recommended next extension — Visa / Work-Permit structured extraction (~1 day)

This is the smallest possible extension because it adds **only** the missing agent + classifier branch;
every other layer (upload, Mistral OCR, persistence, RLS, UI surface, even target vault fields) already
exists.

**The vault is already waiting:** `imm_employee_profiles` has `existing_visa_type` and
`existing_visa_expiry` fields (`immigration_intake_profile.py:81-82`) with no auto-fill source — a
visa extractor would populate them exactly as the passport extractor auto-fills the passport vault.

### Files to touch
1. **`backend/app/services/rce_document_ingest.py:47-64`** — add a `VISA` / `WORK_PERMIT` branch to `classify_rce_document_type` (filename keywords `visa`, `permit`, `work_permit`). One `rce.document_types` row per new code (data, not schema — codes are looked up, not enum'd).
2. **`backend/relopass/agents/extraction/__init__.py:88-93`** — register `VISA_PERMIT → VisaPermitAgent` in `EXTRACTION_AGENT_REGISTRY`.
3. **New `backend/relopass/agents/extraction/visa_permit_agent.py`** — model it on `MarriageCertAgent`/`BirthCertAgent` (same base class, same sink to `rce.extracted_fields`). Fields: `visa_type/subclass`, `expiry_date`, `entry_conditions`, `issuing_country`, `permit_number`. Mask any free-text via `pii_masker.mask_pii()` before the LLM call (CLAUDE.md hard rule).
4. **(optional, +0.25 day) `immigration_intake_profile.save_ocr_to_vault`** — extend to write `existing_visa_type`/`existing_visa_expiry` from the new agent's output, mirroring the passport vault auto-fill.
5. **UI:** none required — `CaseDocumentsPanel.tsx:235-246` already renders `ocr_result` for any type. (Optional later: a visa-specific confidence view like `PassportOCRFlow`.)

### Acceptance test
Upload a visa PDF to a case in `rce.cases` → `rce.extracted_fields` gains `visa_type` + `expiry_date`
rows with confidence; `CaseDocumentsPanel` shows them; (if step 4) the profile vault visa fields
populate. Follow the existing `test_rce_*` patterns.

---

## 4. Sub-processor / RLS / GDPR implications

- **Sub-processor:** none new. Mistral AI is **already** in the GDPR Art. 28 register
  (`docs/security/PRIV-004_sub-processor_register.md`, EU/France, `MISTRAL_API_KEY`). A visa agent
  reuses the same engine — no DPA change.
- **RLS / tables:** **no new `public` table** → no new RLS gate. `rce.extracted_fields` is already
  tenant-scoped via `rce.documents → rce.cases`. (If a future receipts/lease domain adds a `public`
  table, it must carry the full RLS + `company_id` + `REVOKE anon` treatment per CLAUDE.md.)
- **PII:** visa docs contain PII → mask free-text via `pii_masker.mask_pii()` before any LLM call and
  use `safe_log_text()`; never log raw OCR output (matches the existing passport/Mistral discipline).

---

## 5. Roadmap (each ≤1 day, ordered by reuse-ratio)

| # | Task | Effort | Reuses |
|---|---|---|---|
| A | **Visa/work-permit extraction agent** (§3) | ~1 day | Entire pipeline; only adds 1 agent + classifier branch |
| B | Wire `CONTRACT`/`PAYSLIP` agents (already classified, no extractor) | ~1 day each | Same registry pattern; closes a pre-existing gap |
| C | Receipts — **defer**; needs an expense-capture domain (new tables/UI), not a pipeline extension | — | Little; re-evaluate when an expense feature is on the roadmap |
| D | Leases — **defer**; backend is mock-only; revisit with the housing module | — | Frontend mock exists; no backend |

**Bottom line:** the cheapest, highest-fit next step is **visa/work-permit structured extraction (A)** —
it turns the existing "OCR text only" handling of visa docs into structured fields that feed roadmap
deadlines and the waiting profile vault, with **zero** new tables, sub-processors, or RLS surface.
