#!/bin/bash
# Launches Claude Code with the SEC-RLSe (audit/system-only RLS triage) execution prompt preloaded.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-RLSe-audit-system.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-RLSe — RLS for Audit / System Tables (~30 tables, P0)
  Branch (suggested): audit/stage-1-rls-e-audit-system
  Prompt: $PROMPT_FILE
  Parent sprint: AIQ-649
================================================================

First 12 lines of the prompt for sanity:

EOF
head -12 "$PROMPT_FILE"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to launch Claude Code with this prompt (Ctrl+C to abort)..."
exec claude "$(cat "$PROMPT_FILE")"
