#!/bin/bash
# Launches Claude Code with the SEC-RLSf (closer — allowlist reason comments) prompt preloaded.
# RUN LAST — only after SEC-RLSa, b, c, d, e are all at Human Review or beyond.
set -e
REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT_FILE="$REPO/audit/execution-prompts/SEC-RLSf-allowlist-comments.md"

cd "$REPO" || { echo "Repo not found at $REPO"; exit 1; }

clear
cat <<EOF
================================================================
  SEC-RLSf — Final Allowlist Reason-Comment Pass (P0, CLOSER)
  Branch (suggested): audit/stage-1-rls-f-closeout
  Prompt: $PROMPT_FILE
  Parent sprint: AIQ-649

  ⚠️  Only run this AFTER SEC-RLSa-e are all at Human Review.
================================================================

First 12 lines of the prompt for sanity:

EOF
head -12 "$PROMPT_FILE"
echo ""
echo "----------------------------------------------------------------"
read -p "Press ENTER to launch Claude Code with this prompt (Ctrl+C to abort)..."
exec claude "$(cat "$PROMPT_FILE")"
