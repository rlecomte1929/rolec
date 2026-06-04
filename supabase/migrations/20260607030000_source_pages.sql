-- ============================================================
-- [P0-04 / AIQ-188 follow-up] source_pages — persistent per-URL freshness table
-- Date: 2026-06-04
--
-- P0-04 shipped the Tier-1 crawler logic (fetchAndStore / detectChanges /
-- hash-based change detection) but backed it with an InMemorySourcePageStore
-- ("prod swap = PostgreSQL adapter"). The persistent table was never created,
-- which left P1-05d (AIQ-679, "Last verified" on the form card) blocked.
--
-- This migration creates the canonical current-state-per-URL table the crawler
-- writes to: one row per official source URL, holding the latest content hash
-- and the last_fetched_at timestamp that powers "Last verified".
--
-- (Distinct from public.crawled_source_documents, which is an append-per-crawl
-- history; source_pages is the deduplicated current state, keyed by url.)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.source_pages (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  url              text        NOT NULL UNIQUE,
  tier             text        NOT NULL DEFAULT '1',   -- source taxonomy tier (P0-01)
  content_hash     text,                               -- SHA-256 of extracted main text
  previous_hash    text,                               -- prior hash, set when content changes
  page_title       text,
  http_status      int,
  is_accessible     boolean    NOT NULL DEFAULT true,  -- false on 404 (record preserved)
  last_fetched_at  timestamptz,                        -- powers "Last verified" on the form card
  last_changed_at  timestamptz,                        -- last time content_hash changed
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.source_pages IS
  'Current-state freshness record per official source URL (P0-04 crawler target). last_fetched_at powers the "Last verified" date on the Dossier form card (P1-05d). Deduplicated by url; crawled_source_documents holds the per-crawl history.';

CREATE INDEX IF NOT EXISTS idx_source_pages_url ON public.source_pages(url);

-- updated_at trigger (same moddatetime pattern as the dossier tables)
DROP TRIGGER IF EXISTS handle_updated_at ON public.source_pages;
CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.source_pages
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

-- ── RLS ───────────────────────────────────────────────────────
-- Non-tenant reference data (official URLs + fetch timestamps, no PII).
-- Readable by any authenticated user; the backend reads it via the service
-- role (RLS-exempt). Anon is revoked per the public-schema hard-gate.
ALTER TABLE public.source_pages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "source_pages_authenticated_read"
  ON public.source_pages
  FOR SELECT
  TO authenticated
  USING (true);

REVOKE ALL ON public.source_pages FROM anon;

-- ── Seed: one row per official form source URL ────────────────
-- Bootstraps "Last verified" for the seeded form set. The crawler upserts
-- real fetch timestamps + hashes going forward (ON CONFLICT (url)).
INSERT INTO public.source_pages (url, tier, last_fetched_at)
SELECT DISTINCT ft.source_url, '1', now()
FROM public.form_templates ft
WHERE ft.source_url IS NOT NULL
ON CONFLICT (url) DO NOTHING;
