# ie-isd-visa-required-2026-08-22 — does a national of X need an Irish visa?

**This is a lookup table, not a fact stream.** Nothing here promotes to `requirement_items`,
and `manifest.target_table` is deliberately `null`. It is reference data consumed at request
time by `backend/app/services/isd_visa_required.py`.

## Why it exists

`corridors/ES_IE/pathways/CSEP_2026/v1.yaml:108` has always declared:

```yaml
visa_required_nationality:
  source: EXTERNAL_LOOKUP
  lookup: isd_visa_required.{nationality_iso}
```

The lookup did not exist, so `roadmap_corridor_overlay` emitted an *unasserted* advisory
telling the mover to go and ask Irish Immigration Service Delivery or an embassy — the one
question the corridor is built to answer. Commissioned as dependency **A3** in
`docs/otto/andrea-denis-brief-2026-08-21.md`, named as a dependency by
`es-ie-thirdcountry-requirements-2026-08-22`, never delivered. Built here in-repo instead.

## Source, and why this one

`https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/visa-requirements-for-entering-ireland/`

ISD (`irishimmigration.ie`) is the more authoritative publisher and was preferred, but it
serves this list through a JavaScript table (Ninja Tables id 19077) that does not survive
HTML fetching. Citizens Information is the Citizens Information Board's public service — 
official-adjacent, not the Department of Justice's own instrument. Hence
`verification_status: representative`, and the manifest's `review_note` says to corroborate
against ISD before treating it as better.

## What it holds

| | count |
|---|---|
| visa-free nationalities | 45 |
| exemptions that are not nationality-based | 3 |
| preclearance rule | 1 |

## The three-valued contract

`visa_required()` returns `True` / `False` / **`None`**, and `None` is a real answer.

The page states the exempt list *positively* and never publishes its complement, so
"absent from the table means visa-required" is sound **only once the input is a real ISO
code**. `nationality` is unvalidated free text and production already holds `'f'`,
`'asdas'` and `'1212'`. `False` for those would tell a visa-required national she needs
nothing; `True` would invent a requirement from a typo.

## Two things an ISO code cannot settle

Both are quoted verbatim in the artifact and surfaced to the reader rather than swallowed:

- **an EEA/Swiss residence card** held as the family member of a citizen living outside
  their own home country;
- **the UK short-stay visa waiver** / British-Irish Visa Scheme.

This is live, not theoretical. Andrea is Venezuelan in Spain; her spouse is **Macedonian**,
so no carve-out applies and both need a `D` visa. Had the spouse been French, the identical
facts would have made her **visa-exempt**.

## Preclearance — the dangerous half of a "no"

A Critical Skills permit holder's spouse from a **visa-exempt** country (US, Brazil, Canada,
Australia) reads "no visa needed" and books a flight. They still need preclearance before
travelling. Measured 2026-08-22: **0 of 42** Irish `requirement_items` mention preclearance
at all, so the visa-exempt advisory carries it until a requirement row does.

## Integrity

`backend/tests/test_isd_visa_required.py` re-hashes the artifact against the manifest and
re-counts both collections. `scripts/check_otto_batches.py` correctly `[SKIP]`s the
record-level checks here ("manifest declares none … does not apply to a reference batch").

## Re-checking it

The exempt table changes by ministerial order. Re-fetch the source, diff
`visa_free_nationalities`, and if it moved: update the artifact, re-hash into the manifest
(the test will fail until you do), and say what changed and when it took effect.
