# `no-fr-transition-requirements-2026-08-22`

Otto research batch for **Denis's corridor** — Norway → France, French national returning
home (`applies_to.nationality = EEA`, `status = professional`). 15 facts across 8
transition topics: applicable social-security law, folketrygden coverage closure, foreign-employer
French registration, the FR–NO tax treaty, French tax residency, CPAM health affiliation,
dual-nationality resolution, and Norwegian source taxation after emigration.

## Status: STAGED, NOT PROMOTED — and not promotable as it stands

| | |
|---|---|
| `otto_staging.immigration_fact_candidates` | 15 rows, `batch_id='no-fr-transition-requirements-2026-08-22'`, `status='new'` |
| `accuracy_tier` | all 15 `auto_accepted` |
| `requirement_items` | nothing promoted from this batch |
| Verification | **3 of 15** quotes verifiably on the page they cite |

Read **[VERIFICATION-2026-08-30.md](VERIFICATION-2026-08-30.md)** before touching it. Summary:
6 facts cite a bare domain; 12 quotes could not be confirmed on their source; one was proven
to be a paraphrase rather than a quotation; and most of the batch overlaps rows already in
`requirement_items`, one of which it contradicts.

## Files

- `facts.ndjson` — the 15 staged facts, exported **back out of prod** on 2026-08-30. This is
  the staged content as it exists, not a corrected version.
- `VERIFICATION-2026-08-30.md` — the two gate runs, the paraphrase proof, the overlap and
  contradiction against `requirement_items`, and the re-sourcing worklist.

## Why the export direction is backwards

Normally the artifact lands in the repo first and is loaded from here. This batch was staged
directly into prod with no repo record at all — no directory, and no file in the tree naming
the batch id — so the only copy lived in a staging table. `facts.ndjson` was reconstructed
from that table to give the batch something diffable, per CLAUDE.md's intake rule ("a
'verified' fact nobody can diff is not verified").

Treat the prod staging rows as the source of truth until a corrected batch is delivered; then
that corrected batch should land here **first**.

## Re-running the checks

```bash
# citation specificity + evidence grounding over the staged rows
python scripts/verify_ledger.py docs/imports/no-fr-transition-requirements-2026-08-22/facts.ndjson
```

Note `verify_ledger.py` covers V0–V2 (schema, vocabulary, source authority and liveness). The
quote-vs-page check reported in the verification file is V3 and is run separately through
`backend/app/services/fact_evidence.check_evidence` against pages fetched with
`backend/scripts/backfill_fact_evidence.fetch_and_parse`.

Three sources cannot be machine-checked at all: `lovdata.no` disallows crawlers in robots.txt
(2 facts) and `legifrance.gouv.fr` returns 403 (1 fact).
