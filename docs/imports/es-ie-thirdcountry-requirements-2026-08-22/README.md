# ES→IE destination requirements — third-country (non-EEA) professional

**Batch id:** `es-ie-thirdcountry-requirements-2026-08-22`
**Corridor:** ES-IE · **Direction:** DESTINATION (Ireland arrival) · **Jurisdiction:** IE
**Persona:** Andrea — a non-EEA (Venezuelan) national resident in Spain, taking up
professional employment in Dublin (Madrid → Dublin).
**Records:** 38 · **Target table:** `requirement_facts` · **Retrieved:** 2026-08-21T22:30:00Z

This batch replaces the unusable `es-ie-general` drop with a loadable ES→IE **destination**
fact stream scoped entirely to a third-country professional. Every record carries
`applies_to.nationality: "non-EEA"` and `applies_to.status: "professional"`. There is no
`fact_type: "step"` record anywhere in the stream — process steps belong to
`requirement_entities`, not the fact stream, and the nine step records from the previous
drop are dropped rather than reshaped.

## Files

| File | Role | Bytes | Records |
|---|---|---|---|
| `es_ie_thirdcountry_requirements.ndjson` | fact stream (one JSON object per line) | 78,040 | 38 |
| `manifest.json` | counts, sources, reconciliation, dependency state | 10,411 | — |
| `README.md` | this document | — | — |

`manifest.json` carries the SHA-256 of the fact stream
(`188028d60e5e400bb3128fa45c292b584d691c7281c048522900854fd0beacb7`). It does not
checksum itself or this README, matching the convention in
`docs/imports/ie-isd-visa-required-2026-08-22/manifest.json`.

## Topic coverage

| Topic (`applies_to.topic`) | `topic_key` | `domain_area` | Records |
|---|---|---|---|
| `immigration_work_authorization` | `ES-IE:thirdcountry:immigration_work_authorization` | immigration | 9 |
| `isd_irp_registration` | `ES-IE:thirdcountry:isd_irp_registration` | registration | 11 |
| `ppsn` | `ES-IE:thirdcountry:ppsn` | social_security | 5 |
| `revenue_rpn_emergency_tax` | `ES-IE:thirdcountry:revenue_rpn_emergency_tax` | tax | 7 |
| `health_entitlements` | `ES-IE:thirdcountry:health_entitlements` | healthcare | 3 |
| `taxation` | `ES-IE:thirdcountry:taxation` | tax | 3 |

`fact_type` distribution: `eligibility` 10 · `other` 16 · `deadline` 3 · `document` 3 ·
`account` 2 · `fee` 2 · `where_to_apply` 2 · **`step` 0**.

The CSEP employment-permit pathway is carried in `immigration_work_authorization`
(9 records: no-Labour-Market-Needs-Test, the €40,904 / €36,848 / €68,911 thresholds, the
12-week lodgement rule, the permit-is-not-a-residence-permission separation, the employer
50 % EEA workforce test, the €1,000 fee with 90 % refund, the visa-sequence record, the
9-month employer lock, and the direct Stamp 4 route). The 40 %-emergency-tax-from-week-5
rule is `revenue_rpn_emergency_tax` / `emergency_tax_week_5_full_40_percent`.

## Sources — official publishers only

Every record cites one of ten pages on five Irish state domains. Each `evidence_quote` was
copied from a page fetched during this run; no quote was reconstructed from memory.

| Publisher | Domain | Pages | Records |
|---|---|---|---|
| Department of Enterprise, Tourism and Employment (DETE) | `enterprise.gov.ie` | 1 | 9 |
| Immigration Service Delivery (ISD), Department of Justice | `www.irishimmigration.ie` | 3 | 11 |
| Department of Social Protection (DSP) / MyWelfare | `services.mywelfare.ie` | 1 | 4 |
| Office of the Revenue Commissioners | `www.revenue.ie` | 4 | 11 |
| Health Service Executive (HSE) | `www2.healthservice.hse.ie` | 1 | 3 |

**Quote fidelity.** 37 of 38 `evidence_quote` values are byte-verbatim from the source
page. One (`health_non_eea_immigration_permission_verified`) is drawn from a PDF-derived
HSE guideline where bullet glyphs and soft line-wraps were removed; no word was added,
dropped or reordered. That record carries
`applies_to.quote_verbatim_confirmed: false` plus an `applies_to.quote_normalization`
note, and the manifest counts it in `counts.quote_normalized` and
`reconciliation.quote_normalized_records`. Nothing is silently normalised.

## S1 — nationality-scoping self-audit

Task S1 was run over this batch and this README before delivery. It is not a restatement
of the contract check; it asks a harder question: *for each record, is `non-EEA` a
statement about the law, or about this batch's audience?*

