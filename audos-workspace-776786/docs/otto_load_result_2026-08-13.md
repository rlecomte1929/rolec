# Otto → ReloPass load — result, 2026-08-13

Everything below is loaded as **`status='pending'` candidates**. Nothing is live in
the product until the review-and-promote step runs.

## Totals

| table | before | after | change |
|---|--:|--:|--:|
| `requirement_facts` | 1,689 | **2,676** | **+987** |
| `requirement_entities` | 598 | **917** | +319 |
| `vendor_candidates` | 278 | **534** | +256 |
| destination countries covered | 32 | **37** | +5 |
| `pet_import_rules` | 66 rows | 66 rows | 112 origin-group variants merged |

Zero insert errors across all ten runs.

## The countries that were stuck

| country | facts before | facts after | note |
|---|--:|--:|---|
| **Norway** | 63 | **377** | the 308-fact file finally landed — biggest single recovery |
| **Germany** | 0 immigration | **205 total** | primary corridor, was completely empty |
| **UAE** | 11 | 54 | |
| **Japan** | 11 | 50 | |
| **Spain** | 29 | 70 | |
| **United Kingdom** | 8 | 68 | |
| **Italy** | 9 | 30 | still under the "do not import" instruction — this came via the shared manifest, not the IT run |
| new: TR / FI / LU / TH / SA / QA | 0 | 39 / 33 / 32 / 30 / 30 / 19 | wave 3c countries, entirely new destinations |

## How it was done

**otto-loader v6 → v7.1** (three deploys, `verify_jwt` unchanged). Five tolerances
added, all in the mapping layer — no change to the insert logic, the dedupe keys,
or the pending-candidate status:

1. `fact_value` accepted as fact text (wave 3a/3c schema).
2. `manifest` accepted as a rows key (master manifest v2 — 214 rows that had been
   silently returning `files_total: 0`).
3. `readiness_templates` routed, **opt-in only** (`?tables=readiness_templates`),
   because it is a live product table rather than a staging one. Not used in this pass.
4. Entity destination read from `country` / `destination_iso2` as well as
   `destination_country`.
5. Facts that carry only an `entity_id` resolve their destination from the entity
   in the same batch, with deferred retry after all files are read — because files
   are fetched eight at a time and a facts file can arrive before its entities file.

Ten loads ran: master v2, master v1, waves 3a–3d, then DE / NO / JP / AE from bare
file lists via the new `urls` parameter.

## What is still not loaded

**133 records have no fact statement.** Wave 3a's files carry `source_quote`,
`source_url`, `fact_key` and `confidence_score` — but no fact text in any field.
The loader could fall back to the quote and deliberately does not: a verbatim
sentence from a government page is evidence *for* a fact, not the fact. Promoting
one into `fact_text` would put words in the product's mouth that nobody wrote.

**One file in master v2 is not JSON** — returns binary. 213 of 214 fetched cleanly.

**171 entities still have zero facts**, almost all `vehicle_import`. Same shape as
before: the entities file loaded, the facts file did not. These render as blank
sections in the product and should either be re-loaded or deleted.

## Requested from Otto (sent this session)

Spain, the UK and Italy were never written to GCS — their research exists only as
inline chat text. I posted a re-emit request in each of those three meetings asking
Otto to serialise what it already produced into `requirement_entities_<CC>.json` +
`requirement_facts_<CC>.json`, with **both** `fact_text` and `evidence_quote` on
every record, and to reply with complete plain-text URLs. Italy's request restates
the standing "do not import" instruction — this is about persistence only.

All three are running. When the URLs come back, loading them is one `urls=` call each.

## Next

1. Collect the three re-emitted file sets and load them.
2. Decide on the 171 orphan `vehicle_import` entities — re-load their facts or delete.
3. Ask Otto to re-emit the 133 statement-less facts with `fact_text` filled in.
4. Load the nine provider city files (Dubai, Frankfurt, Munich, Milan, Oslo,
   Amsterdam, Dublin, London) — still the largest untouched value in the workspace.
5. Then the seven immigration routine meetings can be closed.
