-- =============================================================================
-- ReloPass Demo Seed — scripts/seed_demo.sql
-- MVP-8 (AIQ-375)
--
-- Creates 3 realistic demo scenarios for sales walkthrough:
--   Scenario 1: GlobalTech SAS     — Adrien Martin    — Lyon → Berlin   (EU Blue Card)
--   Scenario 2: Meridian Capital   — Céline Dupont    — Paris → London  (UK Skilled Worker Visa)
--   Scenario 3: Nexora Labs        — Carlos Rivera    — Barcelona → Amsterdam (EEA Registration)
--
-- Demo credentials (all 6 users share the same password):
--   Password : Demo2026!
--   HR logins: hannah.hr@globaltech-demo.com / sophie.hr@meridian-demo.com / marta.hr@nexora-demo.com
--   Employee : adrien.martin@globaltech-demo.com / celine.dupont@meridian-demo.com / carlos.rivera@nexora-demo.com
--
-- IDEMPOTENT: uses ON CONFLICT DO UPDATE / DO NOTHING throughout.
-- Run with: psql $DATABASE_URL -f scripts/seed_demo.sql
-- Reset:    scripts/reset_demo.sh
-- =============================================================================

BEGIN;

-- =============================================================================
-- FIXED UUIDs (deterministic — never change these)
-- =============================================================================
-- Companies
-- DEMO-CO-1  d0e00001-0000-4000-8000-000000000001  GlobalTech SAS
-- DEMO-CO-2  d0e00002-0000-4000-8000-000000000002  Meridian Capital
-- DEMO-CO-3  d0e00003-0000-4000-8000-000000000003  Nexora Labs

-- HR Profiles
-- DEMO-HR-1  d0e00010-0000-4000-8000-000000000010  Hannah Müller (GlobalTech HR)
-- DEMO-HR-2  d0e00020-0000-4000-8000-000000000020  Sophie Leclerc (Meridian HR)
-- DEMO-HR-3  d0e00030-0000-4000-8000-000000000030  Marta García (Nexora HR)

-- Employee Profiles
-- DEMO-EMP-1 d0e00100-0000-4000-8000-000000000100  Adrien Martin    (GlobalTech)
-- DEMO-EMP-2 d0e00200-0000-4000-8000-000000000200  Céline Dupont    (Meridian)
-- DEMO-EMP-3 d0e00300-0000-4000-8000-000000000300  Carlos Rivera    (Nexora)

-- Cases (IDs match existing vendor/budget seed)
-- DEMO-CASE-1  5b16522e-e899-4db2-bc8d-95af00af8c79  Adrien Martin  FR→DE
-- DEMO-CASE-2  1cbc563e-b984-44b5-adb3-74912d79a84d  Céline Dupont  FR→GB
-- DEMO-CASE-3  65d7aea8-bc11-413a-8d28-8b9818190a2a  Carlos Rivera  ES→NL

-- Immigration Cases
-- DEMO-IMM-1   d0e00500-0000-4000-8000-000000000500
-- DEMO-IMM-2   d0e00600-0000-4000-8000-000000000600
-- DEMO-IMM-3   d0e00700-0000-4000-8000-000000000700


