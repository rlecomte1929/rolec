# Otto vendor re-sourcing brief — 2026-09-08

**Why:** the 2026-08-17 vendor batches cited each vendor's OWN site (or an aggregator) as `source_url`, so 235 of 250 rejected as tier-3 self-declared. This brief says, per city × category, which register to cite instead and the exact URL shape the import gate requires. Sourcing to these registers is the only change needed — vendor identity (name/site/phone/city) was already fine.

**Hard rules (unchanged):** cite the REGISTER, never the provider's own site, an aggregator (Wikipedia / northdata / moverdb / paginegialle / gelbeseiten / 11880 / justlanded), Google Maps, or a review site. One `source_url` per vendor = the register's per-entity page (or the register page + a real licence/roll/registration number where noted). Never invent a URL, a number, or a provider. A vendor you cannot find on its register is a REJECT, not a guess — report it, don't fabricate. Keep the existing NDJSON record shape; only fix `source_url` (+`accreditation_number`/`accreditation_source_url` where the register gives one). Batch small: one city × category at a time.

## Legend
- **HARVESTABLE** — re-source now against the named register.
- **REGISTRY-GAP** — do NOT re-source yet: no register is wired for this pair in the product, so any evidence would still reject. Needs a `registry_sources.py` entry added first (ReloPass code task, not Otto). Listed so the effort isn't wasted.
- **UNHARVESTABLE** — a register is known but confirmed unusable (login-gated / no public search); needs an alternative register identified first.

### Paris — corridor `NO-FR` (destination FR)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
    - or **Chambre Syndicale du Déménagement (CSD) — annuaire adhérents** (`https://www.csdemenagement.fr/`), tier 2. URL must match `/annuaire-demenageurs/\d+`.
