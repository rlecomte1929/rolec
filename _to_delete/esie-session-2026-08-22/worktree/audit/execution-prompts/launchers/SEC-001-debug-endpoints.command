#!/bin/bash
# Launches Claude Code with the SEC-001 (debug endpoint gating) execution prompt preloaded.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-001-debug-endpoints.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-001 — Gate /debug/* endpoints (8 routes, P0)
  Branch (suggested): feature/sec-001-debug-gate
  Prompt: $PROMPT_FILE
================================================================

First 12 lines of the prompt for sanity:

EOF
head -12 "$PROMPT_FILE"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to launch Claude Code with this prompt (Ctrl+C to abort)..."
exec claude "$(cat "$PROMPT_FILE")"
