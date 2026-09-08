#!/usr/bin/env bash
# Open the files-only PR for the ES→IE batch branch.
#
# The landing script skipped PR creation because `gh pr view` matched an older CLOSED PR
# on this branch. This detects an OPEN PR correctly and creates one only if there isn't
# one. Safe to re-run. Run from anywhere inside your rolec clone:
#     bash open_pr.sh
set -euo pipefail
BRANCH="fix/td-qa-services-batch-0719"
BATCH_ID="es-ie-thirdcountry-requirements-2026-08-22"
MAIN="$(git rev-parse --show-toplevel)"
cd "$MAIN"
command -v gh >/dev/null 2>&1 || { echo "❌ gh (GitHub CLI) not found."; exit 1; }

if gh pr list --head "$BRANCH" --state open --json number --jq '.[].number' 2>/dev/null | grep -q .; then
  echo "ℹ An OPEN PR already exists for ${BRANCH}:"
  gh pr list --head "$BRANCH" --state open
  exit 0
fi

# Capture the gate output for the PR body (the batch files are in your working tree).
python3 scripts/check_otto_batches.py "$BATCH_ID" > /tmp/gate_out.txt 2>&1 || true

BODY="$(mktemp)"
{
cat <<'MD'
## Summary
ES→IE **destination** research batch for persona Andrea (Venezuelan, non-EEA professional, Madrid → Dublin):
**38 facts, files only** under `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/`, plus the delivery
**gate** and its CI/validation tooling. **Nothing is promoted into `requirement_facts`.** Full human + lawyer
gate — do not merge until reviewed.

### Delivery gate output (`scripts/check_otto_batches.py es-ie-thirdcountry-requirements-2026-08-22`)
```
MD
cat /tmp/gate_out.txt
cat <<'MD'
```

## Lawyer-gate these 6 records (flagged `applies_to.needs_lawyer_review: true`)
- `employment_permit_is_not_residence_permission` — an employment permit is not a residence permission
- `csep_nine_month_employer_lock` — no change of employer within the first 9 months
- `leaving_state_before_registration_needs_new_entry_visa` — visa-required national leaving before registration needs a new entry visa (also conditional, below)
- `cannot_hold_residence_permits_in_two_eu_states` — an Irish residence permit can't be held alongside another EU state's
- `resident_and_domiciled_means_worldwide_income` — resident + domiciled means worldwide income is chargeable in Ireland
- `non_resident_but_ordinarily_resident_and_domiciled` — leaving Ireland does not immediately end the Irish charge

## A3 dependency — 2 conditional records (never assert a nationality IS visa-required)
- `entry_visa_follows_permit_if_visa_required` — asserts the sequence only; defers to A3 (`ie-isd-visa-required-2026-08-22`)
- `leaving_state_before_registration_needs_new_entry_visa` — asserts the consequence only; defers to A3

## New in this diff — review as code, not as trusted tooling
- `scripts/check_otto_batches.py` — the delivery gate (did not exist when the batch was built).
- `scripts/check_gate_loader_sync.py` (+ `scripts/tests/test_gate_loader_sync.py`) — fails if the gate's allow-lists drift from the loader. NOTE: currently **dormant** — `supabase/functions/otto-loader/index.ts` is untracked, so the guard SKIPs; it re-arms once the loader is committed.
- `scripts/check_otto_promotion.py` — offline pre-promotion collision check vs a workspace DB export.
- `.github/workflows/otto-batches.yml` — gates only batches changed in a PR (not `--all`; legacy grandfathered).
- `.githooks/pre-commit` — runs the gate on staged batches before commit.

## Verification
- Gate PASS 54/0. Independent reproduction incl. a live-export collision check: 38 mapped_new, 0 dup_existing, 6 new entities.
- NDJSON byte-identical to the authoring copy (sha256 188028d6…beacb7, 78,040 B, 38 lines).

## Deferred (not resolved here)
- Editorial overlap with `data/corridor-facts/*.jsonl` + `es-ie.json` — a curation decision (Phase 6).
- Serving does not yet read `applies_to.nationality_scope_basis` (21 nationality_determined / 17 audience_scope) — Phase 5, a separate change.

## Honest limits
- Nothing lawyer-reviewed: `review_status: pending`, `verification_status: representative`, `assurance_status: not_started`.

## Not in this PR
- es-departure (Spain-origin, 28 records) — follow-up commit once its files are verified.
- Any DB promotion — separate, post-review, via the loader.
MD
} > "$BODY"

gh pr create --base main --head "$BRANCH" \
  --title "ES→IE destination batch + delivery gate + batch CI tooling (files only)" \
  --body-file "$BODY"
echo "✅ PR opened against main. Do NOT merge — lawyer-gate the 6 records above first."
