# Cursor Brief F — `otto_resource` profile for `convert_otto_batch.py`

- **Deliverable:** modified `scripts/convert_otto_batch.py` (return the FULL file) +
  additions to `scripts/tests/test_convert_otto_batch.py`.
- **Runtime:** Python 3.11, stdlib. No new deps.
- **You (Cursor) have no repo access** — the current structure and the new vocabulary are embedded
  below. Return the whole modified file.

## Why
Otto's live "resource" deliveries arrive in a **fifth** vocabulary the converter doesn't recognise —
the real GB facts batch (`gb-facts-living-logistics-2026-09-08`) came in this shape and needed a hand
transform. Add an `otto_resource` profile so it converts automatically.

## The delivered vocabulary (one JSON object per NDJSON line)
```jsonc
{
  "batch_id": "gb-facts-living-logistics-2026-09-08",
  "fact_id": "gb-ll-001",                       // → fact_key
  "corridor": "IN-GB",                          // tail (after '-') → destination_country (GB)
  "category": "council_tax",                    // → entity_topic_key AND topic_key
  "fact_type": "liability_rule",                // a descriptive slug, NOT KNOWN_FACT_TYPES → map to 'other', keep raw in applies_to._otto_fact_type
  "fact_text": "…",                             // → fact_text
  "evidence_quote": "…",                        // → evidence_quote
  "source_url": "https://www.gov.uk/…",         // → source_url
  "scope": "non-EEA professional",              // → applies_to.nationality + applies_to.status (parse it)
  "verified_date": "2026-09-08"
}
```
Detect on: a record that has `fact_id` AND `category` AND `scope` AND `corridor` (and no
`entity_topic_key`/`fact_key`).

## Mapping rules (same output contract as the other profiles — both spellings, asserted equal)
- `entity_topic_key` = `topic_key` = `category`
- `fact_key` = `fact_id`
- `destination_country` = iso2 of the corridor tail (`"IN-GB"` → `"GB"`)
- `entity_title` = `category` in Title Case with spaces (`council_tax` → `"Council Tax"`)
- `fact_text` = `fact_text`; `evidence_quote` = `evidence_quote`; `source_url` = `source_url`
- `fact_type` = `'other'` (the input `fact_type` is a descriptive slug, not a `KNOWN_FACT_TYPES`;
  record a downgrade and stash the raw value in `applies_to._otto_fact_type`)
- **`applies_to` from the `scope` STRING** (this is the new bit): parse `scope` (lower-cased) into
  - `status` = the first of `professional|student|family|any` found (else fail the row unless
    `--default-status` — same invariant #1 as every profile)
  - `nationality` = `"non-EEA"` if the scope contains `non-eea`/`non eea`/`third`; `"EU"`/`"EEA"` if it
    names those; else **unset** + list in `missing_nationality` (never derive from the corridor).
  `"non-EEA professional"` → `{"nationality":"non-EEA","status":"professional"}`.
- `domain_area` (loader spelling) from a small category→ALLOWED_DOMAINS map, default `'other'`:
  `council_tax→tax`, `driving_licence→vehicle`, `bank_account→financial`, everything else→`other`.
  (`ALLOWED_DOMAINS`: immigration, registration, tax, social_security, healthcare, housing, other,
  vehicle, vehicle_import, domestic_move, financial, employer_compliance, pet.)

## Fit it into the existing structure
`convert_otto_batch.py` already has `PROFILES = ("parsers","requirement_items","nested_entity","beam")`,
`detect_profile(first)`, `flatten_profile(rec, profile)`, `_destination`, `_fact_key`, `_title`,
`_fact_type`, `_map_nationality_token`. Add `"otto_resource"` to `PROFILES`, a branch in
`detect_profile`, and the mapping in `flatten_profile` (+ the helpers). Do NOT change the other four
profiles' behaviour.

## Acceptance tests you deliver green (offline)
1. **detect:** a record with `fact_id`+`category`+`scope`+`corridor` → profile `"otto_resource"`.
2. **map:** `fact_id`→`fact_key`, `category`→`entity_topic_key`=`topic_key`, corridor tail→`GB`,
   Title-Case `entity_title`, both spellings asserted equal.
3. **scope parse:** `"non-EEA professional"` → `applies_to.nationality="non-EEA"`, `status="professional"`.
   `"EEA family"` → `EU/EEA` + `family`. A scope with no recognised status ⇒ fail (or `--default-status`).
   A scope with no nationality ⇒ unset + `missing_nationality`.
4. **fact_type** → `'other'` + downgrade recorded + raw kept in `applies_to._otto_fact_type`.
5. **domain_area** map (council_tax→tax etc.); unknown category→other.
6. **no fact dropped;** the other 4 profiles' tests stay green.

## Integration parity (applier runs, not yours)
`convert_otto_batch.py docs/imports/gb-facts-living-logistics-2026-09-08/facts.ndjson --out …
--default-status professional` reproduces the 20-record parsers-vocab output that parsed with **0**
`parsers.read_jsonl` rejections (matches the hand transform already committed as that batch's
`clean.ndjson`).

## Return
Full modified file + tests, via the GCS/manifest contract (or abs_path + sha256 on final bytes).
Don't commit or PR.
