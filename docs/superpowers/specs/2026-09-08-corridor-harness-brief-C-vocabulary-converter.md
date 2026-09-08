# Cursor Brief C — general vocabulary converter (`scripts/convert_otto_batch.py`)

- **Deliverable:** `scripts/convert_otto_batch.py` (new) + `scripts/tests/test_convert_otto_batch.py`
  (new).
- **Runtime:** Python 3.11. Stdlib only. `argparse`.
- **You (Cursor) have no repo access.** All vocabularies and constants are embedded below. Build a
  general converter that **replaces** the three fragile per-batch converters
  (`convert_b3_to_otto_jsonl.py`, `convert_ve_ie_to_otto_jsonl.py`,
  `convert_es_ie_thirdcountry_to_otto_jsonl.py`). The integrator verifies semantic parity against the
  three real batches; **byte-parity is NOT required** (this improves on them).

---

## 0. The problem it solves

An Otto corridor batch has **two live readers that disagree on field names**, and each rejects the
other's vocabulary:

| reader | wants |
|---|---|
| `import_otto_facts.py` → `parsers.read_jsonl` (staging) | `entity_topic_key`, `entity_title`, `destination_country`, `fact_key`, `confidence` |
| `check_otto_batches.py` (delivery gate, simulates otto-loader v6) | `target_table`, `topic_key`, `entity{}`, `confidence_score` |

A batch in one vocabulary is unreadable by the other. The converter emits **both spellings in every
record, asserted equal**, so one output passes both readers. It also enforces the invariants that have
silently lost data before (absent `applies_to.status` → invisible rows; nationality derived from the
corridor → wrong track served).

---

## 1. Output record — the shape that satisfies BOTH readers

Every output NDJSON line is one JSON object carrying both spellings:

```jsonc
{
  // ── parsers vocab (staging) ──
  "destination_country": "PT",
  "entity_topic_key":    "residence_permit",
  "entity_title":        "Residence permit",
  "fact_key":            "processing_time",
  "fact_text":           "Composed narrative …",
  "source_url":          "https://imigrante.aima.gov.pt/…",
  "fact_type":           "deadline",            // ∈ KNOWN_FACT_TYPES
  "evidence_quote":      "o prazo … 90 dias",   // optional; carry through
  "confidence":          "high",                // low|medium|high
  "confidence_score":    0.9,                    // > 0 and <= 1, never 0/None
  "applies_to": {
     "nationality": "non-EEA",                   // FROM THE ARTIFACT — never derived from the corridor
     "status":      "professional",              // REQUIRED: professional|student|family|any
     "non_obvious": true,                        // optional, carry through
     "timing":      "…",                         // optional, carry through
     "pillar":      "RESIDENCE",                 // carried but downstream-ignored; harmless
     "_beam": { … }                              // parked structured components (see §4)
  },
  // ── loader/gate vocab ──
  "target_table":  "requirement_facts",
  "topic_key":     "residence_permit",           // == entity_topic_key
  "domain_area":   "immigration",                // ∈ ALLOWED_DOMAINS
  "entity": {
     "destination_country": "PT",                // == destination_country
     "topic_key":           "residence_permit",  // == entity_topic_key
     "domain_area":         "immigration",        // == top-level domain_area
     "title":               "Residence permit"    // == entity_title
  }
}
```

