# AB-P2 - Ecuador Pre-departure Health Resources (Quito)

**Batch ID:** `ec-predeparture-health-2026-09-10`
**Persona:** Abraham - US national relocating Seattle -> Quito, Ecuador, with accompanying family.
**Bundle file:** `ec-predeparture-health-2026-09-10.bundle.json`
**Status:** All resources are candidate-only (`status: "draft"`).

## What this bundle contains

A pre-departure health guide for a family moving to Quito, built **only** from official government sources (US CDC Travelers' Health / CDC Yellow Book, and Ecuador's Ministerio de Salud Publica). No blogs, vendors, or insurer marketing were used.

Bundle shape: `{ categories, tags, sources, resources, events }`.

- **categories:** 1 (`healthcare`)
- **tags:** 9
- **resources:** 9 (all `country_code: "EC"`, `city_name: "Quito"`, `category_key: "healthcare"`, `status: "draft"`)
- **sources:** 8 official pages (all fetched, listed below)
- **events:** `[]` (no date-bound events apply to this pre-departure health guide)

### Resources (9)
1. Recommended vaccinations before relocating to Quito - `guide`
2. Yellow fever: only for Amazon-region travel, not for Quito - `guide`
3. Ecuador Ministry of Health: yellow fever scoped to risk zones (official) - `official_link`
4. Altitude acclimatisation for Quito (~2,850 m) - the non-obvious reality - `guide`
5. Altitude acclimatisation checklist (first days in Quito) - `checklist_item`
6. Carry medical records and repeat prescriptions correctly - `guide`
7. Private / international health insurance for the cover gap - `guide`
8. Finding medical care in Quito - `guide`
9. Tip: book your pre-departure travel-health visit 4-6 weeks out - `tip`

## Topics covered and how they were sourced

| Topic | Official source(s) |
|---|---|
| Recommended vaccinations (Hep A, typhoid, Hep B, routine, measles) | CDC Ecuador destination page |
| Yellow fever scoped to Amazon-region travel only (NOT Quito) | CDC Ecuador destination page; MSP "Requisitos de ingreso al Ecuador"; MSP "Fiebre Amarilla" |
| Altitude acclimatisation (Quito ~2,850 m) | CDC "Travel to High Altitudes"; CDC Yellow Book "High-Altitude Travel and Altitude Illness" |
| Medical records & repeat prescriptions | CDC "Traveling Abroad with Medicine" |
| Private/international health insurance for the cover gap | CDC "Travel Insurance"; CDC "Getting Health Care During Travel" |
| Finding care in Quito | CDC "Getting Health Care During Travel" |

## Yellow-fever scoping note (important)

Yellow fever is deliberately **not** presented as a blanket requirement for Quito. Both sources scope it to lower-elevation Amazon-region travel:
- **CDC:** recommended for areas below 2,300 m east of the Andes (Morona-Santiago, Napo, Orellana, Pastaza, Sucumbios, Tungurahua, Zamora-Chinchipe); explicitly **not** recommended for Quito, Guayaquil, the Galapagos, or areas above 2,300 m.
- **MSP:** endemic risk zones are the Amazon provinces plus Esmeraldas; travelers to those zones are urged to vaccinate 10 days before arrival; urban areas below 1,650 m are not considered endemic.

No vaccination anywhere in this bundle is overstated as mandatory. CDC frames Hep A, typhoid, Hep B, etc. as "recommended"/"consider," and that wording is preserved.

## Sources fetched (official only)

1. CDC Travelers' Health - Ecuador, including the Galapagos Islands (Traveler View) - https://wwwnc.cdc.gov/travel/destinations/traveler/none/ecuador
2. CDC Travelers' Health - Travel to High Altitudes - https://wwwnc.cdc.gov/travel/page/travel-to-high-altitudes
3. CDC Yellow Book 2026 - High-Altitude Travel and Altitude Illness - https://www.cdc.gov/yellow-book/hcp/environmental-hazards-risks/high-altitude-travel-and-altitude-illness.html
4. CDC Travelers' Health - Traveling Abroad with Medicine - https://wwwnc.cdc.gov/travel/page/travel-abroad-with-medicine
5. CDC Travelers' Health - Getting Health Care During Travel - https://wwwnc.cdc.gov/travel/page/getting-health-care-during-travel
6. CDC Travelers' Health - Travel Insurance - https://wwwnc.cdc.gov/travel/page/insurance
7. Ministerio de Salud Publica del Ecuador (MSP) - Requisitos de ingreso al Ecuador - https://www.salud.gob.ec/requisitos-de-ingreso-al-ecuador/
8. Ministerio de Salud Publica del Ecuador (MSP) - Fiebre Amarilla - https://www.salud.gob.ec/fiebre-amarilla/

## Honest gaps (could not source officially)

- **IESS affiliation timing / public-insurance start dates.** The task framed private insurance as covering the gap "before IESS affiliation." CDC's official pages cover the general principle (US insurance often won't cover care abroad; national systems often exclude non-citizens; buy private/international cover, consider medical-evacuation cover) - and that is what the insurance resource is built on. However, the **specific rules, eligibility, and timing of Ecuador's public social-security health system (IESS)** are not addressed by CDC, and I did not locate an authoritative statement of them on the MSP or Cancilleria pages I was able to fetch. The insurance resource therefore flags IESS as a matter to confirm through official Ecuadorian channels rather than asserting any timeframe.
- **Quito-specific hospitals/clinics.** No official source names individual providers, and CDC explicitly does not endorse providers. The "Finding care" resource therefore points to official mechanisms (US embassy/STEP, ISTM and IAMAT directories, CDC Find a Clinic) instead of naming facilities.
- **cancilleria.gob.ec** was listed as an allowed source but did not yield a health/insurance page needed for these topics; the CDC and MSP pages fully covered the required scope, so no cancilleria page is cited.

## Nothing invented

Every factual claim traces to one of the eight fetched official pages. Where an official statement was unavailable (IESS specifics, named clinics), the bundle says so rather than filling the gap.