-- =============================================================================
-- 1. COMPANIES
-- =============================================================================
INSERT INTO public.companies (id, name, slug, country_code, plan_tier, hr_contact_email, active_case_count, total_case_count, settings, created_at, updated_at)
VALUES
  ('d0e00001-0000-4000-8000-000000000001'::uuid, 'GlobalTech SAS',   'globaltech-sas',   'FR', 'growth', 'hr@globaltech-demo.com',   1, 1, '{"demo": true}'::jsonb, NOW(), NOW()),
  ('d0e00002-0000-4000-8000-000000000002'::uuid, 'Meridian Capital', 'meridian-capital', 'FR', 'growth', 'hr@meridian-demo.com',     1, 1, '{"demo": true}'::jsonb, NOW(), NOW()),
  ('d0e00003-0000-4000-8000-000000000003'::uuid, 'Nexora Labs',      'nexora-labs',      'ES', 'growth', 'hr@nexora-demo.com',       1, 1, '{"demo": true}'::jsonb, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
  name              = EXCLUDED.name,
  slug              = EXCLUDED.slug,
  country_code      = EXCLUDED.country_code,
  plan_tier         = EXCLUDED.plan_tier,
  hr_contact_email  = EXCLUDED.hr_contact_email,
  active_case_count = EXCLUDED.active_case_count,
  total_case_count  = EXCLUDED.total_case_count,
  settings          = EXCLUDED.settings,
  updated_at        = NOW();


-- =============================================================================
-- 2. HR PROFILES
-- =============================================================================
INSERT INTO public.profiles (id, email, full_name, role, company_id, locale, timezone, created_at, updated_at)
VALUES
  ('d0e00010-0000-4000-8000-000000000010'::uuid, 'hannah.hr@globaltech-demo.com', 'Hannah Müller',   'hr', 'd0e00001-0000-4000-8000-000000000001'::uuid, 'de', 'Europe/Berlin',    NOW(), NOW()),
  ('d0e00020-0000-4000-8000-000000000020'::uuid, 'sophie.hr@meridian-demo.com',  'Sophie Leclerc',  'hr', 'd0e00002-0000-4000-8000-000000000002'::uuid, 'fr', 'Europe/Paris',     NOW(), NOW()),
  ('d0e00030-0000-4000-8000-000000000030'::uuid, 'marta.hr@nexora-demo.com',     'Marta García',    'hr', 'd0e00003-0000-4000-8000-000000000003'::uuid, 'es', 'Europe/Amsterdam', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
  email      = EXCLUDED.email,
  full_name  = EXCLUDED.full_name,
  role       = EXCLUDED.role,
  company_id = EXCLUDED.company_id,
  updated_at = NOW();


-- =============================================================================
-- 3. EMPLOYEE PROFILES
-- =============================================================================
INSERT INTO public.profiles (id, email, full_name, role, company_id, locale, timezone, created_at, updated_at)
VALUES
  ('d0e00100-0000-4000-8000-000000000100'::uuid, 'adrien.martin@globaltech-demo.com', 'Adrien Martin', 'employee', 'd0e00001-0000-4000-8000-000000000001'::uuid, 'fr', 'Europe/Paris',     NOW(), NOW()),
  ('d0e00200-0000-4000-8000-000000000200'::uuid, 'celine.dupont@meridian-demo.com',   'Céline Dupont', 'employee', 'd0e00002-0000-4000-8000-000000000002'::uuid, 'fr', 'Europe/Paris',     NOW(), NOW()),
  ('d0e00300-0000-4000-8000-000000000300'::uuid, 'carlos.rivera@nexora-demo.com',     'Carlos Rivera', 'employee', 'd0e00003-0000-4000-8000-000000000003'::uuid, 'es', 'Europe/Amsterdam', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
  email      = EXCLUDED.email,
  full_name  = EXCLUDED.full_name,
  role       = EXCLUDED.role,
  company_id = EXCLUDED.company_id,
  updated_at = NOW();


-- =============================================================================
-- 4. CASES
-- IDs must match the IDs already used in case_vendor_shortlist + case_budget_lines
-- =============================================================================
INSERT INTO public.cases (
  id, company_id, employee_id, hr_owner_id,
  origin_country_code, dest_country_code, dest_city,
  purpose, target_move_date, status, stage,
  overall_progress_pct, risk_level, delay_days,
  budget_cap, currency, notes, created_at, updated_at
)
VALUES
  -- Scenario 1: Adrien Martin — Lyon → Berlin — EU Blue Card
  (
    '5b16522e-e899-4db2-bc8d-95af00af8c79'::uuid,
    'd0e00001-0000-4000-8000-000000000001'::uuid,  -- GlobalTech SAS
    'd0e00100-0000-4000-8000-000000000100'::uuid,  -- Adrien Martin
    'd0e00010-0000-4000-8000-000000000010'::uuid,  -- Hannah Müller (HR)
    'FR', 'DE', 'Berlin',
    'work', '2026-09-01',
    'active', 'in_progress',
    55, 'medium', 0,
    22400, 'EUR',
    'Demo scenario: International hire — Lyon to Berlin. EU Blue Card application in progress.',
    NOW(), NOW()
  ),
  -- Scenario 2: Céline Dupont — Paris → London — UK Skilled Worker
  (
    '1cbc563e-b984-44b5-adb3-74912d79a84d'::uuid,
    'd0e00002-0000-4000-8000-000000000002'::uuid,  -- Meridian Capital
    'd0e00200-0000-4000-8000-000000000200'::uuid,  -- Céline Dupont
    'd0e00020-0000-4000-8000-000000000020'::uuid,  -- Sophie Leclerc (HR)
    'FR', 'GB', 'London',
    'work', '2026-10-15',
    'active', 'in_progress',
    70, 'low', 0,
    38000, 'EUR',
    'Demo scenario: Long-term assignment — Paris to London. UK Skilled Worker Visa (post-Brexit).',
    NOW(), NOW()
  ),
  -- Scenario 3: Carlos Rivera — Barcelona → Amsterdam — EEA Registration
  (
    '65d7aea8-bc11-413a-8d28-8b9818190a2a'::uuid,
    'd0e00003-0000-4000-8000-000000000003'::uuid,  -- Nexora Labs
    'd0e00300-0000-4000-8000-000000000300'::uuid,  -- Carlos Rivera
    'd0e00030-0000-4000-8000-000000000030'::uuid,  -- Marta García (HR)
    'ES', 'NL', 'Amsterdam',
    'work', '2026-08-01',
    'active', 'dossier',
    30, 'low', 0,
    19500, 'EUR',
    'Demo scenario: Permanent transfer — Barcelona → Amsterdam. EEA Registration (EU freedom of movement).',
    NOW(), NOW()
  )
ON CONFLICT (id) DO UPDATE SET
  company_id           = EXCLUDED.company_id,
  employee_id          = EXCLUDED.employee_id,
  hr_owner_id          = EXCLUDED.hr_owner_id,
  dest_city            = EXCLUDED.dest_city,
  purpose              = EXCLUDED.purpose,
  target_move_date     = EXCLUDED.target_move_date,
  status               = EXCLUDED.status,
  stage                = EXCLUDED.stage,
  overall_progress_pct = EXCLUDED.overall_progress_pct,
  risk_level           = EXCLUDED.risk_level,
  budget_cap           = EXCLUDED.budget_cap,
  notes                = EXCLUDED.notes,
  updated_at           = NOW();


-- =============================================================================
-- 5. IMMIGRATION CASES
-- =============================================================================
INSERT INTO public.immigration_cases (
  id, case_id, corridor_from, corridor_to, permit_type,
  partner_name, expected_submission_date, expected_grant_date,
  status, document_statuses, created_at, updated_at
)
VALUES
  -- Scenario 1: EU Blue Card (Germany)
  (
    'd0e00500-0000-4000-8000-000000000500'::uuid,
    '5b16522e-e899-4db2-bc8d-95af00af8c79'::uuid,
    'France', 'Germany', 'eu_blue_card',
    'Fragomen Worldwide',
    '2026-07-01', '2026-09-01',
    'documents_collected',
    '{"Valid passport (min 6 months)": "uploaded", "University degree certificate": "verified", "Employment contract": "uploaded", "Proof of salary (above Blue Card threshold)": "not_started", "Health insurance confirmation": "not_started"}'::jsonb,
    NOW(), NOW()
  ),
  -- Scenario 2: UK Skilled Worker Visa
  (
    'd0e00600-0000-4000-8000-000000000600'::uuid,
    '1cbc563e-b984-44b5-adb3-74912d79a84d'::uuid,
    'France', 'United Kingdom', 'work_permit',
    'Delahaye Moving & Relocation',
    '2026-08-15', '2026-10-15',
    'submitted',
    '{"Valid passport": "verified", "Employer sponsorship letter": "verified", "Signed employment contract": "verified", "Proof of qualifications": "uploaded", "Recent payslips (last 3 months)": "uploaded", "Health insurance": "not_started"}'::jsonb,
    NOW(), NOW()
  ),
  -- Scenario 3: EEA Registration (Netherlands)
  (
    'd0e00700-0000-4000-8000-000000000700'::uuid,
    '65d7aea8-bc11-413a-8d28-8b9818190a2a'::uuid,
    'Spain', 'Netherlands', 'eea_registration',
    NULL,
    '2026-07-15', '2026-08-01',
    'initiated',
    '{"Valid EU passport or national ID": "not_started", "Proof of employment or self-employment": "not_started", "Proof of address at destination": "not_started"}'::jsonb,
    NOW(), NOW()
  )
ON CONFLICT (id) DO UPDATE SET
  corridor_from             = EXCLUDED.corridor_from,
  corridor_to               = EXCLUDED.corridor_to,
  permit_type               = EXCLUDED.permit_type,
  partner_name              = EXCLUDED.partner_name,
  expected_submission_date  = EXCLUDED.expected_submission_date,
  expected_grant_date       = EXCLUDED.expected_grant_date,
  status                    = EXCLUDED.status,
  document_statuses         = EXCLUDED.document_statuses,
  updated_at                = NOW();


-- =============================================================================
-- 6. CASE ASSIGNMENTS (links HR user to case for the HR views)
-- Note: employee_identifier is NOT NULL — use the employee's email as identifier
-- =============================================================================
INSERT INTO public.case_assignments (id, case_id, hr_user_id, employee_identifier, status, created_at, updated_at)
VALUES
  ('demo-ca-001', '5b16522e-e899-4db2-bc8d-95af00af8c79', 'd0e00010-0000-4000-8000-000000000010', 'adrien.martin@globaltech-demo.com', 'approved',  NOW(), NOW()),
  ('demo-ca-002', '1cbc563e-b984-44b5-adb3-74912d79a84d', 'd0e00020-0000-4000-8000-000000000020', 'celine.dupont@meridian-demo.com',   'submitted', NOW(), NOW()),
  ('demo-ca-003', '65d7aea8-bc11-413a-8d28-8b9818190a2a', 'd0e00030-0000-4000-8000-000000000030', 'carlos.rivera@nexora-demo.com',     'assigned',  NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
  status     = EXCLUDED.status,
  updated_at = NOW();


-- =============================================================================
-- 7. BACKEND RELOCATION_CASES  (backend's own case table, queried by GET /api/hr/cases)
-- This table is separate from public.cases — the HR dashboard reads from here.
-- profile_json encodes the RelocationProfile (primaryApplicant, locations, visa type).
-- =============================================================================
INSERT INTO relocation_cases (id, hr_user_id, profile_json, company_id, employee_id, status, stage, home_country, host_country, created_at, updated_at)
VALUES
  (
    '5b16522e-e899-4db2-bc8d-95af00af8c79',
    'd0e00010-0000-4000-8000-000000000010',
    '{"primaryApplicant":{"firstName":"Adrien","lastName":"Martin","email":"adrien.martin@globaltech-demo.com","nationality":"FR","employer":{"name":"GlobalTech SAS"}},"currentLocation":{"country":"FR","city":"Lyon"},"destinationLocation":{"country":"DE","city":"Berlin"},"moveType":"work","visaType":"eu_blue_card","targetMoveDate":"2026-09-01","budgetCap":22400}',
    'd0e00001-0000-4000-8000-000000000001',
    'd0e00100-0000-4000-8000-000000000100',
    'active', 'in_progress', 'FR', 'DE',
    NOW()::text, NOW()::text
  ),
  (
    '1cbc563e-b984-44b5-adb3-74912d79a84d',
    'd0e00020-0000-4000-8000-000000000020',
    '{"primaryApplicant":{"firstName":"Celine","lastName":"Dupont","email":"celine.dupont@meridian-demo.com","nationality":"FR","employer":{"name":"Meridian Capital"}},"currentLocation":{"country":"FR","city":"Paris"},"destinationLocation":{"country":"GB","city":"London"},"moveType":"work","visaType":"work_permit","targetMoveDate":"2026-10-15","budgetCap":38000}',
    'd0e00002-0000-4000-8000-000000000002',
    'd0e00200-0000-4000-8000-000000000200',
    'active', 'in_progress', 'FR', 'GB',
    NOW()::text, NOW()::text
  ),
  (
    '65d7aea8-bc11-413a-8d28-8b9818190a2a',
    'd0e00030-0000-4000-8000-000000000030',
    '{"primaryApplicant":{"firstName":"Carlos","lastName":"Rivera","email":"carlos.rivera@nexora-demo.com","nationality":"ES","employer":{"name":"Nexora Labs"}},"currentLocation":{"country":"ES","city":"Barcelona"},"destinationLocation":{"country":"NL","city":"Amsterdam"},"moveType":"work","visaType":"eea_registration","targetMoveDate":"2026-08-01","budgetCap":19500}',
    'd0e00003-0000-4000-8000-000000000003',
    'd0e00300-0000-4000-8000-000000000300',
    'active', 'dossier', 'ES', 'NL',
    NOW()::text, NOW()::text
  )
ON CONFLICT (id) DO UPDATE SET
  company_id   = EXCLUDED.company_id,
  employee_id  = EXCLUDED.employee_id,
  status       = EXCLUDED.status,
  stage        = EXCLUDED.stage,
  home_country = EXCLUDED.home_country,
  host_country = EXCLUDED.host_country,
  updated_at   = EXCLUDED.updated_at;


-- =============================================================================
-- 8. BACKEND CASE_ASSIGNMENTS  (backend's own assignments table)
-- Links HR user to case for the employee portal assignment flow.
-- =============================================================================
INSERT INTO case_assignments (id, case_id, canonical_case_id, hr_user_id, employee_user_id, employee_identifier, status, employee_first_name, employee_last_name, created_at, updated_at)
VALUES
  ('demo-bca-001', '5b16522e-e899-4db2-bc8d-95af00af8c79', '5b16522e-e899-4db2-bc8d-95af00af8c79',
   'd0e00010-0000-4000-8000-000000000010', 'd0e00100-0000-4000-8000-000000000100',
   'adrien.martin@globaltech-demo.com', 'approved', 'Adrien', 'Martin',
   NOW()::text, NOW()::text),
  ('demo-bca-002', '1cbc563e-b984-44b5-adb3-74912d79a84d', '1cbc563e-b984-44b5-adb3-74912d79a84d',
   'd0e00020-0000-4000-8000-000000000020', 'd0e00200-0000-4000-8000-000000000200',
   'celine.dupont@meridian-demo.com', 'submitted', 'Celine', 'Dupont',
   NOW()::text, NOW()::text),
  ('demo-bca-003', '65d7aea8-bc11-413a-8d28-8b9818190a2a', '65d7aea8-bc11-413a-8d28-8b9818190a2a',
   'd0e00030-0000-4000-8000-000000000030', 'd0e00300-0000-4000-8000-000000000300',
   'carlos.rivera@nexora-demo.com', 'assigned', 'Carlos', 'Rivera',
   NOW()::text, NOW()::text)
ON CONFLICT (id) DO UPDATE SET
  status     = EXCLUDED.status,
  updated_at = EXCLUDED.updated_at;


-- =============================================================================
-- 9. BACKEND USERS  (public.users — the ReloPass backend auth table)
-- pbkdf2_sha256 hash of "Demo2026!" — regenerate with:
--   python3 -c "from passlib.context import CryptContext; ctx = CryptContext(schemes=['pbkdf2_sha256']); print(ctx.hash('Demo2026!'))"
-- Roles MUST be uppercase to match backend/schemas.py UserRole enum (HR, EMPLOYEE, ADMIN).
-- =============================================================================
INSERT INTO public.users (id, email, password_hash, role, name, created_at)
VALUES
  ('d0e00010-0000-4000-8000-000000000010', 'hannah.hr@globaltech-demo.com',      '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'HR',       'Hannah Müller',  NOW()::text),
  ('d0e00020-0000-4000-8000-000000000020', 'sophie.hr@meridian-demo.com',         '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'HR',       'Sophie Leclerc', NOW()::text),
  ('d0e00030-0000-4000-8000-000000000030', 'marta.hr@nexora-demo.com',            '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'HR',       'Marta García',   NOW()::text),
  ('d0e00100-0000-4000-8000-000000000100', 'adrien.martin@globaltech-demo.com',   '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'EMPLOYEE', 'Adrien Martin',  NOW()::text),
  ('d0e00200-0000-4000-8000-000000000200', 'celine.dupont@meridian-demo.com',     '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'EMPLOYEE', 'Céline Dupont',  NOW()::text),
  ('d0e00300-0000-4000-8000-000000000300', 'carlos.rivera@nexora-demo.com',       '$pbkdf2-sha256$29000$IySkFILwfi8lRMg5x1hLSQ$I0O6vrRz8Zxl8prbHwJuroAfWFj5A8v13ZISg8N.tfs', 'EMPLOYEE', 'Carlos Rivera',  NOW()::text)
ON CONFLICT (id) DO UPDATE SET
  email         = EXCLUDED.email,
  password_hash = EXCLUDED.password_hash,
  role          = EXCLUDED.role,
  name          = EXCLUDED.name;


-- =============================================================================
-- 8. AUTH USERS  (enables demo login with password: Demo2026!)
-- bcrypt hash of "Demo2026!" — regenerate with:
--   python3 -c "import bcrypt; print(bcrypt.hashpw(b'Demo2026!', bcrypt.gensalt(10)).decode())"
-- =============================================================================
INSERT INTO auth.users (
  id, instance_id, email, encrypted_password,
  email_confirmed_at, created_at, updated_at,
  raw_app_meta_data, raw_user_meta_data,
  is_super_admin, role, aud,
  confirmation_token, recovery_token,
  email_change_token_new, email_change_token_current,
  reauthentication_token
)
VALUES
  ('d0e00010-0000-4000-8000-000000000010'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'hannah.hr@globaltech-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Hannah Müller"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', ''),
  ('d0e00020-0000-4000-8000-000000000020'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'sophie.hr@meridian-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Sophie Leclerc"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', ''),
  ('d0e00030-0000-4000-8000-000000000030'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'marta.hr@nexora-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Marta García"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', ''),
  ('d0e00100-0000-4000-8000-000000000100'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'adrien.martin@globaltech-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Adrien Martin"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', ''),
  ('d0e00200-0000-4000-8000-000000000200'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'celine.dupont@meridian-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Céline Dupont"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', ''),
  ('d0e00300-0000-4000-8000-000000000300'::uuid, '00000000-0000-0000-0000-000000000000'::uuid,
   'carlos.rivera@nexora-demo.com', '$2a$10$IfjnwmofkCd5tbxtZLGSqOOPJysKVjocUpj4UDllVTg9lEAbSNuCS',
   NOW(), NOW(), NOW(), '{"provider":"email","providers":["email"]}'::jsonb, '{"full_name":"Carlos Rivera"}'::jsonb,
   false, 'authenticated', 'authenticated', '', '', '', '', '')
ON CONFLICT (id) DO UPDATE SET
  email                      = EXCLUDED.email,
  encrypted_password         = EXCLUDED.encrypted_password,
  email_confirmed_at         = COALESCE(auth.users.email_confirmed_at, NOW()),
  updated_at                 = NOW(),
  raw_user_meta_data         = EXCLUDED.raw_user_meta_data,
  confirmation_token         = '',
  recovery_token             = '',
  email_change_token_new     = '',
  email_change_token_current = '',
  reauthentication_token     = '';

INSERT INTO auth.identities (
  id, user_id, provider_id, provider, identity_data,
  created_at, updated_at, last_sign_in_at
)
VALUES
  ('d0e00010-0000-4000-8000-000000000010', 'd0e00010-0000-4000-8000-000000000010'::uuid, 'hannah.hr@globaltech-demo.com', 'email',
   '{"sub":"d0e00010-0000-4000-8000-000000000010","email":"hannah.hr@globaltech-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW()),
  ('d0e00020-0000-4000-8000-000000000020', 'd0e00020-0000-4000-8000-000000000020'::uuid, 'sophie.hr@meridian-demo.com', 'email',
   '{"sub":"d0e00020-0000-4000-8000-000000000020","email":"sophie.hr@meridian-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW()),
  ('d0e00030-0000-4000-8000-000000000030', 'd0e00030-0000-4000-8000-000000000030'::uuid, 'marta.hr@nexora-demo.com', 'email',
   '{"sub":"d0e00030-0000-4000-8000-000000000030","email":"marta.hr@nexora-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW()),
  ('d0e00100-0000-4000-8000-000000000100', 'd0e00100-0000-4000-8000-000000000100'::uuid, 'adrien.martin@globaltech-demo.com', 'email',
   '{"sub":"d0e00100-0000-4000-8000-000000000100","email":"adrien.martin@globaltech-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW()),
  ('d0e00200-0000-4000-8000-000000000200', 'd0e00200-0000-4000-8000-000000000200'::uuid, 'celine.dupont@meridian-demo.com', 'email',
   '{"sub":"d0e00200-0000-4000-8000-000000000200","email":"celine.dupont@meridian-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW()),
  ('d0e00300-0000-4000-8000-000000000300', 'd0e00300-0000-4000-8000-000000000300'::uuid, 'carlos.rivera@nexora-demo.com', 'email',
   '{"sub":"d0e00300-0000-4000-8000-000000000300","email":"carlos.rivera@nexora-demo.com","email_verified":true}'::jsonb,
   NOW(), NOW(), NOW())
ON CONFLICT (provider, provider_id) DO UPDATE SET
  identity_data = EXCLUDED.identity_data,
  updated_at    = NOW();


COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================
SELECT
  c.id::text                  AS case_id,
  co.name                     AS company,
  p.full_name                 AS employee,
  c.corridor,
  c.status,
  c.budget_cap,
  imm.permit_type,
  imm.status                  AS imm_status,
  (SELECT COUNT(*) FROM public.case_vendor_shortlist  WHERE case_id = c.id::text) AS vendors,
  (SELECT COUNT(*) FROM public.case_budget_lines       WHERE case_id = c.id::text) AS budget_lines
FROM public.cases c
JOIN public.companies co ON co.id = c.company_id
JOIN public.profiles p   ON p.id  = c.employee_id
LEFT JOIN public.immigration_cases imm ON imm.case_id = c.id
WHERE c.id IN (
  '5b16522e-e899-4db2-bc8d-95af00af8c79'::uuid,
  '1cbc563e-b984-44b5-adb3-74912d79a84d'::uuid,
  '65d7aea8-bc11-413a-8d28-8b9818190a2a'::uuid
)
ORDER BY co.name;
