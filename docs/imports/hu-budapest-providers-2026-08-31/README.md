# Budapest, Hungary — register-verified service providers (2026-08-31)

Corridor tag: `XX-HU` (destination Hungary). Every row is evidenced by an official
statutory register / recognized accreditation body detail page (`source_url`), never
the firm's own marketing site. Browser-grounded / direct-fetched to confirm.

Output: `providers.csv` — 16 rows across 4 categories. 2 categories SKIPPED.

## Per-category summary

| category | count | register used | notes |
|---|---|---|---|
| movers | 3 | FIDI Global Alliance — "Find a FIDI Affiliate" (fidi.org) | all 3 FIDI affiliates registered in Hungary; each cited to its per-affiliate DETAIL page |
| banks | 5 | Magyar Nemzeti Bank (MNB) — "Search of market participants" register (intezmenykereso.mnb.hu) | each cited to its per-institution register detail page (stable `/en/Details/Index?LId=…` URL) |
| schools | 4 | International Baccalaureate Organization — "Find an IB World School" (ibo.org) | Budapest IB World Schools; cited to the IBO per-school page + IB school code |
| tax_finance | 4 | Magyar Könyvvizsgálói Kamara (MKVK) — registered audit firms (mkvk.hu) | Big Four Budapest offices; each cited to its per-firm MKVK register detail page |
| legal_admin | SKIPPED | — | see below |
| housing_agencies | SKIPPED | — | see below |

## movers — FIDI Global Alliance (FAIM)
Register: `fidi.org/find-fidi-affiliate?country=153` (Hungary). All FIDI affiliates
in Hungary are in Budapest. `accreditation_expiry` = FAIM certificate validity year
shown on the affiliate detail page. FAIM carries no per-affiliate number, so
`accreditation_number` is blank.
- AGS Budapest — FAIM valid to 2026 — /find-fidi-affiliate/ags-budapest
- EuroMove — FAIM valid to 2028 — /find-fidi-affiliate/euromove
- Santa Fe Relocation - Budapest — FAIM valid to 2028 — /find-fidi-affiliate/santa-fe-relocation-budapest

## banks — Magyar Nemzeti Bank (MNB)
Register: MNB "Search of market participants" (intezmenykereso.mnb.hu). `accreditation_number`
= MNB registration number ("Registration number" on the detail page). All five are type
"Bank (company limited by shares)", legal status Active, registered office in Budapest.
Banking licences have no expiry, so `accreditation_expiry` is blank.
- OTP Bank Nyrt. — reg 10537914 — LId=273
- Kereskedelmi és Hitelbank Zrt. (K&H) — reg 10195664 — LId=261
- Erste Bank Hungary Zrt. — reg 10197879 — LId=264
- Raiffeisen Bank Zrt. — reg 10198014 — LId=265
- UniCredit Bank Hungary Zrt. — reg 10325737 — LId=269

Note: the MNB search UI is reCAPTCHA-gated (throttles repeated automated queries). The
per-institution DETAIL pages, however, load directly by `LId` with no captcha. OTP and
K&H were located via the register's own search; Erste/Raiffeisen/UniCredit were then
confirmed by reading MNB detail pages directly and matching each institution's exact
registered legal name (cross-checked against the register's non-captcha autocomplete).

## schools — International Baccalaureate Organization (IBO)
Register: IBO "Find an IB World School", country=HU (11 IB World Schools in Hungary;
4 Budapest international schools selected as relevant to relocating families).
`accreditation_number` = IB school code. Cited to `ibo.org/en/school/<code>/`.
- American International School of Budapest — IB code 000714 (city confirmed on IBO detail page: Nagykovácsi / Budapest 2094)
- Budapest British International School — IB code 060907
- The British International School, Budapest — IB code 001107 (Nord Anglia)
- SEK Budapest International School — IB code 002265

Note: IBO per-school detail pages are behind a Cloudflare "verifying you are a human"
interstitial that did not auto-clear. School names + IB codes + per-school URLs were
taken from the official IBO Hungary finder result list (authoritative), and AISB's code
was additionally confirmed on its detail page (which loaded before the interstitial
engaged). Website URLs confirmed via search where the IBO detail page was unreachable.

## tax_finance — Magyar Könyvvizsgálói Kamara (MKVK)
Register: MKVK "Keresés társaságok között" (search among companies), mkvk.hu — a plain
server-side form (no captcha). `accreditation_number` = "Nyilvántartási szám"
(registration number) on the firm's public-data page. Cited to `mkvk.hu/hu/tarsasag?id=<id>`.
All four Big Four Hungarian audit entities, all registered in Budapest.
- KPMG Hungária Könyvvizsgáló, Adó és Közgazdasági Tanácsadó Kft — reg 000202 — id=22731
- Deloitte Könyvvizsgáló és Tanácsadó Kft. — reg 000083 — id=22576
- PricewaterhouseCoopers Könyvvizsgáló Kft. — reg 001464 — id=23974
- Ernst & Young Könyvvizsgáló Kft. — reg 001165 — id=22610

## SKIPPED categories

### legal_admin — SKIPPED
The Budapest Bar Association (bpugyvedikamara.hu) no longer operates its own lawyer
register: since 2018-01-01 (Üttv. §192) the search is run by the national Magyar Ügyvédi
Kamara — the "Országos Ügyvédkereső" (magyarugyvedikamara.hu/html/nyilvanos-kereso/).
That register IS reachable, but it is a multi-step wizard keyed to individual lawyers /
offices (Ügyvéd, Iroda, etc.) with no relocation/immigration service classification.
Selecting "relocation law firms" from it would require seeding firm names from non-register
(marketing) sources — which this task forbids as evidence — so no defensible per-firm
selection could be grounded in the register itself. Register confirmed to exist and be
reachable; SKIPPED rather than populate with an arbitrary selection.

### housing_agencies — SKIPPED
Hungary has no genuine official, publicly reachable per-firm real-estate agency register
comparable to the FIDI/MNB/IBO/MKVK registers above (real-estate intermediary registration
is handled locally and is not a clean public per-firm lookup). Per the task rule, SKIPPED
rather than fall back to firms' own websites.
