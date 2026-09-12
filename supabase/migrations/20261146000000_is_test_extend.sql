-- [AIQ-2327 / ADMIN-IA-0b] Extend the durable is_test flag beyond companies+profiles.
--
-- 20260629000000 added is_test to companies + profiles. Since then new seeders
-- (Google IE / Google Ireland T18-*, CPY *, VCo/WCo *, Company 1, and 1218 signups
-- on Romain's hotmail with +t18/+emp_run/… aliases) landed WITHOUT the flag, and
-- leads / prospect_candidates / linkedin_prospects / hr_supplier_submissions have no
-- flag at all. Every admin metric and list built on them is fiction.
--
-- Column-adds on existing tables — NO new table, so the 3-part RLS gate does not
-- apply (RLS on each table is left intact). The read-time filters in
-- backend/db/test_data_filter.py mirror these patterns so rows are hidden even
-- before this migration is applied; the flag is the durable version so retiring a
-- read-time filter never un-hides them.
--
-- Idempotent: every backfill flips only false → true, so re-runs are no-ops.
-- Demo tenants are provably NOT flagged: 'Testing April' is excluded explicitly, and
-- romain_lecomte@hotmail.com has no '+' alias so the hotmail regex cannot match it.

ALTER TABLE leads                    ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;
ALTER TABLE prospect_candidates      ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;
ALTER TABLE linkedin_prospects       ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;
ALTER TABLE hr_supplier_submissions  ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;

-- ── Companies: the seeder patterns that postdate 20260629000000 ─────────────────
-- Mirrors backend/db/test_data_filter.looks_like_test_company / exclude_test_companies.
UPDATE companies SET is_test = true
WHERE is_test = false
  AND (
       name ~ '^Google (IE|Ireland) [A-Z]?\d{10,}'
    OR name ~ '^Google Ireland T18-[A-Z]-'
    OR name ~ '^CPY '
    OR name ~ '^(VCo|WCo) \d+'
    OR name = 'Company 1'
    OR (name ILIKE '%test%' AND name NOT ILIKE 'testing april')
  );

-- ── Profiles: people in the QA companies above + synthetic signup domains ───────
-- Runs AFTER the companies backfill so the company_id subquery sees the fresh flags.
-- The hotmail-alias regex requires a '+<alias>' segment, so a real address with no
-- alias (romain_lecomte@hotmail.com) is never matched; excluded explicitly anyway.
UPDATE profiles SET is_test = true
WHERE is_test = false
  AND (
       company_id IN (SELECT id FROM companies WHERE is_test = true)
    OR COALESCE(email, '') LIKE '%@reloulexei.resend.app'
    OR COALESCE(email, '') LIKE '%@example.com'
    OR COALESCE(email, '') LIKE 'qa-proj-%'
    OR (
         email ~ '^[^+]+\+(t18|emp_run|hr_run|twin|dryrun|qa)[^@]*@hotmail\.com$'
         AND email <> 'romain_lecomte@hotmail.com'
       )
  );

-- ── Leads: synthetic inbound emails (resend.app / example.com / qa-proj / test@) ─
UPDATE leads SET is_test = true
WHERE is_test = false
  AND (
       COALESCE(email, '') LIKE '%@reloulexei.resend.app'
    OR COALESCE(email, '') LIKE '%@example.com'
    OR COALESCE(email, '') LIKE 'qa-proj-%'
    OR COALESCE(email, '') LIKE 'test@%'
    OR COALESCE(email, '') LIKE '%@testco.com'
  );

-- ── Prospect candidates: named QA rows + any '%test%' company ───────────────────
UPDATE prospect_candidates SET is_test = true
WHERE is_test = false
  AND (
       company_name IN ('QA Corp', 'Bob Dylan Company', 'HR Dir @ Acme', 'HR Dir, Beta Co')
    OR company_name ILIKE '%test%'
  );

-- ── HR supplier submissions: 'School test' / 'test oslo school' / 'ABC test …' ───
UPDATE hr_supplier_submissions SET is_test = true
WHERE is_test = false
  AND name ILIKE '%test%';

-- linkedin_prospects: column added for FK-parity with the outreach pipeline; no
-- backfill pattern was identified, so rows stay is_test=false (the safe default).
