-- Give eight served requirement_items a real, verified citation, and stop serving
-- three rows that no authority defines.
--
-- WHY
-- `requirements_builder` serves rows with review_status='approved'. Measured on prod
-- 2026-08-20: 89 served rows, of which 29 carried NO citation at all. All 29 are
-- verification_status='representative' -- and disclaimers.py defines that status as
-- "curated + CITED ... but not yet signed off by a licensed immigration lawyer". So
-- those rows failed the definition of the status they advertised.
--
-- WHAT THIS DOES NOT DO
-- It does not cite all 29. Roughly half cannot be honestly sourced, and inventing a
-- source URL is worse than leaving the field empty because a fabricated citation
-- survives review. Specifically left alone, for a separate decision:
--   * "Minimum lead time" (DE/SG/US) -- ReloPass planning guidance, not an
--     authority-defined requirement. No government publishes it. DEMOTED below.
--   * "State residency registration" (US x2) -- sub-national; there is no federal
--     source, and the row is stored at country granularity.
--   * Housing contracts (DE/SG x2/US x2/NO) -- a tenancy is an input to registration,
--     not an immigration requirement. UK is the exception and IS cited here, because
--     gov.uk genuinely publishes tenancy law.
--   * US federal sources -- ssa.gov and travel.state.gov both return HTTP 403 to
--     automated requests. The pages exist; this session could not VERIFY them, and an
--     unverified URL does not get written.
--   * DE passport / DE social security / SG IRAS / SG employment letter -- live
--     official pages exist, but this session did not confirm a sentence on them that
--     supports the specific claim. Deferred rather than cited loosely.
--
-- VERIFICATION
-- Every URL below returned HTTP 200 on 2026-08-20. The three marked (quote) were
-- additionally read to confirm the page states the requirement:
--   BMG s17(1)      "Wer eine Wohnung bezieht, hat sich innerhalb von zwei Wochen
--                    nach dem Einzug bei der Meldebehoerde anzumelden"
--   AufenthG s4(1)  "Auslaender beduerfen fuer die Einreise und den Aufenthalt im
--                    Bundesgebiet eines Aufenthaltstitels, sofern nicht durch Recht
--                    der Europaeischen Union ..."   (note: encodes the EEA carve-out)
--   ICA             "All travellers, except Singapore passport holders, must ensure
--                    their passport has a minimum validity of 6 months."
--
-- Citations are raw URLs. That is an established format in this column -- 35 of the 59
-- distinct citation keys in prod are already raw URLs (the others are source_records
-- UUIDs and immigration_rule.* corpus refs).
--
-- verification_status is deliberately UNCHANGED. These rows stay 'representative';
-- they are now curated AND cited, which is what that status is defined to mean.
-- Nothing here sets 'verified' or 'expert_verified' -- that needs a human, and counsel.
--
-- Idempotent: each UPDATE is keyed on id and only fills a row whose citations are
-- still empty, so a re-run cannot overwrite a reviewer's later edit.

BEGIN;

-- ── 1. Cite the eight rows with a verified official source ───────────────────

-- GERMANY - Residence registration (Anmeldung)  [BMG s17, quote verified]
UPDATE public.requirement_items SET citations_json = '["https://www.gesetze-im-internet.de/bmg/__17.html"]'
 WHERE id = 'e1d0a1c0-0001-5000-8000-000000000003'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- GERMANY - Work visa / residence permit (Aufenthaltstitel)  [AufenthG s4, quote verified]
UPDATE public.requirement_items SET citations_json = '["https://www.gesetze-im-internet.de/aufenthg_2004/__4.html"]'
 WHERE id = 'e1d0a1c0-0001-5000-8000-000000000007'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- SINGAPORE - Valid passport (6+ months)  [ICA, quote verified]
UPDATE public.requirement_items SET citations_json = '["https://www.ica.gov.sg/enter-transit-depart/entering-singapore"]'
 WHERE id = '259515dd-cb55-4c58-95b1-6d568cf3ece9'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- SINGAPORE - Long-term pass registration (ICA), study + employment
