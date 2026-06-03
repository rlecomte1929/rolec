#!/bin/bash
# Launches Claude Code with the SEC-006 (file upload validation + bucket audit) execution prompt preloaded.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-006-file-upload-validation.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-006 — Upload Validation + Private Bucket Audit (P1)
  Branch (suggested): feature/sec-006-upload-validation
  Prompt: $PROMPT_FILE
================================================================

First 12 lines of the prompt for sanity:

EOF
head -12 "$PROMPT_FILE"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to launch Claude Code with this prompt (Ctrl+C to abort)..."
exec claude "$(cat "$PROMPT_FILE")"
