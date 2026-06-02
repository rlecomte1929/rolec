# Step I RESULT — Neural translation layer (DeepL Pro + NLLB-200)

_Run: run-20260530-174625 | Branch: audit/parker-step-I-translation_

## Summary
Shipped a document-content translation layer (NOT product i18n) that routes between
**DeepL Pro** (premium quality, short/European text) and **NLLB-200** (self-/managed-host
over HTTP, 200-language coverage, long-form) and caches every result. Routing: a request
goes to DeepL when `quality_tier='premium'` OR the text is < 500 chars; otherwise to
NLLB; `TRANSLATION_FORCE_PROVIDER` overrides; the chosen provider falls back to the other
on `TranslationUnavailable` (missing key / unset endpoint). Results are deduped in
`translation_cache` by `sha256(text|src|tgt|domain)` — a repeat is a cache hit with zero
provider cost. Real spend is recorded on `translation_cache.cost_usd` and on a structured
JSON trace line (`feature_key='translation'`) so it slots into Step G's AI-unit-economics
rollup once that merges (DeepL/NLLB are per-character billed, so G's token→CO2e estimator
is intentionally not used — see deviation #1). A thin `POST /api/translate` route (session
auth, 60/min/user) exposes it; a minimal `<TranslatedText>` frontend wrapper renders
translated content with a "Translated" badge, plus an opt-in `preferred_language` field in
employee settings. The `deepl` SDK and `requests` are lazy-imported in the adapters so the
service loads (and CI runs) without live keys; tests mock the adapters.

## Files changed
```
 backend/app/main.py                                   |   2 +
 backend/app/models.py                                 |  23 +++
 backend/app/rate_limits.py                            |   8 +
 backend/app/routers/translation.py                    |  70 ++++++ (new)
 backend/app/services/translation_service.py           | 145 +++++++++ (new)
 backend/app/services/translation_deepl.py             |  63 ++++++ (new)
 backend/app/services/translation_nllb.py              |  76 ++++++ (new)
 backend/app/services/translation_cache_repo.py        |  61 ++++++ (new)
 backend/app/services/translation_types.py             |  25 ++++ (new)
 backend/requirements.txt                              |   3 +
 backend/tests/test_translation_service.py             | 136 ++++++++++ (new)
 backend/tests/test_translation_deepl.py               |  85 +++++++ (new)
 backend/tests/test_translation_nllb.py                |  90 +++++++ (new)
 backend/tests/test_translation_router.py              | 138 ++++++++++ (new)
 frontend/src/api/translation.ts                       |  29 ++++ (new)
 frontend/src/components/TranslatedText.tsx            |  65 ++++++ (new)
 frontend/src/components/__tests__/TranslatedText.test.tsx | 60 +++++ (new)
 frontend/src/features/platform-v2/settings/SettingsScreen.tsx | 27 +++
 supabase/migrations/20260601100000_translation_cache.sql | 68 ++++++ (new)
 audit/adr/adr-002-translation-routing.md              |  86 ++++++ (new)
```
_(Against the PR base `feature/sec-004-rate-limit-coverage`, not `main` — this step stacks
on the pre-merge pipeline base like D–H.)_

## Tests added
- `backend/tests/test_translation_service.py` (9 tests) — routing (short→deepl, long→nllb,
  premium-forces-deepl, env override), cache hit/miss (second identical call →
  `cache_hit=True`, zero cost, exactly one row), domain is part of the cache key,
  provider fallback on `TranslationUnavailable`, raises when no provider available, blank
  text is a no-op. Adapters monkeypatched to deterministic fakes; persistence on in-memory
  SQLite built from the ORM Base.
- `backend/tests/test_translation_deepl.py` (4 tests) — SDK mocked via an injected fake
  `deepl` module: missing key → `TranslationUnavailable`; per-character cost + model
  version; source strips region / target keeps it (`en-US`→`EN`, `en-GB`→`EN-GB`); SDK
  exception → `TranslationUnavailable`.
- `backend/tests/test_translation_nllb.py` (5 tests) — `requests.post` monkeypatched:
  unset endpoint → `TranslationUnavailable`; posts FLORES codes (`en`→`eng_Latn`) and
  parses; unknown lang → Latin-script guess; empty response → unavailable; transport error
  → unavailable.
