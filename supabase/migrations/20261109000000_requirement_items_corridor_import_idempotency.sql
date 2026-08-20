-- Corridor-import idempotency — the natural key becomes a database constraint.
--
-- On 2026-08-15 the Norway (FR→NO) corridor import was accidentally run twice and
-- inserted duplicate requirement rows. The upsert funnel
-- (backend/app/crud.py::create_requirement_item) matches the natural key
-- (country_code, purpose, title) — but only in application code: a SELECT-then-INSERT
-- with no database constraint behind it. Two racing imports both pre-select nothing and
-- both insert; a writer that bypasses the funnel (a hand-rolled SQL load) duplicates
-- freely; and once duplicates exist, .first() serves an arbitrary one of them.
--
-- This migration makes the invariant physical:
--
--   1. DEDUPE existing duplicate (country_code, purpose, title) groups — including the
--      2026-08-15 Norway rows. The keeper is deterministic: prefer review_status
--      'approved' (live content stays live), then verification_status 'expert_verified'
--      (a human signature is never the row that gets deleted while an equal-rank clone
--      survives), then the earliest last_verified_at (the original import), then the
--      smallest id. corridor_attestation_items.requirement_item_id rows pointing at a
--      losing duplicate are re-pointed at the keeper first — counsel evidence must
--      survive — then the losers are deleted.
--
--   2. CREATE the UNIQUE index. From then on a duplicate import inserts ZERO rows:
--      crud's insert runs ON CONFLICT (country_code, purpose, title) DO NOTHING pinned
--      to this index, and the SQLite test schema declares the same constraint on the
--      model, so the double-import regression test
--      (backend/tests/test_corridor_import_idempotency.py) gates it in CI.
--
-- Verifying the historical Norway import: after this migration is applied, re-running
--   python backend/scripts/seed_requirements.py --file backend/seeds/requirements/norway.yaml
-- against production must report zero new rows (every insert hits the update branch or
-- the ON CONFLICT guard). The row-count check:
--   SELECT country_code, purpose, title, COUNT(*) FROM public.requirement_items
--    GROUP BY 1,2,3 HAVING COUNT(*) > 1;   -- must return zero rows, before AND after.
--
-- requirement_items already exists with RLS; an index adds no new surface. Idempotent —
-- the dedupe loop finds nothing on a second run and the index create is IF NOT EXISTS.
--
-- guard: column-read-ok — operator applies to production BEFORE the PR merges
-- (psql -f + `supabase migration repair --status applied 20261109000000`), same
-- procedure as 20261103/20261104/20261108. Ordering matters here more than usual: the
-- backend's insert names this index in its ON CONFLICT clause, so deploying the code
-- without the index would fail every NEW-row import loudly (never silently).

DO $$
DECLARE
  dup RECORD;
BEGIN
  FOR dup IN
    SELECT country_code, purpose, title,
           (ARRAY_AGG(id ORDER BY
                COALESCE(review_status = 'approved', false) DESC,
                COALESCE(verification_status = 'expert_verified', false) DESC,
                last_verified_at ASC,
                id ASC))[1] AS keeper_id
      FROM public.requirement_items
     GROUP BY country_code, purpose, title
    HAVING COUNT(*) > 1
  LOOP
    -- Counsel evidence survives: attestation items that reference a losing duplicate
    -- follow the requirement to its surviving row.
    UPDATE public.corridor_attestation_items cai
       SET requirement_item_id = dup.keeper_id
     WHERE cai.requirement_item_id IN (
             SELECT r.id
               FROM public.requirement_items r
              WHERE r.country_code IS NOT DISTINCT FROM dup.country_code
                AND r.purpose = dup.purpose
                AND r.title = dup.title
                AND r.id <> dup.keeper_id
           );

    DELETE FROM public.requirement_items r
     WHERE r.country_code IS NOT DISTINCT FROM dup.country_code
       AND r.purpose = dup.purpose
       AND r.title = dup.title
       AND r.id <> dup.keeper_id;
  END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_requirement_items_country_purpose_title
  ON public.requirement_items (country_code, purpose, title);
