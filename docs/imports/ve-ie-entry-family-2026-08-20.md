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
| Staged into | `otto_staging.immigration_fact_candidates`, `status='promoted'` |
| Promoted | **Yes, 2026-08-21** — 9 rows into `public.requirement_items`, landed `review_status='pending'` and **approved the same day at 12:02 UTC**. See *Promotion* and *approved and serving* below. |
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

## Quote verification — 2026-08-21

All nine `evidence_quote` values were re-fetched from their source pages and checked against the
live text. **9 of 9 verbatim.** The artifact ships `quote_verbatim_confirmed: false` on every
row because the research lane could not check them; this is that check.

Method: `curl` with a browser UA, `<script>`/`<style>` stripped, tags removed, whitespace and
smart-punctuation normalised, then an exact substring match of the stored quote.

Two things worth knowing before re-running it:

- **`citizensinformation.ie` starts returning HTTP 403** after a handful of requests. A 403 body
  is ~919 bytes, so it cannot contain a long quote and will not produce a false VERBATIM — but it
  *will* produce a false NOT-FOUND. Always assert the status code; a second pass here reported
  every probe absent purely because it was reading the block page.
- **Tag-stripping leaves a space before punctuation** (`long stay 'D' visa .`), so an exact match
  on a quote ending in a full stop fails. That alone downgraded row 2 to PARTIAL on the first
  pass; the page carries the sentence word for word.

This does not clear the four `needs_lawyer_review` rows. Confirming a quote is transcribed
correctly is not confirming the legal claim built on it.

## ⚠ Known gap — `auto_accepted` on a counsel-flagged row (CLOSED by AIQ-2034)

> **Closed 2026-08-20 in #1937.** `parsers.grade()` now downgrades any row carrying
> `quote_verbatim_confirmed: false`, so all 9 rows in this batch score `needs_review` and none
> reaches `auto_accepted`. `check_ve_ie_batch.py` asserts this as a hard failure rather than the
> warning it used to print. The section below is kept as the record of why the card was raised.

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

## Promotion — 2026-08-21 (AIQ-2027 go-live)

All 9 rows were promoted into `public.requirement_items` on 2026-08-21, taking **IRELAND to
20 approved + 9 pending = 29**; the original 20 were not touched. They landed
`review_status='pending'` / `verification_status='representative'` / `purpose='employment'`, so
`crud.list_requirements` — the single publication gate — withheld all 9 from both readers.

**That is the state at load time, and it lasted about two and a half hours.** All nine were
approved at 12:02 UTC the same day and are now served; see *approved and serving* below. The rest
of this section describes the promotion itself, which is what it was reviewing.

Two gates had to be opened by hand, each previewed and asserted inside a transaction:

**The `new` → `ready` flip.** `promote()` reads only `status='ready'` (`executor.py:369`) and
`stage()` writes `'new'` (`executor.py:68`); nothing in the codebase flips it. That is the
deliberate "a person must move it" gate described above, and it was opened explicitly for this
load rather than automated.

**`purpose` would have been `other`, not `employment`.** `mappings.py:176` resolves
`PURPOSES.get(status or "", "other")`, and the converter carries no `applies_to.status` — so the
batch fell into the importer's uncategorised default. Meanwhile `public_corridor.py:135` defaults
`purpose='employment'`, `crud.list_requirements` filters on it, and all 20 existing IRELAND rows
are `employment`. Promoting as-is would have produced nine rows that every count check reports as
loaded and that the corridor endpoint can never return — the orphaned-`purpose` artifact, and a
silent one. `applies_to.status='professional'` was set on the 9 staged rows before promoting.
That is a **derivation, not an invention**: the manifest scopes the batch to the third-country
*employment-permit* path, and the family rows are family requirements *within* an employment
relocation — the same bucket the existing "Bringing a pet from Spain to Ireland" and "Dublin
rental market" rows already occupy.