- `backend/tests/test_translation_router.py` (7 tests) — real router over a minimal FastAPI
  app with `dependency_overrides`/in-memory SQLite: unauth → 401; first POST
  `cache_hit=false`, second identical POST `cache_hit=true` (same text, zero cost);
  **round-trip EN→DE→EN preserves entity names** (Berlin, ReloPass); empty text → 422;
  bad domain → 422; both providers down → 503; SEC-004 `/api/translate` per-user bucket
  allows exactly 60 then blocks (`TRANSLATE_LIMIT="60/minute"`).
- `frontend/src/components/__tests__/TranslatedText.test.tsx` (4 tests) — renders original
  immediately; shows translation + "Translated" badge on success; falls back to original
  (no badge) on API error; skips translation when target === source.

## Test result
- pytest (translation suite): **25 passed** (`test_translation_service` +
  `test_translation_deepl` + `test_translation_nllb` + `test_translation_router`, 0.58s).
- pytest (existing `test_rate_limit_coverage.py`, re-run after the `rate_limits.py` edit):
  **12 passed** — the new `/api/translate` bucket did not disturb SEC-004 coverage.
- Regression check (collect-only over all `backend/tests`): **2038 tests collected, 10
  pre-existing collection errors** — all in legacy `services.*` un-migrated import-path
  files (`test_employee_policy_resolution`, `test_guidance_pack`, `test_official_ingest`,
  etc., AUDIT-A9.3). **Zero of the errors are translation-related**; my new files collect
  cleanly. `from backend.app.main import create_app; create_app()` imports + wires the
  translation router with no error.
- vitest (`TranslatedText.test.tsx`): **4 passed**.
- tsc: **pass** (`cd frontend && npx tsc --noEmit`, exit 0).

## Migration applied?
- File: `supabase/migrations/20260601100000_translation_cache.sql` — **NOT applied.** Left
  for human review → MCP `apply_migration` (`supabase db push` blocked by ~95-row history
  drift, per repo workflow).
- RLS posture (CLAUDE.md hard gate satisfied for the one new public table):
  - `translation_cache`: RLS **enabled**. `translation_cache_service_all` (FOR ALL,
    service_role) + `translation_cache_authenticated_read` (FOR SELECT, authenticated —
    shared non-tenant cache; rationale in ADR-002). `REVOKE ALL ... FROM anon` ✓;
    `GRANT SELECT ... TO authenticated`. UNIQUE index on `source_hash`.
  - `case_assignments.preferred_language` — **column add only** (`ADD COLUMN IF NOT
    EXISTS`), not a new table; the existing `case_assignments` RLS already covers it.

## New routes
| Method | Path | Auth gate | Rate limit | Router file |
|--------|------|-----------|-----------|-------------|
| POST | /api/translate | get_current_user (session token) | 60/min/user (SEC-004 `rate_limits.path_limit`) | backend/app/routers/translation.py |

Returns `{text, provider, model_version, cost_usd, cache_hit}`. 503 when no provider is
configured/reachable so the caller degrades to showing the original text.

## New tables / schema changes
- `translation_cache` — `id uuid pk default gen_random_uuid()`, `source_hash text not null`
  (UNIQUE), `source_text text not null`, `translated_text text not null`,
  `source_lang char(5) not null`, `target_lang char(5) not null`, `domain text` check
  (`policy|comm|supplier|ui`), `provider text not null` check (`deepl|nllb`),
  `model_version text`, `quality_score numeric`, `cost_usd numeric`,
  `translated_at timestamptz default now()`. Indexes: UNIQUE `(source_hash)`,
  `(target_lang, domain, translated_at desc)`.
- `case_assignments.preferred_language char(5)` — opt-in BCP-47 target language for
  auto-translated journey content (NULL = off).

## Configuration / env vars added
- `DEEPL_API_KEY` — DeepL Pro API key (adapter raises `TranslationUnavailable` if unset).
- `TRANSLATION_NLLB_ENDPOINT` — base URL of the hosted NLLB-200 endpoint (unset → adapter
  unavailable → router falls back to DeepL).
