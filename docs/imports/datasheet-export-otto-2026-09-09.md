# Import — Multi-Country Datasheet Export methodology (Otto)

**Date:** 2026-09-09 · **Source:** Otto/Audos meeting *"Multi-Country Datasheet Export Methodology"*
(workspace `d0c29613-…`) · **Consumed by:** `backend/app/services/datasheet_export.py` (Phase 3 export).

Otto produced the data-driven export methodology that lets **"add a country" stay data-only**: a
canonical export schema + a per-country channel decision + per-country content. These files were
authored by Otto as ReloPass editorial assessment and are **NOT lawyer-verified**
(`lawyer_verified: false` throughout) — treat as representative until counsel sign-off.

## Files (under `data/`)

| File | Records / shape | Purpose |
|---|---|---|
| `export-channels.json` | 3 country blocks (NO, DE, FR) | `country_iso → export_channel` (`acroform` / `render_data_sheet` / `portal_only`) + portal metadata. All three are `render_data_sheet` (no fillable government AcroForm). |
| `export-schema.json` | 25 CSV columns, PDF section layout, `fact_key_conventions` | The canonical export shape — fixed across corridors; country content populates it. |
| `corridor-content/NO.ndjson` | 10 records | Per-step content: `section`, `step`, `authority`, `field_label`, `fact_key`, `deadline_*`, `responsible_party`, `is_non_obvious` + the `official_guidance/actual_reality/action_required/source` framework. |
| `corridor-content/DE.ndjson` | 8 records | same, Germany |
| `corridor-content/FR.ndjson` | 8 records | same, France |
| `corridor-content/GB.ndjson` | 20 records | same, United Kingdom (post-Brexit third-country: Skilled Worker/BRP-eVisa, NI, HMRC PAYE, NHS/GP, council tax, right-to-rent). Wave 1. |
| `corridor-content/ES.ndjson` | 12 records | same, Spain (EU free-mover NIE/empadronamiento vs non-EU visa/TIE, Seguridad Social, NIF/Agencia Tributaria, tarjeta sanitaria). Wave 1. |
| `corridor-content/CH.ndjson` | 12 records | same, Switzerland (canton permit B/L + EU/EFTA, Gemeinde/Anmeldung, AHV, withholding + cantonal/federal tax, health-insurance window, Pillar 3a). Wave 1. |
| `corridor-content/IT.ndjson` | 17 records | same, Italy (permesso di soggiorno, codice fiscale, anagrafe residenza, SSN, Agenzia delle Entrate; EU vs non-EU). Wave 1. |
| `corridor-content/CA.ndjson` | 20 records | same, Canada (work permit LMIA/IMP + Quebec CAQ, SIN, provincial health + wait period, CRA/T1/TD1, CPP/EI, tax-residency, Express Entry PR). Wave 1. |
| `corridor-content/AU.ndjson` | 24 records | same, Australia (482/186 visa, SBS sponsorship + nomination, skills assessment, VEVO, TFN, Medicare, super SG + fund choice, PAYG, state payroll tax, Fair Work, STP, DASP, PR). Wave 1. **`source` citation field omitted by Otto — stored NULL (not invented); citation re-request pending.** |
| `corridor-content/US.ndjson` | 45 records | same, United States (H-1B/L-1/O-1, LCA/prevailing wage, I-94, SSN, I-9, state DL/REAL ID, W-4/FICA, ACA, substantial-presence, dual-status return, tax treaty, ITIN, FBAR/FATCA, PERM green card). Wave 1. |
| `corridor-content/AE.ndjson` | 24 records | same, United Arab Emirates (MOHRE work permit + entry permit, attestation, medical fitness, residence visa, Emirates ID, labour contract, Ejari, DEWA, DHA/DOH health, WPS, end-of-service gratuity, tax-residency cert; nil personal income tax). Wave 1. |
| `corridor-content/SG.ndjson` | 25 records | same, Singapore (EP/COMPASS + S Pass + Work Permit via MOM, IPA, FIN, SingPass, tenancy stamp duty, foreign-worker levy, IRAS tax-residency + non-resident rate + IR21 clearance; CPF nil for foreign employees). Wave 2. |
| `corridor-content/IE.ndjson` | 12 records | same, Ireland (GEP/CSEP employment permit, entry visa, IRP/immigration registration, PPSN, Revenue myAccount/RPN + emergency tax, USC bands, HSE/GP, RTB tenancy, PRSI, tax residence). Wave 2. |
| `corridor-content/NL.ndjson` | 17 records | same, Netherlands (kennismigrant residence permit + MVV via IND, BSN at gemeente, 30% ruling eligibility/application/compliance, DigiD, zorgverzekering, loonheffing payroll, rental, income tax return, PE risk). Wave 2. |
| `corridor-content/SE.ndjson` | 16 records | same, Sweden (work permit + union statement via Migrationsverket, posted-worker notification, folkbokforing, personnummer/samordningsnummer, Forsakringskassan, BankID, ID card, A-skatt, SINK, A1 certificate). Wave 2. |
| `corridor-content/DK.ndjson` | 15 records | same, Denmark (Fast-track employer certification + work/residence permit via SIRI, CPR number, folkeregister, MitID, SKAT tax card, NemKonto, forsker researcher tax scheme, sundhedskort/GP, arsopgorelse, A1). Wave 2. |
| `corridor-content/BE.ndjson` | 14 records | same, Belgium (single permit + entry visa D, LIMOSA, arrival declaration + annex 19 at the commune, residence card type B, rijksregisternummer, mutualite health, ONSS/RSZ, precompte professionnel, IPP tax return). Wave 2. |
| `corridor-content/AT.ndjson` | 14 records | same, Austria (Rot-Weiss-Rot Card / EU Blue Card via AMS, entry visa D, Meldezettel + Anmeldebescheinigung, RWR collection, e-card/OGK health, Finanzamt, Arbeitnehmerveranlagung, Daueraufenthalt-EU, ASVG social insurance + A1). Wave 2. |
| `corridor-content/SA.ndjson` | 16 records | same, Saudi Arabia (block visa/tasreeh + work visa via MHRSD/Qiwa, GAMCA + in-country medical, Iqama via Jawazat, Muqeem, Absher, GOSI, CCHI health, Ejar rental; nil personal income tax). Wave 2. |
| `corridor-content/JP.ndjson` | 24 records | same, Japan (CoE + status of residence + work visa, zairyu card, juminhyo registration, My Number, shakai hoken / kokumin kenko hoken + nenkin, koyo hoken, resident tax, nenmatsu chosei / kakutei shinkoku, pension lump-sum). Wave 1. |
| `corridor-content/LU.ndjson` | 20 records | same, Luxembourg (autorisation de séjour/travail via Direction de l'Immigration + EU Blue Card, déclaration d'arrivée at the commune + Registre National, matricule national, CCSS affiliation, CNS health card, ACD tax class/withholding, cross-border/183-day + PE risk, A1). Wave 3. |
| `corridor-content/PT.ndjson` | 18 records | same, Portugal (third-country residence visa + residence permit via AIMA (ex-SEF) vs EU/EEA CRUE, NIF via Autoridade Tributária/Finanças + fiscal representative, NISS at Segurança Social, SNS número de utente, IFICI/NHR-successor incentive, IRS annual return, 183-day tracking, shadow payroll, A1). Wave 3. Otto split the block across a fence; the truncated boundary duplicate was dropped as redundant (complete record retained). |
| `corridor-content/PL.ndjson` | 19 records | same, Poland (third-country work permit type A via wojewoda or single temp-residence-and-work permit (zezwolenie jednolite) + national visa D vs EU/EEA registration; zameldowanie at the gmina, PESEL, karta pobytu, ZUS social insurance, NFZ health, NIP + PIT at the Urząd Skarbowy, 183-day residence + PE, A1). Wave 3. First conversation errored twice ("Something went wrong on my end") → re-dispatched in a fresh conversation. Otto split the block across a fence; the boundary fragment was truncated before any step/fact_key (unrecoverable) and dropped — the 19 valid records match Otto's own "19 records" count, so no unique record was lost (none invented). |
| `corridor-content/HK.ndjson` | 19 records | same, Hong Kong (employment visa via the Immigration Department under GEP / ASMTP / Top Talent Pass, HKID registration within 30 days at the Registration of Persons Office, MPF enrolment within 60 days via a trustee, Salaries Tax at the IRD — no PAYE withholding, provisional tax, employer IR56B, territorial source + 60/183-day rules, dependant visa). Wave 4. Clean single block, 0 missing sources. |
| `corridor-content/QA.ndjson` | 19 records | same, Qatar (employer work-entry permit + residence permit via the Ministry of Interior and ADLSA, Qatar Visa Centre pre-arrival biometrics/medical, in-country medical commission + fingerprinting, Qatar ID (QID), Metrash2/Hukoomi, ADLSA contract attestation, Hamad/PHCC health card, wage protection system (WPS), end-of-service gratuity, tax-residency cert; nil personal income tax). Wave 4. Clean single block, 0 missing sources. |
| `corridor-content/KR.ndjson` | 20 records | same, South Korea (employer-sponsored E-7/E-series work visa via CVIN + consulate, Alien Registration Card within 90 days via HiKorea, NHIS health, National Pension with totalization exemptions, income tax via NTS Hometax + year-end settlement (yeonmaljeongsan) + 19% flat-rate election, workplace-change reporting, 183-day residence + PE). Wave 4. Otto split the block across a fence; the truncated boundary duplicate (Hometax registration) was auto-reconciled against its complete copy and dropped as redundant — 20 valid records match Otto's "20 records" count. 0 missing sources. |

