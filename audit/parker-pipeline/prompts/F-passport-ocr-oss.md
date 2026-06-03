## Task body — step F

**UI impact:** None. Backend + a single admin JSON endpoint
(`GET /api/admin/ocr-shadow-comparison`). The shadow-comparison dashboard UI is
a deferred follow-up (see `prompts/followups/F-shadow-dashboard-ui.md` —
created later if Romain wants it).

Add a self-hosted open-source fallback for passport OCR so the high-volume vision
task can be served without GPT-4o. Goal: shadow-compare against the existing
GPT-4o pipeline, then ramp traffic if accuracy is comparable. This is a margin
play and a vendor-lock-in mitigation.

### Prerequisites from prior steps

**Soft dependency on step D.** If D is complete, route via `prompt_registry` for the
prompt that drives the structured extraction. Read:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md`

If D is not yet complete, use the existing static-prompt pattern in
`backend/relopass/llm/router.py`. Note this clearly in PLAN.md under "Deviations".

### Source material
- `backend/app/services/ocr_passport_extractor.py` — current GPT-4o-vision extractor.
- `backend/relopass/llm/router.py` — routing pattern + ESCALATION_CONFIDENCE_THRESHOLDS.
- `audit/parker-framework-audit.md` section 2 (W9, W13) and section 4, Prompt F.

### Concrete deliverables

1. ADR at `audit/adr/adr-001-self-hosted-passport-ocr.md` documenting the model
   choice and tradeoffs:
   - **Text/MRZ extraction:** PaddleOCR (server CPU OK for low-volume; GPU for high).
   - **Structured fields (name, DOB, nationality, dates):** Florence-2-base (small VLM,
     0.23B params, runs on a single T4).
   - Alternatives considered: Qwen2-VL-2B, MiniGPT-v2, LLaVA. Document why Florence-2
     was chosen (size + open weights + permissive licence).
2. Create `backend/app/services/passport_ocr_oss.py` exposing the same interface as
   `ocr_passport_extractor.py`:
   - `extract_passport_fields(image_bytes: bytes) -> PassportExtraction` returning
     the same dataclass shape as the GPT-4o extractor.
   - MRZ validation via ICAO 9303 — reuse the existing util, do not duplicate.
   - Confidence scores per field (0.0–1.0). Use Florence-2's logprobs where
     available; otherwise fallback to a calibrated heuristic (e.g. 0.95 if both
     MRZ and visual zone agree; 0.6 if only one source produced the field).
3. Wire into `backend/relopass/llm/router.py`:
   - Add to ROUTING_TABLE under `task_class='mrz_extraction'` a split controlled by
     env var `PASSPORT_OCR_OSS_SHARE` (default `0.0`).
   - Add `SHADOW_COMPARE=true` mode: runs BOTH extractors, returns the GPT-4o result
     to the caller, logs per-field disagreement to the trace logger under
     `feature_key='passport_ocr_shadow'`.
4. Shadow comparison dashboard:
   - Materialized view `mv_ocr_shadow_comparison` aggregating per-field agreement
     rate, MRZ-pass rate, cost-per-extraction for both pipelines.
   - Migration: only the view; no new base table.
   - **RLS enabled** on the view (admin-only).
   - `GET /api/admin/ocr-shadow-comparison?from=...&to=...` returning the rollup.
5. Tests:
   - `backend/tests/test_passport_ocr_oss.py` against a small fixture set of
     synthetic passport images. Use the existing fixtures if any; otherwise
     generate via a passport-image-mock library and commit a small (<200 KB)
     fixture set under `backend/tests/fixtures/passport_synthetic/`.
   - Shadow-comparison test: with `SHADOW_COMPARE=true`, both extractors run and
     the trace logger receives a `passport_ocr_shadow` row with the diff.
   - Disagreement metric: a hand-crafted "disagreement should be 2 fields" fixture.

### Design notes
- **Do not enable in production traffic** until shadow comparison shows ≥99% field
  agreement on a 200+ image eval set. State this clearly in RESULT.md.
- Florence-2 weights are ~450MB. Document in the ADR: where they're hosted
  (Hugging Face hub), how the production container pulls them (cache at build time
  via a Dockerfile RUN step), and the GPU requirement (T4 or better).
- Confidence calibration is the trickiest part. Don't over-engineer — a simple
  rule ("MRZ+visual agree → high; only one source → medium; neither → low") is
  good enough for shadow comparison. Real calibration comes later when we have
  feedback data from step E.
- Document the cost model: USD per 1000 extractions for GPT-4o vs OSS (compute
  cost only). This belongs in RESULT.md so step G can ingest it.

### Out of scope
- Diploma extraction OSS (step F is passport-only).
- Replacing the GPT-4o extractor. This step adds a parallel path; ramp decision
  is a follow-up.

### Acceptance criteria
- pytest passes.
- ADR exists at `audit/adr/adr-001-self-hosted-passport-ocr.md`.
- `PASSPORT_OCR_OSS_SHARE=0.0` is the default — production traffic unchanged.
- `SHADOW_COMPARE=true` produces shadow-comparison trace rows.
- `GET /api/admin/ocr-shadow-comparison` returns a well-formed rollup.
- RESULT.md states explicitly: "OSS path is NOT routed to production users at any %.
  Romain must set `PASSPORT_OCR_OSS_SHARE > 0` after reviewing shadow comparison."
