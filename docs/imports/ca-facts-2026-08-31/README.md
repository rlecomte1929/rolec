# Canada destination facts (2026-08-31)

Canada opened as a destination (coverage-master rank 5, Toronto hub), greenfield. Browser-grounded
against **canada.ca** (federal) and **ontario.ca** (provincial) by a Claude Code research subagent;
`verify_ledger` re-fetched all 9 pages and confirmed **16/16 quotes verbatim, 0 rejected**.

## What landed (16 facts → 10 requirement_items, all `pending` / `representative`)
| requirement_item (topic) | pillar | facts | source |
|---|---|---|---|
| Employer-specific work permit | EMPLOYMENT | 2 | canada.ca (IRCC) |
| Labour Market Impact Assessment (LMIA) | EMPLOYMENT | 1 | canada.ca |
| LMIA-exempt work permits (International Mobility Program) | EMPLOYMENT | 1 | canada.ca |
| Global Talent Stream is LMIA-required | EMPLOYMENT | 1 | canada.ca |
| Express Entry is a permanent-residence route | RESIDENCE | 1 | canada.ca |
| Social Insurance Number (SIN) | SOCIAL_SECURITY | 2 | canada.ca (Service Canada) |
| Residents are taxed on worldwide income + residency/filing | SOCIAL_SECURITY | 4 | canada.ca (CRA) |
| OHIP has no waiting period + eligibility | HEALTHCARE | 2 | ontario.ca |
| 60 days to switch to an Ontario licence | IDENTITY | 1 | ontario.ca |
| Ontario licence exchange only with an agreement | IDENTITY | 1 | ontario.ca |

All `applies_to.nationality = non-EEA` → THIRD_COUNTRY (Canada is non-EEA). Scope guard exit 0.
1 fact `needs_lawyer_review` (day-one tax-residency determination — a treaty tie-breaker can change it).

## Code this batch required
- `requirements_country_key.py`: `"CA": "CANADA"` (promote-blocker, like Ecuador) + `test_canada_is_covered`.
- `backend/imports/otto/parsers.py` `_OFFICIAL_SUFFIXES`: added **`canada.ca`** (the federal portal — the
  legacy `gc.ca` suffix does NOT match it, so every federal fact scored UNOFFICIAL) and **`ontario.ca`**
  (Government of Ontario). 6th too-narrow-allowlist instance.

## Load record (Runbook A)
```
verify_ledger.py facts.ndjson --apply         -> clean 16, importable 16, promotable 16, 0 rejected
import_otto_facts.py clean.ndjson --apply --batch-id ca-facts-2026-08-31   -> staged 16 (new)
park CA-immig-2026-08-12 (8 'ready') -> flip mine new->ready -> promote(country='CA') -> restore CA-immig
  -> 9 requirement_items; SIN topic refused (2 pillars) -> normalised SIN pillar to SOCIAL_SECURITY -> +1 = 10
verify: CANADA 0->10; 0 pre-existing changed; expert_verified=0; all 16 staged -> promoted
```

**Honest corrections the research caught:** the OHIP "3-month waiting period" no longer exists (removed
2020) — landed the corrected immediate-coverage fact instead; the Global Talent Stream is LMIA-*required*
(a fast TFWP stream), not LMIA-exempt (the exempt route is the IMP).

**Gate remaining (human):** approve at `/admin/countries` (CANADA). Serving also needs the `"CA":"CANADA"`
catalog line merged (PR #2138) + deployed.