All 38 records satisfy the contract (`nationality: "non-EEA"`, `status: "professional"`).
Only **21** are nationality-**determined**. The other **17** are nationality-neutral Irish
rules that this batch happens to present to a non-EEA reader.

| Basis | Records | Meaning |
|---|---|---|
| `nationality_determined` | 21 | The obligation exists *because* the person is non-EEA. An EEA/EU national genuinely does not face it. |
| `audience_scope` | 17 | The rule is nationality-neutral in Irish law. `non-EEA` records the audience of this batch, **not** a restriction — the same rule binds an EEA mover and must not be withheld from one. |

Per topic:

| Topic | `nationality_determined` | `audience_scope` |
|---|---|---|
| `immigration_work_authorization` | 9 | 0 |
| `isd_irp_registration` | 11 | 0 |
| `ppsn` | 0 | 5 |
| `revenue_rpn_emergency_tax` | 0 | 7 |
| `health_entitlements` | 1 | 2 |
| `taxation` | 0 | 3 |

**Why the immigration and registration topics are wholly nationality-determined.**
Employment permits exist only for non-EEA nationals, and the ISD registration duty is
expressly limited by its own source text to people "from a country outside the European
Union, UK or Switzerland". An EEA mover faces neither.

**Why PPSN, PAYE/RPN/Emergency Tax and taxation are audience-scoped.** Nothing in the DSP
PPS Number rules, the Revenue Emergency Tax rules or the residence/domicile tests turns on
nationality. A Spanish national moving Madrid → Dublin hits the same week-5 40 % cliff, the
same first-job-registration split, and the same worldwide-income charge. The one health
record that *is* nationality-determined
(`health_non_eea_immigration_permission_verified`) is so because the HSE guideline itself
heads that passage "If you are a non EU/EEA or Switzerland".

**Finding, and what was changed because of it.** Scoping a nationality-neutral rule to
`non-EEA` without saying so is exactly how a serving layer comes to imply that an EEA mover
is exempt from Emergency Tax. Every record therefore now carries a machine-readable
`applies_to.nationality_scope_basis` (`nationality_determined` | `audience_scope`), whose
two values are spelled out once in `manifest.json` under
`dependencies.S1_nationality_scoping_self_audit.basis_definitions` rather than repeated as
prose on all 38 records. The verification harness fails the batch if any record is
unclassified, if a record's basis has no definition in the manifest, if the two bases do not sum to the record total, or if
an `audience_scope` record is *worded* as a non-EEA-only restriction. The counts are
reconciled in `manifest.json` under
`dependencies.S1_nationality_scoping_self_audit.bases`.

**Consequence for the consumer:** filter on `nationality_scope_basis`, not on
`nationality`, when deciding whether a requirement is genuinely inapplicable to an
EEA/EU mover.

## A3 dependency — the visa-required question stays conditional

Task A3 (`docs/imports/ie-isd-visa-required-2026-08-22/`) is the authority on which
nationalities are visa-required, and it has landed. **No record in this batch asserts that
any nationality *is* visa-required.** Two records touch the visa question and both are
marked `applies_to.assertion_mode: "conditional"` with an
`applies_to.conditional_on` pointer to A3:

| `fact_key` | What it asserts | What it does *not* assert |
|---|---|---|
| `entry_visa_follows_permit_if_visa_required` | The ordering: the entry visa is applied for *after* the permit issues, at the local Irish Embassy/Consulate. | That the persona's nationality is visa-required. |
| `leaving_state_before_registration_needs_new_entry_visa` | The consequence: a visa-required national who leaves before their registration appointment cannot re-enter without a new visa. | That the persona's nationality is visa-required. |

Both quote the source's own conditional wording — DETE's "and if visa required" and ISD's
"If you are a visa-required national" — so the conditionality is the publisher's, not an
editorial hedge. The verification harness fails the batch if any record asserts
visa-required status unconditionally.

## Loader contract — how these records promote

The consuming loader is otto-loader v6 (`tools/otto-loader-index.ts`). Three details of
that loader shaped the record schema:

1. **Routing is by `target_table`.** A record whose `target_table` does not match
   `requirement_fact` lands in the loader's `unrouted` bucket — the "Unmapped" count.
   Every record here carries `"target_table": "requirement_facts"` at *record* level, so
   routing does not depend on the manifest row being read correctly.
2. **`topic_key` must be top-level or inside `entity`.** The loader reads
   `topic_key || entity.topic_key`, and does **not** read `entity_topic_key`. The previous
   ES→IE drop (`data/ve-ie-entry-family-2026-08-20.jsonl`) used `entity_topic_key`, so all
   of its records silently collapsed onto the fallback topic `immigration`. This batch sets
   `topic_key` at both levels, with identical values.
3. **Confidence is read from `confidence_score`, not `confidence`.** The loader calls
   `confBucket(rec.confidence_score)`; a string `confidence` field is ignored. Records here
   carry a numeric `confidence_score` (0.9 → high, 0.7 → medium) and a matching
   `confidence` label for human readers.

