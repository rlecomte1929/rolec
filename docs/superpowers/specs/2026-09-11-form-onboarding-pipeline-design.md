# Design — On-demand form-onboarding pipeline

**Date:** 2026-09-11 · **Status:** approved design, pre-implementation · **Author:** Romain + Claude

## 1. Problem

ReloPass can auto-fill a real government form from a case's data — proven end-to-end on the
France-Visas CERFA 14571-*05 (#2286–#2288) and the Spanish EX-17 / TIE (#2292, #2294). But
*adding* each form was a manual routine: acquire the official PDF, verify it is a fillable
AcroForm, enumerate its fields, hand-map each field to a governed `fact_key`, seed
`form_field_mappings`, hand-code radio groups in `CHOICE_GROUPS`, upload the PDF to the
`form-templates` bucket, write a test. The corridor-content harvest already names **498 distinct
forms across 35 corridors** (`docs/form-autofill/form-acquisition-worklist.md`), of which ~57 are
coded-PDF candidates in ~20 languages. Hand-onboarding does not scale.

**Goal:** when a user needs a form that is not yet onboarded, the system prepares its fillable
template in the background — fully automatically — so coverage expands from real demand without
per-form engineering.

## 2. Goals / non-goals

**Goals**
- Fully-automatic onboarding: acquire → analyze → map → register → verify → live, no human in the
  per-form loop.
- Robustness from *automated* safety, not human review: conservative confidence-gated mapping, an
  automatic verify gate, and the standing "never invent / candidate-grade" invariants.
- LLM-assisted mapping so it generalises across languages/forms without hand-tuning.
- Demand-driven: a user's need enqueues the work; the form lights up when ready.
- Config becomes 100% data — onboarding a form writes only data, no code change, no deploy.

**Non-goals (this iteration)**
- Flattened / non-AcroForm government PDFs (no fillable fields) — those remain the coordinate-overlay
  track (`cases_read._generate_filled_pdf`) or the from-scratch data-sheet, and are marked `blocked`.
- Bot-walled sources that refuse a plain HTTP fetch (e.g. France-Visas 403s) — auto-`blocked` with a
  reason; a browser-fetched PDF dropped into the staging slot resumes the form. No headless browser in
  the pipeline this iteration.
- Extending the governed `fact_dictionary` itself — the mapper only targets facts that already exist;
  new facts (e.g. a fact we don't yet store) are a separate, human decision.
- Unifying System A (coordinate-overlay `FormEditorPage`) and System B (AcroForm) — out of scope.

## 3. Approach

A **queue + async worker over a state machine**, driven by a reusable **onboarding engine**. The
engine's stages are idempotent and resumable; the worker advances each pending form one stage at a
time and records status. Two alternatives were rejected: a synchronous in-request background task
(the Render free web dyno spins down and would kill a multi-minute fetch+LLM job, with no durability
or visibility); and an operator-only CLI (not "background/on-demand" — it is really just the engine
without the queue and trigger, so Approach A already contains it as a CLI entry point).

## 4. Data model

### 4.1 New table `form_onboarding_requests` (the state machine / queue)

| column | type | purpose |
|---|---|---|
| `id` | text PK (uuid) | request id |
| `form_id` | text | logical form id, e.g. `ES_ex17_v2024` (stable; = the `form-templates` object name) |
| `form_name`, `country_iso`, `visa_type`, `authority`, `source_url` | text | acquisition inputs (from demand / worklist) |
| `status` | text | `requested \| acquiring \| analyzing \| mapping \| verifying \| live \| blocked \| failed` |
| `stage_detail` | jsonb | per-stage output: field inventory, mapping proposals + confidences, verify report |
| `pdf_sha256` | text | acquired-PDF hash (provenance) |
| `attempts` | int | retry count |
| `error` | text | last failure/blocked reason |
| `requested_by` | text | user/system id that enqueued |
| `created_at`, `updated_at` | timestamptz | |

- **RLS**: enable RLS + an admin/system-scoped policy + `REVOKE ALL ... FROM anon` in the same
  migration (public-schema table — the SEC-002 hard gate).
- **Idempotency**: unique on `form_id` (a form is onboarded once); re-requesting a live form is a
  no-op, a failed/blocked one is retriable.
- Transitions are one-way through the happy path; any stage may move to `failed` (with `error`) or
  `blocked` (needs a human, e.g. bot-walled source or flattened PDF). All recorded for visibility.

### 4.2 `form_field_mappings` gains field-shape-as-data

Two nullable columns, so existing rows are unchanged (`field_kind` defaults to `text`):

- `field_kind text NOT NULL DEFAULT 'text'` — one of `text \| date_part \| single_radio \| checkbox_option`.
- `choice_config jsonb` — for choice shapes only:
  - `single_radio`: `{"M":"/Hombre","F":"/Mujer"}` (canonical option code → AcroForm export value); the
    row's `vault_field_path` is the fact (e.g. `gender`), `form_field_id` is the radio field.
  - `checkbox_option`: `{"code":"M"}` — this checkbox is the `M` option of the `vault_field_path` fact,
    ticked with the field's on-state (resolved at fill time).
  - `date_part`: no `choice_config`; `format_rule` already carries `date_day`/`date_month`/`date_year`.

`build_choice_fill` is refactored to read these rows **instead of the hardcoded `CHOICE_GROUPS`
dict**; the FR CERFA + ES EX-17 groups currently in code migrate to data rows (behaviour identical —
the existing 36 form-fill tests are the regression guard). After this change, registering a form of
any shape is a pure data-write. `form_prefill_service` is System B / authoring, not a serving root,
so this does not touch the serve/LLM isolation boundary.

**Migrations (one-time):** two schema migrations — the new table (with RLS) and the two columns
(the added-column-breaks-two-lanes rule applies: register the ALTER in the PG16-parity lane, and do
not merge code that SELECTs the new columns before the migration is applied). Per-form registration
after that is service-role **data** writes, not migrations.

## 5. The onboarding engine

Module: `backend/app/authoring/form_onboarding/` (authoring layer; **not** a serving root). Each
stage is an idempotent function `(request) -> request'`; the worker calls them in order.

1. **acquire** — HTTP GET `source_url` with a browser-like UA; store the PDF staged (bucket
   `form-templates` under a `staging/{form_id}.pdf` key) and record `pdf_sha256`. Guard: body must
   be `%PDF`. A 403 / non-PDF → `blocked` (`error="acquisition needs browser"`). A human/browser can
   drop the real PDF into the staging slot; the request then resumes at *analyze*.
2. **analyze** — `pypdf.get_fields()`. Zero fields → `blocked` (`error="flattened, not a fillable
   AcroForm"`). Otherwise inventory each field: name, `/FT`, radio `/_States_`, nearest label text;
   classify shape (text / checkbox-option / single-radio / date-part candidate). Output →
   `stage_detail.fields[]`.
3. **map** (LLM, authoring — see §6) — propose per field: `fact_key`/`vault_field_path`,
   `field_kind`, `format_rule`, radio code→export map, and a `confidence`. Then deterministic
   validation keeps only proposals that pass every guard; the rest are dropped (field left unmapped
   → blank).
4. **register** — write the accepted mappings as `form_field_mappings` rows (`field_kind` +
   `choice_config`) via the service role (idempotent: delete this `form_id`'s rows, then insert), and
   move the staged PDF to `form-templates/{form_id}.pdf`.
5. **verify** (the automated gate) — auto-fill the real PDF with synthetic case data through the
   actual fill pipeline (`build_fill_plan` + `build_choice_fill` reading the new rows), then
   `reconcile_report_against_pdf`: **require 0 `not_in_pdf` for every mapped field**. Pass → `live`;
   fail → `failed` (never live on a broken mapping).

`live` = the form-view offers it for its corridor. The stages are exposed as a CLI
(`python -m backend.app.authoring.form_onboarding <form_id>`) for operators/testing — same engine.

## 6. The LLM mapper (authoring layer) — proposes, code disposes

`backend/app/authoring/form_onboarding/mapper.py` is the only new LLM caller, and it runs **only at
onboarding time** (never at fill time or serve time).

- **Input = form metadata only.** Field names, PDF labels, types, radio states, plus the fixed
  `fact_dictionary` vocabulary. It decides *structure*; the fill later injects real case values
  deterministically with no LLM. There is therefore **no case PII in the prompt by construction**;
  the `pii_masker` chokepoint is kept as defense-in-depth.
- **Deterministic disposal is the trust anchor.** The LLM only proposes; code rejects any `fact_key`
  not in the dictionary, any radio export value that is not a real state read from the PDF, any field
  name not actually present in the PDF, and anything below the confidence threshold. A hallucinated
  mapping cannot register.
- **Verify is the backstop.** Even a validated-but-wrong mapping cannot go `live` unless the synthetic
  fill lands it (§5.5).

## 7. Demand trigger + form-view integration

- A corridor's onboardable forms are its coded-PDF candidates from the worklist (harvest → worklist →
  demand — the loop closes).
- When a user opens the form-view (`ImmigrationFormsPage`) for a corridor with a not-yet-onboarded
  form, the page shows **"Preparing your form…"** and POSTs an idempotent onboarding request. The
  worker runs it; on `live` (page refresh/poll) the form is fillable.
- `blocked` / `failed` shows an honest reason ("we couldn't prepare this form automatically —
  <reason>"), never a dead button.
- New employee route/endpoint: `POST /api/employee/cases/{case_id}/immigration/onboard-form`
  (ownership-gated) enqueues a request; `GET .../onboarding-status` reports it. Registered in **both**
  `backend/app/main.py` and `backend/main.py` (the dual-registration rule).

## 8. The worker

A **GitHub Actions scheduled workflow** (the pattern the immigration-indexer already uses):
- Has outbound network for the fetch, holds the LLM key + the Supabase **service** key for the bucket
  upload, and does not burden the spin-down-prone free web dyno.
- Each run drains non-terminal `form_onboarding_requests`, advances each one stage, and writes status
  back. Safely re-runnable; a crash mid-stage leaves the row where it was for the next run.
- Concurrency: one request advances at a time per form (`form_id` unique); the workflow uses a
  concurrency group so two runs don't overlap.

## 9. Hard gates (must all hold)

1. **Serve/LLM isolation** — the mapper is import-unreachable from every `SERVING_ROOT` **and** from
   the fill path (`form_prefill_service`). Enforced by `scripts/check_serving_llm_isolation.py`; the
   new module is added to the audit and confirmed outside the serving closure.
2. **No case PII to the LLM** — structural (metadata-only input) + `mask_pii` chokepoint as backstop;
   `safe_log_text` for logs.
3. **Deterministic disposal** — the LLM proposes; code validates every proposal against the
   `fact_dictionary` and the real PDF fields/states; only high-confidence, validated mappings register.
4. **Verify-must-pass** — no form goes `live` unless the auto-verify fill lands every mapped field.
5. **Never invent** — the fill (unchanged) fills only from real case data; unmapped/unsourced fields
   stay blank.
6. **Candidate-grade** — every output remains a draft the user checks before submitting; the form-view
   keeps that framing and the honesty banner.
7. **RLS + migration discipline** — the onboarding table gets RLS + policy + `REVOKE anon`; the two
   schema migrations follow the timestamp/apply/PG16-parity rules; per-form registration is
   service-role data writes, not migrations; dual router registration for the new endpoints.
8. **Provenance / auditability** — `pdf_sha256`, `source_url`, the mapping, and confidences are
   recorded on each request, so every onboarded form is traceable to its source and decision.

## 10. Testing strategy

- **Engine unit tests** (DB/Storage-free where possible): analyze classifies each shape correctly
  against committed fixture PDFs (reuse the CERFA + EX-17 fixtures); the deterministic mapper-guard
  rejects a hallucinated fact_key / a bogus export value / a low-confidence proposal; the verify gate
  fails a deliberately-broken mapping.
- **Mapper**: unit-test the guard/validation deterministically; the LLM call itself is mocked (no live
  LLM in CI) — the value is in the disposal logic, not the model.
- **Data-driven fill regression**: after moving `CHOICE_GROUPS` to data, the existing 36 form-fill
  tests (incl. the real-PDF CERFA + EX-17 fills) must still pass unchanged — the regression guard for
  the refactor.
- **Isolation**: `check_serving_llm_isolation.py` green with the onboarding module registered.
- **State machine**: transitions (happy path + failed + blocked + resume) covered.

## 11. Rollout

- One-time: the two schema migrations (table + columns), the `CHOICE_GROUPS`→data migration for the
  two existing forms, the engine + mapper + worker, the trigger endpoint + form-view "preparing"
  state, behind the existing `VITE_ENABLE_IMMIGRATION_FORMS` flag.
- Then: coverage grows automatically from demand; the worklist's 57 candidates are the addressable
  set; `blocked` forms (flattened / bot-walled) surface for a human, everything else self-onboards.

## 12. Risks & open questions

- **LLM mapping quality** — a wrong-but-plausible mapping that also passes verify (lands a value in the
  wrong box). Mitigation: confidence threshold tuned high, `exact_match_required` warnings surfaced,
  candidate-grade user check. Residual risk accepted per the "fully automatic, no mapping review"
  decision; revisit the threshold after the first N onboardings.
- **Source-URL quality** — the worklist's `source_url` is a citation, sometimes an info page not a
  direct PDF. acquire must handle "page, not PDF" → `blocked` with a clear reason; a later iteration
  could resolve a PDF link from the page.
- **Second-surname / country-of-birth style gaps** — fields with no governing fact stay blank
  (correct), but they cap how "complete" an auto-fill can be until the `fact_dictionary` grows.
- **Worker cadence vs. UX** — a scheduled workflow adds latency between request and `live`; acceptable
  for "prepare in the background", but if near-real-time is wanted later, a webhook-triggered run is
  the upgrade.
