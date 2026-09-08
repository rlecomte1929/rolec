# AIQ-2150 — premise refuted: `required_fields` drop is real, but not on the pipeline the task names

**Task:** [required_fields is silently dropped at import, so a promoted fact arrives with no intake gaps](https://app.notion.com/p/3c5887c64d4881a48681e2fa0e869997)
**Date:** 2026-09-08 · **Method:** relopass-dev-queue Phase 2.5 (falsify the premise) · **Verdict:** PREMISE — Refuted (partial: mechanism real, effect/consumer wrong, scope insufficient)

## The claim

> `required_fields` is what `compute_requirements_sufficiency` turns into the dossier's "Details
> we still need from you". Dropped at import, that half of the panel is empty for every promoted
> fact.

- **Files to Touch:** `backend/imports/otto/parsers.py`, `backend/imports/otto/executor.py`
- **Validation Criteria:** "A batch carrying `required_fields` promotes with them intact, and the
  dossier's gaps section is non-empty for a case missing one of those fields."

## What is true

`read_jsonl` / `_to_row` in `backend/imports/otto/parsers.py` **does** silently drop
`required_fields`. It is in neither `REQUIRED_FIELDS` (parsers.py:51) nor `OPTIONAL_FIELDS`
(parsers.py:60), and `FactRow` (parsers.py:207) has no such attribute, so `_to_row` never reads
it. That half of the Technical Constraints is accurate.

## Why the premise is refuted

### 1. The dossier reads a different table than the Otto importer writes (disjoint pipelines)

The dossier "Details we still need" panel is built by `compute_requirements_sufficiency`
(`backend/app/services/requirements_sufficiency.py:100,118`), which reads its facts from
`RelopassDB.list_approved_requirement_facts` — and that query is:

```sql
-- backend/db/policies.py:1438
SELECT f.* FROM requirement_facts f
JOIN requirement_entities e ON e.id = f.entity_id
WHERE e.destination_country = :dest AND f.status = 'approved'
  AND COALESCE(f.evidence_verified, TRUE) = TRUE
```

`missing_fields` is derived **only** from `requirement_facts.required_fields`.

The Otto import path named in *Files to Touch* does not write `requirement_facts`. `promote()`
(`backend/imports/otto/executor.py:402`) writes `public.requirement_items` via
`crud.create_requirement_item`, and the payload builder `mappings.resolve` **hardcodes** the
value:

```python
# backend/imports/otto/mappings.py:421
"required_fields_json": "[]",
```

`requirement_facts` is populated by a *different* importer,
`backend/imports/immigration/executor.py:107` (`INSERT INTO requirement_facts (… required_fields …)`),
which already carries the field. **No change to `parsers.py` + `executor.py` can make the dossier
panel non-empty** — it targets `requirement_items`, which the dossier never reads. The Validation
Criterion is therefore unsatisfiable as written.

(This split is a known one: the promote tooling feeds `requirement_items`; the dossier reads
`requirement_facts`.)

### 2. "Carry through staging" requires a migration not in scope

The staging table has no column to carry the field:

```sql
-- supabase/migrations/20260811221900_otto_staging_schema.sql:35
CREATE TABLE IF NOT EXISTS otto_staging.immigration_fact_candidates (
  id uuid …, destination_country text, entity_topic_key text, fact_type text, fact_key text,
  fact_text text, applies_to jsonb, source_url text, evidence_quote text, confidence text,
  confidence_score numeric, accuracy_tier text, extraction_method text, batch_id text,
  dedupe_key text, status text, created_at timestamptz );   -- no required_fields column
```

Carrying `required_fields` through staging needs an `ALTER TABLE` migration — outside the task's
Files to Touch, and an always-split (migration ships alone).

### 3. The cited evidence batch is inert

The ES→IE batch the task names carries `required_fields` on all 38 records, but **every value is
`[]`** — in both the raw and flattened files:

```
docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson
  → required_fields value distribution: {'[]': 38}
docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.flat.ndjson
  → required_fields value distribution: {'[]': 38}
```

Even a perfect parser+staging+promote fix would promote zero intake gaps from this batch.

## Corrected diagnosis

The Otto importer feeds the **corridor / roadmap** requirements builder
(`requirement_items.required_fields_json`, read at `requirements_builder.py:307` and
`public_corridor.py:140`) — **not** the dossier. There *is* a genuine latent bug on that surface:
the parser drops `required_fields` and `mappings.resolve` hardcodes `"[]"`, so every Otto-promoted
requirement has empty `required_fields_json`. But fixing it (a) needs the staging migration in §2
and (b) still would not touch the dossier panel this task is about. The dossier's own importer
(`backend/imports/immigration/executor.py`) already carries `required_fields`.

## Recommendation

Close AIQ-2150 as premise-refuted. If the corridor/roadmap gap is worth pursuing, open a new,
correctly-scoped card:

> **Otto promote drops `required_fields` into `requirement_items.required_fields_json` (corridor/roadmap)**
> - parser: add `required_fields` to `OPTIONAL_FIELDS` + `FactRow` + `_to_row`
> - staging: **migration** adding `required_fields jsonb` to `otto_staging.immigration_fact_candidates`, plus the `_INSERT_FACT` column
> - promote: replace the hardcoded `"required_fields_json": "[]"` in `mappings.resolve` with the facts' aggregated `required_fields`
> - validation stated against `requirement_items` / the requirements builder — **not** the dossier
> - note the ES→IE batch carries only empty `required_fields`; a real fixture batch is needed to prove non-empty output

## Reproduction

```bash
# §3 — the batch carries only empty required_fields
python3 - <<'PY'
import json, collections
for name in ("es_ie_thirdcountry_requirements.ndjson","es_ie_thirdcountry_requirements.flat.ndjson"):
    p=f"docs/imports/es-ie-thirdcountry-requirements-2026-08-22/{name}"
    recs=[json.loads(l) for l in open(p) if l.strip()]
    print(name, collections.Counter(json.dumps(r.get("required_fields")) for r in recs))
PY

# §1/§2 — the code facts
grep -n "required_fields" backend/imports/otto/parsers.py            # absent from field tuples + FactRow
grep -n "required_fields_json" backend/imports/otto/mappings.py      # hardcoded "[]" at :421
grep -n "requirement_facts f"  backend/db/policies.py                # dossier reads requirement_facts, not requirement_items
grep -n "required_fields" supabase/migrations/20260811221900_otto_staging_schema.sql  # no column
```

PREMISE: Refuted   DUPLICATE: no   OUTCOME: docs
