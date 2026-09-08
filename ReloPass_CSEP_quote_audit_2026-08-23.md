# CSEP evidence-quote audit — enterprise.gov.ie

**Measured 2026-08-23** by fetching both cited pages and checking every quote against them.
These rows are in **production `requirement_facts`** (topic_key `csep`), not in any batch file —
which is why the reference did not carry over: it is a different dataset from the ES→IE batch.

## Headline

**0 of 15 CSEP `evidence_quote` values appear on the page they cite.** Every one is a paraphrase
or a summary, not a quotation. Example — `csep_1`:

> stored: *"designed to attract highly skilled people into the labour market and encourage
> permanent residency in Ireland"*
> page: *"…is designed to attract highly skilled people into the labour market **with the aim of
> encouraging them to take up permanent residence in the state**"*

Meaning preserved, wording invented. That is the class of defect nothing downstream can catch,
because the source is the only appeal.

**The substance, separately, mostly holds.** Probing the claims rather than the quotes:

| claim | on the page |
|---|---|
| €40,904 / €36,848 / €68,911 thresholds | yes |
| 12-week application lead time | yes |
| no Labour Market Needs Test | yes |
| 9-month employer lock | yes |
| Stamp 4 pathway | yes |
| 50% EEA workforce rule | yes |
| CSEP fee €1,000 | yes |
| Dependant/Partner/Spouse permit: no fee | yes |
| **90% refund on unsuccessful applications** (`csep_3`) | **NO — the word "refund" does not appear on the fees page at all** |

So this is a citation-quality problem, not a factual one — with one exception.

## Two things worth a decision

**`csep_3` asserts a 90% refund that its source does not support.** Status `pending`. The fee
itself (€1,000) is on the page; the refund is not. Either find the page that states it or drop
the clause.

**`csep_5` is `rejected`, but its content checks out.** It claims *"€68,911 minimum for all other
occupations (no degree required if sufficient experience)"*. The page says *"all occupations with
a minimum annual remuneration of over €68,911, other than those on the ineligible list…"* and
*"a non-EEA national who does not have a degree qualification or higher, must have the
nec[essary experience]"*. Both halves are supported. AIQ-1845 rejected two salary figures as
fabricated; this one is not. Worth re-checking whether the rejection was right, or whether the
page has changed since.

## Do we need Otto for this?

No. The fetch-and-check half is automated (`scripts/verify_batch_quotes.py`) and is what produced
the table above. What is left is a judgement call — *is this paraphrase an acceptable restatement,
or does it misstate the rule?* — and for permit thresholds that is a counsel question, not a
research one.

If the quotes are to be **replaced** with real sentences, that is worth one pass, and the input
Otto asked for is below.

## The input Otto asked for

All 15 CSEP rows citing enterprise.gov.ie (Otto's message said 11; the live table holds 15 with a
non-null quote, plus 3 with none at all — `csep_application_fee`, `csep_eligibility`,
`csep_residency_pathway`).

```ndjson
{"fact_id":"csep_1","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"designed to attract highly skilled people into the labour market and encourage permanent residency in Ireland"}
{"fact_id":"csep_2","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Job offer from bona-fide Irish employer (minimum 2 years duration). Employer registered with Revenue Commissioners and Companies Registration Office"}
{"fact_id":"csep_3","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/fees/","current_quote":"Critical Skills Employment Permit: €1,000 (up to 24 months). Unsuccessful applications receive 90% refund."}
{"fact_id":"csep_4","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"€40,904 minimum for restricted strategically important occupations (requires degree). €36,848 minimum if qualification obtained within 12 months prior to application"}
{"fact_id":"csep_5","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"€68,911 minimum for all other occupations (no degree required if sufficient experience)"}
{"fact_id":"csep_6","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Employer must have 50%+ EEA national employees (waived for start-ups within 2 years, supported by Enterprise Ireland or IDA)"}
{"fact_id":"csep_7","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"No Labour Market Needs Test required"}
{"fact_id":"csep_8","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Must apply 12 weeks before employment start date"}
{"fact_id":"csep_9","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Cannot change employers before 9 months elapsed. Exceptions: redundancy or unforeseen circumstances fundamentally altering employment"}
{"fact_id":"csep_10","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"holders may apply for 'Stamp 4' immigration permission (2 years, renewable). No renewal permit through Department needed for eligible holders"}
{"fact_id":"csep_11","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Immediate family reunification eligible through Immigration Service Delivery. Dependants can apply for free Dependant/Partner/Spouse Employment Permits once resident"}
{"fact_id":"csep_12","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Employment permit is NOT a residence permission. Must obtain visa (if required) from Irish Embassy/Consulate"}
{"fact_id":"csep_13","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Must notify Department within 4 weeks on prescribed form. Up to 6 months to seek alternative employment"}
{"fact_id":"csep_14","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/permit-types/critical-skills-employment-permit/","current_quote":"Permit must be returned within 4 weeks of employment termination. Soft PDF copy may be emailed to employmentpermits@enterprise.gov.ie"}
{"fact_id":"csep_15","source_url":"https://enterprise.gov.ie/en/what-we-do/workplace-and-skills/employment-permits/fees/","current_quote":"Dependant/Partner/Spouse Employment Permit: No fee"}
```

Both pages fetch cleanly (200; CSEP 45KB, fees 33KB), so `source_unreachable` should not occur.
Ask for the contiguous run that states each claim, and `not_found` where the page does not state
it — `csep_3`'s refund clause is the one already known to fall in that bucket.
