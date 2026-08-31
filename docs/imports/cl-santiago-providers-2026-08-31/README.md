# Santiago (Chile) service providers — register-verified

**Corridor:** `XX-CL` (destination Santiago, Chile)
**Compiled:** 2026-08-31
**Rule:** every row is evidenced by an official statutory register or recognized accreditation
body (the `source_url`), not the firm's own marketing site. Categories with no reachable
official per-entity register were SKIPPED rather than filled from self-declared firm sites.

## Result summary

| category          | rows | register used | status |
|-------------------|------|---------------|--------|
| movers            | 3    | FIDI Global Alliance — Find a FIDI Affiliate (per-affiliate detail page) | done |
| banks             | 5    | CMF (Comisión para el Mercado Financiero) — register of supervised banks | done |
| schools           | 4    | IB — Find an IB World School (ibo.org/en/school/<id>) | done |
| tax_finance       | 0    | CMF Registro de Empresas de Auditoría Externa exists but was unreachable at run time | SKIPPED |
| legal_admin       | 0    | — (no mandatory bar / no per-firm register) | SKIPPED |
| housing_agencies  | 0    | — (no mandatory realtor register) | SKIPPED |

Total: **12 rows** across 3 categories.

---

## movers — FIDI Global Alliance (FAIM) — 3 firms

Register: <https://www.fidi.org/find-fidi-affiliate>. Each row cites the **per-affiliate detail
page** (not the search URL). FAIM certification is the audited quality standard (independent
auditor: EY); expiry is the "FAIM Expiry date" shown on the affiliate page. All three confirmed
to have a Santiago metro office, and all three currently show **FAIM Expiry date: 2029**.

- UNIPACK S.A. (Universal Packing & Storage S.A.) — Av. Pdte. Eduardo Frei Montalva 6070,
  **Quilicura, Santiago** — FIDI-FAIM — exp. 2029 — http://www.unipack.cl
- WARD VAN LINES S.A. — Av. Américo Vespucio 2050, **Quilicura, Santiago** — FIDI-FAIM Plus —
  exp. 2029 — http://www.wardvanlines.com
- DECAPACK (Sociedad Internacional de Transportes DECA S.A.) — Av. Claudio Arrau 9452,
  **Pudahuel, Santiago** — FIDI-FAIM Plus — exp. 2029 — http://www.decapack.com

`accreditation_number` left blank — FIDI does not publish a per-affiliate licence number on the
detail page; the certification tier (FAIM / FAIM Plus) is captured in `accreditation_body`. Three
(not four) rows: Unipack, Ward Van Lines and Decapack are the only Chile/Santiago affiliates that
recur across the FIDI register and multiple searches; no fourth Santiago affiliate was found.

## banks — CMF (Comisión para el Mercado Financiero) — 5 firms

Register: the **CMF register of supervised banks**. Each of the five banks named in the brief was
confirmed present on the CMF's own official banks list ("Códigos de Bancos",
`/institucional/seil/certificacion_cir1835_bcos.php`), which enumerates every bank supervised by
the CMF — verified to contain: **BANCO DE CHILE, BANCO SANTANDER-CHILE, BANCO DEL ESTADO DE CHILE,
BANCO DE CRÉDITO E INVERSIONES (listed as "Banco BCI"), SCOTIABANK**. `source_url` cites that
canonical CMF page.

| bank | website | on CMF register |
|---|---|---|
| Banco de Chile | www.bancochile.cl | yes |
| Banco Santander-Chile | www.santander.cl | yes |
| Banco del Estado de Chile (BancoEstado) | www.bancoestado.cl | yes |
| Banco de Crédito e Inversiones (BCI) | www.bci.cl | yes |
| Scotiabank Chile | www.scotiabankchile.cl | yes |

`accreditation_number` / `accreditation_expiry` blank — CMF supervision carries an operating
status, not an expiry; the per-bank CMF/ex-SBIF institution code (e.g. Banco de Chile = 001) is
**not shown on the cited register page**, so it was left blank rather than invented.

