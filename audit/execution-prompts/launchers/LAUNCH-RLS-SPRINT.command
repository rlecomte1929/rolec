#!/bin/bash
# AIQ-649 RLS Sprint dispatcher — opens 5 Terminal windows in parallel for SEC-RLSa-e.
# SEC-RLSf (closer) is intentionally NOT in this dispatcher — run it manually after
# a-e are all at Human Review or beyond.
#
# No file overlap between a-e (each writes a separate migration file in a separate
# domain). Merge them in any order; SEC-RLSf depends on all 5.

LAUNCHERS_DIR="/Users/romainlecomte/Documents/GitHub/rolec/audit/execution-prompts/launchers"

PROMPTS=(
  "SEC-RLSa-cases-domain.command"
  "SEC-RLSb-policy-hr-domain.command"
  "SEC-RLSc-rce-tables.command"
  "SEC-RLSd-catalog-seed.command"
  "SEC-RLSe-audit-system.command"
)

echo "================================================================"
echo "  AIQ-649 RLS Sprint — 5 parallel Claude Code sessions."
echo "  Each window will pause and wait for ENTER before \`claude\`."
echo "  Run SEC-RLSf (closer) manually after a-e reach Human Review."
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
echo "Done. 5 Terminal windows should be open."
echo "Cmd+\` (backtick) cycles between windows."
echo ""
echo "Next step (after a-e are Human Review):"
echo "  open $LAUNCHERS_DIR/SEC-RLSf-allowlist-comments.command"
echo ""
read -p "Press ENTER to close this dispatcher window..."
