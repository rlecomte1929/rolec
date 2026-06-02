# Step F PLAN — Open-source fallback for passport OCR

_Run: run-20260530-174625 | Branch: audit/parker-step-F-passport-ocr-oss (stacked on E)_

## Task understanding
Add a self-hosted, open-source passport OCR path that mirrors the existing GPT-4o
vision extractor, so the high-volume passport task can eventually be served without a
vendor LLM (margin + lock-in mitigation). The OSS path is **dark** by default
(`PASSPORT_OCR_OSS_SHARE=0.0`) — production traffic is unchanged. A `SHADOW_COMPARE`
mode runs both extractors on the same image, returns the GPT-4o result to the caller,
and records per-field agreement + cost to a shadow-comparison table that an admin
rollup endpoint reads. No user-facing UI this step (the dashboard is a deferred
follow-up); the only HTTP surface is `GET /api/admin/ocr-shadow-comparison`.

## Upstream alignment (PREREQUISITES.md → step D)
- D shipped `prompt_registry.get_active_prompt(task_key)` with canonical task_keys
  `policy_extraction` + `policy_assistant_answer`. **There is no registry task_key for
  passport extraction**, and the OSS path is a vision model (Florence-2) driven by a
  task token, not a text system prompt. So F does **not** route the OSS extractor
  through the registry — D's contract is consulted and found N/A here. Recorded under
  Deviations. (The GPT-4o extractor in `ocr_passport_extractor.py` likewise uses a
  static prompt and is out of scope to migrate.)
- Ground-truth interface to mirror (from the real `ocr_passport_extractor.py`, not the
  sketch): `async extract_passport(image_bytes, mime_type) -> PassportExtractionResult`
  and `validate_mrz(l1, l2) -> MrzValidationResult`. The sketch's
  `extract_passport_fields/PassportExtraction` names do not exist — I match the real
  ones and **reuse** `validate_mrz` (ICAO 9303) rather than duplicating it.

## File-by-file change list
- **`audit/adr/adr-001-self-hosted-passport-ocr.md`** (new) — model choice (PaddleOCR
  for MRZ/text, Florence-2-base for structured fields), alternatives (Qwen2-VL-2B,
  MiniGPT-v2, LLaVA) and why Florence-2, weights hosting (HF hub, cached at Docker
  build), GPU (T4+), and the GPT-4o-vs-OSS cost model.
- **`backend/app/services/passport_ocr_oss.py`** (new) — OSS extractor with the same
  interface + dataclass as the GPT-4o path; per-field confidence heuristic; pure
  `diff_extractions()`; `record_shadow_comparison()` (best-effort DB write);
  `extract_passport_shadow()` async orchestrator (injectable extractors for tests).
- **`backend/relopass/llm/router.py`** (edit) — add pure split helpers
  `passport_ocr_oss_share()`, `shadow_compare_enabled()`,
  `choose_passport_ocr_backend(roll, share=None)`. ROUTING_TABLE left intact (see
  Deviations).
- **`backend/app/routers/admin_ocr_shadow.py`** (new) — `GET /api/admin/ocr-shadow-comparison`.
- **`backend/app/main.py`** (edit) — import + `include_router(admin_ocr_shadow.router)`.
- **`supabase/migrations/20260601070000_ocr_shadow_comparison.sql`** (new, NOT applied).
- **`backend/tests/test_passport_ocr_oss.py`** (new) — pure logic + logging + route.

## New tables and migration plan
File: `supabase/migrations/20260601070000_ocr_shadow_comparison.sql` (NOT applied —
human MCP `apply_migration`).
- Base table `public.ocr_shadow_comparisons`: `id uuid pk`, `created_at timestamptz`,
  `case_id text null` (correlation only, no PII), `mrz_pass_gpt4o bool`,
  `mrz_pass_oss bool`, `field_agreement jsonb`, `compared_count int`,
  `agreed_count int`, `disagreement_count int`, `gpt4o_cost_usd numeric`,
  `oss_cost_usd numeric`. Index on `created_at`.
  - **RLS** enabled; policies: admin `SELECT` via `public.is_admin()`; `service_role`
    `ALL`; `REVOKE ALL ... FROM anon`. (Satisfies the CLAUDE.md hard gate.)
