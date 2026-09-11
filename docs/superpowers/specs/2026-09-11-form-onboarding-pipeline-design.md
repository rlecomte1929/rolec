# Design — On-demand form-onboarding pipeline

**Date:** 2026-09-11 · **Spec version:** 3.0 (reconciled after two reviews)
**Status:** approved direction; pre-implementation · **Author:** Romain + Claude

> **Review history.** v1 → repo-blind **standards review** (spec + web standards): accepted the
> architecture, flagged that the trust model proved less than it claimed. v2 folded in its four blockers
> (semantic gate, immutable version vs logical form, SSRF acquisition, durable queue). v2 → **code-grounded
> review** (Cursor, repo-attached, PR #2296): approved-with-changes and caught several v2 assumptions about
> *this repo* that would break the live FR/ES fill path. **v3 reconciles both.** The trust model stands;
> the code picture is corrected. Key v3 corrections: `form_id` stays the public/API/Storage handle (no
> re-key); `form_prefill_service` is the **live fill path**, not authoring, and the isolation guard must be
> extended to cover it; only **radios** move out of code (date-parts are already `format_rule` data);
> publish is Storage-then-atomic-DB-pointer (no cross-store transaction; never `upsert` the live key); the
> **worklist is a search index, not the acquisition allowlist** (it contains tax forms §12 forbids); the
> **first PR is data-driven fill on the current `form_id` key**, not the 7-table foundation.

## 1. Problem

ReloPass can auto-fill a real government form from a case's data — proven on the France-Visas CERFA
14571-*05 (#2286–#2288) and the Spanish EX-17/TIE (#2292, #2294). Adding each form was a manual routine
(acquire → verify AcroForm → enumerate → hand-map to a governed fact → seed `form_field_mappings` →
hand-code radios → upload PDF → test). The harvest names ~57 coded-PDF candidates across 35 corridors in
~20 languages. Hand-onboarding does not scale.

**Goal:** when a user needs a not-yet-onboarded form, the system prepares its fillable template in the
background — automatically — while proving correctness strongly enough for government documents.

## 2. Goals / non-goals

**Goals** — automatic onboarding (acquire → analyze → map → verify → publish → live), no per-form human
loop; robustness from *automated proof* (hardened acquisition, deterministic guards, a 4-gate
verification, precision-over-recall); LLM-assisted mapping in a **new authoring package**; demand-driven
trigger; per-form config becomes data within a versioned supported grammar.

**Non-goals / explicit boundaries**
- Not flattened / XFA / `/Ch` dropdown / signature PDFs — each → a distinct capability/block code (§7).
- Not bot-walled sources (France-Visas 403s) — auto-`blocked_source_access`; a human-supplied PDF resumes.
  **The FR CERFA pilot path is resume-from-committed-fixture, not auto-fetch.**
- Not extending the `fact_dictionary`; the mapper only targets facts that already exist, and **must refuse
  any fact flagged `professional_review_required`** (tax residency, PE, A1, etc. — the flag is the hook).
- **Not a relocation-wide data model.** This is an immigration-form authoring subsystem. Tax, payroll,
  social-security, benefits, housing facts are out of scope and must not be inferred from immigration
  facts (§12). Notably the acquisition allowlist is *not* the worklist, which contains tax forms.
- Not System A (`form_templates` / coordinate-overlay `FormEditorPage`) — `form_definitions` is System B's
  logical-form table, not joined to `form_templates`.
- Not the full versioning/queue/provenance schema at once — v3 leads with a fill-compat first PR (§15).

## 3. Trust model (unchanged from v2 — the core)

v1's gate proved a field **exists and accepts a value**, not that the value answers the **right question**
(`place_of_birth` → the nationality box passes it; and `reconcile_report_against_pdf` only checks `/V` is
non-empty — it does not compare expected vs actual, so a two-field swap still reads "filled"). The model
is therefore:

> authoritative source validated → PDF safely parsed → LLM proposes → deterministic type/fact guards →
> **semantic-evidence gate** → structural + sentinel round-trip + rendering verification → immutable
> version published → active pointer switched atomically.

Two invariants make "no human review" defensible: **precision over recall — blank beats wrong** (ambiguous
→ left blank, never guessed; extends "never invent" to the *mapping decision*); and the user always
reviews a **candidate-grade draft** naming source, edition, retrieval date, and every blank/review field.

## 4. Data model (corrected: `form_id` stays the handle; additive)

`form_field_mappings` is keyed on a string `form_id` (`FR_cerfa_14571_v2024`) which is **also** the
Storage object name `{form_id}.pdf` and the id in the HR/employee API and the SPA. **`form_id` stays the
public handle.** Do not re-key to a version id — that would break `_load_field_mappings`,
`get_available_forms`, `generate_prefilled_pdf`, `_download_template`, the `immigration_forms` router, and
`frontend/src/api/immigrationForms.ts` in one deploy (this repo has no apply-on-merge, so code would ship
before DDL applies). Versioning is layered **additively**.

**Change 1 — additive columns on `form_field_mappings` (first schema PR):**
- `field_kind TEXT NOT NULL DEFAULT 'text'` ∈ `text | date_part | single_radio | checkbox_option`
  (existing rows unchanged).
- `transform_spec JSONB` — typed, schema-validated, the structured successor to open `format_rule`
  strings. Note **date-parts are already data** (`format_rule` = `date_day|date_month|date_year`,
  seeded in `20261137000000`); `transform_spec` is a *rename/typing* of that, plus it carries the radio
  enum map. The guard proves every enum value is defined by the bound dictionary and every export state
  exists in the parsed PDF.
- (optional, nullable) `form_version_id TEXT` — no FK until the version table exists.

**Change 2 — radios move from code to data.** Only the radio/checkbox layer is code today
(`CHOICE_GROUPS`, `RadioField`); FR/ES radios are deliberately *not* in `form_field_mappings`.
`build_choice_fill` learns to read `field_kind in (single_radio, checkbox_option)` rows and their
`transform_spec`. **Kept in code:** the synonym normaliser `_canonical_choice` (`femme`→`F`,
`marié`→`MARRIED`), the `CHECKBOX_ON` sentinel and `_resolve_checkbox_states` (which rewrites the sentinel
to the template's real on-state — real CERFA is `/On`). `transform_spec` stores the code→export map, not
the synonyms. The text plan (`_load_field_mappings`) must **exclude** `field_kind in (single_radio,
checkbox_option)` so choice rows aren't double-written.

**Versioning (a LATER phase, additive):** two tables — `form_definitions` (logical form: `authority`,
`country_iso`, `official_code`, `active_version_id`) and `form_versions` (immutable edition: `pdf_sha256`,
`artifact_key`, `status ∈ candidate|verified|live|superseded|retired`, `valid_from/to`, `retrieved_at`,
`last_checked_at`, `source_url`) + the nullable `form_version_id` FK. Demand (`form_demands`), queue
(`form_onboarding_requests` + leases), and provenance (`form_onboarding_stage_runs`, `mapping_runs`,
`verification_runs`) come with the phases that use them (§15) — queue tables are useless before the worker.

**Fact join.** The mapper targets a `fact_key`; the fill reads a `vault_field_path` (a bare
`imm_employee_profiles` column). These differ — `fact_dictionary.lookup` joins them via
`prefill_source` tail / `field_id`. Persist `vault_field_path` on the mapping row (as today) and record
the `fact_key` in mapping provenance; do not assume they are the same string.

**Fact-dictionary version.** `fact_dictionary.py` has **no** version/hash column. Compute a version as a
hash of the module (or a frozen JSON dump) at mapping time and store it in `mapping_runs`; do not add a
column that doesn't exist or claim the dictionary is versioned.

**RLS / migrations.** Every new public table gets RLS + policy + `REVOKE ALL … FROM anon` — use
`ai_decisions` as the template, **not** `form_field_mappings` (which lacks the `REVOKE anon`; do not copy
it, and consider fixing it separately). Timestamps beat both repo and prod ledger max; the applier is
jammed (`MIGRATIONS_FAILED`) and operator-applied, so a large table set is a real cost — hence the
phasing. The merge gate for "don't read a column before its migration applies" is
`scripts/check_column_read_before_apply.py` (not the PG16 lane); the PG16 `_AUTHORITATIVE_DDL` list is
**curated** — register a migration there only if you add `@pytest.mark.postgres` tests that replay it.

## 5. State machine

Public lifecycle: `candidate → acquiring → analyzing → mapping → verifying → publishing → live →
superseded → retired`; hold/fail branches with machine-readable codes: `blocked_source_access`,
`blocked_unsupported`, `quarantined_security`, `failed_transient` (backoff), `failed_permanent`. Worker
execution state (lease, current stage) lives on the queue row + append-only stage runs, never in the
lifecycle enum.

## 6. Secure acquisition (SSRF boundary — runs on GitHub Actions, not Render)

Treat the fetch as hostile. The **allowlist is curated server-side immigration-authority host data — not
the worklist** (the worklist is a heuristic search index that includes tax forms). Controls (all in a GH
Actions `ubuntu-latest` job, where timeouts/limits/`apt` tools are available; Render is free/spin-down and
must not run this): HTTPS + authority-origin allowlist; DNS/IP validation rejecting loopback/RFC-1918/
link-local/metadata; per-hop redirect validation or disabled redirects; connection/read timeouts and max
bytes/pages/objects before parsing (`%PDF` magic is a format check, not a security check); quarantine +
isolated parse with pypdf limits; only then promote bytes to an immutable `form_version` artifact.

## 7. Analyze (capability classification)

`pypdf.get_fields()` + page widget annotations → a capability profile + per-field inventory (FQ name,
`/FT`, flags, widgets, page, bbox, export/appearance states, `/MaxLen`, default) with **explicit XFA /
signature / `/Ch` / encrypted / malformed detection**, each → a distinct `blocked_unsupported` code, never
mislabeled "flattened". Label extraction (widget bbox ↔ page text, multilingual, reading-order) is
specified with tests; ambiguity lowers mapping evidence.

## 8. Map (LLM in a new authoring package — proposes; code disposes)

`backend/app/authoring/form_onboarding/mapper.py` — a **new package** (`backend/app/authoring/` does not
exist yet; keep it off `backend/app/services/` so serving roots can't import it). It runs only at
onboarding time.
- **Input = form metadata only** + the bound fact-dictionary (hash-versioned). No case data (structural);
  `mask_pii` backstop; a PII-canary test proves zero case values reach the prompt/logs.
- If it imports `llm_client` it is already covered by the isolation gateway list; if it calls a provider
  over raw HTTP it must be registered as a gateway.
- **Structured output** validated to a JSON schema; every run records provider, model id, `prompt_hash`,
  `guard_version`, input hash, and the fact-dictionary hash it bound to.
- **Deterministic disposal** rejects: a `fact_key` not in the dictionary; a `professional_review_required`
  fact (refuse — §2/§12); a `transform_spec` enum/type the fact doesn't permit; an export state not in
  the PDF; a field name not present; anything below the evidence bar. Rejected → left blank.
- **Evidence, not raw confidence** — acceptance needs corroboration (name↔label agreement, value-type
  match, gold-fixture correctness, benchmark-calibrated per language), recorded on the mapping.

## 9. Verify (four independent gates — all mandatory)

1. **Structural** — every accepted mapping's field + export states exist in the PDF.
2. **Sentinel round-trip** — a **new helper** (not `reconcile_report_against_pdf`, which only checks `/V`
   non-empty): fill each mapped text/date field with a *unique* sentinel, re-read it from the *expected*
   field, and assert the value matches **and appears in no other field** (catches swaps). Sentinels
   respect `/MaxLen`; for radios/checkboxes write the **real export state** (`/Hombre`), not a random
   string.
3. **Semantic evidence** — the mapping's evidence meets policy; a deliberately plausible-but-wrong fixture
   must fail here even though the field exists. Zero tolerance on critical identity/document fields.
4. **Rendering** — a reference-renderer smoke check (poppler/pdfium in the GH image) shows synthetic
   values display (guards appearance-stream/`NeedAppearances` breakage). Deferred until the GH image has a
   renderer.

Any mandatory gate failing → `failed_*`, never `live`.

## 10. Register + publish (Storage-then-atomic-DB-pointer; no cross-store transaction)

Postgres and Supabase Storage are **separate systems** — there is no transaction spanning both, and
today's helpers `upsert: true` the live `{form_id}.pdf` (mutable — the opposite of immutable versions).
The safe sequence:
1. Upload to a **new immutable key only, no upsert**: `form-templates/versions/{form_definition_id}/{sha256}.pdf`
   (an existing object at that hash = idempotent success). Never overwrite/delete a hash object; never
   `upsert` a live key.
2. Verify bytes + run all gates against that object.
3. INSERT the version-scoped mapping rows + `form_versions` row (`status=verified`) in **one short** DB
   transaction (statements tiny — `statement_timeout` applies; never hold a txn across the upload/LLM).
4. UPDATE `form_definitions.active_version_id` (+ prior → `superseded`) in a **second short** transaction
   — this pointer swap is the atomic commit. A crash before it leaves the previous live version + its
   serving object untouched. Rollback = point `active_version_id` back (DB-only, atomic).
5. The serving key `{form_id}.pdf` stays as-is until `_download_template` learns `artifact_key`; if a
   compat copy is written it happens *after* the pointer swap and never deletes the old hash object.

## 11. Durable queue + worker

The **database is the authoritative queue** (`FOR UPDATE SKIP LOCKED` — unused in-repo today but correct
on the 6543 transaction-mode pooler **iff** claim+lease is one short transaction that commits *before*
any fetch/LLM; do not use `pg_advisory_lock`/`LISTEN`/`SET`/holding `FOR UPDATE` across HTTP — those break
on 6543). Claim: select one due row (non-terminal, `next_attempt_at ≤ now`, lease free/expired), set
`lease_owner`/`lease_expires_at`, commit, then work; transitions are compare-and-set on (status + lease).
Expired lease → reclaimable; `next_attempt_at` + bounded backoff for transient; permanent doesn't retry.

**Executor = GitHub Actions** (not Render). Reuse `outbox-dispatch.yml`'s `schedule` + `workflow_dispatch`
+ `concurrency` (schedule is the recovery **sweep** since GH schedules can be delayed/dropped;
event-dispatch is the fast path), and `immigration-indexer.yml`'s Python setup. Secrets: a dedicated
**GitHub Environment** (`form-onboarding-worker`) holding `OPENAI_API_KEY` + `SUPABASE_SERVICE_ROLE_KEY`
(Storage goes through the service-role client) + a `DATABASE_URL` (6543, same rewrite as the app). SHA-pin
actions, minimal `GITHUB_TOKEN`. A least-privilege DB role (like `relopass_api`) is a **human follow-up,
not a v1 blocker** — default to the isolated service key in that Environment. The queue is correct
independently of the scheduler; the UX promises no hard latency.

## 12. Demand trigger, API, and relocation boundary

**API — extend `immigration_forms.py`, don't greenfield.** It is already dual-registered
(`backend/main.py` + `backend/app/main.py`) and the SPA (`immigrationForms.ts`) posts a string `form_id`.
Keep `form_id` as the id in the employee contract; a new `form_definition_id` surface is a breaking
frontend change and should wait for a compat alias. Add, on the existing dual-registered router,
object-level-auth'd + idempotency-keyed + rate-limited endpoints to enqueue an onboarding request and read
its `public_stage` with **stable reason codes** (never raw exceptions/paths). The browser identifies the
trusted logical form; the server resolves source/authority from the authorized case + the curated
allowlist (removes the SSRF surface from the API). The form-view shows "Preparing your form…" / an honest
blocked reason (never a dead button), polling with bounded backoff.

**Relocation boundary (explicit).** This subsystem owns immigration-form facts only. It must not infer tax
residence, payroll/social-security applicability, benefits, or housing/domicile from immigration data. The
mapper's refusal of `professional_review_required` facts is the enforcement hook; the acquisition allowlist
being immigration-authority-only (not the tax-containing worklist) is the second. Monetary facts (if ever
mapped) are `{decimal, ISO-4217, period, effective dates}`; temporal facts distinguish `LocalDate` from
`Instant + IANA zone id`.

## 13. Hard gates (all must hold)

1. **Isolation covers the fill path.** Add a `FILL_ROOTS` (or add `backend.app.services.form_prefill_service`
   — and optionally `backend.app.routers.immigration_forms`) to `check_serving_llm_isolation.py`; prove a
   planted mapper import from the fill path fails CI. (The current guard does **not** cover fill; v2's
   claim was wrong.) The mapper is also unreachable from every existing `SERVING_ROOT`.
2. No case PII to the LLM (structural) + `mask_pii`/`safe_log_text`; PII-canary test.
3. LLM proposes; deterministic typed guards validate against the bound dictionary hash + parsed PDF;
   `professional_review_required` facts refused; only evidence-passing mappings register.
4. All four verification gates pass before `live`; a plausible-but-wrong fixture is rejected.
5. Never invent / blank beats wrong; output candidate-grade.
6. Acquisition SSRF/limit controls enforced (on GH Actions) + tested; allowlist ≠ worklist.
7. Publish is Storage-then-atomic-DB-pointer; never `upsert` a live/hash key; queue claim is one short
   pooler-safe transaction; crash-recovery tested.
8. RLS + policy + `REVOKE anon` on every new table (`ai_decisions` template); `check_column_read_before_apply`
   respected; new routes dual-registered with a **route-parity test**.
9. Full append-only provenance (source artifact, mapping run w/ model/prompt/guard/dict-hash, verification
   report) reconstructable from durable records.

## 14. Testing

Regression: the **36 fill tests across five files** (`test_imm11_form_prefill` 16, `test_form_choice_fill`
11, `test_fr_cerfa_real_acroform` 4, `test_fr_cerfa_real_pdf_fill` 2, `test_es_ex17_real_pdf_fill` 3) —
the choice tests are **DB-free** (call `build_choice_fill` directly), so the refactor must inject mapping
rows / a test double; "behaviour identical" is the bar, **not** "zero test edits". New families:
acquisition-security, PDF-parser (incl. XFA/`/Ch`/signature/encrypted), semantic-mapper (incl.
wrong-but-plausible must-reject), verification (swap, truncation, unicode, leap day), state-machine
(crash/lease/supersede/rollback), API/auth (BOLA, idempotency, rate-limit, sanitized codes), migration
(old-app/new-schema), privacy (PII canary). Metric = **precision, not recall** (pilot: zero critical
semantic errors on the gold set; accepted-field precision ≥ 99%).

## 15. Roadmap (fill-compat first; disprove the code risk before the version/queue/LLM risk)

| Phase | Scope | Exit |
|---|---|---|
| **0 Spec** | this v3 | approved |
| **1a First PR — data-driven fill on the `form_id` key** | (i) add `form_prefill_service` as a fill root in the isolation guard + prove a planted mapper import fails CI; (ii) one additive migration: `field_kind` + `transform_spec` (no new tables, no re-key, don't SELECT the new cols in the same PR) | migration is a clean additive file |
| **1b Move radios to data (after operator apply)** | `build_choice_fill` reads `single_radio`/`checkbox_option` rows for FR/ES on `form_id`; keep `_canonical_choice` + `_resolve_checkbox_states`; seed radio rows as data | **36 fill tests green, behaviour identical**; FR/ES still fill; isolation covers fill |
| **2 Logical form + versions** | two tables (`form_definitions`, `form_versions`) + nullable FK; immutable artifact key + `_download_template` learns `artifact_key`; keep `{form_id}.pdf` compat | FR/ES resolve via active version; serving unchanged |
| **3 Secure acquisition + parser** | GH Actions fetch w/ allowlist/SSRF/limits + capability classifier + immutable store | security + unsupported corpus pass; CERFA path = fixture-resume |
| **4 Mapping engine** | structured LLM output in `app/authoring/`, typed fact guards (refuse regulated), evidence + provenance (`mapping_runs`) | deterministic guard tests + multilingual benchmark |
| **5 Verification platform** | structural + sentinel round-trip + semantic + render gates (`verification_runs`) | wrong-but-plausible rejected |
| **6 Queue + worker + API** | `form_onboarding_requests` + leases + stage runs; `form_demands`; GH Actions Environment worker; enqueue/status endpoints on `immigration_forms.py` | parallel/crash tests pass; states observable |
| **7 Controlled pilot** | EX-17 (auto-acquire) + CERFA (**fixture-resume**) + a diverse small set incl. one expected-`blocked` | zero critical semantic errors; targets met |
| **8 Demand rollout** | eligible worklist candidates behind the flag | SLO + freshness monitoring stable |
| **9 Source governance** | revalidation, new-edition detection, rollback | new edition onboards without mutating the old |

## 16. Open questions (safe default each)

Semantic-evidence policy/thresholds (tune on the gold set, Phase 5); source-freshness SLO (Phase 9);
multiple valid editions (model `valid_from/to`); LLM provider/model + geography (provider-agnostic +
recorded metadata; note form metadata still leaves the platform even though case PII doesn't);
least-privilege worker role (dedicated GH Environment + service key default, DB role a human follow-up);
retention/deletion + DPIA (assess before rollout; separate source/mapping audit from case-PII retention);
`source_url` = info page not PDF (classify → blocked; resolve link later); who may resume a browser-blocked
acquisition (restricted operator action, audited); fact-dictionary gaps stay blank until it grows (a
separate human decision). Also: fix the pre-existing missing `REVOKE anon` on `form_field_mappings`.

## 17. Change control

Platform changes (supported field kinds, transform grammar, source-trust model, LLM policy, publish gates,
fact semantics) → reviewed PR with a spec-version bump + migration/API/privacy/security impact + rollback +
tests. Per-form onboarding stays automatic within the reviewed capability; a form outside it is correctly
`blocked`, and expanding the platform is a normal engineering change, not an ad-hoc exception.
