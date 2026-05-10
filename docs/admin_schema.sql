-- Admin console schema (portable SQL, Postgres-compatible)

CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  email TEXT,
  full_name TEXT,
  company_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_allowlist (
  email TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 1,
  added_by_user_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  reason TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT,
  size_band TEXT,
  address TEXT,
  phone TEXT,
  hr_contact TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  band TEXT,
  assignment_type TEXT,
  relocation_case_id TEXT,
  status TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hr_users (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  permissions_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_cases (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  created_by_profile_id TEXT NOT NULL,
  employee_id TEXT,
  hr_profile_id TEXT,
  category TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT,
  last_error_code TEXT,
  last_error_context_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_case_notes (
  id TEXT PRIMARY KEY,
  support_case_id TEXT NOT NULL,
  author_user_id TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_sessions (
  token TEXT PRIMARY KEY,
  actor_user_id TEXT NOT NULL,
  target_user_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eligibility_overrides (
  id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL,
  category TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 1,
  expires_at TEXT,
  note TEXT,
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_support_cases_status ON support_cases(status);
CREATE INDEX IF NOT EXISTS idx_support_cases_severity ON support_cases(severity);
CREATE INDEX IF NOT EXISTS idx_relocation_cases_status ON relocation_cases(status);