- Materialized view `public.mv_ocr_shadow_comparison` — per-day rollup (agreement rate,
  MRZ-pass rate per pipeline, avg cost per pipeline) over the base table, with a
  unique index for `REFRESH ... CONCURRENTLY` and a `refresh_ocr_shadow_comparison()`
  `security definer` function granted to `service_role` (mirrors the `supplier_stats`
  pattern). Matviews can't carry RLS, so admin-only is enforced by `REVOKE ALL FROM
  anon, authenticated` + the route's `is_admin` gate.

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET | /api/admin/ocr-shadow-comparison?from=&to= | require_admin | backend/app/routers/admin_ocr_shadow.py |

The route aggregates **the base table** by date range in portable SQL (works on PG +
SQLite for tests); it does not depend on the matview.

## Tests (backend/tests/test_passport_ocr_oss.py)
- `diff_extractions`: identical results → `disagreement_count==0`, all fields agree
  (happy); a hand-crafted 2-field-difference fixture → `disagreement_count==2` (edge);
  MRZ-pass flags reflect `validate_mrz`.
- Confidence heuristic: both sources agree → 0.95; single source → 0.6; neither → 0.0.
- Router split helpers: default share 0.0; clamp <0→0 and >1→1; `choose_passport_ocr_backend`
  boundaries (share 0.0 → always gpt4o; roll<share → oss); `shadow_compare_enabled`
  truthy/falsy via env (failure-mode: unset → False).
- `record_shadow_comparison` writes one row into a SQLite-patched `SessionLocal`.
- `extract_passport_shadow` with injected fake extractors + shadow on → returns the
  GPT-4o result and logs a row whose `disagreement_count` matches the diff.
- Route: TestClient with `require_admin` overridden + SQLite-seeded rows → GET returns a
  well-formed rollup (agreement_rate, mrz_pass_rate per pipeline, avg costs, n).
- `extract_passport` with ML deps absent → raises `OcrExtractionError("oss_backend_unavailable")`.

## Risks and unknowns
- **ML deps can't run in CI** (PaddleOCR/Florence-2, ~450MB weights, GPU). De-risk:
  heavy imports are lazy inside `extract_passport`; all tested logic is pure or
  injectable; real image extraction is integration-tested manually (documented).
- **Matview RLS**: Postgres matviews can't have RLS policies. De-risk: revoke from
  anon/authenticated + route `is_admin` gate; route reads the base table, not the MV.
- **Cost model** is an estimate (compute-only for OSS). De-risk: constants documented
  in the ADR + RESULT.md so step G can refine.

## Deviations from the original audit prompt
1. **Interface names**: match real `extract_passport`/`PassportExtractionResult` (not
   the sketch's `extract_passport_fields`/`PassportExtraction`).
2. **No `feature_key` trace sink exists** in this repo. The shadow path logs to a new
   dedicated table instead of "the trace logger under feature_key='passport_ocr_shadow'".
3. **A new base table IS required** — a materialized view must aggregate from a table,
   and no existing table holds shadow telemetry. So "no new base table" is not
   achievable; `ocr_shadow_comparisons` is added (RLS-gated).
4. **ROUTING_TABLE left intact**: its rows model cost-table model names, not extractor
   backends, and are asserted by existing tests. The OSS/GPT-4o split is exposed as
   pure helper functions in `router.py` driven by `PASSPORT_OCR_OSS_SHARE`.
5. **No synthetic passport images committed**: Florence-2/PaddleOCR can't run in CI, so
   image-based extraction isn't unit-tested; tests construct `PassportExtractionResult`
   fixtures and exercise the pure diff/confidence/logging/route logic.
6. **Registry not used** for the OSS path (no passport task_key; vision task token).
