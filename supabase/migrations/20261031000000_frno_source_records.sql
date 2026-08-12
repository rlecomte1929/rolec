-- [O1] FR->NO: make the evidence that already exists actually reach the screen.
--
-- THE BUG THIS FIXES IS NOT MISSING DATA. IT IS DROPPED DATA.
--
-- `requirement_items.citations_json` is documented as an array of `source_records.id`. For the
-- Norway rows it holds RAW URLs instead. `requirements_builder.py:263-266` resolves each citation
-- against a source_records map and silently discards anything that does not resolve:
--
--     citations = [_source_dto(source_map[cid])
--                  for cid in item.get("citations", []) if cid in source_map]
--
-- So the correct official URL sits in the database and the user is shown nothing. Measured in
-- production 2026-08-12, BEFORE this migration:
--
--     source_records                    10 rows
--     requirement_items with citations  90
--     items whose citation resolves     27      <-- 63 items, 70%, render zero evidence
--
-- This migration fixes the four FR->NO items the North Star bar depends on. It deliberately does
-- NOT fix the other corridors: that is a larger content question and it should not ride along
-- inside a change whose correctness can be checked item by item. The residual is filed.
--
-- WHY THE QUOTES ARE STORED, NOT JUST THE LINKS
-- Each `snippet` below is the exact official sentence recorded in
-- `ReloPass_FR-NO_Requirements_VERIFICATION.md` (PR #1730), which checked all nine FR->NO items
-- against official sources in July 2026. A link tells a user where to look; the quote tells them
-- what it said on the day we checked, which is the part that decays. `retrieved_at` is the check
-- date, not the load date -- see the note on requirement_items.last_verified_at below.
--
-- NOT A TRUST CLAIM. These rows stay `corpus_grounded`. Nothing here flips a verification tier;
-- that needs a human sign-off against the DRAFT checkboxes and lands separately.
--
-- Idempotent: fixed UUIDs, ON CONFLICT DO NOTHING, and a citation rewrite that only replaces a
-- URL it can resolve.

BEGIN;

-- ── 1. The six official sources behind the four requirements ────────────────────────────
--
-- content_hash is NOT NULL UNIQUE. sha256(url) is deterministic, so re-running inserts nothing
-- and the ids below stay stable for the rewrite in step 2. sha256() is built in from PG 11 --
-- no pgcrypto dependency.

INSERT INTO public.source_records (id, country_code, url, title, publisher_domain, retrieved_at, snippet, content_hash)
VALUES
  ('a7f1c3e2-0001-4b7a-9c31-6e0f5a2d8b01', 'NORWAY',
   'https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/',
   'Tax deduction cards for foreign employees (Skatteetaten)',
   'www.skatteetaten.no', TIMESTAMP '2026-07-15 00:00:00',
   'Without a tax deduction card, the employer must deduct 50 percent tax.',
   encode(sha256('https://www.skatteetaten.no/en/business-and-organisation/foreign/employer/tax-deduction-cards/'::bytea), 'hex')),

  ('a7f1c3e2-0002-4b7a-9c31-6e0f5a2d8b02', 'NORWAY',
   'https://www.udi.no/en/word-definitions/d-number/',
   'D number (UDI)',
   'www.udi.no', TIMESTAMP '2026-07-15 00:00:00',
   'A D number is a temporary identification number that you receive from the Norwegian Tax Administration when you do not meet the criteria to being assigned a national identity number.',
   encode(sha256('https://www.udi.no/en/word-definitions/d-number/'::bytea), 'hex')),

  ('a7f1c3e2-0003-4b7a-9c31-6e0f5a2d8b03', 'NORWAY',
   'https://www.udi.no/en/word-definitions/employers-employing-someone-who-is-an-eueea-national-/',
   'Employers employing an EU/EEA national (UDI)',
   'www.udi.no', TIMESTAMP '2026-07-15 00:00:00',
   'EU/EEA nationals can move to Norway and start working right away, but they must register with the police no later than three months after arriving.',
   encode(sha256('https://www.udi.no/en/word-definitions/employers-employing-someone-who-is-an-eueea-national-/'::bytea), 'hex')),

  ('a7f1c3e2-0004-4b7a-9c31-6e0f5a2d8b04', 'NORWAY',
   'https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/',
   'Employee who is an EU/EEA national - registration (UDI)',
   'www.udi.no', TIMESTAMP '2026-07-15 00:00:00',
   'If you are an EU/EEA national who are going to work and live in Norway for more than three months, you have to register. Registration is free.',
   encode(sha256('https://www.udi.no/en/want-to-apply/residence-under-the-eueeu-regulations/employee-who-is-an-eueea-national/'::bytea), 'hex')),

  ('a7f1c3e2-0005-4b7a-9c31-6e0f5a2d8b05', 'NORWAY',
   'https://www.nav.no/en/home/rules-and-regulations/relatert-informasjon/coming-from-an-eu-eea-country-to-work-in-norway',
   'Coming from an EU/EEA country to work in Norway (NAV)',
   'www.nav.no', TIMESTAMP '2026-07-15 00:00:00',
   'If you are a citizen of an EU/EEA-country and come to work in Norway you automatically become a member of the Norwegian National Insurance Scheme from your first day of work.',
   encode(sha256('https://www.nav.no/en/home/rules-and-regulations/relatert-informasjon/coming-from-an-eu-eea-country-to-work-in-norway'::bytea), 'hex')),

  -- CLEISS is the French side of the A1. Its snippet is a summary, not a verbatim pull: the
  -- report records it as "the A1 attests French social-security law applies for the whole
  -- posting", without a single quotable sentence. Saying so is better than inventing a quote.
  ('a7f1c3e2-0006-4b7a-9c31-6e0f5a2d8b06', 'NORWAY',
   'https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html',
   'Detachement - Reglement (CE) 883/2004 (CLEISS, France)',
   'www.cleiss.fr', TIMESTAMP '2026-07-15 00:00:00',
   'The A1 certificate attests that French social-security law continues to apply for the duration of the posting, and French contributions continue to be paid. Standard limit 24 months (Art. 12, Reg. 883/2004); an Article 16 exception agreement may extend it.',
   encode(sha256('https://www.cleiss.fr/particuliers/venir/travailler/detachement/ue883.html'::bytea), 'hex'))
ON CONFLICT (content_hash) DO NOTHING;

-- ── 2. Repoint the citations from raw URLs to those ids ─────────────────────────────────
--
-- Scoped to the four requirements this migration verified, times their two `purpose` variants
-- (every Norway requirement is duplicated across purpose='employment' and 'other') = 8 rows.
--
-- An element that does not resolve is LEFT AS IT WAS rather than dropped. Losing a citation
-- here would be the same failure this migration exists to fix, one layer down.

UPDATE public.requirement_items ri
   SET citations_json = sub.rebuilt
  FROM (
    SELECT r.id AS rid,
           jsonb_agg(COALESCE(sr.id, c.cid) ORDER BY c.ord)::text AS rebuilt
      FROM public.requirement_items r
      CROSS JOIN LATERAL jsonb_array_elements_text(r.citations_json::jsonb)
                         WITH ORDINALITY AS c(cid, ord)
      LEFT JOIN public.source_records sr
             ON sr.url = c.cid AND sr.country_code = 'NORWAY'
     WHERE r.country_code IN ('NORWAY', 'NO')
       AND r.title IN (
             'Tax deduction card (skattekort) before first salary',
             'D-number (stays under 6 months)',
             'Police registration for EU/EEA nationals (stays over 3 months)',
             'A1 certificate for genuinely posted workers')
     GROUP BY r.id
  ) AS sub
 WHERE ri.id = sub.rid
   AND ri.citations_json IS DISTINCT FROM sub.rebuilt;

COMMIT;

-- Not done here, on purpose:
--   * The other 63 items whose citations still do not resolve. Filed separately -- a per-corridor
--     content job, not a mechanical rewrite.
--   * requirement_items.last_verified_at is NOT NULL but is stamped at LOAD time by
--     seed_requirements.py and read by nothing. It is not a human-check date and this migration
--     does not pretend otherwise; the real check date lives on source_records.retrieved_at.
--   * No verification_status changes. That is a human sign-off, and it is a separate migration.
