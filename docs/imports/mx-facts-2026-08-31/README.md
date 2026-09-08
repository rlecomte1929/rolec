# MX facts — third-country-national professional, employer relocation (hub: Mexico City)

- **Corridor:** `MX` · **Perspective nationality:** `non-EEA` · **Status:** `professional`
- **Produced:** 2026-08-31
- **File:** `facts.ndjson` — **12 facts**, all `confidence: high`, `non_obvious: true`, `needs_lawyer_review: false`
- **Sources:** official Mexican government only (`gob.mx` / `inm.gob.mx` / `sre.gob.mx` / `sat.gob.mx` / IMSS). No blogs, relocation firms, or news.

## Verbatim confirmation

Every `evidence_quote` was confirmed as a verbatim substring of the fetched official text. Method per source below.
Line-wrap/whitespace in PDFs was normalised (a single space) before matching; accents and wording are exact.

| # | pillar | source_url | grounding method | verbatim? |
|---|--------|-----------|------------------|-----------|
| 1 | RESIDENCE | gob.mx/sre …/visa-de-residencia-temporal | Browser pane `get_page_text` → grep | ✅ |
| 2 | EMPLOYMENT | (same SRE page) | Browser pane → grep | ✅ |
| 3 | EMPLOYMENT | (same SRE page) | Browser pane → grep | ✅ |
| 4 | TIMELINE | (same SRE page) | Browser pane → grep | ✅ |
| 5 | RESIDENCE | inm.gob.mx/static/Tramites/expedicion_documento_canje.pdf | curl → pypdf → grep | ✅ |
| 6 | EMPLOYMENT | inm.gob.mx/static/Tramites/obtencion_constancia_inscripcion_empleador.pdf | curl → pypdf → grep | ✅ |
| 7 | EMPLOYMENT | inm.gob.mx/static/Tramites_LM/Autorizacion_Visas_LM/Visa_oferta_de_empleo.pdf | curl → pypdf → grep | ✅ |
| 8 | EMPLOYMENT | (same oferta-de-empleo PDF) | curl → pypdf → grep | ✅ |
| 9 | IDENTITY | gob.mx/public/tramites/detalleTramite.xhtml?homoclave=SEGOB-2021-069-009-A | Browser pane → grep | ✅ |
| 10 | EMPLOYMENT | wwwmat.sat.gob.mx/tramites/97439/…extranjero | WebFetch (reproduced across 2 fetches) | ✅ * |
| 11 | EMPLOYMENT | sat.gob.mx/articulo/46858/articulo-9 (CFF Art. 9) | verbatim from official CFF PDF → pypdf → grep | ✅ ** |
| 12 | SOCIAL_SECURITY | gob.mx/imss/prensa/tu-patron-debe-registrarte-en-el-imss… | WebFetch (reproduced across 2 fetches) | ✅ * |

`*` **SAT (`sat.gob.mx`) and `imss.gob.mx` block both curl (bot challenge / 403 "Access Gateway") and the browser pane.**
Facts 10 and 12 were grounded via WebFetch of the live official page; the quote was reproduced identically across two
independent fetches. They could not be independently grepped from raw HTML the way the PDF/browser sources were.

`**` Fact 11: `sat.gob.mx/articulo/46858/articulo-9` is the canonical SAT page for Código Fiscal de la Federación Art. 9,
but that host is gated. The exact quote (`"Las que hayan establecido su casa habitación en México."`) was verified
verbatim against the official CFF PDF text (SAT MungoBlobs copy, fetched and extracted with pypdf). `source_url` points to
the clean human-readable SAT article page.

## Non-obvious highlights

- The Temporary Resident **visa is obtained at a Mexican consulate abroad**, then **exchanged (canje) at INM within 30
  calendar days of entry** for the actual residence card (Tarjeta de Residente). The consular visa is not the final permit.
- The visa **permits work only if the salary is paid abroad**. A **Mexico-paid role requires the employer to petition INM**
  directly — a fundamentally employer-driven route.
- The **employer must be registered with INM** (Constancia de Inscripción de Empleador) *before* offering a job to a
  foreigner; the work authorization is **tied to the specific occupation, employer, workplace and pay** in the job offer.
- A Mexican work permit **does not validate professional credentials/titles** — regulated professions need separate
  revalidation.
- **CURP is assigned automatically** when INM issues the foreigner's NUE (no separate application); the **RFC** tax ID uses
  the migration document as identification; establishing a **home in Mexico triggers Mexican tax residency** (CFF Art. 9).
- **IMSS enrolment is the employer's obligation**, unlocking public healthcare.

## Sources (full URLs)

- https://www.gob.mx/sre/acciones-y-programas/visa-de-residencia-temporal
- https://www.inm.gob.mx/static/Tramites/expedicion_documento_canje.pdf
- https://www.inm.gob.mx/static/Tramites/obtencion_constancia_inscripcion_empleador.pdf
- https://www.inm.gob.mx/static/Tramites_LM/Autorizacion_Visas_LM/Visa_oferta_de_empleo.pdf
- https://www.gob.mx/public/tramites/detalleTramite.xhtml?homoclave=SEGOB-2021-069-009-A
- https://wwwmat.sat.gob.mx/tramites/97439/inscribete-en-el-rfc-como-persona-fisica-si-eres-extranjero
- https://www.sat.gob.mx/articulo/46858/articulo-9  (CFF Art. 9; quote verified against official CFF PDF)
- https://www.gob.mx/imss/prensa/tu-patron-debe-registrarte-en-el-imss-con-tu-salario-correcto-el-no-hacerlo-afecta-tus-cotizaciones-ante-el-instituto

## Notes / gaps

- **Driving licence** was dropped: it is a Mexico City (CDMX) state-level trámite (`semovi`/`cdmx.gob.mx`), not a federal
  `gob.mx` source with a clean verbatim quote, so it fell outside the official-federal-source scope for this pass.
- `sat.gob.mx` and `imss.gob.mx` are hostile to automated fetching (challenge / 403). Facts 10–12 rely on WebFetch of the
  live pages plus (for fact 11) the official CFF PDF. If a reviewer wants raw-HTML grep confirmation for facts 10 and 12,
  it must be done from a browser session that clears those hosts' gateways.
