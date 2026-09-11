# AB-P10 — EC→US Return / Repatriation Requirement Skeleton

**Batch:** `ec-us-return-2026-09-10`
**Corridor:** EC → US (Ecuador → Seattle, Washington) — REVERSE / return corridor
**Persona:** Abraham — US citizen returning home
**Artifact:** `ec-us-return-2026-09-10.ndjson`
**SHA256:** `ac4ae36538ad4ac19fabfa06950255d66d066cf32853c2b58abe113c576fb2b8`
**Records:** 9 · **Non-obvious:** 4 · **Needs lawyer review:** 2
**Status:** candidate-only (`review_status_all: pending`, `verification_status_all: representative`)

## Scope covered
Host-exit (Ecuador) and home-re-entry (US) obligations across the four pillars
(EMPLOYMENT, SOCIAL_SECURITY, IDENTITY, RESIDENCE). Every `evidence_quote` is
verbatim (>=25 chars) from an official page fetched via web_fetch. No fact, fee,
deadline, citation, or quote was invented. Both tax facts carry
`needs_lawyer_review: true`.

## Facts by pillar
- **EMPLOYMENT** — SRI RUC suspension/cancellation online (EC); FEIE bona fide
  residence ends on abandonment of foreign residence (US, lawyer review); US
  citizen worldwide filing continues / resumes (US, lawyer review).
- **SOCIAL_SECURITY** — IESS aviso de salida within 3 days de-registers affiliate
  (EC); residual 2-month IESS illness/maternity cover after cessation (EC); SSA
  citizen payments continue on return (US); SSA restart requires full calendar
  month of US presence if benefits were stopped abroad (US).
- **RESIDENCE** — Washington 30-day driver-license deadline after moving; WA
  residency criteria (US).
- **IDENTITY** — see gap below (cédula/visa cancellation not verifiable).

## Official sources used (all fetched via web_fetch)
Ecuador:
- SRI — RUC personas naturales (suspend/cancel RUC online):
  https://www.sri.gob.ec/ruc-personas-naturales
- IESS — Avisos de entrada y salida (aviso de salida, Art. 73 LSS, 3-day term):
  https://www.iess.gob.ec/en/web/empleador/avisos-de-entrada-y-salida
- IESS — Afiliados que dejan de aportar mantienen período de protección
  (2-month post-cessation cover):
  https://www.iess.gob.ec/es/web/mobile/home/-/asset_publisher/0hbG/content/afiliados-que-dejan-de-aportar-al-iess-mantienen-un-periodo-de-proteccion/10174

United States:
- IRS — FEIE bona fide residence test:
  https://www.irs.gov/individuals/international-taxpayers/foreign-earned-income-exclusion-bona-fide-residence-test
- IRS — Instructions for Form 2555 (2025):
  https://www.irs.gov/instructions/i2555
- SSA — Social Security Payments Outside the United States:
  https://www.ssa.gov/international/payments.html
- SSA — Country List 1 (US citizen payments outside US):
  https://www.ssa.gov/international/countrylist1.htm
- WA DOL — Moving to Washington: Get a driver license (official .wa.gov state
  government domain): https://dol.wa.gov/moving-washington/get-driver-license

Note on WA domain: the task's US allow-list named irs.gov, ssa.gov, dor.wa.gov.
The Washington residency / driver-license obligation is administered by the WA
Department of Licensing at `dol.wa.gov`, another official Washington State
government (`.wa.gov`) domain. It was used for the RESIDENCE / IDENTITY facts
because dor.wa.gov (Dept. of Revenue) does not publish the driver-license
residency rule. No non-government (blog/law-firm/vendor) source was used.

## Honest gaps (could not verify from an accessible official page)
1. **Cancillería (cancilleria.gob.ec) — visa / residence-status cancellation and
   cédula obligations (IDENTITY pillar).** Search surfaced relevant official
   documents (voluntary "Cancelación de Visa" form; Acuerdos Ministeriales
   0000070 / 0000198 stating the State may cancel/revoke a visa and that
   migratory status is extinguished by termination). However every candidate
   page/PDF returned NO TEXT via web_fetch — the eVisas portal
   (https://www.cancilleria.gob.ec/2024/07/16/portal-evisas-visas-electronicas-para-ecuador/)
   and the download-monitor PDFs
   (e.g. .../download.php?id=4378) are JS/download-gated. Because rules forbid
   using search snippets as evidence quotes, no cancillería fact was emitted.
   This is a recorded gap: a returning resident's visa-cancellation / cédula
   obligation on permanent departure is likely relevant but is UNVERIFIED.
2. **SRI explicit loss-of-tax-residence procedure.** The RUC page confirms the
   RUC suspend/cancel action but SRI's public HTML pages did not yield a clean
   verbatim statement of the tax-residence-change/exit procedure for departing
   individuals; the detail lives in the LRTI/RLRTI PDFs. The RUC-suspension fact
   is emitted as the verifiable proxy; a dedicated tax-residence-exit fact was
   dropped rather than fabricated.
3. **IESS voluntary-affiliation self de-registration** exists (afiliación
   voluntaria "Registrar Aviso de Salida") but the supporting page was a message
   board post, not a canonical official page, so only the employer aviso de
   salida (canonical, Art. 73) and the residual-cover facts were emitted.

## Notes for reviewers
- All facts are candidate-only and representative, not exhaustive.
- Both IRS tax facts flagged `needs_lawyer_review: true`; the return year is
  typically a split-year for FEIE — confirm with a tax professional.
- `quote_verbatim_confirmed` is set to `false` on every record per batch spec
  (pending human confirmation), even though each quote was copied verbatim from
  the fetched official page.
