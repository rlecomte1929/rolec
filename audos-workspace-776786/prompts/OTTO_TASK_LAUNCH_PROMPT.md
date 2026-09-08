# Paste this into Otto (Audos) — ReloPass gap-fill wave

> Paste everything between the lines into a **fresh Otto meeting**. Otto will stage
> ~45 small tasks. Review the draft list, then say "run all" (or name a batch).
> Each task writes files to GCS and reports one manifest URL, which is all I need
> to fetch, QA and load.

---

# ReloPass gap-fill wave — task fan-out brief

You are staging a batch of **small, independent research tasks**. One task per
unit. A unit is one country for one domain, or one city for providers. Do not
merge units. Do not run a single large task.

## The delivery contract — this is the part that has been failing

Every previous wave lost data at the handoff, not at the research. Three rules,
all mandatory:

**1. Write files to GCS. Never paste results inline.**
Use `store_attachment` for every file. Inline chat text cannot be loaded and is
lost when the meeting archives. If a task cannot write to GCS, it must report that
as a failure — not paste the data instead.

**2. Every task emits a manifest, and the manifest key must be `manifest_rows`.**

```json
{
  "unit": "NO-vehicle_import",
  "meeting_id": "<this meeting's id>",
  "generated_at": "<ISO timestamp>",
  "manifest_rows": [
    { "target_table": "requirement_entities", "unit": "NO-vehicle_import",
      "record_count": 9,  "gcs_url": "https://storage.googleapis.com/audos-images/workspace-media/.../file.json" },
    { "target_table": "requirement_facts",    "unit": "NO-vehicle_import",
      "record_count": 47, "gcs_url": "https://storage.googleapis.com/audos-images/workspace-media/.../file.json" }
  ]
}
```

Not `manifest`. Not `files`. **`manifest_rows`** — the loader reads that key.
`gcs_url` must be the complete public URL, no shortening.

**3. Report the manifest URL as plain text, one per line.**
No markdown tables, no `[link](url)`, no `…`, no truncation. The chat UI mangles
formatted links. One bare URL per line is the only format that survives.

Final message of every task, exactly this shape:

```
UNIT: NO-vehicle_import
STATUS: complete
MANIFEST: https://storage.googleapis.com/audos-images/workspace-media/.../manifest.json
COUNTS: requirement_entities=9, requirement_facts=47
T1_PCT: 91
GAPS: 2 topics have no published fee schedule
```

## Record schemas — exact field names, no substitutions

Field names have drifted between runs and every drift silently dropped records.
Use these names literally.

**`requirement_entities` — one object per topic:**

```json
{ "destination_country": "NO", "domain_area": "vehicle_import",
  "topic_key": "vehicle_import_duty", "title": "Vehicle import duty (Norway)",
  "status": "published" }
```

- `destination_country` — ISO-2, this exact key. Not `country`, not `destination_iso2`.
- `domain_area` — one of: `immigration`, `registration`, `tax`, `social_security`,
  `healthcare`, `housing`, `vehicle_import`, `vehicle`, `domestic_move`,
  `financial`, `employer_compliance`, `pet`, `other`.

**`requirement_facts` — one object per fact:**

```json
{ "destination_country": "NO", "topic_key": "vehicle_import_duty",
  "fact_type": "fee", "fact_key": "engangsavgift_rate",
  "fact_text": "One-off registration tax is calculated on CO2 emissions and weight, with a 2026 CO2 component starting at NOK 852 per g/km above 87 g/km.",
  "applies_to": { "nationalities": ["ALL"], "scenario": "single" },
  "source_url": "https://www.skatteetaten.no/...",
  "evidence_quote": "Engangsavgiften beregnes ut fra kjøretøyets vekt og CO2-utslipp.",
  "confidence": "high", "status": "published" }
```

- `fact_text` is **the statement itself**, written by you. `evidence_quote` is the
  **verbatim sentence from the source** that proves it. **Both are required on
  every record.** A record with only `evidence_quote` is discarded — 133 records
  were lost to exactly this last time.
- Put `destination_country` on the fact as well as the entity. Do not rely on
  `entity_id` to carry it.
- `fact_type` — one of: `eligibility`, `document`, `step`, `deadline`, `fee`,
  `where_to_apply`, `account`, `other`.
- `fact_key` unique within its `topic_key`.
- Never write `fact_value`, `body`, `requirement` or `text` instead of `fact_text`.

**`vendor_candidates` — one object per provider:**

```json
{ "name": "Provider Official Name", "city": "Frankfurt", "country": "DE",
  "category": "housing_agencies", "website": "https://...",
  "contact_email": "", "contact_phone": "+49 ...",
  "languages_supported": ["English","German"],
  "description": "1–2 lines, expat-relevant",
  "source_url": "https://official-or-authoritative-source",
  "source_tier": "T1", "confidence": "high",
  "dedupe_key": "housing_agencies|DE|frankfurt|provider official name" }
```

