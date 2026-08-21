# Batch `ve-ie-entry-family-2026-08-20` — VE→IE entry visa + dependants

**AIQ-2027** (load) · research from **AIQ-1993** · loaded as **candidates only**

Nine sourced facts closing the two gaps that block Andrea's real case: a Venezuelan national
resident in Spain relocating Madrid→Dublin with a spouse and two dependants. Before this batch,
`immigration_requirements` held **0** rows for `corridor_to='IE'` and all 14 approved Irish
`requirement_items` were single-applicant permit mechanics — nothing about the entry visa she
needs, nothing about her family.

| | |
|---|---|
| Artifact | `docs/imports/ve-ie-entry-family-2026-08-20/ve_ie_entry_family_requirement_facts.ndjson` |
| sha256 | `2186f59ae0cb06bb7403ef4bed2f291ff1ad4313bc270fb0051883f7e63a46d6` |
| Records | 9 (6 non-obvious, 4 needs_lawyer_review) |
| Corridor | ES→IE, nationality class `THIRD_COUNTRY` |
| Staged into | `otto_staging.immigration_fact_candidates`, `status='new'` |
| Promoted | **No.** Out of scope for AIQ-2027 — needs counsel sign-off first. |
| Gate | `./.venv311/bin/python scripts/check_ve_ie_batch.py` |

## Why a conversion step exists

AIQ-1993 delivered the NDJSON in the **`requirement_items`** field vocabulary — `fact_uid`,
`topic_key`, `destination_country_code`. The otto reader requires `fact_key`,
`entity_topic_key`, `destination_country` and does no aliasing, so the deliverable failed the
card's own Test Command at the first line:

```
✖ line 1: missing required field(s): destination_country, entity_topic_key, fact_key
exit=2
```

That is the same gap `convert_b3_to_otto_jsonl.py` closes for the B3 batch, so this batch
follows that precedent rather than inventing a second intake path:

```
docs/imports/ve-ie-entry-family-2026-08-20/…ndjson   ← source of truth, never retyped
  → scripts/convert_ve_ie_to_otto_jsonl.py           ← rename + compose, writes no DB
  → audos-workspace-776786/data/<batch>.jsonl
  → scripts/import_otto_facts.py <batch> --expected 9   ← existing importer, UNCHANGED
  → otto_staging.immigration_fact_candidates   status='new'
```

`import_otto_facts.py` was not modified. Regenerate the JSONL rather than hand-editing it.

## Reconciliation

```
✔ PASS  batch 've-ie-entry-family-2026-08-20'
    inserted this run: 9
    already present:   0
    accounted for:     9 of 9 expected
    entities touched:  9
```

Zero rejections — every source clears the sourcing gate:

| Host | `classify_source` | Rows |
|---|---|---|
| `www.irishimmigration.ie` | official | 3 |
| `enterprise.gov.ie` | official | 1 |
| `www.citizensinformation.ie` | semi_official | 5 |

The five `citizensinformation.ie` rows are downgraded to `needs_review` by `grade()` — expected,
not a defect: Citizens Information restates rules published elsewhere, so it is deliberately
semi-official in the allowlist.

## Derivations — what was computed, not read

Everything here is derived from delivered fields. Nothing was invented; a field the artifact
does not carry stays absent.

| Field | Derivation |
|---|---|
| `destination_country` | `destination_country_code` verbatim (`IE`) |
| `entity_topic_key` | `topic_key` verbatim — unique across the batch, so 9 facts → 9 entities → the 9 requirement_items the manifest asks for. Collapsing them under one entity would promote to a single merged requirement. |
| `fact_key` | `{origin}_{dest}_{topic_key}` — origin included so a later batch from another origin cannot land on an existing `dedupe_key` |
| `entity_title` | `"Ireland — " + topic_key` with underscores spaced |
| `fact_text` | the artifact's `fact_text`, plus `Commonly believed:` / `Actually:` / `Action required:` from `non_obvious_note` on the 6 non-obvious rows |
| `fact_type` | not carried → `other` (the reader's default). Picking `document`/`step`/`eligibility` per row would be a guess presented as a reading. |
| `confidence` | not carried → `medium` |

### `applies_to.nationality` is read, never derived from the corridor

The corridor is ES→IE, so `nationality_class.classify("ES","IE")` answers **EEA** — a Spanish
national is a free mover into Ireland. The subject of this batch is a **Venezuelan** national
who happens to live in Spain, and the entire deliverable exists because her Spanish residence
does not carry into Ireland. So the delivered `applies_to_nationality_classes: ["THIRD_COUNTRY"]`
is used and the corridor derivation is deliberately **not**.

This is the one mistake that would matter most: a row staged as `EEA` serves the free-mover
track to a visa-required national. `test_nationality_is_read_from_the_artifact_not_the_corridor`
guards it, and was confirmed to fail against a corridor-derived implementation.

### Fields with no column anywhere

`immigration_fact_candidates` has no column for these, so they ride verbatim in the
`applies_to` jsonb — the same place `candidate_beam/importer.py` parks its beam metadata:

`fact_uid` · `pillar` · `non_obvious` · `needs_lawyer_review` · `quote_verbatim_confirmed` ·
`source_name` · `corridor` · `batch_id`

## ⚠ Known gap — `auto_accepted` on a counsel-flagged row

`grade()` awards `auto_accepted` for an official publisher **plus a quotable line of evidence**.
Every row here carries an `evidence_quote`, but every row also carries
`quote_verbatim_confirmed: false` — the quote was captured and never re-checked against the
page. `grade()` has no vocabulary for that flag, so four rows score `auto_accepted`, and **one
of them is counsel-flagged**:

```
IE|dependant_join_family_d_visa_required|es_ie_dependant_join_family_d_visa_required
```

**This is not currently exploitable.** The importer stages every row at `status='new'` and
`promote()` only ever reads `status='ready'`, so nothing reaches `requirement_items` without a
person moving it. The risk is a *reviewer* reading `auto_accepted` as "already cleared" on a row
that needs a lawyer.

`check_ve_ie_batch.py` prints this overlap on every run. The durable fix — teaching
`parsers.grade()` to downgrade on an explicit `quote_verbatim_confirmed: false` — was left out
deliberately: it changes shared behaviour for every batch and belongs in its own card, not
smuggled into a load.

## The four rows counsel must clear before any approval

| `fact_uid` | Claim |
|---|---|
| `…:spanish_residence_does_not_grant_irish_entry` | A Spanish residence card does not grant entry to Ireland (non-Schengen) |
| `…:csep_immediate_family_reunification` | CSEP allows immediate family reunification; GEP restricts it for 12 months |
| `…:spouse_stamp_1g_right_to_work` | CSEP spouse gets Stamp 1G with employment access |
| `…:dependant_join_family_d_visa_required` | Dependants need their own Join Family 'D' visa |

All nine are `verification_status='representative'` and `review_status='pending'`.

## Reproducing

```bash
./.venv311/bin/python scripts/check_ve_ie_batch.py                  # integrity + counts + reader
./.venv311/bin/python scripts/convert_ve_ie_to_otto_jsonl.py        # regenerate the JSONL
./.venv311/bin/python scripts/import_otto_facts.py \
    ve-ie-entry-family-2026-08-20 --expected 9                      # dry run (default)
RELOPASS_QUERY_COUNTER_OFF=1 DATABASE_URL="sqlite:///./ci_test.db" \
    ./.venv311/bin/python -m pytest backend/tests/test_ve_ie_corridor_facts_conversion.py -q
```

To actually stage, add `--apply`. Rollback is deleting the batch's rows by `batch_id`.
