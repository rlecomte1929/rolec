# otto-loader v6 — deployed, re-dry-run 2026-08-13

`otto-loader` is now at **version 6** (`verify_jwt=false`, unchanged). Three
changes, all in the mapping layer, none touching the insert logic:

1. `factText()` also reads **`fact_value`** — the wave 3a/3c schema.
2. Manifest rows also read from the **`manifest`** key — the master manifest v2 shape.
3. **`readiness_templates`** routed. It is *opt-in only* (`?tables=readiness_templates`)
   and deliberately excluded from `all`, because unlike every other target it is a
   live product table, not a pending-candidate staging table.

Nothing has been written. All six manifests were re-run with `dry_run=true`.

## Before → after

| manifest | files | facts new (v5 → v6) | vendors new | entities new | readiness |
|---|--:|---|--:|--:|--:|
| Master v1 — pet/vehicle/domestic | 133 | 0 → 0 | 53 | 0 | — |
| **Master v2 — task #106792** | 214 | **unreadable → 304** | **179** | 2 | — |
| Wave 3a | 9 | 0 → 0 | 8 | 0 | — |
| Wave 3b | 8 | 0 → 0 | 0 | 0 | — |
| Wave 3c — FI, LU, SA, QA, TR, TH | 18 | **0 → 183** | 20 | 0 | 6 |
| Wave 3d | 14 | 49 → 49 | 0 | 0 | — |

Master v2 is a superset of most of the wave manifests, so the totals overlap. The
loader dedupes against the live table on every run, so running all six in sequence
inserts each row exactly once. **Ceiling for this pass: 304 requirement facts,
179 vendor candidates, 2 requirement entities**, plus 6 readiness templates if you
opt in.

## What is still blocked — and why it is right to leave it blocked

**133 records have no fact statement at all.** Wave 3a's fact files (and their
copies inside master v2) carry `source_quote`, `source_url`, `fact_key`,
`applies_to`, `confidence_score` — and no `fact_text`, `fact_value`, `body`,
`requirement` or `text`. Otto wrote the evidence but never wrote the fact.

Sample record keys from `1786608743534_w7wwxve6.json`:

```
topic, entity, status, corridor, fact_key, fact_type, topic_key, applies_to,
dedupe_key, source_url, trust_tier, domain_area, source_name, source_quote,
target_table, review_reason, provenance_json, review_required,
confidence_score, extraction_method
```

The loader could be made to fall back to `source_quote`, and it should not be.
A verbatim quote from a government page is evidence *for* a fact, not the fact —
promoting one into `fact_text` would put words in the product's mouth that no one
wrote. These 19 (in wave 3a) / 133 (across master v2) need Otto to re-emit with the
statement filled in.

**One file in master v2 is not JSON** — it returns binary
(`SyntaxError: Unexpected token 'Z'`). 213 of 214 fetched cleanly.

## Still not reachable by any manifest — DE, AE, JP, NO

These four have complete per-country GCS files (see the index) but appear in no
manifest, and their schema differs again:

- the entities file uses **`country`**, not `destination_country`
- the facts file links by **`entity_id`**, with no country on the fact at all
- neither carries `target_table`, so nothing can route them

Germany is the one that matters most — 20 entities + 60 facts sitting in GCS
against **zero** DE immigration rows in ReloPass. Loading them needs either a
small manifest plus a v7 tolerance pass, or a one-off transform.

## Where that leaves the numbers

| | facts | vendors |
|---|--:|--:|
| Loadable right now | 304 | 179 |
| Blocked on Otto re-emitting the fact statement | 133 | — |
| Blocked on DE/AE/JP/NO schema (v7) | ~60+ | — |
| Never written to GCS (ES, GB, IT) | unknown | — |
