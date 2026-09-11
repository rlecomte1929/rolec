# Design — On-demand form-onboarding pipeline

**Date:** 2026-09-11 · **Spec version:** 2.0 (hardened after external technical review)
**Status:** approved direction; pre-implementation · **Author:** Romain + Claude

> **v2 changelog.** A deep external review (repo-blind, spec + standards grounded) accepted the
> architecture but flagged that the v1 trust model proved less than it claimed. v2 folds in its four
> blockers — a semantic-verification gate, logical-form vs immutable-version lifecycle, a hardened
> (SSRF-aware) acquisition boundary, and a transactional durable queue/publish — plus the high-value
> provenance, typed-schema, and PDF-taxonomy points. Enterprise-grade items beyond ReloPass's current
> stage (full multi-domain relocation data model, DPIA, multi-tenant NFR/RTO/RPO tables) are recorded
> as explicit non-goals / later phases rather than first-build scope. The riskiest assumptions are
> disproven in a controlled pilot before demand-driven rollout (§13 roadmap).

## 1. Problem

ReloPass can auto-fill a real government form from a case's data — proven on the France-Visas CERFA
14571-*05 (#2286–#2288) and the Spanish EX-17/TIE (#2292, #2294). But *adding* each form was a manual
routine (acquire PDF → verify AcroForm → enumerate fields → hand-map to governed `fact_key` → seed
`form_field_mappings` → hand-code radios → upload PDF → test). The harvest names **498 forms across 35
corridors** (`docs/form-autofill/form-acquisition-worklist.md`); ~57 are coded-PDF candidates in ~20
languages. Hand-onboarding does not scale.

**Goal:** when a user needs a not-yet-onboarded form, the system prepares its fillable template in the
background — automatically — so coverage expands from demand without per-form engineering, *while
proving correctness strongly enough for legal/government documents*.

## 2. Goals / non-goals

**Goals**
- Automatic onboarding (acquire → analyze → map → verify → publish → live), no human in the per-form loop.
- Robustness from *automated proof*: a hardened acquisition boundary, deterministic mapping guards, a
  **multi-gate verification** (structural + round-trip + semantic + rendering), and precision-over-recall.
- LLM-assisted mapping (authoring layer) that generalises across languages without hand-tuning.
- Demand-driven trigger; the form lights up when ready.
- Per-form config is data; onboarding writes no code (within a versioned *supported* field grammar).

**Non-goals (this iteration — explicit boundaries)**
- **Not** flattened / non-AcroForm PDFs (no fillable fields), XFA, choice (`/Ch`) dropdowns, or signature
  fields — each gets a distinct capability/block code (§6); they are not mislabeled "flattened".
- **Not** bot-walled sources that refuse a plain HTTPS fetch (France-Visas 403s) — auto-`blocked`; a
  human-supplied PDF resumes the form. No headless browser in the pipeline this iteration.
- **Not** extending the governed `fact_dictionary`; the mapper only targets facts that already exist.
- **Not** a relocation-wide data model. This is an **immigration-form authoring subsystem**. Tax,
  payroll, social-security, benefits, and housing facts are *out of scope and must not be inferred from
  immigration facts* — §12 defines the boundary. (Tax residence ≠ immigration residence; A1/posting
  rules depend on work location/duration — those belong to other domains, effective-dated.)
- **Not** the full enterprise version/audit entity model at once — v2 ships a pragmatic core (§4) and
  names the target as a later phase.
- **Not** System A / System B unification.

## 3. Trust model (the central v2 change)

The v1 gate — "the LLM proposes, deterministic guards check the target exists, the fill lands
(`0 not_in_pdf`)" — proves a field **exists and accepts a value**, not that the value answers the
**right question**. A plausible-but-wrong mapping (`place_of_birth` → the nationality box) passes it.
For a government form that is not acceptable as the sole publish gate. v2 changes the model to:

> authoritative source validated → PDF safely parsed → LLM proposes → deterministic type/fact guards →
> **semantic-evidence gate** → structural + sentinel round-trip + **rendering** verification →
> immutable version published → active pointer switched atomically.

Two invariants make "no human review" defensible:
- **Precision over recall — blank beats wrong.** When evidence is ambiguous, the field is left blank
  (the user completes it), never guessed. This extends the existing "never invent" invariant to the
  *mapping decision*, not just the value.
- **The user always reviews a candidate-grade draft** that names the source, edition, retrieval date,
  and every intentionally-blank / review-needed field, before submitting. Candidate framing does not
  waive the automatic gates.

## 4. Data model

v2 separates six concepts the v1 single JSONB row conflated: **logical form**, **immutable version**,
**user demand**, **onboarding work + stage history**, **mapping decision**, **verification evidence**.
A pragmatic core ships first; the fuller entity model (external review §"revised data model") is the
target for the audit/versioning phase.

**Core tables (v2 first build):**
- `form_definitions` — a logical authority procedure across editions: `authority`, `country_iso`,
  `official_code`, `canonical_name`, `active_version_id` (nullable → the currently-live version).
- `form_versions` — an **immutable** acquired edition: `form_definition_id`, `authority_version`,
  `language_tag`, `pdf_sha256`, `artifact_key` (immutable, hash-addressed — see below), `status`
  (`candidate | verified | live | superseded | retired`), `valid_from/valid_to`, `retrieved_at`,
  `last_checked_at`, `source_url`, `final_url`.
- `form_onboarding_requests` — the **durable queue / worker execution state** for a version being
  prepared: `form_definition_id`, `status` (§5 lifecycle), `attempts`, `next_attempt_at`,
  `lease_owner`, `lease_expires_at`, `error_code`, `error_detail`, timestamps.
- `form_onboarding_stage_runs` — **append-only** per-stage history: `request_id`, `stage`, `attempt`,
  `status`, `software_version`, `error_code`, `output` (jsonb). Never mutated → reproducible decisions.
- `form_demands` — **demand ≠ work**: `form_definition_id`, `case_id`, `requested_by`, `created_at`.
  Many demands → one onboarding work unit (so N cases needing the same form share the work and each
  keeps its own audit trail).
- Mapping/verification provenance: `mapping_runs` (model/provider, `prompt_hash`, `guard_version`,
  `fact_dictionary_version`, threshold) and `verification_runs` (`structural_pass`, `roundtrip_pass`,
  `semantic_pass`, `render_pass`, report). Append-only.

**Immutable artifacts.** The PDF is stored hash-addressed and never overwritten:
`form-templates/versions/{form_definition_id}/{sha256}.pdf`. The DB says which version is active; the
object store is never both the id and the mutable source of truth. A new edition = a new
`form_version`, not an overwrite.

**`form_field_mappings` becomes version-scoped + typed:**
- keyed to `form_version_id` (not a bare `form_id`).
- `field_kind` ∈ `text | date_part | single_radio | checkbox_option` (default `text`; existing rows
  unchanged).
- **`transform_spec` (jsonb, typed + schema-validated)** replaces open-ended `format_rule` + ad-hoc
  `choice_config`. Examples:
  ```json
  {"type":"date_component","source_type":"local_date","component":"month","representation":"zero_padded_numeric"}
  {"type":"enum_to_pdf_state","source_enum":"person.gender","mapping":{"male":"/Hombre","female":"/Mujer"}}
  ```
  The guard proves every `source_enum` value is defined by the bound `fact_dictionary` version and every
  PDF export state actually exists in the parsed form.

`build_choice_fill` (and the date-part rules) refactor to read these version-scoped typed rows **instead
of the hardcoded `CHOICE_GROUPS` dict**; the FR CERFA + ES EX-17 groups migrate to data. The existing
**36 form-fill tests are the regression guard** — behaviour must be identical. `form_prefill_service` is
System B / authoring, not a serving root, so this does not touch the serve/LLM isolation boundary.

**Migrations.** One-time schema migrations create the new tables (each with RLS + policy +
`REVOKE anon`) and the version-scoping/`transform_spec` columns, following the timestamp/apply rules and
registering ALTERs in the PG16-parity lane; do not merge code that SELECTs new columns before apply.
Per-form registration after that is service-role **data** writes, not migrations.

## 5. State machine

Public lifecycle (on `form_onboarding_requests.status`), distinct from lease/stage execution state:

`candidate → acquiring → analyzing → mapping → verifying → publishing → live → superseded → retired`

Failure/hold branches (machine-readable reason codes, not free-form): `blocked_source_access` (bot-wall,
404, non-PDF), `blocked_unsupported` (flattened/XFA/`/Ch`/signature/encrypted), `quarantined_security`
(SSRF/limit tripwire), `failed_transient` (retryable, backoff), `failed_permanent`. A formal transition
table is part of the implementation plan. Transient "worker is mapping now" lives in the lease + a
`stage_run`, never in the lifecycle enum.

## 6. Secure acquisition (untrusted-remote-resource boundary)

Treat the fetch as hostile even from a "trusted" catalog. Controls, all test-covered (§14):
- **Origin allowlist** — only HTTPS and an approved authority-domain allowlist (curated server-side,
  *not* client-supplied). A URL off-allowlist → `blocked_source_access`.
- **IP / redirect validation** — resolve DNS and reject loopback / RFC-1918 / link-local /
  cloud-metadata targets; validate every redirect hop against the same rules, or disable redirects.
- **Resource limits** — connection/read timeouts; max bytes / pages / objects; reject before parsing.
  `%PDF` magic is a format check, not a security check.
- **Quarantine + isolated parse** — store to a quarantine slot, parse in a constrained worker with
  pypdf's decompression/object limits enabled; a parser failure fails safe → `blocked_unsupported`.
Only after these pass is the bytes promoted to an immutable `form_version` artifact + `pdf_sha256`.

## 7. Analyze (capability classification, not just field count)

`pypdf.get_fields()` + page widget annotations (they are distinct structures; radio groups appear as
parent field + child widgets). Produce a **capability profile** and per-field inventory: fully-qualified
name, `/FT`, flags, widgets, page, bounding box, appearance/export states, `/MaxLen`, default value,
and **explicit detection of XFA, digital signatures, `/Ch` choice controls, encrypted, and malformed
field trees** — each → a distinct `blocked_unsupported` code, never mislabeled "flattened". Supported
shapes → the field inventory that mapping consumes. Label extraction (widget bounding box ↔ page text
spans, normalized, reading-order, multilingual) is specified with its own tests; ambiguous labels lower
mapping evidence rather than being silently trusted.

## 8. Map (LLM authoring — proposes; code disposes)

`app/authoring/form_onboarding/mapper.py`, the only new LLM caller, runs **only at onboarding time**.
- **Input = form metadata only** (field names, labels, types, states) + the bound `fact_dictionary`
  version. No case data — structural guarantee; `pii_masker` chokepoint kept as backstop.
- **Structured output** validated against a JSON schema; every invocation records provider, model id,
  `prompt_hash`, `guard_version`, input hash, output-schema version, and the `fact_dictionary_version`
  it was bound to (reproducibility).
- **Deterministic disposal** rejects any `fact_key` not in the dictionary, any `transform_spec` whose
  source enum/type the fact doesn't permit, any export state not present in the PDF, any field name not
  present, and anything below the evidence bar. Rejected → field left unmapped (blank).
- **Evidence, not raw confidence.** A model's self-reported confidence is not calibrated across
  languages; acceptance requires *corroborating evidence* (field-name ↔ label agreement, value-type
  match, benchmark-calibrated policy per language/form-family), recorded on the `field_mapping`.

## 9. Verify (four independent gates — all mandatory to publish)

1. **Structural** — every accepted mapping's field + export states exist in the PDF.
2. **Round-trip with sentinels** — fill each mapped field with a *unique* sentinel (`first_name=ALPHA17`,
   `nationality=BETA29`, …) and re-read it from the *expected* field/widget; a field swap becomes
   observable (zero mismatches required).
3. **Semantic evidence** — the mapping's evidence (label semantics, name agreement, gold-fixture
   correctness for critical fields) meets the policy. A deliberately plausible-but-wrong fixture must
   **fail** here even though the target field exists. Critical identity/document fields have zero
   tolerance.
