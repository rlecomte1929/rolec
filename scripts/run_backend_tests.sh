#!/usr/bin/env bash
# CI sqlite pytest lane (backend-tests in .github/workflows/ci.yml).
# Two invocations, same as the job: full-suite discovery, then the four
# isolation-sensitive files on their own.
#
# Call 1 — full-suite discovery. Env-dependent / import-broken files are in
# collect_ignore (backend/tests/conftest.py). The 4 --ignore'd files below
# PASS in isolation but leak/collide when run with the whole suite (shared
# sqlite state); they keep gating via Call 2 (isolation fix is a follow-up).
#
# [AIQ-1780] test_case_documents_rce_bridge joined this list rather than
# being made suite-safe. It needs the real Database (the root conftest
# installs a MagicMock), which means reaching for the same
# sys.modules.pop + engine-swap dance test_case_documents_flow uses. Two
# rounds of narrowing — deferring the harness import to setUp, restoring
# dbmod._engine/_is_sqlite in tearDown — each fixed the module it was
# breaking and shifted the collision to another (catalog_promotion →
# providers_company_resolution), which is the signature of the shared
# `db` singleton rather than of anything this file does wrong. Root-causing
# that is the same deferred isolation fix the other three are waiting on.
# [AIQ-1852] `not postgres` — that lane needs a real uuid type and a
# migration-built schema; sqlite can provide neither. It runs in
# backend-tests-postgres, not here.
#
# Usage (from repo root, matching CI env):
#   RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 \
#     DATABASE_URL=sqlite:///./ci_test.db \
#     scripts/run_backend_tests.sh
#
# Prefer the repo venv if you are not already on Python 3.11:
#   PYTHON="$(pwd)/.venv311/bin/python" scripts/run_backend_tests.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# CI's setup-python step puts 3.11 on PATH as `python`. Override locally with PYTHON=.
PYTHON="${PYTHON:-python}"

# Match backend-tests job env so a local run does not inherit a leftover Postgres URL.
export DATABASE_URL="${DATABASE_URL:-sqlite:///./ci_test.db}"

# Call 1 — full-suite discovery.
"${PYTHON}" -m pytest -q -c backend/pytest.ini --rootdir . \
  backend/tests scripts/tests \
  -m "not integration and not policy_assistant_audit and not postgres" \
  --ignore=backend/tests/test_llm_client_text.py \
  --ignore=backend/tests/test_policy_propagation.py \
  --ignore=backend/tests/test_supabase_password_sync.py \
  --ignore=backend/tests/test_case_documents_rce_bridge.py

# Call 2 — the isolation-sensitive previously-gated files, on their own.
"${PYTHON}" -m pytest -q -c backend/pytest.ini --rootdir . \
  backend/tests/test_llm_client_text.py \
  backend/tests/test_policy_propagation.py \
  backend/tests/test_supabase_password_sync.py \
  backend/tests/test_case_documents_rce_bridge.py
