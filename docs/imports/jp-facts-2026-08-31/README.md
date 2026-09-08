# JP facts — Tokyo hub, third-country-national professional (non-EEA)

Batch date: 2026-08-31
Destination: JP · Corridor: JP · Perspective nationality: non-EEA · Status: professional
Records: 13 (all `confidence: high`, all `non_obvious: true`, all `needs_lawyer_review: false`)

## Sourcing method (important — read this)

All sources are **official Japanese government** domains only:
- `moj.go.jp/isa` — Immigration Services Agency of Japan (ISA), an external bureau of the Ministry of Justice.
- `nta.go.jp` — National Tax Agency (English income-tax guide).

The interactive sandbox browser in this environment was non-functional (it returned an
unrelated cached page — `fidi.org` — for every navigation, on every tab), and `mofa.go.jp`
plus the `*.emb-japan.go.jp` embassy network hard-block automated fetches (HTTP 403 "Access
Denied", Akamai edge). Because of this, **facts were grounded by downloading the official
source PDF directly from the government domain and extracting its text**, then asserting each
`evidence_quote` is a verbatim, contiguous substring (<200 chars) of that extracted text.
Every quote passed that automated substring check — `quote_verbatim_confirmed: true` reflects
a programmatic match against the official document's own text, not a manual eyeball.

CoE and MOFA-owned visa content was sourced from the **ISA** side of the same government
(the ISA "What Is Immigration Control Administration?" booklet) rather than MOFA, since MOFA
was unreachable.

## Facts and their sources (quote browser/fetch-confirmed verbatim = YES for all)

| # | fact_key | pillar | source_url | quote confirmed verbatim |
|---|----------|--------|-----------|--------------------------|
| 1 | JP:immigration:coe_before_visa | IMMIGRATION | https://www.moj.go.jp/isa/content/930003057.pdf | YES (p7) |
| 2 | JP:immigration:residence_card_issued_on_arrival | IMMIGRATION | https://www.moj.go.jp/isa/content/001453431.pdf | YES (p2) |
| 3 | JP:housing:municipal_address_registration_14days | HOUSING | https://www.moj.go.jp/isa/content/930001396.pdf | YES (p1) |
| 4 | JP:employment:notify_contracting_org_change_14days | EMPLOYMENT | https://www.moj.go.jp/isa/content/930001396.pdf | YES (p2) |
| 5 | JP:immigration:hsp_points_70 | IMMIGRATION | https://www.moj.go.jp/isa/content/001453431.pdf | YES (p8) |
| 6 | JP:immigration:special_reentry_within_1year | IMMIGRATION | https://www.moj.go.jp/isa/content/001453431.pdf | YES (p8) |
| 7 | JP:employment:pension_enrolment_mandatory | EMPLOYMENT | https://www.moj.go.jp/isa/content/001450885.pdf | YES (p90 / "7th edition" guidebook) |
| 8 | JP:healthcare:public_health_insurance_mandatory | HEALTHCARE | https://www.moj.go.jp/isa/content/001450885.pdf | YES (p84) |
| 9 | JP:tax:my_number_required_for_banking | TAX | https://www.moj.go.jp/isa/content/001450885.pdf | YES (p34) |
| 10 | JP:tax:non_permanent_resident_definition | TAX | https://www.nta.go.jp/english/taxes/individual/pdf/incometax_2021/04.pdf | YES (p1) |
| 11 | JP:tax:non_permanent_resident_taxation_scope | TAX | https://www.nta.go.jp/english/taxes/individual/pdf/incometax_2021/04.pdf | YES (p3) |
| 12 | JP:housing:foreign_licence_conversion_gaimen_kirikae | HOUSING | https://www.moj.go.jp/isa/content/001450885.pdf | YES (p118) |
| 13 | JP:family:dependent_work_permission_required | FAMILY | https://www.moj.go.jp/isa/content/001450885.pdf | YES (p25) |

Source documents (official ISA/MOJ / NTA):
- `930003057.pdf` — ISA, *What Is Immigration Control Administration?* (Certificate of Eligibility; visa-abroad-before-entry; Article 19-2 activity permission).
- `001453431.pdf` — ISA, *Procedures for Entry/Residence* (residence-card issuance; HSP points; re-entry / special re-entry).
- `930001396.pdf` — ISA, *Procedure at a Municipal Office* (14-day address notification; 14-day contracting-organisation notification; revocation grounds).
- `001450885.pdf` — ISA, *Guidebook (7th edition)* / living-in-Japan procedures (Individual Number; National & Employees' Health Insurance; National & Employees' Pension; foreign-licence conversion; deportation for unpermitted paid work).
- NTA `incometax_2021/04.pdf` — National Tax Agency, *Income Tax Guide* (resident / non-permanent resident classification and scope of taxable income).

## Notes / gaps
- The specific **"28 hours per week"** cap on a Dependent's permitted part-time work could NOT
  be grounded from a fetchable official English source (the ISA English HTML guide pages
  301-redirect to the JP homepage for non-interactive clients). Per the no-invention rule, fact
  #13 states the **permission requirement** (verbatim-grounded) but deliberately omits the
  28-hour number.
- MOFA (`mofa.go.jp`) and Japanese-embassy visa pages were unreachable (403). The CoE fact is
  therefore grounded on the equivalent ISA statement instead.
- All 13 quotes were verified by an automated exact-substring test against the downloaded
  official document text.
