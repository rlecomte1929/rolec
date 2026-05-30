# Step I PLAN — Neural translation layer (DeepL Pro + NLLB-200)

_Run: run-20260530-174625 | Branch (to create): `audit/parker-step-I-translation` (forks from base `feature/sec-004-rate-limit-coverage` @ 81d98bc8)_

## Task understanding

Build a **document-content translation layer** (NOT product i18n) that routes between two
backends and caches results:

- **DeepL Pro** — premium quality, low volume, strong European pairs. Used for short text
  and any `quality_tier='premium'` request.
- **NLLB-200** — self-hosted/HF-hosted, high volume, 200-language coverage. Used for long
  text on the `fast` tier, and anything DeepL can't cover.

The layer translates relocation **document content**: case summaries, next-step actions,
supplier briefings, policy/communication snippets. Results are cached (dedup by content
hash) with provider + cost recorded. A thin API route exposes it; a minimal frontend wrapper
(`<TranslatedText>`) renders translated content with a "Translated" badge, gated by an opt-in
`preferred_language` field on the employee.

## Upstream alignment (soft deps D and G)

Per `PROMPT.md`: "If either [D prompt-registry or G carbon/cost trace] is absent, fall back to
direct router integration and static prompts. Note this clearly in PLAN.md."

- **Step D (prompt registry)** — on branch `audit/parker-step-D-*`, **absent from base tree**.
  Translation via DeepL/NLLB is not a templated LLM prompt call, so the prompt registry does
  not apply at all. No fallback needed; no dependency. (Noted as non-applicable, not a gap.)
- **Step G (carbon + AI unit economics)** — on branch `audit/parker-step-G-*`, **absent from
  base tree**. G's `TraceSession(..., feature_key=...)` is token-LLM-shaped (tokens_in/out →
  CO2e) and requires a `feature_key` Literal that base's `ai_trace_logger` does not have.
  DeepL/NLLB billing is **per-character**, not per-token, so G's estimator is a poor fit even
  once merged. **Fallback:** record real spend on the `translation_cache.cost_usd` column and
  emit one structured JSON trace log line per translation with `feature_key="translation"`,
  `provider`, `chars`, `cost_usd`, `cache_hit`. This is DB-free and forward-compatible — when
  G merges, `'translation'` can be added to its `FeatureKey` Literal and the same log line
  feeds the rollup with no schema change. **Deviation documented below.**

## File-by-file change list

### Backend — new files
- `backend/app/services/translation_service.py` — public `translate(text, src, tgt, *, domain,
  quality_tier) -> Translation`. Routing rule: `quality_tier=='premium' OR len(text) < 500` →
  DeepL; else NLLB. Env override `TRANSLATION_FORCE_PROVIDER` (`deepl`|`nllb`). Cache lookup
  before call, cache write after. Emits the structured trace log line. `Translation` dataclass:
  `(text, provider, model_version, cost_usd, cache_hit)`.
