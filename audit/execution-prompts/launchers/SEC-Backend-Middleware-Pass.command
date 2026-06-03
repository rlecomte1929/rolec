#!/bin/bash
# Sequential combo launcher: runs SEC-001 (debug gating) then SEC-005 (security headers)
# in the SAME Terminal window — same `backend/main.py` middleware stack, so they share
# context. SEC-005 starts only after you quit SEC-001's Claude Code session.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_001="$REPO/audit/execution-prompts/SEC-001-debug-endpoints.md"
PROMPT_005="$REPO/audit/execution-prompts/SEC-005-security-headers.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  COMBO: Backend Middleware Pass
  Step 1: SEC-001 — Gate /debug/* endpoints (P0)
  Step 2: SEC-005 — Security Headers + CSP (P1)
  Both touch backend/main.py middleware stack.
  Step 2 runs after you quit Step 1's Claude Code session.
================================================================

Step 1 prompt (first 8 lines):
EOF
head -8 "$PROMPT_001"
echo ""
echo "Step 2 prompt (first 8 lines):"
head -8 "$PROMPT_005"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to start Step 1 (Ctrl+C to abort)..."

echo ""
echo "========== STEP 1: SEC-001 =========="
claude "$(cat "$PROMPT_001")"

echo ""
echo "Step 1 finished. Press ENTER to start Step 2 (SEC-005), or Ctrl+C to stop here."
read -p ""

echo ""
echo "========== STEP 2: SEC-005 =========="
exec claude "$(cat "$PROMPT_005")"
