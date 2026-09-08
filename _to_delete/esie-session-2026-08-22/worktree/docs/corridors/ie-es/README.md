# IE→ES — Ireland → Spain (Dublin → Madrid)

**Status:** data landed, load written, **not yet applied to production, no CVR completed.**
Requirements are `review_status='pending'` and are therefore **not served**.

| | |
|---|---|
| Corridor id | `IE_ES` (registry), `IE-ES` (batch/alias) |
| Records | 25, all source-attributed |
| Non-obvious | 15 |
| Needs lawyer review | 2 |
| Data | `corridors/IE_ES/data/ie_es_requirement_facts.ndjson` (sha256-pinned) |
| Load | `supabase/migrations/20261108000000_ie_es_requirement_items.sql` |
| Generator | `scripts/gen_ie_es_corridor_load.py` |
| Validation report | `corridors/IE_ES/data/validation_report.json` |
| Tests | `backend/tests/test_corridor_ie_es.py` (25) |

---

## Goal

An Irish national moving to Madrid needs no visa and no permit — which is exactly why the
corridor is dangerous. There is no gate to fail, so nothing forces the sequence, and the
requirements interlock in ways neither government website mentions. The relief moment this
corridor must deliver is the **dependency chain**, in week 1 rather than week 7:

> You cannot get the certificado de registro without a padrón certificate; you struggle to
> get on the padrón without an address; and landlords want a NIE before they will sign a
> lease. Meanwhile the Beckham election expires six months after your Social Security alta,
> silently.

That circularity is the single most-reported IE→ES surprise, and it is carried as a
`non_obvious` record (`housing_nie_needed_to_rent`) and modelled as a real edge in the
pathway step graph.

## Spec

**Record schema** (one JSON object per NDJSON line):

`fact_uid` · `topic_key` · `domain_area` · `corridor` · `origin_country_code` ·
`destination_country_code` · `fact_text` · `source_url` · `source_name` · `non_obvious` ·
`non_obvious_note`

**Upsert key:** `fact_uid`, format `ES:IE-ES:<topic_key>`.

**The 25 records by domain**

| domain | n | covers |
|---|---|---|
| registration | 8 | certificado de registro UE (EX-18 + tasa 790-012), NIE, means test, cita previa, padrón ×3 |
| tax | 4 | IRPF 183-day residency, Modelo 030, Beckham regime (Modelo 149), IE–ES treaty tie-breaker |
| social_security | 4 | single-state rule, A1 posted worker, NUSS afiliación, employer alta |
| healthcare | 3 | SNS/TSI, TSI requirements, EHIC transition |
| housing | 3 | LAU fianza, regional deposit variation, NIE-needed-to-rent |
| immigration | 1 | TIE applies only to non-EU nationals |
| other | 2 | EU licence validity, DGT registration |

**Source policy.** Every record carries a `source_url` to an official publisher (AEAT,
Seguridad Social, Extranjería, DGT, municipal padrón pages). A requirement decides whether
someone legally has the right to work; one without a source is not a requirement.

**Where it lands, and why not where the manifest said.** The batch manifest names
`requirement_facts` keyed on `fact_uid`. Production's `requirement_facts` has **no
`fact_uid`**, no corridor/topic/domain columns, and two NOT NULL uuid foreign keys
(`entity_id`, `source_doc_id`) the NDJSON cannot supply — that upsert is not expressible.
The load targets **`public.requirement_items`**, whose `id` is `varchar` and therefore holds
the `fact_uid` verbatim, so the upsert key is preserved exactly. It is also the table
`requirements_builder` actually reads, so this is the only landing that makes the corridor
servable. SPAIN held **0** rows before this batch; the load is purely additive.

**Field mapping**

| NDJSON | requirement_items | note |
|---|---|---|
| `fact_uid` | `id` | the upsert key, verbatim |
| `destination_country_code` | `country_code` = `SPAIN` | catalog key, not ISO |
| `domain_area` | `pillar` | there is no TAX pillar → tax maps to `EMPLOYMENT` |
| `fact_text` (+ note) | `description` | the non-obvious note is appended so it reaches the user |
| `source_url`/`source_name` | `citations_json` | plus corridor, topic, domain, review flags |
| `non_obvious` | `non_obvious` | native column |
| — | `review_status` = `pending` | **explicit**; see below |
| — | `verification_status` = `representative` | not SME-verified |

`registration_nie_number` overrides to `IDENTITY` — a NIE is an identity number, not a
residence step. Registration and immigration records are scoped
`applies_to_nationality_classes_json = ["EU_EEA"]`: a returning Spanish national holds a DNI
and cannot be issued a certificado de registro, so serving them one would be wrong. Housing,
healthcare, tax and driving are left unscoped rather than narrowed on a guess.

## Plan — how the data got here

LLM candidate generation → human + source verification → committed artifact → deterministic
serving. The generation step happened outside this repo (Otto batch, `generated_by:
otto-sub_otto`, 2026-08-18); what is committed here is the verified output, pinned by
sha256.

