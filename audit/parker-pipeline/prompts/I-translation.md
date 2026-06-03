## Task body — step I

**UI impact:** Minimal. One small wrapper component `<TranslatedText>` that
inlines into existing markup, plus a single `preferred_language` field added to
the existing employee settings page. No new pages, no new top-level routes.
Reuses antigravity primitives and the existing settings page layout. Does NOT
require UI-PROPOSAL.md.

Add a neural translation layer so policy summaries, supplier briefings, and case
communications can be served in the employee's preferred language. Route between
DeepL Pro (subscription, high quality, low volume) and NLLB-200 (self-hosted, high
volume, cost-sensitive). Relocation is intrinsically multilingual — this closes a
strategic coverage gap.

### Prerequisites from prior steps

**Soft dependency on step D** (for prompt-routed translation prompts).
**Soft dependency on step G** (for cost/CO₂ accounting per translation).

Read these if present:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md` — to register translation in the
  prompt registry under the canonical task_key.
- `audit/parker-pipeline/runs/<RUN_ID>/G/RESULT.md` — to ensure translation calls
  flow `feature_key='translation'` through the trace logger.

If either is absent, fall back to direct router integration and static prompts.
Note this clearly in PLAN.md.

### Source material
- `backend/relopass/llm/router.py` — routing pattern.
- `backend/app/services/policy_assistant_rag_engine.py` — RAG pipeline pattern.
- `frontend/src/features/journey/` — employee journey wizard where translated
  outputs surface.
- `audit/parker-framework-audit.md` section 2 (W8, table in 2.4) and section 4,
  Prompt I.

### Concrete deliverables

1. Add `deepl>=1.18` to `backend/requirements.txt` (DeepL official SDK). Document
   the NLLB-200 deployment path in the ADR — likely Hugging Face Inference
   Endpoints for the open-source side, with a Modal or Replicate fallback. Do not
   add a heavy local-inference dependency to backend/requirements.txt.
2. ADR at `audit/adr/adr-002-translation-routing.md` documenting:
   - Quality vs cost tradeoff for DeepL Pro vs NLLB-200.
   - Language pair coverage and fallback rules.
   - Privacy posture: which strings may leave the EU (relevant for GDPR).
3. Migration `supabase/migrations/<timestamp>_translation_cache.sql`:
   - Table `translation_cache(
       id uuid pk,
       source_hash text not null,                  -- sha256 of (text, src, tgt, domain)
       source_text text not null,
       source_lang char(5) not null,               -- BCP-47, e.g. 'en-US'
       target_lang char(5) not null,
       domain text,                                -- 'policy'|'comm'|'supplier'|'ui'
       provider text not null,                     -- 'deepl'|'nllb'
       model_version text,
       translated_text text not null,
       quality_score numeric,
       cost_usd numeric,
       translated_at timestamptz default now()
     )`.
   - Unique on `source_hash`.
   - Index on `(target_lang, domain, translated_at desc)`.
   - **RLS enabled**: SELECT for authenticated; INSERT for the service role only.
     `REVOKE ALL ... FROM anon`.
4. Create `backend/app/services/translation_service.py`:
   - `translate(text: str, src: str, tgt: str, *, domain: str,
     quality_tier: Literal['fast', 'premium']) -> Translation` — returns
     `Translation(text, provider, model_version, cost_usd, cache_hit)`.
   - Router decision: `quality_tier='premium' OR len(text) < 500` → DeepL Pro;
     otherwise NLLB-200. Override with env var `TRANSLATION_FORCE_PROVIDER` for
     emergencies.
   - DeepL adapter (`backend/app/services/translation_deepl.py`) — wraps the
     official SDK, respects rate limits, handles glossaries (none initially).
   - NLLB adapter (`backend/app/services/translation_nllb.py`) — calls the
     hosted endpoint via HTTP. If env var `TRANSLATION_NLLB_ENDPOINT` is unset,
     return a structured error so the router can fall back to DeepL.
   - Trace every call through `ai_trace_logger` with `feature_key='translation'`
     and the cost/cost_usd field (so G's rollups work).
5. Wire into the journey flow:
   - Add `preferred_language` column to `employee_assignments` (or read from an
     existing field — check the schema first).
   - In the journey wizard, surface translated content for keys: case summary,
     next-steps, supplier briefing. Translation is opt-in via a toggle in
     employee settings.
6. Backend route `backend/app/routers/translation.py`:
   - `POST /api/translate` — body `{text, src, tgt, domain, quality_tier}`.
     Auth: session-token. Rate limit: 60/minute/user via slowapi.
   - Register in `backend/app/main.py`.
7. Frontend hook `frontend/src/api/translation.ts` and a `<TranslatedText>`
   component that fetches and renders translations with a small "translated" badge.
8. Tests:
   - `backend/tests/test_translation_service.py` — router decision rules, cache
     hit/miss, env var override.
   - `backend/tests/test_translation_deepl.py` and `test_translation_nllb.py` —
     adapter contracts with mocked HTTP responses.
   - `backend/tests/test_translation_router.py` — auth, rate limit (set
     `RELOPASS_DISABLE_RATE_LIMITS=1` per CLAUDE.md for the rest of the suite).
   - Round-trip preservation test: EN → DE → EN preserves entity names (company
     names, person names, addresses). This is the standard quality smoke test for
     translation pipelines.
   - Frontend snapshot test for `<TranslatedText>`.

### Design notes
- Translation cache is critical for cost. The same policy summary will be
  translated by hundreds of employees in a company; cache on the canonical hash.
- DeepL has stronger quality for European pairs; NLLB has wider coverage. Encode
  this in the routing decision: short strings → DeepL, long strings or rare
  pairs → NLLB.
- For NLLB hosting: do not vendor weights into the repo. Use HF Inference
  Endpoints; document the endpoint URL via env var and surface its health on the
  admin dashboard.
- Translation strings inside the product UI itself (i18n bundles) are NOT in
  scope here — they're a separate i18n task. This step is for **document content**
  translation (policies, summaries, communications).

### Out of scope
- Real-time chat translation.
- Speech translation.
- Glossaries for company-specific terminology.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; cache table enforces uniqueness on `source_hash`.
- ADR exists and links to D's and G's RESULT.md if relevant.
- `POST /api/translate` returns a Translation with cache_hit=false the first time
  and cache_hit=true the second time (verify with a fixture).
- Round-trip EN→DE→EN preserves entity names (test it on a known fixture).
