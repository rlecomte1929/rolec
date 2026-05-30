# Step F RESULT — Open-source fallback for passport OCR

_Run: run-20260530-174625 | Branch: audit/parker-step-F-passport-ocr-oss (stacked on audit/parker-step-E-rlhf-lite)_

## Summary

Adds a self-hosted, open-source passport-OCR path (PaddleOCR for MRZ/text +
Florence-2-base for structured visual fields) behind the **same interface** as the
GPT-4o vision extractor, plus a shadow-comparison harness that runs both extractors
on one image, **returns the GPT-4o result to the user**, and logs per-field
agreement + per-pipeline cost. This is a margin + vendor-lock-in play: ~19× compute-cost
reduction *if* shadow comparison proves comparable accuracy. The OSS path is **dark by
default** (`PASSPORT_OCR_OSS_SHARE=0.0`) — no production traffic is routed to it. A new
admin-only telemetry table (`ocr_shadow_comparisons`) + daily matview hold the
agreement/cost rollup, surfaced through an admin JSON route. The heavy ML inference is
lazy-imported so the module loads cleanly in CI without the ML stack.

## Files changed
```
 audit/adr/adr-001-self-hosted-passport-ocr.md      |  90 +++++
 backend/app/main.py                                |   2 +
 backend/app/routers/admin_ocr_shadow.py            |  34 ++
 backend/app/services/passport_ocr_oss.py           | 367 +++++++++++++++++++++
 backend/relopass/llm/router.py                     |  45 +++
 backend/tests/test_passport_ocr_oss.py             | 295 +++++++++++++++++
 .../20260601070000_ocr_shadow_comparison.sql       | 102 ++++++
 7 files changed, 935 insertions(+)
```

## Tests added
- `backend/tests/test_passport_ocr_oss.py` (14 tests) — asserts:
  - **Pure diff:** identical extractions → 0 disagreements, agreement_rate 1.0;
    two-field disagreement counted; field empty-in-both is skipped (not counted);
    MRZ-pass flag False without MRZ lines.
  - **Confidence heuristic:** 0.95 (both agree) / 0.60 (one source) / 0.40 (disagree)
    / 0.0 (neither).
  - **Router split helpers:** `passport_ocr_oss_share()` default 0.0 + clamps
    [0,1] + malformed→0.0; `shadow_compare_enabled()` truthy set; `choose_passport_ocr_backend()`
    default routes to gpt4o.
  - **Shadow logging:** `record_shadow_comparison()` writes a row; `extract_passport_shadow()`
    returns GPT-4o always and logs disagreement=2 (surname+nationality); returns GPT-4o
    and logs **nothing** when the OSS extractor raises (best-effort, no row).
  - **OSS unavailable:** `extract_passport()` raises `OcrExtractionError('oss_backend_unavailable')`
    when the ML stack is absent.
  - **Admin rollup route:** well-formed payload (n=2, field_agreement_rate 0.9,
    mrz_pass_rate_gpt4o 1.0, mrz_pass_rate_oss 0.5, avg cost ~0.00765); empty range → zeroed.

## Test result
- pytest: **14 passed, 0 failed** (`backend/tests/test_passport_ocr_oss.py`)
  - Note: the full backend suite has pre-existing cross-module collection errors
    unrelated to this step; the F test file is self-contained (in-memory SQLite,
    `monkeypatch` of `SessionLocal`, `require_admin` dependency override) and runs green
    in isolation.
- tsc: **clean** (`cd frontend && npx tsc --noEmit`, exit 0) — F has no frontend changes.

```
..............                                                           [100%]
14 passed in 0.40s
```

## Migration applied?
- File: `supabase/migrations/20260601070000_ocr_shadow_comparison.sql`
- **NOT applied** — left for human review → MCP `apply_migration` (per standing
  constraint; `supabase db push` is blocked by remote history drift).
- RLS posture:
  - Table `public.ocr_shadow_comparisons`: **RLS enabled** (`ENABLE ROW LEVEL SECURITY`).
    Policies: `ocr_shadow_admin_select` (SELECT TO authenticated USING `public.is_admin()`),
    `ocr_shadow_service_all` (FOR ALL USING `auth.role() = 'service_role'`).
    `GRANT SELECT ... TO authenticated`; **`REVOKE ALL ... FROM anon`**. ✅ all three hard
    gates satisfied.
  - Matview `public.mv_ocr_shadow_comparison`: matviews **cannot** carry RLS — admin-only
    enforced by `REVOKE ALL FROM anon` + `REVOKE ALL FROM authenticated`, plus the admin
    route's `is_admin()` gate. The route reads the **base table** (date-range parameterised),
    not the view, so the view is BI-only and off the request path.

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| GET    | /api/admin/ocr-shadow-comparison | `require_admin` (is_admin) | backend/app/routers/admin_ocr_shadow.py |

