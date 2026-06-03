#!/bin/bash
# Launches Claude Code with the SEC-RLSa (cases-domain RLS) execution prompt preloaded.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-RLSa-cases-domain.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-RLSa — RLS for Cases Domain (~26 tables, P0)
  Branch (suggested): audit/stage-1-rls-a-cases
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
