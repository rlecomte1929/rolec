# Nicosia, Cyprus — register-verified service providers (2026-08-31)

Corridor tag: `XX-CY` (destination = Cyprus; origin unspecified). 22 rows, 6 categories.
Every row is evidenced by an official statutory register or recognized accreditation body
(`source_url`), not the firm's own marketing site. All registers were browser-grounded /
direct-fetched on 2026-08-31.

## Categories

### movers — 2 firms
- **Register:** FIDI Global Alliance — Find a FIDI Affiliate (`fidi.org/find-fidi-affiliate`,
  filtered to Cyprus = `?country=231`). Cited per-affiliate detail page.
- **Finding:** The FIDI register lists **exactly two** affiliates for the whole of Cyprus, and
  that is the complete set. Both are HQ-registered in **Limassol** on their FIDI detail page but
  are the only FAIM-accredited international movers on the island and serve Nicosia; the category
  brief allows a "Nicosia/Cyprus office," so both are included. No third FIDI affiliate exists to add.
  - Columbia Worldwide Movers Ltd — FIDI-FAIM Plus, expiry 2029.
  - Orbit Moving & Storage Co. Ltd — FIDI-FAIM Plus, Top Performer, expiry 2027.
- FAIM expiry captured in `accreditation_expiry`; FAIM level in `accreditation_body`.

### banks — 4 firms
- **Register:** Central Bank of Cyprus — *Register of Credit Institutions operating in Cyprus*
  (`centralbank.cy/en/licensing-supervision/banks/register-of-credit-institutions-operating-in-cyprus`).
- Selected retail banks headquartered/operating in Nicosia: Bank of Cyprus (local ACI),
  Alpha Bank Cyprus (EU subsidiary), Ancoria Bank (local ACI), and **Eurobank Limited**.
- **Two important register facts vs. the candidate list in the brief:**
  - **"Hellenic Bank" and "Eurobank Cyprus" have merged.** The register now carries a single entry:
    *"Eurobank Limited (previous name: Hellenic Bank Public Company Limited)."* Listed under that
    exact name. (Eurobank Limited website left blank — the post-merger primary domain is ambiguous
    and the register does not publish one; the CBC entry is the evidence.)
  - **AstroBank is NOT on the current CBC register** and was therefore excluded per the rules
    (exclude firms not on a real register). It is absent from the Local Authorised Credit
    Institutions list and every other section as of 2026-08-31.
- The register page shows no per-bank licence number or expiry inline, so those columns are blank;
  the register itself is the evidence.

### schools — 4 firms
- **Register:** IB — *Find an IB World School* (`ibo.org`), per-school detail page
  `ibo.org/school/<id>`. `accreditation_number` = IB school code.
- All four confirmed located in the Nicosia district on their IBO detail page:
  - American International School in Cyprus — 000752 (Nicosia).
  - PASCAL Private Secondary School Lefkosia — 002284 (Lakatamia, Nicosia).
  - The Junior and Senior School — 063714 (Latsia, Nicosia).
  - The Falcon School — 063475 (Nicosia).
- Cyprus has 11 IB World Schools total; the 7 non-Nicosia (Limassol, Larnaca, and Northern-Cyprus
  schools) were excluded.

### legal_admin — 4 firms  (NOT skipped)
- **Register:** Cyprus Bar Association (Παγκύπριος Δικηγορικός Σύλλογος) — *Lawyers Company's
  Registry* at `cyprusbar.org/AssociationPage.aspx`. This is the CBA's official e-services registry
  portal, linked from `cyprusbarassociation.org`; the companies list itself lives on `cyprusbar.org`.
- The registry is a searchable DevExpress grid of **22** registered lawyers' partnerships
  (Συνεταιρισμοί), each with a CBA registration number. **6** have a Nicosia landline (area code
  **22**); 4 were selected. `accreditation_number` = the CBA registry number shown in the grid.
- **Scope note:** this online registry is the *partnerships* register — the large modern LLCs
  (ΔΕΠΕ, e.g. Ioannides Demetriou, Chrysostomides) are not present in this grid, so those firms
  could not be register-evidenced here and were not guessed in. Nicosia was confirmed from the
  register's own phone field (area code 22), not an external site. No per-firm URL exists; the
  registry page is the citation (same pattern as the CBC banks register).

### tax_finance — 4 firms  (NOT skipped)
- **Register:** ICPAC / ΣΕΛΚ — *List of statutory audit firms licensed by ICPAC* (Auditors Law
  L.53(I)/2017), `icpac.org.cy/selk/en/practicingfirmauditors.aspx`. The register has **per-firm
  detail pages** (`practicingfirmauditorsdetails.aspx?firmno=<id>`), which are cited.
- The four Big-Four audit entities with Nicosia registered offices were selected; each row carries
  its ICPAC Practising Certificate Number in `accreditation_number`:
  - PricewaterhouseCoopers Ltd — HE143594 — cert E002/A/2013 — Nicosia (Demostheni Severi Ave 43).
  - KPMG Ltd — HE132822 — cert E194/A/2013 — Nicosia (Esperidon 14).
  - Deloitte Limited — HE162812 — cert E047/A/2013 — Nicosia (Spyrou Kyprianou Ave 24).
  - Ernst & Young Cyprus Limited — HE222520 — cert E146/A/2013 — Nicosia (Esperidon 10, Strovolos).
- The ICPAC register publishes no website field, so `website_url` is left blank; the register +
  HE number + certificate number + Nicosia address are the evidence.

### housing_agencies — 4 firms  (NOT skipped)
- **Register:** Real Estate Agents Registration Council (Συμβούλιο Εγγραφής Κτηματομεσιτών) —
  official *Licensed Agents* register at `ktimatomesites.com/agents/` (the Council's own site).
  Each entry shows City, License no, and Registration no.
- Four Nicosia registered agencies (companies, `/E` licences) selected. `accreditation_number` =
  the **Registration no** from the register. License numbers are also available on the register:
  - Blue Realty Ltd — Reg 794 / Licence 155/E — Nicosia.
  - Sabbianco Properties Limited — Reg 798 / Licence 330/E — Nicosia.
  - Ktesion Real Estate Limited — Reg 501 / Licence 74/E — Nicosia.
  - A. Petrides Landtourist Agency Ltd — Reg 484 / Licence 30/E — Nicosia.
- Websites taken from the register listing itself.

## Categories skipped
None. All six categories had a reachable official register and are populated.

## Notes / caveats
- `corridor` = `XX-CY` on every row (per brief).
- Only "MARKIDES, MARKIDES & CO" contains a comma and is quoted.
- Greek registration numbers (Σ8628, Σ11391, Σ11868) are kept verbatim as shown on the CBA registry.
- movers: both affiliates are Limassol-registered on FIDI but constitute the entire FIDI-Cyprus
  register and serve Nicosia; no Nicosia-only FIDI affiliate exists.
