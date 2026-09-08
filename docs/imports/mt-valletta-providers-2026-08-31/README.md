# Malta (Valletta / central Malta) — register-verified service providers

Corridor tag: `XX-MT` (every row). Sourced 2026-08-31. Every row is evidenced by an
official statutory register or recognized accreditation body — never the firm's own
marketing site. `website_url` is a convenience field only; the evidence is `source_url`.

## Summary

| Category | Rows | Register used | Status |
|---|---|---|---|
| movers | 0 | FIDI Global Alliance affiliate finder | **SKIPPED** (no Malta affiliate on register) |
| banks | 5 | MFSA Financial Services Register (Credit Institutions) | done |
| schools | 2 | IBO — Find an IB World School | done (only 2 exist in Malta) |
| tax_finance | 4 | MFSA Financial Services Register (Approved Auditors / CSP) | done |
| legal_admin | 4 | Malta Chamber of Advocates — Find a Lawyer directory | done |
| housing_agencies | 0 | Property Market Agency (PMA) Real Estate Licensing Register | **SKIPPED** (verify-only register, not browsable) |

Total rows: **15**.

## Per-category detail

### movers — SKIPPED
Register: FIDI Global Alliance affiliate finder (https://www.fidi.org/find-fidi-affiliate).
The finder's country filter lists **only countries that have at least one FAIM-accredited
affiliate**. Malta does **not appear anywhere in that list** (the Europe group runs
… Luxembourg, Moldova … with no Malta entry). Confirmed by reading the full country list in
the live page and by targeted `site:fidi.org` searches. There is therefore **no FIDI
affiliate with a Malta office** to cite a per-affiliate detail page for. Per the rules, the
category is skipped rather than padded with self-declared Maltese movers.

### banks — 5 rows
Register: **MFSA Financial Services Register** — the live app at https://fsr.mfsa.mt/
(embedded on https://www.mfsa.mt/financial-services-register/). Each firm was confirmed via
the register's own API (`/Licences/searchLicencesByLicenceHolder`) to hold a
**"Credit Institutions"** licence with status **"Licence Authorised"**.
`accreditation_number` = the register's entity id (the C-number / Malta Business Registry
company number shown against the licence holder). The register app has no stable per-firm
deep link (licence detail links carry ephemeral encrypted tokens), so `source_url` is the
register root; reproduce by searching the company name or C-number there.

- Bank of Valletta p.l.c. — C 2833 — Credit Institutions [Authorised]
- HSBC Bank Malta p.l.c. — C 3177 — Credit Institutions [Authorised]
- APS Bank p.l.c. — C 2192 — Credit Institutions [Authorised]
- BNF Bank plc — C 41030 — Credit Institutions [Authorised]
- Lombard Bank Malta p.l.c. — C 1607 — Credit Institutions [Authorised]

### schools — 2 rows
Register: **IBO — Find an IB World School** (https://www.ibo.org/programmes/find-an-ib-school/,
country code `MT`). The register returns **exactly two** IB World Schools in Malta (no
pagination). Each row cites the school's IBO page and its IB School code. Both websites in
`website_url` are the ones printed on the IBO detail page.

- St Edward's College — IB code **004556** — Birgu (Vittoriosa), Malta — DP, IB school since 2009 — https://www.ibo.org/school/004556/
- Verdala International School — IB code **000832** — Pembroke, Malta — DP / CP / MYP, IB school since 1995 — https://www.ibo.org/school/000832/

### tax_finance — 4 rows
Register: **MFSA Financial Services Register** (same app/API as banks). Audit/accountancy
firms confirmed to hold an MFSA authorisation with status **"Licence Authorised"**:
- PricewaterhouseCoopers (Malta) Limited — C 6685 — Approved Auditor List (Undertakings)
- Deloitte Audit Limited — C 51312 — Approved Auditor List (Undertakings)
- Ernst & Young Malta Limited — C 30252 — Approved Auditor List (Undertakings)
- KPMG Advisory Services Limited — C 2435 — Class A CSP (Company Service Provider)

(KPMG's audit practice appears on the Approved Auditor list as a partnership with no
C-number; the C-numbered KPMG entity holding an authorised MFSA licence is the Class A CSP
above.) `accreditation_number` = the register's C-number; `source_url` = register root
(search by name / C-number).

### legal_admin — 4 rows
Register / body: **Malta Chamber of Advocates — Find a Lawyer directory**
(https://avukati.org/find-a-lawyer/), described on the page as "an official directory of
warranted advocates authorised to practise law in Malta." Each firm below is a provider whose
warranted advocate has a per-advocate profile page in the directory; the firm↔advocate
association is taken from the directory's own firm filter (i.e. register-sourced, not asserted).
`source_url` is the cited advocate's profile page. No warrant number/expiry is published on the
profiles, so `accreditation_number`/`accreditation_expiry` are blank.

- Chetcuti Cauchi Advocates — via Adv. Jean-Philippe Chetcuti — https://avukati.org/lawyer/jean-philippe-chetcuti
- Fenech & Fenech Advocates — via Adv. Ann Fenech — https://avukati.org/lawyer/ann-fenech
- Mamo TCV Advocates — via Adv. Andrew Muscat — https://avukati.org/lawyer/andrew-muscat
- GVZH Advocates — via Adv. Andrew Zammit — https://avukati.org/lawyer/andrew-zammit

(`website_url` left blank for GVZH — firm domain not verified against a register.)

### housing_agencies — SKIPPED
Register: **Property Market Agency (PMA)** Real Estate Licensing Register
(https://realestateregister.gov.mt/), the statutory Licensing Authority register under the
Property Market Agency Act (Cap. 644, successor to the Real Estate Agents, Property Brokers
and Property Consultants Act). The register is a **verify-only** Blazor tool: it accepts
**only** an identity-card number or a licence number and returns a single yes/no verification.
It cannot be browsed or searched by company/agent name (a name query returns nothing), so
licensed firms cannot be discovered or enumerated and no licence number can be captured
without already knowing it. No published/downloadable licensee list exists on the PMA site.
Per the rules — and refusing to substitute agencies' self-declared marketing sites — the
category is skipped.

## Reproduction notes
- MFSA register API (read-only, same-origin): `GET https://fsr.mfsa.mt/Licences/searchLicencesByLicenceHolder?filter=<name>` returns each licence holder with `companyId` (C-number) and its licences + statuses.
- IBO finder: `GET https://www.ibo.org/programmes/find-an-ib-school/?SearchFields.Country=MT` (country value is the ISO code `MT`, not "Malta").
- Chamber directory data loads via WordPress admin-ajax; the rendered cards link to `https://avukati.org/lawyer/<slug>` profile pages.
