# ES→IE third-country batch — promotion DRY RUN

**Batch:** `es-ie-thirdcountry-requirements-2026-08-22` · 38 facts, 6 entities
**Artifact:** `docs/imports/es-ie-thirdcountry-requirements-2026-08-22/es_ie_thirdcountry_requirements.ndjson`
**Generator:** `scripts/plan_es_ie_promotion.py` (dry run only — the file contains no execute path)
**Prod state measured:** 2026-08-22, project `nsvefcvpvwwwhuqyuqmp`
**Status: NOT EXECUTED.** This is the artifact to approve at the gate.

## Three corrections to the task spec, before the numbers

**1. The target table is `requirement_facts`, not `requirement_items`.** Two requirement
pipelines exist and they do not meet. `backend/imports/otto/executor.promote()` — the
`--promote` tooling — writes `public.requirement_items`, which feeds the public corridor
endpoint and the rules engine. The path this batch has to reach is the other one:
`compute_requirements_sufficiency` reads `requirement_facts JOIN requirement_entities`
(`backend/db/policies.py::list_approved_requirement_facts`), and that is what renders in the
employee dossier. **The existing promotion tooling does not serve this batch.**

**2. The dedupe key `(country_code, purpose, title)` does not exist on this table.** Those are
`requirement_items` columns. `requirement_facts` has `entity_id`, `fact_type`, `fact_key`,
`fact_text`, `applies_to`, `source_url`, `evidence_quote`, `confidence`, `status` — and no
`country_code`, `purpose`, `title` or `pillar`. The batch's `pillar` rides inside `applies_to`.

**3. The PR #1973 pillar dependency does not apply, and is in any case satisfied.** #1973 is
merged but its merge commit is *not* an ancestor of `origin/main` — it landed on a branch that
had already merged away, and #1983 re-landed the content. `resolve_pillar` is present on main.
It governs the `requirement_items` path only, so it does not gate this promotion either way.

## What the promotion would insert

| Table | Rows | Note |
|---|---:|---|
| `requirement_entities` | 6 | none exist today — all 6 topics are namespaced `ES-IE:thirdcountry:*` |
| `knowledge_docs` | 8 | 2 of the 10 source URLs already have a doc; 8 do not |
| `requirement_facts` | 38 | **0 collide** with any existing IE `fact_key` |

Entities, by fact count: `isd_irp_registration` 11 · `immigration_work_authorization` 9 ·
`revenue_rpn_emergency_tax` 7 · `ppsn` 5 · `health_entitlements` 3 · `taxation` 3.

Every fact is written `status = 'pending'` **explicitly**. `list_approved_requirement_facts`
serves only `status = 'approved'`, so pending *is* the gate — nothing in this batch reaches a
mover until a human flips it.

Every fact is written `evidence_verified = NULL` — never `TRUE`. NULL means "never checked",
and the dossier renders that as *"Source — not independently verified"*. Writing `TRUE` would
claim a check nobody performed.

## Idempotency: why there is no `ON CONFLICT`

`requirement_facts` and `requirement_entities` each carry a PRIMARY KEY on a
`gen_random_uuid()` `id` and **no other unique constraint** (verified against production).
There is nothing for `ON CONFLICT` to match on, so a naive re-run would insert all 38 rows a
second time, silently.

Idempotency therefore comes from a **deterministic id**: `uuid5` over the natural key
(`fact:{dest}:{topic_key}:{fact_key}`). Re-running produces the same primary key, so the second
insert is refused rather than duplicated. Verified: two runs of the generator are byte-identical,
and none of the 38 derived fact ids or 6 entity ids collide with a row in production.

## Rows the promotion must NOT touch

25 IE facts carry a `reviewed_by` — a human decision already recorded:

| status | reviewed rows |
|---|---:|
| `approved` | 14 |
| `pending` | 11 |

The plan is **insert-only with deterministic keys**, so it issues no `UPDATE` at all and cannot
overwrite a reviewer's decision. This is a property of the plan, not a promise to be careful.

## What still has to be decided before this runs

1. **The 8 missing `knowledge_docs`.** `source_doc_id` is NOT NULL. The known-bad pattern here
   is a placeholder doc: production already holds 222 `knowledge_docs` whose entire
   `text_content` is *"Otto bridge capture, unverified — see source_url"*, carrying 705 facts
   whose quotes are not substrings of it. Fetch the real page text, or leave the batch staged.
   One of the 2 *existing* docs is already bad — the `enterprise.gov.ie` doc's text is a cookie
   banner, so its quote can never verify.
2. **The 6 `needs_lawyer_review` rows** named in the launch pack's gate list.
3. **Approval is a second, separate step.** Inserting at `pending` serves nobody; a human flip
   to `approved` is what puts these in front of Andrea.
