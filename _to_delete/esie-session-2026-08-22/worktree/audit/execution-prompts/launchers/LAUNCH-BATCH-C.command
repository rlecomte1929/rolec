#!/bin/bash
# Batch C dispatcher — opens 3 Terminal windows in parallel:
#   1. SEC-Backend-Middleware-Pass (SEC-001 → SEC-005, sequential in one window)
#   2. SEC-004 (rate limit coverage, standalone)
#   3. SEC-006 (upload validation + bucket audit, standalone)
#
# These three tracks have no file overlap. Run them in parallel and merge in any order.

LAUNCHERS_DIR="/Users/romainlecomte/Documents/GitHub/rolec/audit/execution-prompts/launchers"

PROMPTS=(
  "SEC-Backend-Middleware-Pass.command"
  "SEC-004-rate-limiting.command"
  "SEC-006-file-upload-validation.command"
)

echo "================================================================"
echo "  Batch C dispatch — 3 parallel Claude Code sessions."
echo "  Each window will pause and wait for ENTER before \`claude\`."
echo "================================================================"
echo ""

for p in "${PROMPTS[@]}"; do
  if [[ ! -f "$LAUNCHERS_DIR/$p" ]]; then
    echo "  SKIP (missing): $p"
    continue
  fi
  echo "  Opening: $p"
  open "$LAUNCHERS_DIR/$p"
  sleep 0.4
done

echo ""
echo "Done. 3 Terminal windows should be open."
echo "Cmd+\` (backtick) cycles between windows."
echo ""
read -p "Press ENTER to close this dispatcher window..."
