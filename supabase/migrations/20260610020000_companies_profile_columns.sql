-- ============================================================
-- Add the company-profile columns the HR "Company profile" form writes.
-- Date: 2026-06-10
--
-- The fresh-onboarding probe (scripts/verify_fresh_onboarding.py) found that
-- POST /api/hr/company-profile returns 200 but persists NOTHING beyond the
-- company name: the prod `companies` table never had address/phone/hq_city/etc.
-- columns. `db.create_company` already writes these fields but builds its INSERT
-- from the columns that actually exist (dynamic _table_columns), so they were
-- silently dropped. The frontend CompanyProfileForm reads them straight off the
-- company object (company.address, company.country, ...), and get_company is a
-- SELECT * — so once the columns exist the form round-trips with NO code change.
--
-- Additive, nullable, idempotent (ADD COLUMN IF NOT EXISTS) — no existing data
-- touched. `country` is added alongside the existing `country_code` because the
-- profile form / create_company use the bare `country` field; country_code
-- stays for the surfaces that already read it.
-- ============================================================

ALTER TABLE public.companies
  ADD COLUMN IF NOT EXISTS country                     TEXT,
  ADD COLUMN IF NOT EXISTS size_band                   TEXT,
  ADD COLUMN IF NOT EXISTS address                     TEXT,
  ADD COLUMN IF NOT EXISTS phone                       TEXT,
  ADD COLUMN IF NOT EXISTS hr_contact                  TEXT,
  ADD COLUMN IF NOT EXISTS legal_name                  TEXT,
  ADD COLUMN IF NOT EXISTS website                     TEXT,
  ADD COLUMN IF NOT EXISTS hq_city                     TEXT,
  ADD COLUMN IF NOT EXISTS industry                    TEXT,
  ADD COLUMN IF NOT EXISTS brand_color                 TEXT,
  ADD COLUMN IF NOT EXISTS default_destination_country TEXT,
  ADD COLUMN IF NOT EXISTS support_email               TEXT,
  ADD COLUMN IF NOT EXISTS default_working_location    TEXT;
