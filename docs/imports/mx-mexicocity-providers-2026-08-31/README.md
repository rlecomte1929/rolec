# Mexico City (Mexico) service providers — register-verified

**Corridor:** `XX-MX` (destination Mexico City, Mexico)
**Compiled:** 2026-08-31
**Rule:** every row is evidenced by an official statutory register or recognized accreditation
body (the `source_url`), not the firm's own marketing site. Categories with no reachable
official per-entity register were SKIPPED rather than filled from self-declared firm sites.

## Result summary

| category          | rows | register used | status |
|-------------------|------|---------------|--------|
| movers            | 4    | FIDI Global Alliance — Find a FIDI Affiliate (per-affiliate detail page) | done |
| banks             | 5    | CONDUSEF SIPRES (per-entity record) — supervisor CNBV | done |
| schools           | 4    | IB — Find an IB World School (ibo.org/en/school/<id>) | done |
| tax_finance       | 0    | — | SKIPPED |
| legal_admin       | 0    | — | SKIPPED |
| housing_agencies  | 0    | — | SKIPPED |

Total: **13 rows** across 3 categories.

---

## movers — FIDI Global Alliance (FAIM) — 4 firms

Register: <https://www.fidi.org/find-fidi-affiliate>. Each row cites the **per-affiliate detail
page** (not the search URL). FAIM certification is the audited quality standard; expiry is the
certification year shown on the affiliate page. All confirmed to have a Mexico City / greater
Mexico City metro office.

- GRUPO TRANSPORTISTA GOU (Mudanzas GOU) — Azcapotzalco, **Mexico City** — FAIM, exp. 2028
- TRAFIMAR RELOCATION SERVICES — **Mexico City** — FAIM Plus, exp. 2028
- ATLASMEX RELOCATIONS (ATL Van Lines Mexicana) — Cuauhtémoc, **Mexico City** — FAIM Plus, exp. 2026
- CIME (Cía. Internacional de Mudanzas y Embarques) — Tlalnepantla, **Edo. México (CDMX metro)** — FAIM Plus, exp. 2028

`accreditation_number` left blank — FIDI does not publish a per-affiliate licence number on the
detail page; the certification tier (FAIM / FAIM Plus) is captured in `accreditation_body`.

## banks — CONDUSEF SIPRES / CNBV — 5 firms

Register: **SIPRES** (Sistema de Registro de Prestadores de Servicios Financieros), the official
public register run by CONDUSEF (gob.mx). Each row cites the **per-entity record**
(`home_publico.jsp?idins=<id>`), which shows Sector = *Instituciones de banca múltiple*,
Supervisora = **CNBV**, Estatus = *En operación*, and the **Clave de Registro** (used as
`accreditation_number`). Queried live 2026-08-31 via SIPRES search (`resulbusq.jsp`).

| bank | Clave de Registro | idins | SIPRES domicilio |
|---|---|---|---|
| BBVA México | 40012 | 305 | Ciudad de México |
| Banco Mercantil del Norte (Banorte) | 40072 | 351 | Nuevo León (national bank; branches in CDMX) |
| Banco Santander México | 40014 | 307 | Ciudad de México |
| Banco Nacional de México (Banamex / Citibanamex) | 40002 | 300 | Ciudad de México |
| HSBC México | 40021 | 310 | Ciudad de México |

Note: Banorte's legal domicile on SIPRES is Monterrey (Nuevo León); it is a national bank
operating throughout Mexico City and is one of the five banks named in the sourcing brief.
`accreditation_expiry` blank — SIPRES records carry an operating status ("En operación"), not an
expiry date.

## schools — IB World Schools — 4 firms

Register: **IB — Find an IB World School**. Each row cites the canonical per-school page
`ibo.org/en/school/<id>` and the IB school code as `accreditation_number`. The IBO detail pages
sit behind a Cloudflare challenge (direct body fetch returns a JS challenge / 403), so each
id↔school↔Mexico-City-location mapping was confirmed via IBO's own indexed register titles plus
corroborating sources.

- Greengates School — Naucalpan/CDMX — IB DP — id **000396**
- The American School Foundation, A.C. — CDMX — IB PYP + DP — id **001340**
- El Colegio Británico (Edron Academy) — Álvaro Obregón, CDMX — IB DP — id **000812**
- Lomas Hill School — Cuajimalpa, CDMX — IB PYP — id **004262**

---

## SKIPPED categories (re-source worklist)

- **tax_finance** — SKIPPED. Mexico has no public per-firm statutory register for accounting
  firms. IMCP (imcp.org.mx) is a federation of individual public accountants; the Colegio de
  Contadores Públicos de México directory (`contadoresmexico.org.mx/Directorio`) is **login-gated
  / members-only** and lists individual associates, not firms. Individual CPAs can be verified via
  the SEP cédula profesional lookup, but that is per-person, not per-firm. → No register-backed
  firm rows possible. Re-source only if a public per-firm register (e.g. SAT "Contador Público
  Inscrito" firm list, or a CNBV/CNSF authorized-auditor list) is confirmed reachable per-entity.

- **legal_admin** — SKIPPED. Mexico has no unified mandatory bar and no per-firm register of law
  firms. The only official register is the **SEP RNP / cédula profesional** lookup
  (`cedulaprofesional.sep.gob.mx`), which is per-individual abogado, not per-firm. Listing firms
  would require self-declared firm sites, which the brief forbids. Re-source per-individual only
  if named abogados (with cédula) are required.

- **housing_agencies** — SKIPPED. No mandatory federal realtor register in Mexico. AMPI
  (Asociación Mexicana de Profesionales Inmobiliarios) is a **voluntary** association, not a
  statutory register; some states have local real-estate registries but Mexico City (CDMX) does
  not maintain a mandatory public per-agent/per-firm register. Per the brief, AMPI membership and
  firm sites are not acceptable. → SKIP.

## Method / provenance

- movers: WebSearch on `site:fidi.org` + WebFetch of each per-affiliate detail page (confirmed
  address, website, FAIM tier, expiry).
- banks: live SIPRES query — `POST resulbusq.jsp {tipo:1, pnom:<name>}` then filtered to
  Sector = *Instituciones de banca múltiple* / Estatus = *En operación*; each per-entity page
  `home_publico.jsp?idins=<id>` fetched (HTTP 200) and Clave de Registro / CNBV supervisor /
  domicilio confirmed.
- schools: IB register (ibo.org/en/school/<id>) ids confirmed from IBO-indexed titles +
  corroborating school/location sources; official school domains verified to resolve.
- No numbers, ids, or expiry dates were invented. Fields not shown on a register are left blank.