`domain_area` values are drawn from the loader's own allow-list, and `fact_type` values
from its own set, so neither is silently rewritten to `other` on load.

## Reconciliation and no-collision proof

`manifest.json` reconciles: `records_total == ndjson_lines == 38`, and the record total
equals the sum of `by_topic`, of `by_fact_type`, of `by_domain_area`, of
`sources[].records_citing`, and of the two S1 bases.

**No collision with existing content.** The loader deduplicates facts on
`destination_country | topic_key | fact_key`. A live read of `requirement_entities`
enumerated all **38** existing ES-IE entity `topic_key` values; none is in the
`ES-IE:thirdcountry:*` namespace this batch uses, so no `dup_existing` is possible and the
6 topic entities are created fresh. The 52 existing ES-IE `requirement_facts` rows
(from `es-ie.json` and `ES-IE-knowledge-2026-08-18.jsonl`) are therefore untouched.

**Editorial overlap, disclosed.** Distinct keys are not the same as distinct content.
Several existing rows cover the same ground at lower nationality precision — for example
`ES-IE:tax-emergency-tax:emergency_tax`, `ES-IE:pps-number:pps_purpose` and
`ES-IE:critical-skills-employment-permit:csep_two_year_offer`. This batch does not
supersede them automatically; deciding which row a corridor serves is a curation call for
review, not something an import should take. Note also that several of those existing rows
carry `employee_profile: "all"` on requirements this batch shows to be
nationality-determined — a candidate follow-up for the same S1 lens applied to already-live
rows.

## Verification

The result below was produced by a purpose-built harness run against this directory during
authoring. It has three sections — the §3 delivery contract, the S1 self-audit, and a
promotion simulation that re-implements the routing/mapping branch of
`tools/otto-loader-index.ts` so "0 Unmapped, 100 % promote" is measured rather than
asserted — and it exits 0 only when every check passes.

The authoring run used a purpose-built harness because the workspace gate had not landed
yet. The canonical re-run path is now the standard-library-only workspace gate:

```bash
python3 scripts/check_otto_batches.py es-ie-thirdcountry-requirements-2026-08-22
```

The recorded authoring result below remains **47 checks, all PASS**:

```
--- SECTION 1: DELIVERY CONTRACT (section 3) ---
  [PASS] every record has applies_to.nationality from {EEA, EU, non-EEA, non-EU}, never null - 38/38 ok
  [PASS] every record is scoped nationality='non-EEA' (third-country persona) - 38/38
  [PASS] every record has applies_to.status='professional' - 38/38 ok
  [PASS] no fact_type='step' record in the fact stream - 0 found
  [PASS] every source_url is an absolute https URL - 38/38 ok
  [PASS] every source_url is on an official Irish state publisher host
  [PASS] every record carries a non-empty evidence_quote - 38/38 ok
  [PASS] every evidence_quote is a substantive quotation (>= 25 chars) - shortest 68 chars
  [PASS] quote-normalisation bookkeeping is explicit - 37 byte-verbatim, 1 normalised
  [PASS] manifest quote_normalized count matches the stream - stream 1 vs manifest 1
  [PASS] review_status_all: every record is 'pending' - 38/38
  [PASS] manifest declares review_status_all='pending' - pending
  [PASS] verification_status_all: every record is 'representative' - 38/38
  [PASS] manifest declares verification_status_all='representative' - representative
  [PASS] every record is a DESTINATION fact (destination_country='IE') - 38/38
  [PASS] all six required topics are covered
  [PASS] fact_key is unique across the stream - 0 duplicates
  [PASS] no record asserts unconditionally that a nationality IS visa-required (A3 dependency)

--- SECTION 1a: S1 NATIONALITY-SCOPING SELF-AUDIT ---
  [PASS] every record declares applies_to.nationality_scope_basis - 38/38 classified
  nationality_determined : 21
  audience_scope         : 17
  [PASS] nationality_determined + audience_scope == records_total - 38 vs 38
  [PASS] manifest S1 basis counts match the stream
  [PASS] every record's basis resolves to a manifest basis_definitions entry
  [PASS] no audience-scope record is worded as a non-EEA-only restriction

--- SECTION 1b: MANIFEST RECONCILIATION ---
  [PASS] manifest counts.records_total == records in the stream - 38 vs 38
  [PASS] manifest counts.ndjson_lines == non-empty lines in the stream - 38 vs 38
  [PASS] sum(counts.by_topic) == records_total - 38 vs 38
  [PASS] sum(counts.by_fact_type) == records_total - 38 vs 38
  [PASS] sum(counts.by_domain_area) == records_total - 38 vs 38
  [PASS] counts.nationality_non_eea == records_total - 38
  [PASS] counts.status_professional == records_total - 38
  [PASS] counts.nationality_null_or_missing == 0 - 0
  [PASS] counts.fact_type_step == 0 - 0
  [PASS] manifest by_topic histogram matches the stream
  [PASS] manifest by_fact_type histogram matches the stream
  [PASS] sum(sources[].records_citing) == records_total - 38 vs 38
  [PASS] every source's records_citing matches the stream - 10 distinct source URLs
  [PASS] every source_url used in the stream is declared in the manifest
  [PASS] manifest files[0].bytes matches the file on disk - 78040 vs 78040
  [PASS] manifest files[0].sha256 matches the file on disk
  [PASS] manifest files[0].records matches the stream - 38 vs 38
  [PASS] every manifest reconciliation *_balanced flag is true
  [PASS] manifest asserts no_fact_type_step
  [PASS] manifest asserts fabricated_records == 0

--- SECTION 2: PROMOTION SIMULATION (otto-loader v6) ---
  records routed to requirement_facts : 38
  UNMAPPED (loader 'unrouted' bucket) : 0
  mapped_new (would promote)          : 38
  dup_in_batch                        : 0
  dup_existing                        : 0
  skip_no_source / no_dest / no_text  : 0 / 0 / 0
  requirement_entities auto-created   : 6
  [PASS] 0 Unmapped (every record routes to requirement_facts) - 0
  [PASS] 100% of records promote (mapped_new == records_total) - 38/38
  [PASS] no duplicate (dest|topic|fact_key|applies_to) inside the batch
  [PASS] no collision with keys already in the target
  [PASS] no record skipped for missing source_url / destination / fact_text
  [PASS] no domain_area silently downgraded to 'other' by the loader's allow-list
  [PASS] no fact_type silently coerced by the loader
  [PASS] one requirement_entities row per required topic would be created - 6 entities

VERDICT: PASS - 38 records, 0 Unmapped, 38/38 promote, manifest reconciles
```

