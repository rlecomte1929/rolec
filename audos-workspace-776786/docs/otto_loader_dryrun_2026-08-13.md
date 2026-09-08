# otto-loader dry-run report — 2026-08-13

All five loader-compatible manifests were run with `dry_run=true`. **Nothing was
written.** Every file fetched successfully — 182 of 182, zero failures — so the
GCS side is healthy. The problem is entirely in the mapping layer.

## What each manifest would do right now

| manifest | files | facts new | vendors new | pets new | blocked | unrouted |
|---|--:|--:|--:|--:|--:|--:|
| Master v1 — pet/vehicle/domestic | 133 | 0 (497 already loaded) | **53** | 0 (50 merge) | 0 | 0 |
| Wave 3a | 9 | 0 | **8** | 0 | **19 facts** | 0 |
| Wave 3b | 8 | 0 (18 already loaded) | 0 | 0 | 0 | 0 |
| Wave 3c — FI, LU, SA, QA, TR, TH | 18 | 0 | **20** | 0 | **183 facts** | 6 |
| Wave 3d | 14 | **49** | 0 | 0 | 0 | 0 |
| **Ready to insert today** | | **49 facts** | **81 vendors** | | | |

## Three defects, all in the loader — none in the research

### 1. `fact_value` is not read → 202 facts silently dropped

Wave 3a and Wave 3c files carry the fact text in a field called **`fact_value`**.
`otto-loader` v5 looks for `fact_text`, `body`, `requirement` or `text` — and
when it finds none it counts the record under `skip_no_text` and moves on
without an error. That is 202 researched, sourced, T1-quality facts discarded in
silence.

Sample record keys from `1786608929402_bfi2uafi.json` (33 records):

```
entity, status, corridor, fact_key, fact_type, topic_key, applies_to,
dedupe_key, fact_value, source_url, trust_tier, domain_area, source_name,
country_code, source_quote, target_table, language_code, review_reason,
provenance_json, review_required, confidence_score, extraction_method,
official_authority
```

Destination resolution works (0 `skip_no_dest`) — only the text field is missing.
The fix is one word: add `fact_value` to `factText()`.

### 2. Master manifest v2 is unreadable → 214 rows unreachable

`1786609327030_fhg5r379.json` is the newest and largest manifest (214 rows vs
v1's 156). It puts its rows under the key **`manifest`**. The loader reads
`manifest_rows` or `files` only, so it returns `files_total: 0` and reports
success. A silent no-op, not an error.

The fix is one line: `man.manifest_rows || man.files || man.manifest || []`.

### 3. `readiness_templates` has no route → 6 records unrouted

Wave 3c contains 6 records targeting `readiness_templates`. The loader has no
branch for that table, so they land in `unrouted`. This one is honest — it is
counted and visible — but the records still go nowhere. Worth noting that
AIQ-1809 ("Register IE readiness template") is open in Notion for exactly this
data.

## What this explains

The audit found the recent countries were loaded far thinner than they were
researched — Norway 63 facts of 308, UK 8, Japan 11 of 37, UAE 11, Spain 29 of
65, Germany 0. Defects 1 and 2 are a large part of the mechanism: the overnight
runs wrote in a schema the loader had drifted away from, and the loader reported
success anyway.

## What is still not reachable by any manifest

- **DE, AE, JP, NO** have complete per-country GCS files but appear in **no
  manifest** — they need one written, or a loader that accepts a file list.
- **ES, GB, IT** were never written to GCS at all. Italy was explicitly told not
  to persist. These have to be lifted out of the chat thread before anything can
  load them.

## Recommended order

1. Deploy `otto-loader` v6 with the three fixes (two one-liners + a
   `readiness_templates` branch).
2. Re-run all five manifests as dry runs — expect ~251 facts, 81 vendors, 6
   templates, plus whatever the 214-row v2 manifest adds.
3. Load for real, verify counts per country.
4. Write a small manifest for the DE / AE / JP / NO per-country files and load
   those.
5. Decide what to do about ES, GB and IT.
