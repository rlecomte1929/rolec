#!/usr/bin/env bash
set -euo pipefail

# Manual script for transition_assignment RPC.
# Required env:
#   SUPABASE_URL=https://<project>.supabase.co
#   SUPABASE_ANON_KEY=...
#   SUPABASE_JWT=... (user access token)
#   ASSIGNMENT_ID=...
#
# Example:
#   SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_JWT=... ASSIGNMENT_ID=... \
#     ./scripts/transition_assignment_test.sh EMPLOYEE_SUBMIT

ACTION="${1:-EMPLOYEE_SUBMIT}"

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_ANON_KEY:-}" || -z "${SUPABASE_JWT:-}" || -z "${ASSIGNMENT_ID:-}" ]]; then
  echo "Missing env vars. See script header."
  exit 1
fi

curl -sS "${SUPABASE_URL}/rest/v1/rpc/transition_assignment" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_JWT}" \
  -H "Content-Type: application/json" \
  -d "{\"p_assignment_id\":\"${ASSIGNMENT_ID}\",\"p_action\":\"${ACTION}\",\"p_note\":\"Manual test\"}" | jq .
