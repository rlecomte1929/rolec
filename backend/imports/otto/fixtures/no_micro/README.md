# `no_micro` — covered-country verifier fixture

Eight real NORWAY facts, copied from `public.requirement_facts` on 2026-08-30 (every one
`evidence_verified = true`), plus five deliberately broken lines.

**Why a covered country and not the US→EC batch.** `EC` is in neither `_ISO_TO_CATALOG_NAME`
(11 codes) nor `DESTINATION_COUNTRIES` (21), so every Ecuador record is `Unmapped` at promote.
Testing the verifier on it would conflate "the verifier works" with "the destination is onboarded".
`NO` is covered, so a failure here is the verifier's.

**The broken lines are the point.** A gate that has only ever seen good input proves nothing, so
lines 9–13 are one instance of each way the importer fails:

| line | defect | expected |
|---|---|---|
| 9 | not valid JSON | REJECT `V0/bad_json` — `read_jsonl` would raise here and strand lines 10-13 |
| 10 | no `source_url` | REJECT `V1/missing_required` — `read_jsonl` would raise |
| 11 | publisher is a blog | REJECT `V2/unofficial_source` — `read_jsonl` rejects it |
| 12 | duplicates line 2's `dedupe_key` | REJECT `V1/duplicate_dedupe_key` |
| 13 | `fact_type`/`confidence` off-vocabulary, `domain_area` not immigration | WARN only — imports, then never promotes |

Line 13 is the one worth understanding: nothing rejects it, the importer reports success, and it
produces no requirement. That silence is what the WARN severity exists to break.

Note the real rows carry `applies_to: {}` and `domain_area` of `registration`/`other` — that is
production as it actually is, and it is why the fixture's promotable count is lower than its clean
count. Lines 1-2 carry a populated `applies_to` so the promotable path is exercised too.
