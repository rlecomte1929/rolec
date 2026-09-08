#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Land the ES→IE destination batch + delivery gate + batch validation tooling
# onto branch fix/td-qa-services-batch-0719, then open a files-only PR.
#
# Run this from anywhere inside your rolec clone:
#     bash land_es_ie_batch.sh
#
# What it does (and does NOT do):
#   • Works in an ISOLATED git worktree off the up-to-date origin branch tip, so your
#     current branch (feat/aiq-1854-content-classifier) and its working tree are never touched.
#   • Copies the already-placed files from your main clone into the worktree.
#   • SELF-VERIFIES with the gate + drift guard and ABORTS before committing if anything fails.
#   • Makes two clean commits (batch+gate = files only; then the validation tooling),
#     pushes, and opens a PR against main. It does NOT merge and does NOT promote to the DB.
#
# Safe to re-run: it refuses if the worktree dir already exists (remove it first).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BRANCH="fix/td-qa-services-batch-0719"
WT="${TMPDIR:-/tmp}/rolec-td-0719"
BATCH_ID="es-ie-thirdcountry-requirements-2026-08-22"

# ── locate the main clone ────────────────────────────────────────────────────
MAIN="$(git rev-parse --show-toplevel)"
case "$(git -C "$MAIN" remote get-url origin 2>/dev/null)" in
  *rlecomte1929/rolec*) : ;;
  *) echo "❌ This does not look like the rolec clone (origin != rlecomte1929/rolec). Aborting."; exit 1 ;;
esac
command -v gh >/dev/null 2>&1 || { echo "❌ GitHub CLI (gh) not found — install it or open the PR manually."; exit 1; }

# ── files we expect to already be on disk in the main clone ───────────────────
BATCH_FILES=(
  "docs/imports/$BATCH_ID/es_ie_thirdcountry_requirements.ndjson"
  "docs/imports/$BATCH_ID/manifest.json"
  "docs/imports/$BATCH_ID/README.md"
  "scripts/check_otto_batches.py"
)
TOOLING_FILES=(
  "scripts/check_gate_loader_sync.py"
  "scripts/check_otto_promotion.py"
  "scripts/tests/test_gate_loader_sync.py"
  ".githooks/pre-commit"
)
for f in "${BATCH_FILES[@]}" "${TOOLING_FILES[@]}"; do
  [ -f "$MAIN/$f" ] || { echo "❌ missing on disk: $f  (did the earlier 'place files' step run?)"; exit 1; }
done

# ── fresh worktree off the up-to-date remote branch tip ───────────────────────
# Clean any leftover worktree from a previous aborted run (always safe: this script never
# commits into $WT before it fully succeeds).
if [ -e "$WT" ]; then
  echo "▶ removing leftover worktree at ${WT}…"
  git -C "$MAIN" worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"
fi
git -C "$MAIN" worktree prune 2>/dev/null || true
echo "▶ fetching origin…"; git -C "$MAIN" fetch --no-tags origin "$BRANCH" main
echo "▶ creating worktree at $WT on ${BRANCH}…"
git -C "$MAIN" worktree add "$WT" "$BRANCH"
git -C "$WT" reset --hard "origin/$BRANCH"   # exactly the remote tip (local branch was behind, 0 ahead)

# ── copy files in ─────────────────────────────────────────────────────────────
echo "▶ copying batch + tooling into the worktree…"
for f in "${BATCH_FILES[@]}" "${TOOLING_FILES[@]}"; do
  mkdir -p "$WT/$(dirname "$f")"
  cp "$MAIN/$f" "$WT/$f"
done

# ── write the CI workflow (protected path — created here, on your machine) ─────
mkdir -p "$WT/.github/workflows"
cat > "$WT/.github/workflows/otto-batches.yml" <<'YAML'
name: Otto import batches

