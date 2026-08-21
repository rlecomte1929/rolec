# Gap analysis — `fix/td-qa-services-batch-0719` vs `main` (2026-08-22)

**Method.** Every file where the branch differs from *current* `main` was classified against the
merge-base (`f2baee04`, 2026-08-19): **BRANCH-AHEAD** (content main lacks), **STALE** (main moved
past the branch), or **DIVERGENT** (both moved — then the branch-only lines were read one by one).
This matters because a naive `git diff main...branch` shows ~5,400 "unmerged" lines; almost all of
it landed on main through other PRs (#1884, #1891, #1910, #1950–#1959) and then kept evolving.

## Verdict

**The branch must never be merged wholesale**, for two reasons beyond staleness:
- ~280 files are STALE — merging would regress main (requirements_builder, the eval harnesses,
  the otto importer, corridor pathways, frontend pages all moved after the branch stopped).
- Its two unique migrations sit on version stamps main has since assigned to *different* files
  (`20261107000000_candidate_beam.sql`, `20261109000000_source_records_published_date.sql`) — a
  ledger keyed by version can track only one file per stamp.

**Its entire unique value is three things**, all Andrea/Denis-relevant, harvested below.

## What the branch uniquely held → what was done (2026-08-22)

| # | Gap | Andrea/Denis relevance | Integration | Status |
|---|---|---|---|---|
| 1 | **53 Otto facts refused by the loader** — `es-ie-general` (33) + `no-fr-general` (20), `applies_to.nationality` null on all | The core corridor data for both demo cases | Curated per the §3 contract: re-scoped from each fact's own text, topics re-keyed to requirement granularity, universal facts twinned EEA/non-EEA, steps → pathway candidates, Norway exit duties → `facts.yaml` candidates (D2), self-employment sub-corpus deferred. **46 records, 0 parser rejections, 22 requirement drafts, 0 Unmapped.** `docs/imports/es-ie-general-curated-2026-08-22/` + `no-fr-general-curated-2026-08-22/` + `scripts/curate_general_batches_2026_08_22.py` | ✅ curated + gated; staging load = one command (READMEs) |
| 2 | **Verified-write guardrail** (`79aaee1e`): generators structurally cannot write `expert_verified`; only a named human actor can; a human signature survives re-seeds. Adds `verified_by`/`verified_at` | Andrea's 4 counsel-flagged rows + the whole trust rail: closes "requirement approval has no counsel gate" | Cherry-picked onto main, migration re-stamped **`20261116000000`** | ✅ [PR #1963](https://github.com/rlecomte1929/rolec/pull/1963), 174 tests green |
| 3 | **Corridor-import idempotency** (`54e903b1`): UNIQUE index on `(country_code, purpose, title)` + `ON CONFLICT DO NOTHING` insert with race convergence (= Notion **AIQ-1982**, P0) | Protects exactly the loads in row 1 from double-import duplication | Cherry-picked, re-stamped **`20261117000000`**; conflict resolution ported main's #1924 citation-preserve + non_obvious/timing sync INTO the refactored helper (not resurrected away) | ✅ PR #1963 |
| — | `docs/otto/andrea-denis-brief-2026-08-21.md` | The contract itself | Already open as PR #1960 | awaiting merge |
| — | `20261107…_ie_es_requirement_items.sql` (branch copy) | — | Superseded: main has its own at `20261108000000` | retired |

**Divergent files, all subsumed by main** (branch-only residue read line-by-line): the eval
slicing commit `3c8b7909` merged via #1950s and main's HLP baseline is a **superset** (it adds the
`must_not_serve` precision blocks); the serving/LLM guard — main *generalized* the branch's
`from . import` special-case (its comment documents why); ci.yml migration-guard hardening —
rewritten on main via #1906; B3 doc + corridors README — main carries newer follow-ups.

## Deploy sequencing for PR #1963 (operator step required)

The migrations' own headers require the DDL applied to prod **before** the PR merges (the ON
CONFLICT clause names the index; DTO readers degrade to NULL but the insert path does not).
Status: validated against prod in a rollback transaction on 2026-08-22 — 2 columns + index
create cleanly, **0 duplicate natural-key groups exist** (the dedupe loop is a no-op), row count
156 untouched. The committing apply was **blocked by the session's permission classifier**, so it
is Romain's step (or an interactive session):

1. Run the two migration files' SQL against prod (order: 20261116 then 20261117 — content is in
   the PR; both idempotent).
2. Merge PR #1963.
3. From a checkout containing the files (post-merge `origin/main` worktree, session-mode port 5432):
   ```bash
   supabase migration repair --status applied 20261116000000 --db-url "$DATABASE_URL"
   supabase migration repair --status applied 20261117000000 --db-url "$DATABASE_URL"
   ```

## Remaining Andrea/Denis gaps this branch does NOT close

From the handoff and the master plan (`docs/otto/extraction-and-campaign-master-plan-2026-08-21.md`):
intake `holds_eu_ltr_in_spain` (flips Andrea's LTR + D-visa advisories to asserted) · `rce.*`
audit-trail create-hook (0 rows for ES_IE) · Dublin/Paris vendor directories (AIQ-2064/2069) ·
ES→IE / NO→FR RAG corpora (AIQ-2065/2070) · Spain-departure + Norway-departure origin sets
(AIQ-2062/2068 — the 3 origin candidates in the NO→FR README feed D2) · the FR_NO third-country
overserving product decision (pinned in `KNOWN_VIOLATIONS`).

## Branch disposition

Keep `fix/td-qa-services-batch-0719` alive — it is the Audos sync's file channel and Otto's
`PUSH_INSTRUCTIONS.md` targets it. Treat it as an **inbox, never a merge source**: harvest new
`audos-workspace-776786/data/` deliveries from it; everything else on it is stale by design.
