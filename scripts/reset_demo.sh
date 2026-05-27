#!/usr/bin/env bash
# =============================================================================
# scripts/reset_demo.sh — Reset ReloPass demo data to clean state
# MVP-8 (AIQ-375)
#
# Usage:
#   DATABASE_URL="postgresql://..." ./scripts/reset_demo.sh
#   npm run seed:demo              (via package.json)
#
# What it does:
#   1. Deletes all demo data rows (keyed by the fixed demo UUIDs)
#   2. Re-runs scripts/seed_demo.sql to recreate clean demo state
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED_FILE="$SCRIPT_DIR/seed_demo.sql"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "❌  DATABASE_URL is not set. Export it first:"
  echo "    export DATABASE_URL=\"postgresql://postgres:password@host:5432/postgres\""
  exit 1
fi

echo "🗑️  Clearing existing demo data..."
psql "$DATABASE_URL" <<'SQL'
BEGIN;

-- Auth identities + users (must go before profiles)
DELETE FROM auth.identities
WHERE user_id IN (
  'd0e00010-0000-4000-8000-000000000010'::uuid,
  'd0e00020-0000-4000-8000-000000000020'::uuid,
  'd0e00030-0000-4000-8000-000000000030'::uuid,
  'd0e00100-0000-4000-8000-000000000100'::uuid,
  'd0e00200-0000-4000-8000-000000000200'::uuid,
  'd0e00300-0000-4000-8000-000000000300'::uuid
);

DELETE FROM auth.users
WHERE id IN (
  'd0e00010-0000-4000-8000-000000000010'::uuid,
  'd0e00020-0000-4000-8000-000000000020'::uuid,
  'd0e00030-0000-4000-8000-000000000030'::uuid,
  'd0e00100-0000-4000-8000-000000000100'::uuid,
  'd0e00200-0000-4000-8000-000000000200'::uuid,
  'd0e00300-0000-4000-8000-000000000300'::uuid
);

-- Backend users (public.users — ReloPass auth table)
DELETE FROM public.users
WHERE id IN (
  'd0e00010-0000-4000-8000-000000000010',
  'd0e00020-0000-4000-8000-000000000020',
  'd0e00030-0000-4000-8000-000000000030',
  'd0e00100-0000-4000-8000-000000000100',
  'd0e00200-0000-4000-8000-000000000200',
  'd0e00300-0000-4000-8000-000000000300'
);

-- Demo fixed IDs
DELETE FROM public.immigration_cases
WHERE id IN (
  'd0e00500-0000-4000-8000-000000000500',
  'd0e00600-0000-4000-8000-000000000600',
  'd0e00700-0000-4000-8000-000000000700'
);

DELETE FROM public.case_assignments
WHERE id IN ('demo-ca-001', 'demo-ca-002', 'demo-ca-003');

DELETE FROM public.case_vendor_shortlist
WHERE case_id IN (
  '5b16522e-e899-4db2-bc8d-95af00af8c79',
  '1cbc563e-b984-44b5-adb3-74912d79a84d',
  '65d7aea8-bc11-413a-8d28-8b9818190a2a'
);

DELETE FROM public.case_budget_lines
WHERE case_id IN (
  '5b16522e-e899-4db2-bc8d-95af00af8c79',
  '1cbc563e-b984-44b5-adb3-74912d79a84d',
  '65d7aea8-bc11-413a-8d28-8b9818190a2a'
);

DELETE FROM public.cases
WHERE id IN (
  '5b16522e-e899-4db2-bc8d-95af00af8c79',
  '1cbc563e-b984-44b5-adb3-74912d79a84d',
  '65d7aea8-bc11-413a-8d28-8b9818190a2a'
);

DELETE FROM public.profiles
WHERE id IN (
  'd0e00010-0000-4000-8000-000000000010',
  'd0e00020-0000-4000-8000-000000000020',
  'd0e00030-0000-4000-8000-000000000030',
  'd0e00100-0000-4000-8000-000000000100',
  'd0e00200-0000-4000-8000-000000000200',
  'd0e00300-0000-4000-8000-000000000300'
);

DELETE FROM public.companies
WHERE id IN (
  'd0e00001-0000-4000-8000-000000000001',
  'd0e00002-0000-4000-8000-000000000002',
  'd0e00003-0000-4000-8000-000000000003'
);

COMMIT;
SQL

echo "✅  Demo data cleared."
echo ""
echo "🌱  Seeding fresh demo data..."
psql "$DATABASE_URL" -f "$SEED_FILE"

echo ""
echo "✅  Demo seed complete. 3 scenarios ready:"
echo ""
echo "    Scenario 1: Adrien Martin    — GlobalTech SAS    — FR→DE — EU Blue Card"
echo "    Scenario 2: Céline Dupont    — Meridian Capital  — FR→GB — UK Skilled Worker"
echo "    Scenario 3: Carlos Rivera    — Nexora Labs       — ES→NL — EEA Registration"
echo ""
echo "    Demo credentials (password: Demo2026!)"
echo "    HR logins :"
echo "      hannah.hr@globaltech-demo.com"
echo "      sophie.hr@meridian-demo.com"
echo "      marta.hr@nexora-demo.com"
echo "    Employee logins:"
echo "      adrien.martin@globaltech-demo.com"
echo "      celine.dupont@meridian-demo.com"
echo "      carlos.rivera@nexora-demo.com"
