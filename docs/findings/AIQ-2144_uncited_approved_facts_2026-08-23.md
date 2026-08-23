# AIQ-2144 — the 9 uncited approved facts: quotes proposed, 2 demotions recommended

**Nothing in this document has been written to the database.** These are proposals for
review, per the card's constraint that a quote must not be machine-asserted.

Date: 2026-08-23 · 8 pages fetched, all HTTP 200 · probes are literal-string matches
against the page text, not token heuristics.

---

## Summary

| outcome | n |
|---|---:|
| Quote found — propose to attach | 7 |
| **Fact is WRONG — recommend demote + correct** | 1 |
| **Specific unsupported by its own citation — recommend split or demote** | 1 |

The exercise was framed as "add the missing quotes". Two of the nine turned out not to be
citation gaps at all. That is the argument for doing this by reading the source rather than
by backfilling: a backfill would have attached a plausible passage to a claim the page
contradicts.

### Scope note
These 9 are the ones that are **served**: `status='approved'`, no `evidence_quote`, and
`evidence_verified IS NULL` — which the reader treats as passing, because it filters
`COALESCE(evidence_verified, TRUE) = TRUE`. A further 6 approved facts also lack a quote
but are already `evidence_verified = false` and therefore excluded from serving. They are
not in scope here.

---

## A. Recommend DEMOTE — the fact is wrong

### 1. `ep_fcf_advertising` (`b317c3d6-9b83-4806-a93b-f658da5d629c`)

**Our fact:** "the employer must advertise the vacancy on MyCareersFuture.sg for at least
**28 calendar days** and fairly consider all Singaporean applicants under the Fair
Consideration Framework (FCF)"

**The cited page says:**

> "Duration of advertisement — The MyCareersFuture job advertisement must be open for at
> least **14 consecutive days** to allow job seekers to view and apply for the vacancy.
> This also applies if you repost an advertisement that has closed."

— <https://www.mom.gov.sg/passes-and-permits/employment-pass/consider-all-candidates-fairly>

**28 is not a rounding of 14; it is double.** An employer following our roadmap waits two
unnecessary weeks before they may submit the EP application. This is an approved,
`confidence='high'`, currently-served fact.

**Recommended:** set `evidence_verified = false` now so it stops being served, then correct
`fact_text` to 14 consecutive days and attach the quote above. The correction is a separate,
human-confirmed edit — I have not made it.

> Worth noting for whoever corrects it: the same page also says a *repost with updated
> details* must stay open "at least another 14 consecutive days". Neither figure is 28.

## B. Recommend SPLIT or DEMOTE — the specific is not in the source

### 2. `ie_csep_occupation` (`7f8c9670-2e3c-487f-9ca2-a5f7895f3db6`)

**Our fact:** "…the role must appear on the Critical Skills Occupations List (Schedule 3 of
the Regulations, updated by SI 213 of 2026, effective 13 May 2026). Roles earning
**€68,911 or more annually**…"

**Supported** — the page states the list, the Schedule and the instrument:

> "This list is set out in **Schedule 3 of the Regulations**. This list is effective from
> **13 May 2026**, when **SI 213 of 2026** came into effect."

**Not supported** — the page contains **no salary figure at all**. Not €68,911, not any
euro amount, not any number of the form `NN,NNN`. The threshold is published elsewhere.

**Recommended:** either drop the salary sentence from this fact and attach the quote above
(the remainder is fully supported), or add a second `source_url` for the page that does
publish the threshold. Do not attach the quote as-is — it would certify a figure the cited
page does not contain, which is the "unsupported specifics" defect class AIQ-2018 names.

## C. Quote found — propose to attach

Each quote below is verbatim from the fact's own `source_url`.

| # | fact_key | proposed `evidence_quote` |
|---|---|---|
| 3 | `ie_gep_lmnt` | "any employment permit application where a Labour Market Needs Test is required must have published a EURES ad for at least 28 consecutive days before a valid application can be submitted" |
| 4 | `csep_eligibility` | "they are only issued in respect of a job offer that is at least a minimum of 2 years' duration. For job offers of less than 2 years, a General Employment Permit may be applied for." |
| 5 | `ep_dependants_pass` | "children under 21 years old, including legally adopted children. If your family members are not eligible for a Dependant's Pass, they may qualify for a Long-Term Visit Pass." |
| 6 | `ep_application_fee` | "Pay the $105 fee by GIRO, Visa, Mastercard or Amex" + "Pay the fees using GIRO, Visa, Mastercard or Amex: $225 for each pass" |
| 7 | `ep_route_overview` | "The Employment Pass allows foreign professionals, managers, executives and technicians to work in Singapore. Candidates need to earn at least $5,600 a month." |
| 8 | `ep_compass_points` | "candidates will need to pass a 2-stage eligibility framework: Stage 1 Earn at least the EP qualifying salary, which is benchmarked to the top 1/3 of local PMET salaries by age. Stage 2 Unless exempted, pass the points-based Complementarity Assessment (COMPASS)" |
| 9 | `ep_salary_threshold` | "All (except financial services) $5,600 (increases progressively with age from age 23, up to $10,700 at age 45 and above) $6,000 (increases progressively with age from age 23, up to $11,500…" |

### One caveat on #9, flagged rather than asserted

The table that quote comes from is headed **"Minimum qualifying salary for new applications
from 1 Jan 2027, and for renewal of passes expiring from 1 Jan 2028"**. Today is 2026-08-23,
so on that page the figures read as future-effective.

The EP *overview* page, however, states in the present tense: "Candidates need to earn at
least $5,600 a month."

I have not resolved which table governs an application submitted today — the eligibility
page may carry both a current and a forthcoming table, and my extraction matched one of
them. **Someone should confirm which applies before this quote is attached**, because
attaching the 2027 table to a present-tense fact would be the same class of error as A.1,
just quieter.

## What I did NOT do

- No write to `requirement_facts`. No quote attached, no `evidence_verified` flipped, no
  `fact_text` corrected.
- No source invented. Every quote above is verbatim from the fact's existing `source_url`.
- The 6 already-`false` uncited facts were left alone — they are not served.

## Recommended order

1. Demote A.1 (`ep_fcf_advertising`) — it is wrong and live. This is the only urgent one.
2. Resolve the C.9 caveat.
3. Attach the 7 quotes (6 unconditionally, #9 after step 2).
4. Decide B.2: split the fact, or add the second source.