> **Access constraint (important for re-sourcing).** `cmfchile.cl` (and its subdomains, incl.
> `datosbanco.cmfchile.cl`, `cronologiabancaria.cmfchile.cl`) is **unreachable from this
> environment** — every request times out (curl exit 28) from the WebFetch egress, direct curl,
> and the browser, while a different Chilean host (`mercadofinanciero.cl`) responds normally. This
> is a targeted block of the cmfchile.cl domain, not a transient outage (consistent across repeated
> attempts and multiple hosts). The register content above was therefore verified via the Internet
> Archive snapshot of the live canonical CMF URL (Wayback CDX + a decompressed snapshot of the
> "Códigos de Bancos" page, timestamp 20260625). The `source_url` given is the **live canonical CMF
> URL**, which is authoritative and will resolve from a Chile-reachable network. The per-bank
> "Buscador de entidades supervisadas" fichas (`entidad.php?mercado=B…` / the `consulta.php?mercado=B`
> AJAX listing) exist but are AJAX/JS and were not reachable to cite per-firm at run time.

## schools — IB World Schools — 4 firms

Register: **IB — Find an IB World School**. Each row cites the canonical per-school page
`ibo.org/en/school/<id>` and the IB school code as `accreditation_number`. The IBO detail pages
sit behind a Cloudflare challenge (WebFetch and curl both return HTTP 403 / "Just a moment…"), so
each id↔school↔Santiago mapping was confirmed via IBO's own indexed register titles
(`ibo.org/en/school/<id>` returned in search with the school name) plus corroborating
location/programme sources; official school domains were verified to resolve.

- Santiago College — Lo Barnechea, **Santiago** — IB PYP + MYP + DP — id **000184** — www.scollege.cl
- International School Nido de Aguilas — Lo Barnechea, **Santiago** — IB DP — id **000233** — www.nido.cl
- Redland School — Las Condes, **Santiago** — IB PYP + MYP + DP — id **000417** — www.redland.cl
- Craighouse School — Lo Barnechea, **Santiago** — IB PYP + MYP + DP (full continuum) — id **000635** — www.craighouse.cl

Additional Santiago IB World Schools exist on the same register if more rows are wanted (e.g.
Wenlock School id 000792, The Mayflower School id 001074) — verify id↔location before adding.

---

## SKIPPED categories (re-source worklist)

- **tax_finance** — SKIPPED. A genuine official per-firm register **does exist**: the CMF
  **Registro de Empresas de Auditoría Externa** (entities of `tipoentidad=AUDEX` in the CMF
  "Buscador de entidades supervisadas"; ~550+ entities enumerated via the Wayback CDX of
  `cmfchile.cl/institucional/mercados/entidad.php`). It could not be used because (a) `cmfchile.cl`
  is unreachable from this environment (see access constraint above) and (b) the CDX rows carry a
  RUT + opaque `row` token but not the firm name, so no per-firm page could be fetched to confirm
  which URL maps to which audit firm (Deloitte / EY / KPMG / PwC / Surlatina, etc.). Citing a URL
  whose content I could not verify would be fabrication. **Re-source:** from a Chile-reachable
  network, open the AUDEX register, capture each firm's live `entidad.php?…tipoentidad=AUDEX…` ficha
  URL and the register number, and add ~3–4 Santiago-based external-audit firms.

- **legal_admin** — SKIPPED. Chile has **no mandatory bar**; the Colegio de Abogados de Chile is a
  voluntary association, and there is no official per-firm register of law firms. Listing firms would
  require self-declared firm sites, which the brief forbids. → No register-backed rows possible.

- **housing_agencies** — SKIPPED. Chile has **no mandatory realtor/agency register** (real-estate
  brokerage — "corretaje de propiedades" — is not a licensed profession with a statutory public
  roll). Trade bodies (e.g. ACOP / CChC) are voluntary. Per the brief, association membership and
  firm sites are not acceptable. → SKIP.

## Method / provenance

- movers: WebSearch on fidi.org + direct curl of each per-affiliate detail page (HTTP 200);
  confirmed Santiago address, website, FAIM tier and "FAIM Expiry date: 2029" (the 2026 on the page
  is the "© 2026 FIDI" footer, not the certificate year).
- banks: all five confirmed on the CMF official banks list ("Códigos de Bancos"), content verified
  via the Internet Archive snapshot of the live canonical CMF URL because cmfchile.cl is
  geo/IP-blocked from this environment; `source_url` is the live canonical CMF page. Official bank
  domains verified to resolve.
- schools: IB register (ibo.org/en/school/<id>) ids confirmed from IBO-indexed search titles +
  corroborating school/location/programme sources (IBO detail pages are Cloudflare-gated); official
  school domains verified to resolve.
- No numbers, ids or expiry dates were invented. Fields not shown on a register are left blank.