4. **Rendering** — a reference-renderer smoke check shows the synthetic values actually display (guards
   appearance-stream/`NeedAppearances` breakage), for a defined supported-viewer profile.

Any mandatory gate failing → `failed_*`, never `live`.

## 10. Register + publish (atomic, non-destructive)

Registration never destructively replaces the active version. The worker: writes the immutable artifact
+ the version-scoped mapping rows for a *new* `form_version` (status `candidate`), runs verification →
`verified`, then **transactionally switches `form_definitions.active_version_id`** to the new version
(→ `live`, prior → `superseded`). A crash between steps leaves the previous live version untouched and
the candidate re-runnable. Rollback = point `active_version_id` back at a prior `verified` version, no
re-onboarding.

## 11. Durable queue + worker

The **database is the authoritative queue**; the executor is replaceable.
- **Claiming** — a worker selects one due request (`status` non-terminal, `next_attempt_at ≤ now`,
  lease free/expired) via `FOR UPDATE SKIP LOCKED`, sets `lease_owner` + `lease_expires_at`, commits,
  *then* does network/LLM work. State transitions are compare-and-set on (expected status + lease owner).
- **Recovery** — an expired lease makes a crashed item reclaimable; no duplicate publication (publish is
  atomic, §10). `next_attempt_at` + bounded exponential backoff + jitter for `failed_transient`;
  permanent failures don't retry forever.
