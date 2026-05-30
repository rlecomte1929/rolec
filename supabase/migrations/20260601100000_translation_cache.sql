-- Parker-I: Neural translation layer cache (DeepL Pro + NLLB-200)
-- ─────────────────────────────────────────────────────────────────────────────
-- Caches document-content translations (case summaries, next-steps, supplier
-- briefings, policy/comm snippets) keyed by a sha256 of (text, src, tgt, domain).
-- A repeated translation is a cache hit with zero provider cost. The backend writes
-- through the service role only; the frontend never inserts.
--
-- The cache is intentionally NON-tenant-scoped: identical source text translated by
-- any company yields the same row (generic document content). Authenticated read is
-- acceptable for this content class — see ADR-002 for the privacy rationale and the
-- path to tenant isolation (add company_id to the hash + an RLS scoping predicate)
-- should it ever be required.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.translation_cache (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  source_hash     TEXT        NOT NULL,                       -- sha256(text|src|tgt|domain)
  source_text     TEXT        NOT NULL,
  translated_text TEXT        NOT NULL,
  source_lang     CHAR(5)     NOT NULL,                       -- BCP-47 (e.g. 'en', 'de-CH')
  target_lang     CHAR(5)     NOT NULL,
  domain          TEXT        CHECK (domain IN ('policy', 'comm', 'supplier', 'ui')),
  provider        TEXT        NOT NULL CHECK (provider IN ('deepl', 'nllb')),
  model_version   TEXT,
  quality_score   NUMERIC,
  cost_usd        NUMERIC,
  translated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedup key — one row per unique (text, src, tgt, domain).
CREATE UNIQUE INDEX IF NOT EXISTS uq_translation_cache_source_hash
  ON public.translation_cache (source_hash);

-- Lookup by freshness within a corridor/domain (cache analytics, invalidation sweeps).
CREATE INDEX IF NOT EXISTS idx_translation_cache_lang_domain_time
  ON public.translation_cache (target_lang, domain, translated_at DESC);

-- ── Row Level Security (CLAUDE.md hard gate: ENABLE + policy + REVOKE anon) ──────
ALTER TABLE public.translation_cache ENABLE ROW LEVEL SECURITY;

-- Service role full access (backend writes/reads through here).
CREATE POLICY "translation_cache_service_all"
  ON public.translation_cache FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Any authenticated user may read cached translations (shared, non-tenant content).
CREATE POLICY "translation_cache_authenticated_read"
  ON public.translation_cache FOR SELECT
  USING (auth.role() = 'authenticated');

-- Defense-in-depth: the anon key is shipped in the frontend bundle.
REVOKE ALL ON public.translation_cache FROM anon;
GRANT SELECT ON public.translation_cache TO authenticated;

COMMENT ON TABLE  public.translation_cache              IS 'Parker-I: neural translation cache (DeepL Pro + NLLB-200), dedup by source_hash';
COMMENT ON COLUMN public.translation_cache.source_hash  IS 'sha256 of (source_text, source_lang, target_lang, domain)';
COMMENT ON COLUMN public.translation_cache.provider     IS 'Which backend produced this translation: deepl | nllb';
COMMENT ON COLUMN public.translation_cache.cost_usd     IS 'Real provider spend (per-character billed); feeds Step G AI unit economics';

-- ── Employee opt-in target language ─────────────────────────────────────────────
-- Per-employee preferred language for auto-translated journey content. NULL = no
-- auto-translation (opt-in). Lives on the existing per-employee assignment table, so
-- no new-table RLS gate applies — existing case_assignments RLS already covers it.
ALTER TABLE public.case_assignments
  ADD COLUMN IF NOT EXISTS preferred_language CHAR(5);

COMMENT ON COLUMN public.case_assignments.preferred_language IS 'Parker-I: opt-in BCP-47 target language for auto-translated journey content (NULL = off)';
