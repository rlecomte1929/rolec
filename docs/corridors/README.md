# Corridor index

A corridor is `country-pair × employee-type × current requirements`. Two things make one
real, and they live in different places:

| what | where |
|---|---|
| Registry profile + pathway step graph | `corridors/<ID>/corridor.yaml`, `corridors/<ID>/pathways/<PATHWAY>/v1.yaml` |
| Requirement records (the served facts) | `public.requirement_items` — several loaders write it, see [`DATA-PATHS.md`](DATA-PATHS.md) |
| Documentation, metrics, validation, CVR | `docs/corridors/<id>/` |

Thirteen corridor profiles exist under `corridors/` (see `corridor_registry.list_corridors()`).
A profile is not the same as a served corridor — most have no requirement records behind them yet.

## Demand-pull: no corridor without a real case

Do not pre-create empty `requirement_items` for an unverified pair. The registry lives in git
(`corridors/<ID>/corridor.yaml`), not a DB table, so a fictional `anchor_case_id NOT NULL`
would not stop a load.

**New** `corridors/*/corridor.yaml` files must declare an `anchor` naming a real case.
Existing profiles are grandfathered (`scripts/check_corridor_anchor.py`). Served facts still
fail closed: `requirements_builder` reads only `review_status = 'approved'`.

```yaml
corridor:
  id: "XX_YY"
  origin_iso: "XX"
  destination_iso: "YY"
  display_name: "Origin → Destination"
  anchor:
    case_id: "<relocation_cases.id>"   # and/or
    case_ref: "Named case + corridor + year"
    note: "Why this pair exists"         # optional
```

See [`backend/docs/adr-003-access-pattern-structures.md`](../../backend/docs/adr-003-access-pattern-structures.md).

## Documented corridors

| corridor | records | served? | CVR | docs |
|---|---|---|---|---|
| IE→ES (Dublin→Madrid) | 25 (15 non-obvious, 2 need counsel) | **no** — all `pending`, migration not applied | none | [`ie-es/`](ie-es/README.md) |
| FR→NO (knowledge-layer golden) | in-repo seed scored pending-only | **no** — 0 approved | QBR stub | [`fr-no/QBR-knowledge-layer.md`](fr-no/QBR-knowledge-layer.md) |

## Conventions worth knowing before adding one

**Name the anchoring case.** A new `corridor.yaml` without `anchor.case_id` or
`anchor.case_ref` fails `scripts/check_corridor_anchor.py`. Do not expand that script's
grandfather set to dodge it.

**Know which loader you are.** A generated migration with `ON CONFLICT (id)` is one of
several paths into `requirement_items`, and it is the only one that sets `id` itself; the
others upsert on `(country_code, purpose, title)` through `crud.create_requirement_item`.
The two cannot see each other's rows, because there is no unique index on that natural key.
[`DATA-PATHS.md`](DATA-PATHS.md) maps all of them and recommends a fix.


**Pick the structural mirror, not the reverse corridor.** IE→ES mirrors `FR_ES`
(EU free movement into Spain), not `ES_IE` — the reverse corridor models a third-country
national on an employment permit and its salary floors and visa gates do not apply to a free
mover. Match the *legal shape*, not the country pair.

**Writers target `requirement_items`, not `requirement_facts` and not imaginary `kg_*` tables.**
`requirement_facts` is a parallel evidence shape used by some HR/sufficiency reads; new Otto
and corridor loads promote into `requirement_items` with `review_status='pending'`.

**`requirement_items.review_status` defaults to `'approved'`.** `requirements_builder`
serves only approved rows, so a load that omits the column publishes unreviewed facts to real
users the moment it applies. Set it to `'pending'` explicitly, and never let an `ON CONFLICT`
update overwrite it — re-running a load must not un-approve what a reviewer approved.

**The manifest may name a table that cannot hold the data.** Verify the live schema before
writing SQL. The IE→ES batch named `requirement_facts`, which has no `fact_uid` and two NOT
NULL uuid FKs the NDJSON cannot supply; the load targets `requirement_items` instead, whose
varchar `id` carries the `fact_uid` verbatim.

**Generate the SQL, don't type it.** `scripts/gen_ie_es_corridor_load.py` re-verifies the
data's sha256 against its manifest, runs the gates, and derives the migration. A hand-edited
load drifts from the artifact it claims to represent.

**Prove idempotency against real Postgres.** SQLite cannot stand in for `ON CONFLICT` with a
real unique index. Apply the migration twice inside `BEGIN…ROLLBACK` and assert the row count
did not double.

**Nationality NULL is not an importer default.** Six approved Irish payroll/tax rows are
NULL on `applies_to_nationality_classes_json` because they are universal statutory
obligations. Immigration pathways must stay class-scoped. Decision record:
[`ie-nationality-scope.md`](ie-nationality-scope.md).