- **Executor** — a **GitHub Actions** run (event-triggered on new demand *plus* a scheduled recovery
  sweep — GH schedules can be delayed/dropped, so the sweep is the safety net), with a concurrency group.
  It holds the LLM key + a **least-privilege worker DB/storage identity** (not the broad Supabase service
  key where avoidable; the service key bypasses RLS, so it's isolated to one workflow/environment,
  SHA-pinned actions, minimal `GITHUB_TOKEN`, rotated, log-redacted). The DB queue is correct
  independently of the scheduler; the UX makes **no hard latency promise**.

## 12. Demand trigger, API, and relocation-domain boundary

**Trigger + API.** The browser identifies the **trusted logical form** it needs — it never sends a
`source_url`/authority (server resolves those from the authorized case + the allowlisted catalog; this
removes the SSRF surface from the API). Endpoints (dual-registered in `backend/app/main.py` *and*
`backend/main.py`; object-level auth on every call; idempotency-key; per-user rate limit so a refresh
storm can't spawn unbounded LLM/worker work):
- `POST /api/employee/cases/{case_id}/immigration/forms/{form_definition_id}/onboarding` → `202` with
  `{request_id, public_stage:"preparing", joined_existing_work, retry_after_seconds}`, or `200` with the
  live `form_version` if already live.
- `GET .../forms/{form_definition_id}/onboarding-status` → `{public_stage, progress, retry_after_seconds}`
  with **stable reason codes** (`SOURCE_REQUIRES_BROWSER`, …), never raw exceptions / stack traces /
  bucket paths. The form-view shows "Preparing your form…" and, on failure, an honest reason — never a
  dead button. Frontend uses bounded backoff polling.

**Relocation-domain boundary (explicit).** This subsystem owns *immigration-form* facts only. It must
**not** infer tax residence, payroll/social-security applicability, benefits eligibility, or housing/
domicile from immigration data. Those are separate domains, effective-dated, owned elsewhere; this
pipeline consumes only governed `fact_dictionary` facts and leaves anything it can't source blank. A
governed fact used here should carry (or defer to the dictionary's) semantic owner, jurisdiction, and
validity semantics — e.g. `country_of_residence` has distinct immigration/tax/payroll/mailing meanings
and must not be treated as interchangeable. Monetary facts (if ever mapped) are `{decimal, ISO-4217
currency, period, effective dates}`, never a bare number; temporal facts distinguish `LocalDate`
(legal date) from an `Instant + IANA zone id` (appointment), never a fixed offset.

## 13. Hard gates (all must hold)

1. Mapper import-unreachable from every `SERVING_ROOT` **and** the fill path — `check_serving_llm_isolation.py`.
2. No case PII to the LLM (structural) + `mask_pii`/`safe_log_text` backstop; a **PII-canary test** proves
   a synthetic-PII case yields zero case values in the serialized prompt/logs.
3. LLM proposes; deterministic typed guards validate every proposal against the bound dictionary version +
   the parsed PDF; only evidence-passing mappings register.
4. All four verification gates pass before `live`; a plausible-but-wrong fixture is rejected.
5. Never invent / **blank beats wrong** — unmapped or ambiguous fields stay blank; output is candidate-grade.
6. Acquisition SSRF/limit controls (§6) enforced and tested; parser runs constrained.
7. Publish is atomic + non-destructive; queue claiming is transactional with leases; crash-recovery tested.
8. RLS + policy + `REVOKE anon` on every new public table; migration + PG16-parity discipline; dual router
   registration + a **route-parity test**; least-privilege worker credential.
9. Full append-only provenance — an operator can reconstruct source artifact, mapping run
   (model/prompt/guard/dictionary version), and verification report for any live version from durable
   records, not mutable logs.

## 14. Testing

Beyond the current happy-path fixtures (which stay as regression), test families:
- **Acquisition security** — official PDF · HTML-not-PDF · 403 · redirect to approved/unapproved host ·
  loopback/RFC-1918/link-local/metadata · oversized · timeout · bad TLS · misleading content-type ·
  `%PDF`+malformed.
- **PDF parser** — CERFA · EX-17 · flattened · XFA · encrypted · malformed tree · duplicate/hierarchical
  names · repeated widgets · radio · checkbox · `/Ch` · signature · readonly/required · max-length.
- **Semantic mapper** — correct multilingual labels · ambiguous · duplicate label · misleading name ·
  unknown fact · wrong value-type · radio enum mismatch · **wrong-but-plausible target (must reject)**.
- **Verification** — missing field · wrong export state · write-to-wrong-semantic-field · appearance
  missing · truncation · unicode/accents · leap day · locale date components.
- **State machine** — happy path · block · transient/permanent failure · resume after human-staged PDF ·
  worker crash · lease expiry · retry exhaustion · new authority version · supersession · rollback.
- **API & auth** — duplicate POST (idempotent) · multi-case shared demand · unauthorized case (BOLA) ·
  unknown/unsupported form · rate-limit · sanitized blocked message.
- **Migration** — old-app/new-schema, existing mappings untouched, code rollback with expanded schema.
- **Privacy** — PII canary absent from prompt/logs · audit access restricted · secret redaction.
- **Fill regression** — the 36 existing tests pass unchanged after the `CHOICE_GROUPS`→data refactor.
- **Isolation** — `check_serving_llm_isolation.py` green with the mapper registered.

Quality metric = **precision, not recall**: pilot target zero critical-field semantic errors on the gold
set; accepted-field precision ≥ 99%, coverage sacrificed when uncertain.

## 15. Roadmap (disprove the riskiest assumptions first)

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 Spec hardening** | this v2 (lifecycle, versions, threat model, semantic gate, boundaries) | approved |
| **1 Schema foundation** | logical form / immutable version / demand≠work / stage history / leases / provenance; version-scoped typed `form_field_mappings` | parity + backward-compat tests pass; existing forms unchanged |
| **2 Data-driven fill refactor** | `CHOICE_GROUPS` + date-parts → typed data | **36 fill tests pass, no behaviour change** |
| **3 Secure acquisition + parser** | allowlist/SSRF controls/limits; capability classifier; immutable artifact store | security + malformed/unsupported corpus pass |
| **4 Mapping engine** | structured LLM output, typed fact guards, evidence + provenance | deterministic guard tests + multilingual benchmark |
| **5 Verification platform** | structural + sentinel round-trip + semantic + render gates | wrong-but-plausible fixtures rejected |
| **6 Worker + API** | durable leases/retries; idempotent, auth'd, rate-limited API; event exec + recovery sweep | parallel/crash tests pass; states observable |
| **7 Controlled pilot** | CERFA + EX-17 **plus a deliberately diverse small set** (languages, authorities, radio/checkbox, multi-page, one expected-`blocked`) | zero critical semantic errors; precision/reliability/cost targets met |
| **8 Demand-driven rollout** | eligible worklist candidates behind the flag | SLO + source-freshness monitoring stable |
| **9 Source governance** | revalidation, new-edition detection, candidate creation, rollback | new authority version onboards without mutating/losing the old |

## 16. Open questions (decide before the phase that needs them)

Recorded so unknowns don't vanish into implementation choices; each has a safe default:
- **Semantic-evidence policy & thresholds** — the core residual risk; tune on the gold set (Phase 5).
- **Source-freshness SLO** — how often to revalidate an authority artifact (per-form risk; Phase 9).
- **Multiple valid editions simultaneously?** — model `valid_from/to` + allowed editions, don't assume one.
- **LLM provider/model + geography** — provider-agnostic interface, recorded model metadata; document
  vendor/data-residency (case PII is excluded by design, but form metadata still leaves the platform).
- **Least-privilege worker identity** — dedicated DB/storage role vs. isolated service key (Phase 6).
- **Latency SLO** — none promised until an execution SLO exists; Actions cadence is "background".
- **Retention/deletion + whether a DPIA is required** — assess before rollout; keep source/mapping audit
  retention separate from case-PII retention.
- **`source_url` = info page, not a direct PDF** — acquire must classify "page not PDF" → blocked; a later
  iteration resolves the PDF link from the page.
- **Who may manually resume a browser-blocked acquisition** — restricted operator action, recording actor,
  timestamp, original source, replacement SHA.
- **Fact-dictionary gaps** (second surname, country-of-birth, …) — stay blank until the dictionary grows
  (a separate, human decision — extending it is not in this pipeline).

## 17. Change control

Two levels. **Platform changes** (supported field kinds, transform grammar, source-trust model, LLM
provider/model policy, publish gates, fact semantics) go through a reviewed PR with a spec-version bump +
migration/API/privacy/security impact + rollback + tests. **Per-form onboarding stays automatic** — a new
form/edition within the reviewed capability needs no code and no manual mapping approval; a form outside
it is correctly `blocked`, and expanding the platform to support it is a normal engineering change, not an
ad-hoc exception.
