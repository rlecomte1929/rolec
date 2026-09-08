# Hong Kong service providers — register-verified sourcing (2026-08-31)

Corridor tag: `XX-HK` (destination = Hong Kong SAR). Every row is evidenced by an official
statutory register or recognized accreditation body — the `source_url` is the register page,
not the firm's own marketing site. Firms not confirmable on a register were excluded, and two
categories were skipped rather than sourced from self-declared firm sites.

`providers.csv` header:
`corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry`

## Counts

| category | rows | register used | status |
|---|---|---|---|
| movers | 4 | FIDI Global Alliance — FAIM affiliate register (per-affiliate detail pages) | done |
| banks | 4 | HKMA Register of Authorized Institutions (per-institution pages) | done |
| schools | 4 | IB — Find an IB World School (ibo.org, per-school pages) | done |
| legal_admin | 4 | The Law Society of Hong Kong — The Law List (per-firm pages) | done |
| housing_agencies | 0 | Estate Agents Authority (EAA) Licence List | SKIPPED |
| tax_finance | 0 | HKICPA practice-unit register | SKIPPED |

Total: 16 rows across 4 categories.

## Per-category notes

### movers — FIDI Global Alliance (FAIM)
Register: `fidi.org/find-fidi-affiliate`. Each row cites the per-affiliate **detail** page
(`fidi.org/find-fidi-affiliate/<slug>`), not the country-filter search URL. All four are
FIDI-FAIM Plus certified with a Hong Kong office confirmed on the detail page.
`accreditation_expiry` is the FAIM certification expiry year shown on the detail page. FIDI
does not publish a per-affiliate membership number, so `accreditation_number` is blank.
- Asian Tigers Hong Kong (K.C. DAT Ltd) — Kwun Tong — FAIM Plus, exp 2029
- Santa Fe Relocation Hong Kong (Santa Fe Transport International Ltd) — Wan Chai — FAIM Plus, exp 2026
- AGS Four Winds International Movers Ltd — Kwai Chung — FAIM Plus, exp 2028
- Allied Moving Services (HK) Ltd — Wan Chai — FAIM Plus, exp 2027

### banks — Hong Kong Monetary Authority (HKMA)
Register: HKMA "Register of AIs & LROs" at `vpr.hkma.gov.hk`. Each row cites the
per-institution register page (`.../register-of-ais-and-lros/info/<id>`) and each was
confirmed with classification "Licensed Bank". The register does not expose a public licence
number (only the classification), so `accreditation_number`/`accreditation_expiry` are blank.
The four Hong Kong-incorporated retail entities a relocator would actually use were chosen
(HSBC, Hang Seng, Standard Chartered HK, Bank of China HK), all also on HKMA's D-SIB list.

### schools — International Baccalaureate (IB)
Register: IB "Find an IB World School" on `ibo.org`. Each row cites the school's IBO page and
carries the IB school code in `accreditation_number`. NOTE on URL form: the task named
`ibo.org/en/school/<id>`; that path returns a Cloudflare bot challenge and is not the live
canonical page. The live, browser-confirmed register page is
`ibo.org/programmes/find-an-ib-school/ibap/<letter>/<slug>/` — that is what is cited, with the
IB code captured separately. Confirmed HONG KONG + programmes on each page:
- German Swiss International School — IB code 006164 (DP)
- Chinese International School — IB code 000637 (DP, MYP)
- Hong Kong Academy — IB code 002218 (PYP, MYP, DP)
- French International School of Hong Kong — IB code 000514 (DP)

### legal_admin — The Law Society of Hong Kong (The Law List)
Register: `hklawsoc.org.hk` "The Law List" → Hong Kong Law Firms, which has reachable per-firm
pages (`Firm-Detail?FirmId=<id>`). The name filter (`?name=`) maps a firm to its FirmId. Each
row cites the per-firm page and each was confirmed as a listed HK solicitors' firm with a HK
address. The Law List does not publish a firm "licence number" (FirmId is an internal record
id, carried in the source_url only), so `accreditation_number` is blank. Firms chosen are
relocation-relevant (immigration / employment / family / private client):
- Deacons — FirmId 243 — Alexandra House, Central
- Tanner De Witt — FirmId 837 — Lippo Centre, Admiralty
- Withers — FirmId 947 — United Centre, Admiralty
- Baker & McKenzie — FirmId 30 — One Taikoo Place, Quarry Bay

## Skipped categories (with reason)

### housing_agencies — SKIPPED
Register exists: Estate Agents Authority (EAA) Licence List at
`eaa.org.hk/en-us/Licence-list`, with per-licence detail pages
(`.../Licensing/Licence-Detail/licId/<guid>`) that ARE directly fetchable and DO show the
company licence number (`C-######`), type, status and expiry — this was verified against
several live pages (e.g. Wanchai Property Real Estate Agency Ltd, C-084976, valid to
02/12/2026).

Why skipped: the only way to map a **named** agency to its `licId` GUID is the EAA Licence
List **name/number search, which is gated by an image Security Code (CAPTCHA)**. Bypassing
CAPTCHAs is out of policy, and GUID discovery via web search surfaced only unrelated
small/expired licensees (a salesperson S-717239; an expired company C-066887; two SPOB branch
statements), none of them relocation-relevant agencies (Centaline, Midland, Ricacorp, Savills,
JLL, Knight Frank, OKAY.com, Habitat). Rather than pad the file with random verified-but-
irrelevant local agencies, the category is skipped. To complete it, a human can run the EAA
Licence List name search (solving the Security Code) for the target agencies and read each
`licId` detail page — the detail-page format and field mapping are proven and ready.

### tax_finance — SKIPPED
The register named for this category is no longer reachable per-firm:
- HKICPA "Hong Kong CPA Practice Directory"
  (`hkicpa.org.hk/.../Find-a-CPA/Hong-Kong-CPA-Practice-Directory`) returns **404 / Page not
  found** (deprecated).
- HKICPA "Membership List (Public)" is an **individual-member** lookup by family-name initial,
  not a register of practice units / firms — no per-firm citable pages.
- Since the 2022 reforms the statutory register of CPA firms & corporate practices is
  maintained by the **AFRC** (`armies.afrc.org.hk/.../WWP_FE_FMCP_PublicRegisterList.aspx`,
  1,975 records). It is an ASP.NET **postback search form with no stable per-firm URLs**, so
  individual practices are not citable by link.
No CAPTCHA was involved here; the blocker is the absence of any reachable per-firm register
page. Per the task rule ("if reachable per-firm, cite it; else SKIP"), and to avoid citing
firms' own marketing sites, the category is skipped.

## Method / grounding notes
- Registers were opened and confirmed live on 2026-08-31 (FIDI, HKMA, IBO, Law Society via the
  browser and/or direct register fetch; EAA and HKICPA/AFRC inspected to establish
  reachability). The shared browser pane was under heavy concurrent contention, so some
  register content was confirmed by fetching the register's own server pages directly.
- No numbers were invented: FAIM expiry years, IB codes, HKMA classification, and Law List
  addresses are all taken verbatim from the register pages cited in `source_url`.