- Categories, exact keys: `housing_agencies`, `movers`, `schools`, `legal_admin`,
  `tax_finance`, `banks`, `medical`, `telecom`, `insurance`, `storage`,
  `language_cultural`, `rmc`, `dsp`.
- `source_url` must be a registry, licensing body, chamber roll or official
  directory that a third party can check. **A provider's own website is a
  supporting link, never the accreditation evidence.** Wikipedia and Wikidata are
  not registries.
- `dedupe_key` = `category|COUNTRY|city_lowercase|name_lowercase`.

**`staged_resource_candidates` — one object per guide:**

```json
{ "country_code": "DE", "city_name": "Frankfurt", "category_key": "neighbourhoods",
  "title": "...", "summary": "...", "body": "...",
  "resource_type": "guide", "audience_type": "all",
  "source_url": "https://...", "trust_tier": "T1", "confidence_score": 0.9 }
```

## Quality bar

- **T1 sources only** — government, regulator, official registry, chamber. Aim
  >70% T1 per unit; state the actual percentage in `T1_PCT`.
- **No fabrication.** If a figure is not published, say so in `GAPS` and omit the
  fact. A short honest set beats a padded one.
- **Dead links are dropped on load** — every `source_url` is fetched and checked.
- Name what you could not find. A stated gap is a finding; a silent omission is a
  defect.
- If a source is JavaScript-rendered and returns nothing to a static fetch, report
  that in `GAPS` rather than guessing.

## Cost and stopping

Each unit is bounded at roughly $3–6. If a unit approaches its bound, **stop, emit
what you have, and list the remainder under `GAPS`** — a partial unit with an
honest gap list is worth more than an over-run.

---

# The tasks

## Batch A — vehicle import facts (18 tasks)

Each of these countries already has its `vehicle_import` topics loaded and **zero
facts against them**. Do not re-create the topics; research the facts and tag them
to the existing `topic_key` values you generate for the same topics.

> NO, PT, AT, CZ, PL, IN, IE, JP, IT, SE, BR, HK, AE, IL, DK, KR, ZA, BE

Per country, cover: import duty and VAT treatment, emissions/homologation
requirements, registration procedure and where to apply, required documents,
timelines, temporary-import and returning-resident relief, EU/EEA vs third-country
differences, and left/right-hand-drive rules where relevant.

`domain_area: "vehicle_import"`. One task per country.

## Batch B — immigration top-up (16 tasks)

These countries are far below usable depth. Bring each to at least 40 facts across
its main work-authorisation routes.

- **Critical (9–11 facts today):** UA, RU, BR, KR, ZA, IL, HK, CZ, IN
- **Thin (19–33 facts today):** QA, PL, IT, SA, TH, LU, FI

Per country cover: each main work permit / visa route, eligibility, required
documents (one fact each), fees with currency, processing times, application
steps, where to apply, residence registration, tax ID, social security and health
insurance registration, family reunification and dependant rights.

Tag `applies_to.nationalities` only where the rule genuinely differs by
nationality; otherwise `["ALL"]`. Use `applies_to.scenario` from: `single`,
`spouse`, `family_children`, `partner_unmarried`, `student`, `special_routes`.

`domain_area: "immigration"`. One task per country.

## Batch C — provider cities (8 tasks)

- **Zero coverage today:** Frankfurt (DE), Milan (IT), Amsterdam (NL), Dublin (IE), London (GB)
- **Barely started:** Munich (DE, 8 rows), Oslo (NO, 12 rows), Dubai (AE, 5 rows)

Per city: 5–10 providers each in `housing_agencies`, `movers`, `schools`,
`legal_admin`, `tax_finance`, `banks`, `medical`; 3–7 each in `telecom`,
`insurance`. For the three partial cities, only add what is missing — the existing
rows are live.

`target_table: "vendor_candidates"`. One task per city.

## Batch D — repair the statement-less facts (1 task)

The wave 3a output wrote `source_quote` with no fact statement, so 133 records were
discarded. Locate that run's fact files, and for every record write the missing
`fact_text` from the quote and source you already have. Do not re-research; do not
invent. If a record's quote does not support a statable fact, drop it and list it
under `GAPS`.

## Batch E — reference content (2 tasks)

`staged_resource_candidates` holds 33 rows in total, so this stream is effectively
empty. Two tasks:

1. Neighbourhood and cost-of-living guides for the five Batch C cities.
2. Arrival how-to guides (first 30 days) for DE, NO, FR, US, IE.

---

## Before you stage anything

Reply first with **the task list only** — unit name, batch, and estimated cost per
unit. Do not start any research until I confirm. Then run them in batch order:
A, then C, then B, then D, then E.