## New tables / schema changes
- `public.ocr_shadow_comparisons` — `id uuid pk`, `created_at timestamptz`,
  `case_id text NULL` (correlation only, no PII), `mrz_pass_gpt4o/mrz_pass_oss bool`,
  `field_agreement jsonb` (`{field: bool}`), `compared_count/agreed_count/disagreement_count int`,
  `gpt4o_cost_usd/oss_cost_usd numeric`. Index `idx_ocr_shadow_created_at (created_at DESC)`.
  No FKs (telemetry, no PII). **No biographical data stored** — only field-level agreement
  booleans + MRZ-checksum pass flags + cost.
- `public.mv_ocr_shadow_comparison` — daily matview (day, n, field_agreement_rate,
  mrz_pass_rate_gpt4o/oss, avg_cost_usd_gpt4o/oss). Unique index on `day` for
  `REFRESH ... CONCURRENTLY`. Refresh helper `public.refresh_ocr_shadow_comparison()`
  (SECURITY DEFINER, granted to service_role).

## Configuration / env vars added
- `PASSPORT_OCR_OSS_SHARE` — fraction of passport-OCR traffic routed to the OSS path.
  **Default `0.0`** (all traffic stays on GPT-4o). Clamped to [0,1]; malformed → 0.0
  (fail-safe). Read in `backend/relopass/llm/router.py::passport_ocr_oss_share()`.
- `SHADOW_COMPARE` — when truthy (`1/true/yes/on`), runs both extractors on each image,
  returns GPT-4o, logs the comparison. Default off. Read in
  `backend/relopass/llm/router.py::shadow_compare_enabled()`.

## UI changes summary
- New routes added: none
- New components added: none
- Existing antigravity components reused: none
- UI-PROPOSAL.md status: not required — the shadow dashboard is a deferred follow-up;
  this step ships only the backend telemetry surface it will read.

## Deviations from the original audit prompt
1. **Real interface names.** Implemented against the actual extractor
   (`ocr_passport_extractor.extract_passport` / `PassportExtractionResult` /
   `validate_mrz`), not the sketch's `extract_passport_fields` / `PassportExtraction`,
   which do not exist in the repo.
2. **No `feature_key` trace sink exists.** The sketch assumed a routing-trace sink to
   reuse; there is none, so shadow telemetry lands in a **dedicated new table**
   (`ocr_shadow_comparisons`).
3. **"No new base table" not achievable.** A Postgres materialized view requires a base
   table to aggregate; the base table is therefore introduced (with full RLS).
4. **ROUTING_TABLE left intact.** The passport-image OCR split is a different axis from
   the cost-table's `mrz_extraction` (MRZ-*string* regex) row, so it lives as **pure,
   env-driven helper functions** appended to `router.py` rather than a ROUTING_TABLE edit
   — keeps existing byte-for-byte router tests green.
5. **No synthetic eval images.** The ML inference (PaddleOCR/Florence-2) cannot run in
   CI, so tests exercise the reviewed surface (pure diff/confidence logic, env split,
   best-effort logging, admin rollup) over in-memory SQLite, not real OCR.
6. **Prompt registry (Step D) does not apply.** Florence-2 is driven by a task token, not
   a text system prompt, and there is no passport `task_key`; the OSS path does not read
   the registry.

## What downstream steps will need from this step
- **Cost model for Step G (telemetry refinement).** Constants live in
  `backend/app/services/passport_ocr_oss.py`: `GPT4O_COST_PER_EXTRACTION_USD = 0.00765`
  (~$7.65 / 1,000) and `OSS_COST_PER_EXTRACTION_USD = 0.00040` (~$0.40 / 1,000) →
  ~**19× compute-cost reduction**. Step G should replace these flat constants with real
  per-image telemetry pulled from `ocr_shadow_comparisons` (gpt4o_cost_usd / oss_cost_usd
  columns) via the admin rollup `GET /api/admin/ocr-shadow-comparison`.
- **Ramp gate.** Do not raise `PASSPORT_OCR_OSS_SHARE` until shadow comparison shows
  **≥99% field agreement** on a 200+ image eval set (ADR-001 §Consequences). The ramp is
  a human, post-review action.
- **Rollup payload shape** (for the deferred dashboard): `{ n, field_agreement_rate,
  disagreement_count, mrz_pass_rate_gpt4o, mrz_pass_rate_oss, avg_cost_usd_gpt4o,
  avg_cost_usd_oss, total_cost_usd_gpt4o, total_cost_usd_oss }`, date-range filtered via
  `?from=&to=` ISO-8601.

> **OSS path is NOT routed to production users at any %. Romain must set
> `PASSPORT_OCR_OSS_SHARE > 0` after reviewing shadow comparison.**

## Known gaps / follow-ups
- **Migration not applied** — left for human MCP `apply_migration` (history drift blocks
  `supabase db push`). The route + logging will 500/no-op against a DB that lacks the
  table until applied.
- **Real ML inference unverified in CI** — PaddleOCR/Florence-2 accuracy is unproven
  until the shadow comparison runs against real traffic on a GPU host. `extract_passport()`
  currently raises `oss_backend_unavailable` everywhere the ML stack is absent.
- **Shadow dashboard UI deferred** — only the backend JSON rollup ships here.
- **Matview refresh scheduling deferred** — `refresh_ocr_shadow_comparison()` exists but
  no Edge Function/cron calls it yet; wire it when the dashboard ships.
