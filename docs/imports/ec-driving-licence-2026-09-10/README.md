# ReloPass Bundle — Ecuador Driving Licence Guide (Abraham)

- **Batch ID:** `ec-driving-licence-2026-09-10`
- **Task:** AB-P5 — Ecuador driving-licence exchange guide
- **Persona:** Abraham — US national relocating Seattle, WA → Quito, Ecuador
- **Bundle file:** `ec-driving-licence-2026-09-10.bundle.json`
- **Status:** all resources are `draft` (candidate-only)
- **Generated:** 2026-09-11

## Question answered

1. **How long can Abraham drive on a US licence / IDP in Ecuador?**
   - Ecuadorian law (as corroborated by the U.S. Embassy in Ecuador) allows tourists / temporary
     visitors to drive on a **valid foreign licence** of a category equivalent to a non-professional
     Ecuadorian **Type B** licence. Passport/visa may be checked.
   - **An Ecuador-issued International Driving Permit (PIC) is explicitly NOT valid in Ecuador** — it
     is an outbound document for Ecuadorian licence-holders driving abroad. A US-issued IDP only
     accompanies/translates the US licence; it does not extend local driving rights.
   - **HONEST GAP:** no official ANT / Cancillería page publishes a **specific number of days/months**
     for the visitor grace period. See the gap note below.

2. **Can a US licence be exchanged, or is a local test required?**
   - Yes — via the ANT **"Canje de licencia de conducir extranjera por ecuatoriana."** It is a
     **document convalidation**, not a fresh driving exam. ANT lists **no practical/theory test** as a
     requirement for the exchange route.

3. **Process / where to apply / documents:**
   - Apply **in person** at an **ANT Provincial Directorate** (in Quito: Pichincha / ANT Matriz),
     Mon–Fri 08h00–16h30. Generate payment order on the ANT website → pay → submit docs → receive licence.
   - **Cost:** USD **142.00** (no VAT) + bank commission (ANT tariff 2024, Res. 025-DIR-2023-ANT).
   - **Issued licence validity:** **5 years** (or limited to the visa/authorised stay if shorter).
   - **Documents:** ID; Cruz Roja blood-type certificate; valid foreign licence; an official Spanish
     certification of the foreign licence (apostilled/consularised + notarised translation as needed —
     for a US licence: DMV certification → state Secretary of State apostille → translation); proof of
     payment; migratory-movement certificate. Holder must read/write Spanish.

## Bundle contents

- **categories:** 1 (`transport`)
- **tags:** 8
- **sources:** 3 (2 primary ANT official pages actually fetched + 1 corroborating US-Gov page)
- **resources:** 7 — 2 guides, 1 checklist_item, 2 tips, 2 official_link
- **events:** 0

## Sources (all actually fetched)

1. ANT / gob.ec — **Canje de licencia de conducir extranjera por ecuatoriana**
   https://www.gob.ec/ant/tramites/canje-licencia-conducir-extranjera-ecuatoriana
   (PRIMARY — exchange requirements, cost, validity, legal basis. Page updated 2026-01-13.)
2. ANT / gob.ec — **Emisión de permiso internacional para conductores**
   https://www.gob.ec/ant/tramites/emision-permiso-internacional-conductores
   (PRIMARY — confirms Ecuador-issued IDP is NOT valid in Ecuador. Page updated 2026-01-13.)
3. U.S. Embassy & Consulate in Ecuador — **Information about U.S. Driver License in Ecuador**
   https://ec.usembassy.gov/es/services-es/information-about-u-s-driver-license-in-ecuador-es/
   (SECONDARY / corroborating only — official U.S. Government source, not on the ANT/Cancillería
   allow-list. Used solely to corroborate the visitor-driving allowance and the DMV+apostille route.
   It does NOT establish a specific grace period.)

`ant.gob.ec` root and section pages (`/licencias-de-conducir/`) returned no text via the scraper;
the equivalent authoritative content is served by the government portal **gob.ec/ant**, which is the
official ANT trámite guide and was used instead.

## Rule I could NOT confirm officially (honest gap)

**The specific length of the tourist / temporary-visitor driving grace period is NOT published on any
official source (`ant.gob.ec`, `gob.ec/ant`, or `cancilleria.gob.ec`).**

- The commonly-cited figures — "up to **one year** for tourism" and "exchange required if your visa is
  **> 180 days**" — appear **only on ANT's social-media posts** (Facebook / Instagram / X) and on
  third-party blog/vendor pages. These do **not** meet ReloPass's official-source standard, so they are
  **not asserted as fact** anywhere in this bundle.
- Cancillería pages cover only Ecuadorians renewing Ecuadorian licences abroad — nothing about
  foreigners driving in Ecuador.

**Recommendation:** confirm the current grace period directly with ANT (Contacto Ciudadano Digital,
tel. 023828890) or at the ANT Quito office. The **canje** is the safe, officially-documented path once
Abraham is a resident.

## Verification

- Bundle validated as well-formed JSON (7 resources, 3 sources, 0 events).
- SHA-256 checksums recorded at delivery; both files uploaded to GCS via `store_attachment`.
