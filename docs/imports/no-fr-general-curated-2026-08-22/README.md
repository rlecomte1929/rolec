# no-fr-general-curated-2026-08-22 — Denis's NO→FR destination facts, made loadable

contract: `docs/otto/andrea-denis-brief-2026-08-21.md` §3

**What this is.** Otto's `no-fr-general-2026-08-21` batch (20 facts, branch
`fix/td-qa-services-batch-0719` @ `2732903b`, verbatim copy in `raw/`) was refused whole for
null `applies_to.nationality`. This is the curated, loadable derivation — same method and same
audit trail as the ES→IE sibling: the per-fact disposition table in
`scripts/curate_general_batches_2026_08_22.py` is the S1 scoping audit, and each record carries
its `curation_justification`.

**Reconciliation (must hold):** 20 raw = **16 loaded** base facts (→ 17 records after twinning)
+ **3 origin-side candidates** + **1 deferred**. Manifest sha256 covers the curated NDJSON.

**Gate results (2026-08-22):** `parsers.read_jsonl`: 17 rows, **0 rejections**; nationality
scoped 17/17 (15 EEA / 2 non-EEA), status `professional` 17/17; all `needs_review`
(quote_verbatim_confirmed=false pending human quote re-verification; sources are
service-public.fr / urssaf.fr / legifrance / skatteetaten — all official). `mappings.resolve`
simulation: **9 requirement drafts for FRANCE, 0 Unmapped**. EEA maps to
`[OWN_NATIONAL, EU_EEA]`, so Denis (French national returning) is served by every EEA row.

**Origin-side candidates — NOT loaded here** (they are Norway exit duties in a
destination-France file; their home is `corridors/NO_FR/facts.yaml`, which already holds 4
origin facts — hand these to Otto task D2 / AIQ-2068 with the existing `fact_key`s to avoid
collisions): `no_fr_norway_folkeregister_deregistration_obligation` ·
`no_fr_norway_must_notify_move_abroad_skatteetaten` · `no_fr_norway_tax_4_year_rule`
(the Skatteloven §2-1(3) continued-liability rule pairs with the existing
`no_tax_residence_does_not_end_on_move` HLP baseline entry).

**Deferred:** `no_fr_urssaf_self_employed_registration_obligation` (self-employment; also a
sequence step). Preserved in `raw/`.

**Load contract:** candidates only.
`python scripts/import_otto_facts.py docs/imports/no-fr-general-curated-2026-08-22/no-fr-general-curated-2026-08-22.ndjson --expected 17`
(dry-run; the CLI resolves workspace batch-ids only, so pass the path), then `--apply`; human flips staging rows to `'ready'` before any `--promote`. Never past pending.
