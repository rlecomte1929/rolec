# Lisbon, Portugal — register-verified service providers (2026-08-31)

Corridor tag: `XX-PT` (every row). Each row is evidenced by an official statutory register
or recognised accreditation body — **not** the firm's own marketing site. Firms that could
only be evidenced by a self-declared site were excluded; a whole category was skipped rather
than filled with unverifiable rows.

Output: `providers.csv` — 20 rows across 5 categories (1 category skipped).

## Registers used, per category

### movers — 3 firms
- **Register:** FIDI Global Alliance — "Find a FIDI Affiliate", filtered to Portugal
  (`https://www.fidi.org/find-fidi-affiliate?country=89`). FIDI affiliation requires FAIM
  accreditation (independently audited, currently by EY).
- Browser-grounded: opened the Portugal filter; captured the three affiliates with a
  Lisbon-metro office (Global International Relocation = Lisbon office; Invictus Relocation
  Services = Lisbon; Premier International Movers = Sintra). Global also lists Faro/Porto
  offices and there is one more Porto affiliate — excluded as non-Lisbon.
- `accreditation_number`/`expiry` left blank: the affiliate finder does not expose a FAIM
  certificate number or expiry per firm.

### banks — 5 firms
- **Register:** EBA Credit Institutions Register (EUCLID), Portugal
  (`https://euclid.eba.europa.eu/register/cir/search`). Data is owned and submitted by
  **Banco de Portugal** as national competent authority. Used because `bportugal.pt` and
  `clientebancario.bportugal.pt` were behind an unclearing Cloudflare bot-check during this run
  — the EBA register is the EU-level list explicitly allowed by the brief.
- Browser-grounded: searched Country = Portugal (141 credit institutions); confirmed each of
  the five named majors with its LEI, Banco de Portugal institution code and town.
- `source_url` is the per-institution register entry (`.../entityView/CRD_CRE_INS/<LEI>`;
  shows an EBA disclaimer interstitial before the entity record). `accreditation_number` =
  the Banco de Portugal institution code shown in the register. LEIs (in the URL): CGD
  `TO822O0VT80V06K0FH57`, Millennium BCP `JU1U6S0DG9YLT7N8ZV32`, Novo Banco
  `5493009W2E2YDCXY6S81`, Santander Totta `549300URJH9VSI58CS32`, BPI
  `3DM5DPGI3W6OU6GJ4N92`.
- `website_url` left blank: the register does not list a bank website (register-strict).

### schools — 4 firms
- **Register:** IB "Find an IB World School" (`ibo.org/en/school/<id>`). All four are
  authorised IB World Schools (Diploma Programme) in the Lisbon area.
- Browser-grounded: opened the finder filtered to Portugal + keyword "Lisbon" (4 results);
  captured each school's IB code from its listing link, and fully confirmed Carlucci's detail
  page (IB code 001048, authorised 1998, "World school", Sintra/Lisbon, site caislisbon.org).
- `website_url` blank for the other three: `ibo.org` fell behind a Cloudflare 403 after the
  finder + Carlucci loaded, so the three detail pages (and their listed websites) could not be
  re-opened. The rows remain register-grounded via their IB codes. Re-source note below.

### housing_agencies — 4 firms
- **Register:** IMPIC public register of licensed real-estate mediators
  (`https://www.impic.pt/impic/pt-pt/consultar/empresas-titulares-de-licenca-de-mediacao-imobiliaria`),
  the "empresas titulares de licença" (currently-licensed) list.
- Browser-grounded (isolated browser): searched Distrito = Lisboa; the result table exposes
  `Nº Licença` (= AMI number), NIPC, name and address. Confirmed four established Lisbon-area
  agencies by name and captured the AMI verbatim: Porta da Frente (Christie's affiliate) AMI
  6335 (Cascais), Savills Portugal AMI 5446 (Lisboa), Cobertura AMI 479 (Lisboa), Predifixe
  AMI 124 (Lisboa city). Franchise brands (Engel & Völkers, Century 21) return 0 by brand name
  because offices register under local company names — not searched further.
- `accreditation_number` = AMI (Nº Licença). `expiry`/`website_url` blank: the register list
  does not show a licence expiry or a firm website.

### tax_finance — 4 firms
- **Register:** OROC — "Lista de SROCs registados na Ordem" (audit firms), the official current
  PDF `https://www.oroc.pt/wp-content/uploads/2026/07/SROC_28-07-2026.pdf`, linked from
  `https://www.oroc.pt/ordem/lista-de-roc-e-sroc/`. Chose OROC over OCC because OROC's SROC list
  is firm-level (audit firms), whereas OCC/contabilistas certificados are individuals.
- Grounded from the register file (text layer extracted): the Big Four, all with a Lisbon
  registered office — Deloitte SROC nº 43, PwC SROC nº 183, KPMG SROC nº 189, Ernst & Young
  SROC nº 178. `accreditation_number` = OROC SROC registration number; `website_url` taken from
  the "Sítio na Internet" field in the register entry. `expiry` blank (all "Inscrição Definitiva").

## SKIPPED category (re-source worklist)

### legal_admin — SKIPPED
- **Reason:** The Ordem dos Advogados public "Pesquisa de Advogados" (`portal.oa.pt`) is a
  register of **individual lawyers** (search by cédula / nome / localidade / Conselho Regional).
  It has no firm-level entries and no practice-area (e.g. immigration/relocation) filter, so it
  is not reachable "per-firm" as the brief requires. Per the rules (skip a whole category rather
  than use self-declared firm sites), this category was skipped rather than populated with
  arbitrarily chosen individuals or law-firm marketing sites.
- **Re-source options:** (a) accept individual-lawyer rows from the OA directory (company_name =
  lawyer name, accreditation_number = cédula) scoped to Conselho Regional de Lisboa, if the
  catalog model allows individuals; (b) cross-reference an immigration-law specialist list, then
  verify each named lawyer against the OA cédula register for the accreditation number.

## Notes / provenance
- Confirmed live 2026-08-31.
- No accreditation numbers were invented: AMI numbers and IB codes are copied verbatim from the
  register; bank rows carry the Banco de Portugal institution code (LEIs in the source_url);
  SROC numbers are from the OROC register file. Fields the register did not expose (websites for
  banks/housing, three school websites, all expiries) are left blank.
- `bportugal.pt` and `ibo.org` (detail pages) were intermittently Cloudflare-blocked during the
  run; these are transient bot-checks, not dead sources — retry to backfill the three school
  websites, or substitute the primary Banco de Portugal register for the EBA citation if preferred.
