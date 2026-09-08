-- [O1] Stop showing users placeholder text as if it were an official quote.
--
-- Found while fixing the FR->NO citation resolution (20261031000000). Once real quotes started
-- rendering, the pre-existing ones became obviously wrong by comparison. Measured in production
-- 2026-08-12, immediately after that migration:
--
--     requirement items showing a source        35
--       ...showing "Stub content for <url>"     27      <-- placeholder text, rendered as evidence
--       ...whose link is example.com             6      <-- a fake domain, shown to the user
--       ...showing a real official quote         8      <-- the ones added an hour earlier
--
-- So before 20261031000000 landed, EVERY piece of visible evidence in the product was a
-- placeholder. All ten original source_records carry `snippet = 'Stub content for ' || url`, and
-- two of them point at https://example.com/. `_source_dto` passes `snippet` straight to the DTO
-- and the UI renders it under the requirement.
--
-- This is the accuracy bar, not a cosmetic issue: a fabricated quote beside a real requirement is
-- worse than no quote at all, because it looks like corroboration.
--
-- TWO DIFFERENT PROBLEMS, TWO DIFFERENT FIXES
--
-- 1. Real government URL, fake snippet (8 records). The LINK is genuine and useful; only the
--    quote is invented. Null the snippet. The user gets "here is the authority" without a
--    sentence we never read. Honest, and reversible by a real fetch later.
--
-- 2. example.com (2 records, 6 items). The URL itself is fake, so there is nothing to keep.
--    Remove the citation from the items and delete the records.
--
-- Deliberately NOT done: fetching real quotes for the eight legitimate URLs. That is content
-- work per corridor and needs the same source-checking discipline the FR->NO items got. Filed.
-- Removing a false claim needs no research; adding a true one does.

BEGIN;

-- ── 1. Real URL, invented quote: keep the link, drop the sentence ────────────────────────
UPDATE public.source_records
   SET snippet = NULL
 WHERE snippet LIKE 'Stub content for %'
   AND url NOT LIKE '%example.com%';

-- ── 2. example.com: the source itself is fake ────────────────────────────────────────────
--
-- Rebuild each affected item's citation array without the fake ids. An item left with zero
-- citations is the correct outcome: it has no evidence, and the UI should say so rather than
-- link somewhere that does not exist.
UPDATE public.requirement_items ri
   SET citations_json = coalesce(sub.rebuilt, '[]')
  FROM (
    SELECT r.id AS rid,
           jsonb_agg(c.cid ORDER BY c.ord) FILTER (
             WHERE c.cid NOT IN (SELECT id FROM public.source_records
                                  WHERE url LIKE '%example.com%')
           )::text AS rebuilt
      FROM public.requirement_items r
      CROSS JOIN LATERAL jsonb_array_elements_text(r.citations_json::jsonb)
                         WITH ORDINALITY AS c(cid, ord)
     GROUP BY r.id
  ) AS sub
 WHERE ri.id = sub.rid
   AND ri.citations_json IS DISTINCT FROM coalesce(sub.rebuilt, '[]');

DELETE FROM public.source_records WHERE url LIKE '%example.com%';

COMMIT;

-- After this, a requirement either shows a real authority link (sometimes with a real quote) or
-- shows nothing. It never shows an invented one. The eight FR->NO citations added by
-- 20261031000000 are unaffected -- their snippets are verbatim official sentences.
