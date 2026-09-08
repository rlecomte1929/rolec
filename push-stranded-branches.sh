#!/usr/bin/env bash
# Push the four branches stranded by the 2026-08-04 GitHub outage.
#
# Four agents completed work today and every push failed with
#   "Failed to connect to github.com port 443".
# The commits are safe locally but invisible to CI, review and Render.
# Run this once connectivity is back; it is idempotent and safe to re-run.
#
#   bash push-stranded-branches.sh
#
# Then open PRs (gh pr create 401s on GraphQL in this repo — use the REST form):
#   gh api -X POST repos/rlecomte1929/rolec/pulls \
#     -f title="..." -f head="<branch>" -f base=main -f body="..."

set -uo pipefail
cd "$(dirname "$0")"

BRANCHES=(
  "docs/aiq-1764-pipeline-owner"                # ef2e40fb — extraction-pipeline owner analysis (docs)
  "feat/aiq-1765-register-extraction-agents"    # 3e8d7880 — DIPLOMA registered, TAX_CERT routing
  "feat/aiq-1771-corridor-generic"              # 5df4bd65 — drop the blue_card / DE default
  "feat/aiq-1758-register-prefilled-doc"        # e1f29c24 — register reviewed prefilled data-sheet
)

if ! git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
  echo "github.com still unreachable — try again later."
  exit 1
fi

failed=0
for b in "${BRANCHES[@]}"; do
  if ! git rev-parse --verify "$b" >/dev/null 2>&1; then
    printf '%-45s SKIP (branch not found locally)\n' "$b"
    continue
  fi
  if git push -u origin "$b" >/dev/null 2>&1; then
    printf '%-45s pushed %s\n' "$b" "$(git rev-parse --short "$b")"
  else
    printf '%-45s FAILED\n' "$b"
    failed=1
  fi
done

exit "$failed"