**Why the staged rows had to be patched even though the converter was fixed.** #1941 (AIQ-2035)
taught `convert_ve_ie_to_otto_jsonl.py` to emit `"status": "professional"` and to assert it in
`check()`. But `promote()` reads `applies_to` from the **staged rows in the database**, not from
the JSONL — and those rows were written on 2026-08-20 by #1934, before that fix. Regenerating the
file would not have touched them. So the converter fix protects future batches; this batch's
already-staged rows needed the patch.

The promote-side fallback is unchanged: `mappings.py:218` still resolves
`PURPOSES.get(status or "", "other")`. Its sibling key `applies_to.nationality` refuses loudly
(`Unmapped`) when absent; a missing `status` still yields a plausible-looking row instead. Worth
considering whether that should be `Unmapped` too — a converter fix stops the batch that is
already known about, not the next one nobody has written yet.

## 2026-08-21 — approved and serving

All nine rows were approved at **12:02:59 UTC** by `admin@relopass.com`, in a single scripted
call through the review API, and are now served to employees, HR and the unauthenticated public
corridor endpoint. `IRELAND` reads 29 approved, 0 pending.

**That includes the four rows below, which counsel has not cleared**, and it happened while all
nine still carried `quote_verbatim_confirmed: false` — every evidence quote was captured and
never re-checked against its page. Recorded here because the batch doc is the place someone will
look to find out what state this content is in, and "approved" now means "live", not "reviewed".

Two consequences followed immediately, both traceable to the approval rather than to the load:

- **`needs_lawyer_review` became public.** `public_corridor.py` emitted `citations_json` raw on an
  endpoint that is unauthenticated and answers `Access-Control-Allow-Origin: *`, so the internal
  counsel flag appeared in the live body on four requirements. Fixed by an allowlist — the public
  `source` array now carries URLs and nothing else.
- **The machine titles went live.** Real users are now served headings like
  *"Ireland — dependant join family d visa required"*, because `entity_title` was derived as
  `"Ireland — " + topic_key` with underscores spaced. A rewrite was prepared and **not applied**:
  `executor.promote()` derives the row id as `uuid5(_SEED_NS, 'IRELAND|employment|<title>')`, so
  changing a title means re-keying, and re-keying an *approved* row risks orphaning
  `case_requirement_checklist_state` (TEXT, no FK) and breaking the `corridor_attestation_items`
  FK (no `ON UPDATE CASCADE`). That window was open while the rows were pending and closed when
  they were approved. Reopening it means withholding the rows first — a decision, not a cleanup.

### ⚠ The content is origin-specific; the serving is not

`requirement_items` is keyed on destination + nationality class only — there is no origin column.
These rows say *"A **Venezuelan** national is visa-required"* and *"A **Spanish** residence card /
TIE"* in their `fact_text`, and they are now served to **every** third-country national moving to
Ireland, including someone relocating from Berlin.

Not introduced by this batch: the approved row *"Bringing a pet from **Spain** to Ireland"* has
exactly the same shape. It is a catalog-wide modelling gap and wants its own card.

## The four rows counsel must clear before any approval

| `fact_uid` | Claim |
|---|---|
| `…:spanish_residence_does_not_grant_irish_entry` | A Spanish residence card does not grant entry to Ireland (non-Schengen) |
| `…:csep_immediate_family_reunification` | CSEP allows immediate family reunification; GEP restricts it for 12 months |
| `…:spouse_stamp_1g_right_to_work` | CSEP spouse gets Stamp 1G with employment access |
| `…:dependant_join_family_d_visa_required` | Dependants need their own Join Family 'D' visa |

All nine are `verification_status='representative'`. They were `review_status='pending'` when this was written and were approved at 2026-08-21 12:02 UTC — including these four, which is the reason the *approved and serving* section below exists.

## Reproducing

```bash
./.venv311/bin/python scripts/check_ve_ie_batch.py                  # integrity + counts + reader
./.venv311/bin/python scripts/convert_ve_ie_to_otto_jsonl.py        # regenerate the JSONL
./.venv311/bin/python scripts/import_otto_facts.py \
    ve-ie-entry-family-2026-08-20 --expected 9                      # dry run (default)
RELOPASS_QUERY_COUNTER_OFF=1 DATABASE_URL="sqlite:///./ci_test.db" \
    ./.venv311/bin/python -m pytest backend/tests/test_ve_ie_corridor_facts_conversion.py -q
```

