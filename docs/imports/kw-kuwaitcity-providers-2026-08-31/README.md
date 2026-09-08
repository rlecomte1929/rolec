# Kuwait City provider sourcing — 2026-08-31

Corridor tag: `XX-KW` (all rows). Every row is evidenced by an official statutory register or
recognised accreditation body — never the firm's own marketing site. Firms not on a real register
were excluded; three categories with no reachable per-firm register were SKIPPED (worklist below).

Output: `providers.csv` — 10 rows across 3 categories.

## Categories INCLUDED

### movers — 1 firm
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate" (per-affiliate detail page).
- **Count:** 1 (Kuwait has exactly one FIDI/FAIM affiliate — not padded).
- Kuwait filter (`?country=197`) returns a single affiliate:
  **GULF AGENCY COMPANY (KUWAIT) LTD** — FAIM certified, certificate validity expiry **2027**.
  Detail page: https://www.fidi.org/find-fidi-affiliate/gulf-agency-company-kuwait-ltd
  (legal name on FIDI: "GULF AGENCY CO LIMITED FOR SHIPPING / SALAH RASHID BURISLEE & PARTNER W.L.L";
  address Dajeej Block 1, Kuwait).

### banks — 6 firms
- **Register:** Central Bank of Kuwait (CBK), Supervision → Regulated Entities → Kuwaiti Banks.
  Two register pages cited:
  - Conventional: https://www.cbk.gov.kw/en/supervision/regulated-entities/kuwaiti-banks/conventional-banks
  - Islamic: https://www.cbk.gov.kw/en/supervision/regulated-entities/kuwaiti-banks/islamic-banks
- **Count:** 6 major retail banks, all HQ'd in Kuwait City (Sharq / Qibla districts):
  - Conventional register: National Bank of Kuwait, Gulf Bank, Burgan Bank, Commercial Bank of Kuwait.
  - Islamic register: Kuwait Finance House, Boubyan Bank.
- CBK register pages list name/address/website but no public licence number → `accreditation_number` blank,
  no expiry shown → `accreditation_expiry` blank. Full conventional register also includes Al Ahli Bank of
  Kuwait; full Islamic register also includes Kuwait International Bank and Warba Bank — all available on the
  same two CBK pages if more banks are wanted later.

### schools — 3 firms
- **Register:** International Baccalaureate Organization, "Find an IB World School" (per-school page + IB code).
- **Count:** 3 IB World Schools within the Kuwait City metropolitan area.
  - **American International School Kuwait** — Salmiya (Kuwait City metro, Hawalli) — IB code **000657** —
    PYP/MYP/DP — https://www.ibo.org/school/000657/
  - **Little Land Nursery and Montessori Center** — Faiha, Kuwait City (Capital) — IB code **060251** —
    PYP — https://www.ibo.org/school/060251/
  - **Reborn Kids Education Academy (RKEA)** — Al-Siddeeq, Kuwait City metro (Hawalli) — IB code **051906** —
    PYP — https://www.ibo.org/school/051906/
- **Excluded (in Kuwait, but NOT Kuwait City):** *Kuwait Bilingual School* (IB code 006924,
  https://www.ibo.org/school/006924/, PYP/MYP/DP) — located in **Al Jahra City**, a separate governorate
  ~30 km west of Kuwait City. It is the 4th (and last) IB World School in the country. Include only if the
  scope is widened from "Kuwait City" to country-level KW.
- IB authorization carries no expiry on the school page → `accreditation_expiry` blank; `accreditation_number`
  holds the IB school code.
- Note: the IB country page for Kuwait states "5 IB World Schools", but the live "Find an IB World School"
  register returns only 4 authorised schools for Kuwait (the fifth is not currently listed as authorised).

## Categories SKIPPED (no reachable per-firm official register)

Per the hard rule, a category is skipped rather than sourced from firm marketing sites or third-party
directories. Re-source worklist below.

### legal_admin — SKIPPED
- No public, searchable official register of licensed lawyers / law firms from the **Kuwaiti Lawyers
  Association** (Kuwait Bar) is reachable online. Only third-party directories exist (edarabia, Legal 500,
  HG.org, PathLegal) — not acceptable as a statutory register.
- **Re-source:** check whether the Kuwaiti Lawyers Association (jamiya) publishes a members roster; check
  the Ministry of Justice for a licensed-lawyer lookup. If a genuine gov/association register with per-firm
  or per-lawyer entries becomes reachable, add rows citing it.

### tax_finance — SKIPPED
- No reachable public **Ministry of Commerce and Industry (MOCI Kuwait)** register/list of licensed auditors
  was found (Qatar's MOCI publishes an "Auditors Lists" page; Kuwait's does not appear to expose an
  equivalent public list). Kuwait auditors are registered with MOCI but the roster is not a reachable
  public register.
- **Re-source:** probe moci.gov.kw e-services for an "auditors register / accountants roll"; check the
  Kuwait Association of Accountants and Auditors (KAAA) for an official members list. Add rows only against
  a genuine statutory/association register.

### housing_agencies — SKIPPED
- Kuwait's MOCI "Real Estate Broker System" (e.gov.kw / moci.gov.kw digital real-estate portal) is a
  transaction-processing / licence-application e-service, **not** a public searchable register of named
  licensed brokers, and was reported unavailable at time of check. No per-firm register page to cite.
- **Re-source:** re-check the MOCI real-estate portal for a public "licensed brokers" lookup; if it exposes
  named, verifiable broker licences, add rows citing the per-broker/licence page.

## Registers used (summary)
| Category | Register / body | Reachable | Rows |
|---|---|---|---|
| movers | FIDI Global Alliance (FAIM) — fidi.org affiliate detail page | yes | 1 |
| banks | Central Bank of Kuwait — Regulated Entities (Kuwaiti banks) | yes | 6 |
| schools | International Baccalaureate Organization — Find an IB World School | yes | 3 |
| legal_admin | Kuwaiti Lawyers Association / MoJ | no public register | SKIP |
| tax_finance | MOCI Kuwait auditors list / KAAA | no public register | SKIP |
| housing_agencies | MOCI real-estate broker register | e-service only, not a register | SKIP |

All register pages were browser-grounded on 2026-08-31 (FIDI affiliate detail, both CBK bank register
pages, and each IBO school page were opened and read directly).
