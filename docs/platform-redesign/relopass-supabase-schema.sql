-- ============================================================
-- RELOPASS SUPABASE SCHEMA — TARGET PLATFORM MIGRATION
-- Version: 1.0.0  |  Date: 2026-05-20
-- Run with: supabase db push
--
-- Design intent:
--   The employee going through a relocation must feel zero friction.
--   Every table here is in service of one goal: surfacing the right
--   information at the right moment, so the employee never has to
--   wonder "what do I need to do next?" or "is my company covering this?"
--   The HR contact is a facilitator, not a gatekeeper.
--
-- Architecture:
--   - Multi-tenant via company_id on every case-linked table
--   - All user FKs go via profiles (which extends auth.users)
--   - RLS on every table — cross-company reads are impossible by design
--   - moddatetime triggers keep updated_at fresh
--   - Indexes on all FK + search columns
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS moddatetime;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- SECTION 1: IDENTITY & TENANCY
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: companies
-- Tenant organizations. Each company is an HR buyer.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.companies (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name               text NOT NULL,
  slug               text UNIQUE NOT NULL,
  logo_url           text,
  country_code       text,
  plan_tier          text NOT NULL DEFAULT 'starter'
                       CHECK (plan_tier IN ('starter', 'growth', 'enterprise')),
  hr_contact_email   text,
  active_case_count  int  NOT NULL DEFAULT 0,
  total_case_count   int  NOT NULL DEFAULT 0,
  settings           jsonb NOT NULL DEFAULT '{}',
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.companies IS 'HR buyer organizations. Every case, policy, and vendor relationship is scoped to a company.';

-- ----------------------------------------------------------
-- TABLE: profiles
-- Platform user registry. Extends Supabase auth.users.
-- Every authenticated user has exactly one profile.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id                   uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email                text NOT NULL,
  full_name            text NOT NULL DEFAULT '',
  role                 text NOT NULL DEFAULT 'employee'
                         CHECK (role IN ('employee', 'hr', 'admin')),
  plan_tier            text NOT NULL DEFAULT 'basic'
                         CHECK (plan_tier IN ('basic', 'hr', 'admin')),
  company_id           uuid REFERENCES public.companies(id) ON DELETE SET NULL,
  avatar_url           text,
  locale               text DEFAULT 'en',
  timezone             text DEFAULT 'UTC',
  notification_prefs   jsonb NOT NULL DEFAULT '{"email": true, "in_app": true}',
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.profiles IS 'Extended profile for every auth.users row. role+plan_tier controls feature access. company_id scopes HR users to their tenant.';
COMMENT ON COLUMN public.profiles.plan_tier IS 'basic=employee access, hr=HR access, admin=platform admin access. Mirrors role but used for feature gating.';

-- ============================================================
-- SECTION 2: REFERENCE DATA
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: countries
-- Destination / origin country reference data.
-- Seeded with 16 countries, updated by ops team.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.countries (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                  text UNIQUE NOT NULL,     -- ISO 3166-1 alpha-2
  name                  text NOT NULL,
  flag_emoji            text NOT NULL,
  region                text NOT NULL,            -- 'EU', 'North America', 'APAC', 'MENA'
  visa_complexity       text NOT NULL DEFAULT 'medium'
                          CHECK (visa_complexity IN ('low', 'medium', 'high', 'very_high')),
  processing_weeks_min  int  NOT NULL DEFAULT 4,
  processing_weeks_max  int  NOT NULL DEFAULT 12,
  popular_corridors     text[] NOT NULL DEFAULT '{}',   -- ['FR-DE', 'DE-UK']
  requires_apostille    bool NOT NULL DEFAULT false,
  key_authorities       jsonb NOT NULL DEFAULT '[]',    -- [{name, url, type}]
  notes                 text,
  is_active             bool NOT NULL DEFAULT true,
  created_at            timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.countries IS 'Reference data for 16 supported relocation corridors. Drives discovery complexity estimates and authority links.';

-- ----------------------------------------------------------
-- TABLE: discovery_sources
-- AI data sources for compliance requirement discovery.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.discovery_sources (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name              text NOT NULL,
  logo_initials     text NOT NULL,
  category          text NOT NULL,    -- 'Immigration Authority', 'Tax Authority', 'Labour Ministry'
  country_code      text NOT NULL,
  is_live_api       bool NOT NULL DEFAULT false,
  api_endpoint      text,
  last_synced_at    timestamptz,
  item_count        int NOT NULL DEFAULT 0,
  sync_frequency    text DEFAULT 'weekly',
  is_active         bool NOT NULL DEFAULT true,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.discovery_sources IS 'Immigration, civil, and tax authorities the AI queries during compliance discovery. item_count reflects how many rules/documents are indexed from each source.';

-- ============================================================
-- SECTION 3: THE RELOCATION CASE
-- The core aggregate. Every other table links here.
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: policy_tiers (defined before cases — FK dependency)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_tiers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  name          text NOT NULL,           -- 'Standard', 'Premium', 'Executive'
  description   text,
  cost_cap      numeric(12,2) NOT NULL DEFAULT 0,
  currency      text NOT NULL DEFAULT 'EUR',
  is_default    bool NOT NULL DEFAULT false,
  is_active     bool NOT NULL DEFAULT true,
  version       int  NOT NULL DEFAULT 1,
  published_at  timestamptz,
  created_by    uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.policy_tiers IS 'HR-defined relocation policy tiers. Each case is assigned one tier. Drives the policy screen (S5) and exception flow.';

-- ----------------------------------------------------------
-- TABLE: cases
-- The root aggregate for a single employee relocation.
-- Every document, form, requirement, and message is a child.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cases (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id            uuid NOT NULL REFERENCES public.companies(id),
  employee_id           uuid NOT NULL REFERENCES public.profiles(id),
  hr_owner_id           uuid REFERENCES public.profiles(id),
  origin_country_code   text NOT NULL,
  dest_country_code     text NOT NULL,
  dest_city             text,
  -- Generated corridor key — indexed for fast vendor/requirement lookup
  corridor              text GENERATED ALWAYS AS (origin_country_code || '-' || dest_country_code) STORED,
  purpose               text NOT NULL DEFAULT 'work'
                          CHECK (purpose IN ('work', 'intra_company_transfer', 'family_join', 'remote_work')),
  target_move_date      date,
  actual_move_date      date,
  status                text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('draft', 'active', 'on_hold', 'completed', 'cancelled')),
  stage                 text NOT NULL DEFAULT 'discovery'
                          CHECK (stage IN ('discovery', 'dossier', 'roadmap', 'in_progress', 'closing', 'closed')),
  overall_progress_pct  int  NOT NULL DEFAULT 0
                          CHECK (overall_progress_pct BETWEEN 0 AND 100),
  risk_level            text NOT NULL DEFAULT 'low'
                          CHECK (risk_level IN ('low', 'medium', 'high')),
  delay_days            int  NOT NULL DEFAULT 0,
  budget_cap            numeric(12,2),
  currency              text NOT NULL DEFAULT 'EUR',
  policy_tier_id        uuid REFERENCES public.policy_tiers(id) ON DELETE SET NULL,
  -- JSONB intake: stores wizard answers (housing prefs, family config, etc.)
  -- See IntakeData type in relopass-api-contracts.ts for full shape
  intake_data           jsonb NOT NULL DEFAULT '{}',
  notes                 text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.cases IS 'Root aggregate for a single relocation. One row = one employee moving from A to B. All requirements, documents, forms, and roadmap steps are children of this row.';
COMMENT ON COLUMN public.cases.corridor IS 'Auto-generated "FR-DE" style key used for vendor matching and requirement lookup.';
COMMENT ON COLUMN public.cases.intake_data IS 'JSONB wizard intake answers: family_config, housing_prefs, temp_housing, financial_tax, school_needs. Shape defined in api-contracts IntakeData.';
COMMENT ON COLUMN public.cases.stage IS 'Workflow stage drives which screens are primary. discovery→dossier→roadmap→in_progress→closing→closed.';

-- ----------------------------------------------------------
-- TABLE: case_dependents
-- Family members traveling on this case.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.case_dependents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id         uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  relationship    text NOT NULL
                    CHECK (relationship IN ('spouse', 'partner', 'child', 'parent', 'other')),
  full_name       text NOT NULL,
  date_of_birth   date,
  nationality     text,
  requires_visa   bool NOT NULL DEFAULT false,
  visa_status     text DEFAULT 'not_started'
                    CHECK (visa_status IN ('not_started', 'in_progress', 'approved', 'rejected')),
  passport_expiry date,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.case_dependents IS 'Spouse, children, and other dependents on a relocation case. Drives dependent visa sub-requirements and family section of the dossier.';

-- ============================================================
-- SECTION 4: ROADMAP & COMPLIANCE
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: requirements
-- AI-computed compliance requirements for a case.
-- These are the "what do you need to do" items discovered by AI.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.requirements (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id             uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  req_number          text NOT NULL,      -- 'REQ-001', 'REQ-012' etc. — display identifier
  title               text NOT NULL,
  description         text,
  pillar              text NOT NULL
                        CHECK (pillar IN ('immigration', 'civil', 'tax', 'housing', 'health', 'education', 'banking', 'employment')),
  category            text NOT NULL,      -- 'Visa Application', 'Document Apostille', 'Address Registration'
  owner_type          text NOT NULL DEFAULT 'employee'
                        CHECK (owner_type IN ('employee', 'hr', 'vendor', 'authority', 'system')),
  confidence_pct      int  NOT NULL DEFAULT 80
                        CHECK (confidence_pct BETWEEN 0 AND 100),
  time_estimate_weeks int,
  is_conditional      bool NOT NULL DEFAULT false,
  condition_key       text,              -- 'kids', 'spouse', 'pet', 'non_eu' — hide if condition unmet
  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'in_progress', 'complete', 'blocked', 'waived')),
  priority            text NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  authority_name      text,
  authority_url       text,
  citations           jsonb NOT NULL DEFAULT '[]',   -- [{source, url, excerpt}]
  computed_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.requirements IS 'AI-discovered compliance requirements per case. Each row is one thing the employee (or HR) needs to do. confidence_pct reflects AI certainty. is_conditional rows are hidden unless the case matches the condition.';
COMMENT ON COLUMN public.requirements.confidence_pct IS '>80% = green bar, 50-80% = yellow, <50% = red. Drives RequirementCard confidence visualization in S2.';
COMMENT ON COLUMN public.requirements.condition_key IS 'If set, this requirement is only shown when cases.intake_data matches the condition (e.g. has_kids=true for "kids" condition).';

-- ----------------------------------------------------------
-- TABLE: requirement_deps
-- Dependency graph between requirements (DAG).
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.requirement_deps (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id   uuid NOT NULL REFERENCES public.requirements(id) ON DELETE CASCADE,
  depends_on_id    uuid NOT NULL REFERENCES public.requirements(id) ON DELETE CASCADE,
  dep_type         text NOT NULL DEFAULT 'blocks'
                     CHECK (dep_type IN ('blocks', 'recommends', 'informs')),
  UNIQUE (requirement_id, depends_on_id)
);

COMMENT ON TABLE public.requirement_deps IS 'DAG of requirement dependencies. blocks=the child cannot start until parent complete. recommends=suggested order. informs=parent data used by child.';

-- ----------------------------------------------------------
-- TABLE: roadmap_tracks
-- The 4 high-level tracks for each case.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.roadmap_tracks (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id               uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  track_key             text NOT NULL
                          CHECK (track_key IN ('visa', 'civil', 'family', 'settle')),
  name                  text NOT NULL,  -- 'Immigration & Visa', 'Civil Registration', 'Family Setup', 'Settling In'
  icon                  text NOT NULL,  -- emoji: '🛂', '🏛', '👨‍👩‍👧', '🏠'
  description           text,
  step_count            int  NOT NULL DEFAULT 0,
  completed_step_count  int  NOT NULL DEFAULT 0,
  completion_pct        int  NOT NULL DEFAULT 0
                          CHECK (completion_pct BETWEEN 0 AND 100),
  is_collapsed          bool NOT NULL DEFAULT false,
  sort_order            int  NOT NULL DEFAULT 0,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, track_key)
);

COMMENT ON TABLE public.roadmap_tracks IS '4 parallel tracks per case: visa, civil, family, settle. Each track groups related roadmap steps. Drives S3 Roadmap screen.';

-- ----------------------------------------------------------
-- TABLE: roadmap_steps
-- Individual action items within a roadmap track.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.roadmap_steps (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id         uuid NOT NULL REFERENCES public.roadmap_tracks(id) ON DELETE CASCADE,
  case_id          uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  title            text NOT NULL,
  description      text,
  status           text NOT NULL DEFAULT 'available'
                     CHECK (status IN ('done', 'active', 'available', 'waiting')),
  owner_type       text NOT NULL DEFAULT 'employee'
                     CHECK (owner_type IN ('employee', 'hr', 'vendor', 'authority', 'system')),
  owner_name       text,              -- Display name of current owner (e.g. 'You', 'HR Team', 'Fragomen')
  due_date         date,
  completed_at     timestamptz,
  sort_order       int  NOT NULL DEFAULT 0,
  is_milestone     bool NOT NULL DEFAULT false,
  requirement_id   uuid REFERENCES public.requirements(id) ON DELETE SET NULL,
  document_ids     uuid[] NOT NULL DEFAULT '{}',
  external_url     text,              -- Authority website, appointment booking link
  note             text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.roadmap_steps IS 'Individual to-do items within a roadmap track. status drives the visual indicator: done=green checkmark, active=accent pulse, available=ghost button, waiting=gray lock.';
COMMENT ON COLUMN public.roadmap_steps.owner_name IS 'Human-readable owner shown in step row: "You", "HR Team", "Fragomen", "French Consulate" etc. Updated when step is assigned.';
COMMENT ON COLUMN public.roadmap_steps.document_ids IS 'UUIDs of documents from the documents table required to complete this step.';

-- ============================================================
-- SECTION 5: DOCUMENTS & FORMS
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: documents
-- Employee document vault. Uploaded by employees, OCR'd by AI.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.documents (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id            uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  owner_id           uuid NOT NULL REFERENCES public.profiles(id),
  owner_type         text NOT NULL DEFAULT 'employee'
                       CHECK (owner_type IN ('employee', 'spouse', 'child', 'parent', 'other')),
  owner_name         text NOT NULL DEFAULT '',
  name               text NOT NULL,           -- 'Passport — Jean Dupont'
  category           text NOT NULL
                       CHECK (category IN ('Identity', 'Civil', 'Employment', 'Education', 'Health', 'Housing', 'Financial', 'Other')),
  doc_type           text NOT NULL,           -- 'Passport', 'Birth Certificate', 'Employment Contract'
  file_url           text,                    -- Supabase Storage URL
  file_ext           text,                    -- 'pdf', 'jpg', 'png'
  file_size_bytes    int,
  status             text NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('verified', 'translating', 'apostille', 'ocr', 'missing', 'pending', 'rejected')),
  fields_extracted   int  NOT NULL DEFAULT 0,
  expires_at         date,
  apostille_needed   bool NOT NULL DEFAULT false,
  translation_needed bool NOT NULL DEFAULT false,
  ocr_data           jsonb NOT NULL DEFAULT '{}',          -- { full_name, date_of_birth, passport_number, ... }
  processing_status  text DEFAULT 'idle'
                       CHECK (processing_status IN ('idle', 'uploading', 'ocr_processing', 'ocr_complete', 'needs_review')),
  uploaded_at        timestamptz,
  verified_at        timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.documents IS 'Central document vault. Every file an employee uploads — passport, birth cert, employment letter — lands here. OCR extracts fields_extracted values into ocr_data, which feeds form auto-fill (forms table).';
COMMENT ON COLUMN public.documents.ocr_data IS 'Extracted field values from OCR: {full_name, date_of_birth, nationality, passport_number, employer_name, salary, ...}. Used to auto-fill government forms.';
COMMENT ON COLUMN public.documents.status IS 'verified=all good, translating=translation in progress, apostille=apostille required, ocr=OCR in progress, missing=required but not uploaded, pending=uploaded awaiting check.';

-- ----------------------------------------------------------
-- TABLE: forms
-- Government form auto-fill tracking.
-- AI fills these from documents.ocr_data.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.forms (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  form_code         text NOT NULL,       -- 'UTL-2010', 'RF-1234', 'GP-7-04', 'HELFO-1'
  form_name         text NOT NULL,       -- 'Declaration of Arrival', 'Residence Registration Form'
  authority         text NOT NULL,       -- 'OFII', 'Ausländerbehörde', 'Gemeente Amsterdam'
  country_code      text NOT NULL,
  for_person        text NOT NULL DEFAULT 'employee'
                      CHECK (for_person IN ('employee', 'spouse', 'child', 'family')),
  deadline          date,
  urgency           text NOT NULL DEFAULT 'flexible'
                      CHECK (urgency IN ('urgent', 'soon', 'flexible')),
  status            text NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft', 'ready', 'submitted', 'approved', 'rejected')),
  fields_total      int  NOT NULL DEFAULT 0,
  fields_auto_filled int NOT NULL DEFAULT 0,
  fields_missing    int  NOT NULL DEFAULT 0,
  -- AI tone: good=AI is confident all fields correct, wait=some fields need manual check, block=critical missing info
  ai_tone           text NOT NULL DEFAULT 'wait'
                      CHECK (ai_tone IN ('good', 'wait', 'block')),
  ai_title          text,    -- e.g. 'Ready to submit — 12/12 fields complete'
  ai_subtitle       text,    -- e.g. 'All fields extracted from passport and employment letter'
  fields_data       jsonb NOT NULL DEFAULT '[]', -- [{label, value, source: 'ai'|'manual'|'missing', field_key, is_required}]
  generated_at      timestamptz,
  submitted_at      timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.forms IS 'Government form auto-fill state. AI populates fields_data from documents.ocr_data. The key UX differentiator: employees see exactly which fields are filled (ai), manual, or missing — saving hours of form-filling.';
COMMENT ON COLUMN public.forms.ai_tone IS 'good=green ring (ready), wait=amber (some manual input needed), block=red X (critical info missing). Drives the form card visual indicator in S4 Dossier screen.';

-- ============================================================
-- SECTION 6: POLICY
-- ============================================================

-- policy_tiers already created in Section 3 (FK dependency)

-- ----------------------------------------------------------
-- TABLE: policy_benefits
-- Individual benefit line items within a policy tier.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_benefits (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_tier_id   uuid NOT NULL REFERENCES public.policy_tiers(id) ON DELETE CASCADE,
  name             text NOT NULL,   -- 'Housing Allowance', 'Flight Reimbursement', 'Language Training'
  category         text NOT NULL,   -- 'Housing', 'Travel', 'Moving', 'Tax', 'Education', 'Healthcare'
  status           text NOT NULL DEFAULT 'covered'
                     CHECK (status IN ('covered', 'partial', 'excluded')),
  cap_description  text,            -- 'Up to €2,000/month for 3 months'
  cap_amount       numeric(12,2),
  cost_estimate    numeric(12,2),
  notes            text,
  sort_order       int  NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.policy_benefits IS 'Individual benefit rows within a policy tier. covered=teal, partial=amber, excluded=red in the policy screen (S5). HR manages these in the Policy Builder (S5b).';

-- ----------------------------------------------------------
-- TABLE: policy_exceptions
-- Employee requests to go beyond their policy tier.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.policy_exceptions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  policy_tier_id    uuid NOT NULL REFERENCES public.policy_tiers(id),
  requested_by      uuid NOT NULL REFERENCES public.profiles(id),
  decided_by        uuid REFERENCES public.profiles(id),
  benefit_id        uuid REFERENCES public.policy_benefits(id) ON DELETE SET NULL,
  exception_type    text NOT NULL
                      CHECK (exception_type IN ('cap_override', 'additional_coverage', 'timeline_extension', 'new_category')),
  justification     text NOT NULL,
  requested_amount  numeric(12,2),
  approved_amount   numeric(12,2),
  status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
  hr_note           text,
  decided_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.policy_exceptions IS 'Structured exception requests. Replaces ad-hoc email threads where employees ask HR for more coverage. The slide-in exception panel in S5 submits here. HR approves/rejects in S7 (pending approvals panel).';

-- ============================================================
-- SECTION 7: VENDORS & MARKETPLACE
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: vendors
-- Global relocation service provider registry.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.vendors (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text NOT NULL,
  slug             text UNIQUE NOT NULL,
  logo_url         text,
  logo_initials    text NOT NULL,         -- 2-3 char initials for avatar fallback
  category         text NOT NULL,         -- 'Moving & Freight', 'Housing Search', 'Immigration Legal'
  description      text,
  website_url      text,
  email            text,
  rating           numeric(3,2) CHECK (rating BETWEEN 0 AND 5),
  rating_count     int NOT NULL DEFAULT 0,
  price_label      text,                  -- 'From €1,200', 'Custom quote', 'Free'
  sla_label        text,                  -- 'Responds in 24h', 'Assessment in 48h'
  is_preferred     bool NOT NULL DEFAULT false,
  is_active        bool NOT NULL DEFAULT true,
  corridor_codes   text[] NOT NULL DEFAULT '{}',   -- ['FR-DE', 'FR-UK', '*'] — '*' = global
  service_types    text[] NOT NULL DEFAULT '{}',
  countries_served text[] NOT NULL DEFAULT '{}',
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.vendors IS 'Global marketplace of vetted relocation vendors. corridor_codes drives smart filtering in S6: only vendors matching the case corridor are shown.';

-- ----------------------------------------------------------
-- TABLE: company_vendors
-- Which vendors a company has contracted / preferred.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.company_vendors (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id       uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  vendor_id        uuid NOT NULL REFERENCES public.vendors(id) ON DELETE CASCADE,
  is_preferred     bool NOT NULL DEFAULT false,
  coverage_status  text NOT NULL DEFAULT 'employee_pays'
                     CHECK (coverage_status IN ('covered', 'partial', 'employee_pays')),
  coverage_notes   text,
  contract_ref     text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, vendor_id)
);

COMMENT ON TABLE public.company_vendors IS 'Company-specific vendor preferences and coverage. covered=company pays, partial=split, employee_pays=employee pays. Shown in vendor card badges on S6.';

-- ============================================================
-- SECTION 8: MESSAGING
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: threads
-- Messaging threads per case.
-- Replaces email inbox fragmentation — everything in one place.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.threads (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  subject           text NOT NULL,
  category          text NOT NULL DEFAULT 'hr'
                      CHECK (category IN ('hr', 'vendors', 'auth', 'family', 'system', 'starred')),
  is_starred        bool NOT NULL DEFAULT false,
  unread_count      int  NOT NULL DEFAULT 0,
  last_message_at   timestamptz,
  created_by        uuid NOT NULL REFERENCES public.profiles(id),
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.threads IS 'Case-scoped messaging threads. category groups threads into folders (hr, vendors, auth, family, system). Drives S10 3-column inbox.';

-- ----------------------------------------------------------
-- TABLE: thread_participants
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.thread_participants (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id      uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  profile_id     uuid NOT NULL REFERENCES public.profiles(id),
  role           text NOT NULL DEFAULT 'member'
                   CHECK (role IN ('owner', 'member', 'observer')),
  joined_at      timestamptz NOT NULL DEFAULT now(),
  last_read_at   timestamptz,
  UNIQUE (thread_id, profile_id)
);

-- ----------------------------------------------------------
-- TABLE: messages
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.messages (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id        uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
  sender_id        uuid NOT NULL REFERENCES public.profiles(id),
  sender_name      text NOT NULL,
  sender_initials  text NOT NULL,
  body             text NOT NULL,
  is_ai_drafted    bool NOT NULL DEFAULT false,
  sent_at          timestamptz NOT NULL DEFAULT now(),
  edited_at        timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.messages IS 'Individual messages. is_ai_drafted=true when composed via the AI panel "Draft with AI" feature.';

-- ----------------------------------------------------------
-- TABLE: message_attachments
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.message_attachments (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id       uuid NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
  file_name        text NOT NULL,
  file_url         text NOT NULL,
  file_ext         text NOT NULL,
  file_size_bytes  int  NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- SECTION 9: AI DISCOVERY RUNS
-- ============================================================

-- ----------------------------------------------------------
-- TABLE: case_discovery_runs
-- Audit log of AI compliance discovery runs per case.
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.case_discovery_runs (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id             uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
  triggered_by        uuid REFERENCES public.profiles(id),
  status              text NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'complete', 'failed')),
  requirements_found  int  NOT NULL DEFAULT 0,
  documents_required  int  NOT NULL DEFAULT 0,
  estimated_weeks     int,
  estimated_cost      numeric(12,2),
  authorities_count   int  NOT NULL DEFAULT 0,
  sources_used        int  NOT NULL DEFAULT 0,
  model_used          text,
  completed_at        timestamptz,
  error_text          text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.case_discovery_runs IS 'Each time the AI scans a case corridor for compliance requirements, a run is logged here. The discovery banner stats in S2 derive from the latest completed run.';

-- ============================================================
-- SECTION 10: UPDATED_AT TRIGGERS
-- ============================================================

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.companies
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.discovery_sources
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.policy_tiers
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.cases
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.requirements
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.roadmap_tracks
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.roadmap_steps
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.documents
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.forms
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.policy_benefits
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.policy_exceptions
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.vendors
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

CREATE TRIGGER handle_updated_at BEFORE UPDATE ON public.threads
  FOR EACH ROW EXECUTE FUNCTION moddatetime('updated_at');

-- ============================================================
-- SECTION 11: INDEXES
-- ============================================================

-- profiles
CREATE INDEX IF NOT EXISTS idx_profiles_company_id  ON public.profiles(company_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email        ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role         ON public.profiles(role);

-- cases
CREATE INDEX IF NOT EXISTS idx_cases_company_id      ON public.cases(company_id);
CREATE INDEX IF NOT EXISTS idx_cases_employee_id     ON public.cases(employee_id);
CREATE INDEX IF NOT EXISTS idx_cases_hr_owner_id     ON public.cases(hr_owner_id);
CREATE INDEX IF NOT EXISTS idx_cases_status          ON public.cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_corridor        ON public.cases(corridor);
CREATE INDEX IF NOT EXISTS idx_cases_stage           ON public.cases(stage);
CREATE INDEX IF NOT EXISTS idx_cases_policy_tier_id  ON public.cases(policy_tier_id);

-- case_dependents
CREATE INDEX IF NOT EXISTS idx_case_dependents_case  ON public.case_dependents(case_id);

-- requirements
CREATE INDEX IF NOT EXISTS idx_requirements_case_id  ON public.requirements(case_id);
CREATE INDEX IF NOT EXISTS idx_requirements_pillar   ON public.requirements(pillar);
CREATE INDEX IF NOT EXISTS idx_requirements_status   ON public.requirements(status);

-- requirement_deps
CREATE INDEX IF NOT EXISTS idx_req_deps_req_id       ON public.requirement_deps(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_deps_depends_on   ON public.requirement_deps(depends_on_id);

-- roadmap_tracks
CREATE INDEX IF NOT EXISTS idx_rt_case_id            ON public.roadmap_tracks(case_id);
CREATE INDEX IF NOT EXISTS idx_rt_track_key          ON public.roadmap_tracks(case_id, track_key);

-- roadmap_steps
CREATE INDEX IF NOT EXISTS idx_rs_track_id           ON public.roadmap_steps(track_id);
CREATE INDEX IF NOT EXISTS idx_rs_case_id            ON public.roadmap_steps(case_id);
CREATE INDEX IF NOT EXISTS idx_rs_status             ON public.roadmap_steps(status);

-- documents
CREATE INDEX IF NOT EXISTS idx_docs_case_id          ON public.documents(case_id);
CREATE INDEX IF NOT EXISTS idx_docs_owner_id         ON public.documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_docs_status           ON public.documents(status);
CREATE INDEX IF NOT EXISTS idx_docs_category         ON public.documents(category);

-- forms
CREATE INDEX IF NOT EXISTS idx_forms_case_id         ON public.forms(case_id);
CREATE INDEX IF NOT EXISTS idx_forms_status          ON public.forms(status);
CREATE INDEX IF NOT EXISTS idx_forms_urgency         ON public.forms(urgency);

-- policy_tiers
CREATE INDEX IF NOT EXISTS idx_pt_company_id         ON public.policy_tiers(company_id);

-- policy_benefits
CREATE INDEX IF NOT EXISTS idx_pb_tier_id            ON public.policy_benefits(policy_tier_id);

-- policy_exceptions
CREATE INDEX IF NOT EXISTS idx_pe_case_id            ON public.policy_exceptions(case_id);
CREATE INDEX IF NOT EXISTS idx_pe_status             ON public.policy_exceptions(status);
CREATE INDEX IF NOT EXISTS idx_pe_requested_by       ON public.policy_exceptions(requested_by);

-- vendors
CREATE INDEX IF NOT EXISTS idx_vendors_category      ON public.vendors(category);
CREATE INDEX IF NOT EXISTS idx_vendors_is_active     ON public.vendors(is_active);

-- company_vendors
CREATE INDEX IF NOT EXISTS idx_cv_company_id         ON public.company_vendors(company_id);
CREATE INDEX IF NOT EXISTS idx_cv_vendor_id          ON public.company_vendors(vendor_id);

-- threads
CREATE INDEX IF NOT EXISTS idx_threads_case_id       ON public.threads(case_id);
CREATE INDEX IF NOT EXISTS idx_threads_category      ON public.threads(category);
CREATE INDEX IF NOT EXISTS idx_threads_last_msg      ON public.threads(last_message_at DESC NULLS LAST);

-- thread_participants
CREATE INDEX IF NOT EXISTS idx_tp_thread_id          ON public.thread_participants(thread_id);
CREATE INDEX IF NOT EXISTS idx_tp_profile_id         ON public.thread_participants(profile_id);

-- messages
CREATE INDEX IF NOT EXISTS idx_messages_thread_id    ON public.messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at      ON public.messages(sent_at DESC);

-- case_discovery_runs
CREATE INDEX IF NOT EXISTS idx_cdr_case_id           ON public.case_discovery_runs(case_id);
CREATE INDEX IF NOT EXISTS idx_cdr_status            ON public.case_discovery_runs(status);

-- ============================================================
-- SECTION 12: ROW LEVEL SECURITY (RLS)
-- ============================================================

ALTER TABLE public.companies         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.countries         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.discovery_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_tiers      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cases             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_dependents   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requirements      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requirement_deps  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_tracks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roadmap_steps     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.forms             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_benefits   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vendors           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_vendors   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.threads           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thread_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_discovery_runs ENABLE ROW LEVEL SECURITY;

-- Helper: get current user's company_id and role
-- Use these functions in policies to avoid repeated subqueries.
CREATE OR REPLACE FUNCTION auth.my_company_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT company_id FROM public.profiles
  WHERE id = (SELECT auth.uid())
$$;

CREATE OR REPLACE FUNCTION auth.my_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT role FROM public.profiles
  WHERE id = (SELECT auth.uid())
$$;

-- --- PROFILES ---
-- Users can read/update own profile; HR can read profiles in same company; admin reads all.
CREATE POLICY profiles_select_own ON public.profiles
  FOR SELECT USING (id = (SELECT auth.uid()));

CREATE POLICY profiles_select_hr ON public.profiles
  FOR SELECT USING (
    auth.my_role() IN ('hr', 'admin')
    AND company_id = auth.my_company_id()
  );

CREATE POLICY profiles_select_admin ON public.profiles
  FOR SELECT USING (auth.my_role() = 'admin');

CREATE POLICY profiles_update_own ON public.profiles
  FOR UPDATE USING (id = (SELECT auth.uid()));

-- --- COMPANIES ---
CREATE POLICY companies_select_members ON public.companies
  FOR SELECT USING (id = auth.my_company_id());

CREATE POLICY companies_all_admin ON public.companies
  FOR ALL USING (auth.my_role() = 'admin');

-- --- COUNTRIES & DISCOVERY SOURCES (public read) ---
CREATE POLICY countries_public_read ON public.countries
  FOR SELECT USING (is_active = true);

CREATE POLICY discovery_sources_public_read ON public.discovery_sources
  FOR SELECT USING (is_active = true);

CREATE POLICY discovery_sources_admin_write ON public.discovery_sources
  FOR ALL USING (auth.my_role() = 'admin');

-- --- CASES ---
CREATE POLICY cases_select_employee ON public.cases
  FOR SELECT USING (employee_id = (SELECT auth.uid()));

CREATE POLICY cases_select_hr ON public.cases
  FOR SELECT USING (
    auth.my_role() IN ('hr', 'admin')
    AND company_id = auth.my_company_id()
  );

CREATE POLICY cases_insert_hr ON public.cases
  FOR INSERT WITH CHECK (
    auth.my_role() IN ('hr', 'admin')
    AND company_id = auth.my_company_id()
  );

CREATE POLICY cases_update_hr ON public.cases
  FOR UPDATE USING (
    auth.my_role() IN ('hr', 'admin')
    AND company_id = auth.my_company_id()
  );

CREATE POLICY cases_all_admin ON public.cases
  FOR ALL USING (auth.my_role() = 'admin');

-- --- CHILD TABLES: share case-level access ---
-- Helper macro pattern: policies on child tables join through cases.
-- case_dependents, requirements, requirement_deps, roadmap_tracks, roadmap_steps,
-- documents, forms, policy_exceptions, threads, messages, case_discovery_runs

CREATE POLICY case_dependents_via_case ON public.case_dependents FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY requirements_via_case ON public.requirements FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY requirement_deps_via_req ON public.requirement_deps FOR ALL
  USING (requirement_id IN (
    SELECT id FROM public.requirements
    WHERE case_id IN (
      SELECT id FROM public.cases
      WHERE employee_id = (SELECT auth.uid())
         OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
    )
  ));

CREATE POLICY roadmap_tracks_via_case ON public.roadmap_tracks FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY roadmap_steps_via_case ON public.roadmap_steps FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY documents_via_case ON public.documents FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY forms_via_case ON public.forms FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY threads_via_case ON public.threads FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY thread_participants_via_thread ON public.thread_participants FOR ALL
  USING (thread_id IN (
    SELECT t.id FROM public.threads t
    JOIN public.cases c ON c.id = t.case_id
    WHERE c.employee_id = (SELECT auth.uid())
       OR (c.company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY messages_via_thread ON public.messages FOR ALL
  USING (thread_id IN (
    SELECT t.id FROM public.threads t
    JOIN public.cases c ON c.id = t.case_id
    WHERE c.employee_id = (SELECT auth.uid())
       OR (c.company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY message_attachments_via_msg ON public.message_attachments FOR ALL
  USING (message_id IN (
    SELECT m.id FROM public.messages m
    JOIN public.threads t ON t.id = m.thread_id
    JOIN public.cases c ON c.id = t.case_id
    WHERE c.employee_id = (SELECT auth.uid())
       OR (c.company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY case_discovery_runs_via_case ON public.case_discovery_runs FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

CREATE POLICY policy_exceptions_via_case ON public.policy_exceptions FOR ALL
  USING (case_id IN (
    SELECT id FROM public.cases
    WHERE employee_id = (SELECT auth.uid())
       OR (company_id = auth.my_company_id() AND auth.my_role() IN ('hr','admin'))
  ));

-- --- POLICY TIERS & BENEFITS ---
CREATE POLICY policy_tiers_read_company ON public.policy_tiers
  FOR SELECT USING (company_id = auth.my_company_id());

CREATE POLICY policy_tiers_write_hr ON public.policy_tiers
  FOR ALL USING (
    company_id = auth.my_company_id()
    AND auth.my_role() IN ('hr','admin')
  );

CREATE POLICY policy_benefits_via_tier ON public.policy_benefits FOR ALL
  USING (policy_tier_id IN (
    SELECT id FROM public.policy_tiers
    WHERE company_id = auth.my_company_id()
  ));

-- --- VENDORS ---
CREATE POLICY vendors_public_read ON public.vendors
  FOR SELECT USING (is_active = true);

CREATE POLICY vendors_admin_write ON public.vendors
  FOR ALL USING (auth.my_role() = 'admin');

CREATE POLICY company_vendors_hr ON public.company_vendors FOR ALL
  USING (
    company_id = auth.my_company_id()
    AND auth.my_role() IN ('hr','admin')
  );

-- ============================================================
-- SECTION 13: SEED DATA — 16 COUNTRIES
-- ============================================================

INSERT INTO public.countries (code, name, flag_emoji, region, visa_complexity, processing_weeks_min, processing_weeks_max, popular_corridors, requires_apostille, key_authorities, notes)
VALUES
  ('FR', 'France',         '🇫🇷', 'EU',            'medium',    4,  8,  ARRAY['FR-DE','FR-GB','FR-US','FR-NL'], false,
   '[{"name":"OFII","url":"https://www.ofii.fr","type":"immigration"},{"name":"Service Public","url":"https://www.service-public.fr","type":"civil"}]',
   'EU freedom of movement simplifies most EU→FR cases. Non-EU requires long-stay visa + OFII procedure post-arrival.'),

  ('DE', 'Germany',        '🇩🇪', 'EU',            'high',      6,  12, ARRAY['DE-FR','DE-GB','DE-NL','DE-US'], true,
   '[{"name":"Ausländerbehörde","url":"https://www.bamf.de","type":"immigration"},{"name":"Bundesagentur für Arbeit","url":"https://www.arbeitsagentur.de","type":"labour"}]',
   'EU Blue Card popular for skilled workers. Anmeldung (registration) required within 2 weeks of arrival.'),

  ('GB', 'United Kingdom', '🇬🇧', 'EU',            'high',      8,  16, ARRAY['GB-DE','GB-FR','GB-US','GB-NL'], true,
   '[{"name":"Home Office","url":"https://www.gov.uk/browse/visas-immigration","type":"immigration"},{"name":"UKVI","url":"https://www.gov.uk/government/organisations/uk-visas-and-immigration","type":"immigration"}]',
   'Post-Brexit: EU citizens need Skilled Worker visa. Sponsor licence required. Right to Work check mandatory.'),

  ('US', 'United States',  '🇺🇸', 'North America', 'very_high', 12, 52, ARRAY['US-GB','US-DE','US-FR','US-IN'], true,
   '[{"name":"USCIS","url":"https://www.uscis.gov","type":"immigration"},{"name":"US Embassy","url":"https://travel.state.gov","type":"immigration"}]',
   'H-1B cap-subject, lottery in April. L-1 (ICT) faster for intra-company. O-1 for exceptional talent. Plan 12+ months for H-1B.'),

  ('NL', 'Netherlands',    '🇳🇱', 'EU',            'medium',    4,  8,  ARRAY['NL-GB','NL-DE','NL-BE'], false,
   '[{"name":"IND","url":"https://ind.nl/en","type":"immigration"},{"name":"Gemeente Amsterdam","url":"https://www.amsterdam.nl","type":"civil"}]',
   '30% tax ruling available for skilled migrants. BSN registration at municipality within 5 days of arrival.'),

  ('BE', 'Belgium',        '🇧🇪', 'EU',            'medium',    4,  10, ARRAY['BE-FR','BE-DE','BE-NL'], false,
   '[{"name":"Office des Étrangers","url":"https://dofi.ibz.be","type":"immigration"},{"name":"Commune","url":"https://www.belgium.be","type":"civil"}]',
   'Register at commune (Gemeentehuis) within 8 days of arrival. Multiple language regions — document requirements vary.'),

  ('CH', 'Switzerland',    '🇨🇭', 'Europe',        'high',      6,  14, ARRAY['CH-DE','CH-FR','CH-IT'], true,
   '[{"name":"SEM","url":"https://www.sem.admin.ch","type":"immigration"},{"name":"Kantonales Migrationsamt","url":"https://www.ch.ch","type":"immigration"}]',
   'Not EU — requires work permit (L/B/C) sponsored by employer. Bilateral agreements with EU simplify process slightly.'),

  ('ES', 'Spain',          '🇪🇸', 'EU',            'medium',    4,  10, ARRAY['ES-DE','ES-FR','ES-GB'], true,
   '[{"name":"Extranjería","url":"https://extranjeros.inclusion.gob.es","type":"immigration"},{"name":"Registro Civil","url":"https://www.mjusticia.gob.es","type":"civil"}]',
   'NIE (Número de Identificación de Extranjero) required for any financial/legal activity. EU citizens register at Padrón Municipal.'),

  ('IT', 'Italy',          '🇮🇹', 'EU',            'medium',    4,  10, ARRAY['IT-DE','IT-FR','IT-GB'], true,
   '[{"name":"Questura","url":"https://www.poliziadistato.it","type":"immigration"},{"name":"Agenzia delle Entrate","url":"https://www.agenziaentrate.gov.it","type":"tax"}]',
   'Codice Fiscale (tax code) required for almost everything. Permesso di Soggiorno needed for non-EU citizens.'),

  ('PT', 'Portugal',       '🇵🇹', 'EU',            'medium',    3,  8,  ARRAY['PT-GB','PT-DE','PT-FR'], false,
   '[{"name":"SEF/AIMA","url":"https://aima.gov.pt","type":"immigration"},{"name":"Finanças","url":"https://www.portaldasfinancas.gov.pt","type":"tax"}]',
   'NHR tax regime attractive for qualified professionals. NIF (tax number) available from local Finanças office or embassy.'),

  ('SG', 'Singapore',      '🇸🇬', 'APAC',          'medium',    4,  8,  ARRAY['SG-IN','SG-GB','SG-AU'], false,
   '[{"name":"MOM","url":"https://www.mom.gov.sg","type":"immigration"},{"name":"ICA","url":"https://www.ica.gov.sg","type":"immigration"}]',
   'Employment Pass for professionals (min SGD 5,000/month). S Pass for mid-skilled. Fast processing (3-8 weeks). CPF contribution mandatory.'),

  ('AE', 'United Arab Emirates', '🇦🇪', 'MENA',   'medium',    2,  6,  ARRAY['AE-IN','AE-GB','AE-FR'], false,
   '[{"name":"GDRFA","url":"https://www.gdrfad.gov.ae","type":"immigration"},{"name":"MOHRE","url":"https://www.mohre.gov.ae","type":"labour"}]',
   'Employment visa + work permit now combined. Golden Visa available for investors/skilled talent. No income tax.'),

  ('CA', 'Canada',         '🇨🇦', 'North America', 'high',      6,  16, ARRAY['CA-US','CA-GB','CA-FR'], true,
   '[{"name":"IRCC","url":"https://www.canada.ca/immigration","type":"immigration"}]',
   'Express Entry system for permanent residency. Intra-company transferees via C11 work permit (fast). LMIA may be required.'),

  ('AU', 'Australia',      '🇦🇺', 'APAC',          'high',      8,  20, ARRAY['AU-GB','AU-IN','AU-SG'], true,
   '[{"name":"Home Affairs","url":"https://immi.homeaffairs.gov.au","type":"immigration"},{"name":"TFN","url":"https://www.ato.gov.au","type":"tax"}]',
   '482 TSS (Temporary Skill Shortage) visa most common. Medical exam required. Police clearance certificate needed.'),

  ('IN', 'India',          '🇮🇳', 'APAC',          'high',      8,  16, ARRAY['IN-DE','IN-GB','IN-US','IN-AE'], true,
   '[{"name":"FRRO","url":"https://indianfrro.gov.in","type":"immigration"},{"name":"MHA","url":"https://mha.gov.in","type":"immigration"}]',
   'Employment visa from Indian embassy abroad. FRRO registration required within 14 days of arrival if stay >180 days.'),

  ('JP', 'Japan',          '🇯🇵', 'APAC',          'medium',    6,  12, ARRAY['JP-SG','JP-US','JP-DE'], true,
   '[{"name":"Immigration Services Agency","url":"https://www.isa.go.jp/en/","type":"immigration"},{"name":"My Number","url":"https://www.cao.go.jp/bangouseido","type":"civil"}]',
   'Work visa (Engineer/Specialist in Humanities) most common. Resident card (Zairyu card) issued on arrival. My Number registration required.')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- SECTION 14: SEED DATA — 8 VENDORS
-- ============================================================

INSERT INTO public.vendors (name, slug, logo_initials, category, description, website_url, rating, rating_count, price_label, sla_label, is_preferred, corridor_codes, service_types, countries_served)
VALUES
  ('Fragomen Worldwide',
   'fragomen',
   'FR',
   'Immigration Legal',
   'Global leader in immigration legal services. 50+ countries, specialist attorneys for EU Blue Card, UK Skilled Worker, US H-1B, and ICT permits. Pre-filing eligibility assessment included.',
   'https://www.fragomen.com',
   4.9, 2847,
   'Custom quote',
   'Assessment in 48h',
   true,
   ARRAY['*'],
   ARRAY['immigration_legal', 'visa_application', 'work_permit', 'permanent_residency'],
   ARRAY['FR','DE','GB','NL','BE','CH','ES','US','SG','AE','CA','AU','IN','JP']),

  ('SIRVA Worldwide',
   'sirva',
   'SV',
   'Moving & Freight',
   'End-to-end international moving and destination services. Packing, freight, customs clearance, and storage in 180+ countries. Volume discounts for corporate accounts.',
   'https://www.sirva.com',
   4.6, 1923,
   'From €1,800',
   'Quote in 24h',
   true,
   ARRAY['*'],
   ARRAY['moving_freight', 'packing', 'customs_clearance', 'storage', 'destination_services'],
   ARRAY['FR','DE','GB','NL','BE','CH','ES','IT','US','SG','AE','CA','AU']),

  ('Déménagements Delahaye',
   'delahaye',
   'DD',
   'Moving & Freight',
   'Specialist Franco-German moving company. Volume-optimized loads, full customs documentation for FR↔DE corridor. Family-run since 1987, known for punctuality and care.',
   'https://www.delahaye-demenagements.fr',
   4.7, 412,
   'From €950',
   'Quote in 12h',
   false,
   ARRAY['FR-DE','DE-FR','FR-BE','FR-NL','FR-CH'],
   ARRAY['moving_freight', 'packing', 'storage'],
   ARRAY['FR','DE','BE','NL','CH']),

  ('BerlinReloc GmbH',
   'berlinreloc',
   'BR',
   'Housing Search',
   'Dedicated housing search for international relocatees moving to Germany. Apartment sourcing, Mietschuldenfreiheitsbescheinigung translation, landlord negotiation, and Anmeldung assistance.',
   'https://www.berlinreloc.de',
   4.5, 318,
   'From €1,200',
   'Responds in 24h',
   false,
   ARRAY['*-DE','DE-DE'],
   ARRAY['housing_search', 'tenant_support', 'civil_registration'],
   ARRAY['DE']),

  ('NestFinders Europe',
   'nestfinders',
   'NF',
   'Housing Search',
   'Pan-European housing search platform. Agent network in Amsterdam, London, Brussels, and Zurich. Virtual tours, neighbourhood reports, school proximity analysis, and lease review.',
   'https://www.nestfinders.eu',
   4.4, 521,
   'From €1,500',
   'First properties in 48h',
   false,
   ARRAY['*-NL','*-GB','*-BE','*-CH','NL-*','GB-*','BE-*'],
   ARRAY['housing_search', 'virtual_tours', 'school_proximity', 'lease_review'],
   ARRAY['NL','GB','BE','CH']),

  ('TaxConnect International',
   'taxconnect',
   'TC',
   'Tax Advisory',
   'Dual-tax advisory for international relocatees. Specialises in FR, DE, UK, NL tax treaties. Tax equalization calculations, split-year returns, and 30% ruling applications in NL.',
   'https://www.taxconnect-intl.com',
   4.3, 674,
   'From €800',
   'Initial call in 48h',
   false,
   ARRAY['*'],
   ARRAY['tax_advisory', 'dual_taxation', 'tax_equalization', 'social_security'],
   ARRAY['FR','DE','GB','NL','BE','CH']),

  ('SchoolFinder Europe',
   'schoolfinder',
   'SF',
   'School Search',
   'International school research and enrollment support. Database of 400+ international and bilingual schools across DE, FR, NL, CH. Application management and deadline tracking.',
   'https://www.schoolfinder-europe.com',
   4.5, 289,
   'From €600',
   'Report in 72h',
   false,
   ARRAY['*-DE','*-FR','*-NL','*-CH','*-BE'],
   ARRAY['school_search', 'enrollment_support', 'application_management'],
   ARRAY['DE','FR','NL','CH','BE']),

  ('ExpatBanking',
   'expatbanking',
   'EB',
   'Banking Setup',
   'Streamlined bank account opening for international relocatees before or on arrival. Partners with N26, Bunq, Wise, and HSBC Expat. Digital onboarding in 48h for EU residents.',
   'https://www.expat-banking.com',
   4.2, 856,
   'Free',
   'Account in 48h',
   false,
   ARRAY['*'],
   ARRAY['banking_setup', 'account_opening', 'digital_onboarding'],
   ARRAY['FR','DE','GB','NL','BE','CH','ES','IT','PT','SG','AE'])
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- END OF MIGRATION
-- ============================================================
-- To apply: supabase db push
-- Validate: supabase db diff --use-migra
-- ============================================================
