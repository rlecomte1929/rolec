# Helsinki, Finland — register-verified service providers (corridor XX-FI)

Sourced 2026-08-31. Every row is evidenced by an official statutory register or
recognised accreditation body (the `source_url`), not the firm's own marketing site.
Firms not confirmable on a real register were excluded; two-of-six discovery-only
registers that cannot be browsed were skipped (see worklist).

Total rows: **20** across **5** categories. **1** category skipped (housing_agencies).

## Per-category summary

### movers — 4 firms
- **Register:** FIDI Global Alliance affiliate finder, filtered to Finland.
  `https://www.fidi.org/find-fidi-affiliate?country=287` (Finland = country id 287).
- **Verification:** opened the Finland-filtered affiliate list; all 4 affiliates are
  registered with a **Helsinki** office and carry a live FAIM certification.
- Firms: ALFA MOBILITY (FIDI-FAIM, FIDI-DSP), NIEMI SERVICES LTD (FIDI-FAIM PLUS),
  TRAVELCARGO INTERNATIONAL REMOVALS (FIDI-FAIM PLUS, TOP PERFORMER),
  VICTOR EK MOVING LIMITED (FIDI-FAIM PLUS). FAIM level recorded in `accreditation_body`.
  FIDI shows no numeric affiliate id, so `accreditation_number` is blank.

### banks — 4 credit institutions
- **Register:** ECB Banking Supervision *List of supervised entities* (SSM), Finland
  section. `https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.listofsupervisedentities202408.en.pdf`
  (task-permitted ECB/EBA alternative to the FIN-FSA register).
- **Verification:** extracted the Finland block from the PDF and confirmed each as a
  Finnish credit institution ("CI"), with its LEI recorded in `accreditation_number`:
  Nordea Bank Abp (`529900ODI3047E2LIV03`, significant institution),
  OP Corporate Bank plc / OP Yrityspankki Oyj (`549300NQ588N7RWKBP98`),
  S-Pankki Oy (`743700FTBNXAUN57RH30`), Aktia Bank Abp (`743700GC62JLHFBUND16`).
- **Danske Bank EXCLUDED:** in Finland it operates as *"Danske Bank A/S, Finland Branch"*
  — a branch of a Danish bank (listed "BR" on the ECB list), passported and supervised
  from Denmark, **not** a FIN-FSA-authorised Finnish credit institution. Dropped to keep
  the "authorised by FIN-FSA" claim honest.
- The FIN-FSA supervised-entities register (`https://www.finanssivalvonta.fi/en/registers/supervised-entities/`,
  "Credit market entities") is the corroborating national register; it was browser-confirmed
  to exist and be searchable but its result set is a JS SPA (see note below), so the ECB
  list — which carries the same authorisation status plus LEIs — is cited as `source_url`.

### schools — 4 IB World Schools (Helsinki)
- **Register:** IBO "Find an IB World School" — `https://www.ibo.org/en/school/<id>`.
  `accreditation_number` = the IB School code shown on the page.
- **Verification:** International School of Helsinki (000652) was fully browser-confirmed
  (page shows "IB School code: 000652", Country: FINLAND, IB school since 1992). The other
  three ibo.org register pages were confirmed via search indexing of ibo.org's own pages
  (exact name + id): Helsingin Suomalainen Yhteiskoulu / SYK (000571),
  Ressun lukio (001419), Ressu Comprehensive School (002343). ibo.org intermittently
  serves a Cloudflare bot challenge to direct fetches (not a bypass-able CAPTCHA), so the
  latter three were not re-opened live — their ids/URLs are in the ibo.org register.

### tax_finance — 4 approved audit firms
- **Register:** PRH Auditor Oversight auditor search (Tilintarkastajahaku) —
  `https://tietopalvelut.prh.fi/tilintarkastajahaku`.
- **Verification:** searched the register, filtered to class **Tilintarkastusyhteisö**
  (approved audit firm). Confirmed each with a registered **Helsinki** address:
  KPMG Oy Ab (Töölönlahdenkatu 3, 00100), Ernst & Young Oy (Korkeavuorenkatu 32-34, 00130),
  Deloitte Oy (Itämerenkatu 25, 00181), BDO Oy (Porkkalankatu 3, 00180). The register only
  shows name / auditor class / postal address (no numeric licence id), so
  `accreditation_number` is blank; the class is recorded in `accreditation_body`.

### legal_admin — 4 Bar-member law firms
- **Register:** Finnish Bar Association "Find an Attorney" — `https://www.findanattorney.fi/`.
- **Verification:** searched by law-firm name; each returned dozens of members listed as
  "Attorney-at-law" (Asianajaja = Bar member), which is the register's proof of membership:
  Castrén & Snellman Attorneys Ltd (113), Hannes Snellman Attorneys Ltd (94),
  Roschier, Attorneys Ltd. (90), Borenius Attorneys Ltd (80). All four are
  Helsinki-headquartered firms. The register carries no numeric member id at firm level, so
  `accreditation_number` is blank.

## Skipped categories (re-source worklist)

### housing_agencies — SKIPPED
- **Register exists but is not browsable.** The real-estate/letting agency register
  (välitysliikerekisteri) is now run by the Lupa- ja valvontavirasto (Finnish Supervisory
  Agency; AVI's tasks transferred to it 1 Jan 2026): `https://vasa.avi.fi/`.
- It **only accepts an exact business ID (Y-tunnus, format 1234567-8)** and explicitly
  states it does not publish the whole register (data-protection). There is no name- or
  location-based search, so specific Helsinki agencies **cannot be discovered from the
  register itself**, and firm marketing sites are auto-rejected downstream. Skipped per the
  task's "if not reachable/usable, SKIP" rule.
- **Re-source path:** (1) get each candidate brokerage's Y-tunnus from the official Business
  Information System `https://www.ytj.fi/` (e.g. Kiinteistömaailma, Huoneistokeskus, OP Koti,
  SKV, Sp-Koti, Habita, Bo LKV franchise entities), then (2) confirm each Y-tunnus is entered
  in `https://vasa.avi.fi/` and record the registration id/date it returns.

## Notes / caveats
- `corridor` = `XX-FI` on every row (destination-Finland; origin unset).
- `website_url` is the firm's own site (not evidence); `source_url` is the proving register.
  Mover and ISH sites are as shown by FIDI/IBO; bank/audit/law-firm/SYK sites are the firms'
  well-known official domains. The two Ressu school sites were left blank (city-operated;
  not asserted).
- Some Finnish statutory registers are JS single-page apps that server-side fetch (WebFetch)
  cannot render; they were grounded via the live browser (React-state-aware input) and, for
  banks, via the downloadable ECB PDF.