Record counts reconcile against Otto's informal manifest (NO=10, DE=8, FR=8, GB=20, ES=12, CH=12, IT=17, CA=20, AU=24, US=45, AE=24, JP=24).

## Wave 1 harvest — GB (2026-09-09)

GB was dispatched as a follow-on batch and captured the same way (inline, ART URL-repair). Two
capture notes specific to GB:

- **One record was re-emitted.** On the first pass Otto drifted off-topic mid-record inside the
  `NHS GP Registration` row (`fact_key gb.nhs_number`) — an unrelated hallucinated tangent, leaving
  that record unterminated. The other 19 were complete and valid; the NHS row was **re-emitted
  cleanly on request** (never hand-filled) to reach 20/20.
- **`step` is a descriptive string** here (e.g. `"NHS GP Registration"`), not the integer NO/DE/FR
  use. The renderer orders steps by phase with a stable sort, so `step` type does not affect ordering
  (`data_sheet_service._build_from_corridor_content`).

Operational note: Otto's process aborts on large multi-file generations in one turn, so countries are
harvested **one file per request**. `lawyer_verified: false` throughout, as with NO/DE/FR.

## Capture note (why a repair step was needed)

Otto delivered the files **inline in chat** (its GCS/attachment store path was unavailable). Audos's
code-block renderer **auto-linkified URLs**, corrupting the JSON (`"url": "www.udi.no"}` rendered as
`"url": "[www.udi.no"}/](https://www.udi.no"})`). Capture + repair:

1. Bundled the five `<pre>` blocks into a Blob and downloaded it (byte-exact vs the rendered DOM).
2. Reversed the linkification by rebuilding each URL from the markdown **href** (which carries the
   full URL + the real JSON delimiter), discarding the mangled/truncated display.
3. Validated: all five files parse; record counts match the manifest; zero `](` artifacts remain.

The only lossy field is the occasional URL that Otto truncated in the display with `…`; those were
recovered from the href, so the stored URL is the full `https://` form.

## Adding a country later (data-only)

Write `data/corridor-content/{ISO}.ndjson` following the same record shape and add a block to
`data/export-channels.json`. No code change: `datasheet_export.resolve_export_channel` reads the
channels file, and the renderer iterates corridor content by `country_iso`.
