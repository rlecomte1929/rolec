-- [PRODSEED-3 / AIQ-1130] Durable test-data isolation: is_test flag.
--
-- Adds an is_test boolean to companies + profiles so admin surfaces can hide
-- synthetic e2e/verify tenants by a durable flag instead of fragile read-time
-- name/email pattern matching (PR #685 / AIQ-913).
--
-- Column-add on existing tables — NO new table, so no 3-part RLS gate applies.
-- RLS on companies/profiles is left intact.
--
-- The one-time backfill flips the rows that PR #685's read-time filter was
-- hiding, so retiring that filter does not un-hide them. The patterns mirror
-- backend/db/test_data_filter.py exactly. Demo tenants are provably excluded:
--   • 'Testing April'        — not in the name list, not LIKE 'Probe ISO-%'/'%(Seed)%'
--   • '…@testcompany.com'    — does NOT end in '@testco.com' (LIKE '%@testco.com' is false)
--   • '…@testingapril.com'   — same
-- The backfill is idempotent (only flips false → true; re-runs are no-ops).

ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;
ALTER TABLE profiles  ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;

-- Pre-existing synthetic companies (names the e2e/verify seeders create).
-- Mirrors backend/db/test_data_filter.looks_like_test_company exactly.
UPDATE companies SET is_test = true
WHERE is_test = false
  AND (
       name IN ('Other Corp', 'Test Co (Seed)', 'Test company')
    OR name LIKE 'Probe ISO-%'
    OR name LIKE 'Probe RLS-%'
    OR name LIKE '%(Seed)%'
  );

-- Pre-existing synthetic people (the @testco.com + @probe.test seeder domains).
-- Mirrors backend/db/test_data_filter.looks_like_test_email exactly.
UPDATE profiles SET is_test = true
WHERE is_test = false
  AND (
       COALESCE(email, '') LIKE '%@testco.com'
    OR COALESCE(email, '') LIKE '%@probe.test'
  );
