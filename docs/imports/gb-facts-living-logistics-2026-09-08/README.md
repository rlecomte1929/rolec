# GB living-logistics facts — B22 (2026-09-08)

Otto batch `gb-facts-living-logistics-2026-09-08` (corridor IN→GB, scope non-EEA/professional),
delivered to GCS and pulled off the `otto_to_claude` bridge (id 33). First real end-to-end exercise
of the import pipeline.

## Delivery
- `facts.ndjson` — 20 facts, Otto "resource" vocabulary (`fact_id`/`category`/`scope`), all
  `www.gov.uk` sources. sha256 reconciled against the bridge manifest.
- `manifest.json` — as delivered. `clean.ndjson` — transformed to the parsers vocabulary
  (category→entity_topic_key, fact_id→fact_key, corridor→GB, `scope`→`applies_to`); 0 parser
  rejections.

## Verification (applier, independent)
`verify_ledger`'s HTTP fetch gets gov.uk's cookie/JS shell, so **every quote was browser-grounded**
(read the real gov.uk page in the in-app browser and confirmed the quote verbatim).

- **11 LANDED** (pending, `corpus_grounded`, direct insert into `requirement_items`,
  `country_code='UNITED KINGDOM'`): council tax (gb-ll-001…006) + school admissions
  (gb-ll-007…011). Every quote confirmed verbatim on its proper gov.uk page.
- **9 HELD (mis-sourced, need re-sourcing):** driving (gb-ll-012…015) cite a Ukraine consultation /
  an e-scooter page / a news release; bank (gb-ll-016…020) cite the *Homes-for-Ukraine* scheme page.
  The facts may be true but the sources are wrong-context for an India-corridor fact — re-source to
  the canonical gov.uk guidance before landing.

## Landing method (NOT the harness)
`mappings.resolve()` refuses `domain_area != 'immigration'`, so living-logistics facts cannot land
via the otto_staging→requirement_items promote path. They land by **direct insert** (the method used
for the prior 12 UK facts): `uuid5(_SEED_NS, "UNITED KINGDOM|<purpose>|<title>")`,
`verification_status='corpus_grounded'`, `review_status='pending'`, `["THIRD_COUNTRY"]`,
`pillar=HOUSING` (matching the existing UK skeleton rows). purpose: council tax=employment,
schools=family. Append-only proven: UK `fp_protected` d2d904fa… unchanged, approved 6→6,
expert_verified 0.

## Follow-ups
- Re-source the 9 held driving/bank facts to canonical gov.uk pages.
- `convert_otto_batch.py` needs an `otto_resource` profile for this `scope`-string vocabulary
  (5th shape) so future resource deliveries convert without a hand transform.
- The old UK skeleton rows "Council tax" / "State school admissions" are now superseded by these
  specific facts — reject them at review.