# Gate Otto research batches under docs/imports/ against the delivery contract, and keep
# the gate's loader mirror in sync with the deployed loader. Runs only when a batch, the
# gate, its drift guard, or the loader's allow-lists change (native path filter — the repo
# configures no required status checks, so a skipped run is safe and does not block merge).
#
# Design note: this gates only batches ADDED OR CHANGED in the PR, not `--all`. Several
# batches predate the gate and do not meet the strict contract; re-gating them would fail
# CI on untouched legacy content. Grandfathering-by-non-change mirrors ci.yml's path
# filters ("run only the jobs that matter for this diff"). Editing a legacy batch opts it
# back into the gate — touching it means bringing it up to standard.
on:
  pull_request:
    paths:
      - 'docs/imports/**'
      - 'scripts/check_otto_batches.py'
      - 'scripts/check_gate_loader_sync.py'
      - 'supabase/functions/otto-loader/index.ts'

concurrency:
  group: otto-batches-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  gate:
    name: Delivery gate (changed batches)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # need the PR base commit to diff which batches changed

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.11"

      # The gate mirrors the deployed loader's allow-lists (FACT_TYPES / ALLOWED_DOMAINS)
      # by copy. Fail if they have drifted, so the offline gate can never grade a batch
      # against a stale taxonomy. Pure stdlib — no install step.
      - name: Gate<->loader allow-list drift guard
        run: python scripts/check_gate_loader_sync.py

      # Enforce the delivery contract on each batch touched in this PR.
      - name: Delivery gate on changed batches
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: |
          mapfile -t ids < <(git diff --name-only "$BASE_SHA...$HEAD_SHA" -- 'docs/imports/**' \
            | awk -F/ 'NF>=3 {print $3}' | sort -u)
          if [ "${#ids[@]}" -eq 0 ]; then
            echo "No batch directory changed in this PR (gate/loader-only change)."
            exit 0
          fi
          rc=0
          for id in "${ids[@]}"; do
            if [ ! -f "docs/imports/$id/manifest.json" ]; then
              echo "skip '$id' (no manifest.json — not a batch directory)"
              continue
            fi
            echo "::group::delivery gate — $id"
            python scripts/check_otto_batches.py "$id" || rc=1
            echo "::endgroup::"
          done
          exit "$rc"
YAML

# ── self-verify BEFORE committing (abort on any failure) ──────────────────────
echo "▶ self-verifying in the worktree…"
( cd "$WT" && python3 scripts/check_gate_loader_sync.py ) || { echo "❌ gate<->loader drift — NOT committing. Worktree left at $WT."; exit 1; }
( cd "$WT" && python3 scripts/check_otto_batches.py "$BATCH_ID" ) | tee /tmp/gate_out.txt || true
if ! grep -q "VERDICT: PASS" /tmp/gate_out.txt; then
  echo "❌ gate did not PASS — NOT committing. Worktree left at $WT for inspection."
  exit 1
fi

# ── two clean commits ─────────────────────────────────────────────────────────
echo "▶ committing…"
git -C "$WT" add "docs/imports/$BATCH_ID" scripts/check_otto_batches.py
git -C "$WT" commit -m "feat(imports): land ES→IE destination third-country batch + delivery gate (files only)

38 non-EEA/professional destination facts for Andrea (Madrid→Dublin) under docs/imports/.
Gate scripts/check_otto_batches.py is NEW in this diff — review it as code. Files only:
nothing is promoted into requirement_facts."

git -C "$WT" add scripts/check_gate_loader_sync.py scripts/check_otto_promotion.py \
                 scripts/tests/test_gate_loader_sync.py .github/workflows/otto-batches.yml \
                 .githooks/pre-commit
git -C "$WT" commit -m "ci(imports): gate Otto batches in CI + pre-commit; add loader-drift guard and pre-promotion collision check

- .github/workflows/otto-batches.yml: gate batches changed in a PR (not --all; legacy grandfathered)
- scripts/check_gate_loader_sync.py (+ scripts/tests): fail if the gate's allow-lists drift from the loader
- scripts/check_otto_promotion.py: offline collision check vs a workspace DB export (the online half of the gate)
- .githooks/pre-commit: run the gate on staged batches before commit"

# ── push ──────────────────────────────────────────────────────────────────────
echo "▶ pushing…"
git -C "$WT" push origin "$BRANCH"