To actually stage, add `--apply`.

**Rollback.** Staging: delete the batch's rows by `batch_id` from
`otto_staging.immigration_fact_candidates` (plus the matching `immigration_entities` /
`load_log` rows). The promoted rows are separate — they live in `public.requirement_items`.
Select them by the nine canonical ids that check 7 re-derives, **not** by
`review_status='pending'`: every one of them was approved on 2026-08-21 12:02 UTC, so that
predicate now matches nothing here and would read as "already rolled back".

## Closure verification (AIQ-2027)

`scripts/verify_aiq_2027_ve_ie_load.py` gates the *landing*, where `check_ve_ie_batch.py`
gates the *artifact*. Offline it re-hashes the NDJSON against a pinned sha256, asserts nine
facts with zero shape errors, asserts every `review_status='pending'` and every
`quote_verbatim_confirmed=false`, and pins the four counsel-flagged topic keys **by name**
rather than by count — a count still passes if a flag drifts from the load-bearing
`spanish_residence_does_not_grant_irish_entry` onto a routine fact. With `--db-url` it adds a
read-only reconciliation: all nine rows present, `purpose='employment'`, counsel flag and
`topic_key` intact, and no duplicate beside any canonical id.

```bash
./.venv311/bin/python scripts/verify_aiq_2027_ve_ie_load.py                    # CI-safe, no DB
./.venv311/bin/python scripts/verify_aiq_2027_ve_ie_load.py --db-url "$URL"    # + reconciliation
RELOPASS_QUERY_COUNTER_OFF=1 DATABASE_URL="sqlite:///./ci_test.db" \
    ./.venv311/bin/python -m pytest scripts/tests/test_verify_aiq_2027.py -q
```

### Why there is no AIQ-2027 migration

The card asked for nine `INSERT`s into `public.requirement_items` keyed on the artifact's
`fact_uid` with `ON CONFLICT (id) DO NOTHING`. That contract does not hold against this table
and the migration was not written.

The load path is `promote()`, which writes through `crud.create_requirement_item` — an upsert
on the natural key `(country_code, purpose, title)` whose primary key is
`uuid5(_SEED_NS, "country|purpose|title")`, deliberately the same namespace
`seed_requirements.py` uses so a promoted row and a later YAML re-seed converge on one row.
Prod holds these nine under ids like `a179d689-f19a-5f2f-8f20-e979cf82db88`; **zero** rows in
the table are keyed by `fact_uid`. An `INSERT ... ON CONFLICT (id) DO NOTHING` keyed on
`ES_IE:THIRD_COUNTRY:<topic_key>` therefore conflicts with nothing: it fires zero times and
inserts nine duplicates beside the nine already live, taking IRELAND to 38 rows with each of
these facts twice in the reviewer queue and twice in the corridor call.

The idempotency claim is instead evidenced where it actually lives. Check 7 re-derives all
nine ids through the real converter → reader → mappings path and asserts they equal the ids
prod holds; equal ids mean a re-run upserts the same nine rows. `test_verify_aiq_2027.py`
proves the gate discriminates, and the `fact_uid`-keying bug above was itself run against the
live table — it reports all nine as duplicated, which is the outcome the migration would have
produced.

Two things worth knowing before touching this batch again:

- Three facts (`csep_immediate_family_reunification`, `spouse_stamp_1g_right_to_work`,
  `dependant_join_family_d_visa_required`) are authored `domain_area='family'`.
  `mappings.resolve` returns `Unmapped` for any value other than `'immigration'`, so they
  promote **only** because staging normalises them. Were that to stop, these three would
  silently fail to promote while the other six succeeded. Check 6b pins the set.
- The duplicate check matches on `topic_key`. An earlier revision matched a `batch_id` marker
  in `citations_json` — a column that carries no `batch_id` at all, so it reported "no
  duplicates" against a table it had never actually interrogated.
