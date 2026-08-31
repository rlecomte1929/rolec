# Argentina (AR) — non-obvious relocation facts

**Corridor:** third-country-national (non-EEA) professional relocated by an employer to Argentina (hub: Buenos Aires).
**Generated:** 2026-08-31
**Facts:** 12 (all `confidence: high`, `non_obvious: true`, `needs_lawyer_review: false`).
**Sources:** official Argentine government only (`argentina.gob.ar`, `migraciones.gob.ar`, `arca.gob.ar`).
**Verification:** every `evidence_quote` was direct-fetched via `curl` and confirmed as a **verbatim substring** (whitespace-normalized only) of the fetched official HTML. Each quote is < 200 chars. All 12 pass (`quote_verbatim_confirmed: true`).

## Pillar spread
- RESIDENCE ×5, EMPLOYMENT ×5, IDENTITY ×2. (No IMMIGRATION / TAX / FAMILY used.)

## Facts → source URL (all verbatim-confirmed)

| fact_key | pillar | source URL |
|---|---|---|
| AR:residence:file-from-within-argentina | RESIDENCE | https://www.argentina.gob.ar/servicio/obtener-una-residencia-temporaria-como-trabajador-migrante |
| AR:residence:temporaria-1-year-renewable | RESIDENCE | https://www.argentina.gob.ar/servicio/obtener-una-residencia-temporaria-como-trabajador-migrante |
| AR:employment:renure-employer-registration | EMPLOYMENT | https://www.argentina.gob.ar/interior/migraciones/permisos-de-ingreso |
| AR:employment:salary-convenio-colectivo | EMPLOYMENT | https://www.argentina.gob.ar/servicio/obtener-una-residencia-temporaria-como-trabajador-migrante |
| AR:employment:afip-alta-temprana-30-days | EMPLOYMENT | https://www.argentina.gob.ar/servicio/obtener-una-residencia-temporaria-como-trabajador-migrante |
| AR:residence:precaria-90-days | RESIDENCE | https://www.argentina.gob.ar/normativa/nacional/ley-25871-92016/actualizacion |
| AR:employment:precaria-cuil-can-work | EMPLOYMENT | https://www.argentina.gob.ar/recibir-orientacion-laboral-para-trabajadores-extranjeros-y-sus-empleadores |
| AR:residence:precaria-not-valid-for-arraigo | RESIDENCE | https://www.argentina.gob.ar/normativa/nacional/ley-25871-92016/actualizacion |
| AR:identity:dni-requires-dnm-residence | IDENTITY | https://www.argentina.gob.ar/interior/dni/extranjeros |
| AR:identity:dni-60-business-days-after-entry | IDENTITY | https://www.argentina.gob.ar/interior/migraciones/permisos-de-ingreso |
| AR:employment:cuit-provisoria-2-years | EMPLOYMENT | https://www.arca.gob.ar/inscripcion/cuit-cdi/extranjeros-residentes-sin-dni.asp |
| AR:residence:antecedentes-penales-integrated-radex | RESIDENCE | https://www.migraciones.gob.ar/radex/inicio-pasos.html |

## Notes / caveats for the reviewer
- **Precaria = 90 days, not 180.** The current (actualizada) text of Law 25.871 on `argentina.gob.ar` states the precaria is valid "hasta NOVENTA (90) días corridos" (reflecting the 2025 reform). The older Decreto 616/2010 reglamentario still literally reads 180 days (Art. 69), and some third-party pages repeat 180. The fact deliberately cites the current **law** text, which prevails. Flag if the corridor should instead track the reglamentario figure.
- **Two entry routes exist.** `AR:residence:file-from-within-argentina` describes the RADEX online route (must be inside Argentina). `AR:identity:dni-60-business-days-after-entry` describes the parallel consular **Permiso de Ingreso** route for a worker still abroad — the employer files the entry permit, the worker collects the visa at the consulate, is automatically *radicado* on entry, then has 60 business days for the DNI. Both are valid; a TCN hired abroad typically uses the consular route.
- **CUIL vs CUIT.** CUIL (ANSES) is the labour code that lets an employee be put on payroll (`precaria-cuil-can-work`). CUIT (ARCA/AFIP) is the tax key; a temporary resident without a DNI gets a *provisional* CUIT (`cuit-provisoria-2-years`). The `non_obvious_note` on the CUIT fact also carries the 10-business-day replace-after-DNI rule from the same ARCA page.
- **RENURE quote source.** The verbatim RENURE requirement is quoted from the *Permisos de Ingreso* page (cleaner wording); the same requirement also appears on the trabajador-migrante page (with an in-page typo "Registro Registro Único"), so the cleaner source was chosen.

## Unverifiable / rejected sources
- **RENURE landing page (`argentina.gob.ar/migraciones/registro-nacional-unico-de-requirentes-de-extranjeros`)** — the contact email is rendered as a Cloudflare `[email protected]` obfuscation placeholder, so no reliable verbatim email quote could be extracted. Not used.
- **AFIP `serviciosweb.afip.gob.ar` step-by-step guides** — not used as primary quote sources for this batch; the `arca.gob.ar` static page carried the same CUIT-provisional facts as clean, curl-verifiable HTML.
- No blogs, relocation firms, or news outlets were used. No numbers, fees, or citations were invented; where the artifact did not carry a value it was left out.

## Reproduce
Raw HTML + text dumps, the quote list (`ar_quotes.tsv`), the verifier (`ar_verify.py`) and the builder (`ar_build.py`) live in the generating session's scratchpad. Re-verification re-fetches each `source_url` and asserts the `evidence_quote` is a verbatim substring and < 200 chars; all 12 pass.
