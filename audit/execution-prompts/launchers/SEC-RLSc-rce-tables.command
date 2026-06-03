#!/bin/bash
# Launches Claude Code with the SEC-RLSc (rce.* schema RLS) execution prompt preloaded.
# Supersedes the standalone C1-01a launcher from Batch B.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-RLSc-rce-tables.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-RLSc — RLS for rce.* Case Engine Tables (P0)
  Branch (suggested): audit/stage-1-rls-c-rce
  Prompt: $PROMPT_FILE
  Parent sprint: AIQ-649 (supersedes standalone C1-01a)
================================================================

First 12 lines of the prompt for sanity:

EOF
head -12 "$PROMPT_FILE"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to launch Claude Code with this prompt (Ctrl+C to abort)..."
exec claude "$(cat "$PROMPT_FILE")"