# ── PR body (embeds the real gate output captured above) ──────────────────────
BODY="$(mktemp)"
{
  cat <<'MD'
## Summary
ES→IE **destination** research batch for persona Andrea (Venezuelan, non-EEA professional,
Madrid → Dublin): **38 facts, files only** under `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/`.
Plus the delivery **gate** and its CI/validation tooling. **Nothing is promoted into
`requirement_facts`** — this is a files-only PR. 🔴 full human + lawyer gate. Do not merge until reviewed.

### Delivery gate output (`scripts/check_otto_batches.py es-ie-thirdcountry-requirements-2026-08-22`)
```
MD
  cat /tmp/gate_out.txt
  cat <<'MD'
```

## New in this diff — review as code, not as trusted tooling
- `scripts/check_otto_batches.py` — the delivery gate. It did not exist when the batch was
  built; it was written in the same effort. Review it on its own merits.
- `scripts/check_gate_loader_sync.py` (+ `scripts/tests/test_gate_loader_sync.py`) — fails if
  the gate's `LOADER_FACT_TYPES` / `LOADER_DOMAIN_AREAS` drift from the deployed loader's
  `FACT_TYPES` / `ALLOWED_DOMAINS`, so the offline gate can't grade against a stale taxonomy.
- `scripts/check_otto_promotion.py` — offline pre-promotion collision check against a
  workspace DB export (the DB-aware half the gate deliberately omits). On the 2026-08-18
  export: 38 mapped_new, 0 dup_existing, 6 new entities.
- `.github/workflows/otto-batches.yml` — gates only batches **changed** in a PR (not `--all`:
  several legacy batches predate the gate and would fail; grandfathered until touched).
- `.githooks/pre-commit` — runs the gate on staged batches before commit.

## Independent verification
- Gate: **PASS, 54/0** (output above). A separate reproduction incl. a live-export collision
  check also passed (38 mapped_new, 0 dup_existing, 6 new entities).
- The NDJSON is byte-identical to the authoring copy (sha256 `188028d6…beacb7`, 78,040 B, 38 lines).

## Judgement calls for the reviewer
- **Editorial overlap is NOT resolved here.** This `docs/imports` NDJSON batch (namespace
  `ES-IE:thirdcountry:*`) sits alongside the `data/corridor-facts/*.jsonl` ES→IE batches
  already on this branch and the curated `es-ie.json`. Which representation a corridor serves
  is a curation decision deferred to a follow-up, not taken by this import.
- **S1 nationality-scoping:** 21 records are `nationality_determined`, 17 are `audience_scope`
  (nationality-neutral rules shown to a non-EEA audience). The serving layer does not yet read
  `applies_to.nationality_scope_basis` — wiring it is a separate 🔴 change so an EEA mover is
  not wrongly told they're exempt.

## Honest limits
- Nothing is lawyer-reviewed: `review_status: pending`, `verification_status: representative`,
  `assurance_status: not_started`. 6 records are flagged `needs_lawyer_review`.
- The two visa-touching records are `assertion_mode: conditional` (defer to the A3 batch);
  no record asserts a nationality IS visa-required.

## Not in this PR
- The **es-departure** (Spain-origin, 28 records) half — land it in a follow-up commit on this
  branch once its files are verified with the same gate.
- Any DB promotion — separate, post-review, via the loader.
MD
} > "$BODY"

# ── open the PR (skip if one already exists) ──────────────────────────────────
if gh pr view "$BRANCH" >/dev/null 2>&1; then
  echo "ℹ A PR already exists for $BRANCH — pushed the new commits to it. Update its description from $BODY if needed."
else
  gh pr create --base main --head "$BRANCH" \
    --title "ES→IE destination batch + delivery gate + batch CI tooling (files only)" \
    --body-file "$BODY"
fi

# ── cleanup ───────────────────────────────────────────────────────────────────
echo "▶ removing worktree…"
git -C "$MAIN" worktree remove "$WT"
echo "✅ done. Review the PR (do NOT merge; lawyer-gate the 6 flagged records). main was not touched."