UPDATE public.requirement_items SET citations_json = '["https://www.ica.gov.sg/reside/LTVP/apply"]'
 WHERE id IN ('03d796ee-9f56-5a13-bf77-e09f66c414c5','24c19002-b9a7-5de5-bf76-d067d53ff504')
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- UNITED KINGDOM - National Insurance number registration
UPDATE public.requirement_items SET citations_json = '["https://www.gov.uk/apply-national-insurance-number"]'
 WHERE id = 'f1d1800c-ba32-573e-90f9-7d8431a744b1'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- UNITED KINGDOM - Residence permit / eVisa activation
UPDATE public.requirement_items SET citations_json = '["https://www.gov.uk/evisa"]'
 WHERE id = 'bfbb2f05-ab0f-5cad-91be-bca41ece28d6'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- UNITED KINGDOM - Long-term tenancy agreement (AST)
UPDATE public.requirement_items SET citations_json = '["https://www.gov.uk/private-renting-tenancy-agreements"]'
 WHERE id = '2a3e4f76-da81-5452-8622-2253207898c0'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- ── 2. Stop serving the three "Minimum lead time" rows ───────────────────────
-- Our own planning guidance, presented as a requirement. No authority defines it, so
-- it can never be cited; serving it as a requirement is the dishonest part, not the
-- advice itself. Demoted, not deleted -- the content is still there to re-model as
-- guidance. Only demotes a row still sitting at 'approved' with no citation.
UPDATE public.requirement_items SET review_status = 'pending'
 WHERE id IN ('e1d0a1c0-0001-5000-8000-000000000002',
              'f179d500-fd03-493b-ba4b-d5e4d35377da',
              'bdfa3247-3570-4681-972d-a0a8b0df675a')
   AND review_status = 'approved'
   AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));

-- ── 3. Assert the intended shape before committing ───────────────────────────
DO $$
DECLARE cited int; still_uncited int; demoted int;
BEGIN
  SELECT count(*) INTO cited FROM public.requirement_items
   WHERE id IN ('e1d0a1c0-0001-5000-8000-000000000003','e1d0a1c0-0001-5000-8000-000000000007',
                '259515dd-cb55-4c58-95b1-6d568cf3ece9','03d796ee-9f56-5a13-bf77-e09f66c414c5',
                '24c19002-b9a7-5de5-bf76-d067d53ff504','f1d1800c-ba32-573e-90f9-7d8431a744b1',
                'bfbb2f05-ab0f-5cad-91be-bca41ece28d6','2a3e4f76-da81-5452-8622-2253207898c0')
     AND citations_json IS NOT NULL AND citations_json::text NOT IN ('[]','null','{}');
  IF cited <> 8 THEN
    RAISE EXCEPTION 'expected 8 newly-cited rows, found %', cited;
  END IF;

  SELECT count(*) INTO demoted FROM public.requirement_items
   WHERE id IN ('e1d0a1c0-0001-5000-8000-000000000002','f179d500-fd03-493b-ba4b-d5e4d35377da',
                'bdfa3247-3570-4681-972d-a0a8b0df675a')
     AND review_status = 'pending';
  IF demoted <> 3 THEN
    RAISE EXCEPTION 'expected 3 demoted lead-time rows, found %', demoted;
  END IF;

  -- No row may have been elevated by this migration.
  IF EXISTS (SELECT 1 FROM public.requirement_items
              WHERE verification_status IN ('verified','expert_verified')
                AND id IN ('e1d0a1c0-0001-5000-8000-000000000003','e1d0a1c0-0001-5000-8000-000000000007',
                           '259515dd-cb55-4c58-95b1-6d568cf3ece9','03d796ee-9f56-5a13-bf77-e09f66c414c5',
                           '24c19002-b9a7-5de5-bf76-d067d53ff504','f1d1800c-ba32-573e-90f9-7d8431a744b1',
                           'bfbb2f05-ab0f-5cad-91be-bca41ece28d6','2a3e4f76-da81-5452-8622-2253207898c0')) THEN
    RAISE EXCEPTION 'a cited row was elevated above representative -- that needs a human';
  END IF;

  SELECT count(*) INTO still_uncited FROM public.requirement_items
   WHERE review_status='approved'
     AND (citations_json IS NULL OR citations_json::text IN ('[]','null','{}'));
  RAISE NOTICE 'served-but-uncited: 29 -> % (8 cited, 3 demoted, remainder deferred)', still_uncited;
END $$;

COMMIT;
