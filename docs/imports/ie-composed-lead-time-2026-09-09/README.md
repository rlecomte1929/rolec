# Ireland composed permit-then-visa lead time (AIQ-2192)

**Status: artifacts landed in the repo. Nothing loaded into any database yet.**
Operator apply is out of band. Dry-run default:

```
python scripts/check_ie_composed_lead_time_batch.py
python scripts/convert_ie_composed_lead_time_to_otto_jsonl.py
python scripts/import_otto_facts.py ie-composed-lead-time-2026-09-09
```

Do **not** pass `--apply` against production from this ticket.

| | |
|---|---|
| Batch id | `ie-composed-lead-time-2026-09-09` |
| Ticket | AIQ-2192 |
| Destination | Ireland (`requirement_items.country_code` = `IRELAND`) |
| Scope | `THIRD_COUNTRY` only |
| Served to any user? | **No.** `review_status='pending'` |

## What this is

One new candidate requirement: DETE's **12-week** permit lodgement and the existing **~8-week** employment-visa decision are **sequential**, so a third-country national who needs both should treat **approximately 20 weeks** before the proposed start as the combined runway.

The 20-week figure is 12 + ~8 from the two already-published source rows. It is **not** a new statutory number.

## Source rows (do not edit)

Copied citations only. This batch does not UPDATE either row.

1. **Employment permit 12-week lodgement** — `ES_IE:THIRD_COUNTRY:permit_application_12_week_lead_time`  
   DETE: *“An application for any employment permit must be received at least 12 weeks before the proposed employment start date.”*  
   https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/

2. **Entry visa after permit timing** — `ES_IE:THIRD_COUNTRY:entry_visa_after_permit_timing`  
   Existing fact text states ~8 weeks and up to 3 months before travel.  
   ISD evidence quote supports **sequence only**, not those durations: *“Once you have received a permit, you are eligible to apply for an Employment Visa.”*  
   https://www.irishimmigration.ie/coming-to-work-in-ireland/what-are-my-work-visa-options/applying-for-a-long-stay-employment-visa/employment-visa/

The composed `fact_text` says that the ISD quote does not itself state 8 weeks / 3 months.

## Honesty constraints

- `quote_verbatim_confirmed` is `false` — this composition was not re-fetched from live pages in this ticket.
- `review_status` is `pending`. Otto `promote()` always writes pending and does not overwrite a later reviewer decision.
- `applies_to_nationality_classes` is `["THIRD_COUNTRY"]` only.

## Gate

`scripts/check_ie_composed_lead_time_batch.py` re-hashes the NDJSON against this manifest, reconverts, and parses through `read_jsonl`.
