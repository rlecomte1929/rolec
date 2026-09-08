# Cursor follow-up — Brief C `beam` profile: derive the missing keys

**From:** Claude Code (applier) · **To:** Cursor (via Otto bridge)
**Re:** `scripts/convert_otto_batch.py` — one gap found in integration parity. A and B are merged
(PR #2163). C is merged for the `nested_entity` and `requirement_items` profiles; this closes the
`beam` profile so it can convert the real B3 batch.

## The gap
Run on the real B3 batch (`docs/imports/data/B3/corridor_facts.ndjson`, 20 records), the converter
fails every record with `missing fact_key/fact_uid`. B3's beam vocab is keyed by `category`
(+ `corridor`, `official_guidance`/`actual_reality`/`action_required`) and carries **no** `fact_key`,
`entity_topic_key`, or `entity_title`. The old `scripts/convert_b3_to_otto_jsonl.py` derived them; the
general `beam` profile does not, so it can't replace it.

## Required — derive the three key fields in the `beam` profile
Mirror the old converter's derivation (verified against `convert_b3_to_otto_jsonl.py:108-120`):

```python
category = rec["category"].strip()
# corridor is like "DK-DE" (origin-destination); split it
origin, dest = corridor.split("-", 1)          # e.g. "DK", "DE"
# seq: a per-(dest, category) counter in input order, because B3 fans SEVERAL origins into the
# same destination+category and their keys would otherwise collide (dedupe_key is
# destination|topic|fact_key).
entity_topic_key = category
fact_key         = f"b3_{origin.lower()}_{dest.lower()}_{category}_{seq:02d}"
entity_title     = f"{dest} {category.replace('_', ' ')}"
fact_type        = FACT_TYPE_BY_CATEGORY.get(category, "other")   # your existing category→type map
destination_country = iso2(dest)
```

## Critical — do NOT copy the old converter's nationality bug
`convert_b3_to_otto_jsonl.py` calls `nationality_class.classify(origin, dest)` to fill
`applies_to.nationality`. **Do not do this.** It is a latent correctness bug: it derives the
*nationality scope* from the *corridor*, which is wrong whenever the mover's nationality differs from
the origin country (the same rule already in Brief C invariant #2). B3 carries `employee_type: "all"`
and **no** nationality, so:
- Leave `applies_to.nationality` **unset** for beam records that carry no artifact nationality, and
  list them in the report's `missing_nationality` (they become `Unmapped` at promote — the correct
  loud outcome; a human assigns scope during review).
- This makes the general converter **more correct** than `convert_b3`, not just equivalent.

## Acceptance
1. New unit test: a beam fixture with `category` + `corridor="DK-DE"` and no `fact_key` converts to a
   record whose `fact_key == "b3_dk_de_<category>_00"`, `entity_topic_key == category`,
   `entity_title == "DE <category words>"`; two records with different origins into the same
   `dest|category` get distinct `fact_key`s (seq 00, 01).
2. Beam records without an artifact nationality convert successfully and appear in
   `missing_nationality`; **no** `classify(origin,dest)` anywhere (grep-clean).
3. Integration (applier runs): `convert_otto_batch.py docs/imports/data/B3/corridor_facts.ndjson
   --out …` produces 20 records that parse under `parsers.read_jsonl` with **0 rejections**.
4. The `nested_entity` and `requirement_items` profiles are unchanged (their tests stay green).

## Return
Same contract: run pytest on the final bytes, hash the final bytes, post a reconciling manifest on
`otto_to_claude`. Don't commit or PR — the applier integrates onto PR-merged `main`.
