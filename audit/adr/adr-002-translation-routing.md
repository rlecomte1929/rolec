# ADR-002 — Neural translation routing (DeepL Pro + NLLB-200)

- **Status:** Accepted
- **Date:** 2026-05-30
- **Context:** Parker Framework Audit, Step I (run-20260530-174625)
- **Scope:** Translation of relocation **document content** (case summaries, next-step
  actions, supplier briefings, policy/communication snippets). **Not** product i18n
  (UI strings), real-time chat, or speech translation — those are out of scope.

## Decision

Route each translation request between two backends and cache the result:

| Backend | Role | When chosen |
|---------|------|-------------|
| **DeepL Pro** | Premium quality, strong European pairs, per-character billed (~$25/1M chars) | `quality_tier == 'premium'` **OR** `len(text) < 500` |
| **NLLB-200** (self-/managed-host over HTTP) | 200-language coverage, near-zero marginal cost | Long text on the `fast` tier; anything DeepL can't cover |

- Override with env `TRANSLATION_FORCE_PROVIDER` (`deepl` | `nllb`).
- The chosen provider falls back to the other on `TranslationUnavailable` (missing API
  key / unset endpoint / transport error), so a single misconfigured backend degrades
  to the other rather than failing the request.
- Results are cached in `public.translation_cache`, deduped by `sha256(text|src|tgt|domain)`.
  A repeat is a cache hit with **zero** provider cost.

## Quality vs cost

Short snippets (the common case — a next-step line, a benefit name) go to DeepL Pro:
the per-character cost is trivial at that length and the quality is the best available
for European corridors. Long-form content on the fast tier goes to NLLB-200, where the
marginal cost is effectively zero (amortized self-host) and the quality is adequate for
informational document content. `quality_tier='premium'` forces DeepL regardless of
length for content where quality must not regress. The cache makes the steady-state cost
of repeated content (the same policy summary across a company's employees) zero.

## Language coverage + fallback chain

- DeepL Pro covers ~30 mostly-European languages at the highest quality.
- NLLB-200 covers 200 languages (FLORES-200 codes), filling every corridor DeepL misses.
- Fallback chain per request: **chosen provider → other provider → 503** (caller then
  shows the original untranslated text). BCP-47 inputs are mapped to each backend's code
  scheme (DeepL `EN`/`EN-GB`; NLLB FLORES `eng_Latn`), with a Latin-script guess for
  unknown NLLB codes so the endpoint can still attempt the pair.

## GDPR / EU privacy posture

- **DeepL Pro** processes data on EU infrastructure and (on the Pro/API plan)
  contractually does not retain text after translation — acceptable for relocation
  document content under GDPR processor terms.
- **NLLB-200** is self-/EU-managed-hosted (e.g. a Hugging Face Inference Endpoint in an
  EU region), keeping content in-region and under our control. **No heavy local-inference
  dependency** is added to the backend image — NLLB is reached over HTTP only.
- **Cache contents** (`source_text` + `translated_text`) are document-content PII-class
  data: RLS is authenticated-read only, inserts are service-role only, and `anon` is
  revoked (the anon key ships in the frontend bundle). See the migration
  `20260601100000_translation_cache.sql`.
- The cache is **non-tenant-scoped** by design (identical generic source text → one row,
  shared across companies). If tenant isolation is later required for a sensitive domain,
  add `company_id` to the hash input and an RLS scoping predicate — a forward-compatible
  change that does not alter the public API.

## NLLB-200 deployment note

NLLB-200 is expected to run behind `TRANSLATION_NLLB_ENDPOINT` as a **Hugging Face
Inference Endpoint** (or equivalent managed GPU endpoint) in an EU region, with an
optional bearer token in `TRANSLATION_NLLB_TOKEN`. The backend never loads the model
locally; when the endpoint is unset the adapter raises `TranslationUnavailable` and the
router falls back to DeepL. `deepl>=1.18` is the only new backend dependency.

## Cost accounting (relationship to Step G)

Real provider spend is recorded on `translation_cache.cost_usd` and emitted on one
structured JSON trace line per translation with `feature_key='translation'`. DeepL/NLLB
bill **per character**, not per token, so Step G's token→CO2e estimator is intentionally
**not** used here. When Step G merges, adding `'translation'` to its `FeatureKey` Literal
lets the same trace line feed the AI-unit-economics rollup with no schema change.

## Consequences

- New env vars: `DEEPL_API_KEY`, `TRANSLATION_NLLB_ENDPOINT`, `TRANSLATION_NLLB_TOKEN`
  (optional), `TRANSLATION_FORCE_PROVIDER` (optional). All absent → endpoint returns 503,
  cache stays empty, nothing else breaks.
- One new public table (`translation_cache`) under the RLS hard gate; one opt-in column
  (`case_assignments.preferred_language`).
- The `deepl` SDK and `requests` are lazy-imported in the adapters so the service loads
  (and CI runs) without live keys; tests mock the adapters.
