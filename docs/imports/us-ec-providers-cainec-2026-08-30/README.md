# US→EC providers — CAINEC housing (browser-grounded), 2026-08-30

Second EC provider batch, from the browser-grounding round for the categories Otto could not source
(all 6 EC registers were JS/iframe/login-gated). **CAINEC** turned out to expose real per-entity
records — `cainec.com/ficha.php?codigo=INMO-GP-...` pages render fully in a browser (Otto's scraper
saw only the JS shell). Firm names + business emails were read from those certificate records.

## Landed (4 housing_agencies, pending vet)
| firm | level | email | ficha |
|---|---|---|---|
| EDENCORP S.A. | PLATINUM | patricia.cabrera@inmobiliariaedencorp.com | INMO-GP-2026-06-005 |
| Ksa Inmobiliaria | GOLD | irojas@ksa.com.ec | INMO-GP-2026-06-003 |
| Huasi360 | GOLD | inmobiliaria@huasi360.com | INMO-GP-2026-06-006 |
| IMMOBILLIS | SILVER | informacion@immobillis.com | INMO-GP-2026-06-004 |

Source_url is the per-entity ficha record; landed via scoped promote. **EC now has 5 providers
pending** (4 housing + 1 mover — INSA, prior batch).

## Excluded (honest)
- **FORXA INMOBILIARIA** — its ficha is the only one that lists a city, and it is **CUENCA, not Quito**.
- **Aquaterra**, **Gerardo Tacuri** — gmail-only contact, no business website.

**City caveat:** CAINEC is a national body (Cuenca-based) and the ficha pages carry no city for these 4.
Landed `claimed` — the `/admin/vetting-queue` human confirms each firm actually serves Quito.

## Still blocked (registers inaccessible — the honest EC reality)
Browser-grounding could not reach these EC registers, so their categories remain unsourced:
- **banks** — `superbancos.gob.ec` navigation **denied/blocked** (not renderable).
- **schools** — MinEduc AMIE (`web.educacion.gob.ec/CNIE`) — login/JS.
- **legal_admin** — Colegio de Abogados de Pichincha directorio — iframe.
- **tax_finance** — Colegio de Contadores CCPP (`ccpp.org.ec`) — login-gated.

Ecuador's provider registers are genuinely thin and access-restricted (Otto warned of this on the
facts side too). Sourcing these four will need a different route — the registers' own APIs, a
credentialed session, or firm-by-firm confirmation against the register.
