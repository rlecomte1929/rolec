# ADR-001: Self-hosted open-source passport OCR fallback

- **Status:** Accepted (shadow-only; not routed to production users)
- **Date:** 2026-05-30
- **Context:** Parker Step F — margin play + vendor-lock-in mitigation for the
  high-volume passport OCR task currently served by GPT-4o vision.

## Context

Passport biographical-page extraction is one of our highest-volume vision tasks
(`backend/app/services/ocr_passport_extractor.py`, GPT-4o vision). Two problems:

1. **Margin.** At scale, per-image GPT-4o vision cost dominates the unit economics
   of immigration onboarding.
2. **Lock-in.** A single closed vendor on a core path is a strategic risk.

We want a self-hosted path we can shadow-compare against GPT-4o and ramp only if
accuracy is comparable. This ADR records the model choice and trade-offs.

## Decision

A two-model open-source stack, exposed behind the **same interface** as the GPT-4o
extractor (`extract_passport(image_bytes) -> PassportExtractionResult`):

- **Text / MRZ extraction → PaddleOCR.** Mature, permissively licensed (Apache-2.0),
  strong on the dense monospaced MRZ zone. Runs on server CPU for low volume; GPU
  for high. The two MRZ lines are then validated with our existing ICAO-9303
  checksum (`validate_mrz`, reused — not duplicated).
- **Structured visual fields (name, DOB, nationality, dates) → Florence-2-base.**
  A small (0.23B-param) vision-language model from Microsoft, MIT-licensed, that
  runs comfortably on a single T4. Driven by a task token (region-to-text /
  OCR-with-region), not a text system prompt — so the prompt registry (Step D) does
  not apply to this path.

### Alternatives considered

| Model | Params | Why not chosen |
|-------|--------|----------------|
| **Qwen2-VL-2B** | 2B | ~9× larger than Florence-2; needs more VRAM; licence (Apache-2.0) is fine but the size/cost trade-off loses for a constrained extraction task. |
| **MiniGPT-v2** | 7B | Far too large for a per-image cost-sensitive path; research-oriented licence ambiguity. |
| **LLaVA (7B/13B)** | 7–13B | Excellent general VQA but massively over-provisioned for fixed-schema passport fields; cost erases the margin rationale. |
| **Florence-2-base** | **0.23B** | **Chosen** — smallest capable VLM, permissive MIT weights, single-T4 inference, purpose-built for OCR/region tasks. |

Florence-2 wins on the three axes that matter here: **size**, **open/permissive
weights**, and **fit to a fixed-schema extraction task**.

## Confidence calibration

Florence-2 logprobs are used where available. The fallback heuristic
(`heuristic_confidence`) is deliberately simple — real calibration comes later from
Step E human-feedback data:

- MRZ source and visual source agree on a field → **0.95**
- exactly one source produced the field → **0.60**
- both produced but disagree → **0.40**
- neither produced the field → **0.0**

## Deployment / operations

- **Weights (~450 MB)** are hosted on the Hugging Face hub
  (`microsoft/Florence-2-base`). The production container **pulls and caches them at
  build time** via a Dockerfile `RUN` step (no cold-start download, no runtime
  network dependency on HF).
- **GPU requirement:** T4 or better for the structured-field model. PaddleOCR can run
  CPU-only for low volume.
- **Dependencies** (`paddleocr`, `transformers`, `torch`) are **lazy-imported** inside
  `extract_passport`, so the service module imports cleanly in CI / hosts without the
  ML stack. The OSS path raises `OcrExtractionError('oss_backend_unavailable')` when
  the stack is absent, and callers fall back to GPT-4o.

## Cost model (USD per 1,000 extractions)

Compute-only; refined by Step G with real telemetry from the shadow comparison.

| Pipeline | Per extraction | Per 1,000 | Basis |
|----------|----------------|-----------|-------|
| GPT-4o vision | ~$0.00765 | **~$7.65** | ~1,100 input + 350 output tokens at gpt-4o vision pricing |
| OSS (Florence-2 + PaddleOCR) | ~$0.00040 | **~$0.40** | T4 GPU amortised at ~1.5 s/extraction |

→ roughly a **19× compute-cost reduction** *if* shadow comparison shows comparable
accuracy. These constants live in `passport_ocr_oss.py`
(`GPT4O_COST_PER_EXTRACTION_USD`, `OSS_COST_PER_EXTRACTION_USD`).

## Consequences

- **Do NOT enable in production traffic** until shadow comparison shows **≥99% field
  agreement** on a 200+ image eval set. Default `PASSPORT_OCR_OSS_SHARE=0.0`.
- A new admin-only telemetry table (`ocr_shadow_comparisons`) + materialized view
  (`mv_ocr_shadow_comparison`) hold the agreement/cost rollup.
- The ramp decision (raising `PASSPORT_OCR_OSS_SHARE`) is a human, post-review action.
