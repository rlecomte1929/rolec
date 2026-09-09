# When `applies_to_nationality_classes` may be NULL (Ireland)

AIQ-2037. Read-only decision: **affirm NULL** on six approved IRELAND `purpose='employment'`
rows. No bulk UPDATE.

## Doctrine

Two different things share one column:

| Kind | Scope | NULL? |
|---|---|---|
| **Immigration pathway** (permit, entry visa, IRP, free-movement registration) | Always a nationality class (`THIRD_COUNTRY`, `EU_EEA`, `OWN_NATIONAL`, or a combination that is still a class) | **Never.** NULL here serves a visa track to a free mover. |
| **Statutory obligation that turns on residence or employment** (Irish tax residence, PAYE/RPN, emergency tax *as a payroll consequence of an unregistered job*, PRSI compulsion, combining social-insurance contributions) | Presence, a job, or a claim — not passport | **Yes, after a human affirms it.** |

`backend/imports/otto/mappings.py` `NATIONALITY_CLASSES` still has no `"any"` and still
refuses to write NULL for **new immigration content**. The six live NULLs are not a licence
for the importer; they are reviewed catalog. A future tax/PRSI row may be NULL only when a
reviewer records that it is universal statutory content, same as below.

`scripts/check_nationality_scope.py` already treats tax, PRSI and social-charge liability as
deliberately not permission content.

## Six IRELAND rows — 2026-09-09

Titles as served / seeded (`backend/seeds/facts/IE.yaml`). All six: **affirm NULL**.

| # | Title | Pillar | Decision | Why |
|---|---|---|---|---|
| 1 | Irish tax residence turns on 183 days in a year, or 280 across two | EMPLOYMENT | Affirm NULL | Day-count residence is a Revenue test on presence, not nationality. |
| 2 | Split-year treatment can be requested for the year of arrival | EMPLOYMENT | Affirm NULL | Arrival-year treatment of employment income; available to a resident regardless of passport. |
| 3 | The employer's RPN drives Income Tax, USC and PRSI deductions | EMPLOYMENT | Affirm NULL | PAYE mechanics once a job exists. |
| 4 | Register the job with Revenue through myAccount to avoid emergency tax | EMPLOYMENT | Affirm NULL | First-job registration with Revenue. An Irish or Spanish employee starting PAYE is in the same machinery. |
| 5 | PRSI is compulsory for most employees between 16 and pensionable age | SOCIAL_SECURITY | Affirm NULL | Compulsion follows employment in the State, not nationality. |
| 6 | Contributions paid abroad can be combined with Irish contributions | SOCIAL_SECURITY | Affirm NULL | Coordination / aggregation of contributions; nationality is not the gate. |

Not in this six: immigration-scoped Ireland rows (employment permit, entry visa, IRP) stay
`THIRD_COUNTRY` (or the class the row already carries). Do not NULL those.

Emergency-tax *rate cliff* content that is only a consequence of an unregistered PAYE job is
the same statutory family as (4); it was not one of the six NULL rows named on the card, so
it is not re-scoped here.

## Serving counts (no rescope)

Card snapshot **2026-08-21** (failure evidence):

```
GET /api/public/corridor-requirements?from=ES&to=IE&employee_type=PERMANENT&purpose=employment&nationality=ES
→ 7  (the six NULLs + free-movement notice)

…&nationality=IN
→ 20 (the six NULLs + 14 THIRD_COUNTRY rows)
```

Re-measured **2026-09-09** with the same query (curl; urllib is Cloudflare-403ed):

| nationality | `.requirements \| length` |
|---|---|
| ES | 164 |
| IN | 207 |

The list is longer than in August (more approved destination content now ships on the public
seam). The **gap** (IN − ES = 43) is still the nationality-scoped immigration track; the six
payroll/tax rows remain on **both** tracks because NULL was affirmed, not because they were
forgotten. No row was rescoped, so no count change is attributed to this ticket.

## Fail-open labels (related, not a data change)

`applies_to_matcher.nationality_applies` still fails **open** on an unrecognised nationality
label. That behaviour is unchanged. It now `log.warning`s so an alias like the old
`EEA/EU/Swiss` cannot un-gate a batch with no signal (see AIQ-2037 card addendum / PR #2033).
