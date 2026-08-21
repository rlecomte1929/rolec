# es-ie-general-curated-2026-08-22 — Andrea's ES→IE destination facts, made loadable

contract: `docs/otto/andrea-denis-brief-2026-08-21.md` §3

**What this is.** Otto's `es-ie-general-2026-08-21` batch (33 facts, branch
`fix/td-qa-services-batch-0719` @ `2732903b`, verbatim copy in `raw/`) was refused whole by the
loader: `applies_to.nationality` was null on every record, and null is refused by design. This
directory is the curated, loadable derivation: every fact re-scoped from its own text, re-keyed
to requirement-granularity topics, and accounted for. The curation is code, not prose —
`scripts/curate_general_batches_2026_08_22.py` holds the per-fact disposition table (the S1
scoping audit: one justification line per fact, also carried on each record as
`applies_to.curation_justification`), and re-running it reproduces this directory byte-for-byte.

**Reconciliation (must hold):** 33 raw = **18 loaded** base facts (→ 29 records after
universal-fact twinning) + **3 step candidates** + **12 deferred**. Manifest sha256 covers the
curated NDJSON.

**Gate results (2026-08-22):** `parsers.read_jsonl`: 29 rows, **0 rejections**; nationality
scoped 29/29 (15 non-EEA / 14 EEA), status `professional` 29/29; all rows grade `needs_review`
(quote_verbatim_confirmed=false — quotes not yet re-verified against pages, and 25/29 cite
`citizensinformation.ie`, semi-official). `mappings.resolve` simulation: **13 requirement
drafts for IRELAND, 0 Unmapped** — 2 THIRD_COUNTRY-only (work permission; IRP/ISD registration
— Andrea's core), 11 audience-split twins (PPSN, PRSI, USC, income tax, health, A1).

**Step candidates** (for `corridors/ES_IE/pathways/CSEP_2026`, not the fact stream):
`es_ie_pps_number_online_application_mygov_id` · `es_ie_prsi_employer_requires_pps_number` ·
`es_ie_eu_citizen_medical_card_posted_worker_e106`. The CSEP graph already covers PPSN and
payroll sequencing — placing these is the graph owner's call.

**Deferred — the self-employment sub-corpus (12 facts).** Revenue self-assessment, ROS, Form
11, preliminary tax, CRO business names, Class S PRSI, USC surcharge, VAT threshold. Both demo
movers are employees; these stay preserved in `raw/` and go back through the Otto re-delivery
(AIQ-1833 / A1) for scoping if wanted.

**Open question flagged for counsel/review:** the A1 posted-worker fact is loaded EEA-scoped as
published. Whether EU social-security coordination extends to third-country nationals **for
Ireland** (Reg. 1231/2010 participation) is a legal determination deliberately NOT encoded here.

**Load contract:** candidates only.
`python scripts/import_otto_facts.py docs/imports/es-ie-general-curated-2026-08-22/es-ie-general-curated-2026-08-22.ndjson --expected 29`
(dry-run; the CLI resolves workspace batch-ids only, so pass the path), then `--apply`. Stages to `otto_staging` at `status='new'`; promotion needs the human flip to
`'ready'` and `--promote`, landing `review_status='pending'` / `verification_status='representative'`
in `public.requirement_items`. Never past pending.