- `TRANSLATION_NLLB_TOKEN` — optional bearer for the NLLB endpoint.
- `TRANSLATION_FORCE_PROVIDER` — optional `deepl`|`nllb` override of the routing rule.
- New dependency: `deepl>=1.18` in `backend/requirements.txt` (lazy-imported). NLLB needs
  no new dep — reached over HTTP via the existing `requests`.

## UI changes summary
- New routes added: none (no new top-level route — the prompt explicitly says this does
  not require UI-PROPOSAL.md).
- New components added: `<TranslatedText>` (`frontend/src/components/TranslatedText.tsx`) +
  the `frontend/src/api/translation.ts` API wrapper.
- Existing antigravity components reused: `Badge` (`variant="info" size="sm"` → "Translated").
- Settings: added an opt-in `Preferred language` `<select>` to the Profile tab
  (`SettingsScreen.tsx`, native control matching the page's existing input styling).
- UI-PROPOSAL.md status: **not required** per the task body (minimal wrapper + one field).

## Deviations from the original audit prompt
1. **Cost/trace via `translation_cache.cost_usd` + structured JSON log, not Step G's
   `TraceSession`.** G is unmerged and token-LLM-shaped (per-token → CO2e); translation is
   per-character billed, so G's estimator is a poor fit even once merged. The trace line
   carries `feature_key="translation"`, so adding `'translation'` to G's `FeatureKey`
   Literal later ingests it into the AI-unit-economics rollup with **zero schema change**.
   (Soft-dep fallback, explicitly permitted by the prompt: "If either is absent, fall back
   to direct router integration … Note this clearly in PLAN.md.")
2. **Step D (prompt registry) is non-applicable, not a gap.** Translation via DeepL/NLLB is
   not a templated LLM prompt call, so there is no prompt to register; no fallback needed.
3. **Rate limit added in `rate_limits.py path_limit()`, not a slowapi route decorator.**
   SEC-004 moved all buckets to the request middleware because slowapi 0.1.9 requires a
   literal `request` param; following that pattern keeps `/api/translate` consistent and
   needs no `backend/main.py` edit (the middleware already calls `path_limit()` for every
   request).
4. **`preferred_language` column lives on `case_assignments`**, the actual per-employee
   assignment table (`employee_assignments` named in the prompt is a function-name
   fragment, not a table — no such table exists).
5. **Settings `preferred_language` field is state-wired only.** The settings page is
   pre-existing mock-only (no real persistence API — `onSaveProfile` is a mock callback);
   durable save is out of scope. See Known gaps.

## What downstream steps will need from this step
- **Step G (when it merges)**: add `'translation'` to its `FeatureKey` Literal to ingest
  the per-translation trace line (`feature_key='translation'`, `provider`, `chars`,
  `cost_usd`, `cache_hit`) and the `translation_cache.cost_usd` column into the
  `GET /api/admin/ai-unit-economics` rollup. No code change needed here.
- **Frontend consumers**: import `<TranslatedText text src tgt domain />` to render any
  document snippet translated to the viewer's `preferred_language`; it degrades to the
  original on error and never blocks content. API contract: `POST /api/translate`
  `{text, src, tgt, domain, quality_tier}` → `{text, provider, model_version, cost_usd,
  cache_hit}`.

## Known gaps / follow-ups
- **Settings persistence is mock-only** — the `preferred_language` field is wired to local
  state and the translation flow, but durable save needs the (out-of-scope) settings API.
  Map to a Notion AI Work Queue follow-up when the settings backend lands.
- **Journey-content wiring is the wrapper, not a full rollout** — `<TranslatedText>` is the
  reusable primitive; wiring it into every journey card (case summary, next-steps, supplier
  briefing) end-to-end + reading the employee's `preferred_language` is a follow-up once
  the settings persistence exists.
- **Migration not applied** — left for human MCP `apply_migration` review (1 new public
  table; RLS hard-gate satisfied + 1 column add).
- **Live providers not exercised in CI** — adapters lazy-import `deepl`/`requests` and are
  mocked in tests; real DeepL/NLLB calls need keys + a hosted endpoint (ADR-002).
- **Full local suite is known-red** (pre-existing legacy `services.*` collection errors,
  AUDIT-A9.3) — out of scope; this branch adds no new failures or errors.