### Canonical gate path

`scripts/check_otto_batches.py` is now present in this workspace and is the canonical gate
for batches under `docs/imports/`. It has no third-party dependencies, so invoke it with an
available Python 3 interpreter; do not point batch tasks at a workspace-specific virtualenv:

```bash
python3 scripts/check_otto_batches.py es-ie-thirdcountry-requirements-2026-08-22
```

The gate mirrors `tools/otto-loader-index.ts` and includes the checks that exposed the
previous drop's silent-loss risks: every record must route via `target_table`; `topic_key`
must be present at record level and match `entity.topic_key` because the loader ignores
`entity_topic_key`; and `confidence_score` must be numeric in `[0, 1]` because the
requirement-fact path ignores `confidence`. Its promotion simulation must report 0 records
in the loader's `unrouted` bucket and every record promoting.

Do not substitute `scripts/import_otto_facts.py`. It validates the older flat Otto schema
from `backend/imports/otto/parsers.py`, whose `applies_to` accepts only `route`, `scenario`,
and `nationalities` and rejects this delivery contract's `applies_to.nationality` and
`applies_to.status` fields.

## Honest limits

- **`review_status: pending` / `verification_status: representative` on every record.** No
  lawyer or tax adviser has reviewed this content. ES-IE `assurance_status` is
  `not_started`. Nothing here may be presented as legal or tax advice.
- **6 records are flagged `applies_to.needs_lawyer_review: true`**, concentrated on the
  permit/residence interaction, the two-EU-residence-permits point, and the worldwide-income
  and post-departure tax positions.
- **16 records are flagged `non_obvious: true`** and carry the
  *Commonly believed / Actually / Action required* structure. That flag is authored
  judgement, not a measured recall figure against the Andrea golden fixture.
- **`es-ie-general` was not located in this tree.** Enumerated without finding it:
  `docs/imports/` (only the A3 batch), `docs/`, `data/`, `data/corridor-facts/`,
  `research/`, `imported-source/`, `.audos-import/`, plus `overnight_manifest.json` and
  `docs/gcs-manifest-inventory.md`. The closest artefact present is
  `data/ve-ie-entry-family-2026-08-20.jsonl` (9 records, ES→IE non-EEA professional,
  `fact_type: "other"`). This batch was therefore written to the delivery contract and the
  topic list directly rather than as a diff against a file that could not be read; if
  `es-ie-general` held records outside the six topics above, that coverage is not carried
  over here.
- **The batch is not loaded.** These are files on disk. Promotion into
  `requirement_facts` runs through the loader with the founder-held loader token, which is
  not available from this workspace. The promotion numbers above are a simulation of that
  loader's logic, not a live import.
- **This workspace has no git access**, so no branch, commit or PR was created — see the
  same note in `docs/esie-andrea-golden-fixture.md`. The batch is intended for branch
  `fix/td-qa-services-batch-0719`, never `main`.
