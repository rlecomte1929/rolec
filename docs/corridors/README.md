# Corridor index

A corridor is `country-pair × employee-type × current requirements`. Two things make one
real, and they live in different places:

| what | where |
|---|---|
| Registry profile + pathway step graph | `corridors/<ID>/corridor.yaml`, `corridors/<ID>/pathways/<PATHWAY>/v1.yaml` |
| Requirement records (the served facts) | `public.requirement_items`, loaded by a `supabase/migrations/` file |
| Documentation, metrics, validation, CVR | `docs/corridors/<id>/` |

Ten corridor profiles exist under `corridors/`: `DE_NO`, `ES_IE`, `ES_NL`, `FR_CH`, `FR_DE`,
`FR_ES`, `FR_NL`, `FR_NO`, `IE_ES`, `IN_DE`, `NO_FR`. A profile is not the same as a served
corridor — most have no requirement records behind them yet.

## Documented corridors

| corridor | records | served? | CVR | docs |
|---|---|---|---|---|
| IE→ES (Dublin→Madrid) | 25 (15 non-obvious, 2 need counsel) | **no** — all `pending`, migration not applied | none | [`ie-es/`](ie-es/README.md) |

## Conventions worth knowing before adding one

**Pick the structural mirror, not the reverse corridor.** IE→ES mirrors `FR_ES`
(EU free movement into Spain), not `ES_IE` — the reverse corridor models a third-country
national on an employment permit and its salary floors and visa gates do not apply to a free
mover. Match the *legal shape*, not the country pair.

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
