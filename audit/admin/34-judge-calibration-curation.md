# 34 — Judge Calibration Gold-Set Curation

**Policy applied:** support-based (Romain's domain call, 2026-06-30)

> `grounded` = every claim in the answer is supported by some chunk (omissions are OK).
> `partially_grounded` = supported claims mixed with at least one unsupported claim.
> `ungrounded` = core claim unsupported by any chunk, or contradicts a chunk.

## Per-case review

| id   | old gold → new gold       | rationale |
|------|---------------------------|-----------|
| C-01 | grounded → **grounded**   | "EUR 2,500 per month" fully supported; omits "for a standard relocating employee" — omission allowed. |
| C-02 | grounded → **grounded**   | "two home-leave trips per year" fully supported; omits "in economy class" — omission allowed. |
| C-03 | grounded → **grounded**   | "up to EUR 20,000 per child per year" fully supported; omits "against invoices" — omission allowed. |
| C-04 | grounded → **grounded**   | Verbatim match to chunk; omits nothing material. |
| C-05 | grounded → **grounded**   | "up to 30 days on arrival" supported; omits "before the lease starts" — omission allowed. |
| C-06 | grounded → **grounded**   | COLA trigger condition fully supported; "(COLA)" acronym expansion omitted — allowed. |
| C-07 | grounded → **grounded**   | "assignee pays hypothetical home-country tax" supported; omits "company covers actual taxes" — omission allowed. |
| C-08 | grounded → **grounded**   | "EUR 5,000 for job-search costs" supported; omits "and accreditation costs" — omission allowed. |
| C-09 | grounded → **grounded**   | "covers assignee and dependants" supported; omits "for the assignment" — omission allowed. |
| C-10 | partially_grounded → **partially_grounded** | "EUR 2,500 cap" supported; "furniture rental budget of EUR 500" fabricated — not in any chunk. |
| C-11 | partially_grounded → **partially_grounded** | "two home-leave trips" supported; "unlimited weekend trips" fabricated. |
| C-12 | partially_grounded → **partially_grounded** | "EUR 20,000 per child" supported; "university fees also reimbursed" fabricated. |
| C-13 | partially_grounded → **partially_grounded** | "40 cubic metres shipment" supported; "new car is provided" fabricated. |
| C-14 | partially_grounded → **partially_grounded** | "30 days accommodation" supported; "personal chef" fabricated. |
| C-15 | partially_grounded → **partially_grounded** | "COLA is paid" supported; "guaranteed annual bonus of 20 percent" fabricated. |
| C-16 | partially_grounded → **partially_grounded** | "tax equalization applies" supported; "company pays your mortgage at home" fabricated. |
| C-17 | partially_grounded → **partially_grounded** | "EUR 5,000 spousal allowance" supported; "spouse gets a guaranteed local job" fabricated. |
| C-18 | ungrounded → **ungrounded** | "company yacht and private island" completely unsupported by housing-cap chunk. |
| C-19 | ungrounded → **ungrounded** | "lifetime first-class travel for extended family" contradicts chunk ("two trips per year in economy"). |
| C-20 | ungrounded → **ungrounded** | "Harvard with full scholarships" unsupported; chunk only mentions school tuition cap. |
| C-21 | ungrounded → **ungrounded** | "entire mansion" and "fleet of luxury vehicles" unsupported by shipment-limit chunk. |
| C-22 | ungrounded → **ungrounded** | "five-star suite indefinitely" contradicts chunk ("up to 30 days"). |
| C-23 | ungrounded → **ungrounded** | "guaranteed doubling of salary" unsupported; COLA chunk is conditional, not a salary doubling. |
| C-24 | ungrounded → **ungrounded** | "company pays zero tax" contradicts chunk ("assignee pays hypothetical home-country tax"). |
| C-25 | ungrounded → **ungrounded** | "spouse appointed regional director" unsupported by job-search-allowance chunk. |

## Summary

**Labels changed: 0 of 25.** All existing synthetic labels are consistent with the support-based policy.

## Verdict distribution (post-curation)

| verdict             | count |
|---------------------|-------|
| grounded            | 9     |
| partially_grounded  | 8     |
| ungrounded          | 8     |
| **total**           | **25** |

## Coverage assessment

Distribution is **not degenerate**: 9 / 8 / 8 across three classes gives a well-balanced calibration set. No fabricated cases were added. The slightly higher grounded count (9 vs 8) reflects the nine clean paraphrase/subset cases designed to test omission tolerance.

No coverage gap flagged. The set is fit for kappa measurement.