`scripts/gen_ie_es_corridor_load.py` reads the NDJSON, re-verifies the hash against
`manifest.json`, runs the gates, and **derives** the migration SQL. The SQL is generated,
never hand-edited — if the data changes, regenerate.

**`review_status='pending'` is deliberate and load-bearing.** The column defaults to
`'approved'` and `requirements_builder` serves only approved rows, so an INSERT that omitted
it would publish 25 unreviewed REPRESENTATIVE facts to real users the moment it applied. The
`ON CONFLICT` update also never touches `review_status` — re-running a load must not
un-approve what a reviewer has since approved.

## Metrics

**Non-obvious hit rate — the moat metric.** 15 of 25 records are things an HR generalist
would not know to look for. Each carries a `non_obvious_note`, and the note is appended to
the served `description` ("Why this is easy to miss: …") so it is visible in the roadmap and
therefore measurable.

| topic | domain |
|---|---|
| `registration_certificado_registro_ue` | registration |
| `registration_nie_number` | registration |
| `registration_cita_previa_bottleneck` | registration |
| `registration_tie_only_for_non_eu` | immigration |
| `empadronamiento_dependency_chain` | registration |
| `tax_residency_183_days` | tax |
| `tax_beckham_regime` | tax |
| `tax_ie_es_double_taxation` | tax |
| `social_security_a1_posted_worker` | social_security |
| `social_security_nuss_afiliacion` | social_security |
| `healthcare_tsi_requirements` | healthcare |
| `healthcare_ehic_transition` | healthcare |
| `housing_fianza_regional_deposit` | housing |
| `housing_nie_needed_to_rent` | housing |
| `driving_dgt_registration` | other |

**Relief-moment metric.** After the roadmap renders the user is asked "Was there anything in
this roadmap you didn't already know about?" and the answer is logged to PostHog as
`relief_moment_response` (`corridor`, `employee_type`, `response`, `open_text`, `case_id`,
`timestamp`). This corridor introduces no new analytics pipeline. **Open item:** confirm
`corridor` flows through as `IE-ES` and is not hardcoded to another corridor — not verified
as part of this batch.

## Validation

Ten gates, all passing. The machine-readable result is
`corridors/IE_ES/data/validation_report.json`, regenerated by the generator and committed as
the corridor's proof-of-verification artifact.

| gate | result |
|---|---|
| sha256 vs manifest | PASS — `ba53fd12…10de1` |
| structural (source, text, enum, corridor, uid format) | PASS — 25/25 |
| fact_uid unique | PASS — 25 of 25 |
| count | PASS — 25 |
| domain profile | PASS — 8/4/4/3/3/1/2 |
| non_obvious count | PASS — 15 |
| non_obvious note present | PASS — 15/15 |
| trust / lawyer review | PASS — 2 flagged |
| serving status | PASS — all `pending`, none served |
| idempotency | PASS — applied **twice** in `BEGIN…ROLLBACK` against production: **25 rows, not 50** |

The idempotency gate was proven with `psql` against production inside a rollback
transaction, because it needs a real `ON CONFLICT` and a real unique index that SQLite
cannot stand in for. The same run confirmed 25 pending / 15 non-obvious / 2 lawyer-flagged /
6 distinct pillars, then rolled back.

### The two flagged records

`tax_residency_183_days` and `tax_ie_es_double_taxation` both make a claim about the
**Ireland–Spain double taxation treaty tie-breaker** while citing the **AEAT residency
page**, not the treaty text. They are carried with `needs_lawyer_review: true` in
`citations_json` (the table has no dedicated column) together with the reason. This is not a
defect to be tidied away — it is the verification gate staying honest about a claim that
outruns its source. They must not be approved until counsel closes the gap.

## Eval

**Case Verification Report (CVR).** Each corridor is validated by a real-user session whose
output is both a validation artifact and future fine-tuning training data. ES→IE has
`andrea-es-ie`. **IE→ES has no CVR yet** — the template stub is `CVR-TEMPLATE.md` in this
directory.

**Readiness gate — IE→ES is not ready to serve.** Three things stand between here and a
served corridor:

1. The migration is written but **not applied** to production.
2. All 25 rows are `pending`; a human must approve them.
3. The 2 treaty records need counsel before they can be approved at all.

Until those close, opening an IE→ES case returns the corridor profile and pathway, and no
requirement rows. That is the correct behaviour: an unreviewed fact not being served is the
system working.

## Also

The registry entry mirrors **`FR_ES` / `ES_FREEMOVE_2026`**, not `ES_IE`. The reverse
corridor models a third-country national on an Irish employment permit — salary floors,
permit windows, a visa gate. An Irish national moving to Spain is an EU free mover with none
of those. FR_ES already models free movement into the same destination, so it is the
structural template; copying ES_IE would have imported permit assumptions that do not apply.