- **housing_agencies** — HARVESTABLE → cite **FNAIM — annuaire des adhérents (Paris)** (`https://www.fnaim.fr/`), tier 2. URL must match `/agence-immobiliere/\d+`.
- **legal_admin** — HARVESTABLE → cite **Barreau de Paris — annuaire des avocats** (`https://www.avocatparis.org/annuaire`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **tax_finance** — HARVESTABLE → cite **Ordre des Experts-Comptables — annuaire** (`https://annuaire.experts-comptables.org/`), tier 1. URL must match `/expert-comptable/\d+`.
- **banks** — HARVESTABLE → cite **REGAFI — registre des agents financiers (ACPR / Banque de France)** (`https://www.regafi.fr/`), tier 2. URL must match `id_referentiel=\d+`.
- **schools** — HARVESTABLE → cite **Annuaire de l'Éducation nationale (annuaire-education.fr)** (`https://annuaire-education.fr/`), tier 2. URL must match `/etablissement/`.

### Oslo — corridor `FR-NO` (destination NO)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
    - or **EuRA member directory** (`https://www.eura-relocation.com/members/`), tier 1. URL must match `/members/[^/]`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **housing_agencies** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
    - or **EuRA member directory** (`https://www.eura-relocation.com/members/`), tier 1. URL must match `/members/[^/]`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **legal_admin** — HARVESTABLE → cite **Advokatforeningen + Brønnøysund register (NO)** (`https://www.advokatenhjelperdeg.no/`), tier 1. URL must match `/oppslag/enheter/\d+|/advokat/\d+`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **tax_finance** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **banks** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
- **schools** — REGISTRY-GAP: no register wired for NO/schools. Do not re-source until one is added to `registry_sources.py`.

### Madrid — corridor `XX-ES` (destination ES)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — REGISTRY-GAP: no register wired for ES/housing_agencies. Do not re-source until one is added to `registry_sources.py`.
- **legal_admin** — REGISTRY-GAP: no register wired for ES/legal_admin. Do not re-source until one is added to `registry_sources.py`.
- **tax_finance** — REGISTRY-GAP: no register wired for ES/tax_finance. Do not re-source until one is added to `registry_sources.py`.
- **banks** — REGISTRY-GAP: no register wired for ES/banks. Do not re-source until one is added to `registry_sources.py`.
- **schools** — HARVESTABLE → cite **IBO — IB World Schools directory** (`https://www.ibo.org/programmes/find-an-ib-school/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

### Dublin — corridor `ES-IE` (destination IE)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — HARVESTABLE → cite **PSRA — Register of Licensed Property Services Providers** (`https://www.psr.ie/en/psra/register/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **legal_admin** — HARVESTABLE → cite **Law Society of Ireland — Find a Solicitor** (`https://www.lawsociety.ie/Find-a-Solicitor/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **tax_finance** — HARVESTABLE → cite **CPA Ireland — firm directory** (`https://www.cpaireland.ie/find-a-cpa/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **banks** — HARVESTABLE → cite **Central Bank of Ireland — Register of Authorised Firms** (`https://registers.centralbank.ie/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **schools** — HARVESTABLE → cite **Tusla — Register of Independent Schools** (`https://www.tusla.ie/services/preschool-services/independent-schools/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

### Stavanger — corridor `FR-NO` (destination NO)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
    - or **EuRA member directory** (`https://www.eura-relocation.com/members/`), tier 1. URL must match `/members/[^/]`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **housing_agencies** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
    - or **EuRA member directory** (`https://www.eura-relocation.com/members/`), tier 1. URL must match `/members/[^/]`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **legal_admin** — HARVESTABLE → cite **Advokatforeningen + Brønnøysund register (NO)** (`https://www.advokatenhjelperdeg.no/`), tier 1. URL must match `/oppslag/enheter/\d+|/advokat/\d+`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **tax_finance** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
    - or **INSEE SIRENE / recherche-entreprises (FR)** (`https://recherche-entreprises.api.gouv.fr/search`), tier 2. URL must match `^https://annuaire-entreprises\.data\.gouv\.fr/entreprise/\d{9}$`.
- **banks** — HARVESTABLE → cite **Finanstilsynet — estate agency register (NO)** (`https://www.finanstilsynet.no/en/registers/`), tier 1. URL must match `[?&]id=\d+`.
- **schools** — REGISTRY-GAP: no register wired for NO/schools. Do not re-source until one is added to `registry_sources.py`.

### Aberdeen — corridor `XX-GB` (destination GB)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — HARVESTABLE → cite **ARLA Propertymark — member directory** (`https://www.propertymark.co.uk/`), tier 2. URL must match `/company/`.
- **legal_admin** — HARVESTABLE → cite **SRA — Solicitors Regulation Authority register** (`https://www.sra.org.uk/consumers/register/`), tier 2. URL must match `sraNumber=\d+`.
- **tax_finance** — HARVESTABLE → cite **ICAEW — Find a Chartered Accountant** (`https://find.icaew.com/`), tier 2. URL must match `/firms/`.
- **banks** — HARVESTABLE → cite **FCA Financial Services Register** (`https://register.fca.org.uk/s/`), tier 2. URL must match `/s/firm`.
- **schools** — HARVESTABLE → cite **GIAS — Get Information About Schools (DfE)** (`https://get-information-schools.service.gov.uk/`), tier 2. URL must match `/Establishment/Details/\d+`.

### Stockholm — corridor `XX-SE` (destination SE)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — REGISTRY-GAP: no register wired for SE/housing_agencies. Do not re-source until one is added to `registry_sources.py`.
- **legal_admin** — REGISTRY-GAP: no register wired for SE/legal_admin. Do not re-source until one is added to `registry_sources.py`.
- **tax_finance** — REGISTRY-GAP: no register wired for SE/tax_finance. Do not re-source until one is added to `registry_sources.py`.
- **banks** — REGISTRY-GAP: no register wired for SE/banks. Do not re-source until one is added to `registry_sources.py`.
- **schools** — HARVESTABLE → cite **IBO — IB World Schools directory** (`https://www.ibo.org/programmes/find-an-ib-school/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

### Copenhagen — corridor `XX-DK` (destination DK)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — HARVESTABLE → cite **MDE — Dansk Ejendomsmæglerforening members** (`https://www.de.dk/boligkob-salg/find-medlem`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **legal_admin** — HARVESTABLE → cite **Advokatsamfundet — Advokatnøglen (Danish bar)** (`https://www.advokatnoeglen.dk/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **tax_finance** — HARVESTABLE → cite **FSR — danske revisorer member directory** (`https://www.fsr.dk/vaerktoejer/find-revisor`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **banks** — HARVESTABLE → cite **Finanstilsynet — Danish FSA company register** (`https://virksomhedsregister.finanstilsynet.dk/index-en.html`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **schools** — HARVESTABLE → cite **IBO — IB World Schools directory** (`https://www.ibo.org/programmes/find-an-ib-school/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

### Helsinki — corridor `XX-FI` (destination FI)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — REGISTRY-GAP: no register wired for FI/housing_agencies. Do not re-source until one is added to `registry_sources.py`.
- **legal_admin** — HARVESTABLE → cite **Finnish Bar Association — Find an Attorney** (`https://www.findanattorney.fi/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **tax_finance** — HARVESTABLE → cite **PRH — Finnish auditor register (Tilintarkastajahaku)** (`https://tietopalvelut.prh.fi/tilintarkastajahaku/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **banks** — HARVESTABLE → cite **ECB Banking Supervision — supervised entities (SSM)** (`https://www.bankingsupervision.europa.eu/banking/list/who/html/index.en.html`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).
- **schools** — HARVESTABLE → cite **IBO — IB World Schools directory** (`https://www.ibo.org/programmes/find-an-ib-school/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

### Berlin — corridor `FR-DE` (destination DE)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — UNHARVESTABLE: IVD — Immobilienverband Deutschland directory, FNAIM (FR) (known but unusable). Needs an alternative register first.
- **legal_admin** — HARVESTABLE → cite **Official public business register (DE)** (`https://www.hamburg.de/branchenbuch/`), tier 2. URL must match `/branchenbuch/.+/eintrag/\d+`.
- **tax_finance** — HARVESTABLE → cite **Official public business register (DE)** (`https://www.hamburg.de/branchenbuch/`), tier 2. URL must match `/branchenbuch/.+/eintrag/\d+`.
    - or **BaFin institute register (DE)** (`https://portal.mvp.bafin.de/database/InstInfo/`), tier 1. URL must match `institutId=\d+|/account/\w+`.
- **banks** — HARVESTABLE → cite **BaFin institute register (DE)** (`https://portal.mvp.bafin.de/database/InstInfo/`), tier 1. URL must match `institutId=\d+|/account/\w+`.
- **schools** — REGISTRY-GAP: no register wired for DE/schools. Do not re-source until one is added to `registry_sources.py`.

### Frankfurt — corridor `FR-DE` (destination DE)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — UNHARVESTABLE: IVD — Immobilienverband Deutschland directory, FNAIM (FR) (known but unusable). Needs an alternative register first.
- **legal_admin** — HARVESTABLE → cite **Official public business register (DE)** (`https://www.hamburg.de/branchenbuch/`), tier 2. URL must match `/branchenbuch/.+/eintrag/\d+`.
- **tax_finance** — HARVESTABLE → cite **Official public business register (DE)** (`https://www.hamburg.de/branchenbuch/`), tier 2. URL must match `/branchenbuch/.+/eintrag/\d+`.
    - or **BaFin institute register (DE)** (`https://portal.mvp.bafin.de/database/InstInfo/`), tier 1. URL must match `institutId=\d+|/account/\w+`.
- **banks** — HARVESTABLE → cite **BaFin institute register (DE)** (`https://portal.mvp.bafin.de/database/InstInfo/`), tier 1. URL must match `institutId=\d+|/account/\w+`.
- **schools** — REGISTRY-GAP: no register wired for DE/schools. Do not re-source until one is added to `registry_sources.py`.

### Milan — corridor `XX-IT` (destination IT)
- **movers** — HARVESTABLE → cite **FIDI FAIM member directory** (`https://www.fidi.org/find-fidi-affiliate`), tier 1. URL must match `/find-fidi-affiliate/[^/]`.
- **housing_agencies** — REGISTRY-GAP: no register wired for IT/housing_agencies. Do not re-source until one is added to `registry_sources.py`.
- **legal_admin** — REGISTRY-GAP: no register wired for IT/legal_admin. Do not re-source until one is added to `registry_sources.py`.
- **tax_finance** — REGISTRY-GAP: no register wired for IT/tax_finance. Do not re-source until one is added to `registry_sources.py`.
- **banks** — REGISTRY-GAP: no register wired for IT/banks. Do not re-source until one is added to `registry_sources.py`.
- **schools** — HARVESTABLE → cite **IBO — IB World Schools directory** (`https://www.ibo.org/programmes/find-an-ib-school/`), tier 2. no per-entity URL — cite the register page **and** put the licence/roll/registration number in accreditation_number (vetter confirms by name+number).

## Totals

- HARVESTABLE pairs (re-source now): **53**
- REGISTRY-GAP pairs (need a registry wired first): **17**
- UNHARVESTABLE pairs (register known but unusable): **2**

The 15 rows that already pass (`passing_set.md`) are all in HARVESTABLE pairs and need no rework — they are the proof the pipeline lands clean data when the source is a register.