**Paired-equality assertions the converter must enforce on every record** (raise, don't warn):
`topic_key == entity_topic_key == entity.topic_key` · `entity.destination_country ==
destination_country` · `entity.title == entity_title` · `domain_area == entity.domain_area ∈
ALLOWED_DOMAINS` · `confidence_score == SCORE[confidence]` and `0 < confidence_score <= 1`.

## 2. Embedded constants (verbatim — you can't see the source)

```python
KNOWN_FACT_TYPES = ("fee", "eligibility", "document", "deadline", "step", "where_to_apply", "other")
# input 'timeline' -> 'deadline'; anything else unknown -> 'other' (record a downgrade note)

ALLOWED_DOMAINS = ("immigration", "registration", "tax", "social_security", "healthcare", "housing",
                   "other", "vehicle", "vehicle_import", "domestic_move", "financial",
                   "employer_compliance", "pet")   # unknown domain_area -> 'other' (record a downgrade)

NATIONALITY_CLASSES = ("EU", "EEA", "non-EEA", "non-EU")   # the only accepted applies_to.nationality values
STATUS_TO_PURPOSE   = {"professional": "employment", "student": "study", "family": "family", "any": "other"}
SCORE = {"low": 0.3, "medium": 0.6, "high": 0.9}           # confidence label -> score; absent -> 0.6, NEVER 0/None
```

## 3. Invariant rules (the "hardening")

1. **`applies_to.status` is REQUIRED.** If a record lacks it (and no `--default-status` is given),
   **fail the whole run** (exit 1) naming the offending `dedupe_key`s. Absent status silently becomes
   `purpose='other'` downstream and the row is invisible to the corridor call — this is the trap being
   closed. `--default-status professional` may supply it batch-wide *only when the operator asserts
   it*; never invent it per-record.
2. **Nationality comes FROM THE ARTIFACT, never from the corridor.** Read
   `applies_to.nationality` / `applies_to_nationality_classes` / `nationality_classes` off the input.
   Map to a single `NATIONALITY_CLASSES` value. **Never** call any `classify(origin, dest)` — a
   Venezuelan resident in Spain on an ES→IE move is `non-EEA`, not the corridor's EEA. If the artifact
   carries no nationality, leave `applies_to.nationality` **unset** and record it in the report's
   `missing_nationality` list (it becomes `Unmapped` at promote — the correct loud failure). Do not
   fabricate.
3. **fact_type** → `KNOWN_FACT_TYPES` (`timeline`→`deadline`; unknown→`other`, recorded).
4. **domain_area** → `ALLOWED_DOMAINS` (unknown→`other`, recorded).
5. **confidence_score** from `SCORE`; absent→0.6; assert `0 < score <= 1`.
6. **No fact dropped.** `len(input) == len(output)`. A record that cannot be converted (e.g. missing a
   required source_url/fact_text/topic) is an **error that fails the run**, never a silent skip.
7. **pillar** is carried into `applies_to.pillar` untouched if present (downstream ignores it); do not
   act on it.

## 4. Input profiles (auto-detect from the first record's keys; `--profile` overrides)

| profile | detect (keys present) | mapping |
|---|---|---|
| `parsers` | `entity_topic_key` & `fact_key` & `destination_country` | pass-through + add loader spellings + enforce invariants |
| `requirement_items` | `fact_uid` \| `topic_key` & `destination_country_code` | rename `fact_uid`→`fact_key`, `topic_key`→`entity_topic_key`, `destination_country_code`→`destination_country`; `title`→`entity_title` |
| `nested_entity` | top-level `entity` is an object | flatten `entity.{destination_country,topic_key,title,domain_area}` up to the parsers keys |
| `beam` | `official_guidance` \| `actual_reality` \| `action_required` \| `category` | `category`→`fact_type`; compose the narrative fields into one `fact_text`; keep the components in `applies_to._beam` |

**`beam` composition:** when the input has no single `fact_text` but carries narrative components,
compose them labelled into one string, e.g.
`"Official guidance: … \nActual reality: … \nAction required: …"` (omit absent parts), and stash the
raw components in `applies_to._beam = {official_guidance, actual_reality, action_required, source}`.
The channel carries one `fact_text`; the structured pieces are parked, not lost.

Unknown profile (no branch matches) ⇒ exit 2, printing the keys of the first record so the operator
can add a `--profile` or a mapping.

## 5. CLI

```
python scripts/convert_otto_batch.py <in.ndjson> --out <clean-input.ndjson> [--profile P]
        [--default-status professional] [--report <json>]
python scripts/convert_otto_batch.py <in.ndjson> --check --out <committed.ndjson>   # re-convert & diff
```
- Writes `--out` (parsers+loader NDJSON). `--report` writes `{profile, records_in, records_out,
  downgrades:{fact_type:[…], domain_area:[…]}, missing_nationality:[…]}`.
- `--check`: re-convert the input and assert it equals the committed `--out` file (record-set equality
  modulo key order); exit 1 on any diff. This is the CI/pre-commit parity guard, mirroring the old
  per-batch `--check`.
- **Exit:** `0` clean · `1` invariant failure (missing status, dropped fact, bad paired-equality,
  `--check` mismatch) · `2` usage / unknown profile.

## 6. Acceptance tests you deliver green — offline, inline fixtures

Load by path with `importlib.util.spec_from_file_location` (scripts/ vs backend/scripts/ shadowing).

1. **parsers profile** — an already-parsers-vocab record converts to output with both spellings and
   all paired equalities holding.
2. **requirement_items profile** — `fact_uid`/`topic_key`/`destination_country_code` rename correctly.
3. **nested_entity profile** — a nested `entity{}` flattens; `entity.title` → `entity_title`.
4. **beam profile** — `category`→`fact_type`; the three narrative fields compose into one `fact_text`
   and land in `applies_to._beam`; count preserved.
5. **status REQUIRED** — a record missing `applies_to.status` and no `--default-status` ⇒ exit 1,
   message names the dedupe_key. With `--default-status professional` ⇒ succeeds and stamps it.
6. **nationality NOT derived from corridor** — input corridor `ES-IE` but artifact
   `applies_to.nationality='non-EEA'` ⇒ output `non-EEA` (proves no `classify(origin,dest)`).
   A record with no artifact nationality ⇒ unset + listed in `--report` `missing_nationality`, run
   still succeeds.
7. **fact_type mapping** — `timeline`→`deadline`; `garbage`→`other` + a downgrade recorded.
8. **domain_area mapping** — unknown domain ⇒ `other` + downgrade recorded; a valid one passes.
9. **confidence_score** — `high`→0.9; absent→0.6; asserts `0 < score <= 1`; never 0/None.
10. **no fact dropped** — `records_in == records_out`; an unconvertible record fails the run (exit 1),
    never a silent skip.
11. **paired-equality guard** — a hand-broken intermediate (e.g. `topic_key != entity_topic_key`)
    raises rather than writing.
12. **--check** — converting then `--check` against the written file passes; a mutated file fails.

## 7. Integration parity the applier runs (NOT your responsibility to green)
Against the three real committed batches (`b3` corridor facts, `ve-ie-entry-family`,
`es-ie-thirdcountry`): the converter's output must (a) parse under `import_otto_facts.py` with **0
rejections**, (b) pass `check_otto_batches.py` (both spellings present), and (c) carry the same facts
and keys the old per-batch converters produced (semantic parity, not byte-identity). Marked
`@pytest.mark.integration`.

## 8. Do NOT
- derive `applies_to.nationality` from the corridor, ever;
- silently skip or drop a record;
- default `applies_to.status` per-record (only batch-wide via explicit `--default-status`);
- emit `confidence_score` of 0 or None;
- modify `parsers.py`/`mappings.py`/`import_otto_facts.py` — this converter feeds them unchanged;
- import from `scripts.*`/`backend.*` at module top level (keep it standalone).

## 9. Return to the integrator
The two files + a 3-line note: the `python -m pytest …` that greens your tests, the profile
auto-detection order, and any input key you saw that you could not map to a profile.