- `backend/app/services/translation_deepl.py` — DeepL adapter. Lazy-imports `deepl` SDK inside
  the call (mirrors H's numpy/scipy lazy-import so the module imports cleanly without the dep).
  Reads `DEEPL_API_KEY`. Cost = chars × DeepL per-char rate constant. Raises a typed
  `TranslationUnavailable` when key/SDK absent so the router can fall through.
- `backend/app/services/translation_nllb.py` — NLLB adapter. HTTP POST (lazy-import `requests`)
  to `TRANSLATION_NLLB_ENDPOINT`. If endpoint unset → raise `TranslationUnavailable` so the
  service falls back to DeepL. Cost = self-host amortized constant (near-zero) × chars.
- `backend/app/services/translation_cache_repo.py` — portable repo (text UUID ids, works on
  SQLite for tests). `get_by_hash(session, source_hash)`, `insert(session, row)`,
  `compute_hash(text, src, tgt, domain)` = sha256.
- `backend/app/routers/translation.py` — `POST /api/translate`. Auth: `get_current_user`
  (session token). Body `{text, src, tgt, domain, quality_tier}`. Returns the `Translation`
  serialized + `cache_hit`.

### Backend — edits
- `backend/requirements.txt` — add `deepl>=1.18`.
- `backend/app/main.py` — `include_router(translation.router)`.
- `backend/app/rate_limits.py` — add `TRANSLATE_LIMIT = "60/minute"` and a per-user bucket for
  `/api/translate` in `path_limit()`. **No `backend/main.py` edit needed** — the SEC-004
  middleware already calls `path_limit()` for every request, so a new per-user bucket
  auto-applies. (This is why we route the limit through `path_limit` rather than a slowapi
  decorator — slowapi 0.1.9 needs a literal `request` param; see SEC-004 RESULT.)

### Migration
- `supabase/migrations/20260601100000_translation_cache.sql` — see schema below. Plus
  `ALTER TABLE employee_assignments ADD COLUMN preferred_language char(5)` (opt-in target lang;
  NULL = no auto-translation). `employee_assignments` already exists, so the column add is not
  a new-table RLS gate; existing table RLS already covers it.

### Frontend — new files
- `frontend/src/api/translation.ts` — `translateText(req): Promise<Translation>` via
  `apiPost('/api/translate', body)` (mirrors `frontend/src/api/cases.ts`).
- `frontend/src/components/TranslatedText.tsx` — fetches translation for `{text, src, tgt,
  domain}`, renders translated text + `<Badge variant="info" size="sm">Translated</Badge>`.
  Renders the original while loading / on error (graceful degradation).
- Snapshot/RTL test for `<TranslatedText>`.

### Frontend — edits
- Employee settings (`frontend/src/features/platform-v2/settings/SettingsScreen.tsx`) — add a
  `preferred_language` Select (reuse existing antigravity `Select.tsx`). NOTE: this page is
  currently mock-only (no real API persistence — pre-existing gap); I add the field + state
  and note the persistence gap in Known gaps rather than building a new settings API in scope.

### ADR
- `audit/adr/adr-002-translation-routing.md` — quality vs cost; language coverage + fallback
  chain; GDPR/EU privacy posture (DeepL Pro EU data processing, NLLB self-host keeps PII
  in-region; cache stores source+translated text → treat as document-PII, RLS authenticated-
  read only); NLLB-200 deployment note (HF Inference Endpoints; no heavy local-inference dep).

### Tests
- `backend/tests/test_translation_service.py` — routing (short→deepl, long→nllb,
  premium-forces-deepl, env override), cache hit/miss (second call cache_hit=true, one row),
  NLLB-unavailable → DeepL fallback. Fake adapters via monkeypatch (no network, no real keys).
- `backend/tests/test_translation_deepl.py` — mocked `deepl.Translator`; asserts char-count
  cost + model_version; SDK-absent → `TranslationUnavailable`.
- `backend/tests/test_translation_nllb.py` — mocked `requests.post`; endpoint-unset →
  `TranslationUnavailable`; success path parses response.
- `backend/tests/test_translation_router.py` — over in-memory SQLite (monkeypatched
  `SessionLocal`): unauth → 401; first POST cache_hit=false, second identical POST
  cache_hit=true; round-trip EN→DE→EN preserves capitalized entity tokens (deterministic fake
  adapter that echoes entities). Rate-limit assertion uses `RELOPASS_DISABLE_RATE_LIMITS`
  toggle semantics (bucket presence asserted directly in rate_limits test instead of hammering).
- `frontend/src/components/__tests__/TranslatedText.test.tsx` — `vi.mock('../../api/translation')`;
  renders translated text + badge; renders original on error.

## New tables and migration plan

`translation_cache` (NEW public table → full RLS hard gate):
- `id uuid pk default gen_random_uuid()`
- `source_hash text not null` (sha256 of text|src|tgt|domain) — **UNIQUE**
- `source_text text not null`, `translated_text text not null`
- `source_lang char(5) not null`, `target_lang char(5) not null` (BCP-47)
- `domain text` check in (`policy`,`comm`,`supplier`,`ui`)
- `provider text not null` check in (`deepl`,`nllb`)
- `model_version text`, `quality_score numeric`, `cost_usd numeric`
- `translated_at timestamptz default now()`
- Index on `(target_lang, domain, translated_at desc)`
- **RLS (hard gate):**
  - `ENABLE ROW LEVEL SECURITY`
  - `translation_cache_authenticated_read` — `FOR SELECT TO authenticated USING (true)`
    (cache is shared, non-tenant — translated document snippets, read-only to logged-in users;
    privacy rationale in ADR).
  - `translation_cache_service_write` — `FOR INSERT TO service_role WITH CHECK (true)` (writes
    only ever happen through the backend SessionLocal/service role; frontend never inserts).
  - `REVOKE ALL ON public.translation_cache FROM anon;`

`employee_assignments.preferred_language` — column add only; not a new table; existing RLS
covers it.

## New routes
| Method | Path | Auth | Rate limit | Router |
|--------|------|------|-----------|--------|
| POST | /api/translate | get_current_user (session token) | 60/min/user (rate_limits.path_limit) | backend/app/routers/translation.py |

## Risks and unknowns
- **DeepL/NLLB not callable in CI** (no keys, deepl SDK + live endpoint absent). Mitigated by
  lazy-import + typed `TranslationUnavailable` + monkeypatched fakes in every test (mirrors H).
- **Settings persistence is mock-only** today — the `preferred_language` field is wired to
  local state + the translation flow, but durable save needs the (out-of-scope) settings API.
  Documented as a Known gap, not silently half-built.
- **Cache is non-tenant shared.** A translated policy snippet cached by company A is readable
  (via the API/RLS authenticated-read) by company B if they translate identical source text.
  This is acceptable for generic document content but is called out in the ADR; if tenant
  isolation is later required, add `company_id` to the hash + an RLS scoping predicate.

## Deviations from the original audit prompt
1. **Cost/trace via `translation_cache.cost_usd` + structured JSON log, not G's TraceSession.**
   G is unmerged and token-LLM-shaped (per-token CO2e); translation is per-character. Log line
   carries `feature_key="translation"` so it slots into G's rollup once `'translation'` is added
   to its `FeatureKey` Literal — zero schema change. (Soft-dep fallback, per prompt.)
2. **Rate limit added in `rate_limits.py path_limit()`, not a slowapi route decorator.** SEC-004
   moved all buckets to the middleware because slowapi 0.1.9 requires a literal `request` param;
   following that established pattern keeps `/api/translate` consistent and needs no main.py edit.
3. **`deepl` and `requests` lazy-imported inside the adapters** so the service module imports
   cleanly without the SDK/network, and tests `monkeypatch`/mock them (mirrors H's numpy/scipy).
4. **Settings `preferred_language` field is state-wired only** (page is pre-existing mock-only);
   durable persistence deferred — noted in Known gaps.
