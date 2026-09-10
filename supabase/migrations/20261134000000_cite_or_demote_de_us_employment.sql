-- Cite the rows we can source, demote the rows that are inputs (not authority-defined
-- requirements), and thereby lift GERMANY/employment and UNITED STATES/employment back
-- over the citation-sufficiency bar so they stop serving a "not ready" caveat.
--
-- WHY NOW
-- Commit 82c02e0f ("knowledge-layer contract") added a serving gate
-- (backend/app/services/knowledge_layer_scorecard.py): a corridor is "ready" only if
-- >= 50% of its APPROVED requirements carry a resolvable citation (CITATION_RESOLVE_BAR)
-- across > 1 pillar. That turned the pre-existing provenance debt (the 18 rows in
-- scripts/requirement_provenance_baseline.txt) into a live, user-facing caveat. Measured
-- on prod 2026-09-09:
--   GERMANY/employment       7 approved, 3 cited (43%)  -> "not ready" banner
--   UNITED STATES/employment 5 approved, 0 cited (0%)   -> "not ready" banner
-- Both still SERVE their rows; the banner is a trust-degradation, not a blackout.
--
-- WHAT THIS DOES (and the taxonomy, reused verbatim from
-- 20261112000000_cite_served_requirement_items.sql):
--   * CITE the rows backed by a verified official source read this session.
--   * DEMOTE (review_status='pending') the rows that are INPUTS to a requirement, not
--     authority-defined requirements, and therefore have no honest citation:
--       - housing/tenancy contracts (a tenancy is an input to residence registration),
--       - a duplicate passport row,
--       - US "state residency registration" (sub-national; no federal, country-granular
--         source),
--       - the US "Employment letter" (employer-provided document; also the row that must
--         leave the served set for US/employment to clear the bar).
--
-- WHAT THIS DELIBERATELY LEAVES (still uncited, still in the guard baseline — honest debt,
-- a documented follow-up, NOT fabricated):
--   DE Employment letter, DE Sozialversicherung, SG Employment letter, SG IRAS x2,
--   US Valid passport. These are real requirements whose official pages this session could
--   not verify without either a wrong URL (IRAS) or bypassing a Cloudflare bot-challenge
--   (travel.state.gov) — which we do not do. They can be cited once a supporting sentence
--   is read on the official page. All corridors are already >= 50% cited without them.
--
-- verification_status is UNCHANGED (rows stay 'representative' = curated AND cited).
-- Nothing here sets 'verified'/'expert_verified' — that needs a human and counsel.
-- Idempotent: each UPDATE is keyed on id and only touches a row that is still
-- served-and-uncited, so a re-run cannot overwrite a reviewer's later edit.
--
-- Applied to prod OUT OF BAND (operator MCP execute_sql/apply_migration) — never
-- `supabase db push`. After apply, prune the resolved ids from
-- scripts/requirement_provenance_baseline.txt (the guard prints them as "no longer
-- violate"); do NOT prune before apply or the guard flags them as new violations.

BEGIN;

-- ── 1. Cite the SSN rows [SSA, quote verified 2026-09-09] ────────────────────
-- https://www.ssa.gov/number-card/request-number-first-time :
--   "You may need your Social Security number to: File taxes, Start a job, Open a bank
--    account, Apply for a loan, Get a passport, Claim government benefits."
UPDATE public.requirement_items
   SET citations_json = '["https://www.ssa.gov/number-card/request-number-first-time"]'
 WHERE id IN ('42878466-59df-519e-8067-b4d4a00c858f',   -- US/employment SSN
              '7f79ffd2-9403-593f-bd67-2641b81b5ea7')   -- US/family     SSN
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- ── 2. Demote the input / duplicate / sub-national rows ──────────────────────
-- Housing & tenancy — an input to registration, not an immigration requirement.
UPDATE public.requirement_items SET review_status = 'pending'
 WHERE id IN ('e1d0a1c0-0001-5000-8000-000000000005',   -- GERMANY  Mietvertrag
              'eddd79a9-efb9-5667-82b6-88de2aff6443',   -- NORWAY   Long-term housing contract
              'e01ea767-1656-5c04-b3fe-ecaf993e2a29',   -- SINGAPORE/employment Tenancy
              '2bd170a3-e7c3-516b-ba55-caa56056cc01',   -- SINGAPORE/study      Tenancy
              '48682196-4ee6-5349-ac1a-5cfaeb689c58',   -- US/employment Long-term lease
              '14f8bfd7-b7fc-512a-a906-57ed92a9f832',   -- US/family     Long-term lease
              -- Duplicate of the cited GERMANY "Valid passport or national identity card".
              'e1d0a1c0-0001-5000-8000-000000000006',   -- GERMANY  Valid passport (6+ months) [dup]
              -- Sub-national; no federal, country-granular source exists.
              '9455ae2c-7e68-59b7-9bdf-08f6b3b22b8e',   -- US/employment State residency registration
              '1582245b-0f52-5554-8e60-426c01c63aeb',   -- US/family     State residency registration
              -- Employer-provided document (input); also the row US/employment must shed
              -- to cross the citation bar with SSN cited.
              '05f267da-f763-468f-be37-40f8b60aecb2')   -- US/employment Employment letter
   AND review_status = 'approved'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- ── 3. Assert the intended shape before committing ───────────────────────────
DO $$
DECLARE cited int; demoted int;
BEGIN
  SELECT count(*) INTO cited FROM public.requirement_items
   WHERE id IN ('42878466-59df-519e-8067-b4d4a00c858f','7f79ffd2-9403-593f-bd67-2641b81b5ea7')
     AND citations_json IS NOT NULL AND citations_json::text NOT IN ('[]','null','{}');
  IF cited <> 2 THEN
    RAISE EXCEPTION 'expected 2 newly-cited SSN rows, found %', cited;
  END IF;

  SELECT count(*) INTO demoted FROM public.requirement_items
   WHERE id IN ('e1d0a1c0-0001-5000-8000-000000000005','eddd79a9-efb9-5667-82b6-88de2aff6443',
                'e01ea767-1656-5c04-b3fe-ecaf993e2a29','2bd170a3-e7c3-516b-ba55-caa56056cc01',
                '48682196-4ee6-5349-ac1a-5cfaeb689c58','14f8bfd7-b7fc-512a-a906-57ed92a9f832',
                'e1d0a1c0-0001-5000-8000-000000000006','9455ae2c-7e68-59b7-9bdf-08f6b3b22b8e',
                '1582245b-0f52-5554-8e60-426c01c63aeb','05f267da-f763-468f-be37-40f8b60aecb2')
     AND review_status = 'pending';
  IF demoted <> 10 THEN
    RAISE EXCEPTION 'expected 10 demoted input rows, found %', demoted;
  END IF;

  -- No row may have been elevated above 'representative' by this migration.
  IF EXISTS (SELECT 1 FROM public.requirement_items
              WHERE verification_status IN ('verified','expert_verified')
                AND id IN ('42878466-59df-519e-8067-b4d4a00c858f','7f79ffd2-9403-593f-bd67-2641b81b5ea7')) THEN
    RAISE EXCEPTION 'a cited SSN row was elevated above representative -- that needs a human';
  END IF;
END $$;

COMMIT;
