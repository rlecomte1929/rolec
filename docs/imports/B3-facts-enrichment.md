# B3 — corridor compliance flags + destination enrichment

**Status: artifacts landed in the repo. Nothing loaded into any database *yet*.**
The batch's real target is `otto_staging`, via `backend/imports/otto/` — not the `kg_*` tables
the originating task named, which do not exist. See
[What was not done, and why](#what-was-not-done-and-why).

| | |
|---|---|
| Batch id | `B3-facts-enrichment` |
| Researched by | Otto (Audos workspace `d0c29613-9cb5-4652-9c6a-494eeed352e5`) |
| Research date | 2026-08-18 |
| Landed here | 2026-08-19 |
| Contents | 20 non-obvious compliance flags across 6 corridor directions; 13 city-enrichment records across 2 cities |
| Served to any user? | **No.** Candidate material only. |

---

## 1. Goal

ReloPass's durable moat is a proprietary corridor knowledge graph — *country-pair ×
employee-type × current requirements* — that is continuously verified and kept current. The
valuable part is not the requirement list; it is the **divergence between what the official
guidance says and what actually happens**. That divergence is what an HR generalist cannot
get from a government website, and it is what a relocating employee is blindsided by.

B3 is one research batch against that goal: six new corridor directions in the Nordic/UK/DE
cluster, plus destination enrichment for two cities.

Before this commit the batch existed only as NDJSON files on Google Cloud Storage. A GCS
object with no repository record is not an asset — nobody can find it, nobody can review it,
and it disappears the moment the bucket is cleaned. This document and the files under
`data/B3/` make the batch reviewable.

## 2. What is here

```
docs/imports/
├── B3-facts-enrichment.md          ← this file
└── data/B3/
    ├── manifest.json               ← Otto's batch manifest, byte-identical to GCS
    ├── corridor_facts.ndjson       ← 20 records
    ├── city_stavanger.ndjson       ←  6 records
    ├── city_copenhagen.ndjson      ←  7 records
    └── validation_report.json      ← generated, see §7
```

All four source files are byte-identical copies of the GCS objects named in the manifest.
Their sha256 digests are recorded in `validation_report.json` and re-checked by the gate
script, so a later edit to a "verified" fact cannot pass silently.

### Corridor facts — 20 records, 6 directions

| direction | records |
|---|---|
| NO→GB | 4 |
| GB→NO | 4 |
| DK→NO | 3 |
| NO→DK | 3 |
| DK→DE | 3 |
| DE→DK | 3 |

Each record is a *flag*: a place where official guidance and operational reality diverge.
Schema: `corridor, employee_type, category, official_guidance, actual_reality,
action_required, source_url, source_name, retrieved_at, source_missing, flagged`.

The `official_guidance` / `actual_reality` pair **is the payload**. Any target schema that
flattens the two into a single text field destroys the thing the batch exists to capture —
see §5.

### City enrichment — 13 records, 2 cities

Stavanger (NO, 6 records) and Copenhagen (DK, 7 records), covering neighborhoods,
transport, schools, banking, healthcare, practicalities, and (Copenhagen only) cost of
living.

Actual schema, as delivered: `city, country, topic, title, body, source_url, source_name,
retrieved_at`. Eight keys. This matters — see §5.

## 3. Provenance and the no-fabrication rule

The batch's own policy, from the manifest:

> Every fact carries a real fetched `source_url` + `source_name` + `retrieved_at`. No
> invented sources, phones, numbers, or facts. Unverifiable items were omitted rather than
> guessed.

Independently checked on 2026-08-19, not taken on trust:

- 20/20 corridor facts carry all 11 schema fields. Zero `source_missing`, zero `flagged`.
- The 20 facts cite **16 distinct source URLs**. All 16 were fetched and returned **HTTP 200**.
- Sources are overwhelmingly primary and official: GOV.UK, Skatteetaten, UDI, SKAT,
  borger.dk (Life in Denmark), BZSt, service.berlin.de, rundfunkbeitrag.de.

### Honesty notes — what was deliberately omitted

Carried forward verbatim from the manifest, because "what we chose not to claim" is the part
that decays fastest into a false certainty if it is lost:

1. **EU/EEA A1 / posted-worker certificate flags were NOT included.** The authoritative Your
   Europe / europa.eu registration pages are JS-rendered and returned no static text to
   verify cleanly. Continental-shelf social-security coverage is covered instead via the
   fetched NAV (NO→GB) and HMRC (GB→NO) certificate-of-coverage pages.
2. **No DK↔DE Øresund commuter flag.** The Øresund cross-border region is DK↔SE
   (Copenhagen–Malmö), not DK↔DE, so no such flag applies to these directions.
3. **Germany Rundfunkbeitrag amount (EUR 18.36/month).** The official rundfunkbeitrag.de
   amount page is JS-rendered; the figure was corroborated against an institutional
   (Uni Kiel) page and the fetched welcome page — not read off the official amount page.
4. **Copenhagen neighborhoods.** expatarrivals.com returned HTTP 403, so the record is
   anchored on verified international-school cluster locations (CIS Nordhavn; Rygaards/ISH
   Hellerup) rather than unsourced area claims.
5. **Stavanger schools.** Lycée français de Stavanger closed permanently in summer 2019 and
   is not listed as active; ISS + BISS retained.

## 4. What was not done, and why

The originating task specified a target and a write path:

> Import into `kg_corridor_requirements` (+ citations in `kg_requirement_sources`) … reuse
> `tools/wave2-import-pipeline.mjs` and the curated-import server function — do not invent a
> new write path.

**None of that exists in this repository.** Verified 2026-08-19 across the working tree and
every local and remote ref:

| named by the task | actually present? |
|---|---|
| `tools/wave2-import-pipeline.mjs` | no — there is no `tools/` at repo root |
| `tools/corridor-facts/`, `knowledge-pack-import.mjs` | no |
| `kg_corridors`, `kg_corridor_requirements`, `kg_employee_types` | **zero occurrences anywhere in the repo** |
| `geo_city_content` | **zero occurrences anywhere in the repo** |
| curated-import / corridor-blocks-import server functions | no |

The task also asserted that `kg_corridor_requirements` is "what the rule engine reads". The
rule engine — `audos-workspace-776786/apps/case-command/rule-engine.ts` — reads **no database
at all**. It is 1018 lines with zero `fetch`, `supabase`, or `db.` references, and its own
header says so: *"ALL requirements are hardcoded authored constants."*

WorkspaceDB is real, but in this repo it is a **browser-side SDK** (`window.__workspaceDb`,
`useWorkspaceDB`; see `AUDOS.md`). It is not reachable from a CLI checkout, and the `kg_*`
toolchain lives in the Audos workspace where Otto runs.

Writing an importer against an imagined schema would mean inventing the row shape, the column
names and the write contract — "the exact improvisation the runbook forbids, and worse than
nothing for work whose entire purpose is auditability"
(`docs/runbooks/corridor-facts/README.md`, same day).

### But the repo does have a home for this — it is just not the one the task named

**Correction, 2026-08-19.** The finding above is about the *named* targets, and it stands: the
`kg_*` tables and `tools/wave2-import-pipeline.mjs` are fictional. The conclusion originally
drawn from it — "the write must run in Audos" — was wrong. This repo has a complete
authoring→staging→serving pipeline that is the correct home for exactly this data. The first
pass searched for the task's table names rather than for the capability, and missed it.

```
Otto research (JSONL in audos-workspace-776786/data/)
  → backend/imports/otto/parsers.py     FactRow, source-domain tiering
  → executor.stage()                    otto_staging.immigration_entities
                                        otto_staging.immigration_fact_candidates
  → executor.reconcile()                load_log, processing_queue
  → executor.promote()   [opt-in]       public.requirement_items   ← human gate
```

`backend/imports/otto/__init__.py` describes itself as *"Read Otto research deliverables out of
the synced Audos workspace into `otto_staging`"* — this batch's exact use case.
`scripts/import_otto_facts.py` is the CLI and dry-run is its default. City content has a
parallel path in `backend/imports/resources/` (`scripts/import_resources.py --bundle`,
`draft_only` mode; `bundle_oslo.json` is the template).

Staging there satisfies every layer-separation constraint in §6: rows land at `needs_review`,
`promote()` is opt-in and reaches customers only through the existing `/admin/countries`
approval gate, and research text can never reach `auto_accepted` without a human.

**One gap must close first.** `classify_source()` rejects UNOFFICIAL sources outright, and
scored against this batch's real URLs it rejects **9 of the 20 facts — every Danish- and
German-destination direction** (NO→DK, DK→DE, DE→DK each score zero). The five rejected hosts
are all statutory bodies: `skat.dk`, `bzst.de`, `service.berlin.de`, `rundfunkbeitrag.de`,
`lifeindenmark.borger.dk`. That is the identical failure the parser's own comments record for
Ireland, where the suffix rule *"read them as a relocation blog and REJECTED them outright"*.
It is a standing bug affecting every future DK/DE batch, not a B3 inconvenience, and it is
fixed separately from this batch.

### The one reachable loader will not ingest this batch as-is

For completeness, because it is the obvious next thing to reach for: the ReloPass Supabase
`otto-loader` edge function (project `nsvefcvpvwwwhuqyuqmp`, v6, ACTIVE) is the proven
GCS→database path documented in
`audos-workspace-776786/docs/otto-to-relopass-loading-playbook.md`. Reading its deployed
source against these artifacts:

- It routes on a per-record **`target_table`** key. The B3 manifest has `artifact` and
  `kind`, no `target_table`. All 33 records would fall through to `unrouted`.
- It reads fact text from `fact_text | body | requirement | text | fact_value`. The corridor
  facts have `official_guidance` / `actual_reality` / `action_required` and none of those
  keys, so even if routed all 20 would count as `skip_no_text`.
- It has **no `geo_city_content` route**, and no concept of a non-obvious flag.

**Predicted result of pointing it at this manifest today: 0 rows loaded.** Nothing was run;
this is derived by reading the deployed function source, and should be confirmed with a
`dry_run=true` call before anyone relies on it.

The repo has already been bitten by the general form of this. The IE→ES batch (landing
separately, on `fix/td-qa-services-batch-0719`) named `requirement_facts` keyed on `fact_uid`
— a table with no `fact_uid` column and two NOT NULL uuid FKs the batch could not supply — and
its `docs/corridors/README.md` records the rule that came out of it: *"The manifest may name a
table that cannot hold the data. Verify the live schema before writing SQL."* B3 is the same
lesson one step further along — the named tables do not exist at all.

## 5. Field mapping (for whoever runs the write)

Recorded now, while the analysis is fresh. **Unverified against any live schema** — every
target column below is named by the originating task, not confirmed to exist.

### Corridor facts

| artifact field | proposed column | note |
|---|---|---|
| `corridor` (`"NO->GB"`) | `corridor_id` FK → `kg_corridors.id` | All 6 parent rows must be created first; none exist. |
| `employee_type` (`"all"`) | — | **Ambiguous, do not guess.** See below. |
| `category` | `category` | 14 distinct values, e.g. `immigration_work_authorization`, `registration_cpr`, `tax_expat_scheme`. |
| `official_guidance` | `official_guidance` | Must stay a **separate column** from `actual_reality`. |
| `actual_reality` | `actual_reality` | ″ |
| `action_required` | `action_required` | |
| `source_url` + `source_name` + `retrieved_at` | one `kg_requirement_sources` row | One requirement may carry several. |
| `source_missing` / `flagged` | keep as honesty flags | Zero set in this batch; a `true` gets **no invented citation**. |
| — | `non_obvious_flag` | `true` for all 20 — every B3 record *is* a divergence flag. |
| — | `status` | `'candidate'`. Never `live` / `lawyer_verified` / `user_verified`. |
| — | `consensus_score` | Single-pass Otto research, **not** a 5-pass beam. Record that honestly; do not inflate. |
| — | `id` | `[corridor_id]-[employee_type_id]-[category]-[seq]`, per the task. |

**The `employee_type` mapping has no honest answer and must not be guessed.** All 20 records
carry the literal value `"all"`. That is a wildcard, not an employee type — there is no
`kg_employee_types` row it corresponds to. It maps naturally onto an *applies-to* predicate,
which is exactly how the in-repo rule engine models it (`appliesTo: 'all' | 'eea' |
'non-eea'`, distinct from `EmployeeType = 'eea' | 'non-eea'`). If the target schema requires
a concrete `employee_type_id` FK, this batch cannot supply one and the schema needs a
wildcard row or a nullable column. **Flagged, per the task's instruction not to silently drop
a fact on an ambiguous mapping.**

### City enrichment

The delivered artifacts carry **8 keys**, not the 21 columns the task described.

| artifact field | proposed `geo_city_content` column |
|---|---|
| `country` (`"NO"` / `"DK"`) | `country_code` |
| `city` | `city_name` |
| `topic` | `category` |
| `title` | `title` |
| `body` | `body` |
| `source_url` | `source_url` |
| `source_name` | *(no named column — put in `extras`)* |
| `retrieved_at` | *(no named column — put in `extras`)* |
| — | `geo_uid` — **derived**, not delivered: `geo-<country-city-category-title>` slugified. This is the idempotency key; the artifacts do not contain it. |
| — | `provenance` = `'research'`, `source_file` = the artifact filename |

**Eleven task-named columns have no source data**: `summary`, `latitude`, `longitude`,
`district`, `budget_tier`, `is_family_friendly`, `min_child_age`, `max_child_age`,
`price_range_text`, `external_url`, `trust_tier`. These must be left **NULL**. Filling them
is fabrication, which the batch policy forbids outright.

### Idempotency

- City enrichment: unique on `geo_uid`; duplicates **skipped**, never overwritten.
- Corridor facts: unique on the composite `id` above.

A re-run must produce zero duplicates and must never overwrite a row a reviewer has already
approved. `requirement_items.review_status` is the standing example of how this goes wrong —
it defaults to `'approved'`, so an `ON CONFLICT … UPDATE` that touches it can silently
un-approve reviewed work.

## 6. Layer separation — the non-negotiable rule

The pipeline is:

```
Otto / LLM generates candidates
        ↓
real user + regulated lawyer verify   (CVR, attestations, sign-offs)
        ↓
deterministic engine serves
```

Generation and serving never touch. This batch ends at **"candidate, in the repo,
reviewable"**. Nothing here is customer-served, and nothing may be marked
`verified` / `live` / `lawyer_signed` / `sellable` by this import or any follow-up that
skips the middle row.

This mirrors the hard gate already in `CLAUDE.md` (*Generation/serving split*): the
deterministic serving path must never be able to reach an LLM at request time, and LLM output
becomes served data only after human review.

The `candidate_only` gate in the verification script asserts no record carries a served
status. It currently passes on all 20.

## 7. Validation

`scripts/verify_b3_batch.py` is the gate. It is generated output, not prose — re-run it
rather than trusting this document:

```bash
python3 scripts/verify_b3_batch.py          # check, exit non-zero on failure
python3 scripts/verify_b3_batch.py --write  # also refresh validation_report.json
```

Result as committed — **7/7 pass**:

| gate | result |
|---|---|
| `count:corridor_facts` | 20 records, manifest declares 20 |
| `count:city_stavanger` | 6 records, manifest declares 6 |
| `count:city_copenhagen` | 7 records, manifest declares 7 |
| `no_fabrication` | 0 facts with neither `source_url` nor `source_missing=true` |
| `direction_breakdown` | matches the manifest exactly across all 6 directions |
| `employee_type_unambiguous` | records the wildcard `["all"]` rather than guessing a mapping |
| `candidate_only` | 0 records carry a served status |

Counts reconcile exactly against the manifest: 20 / 6 / 7. **Skip list: empty** — nothing was
skipped, because nothing was written.

The task's remaining validation criteria are **not yet satisfiable** and are deferred with
the write: FK integrity against `kg_corridors` / `kg_employee_types` cannot be checked
against tables that do not exist here.

## 8. Metrics this feeds

- **The moat metric** — count of non-obvious items a real user confirms they did not already
  know, captured later in CVRs. All 20 records are divergence flags; preserving
  `official_guidance` vs `actual_reality` as *separate* fields is what makes that
  confirmation possible. Flatten them and the metric cannot be computed.
- **`consensus_score` / `pass_frequency`** — these are single-pass Otto research, not a
  5-pass beam. Whatever schema receives them must reflect that. Inflating a confidence score
  to match a field's default is the quiet version of fabrication.
- **`relief_moment_response`** (PostHog) and funnel metrics are downstream. No action here
  beyond not corrupting the candidate data they will be measured on.

## 9. Eval

The corridor publish gate requires a **Case Verification Report from a real case with verdict
`pass`**, plus regulated-lawyer attestations, before a corridor can go live. The eval harness
(`kg_case_verification_reports`, `attestations`, `verification_log`) acts on corridors sitting
at candidate status.

This batch leaves the six B3 directions cleanly *outside* that harness — they are not yet rows
in any corridor table. **No eval table was touched, and none was seeded with placeholder
data.** When the write happens, the corridors must land at `candidate` so the harness can pick
them up.

## 10. How to re-run / how to finish this

1. **Re-verify what is committed:** `python3 scripts/verify_b3_batch.py`
2. **Close the DK/DE source gap first** (§4). Without it `scripts/import_otto_facts.py`
   rejects 9 of the 20 facts outright and the three DK/DE directions land nothing.
3. **Convert to otto JSONL** and stage:
   ```bash
   python scripts/import_otto_facts.py B3-corridor-facts-2026-08-18            # dry run (default)
   python scripts/import_otto_facts.py B3-corridor-facts-2026-08-18 --apply \
       --source-label "B3 corridor compliance flags (Nordics/UK/DE)"
   ```
   Dry run takes the same code path as the real run, so its numbers are the numbers you get.
   Do not reach for `--allow-rejections` — the reject list is the re-sourcing worklist.
4. **City enrichment** goes through the resources bundle path, `draft_only`:
   `python scripts/import_resources.py --bundle .../bundle_stavanger.json`
5. **Do not promote.** No `--promote` in any of the above. Rows stay at `needs_review` and
   reach customers only through the existing `/admin/countries` gate.
6. **Update this document's Status line** and the `loaded_into_database` field in
   `validation_report.json` when the write lands.

The `employee_type = "all"` question from §5 is **closed**: `backend/imports/otto/mappings.py`
states that NULL in the nationality column means *applies to everyone*, and explicitly notes
that `"any"` is deliberately not a value. The wildcard therefore maps to an **omitted**
`applies_to.nationality` — the correct representation, not a compromise.

### The general procedure

This batch is one instance of "GCS NDJSON research batch → staging/candidate". The repeatable
form is documented in `CLAUDE.md` under *Research batch intake (GCS → candidate)*.
