# Buenos Aires, Argentina — register-verified service providers (2026-08-31)

Corridor tag: `XX-AR` (all rows). Every row is evidenced by an **official statutory
register or recognized accreditation body**, cited in `source_url` — never the firm's own
marketing site. Firms not confirmed on a real register were excluded. Two categories were
SKIPPED because their public registers are session-bound POST verification tools that list
individuals and expose no URL-addressable per-firm record (see below).

`providers.csv` header (verbatim):
`corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry`

## Included categories

### movers — 4 firms
- **Register:** FIDI Global Alliance — FAIM affiliate directory. Each row cites the
  **per-affiliate DETAIL page** (`fidi.org/find-fidi-affiliate/<slug>`), not the search URL.
- All four confirmed with a Buenos Aires / Greater Buenos Aires office and a current FAIM
  certification. `accreditation_expiry` = FAIM certificate year shown on the detail page.
  `accreditation_number` left blank (FIDI shows a FAIM status/expiry, not a per-affiliate number).
- Firms: ARGENMOVE (Suipacha 612, CABA; FAIM 2028), Universal Cargo (Tacuari 202, CABA;
  FAIM Plus 2028), Transpack Argentina (Florencio Varela, Prov. BA; FAIM Plus 2027, Top
  Performer), Lift-Van International (Ruta 202, Gran BA; FAIM 2027).

### banks — 5 banks
- **Register:** BCRA (Banco Central de la República Argentina) — "Entidades Financieras"
  directory of authorised entities. Each row cites the **per-entity page**
  (`bcra.gob.ar/entidades-financieras/?bco=<code>`), which shows Nro° Banco, CUIT, casa
  matriz address (all CABA) and official website.
- `accreditation_number` = BCRA entity code (Nro° Banco). Banco Nación 00011, Galicia 00007,
  Santander Argentina 00072, BBVA Argentina 00017, Macro 00285. Directory data as of May 2026.

### schools — 4 IB World Schools
- **Register:** IB (International Baccalaureate) — "Find an IB World School"
  (`ibo.org/en/school/<id>`). `accreditation_number` = IB school code.
- St. Catherine's Moorlands (000049, Belgrano/CABA — DP + MYP), Colegio Lincoln (000715,
  Palermo/CABA — DP), Asociación Escuelas Lincoln (000711, La Lucila/Gran BA — DP; the
  American international school), Northlands (000869, Olivos/Gran BA — DP + PYP). IB shows no
  expiry date, so `accreditation_expiry` is blank.

### housing_agencies — 4 brokers
- **Register:** CUCICBA (Colegio Único de Corredores Inmobiliarios de la CABA) — mandatory
  matrícula. Live site is `colegioinmobiliario.org.ar` (the `cucicba.com.ar` domain named in
  the brief now redirects to it). The public **"Guía de Matriculados"** lists only corredores
  *con oficina habilitada* and is backed by an open GET/JSON endpoint
  (`/servicios/guia-de-matriculados/buscar?q=<term>`), so each row cites a **reproducible
  per-firm query URL** that returns the matriculado record.
- `company_name` = registered `nombre_fantasia`; `accreditation_number` = matrícula.
  Toribio Achával (mat 394, Av. Callao 1515, Recoleta), Adrián Mercado Real Estate (mat 5604,
  Valle 1108, Caballito), Bullrich Brokers (mat 2337, San Martín 66, Comuna 14), Cornejo
  Realty (mat 2312, Av. del Libertador 734, Recoleta). Websites derived from the register's
  own email-domain field where unambiguous; blank where the register lists only a personal email.

## SKIPPED categories

### legal_admin — SKIPPED
- **Register checked:** CPACF (Colegio Público de Abogados de la Capital Federal), public
  "Guía de Abogados" at `w3.cpacf.org.ar/guiaabo2/guiaabo3.aspx`.
- **Reason:** ASP.NET WebForms search (VIEWSTATE / EVENTVALIDATION, POST-only). Results are
  session/postback-bound with **no URL-addressable per-lawyer page**, and the register lists
  individual matriculados (tomo/folio), not firms. Producing rows would require seeding lawyer
  names from marketing sites and citing a generic form URL — disallowed by the rules. Skipped
  rather than cite self-declared firm sites.

### tax_finance — SKIPPED
- **Register checked:** CPCECABA (Consejo Profesional de Ciencias Económicas de CABA),
  "Verificación de Profesionales Matriculados" at `z0723.cponline.org.ar/vpm/consultaMatricula`.
- **Reason:** Java Struts POST form with `jsessionid` (search by tipo de matrícula + tomo/folio
  or apellido/nombre). Session-bound, **not URL-addressable per professional**, and verifies
  individual contadores, not firms. Same disqualification as CPACF. Skipped.

## Method / verification
- All FIDI and BCRA data confirmed by direct fetch / browser read of the register pages; IB
  and CUCICBA confirmed by browser-grounding (IBO and the BCRA/CUCICBA endpoints block plain
  WebFetch). No numbers were invented — matrícula/entity/IB codes were captured only where the
  register displayed them; blanks left where the register showed nothing.
