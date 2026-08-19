# ES→IE vendor audit — 2026-08-19

Audit of the Spain→Ireland (Madrid→Dublin) supplier layer.

> **Scope note.** As with the NO→FR audit of the same date, the task brief described a
> `supabase/seed/vendors/` tree and a `vendor_providers` table that **do not exist** in this
> repository or in production. See the NO→FR report §6 for the full absence list. This audit was
> run against the supplier layer that does exist.

## 1. The finding

**The ES→IE corridor has no supplier layer at all.**

| measure | IE | ES |
|---|---|---|
| rows in `suppliers` | **0** | **0** |
| rows in `supplier_service_capabilities` | **0** | **0** |
| categories with ≥1 supplier | **0 of 6** | **0 of 6** |

Every category is empty on both sides, including both compliance-critical ones
(`legal_admin`, `tax_finance`).

There was consequently nothing to dedup, nothing to recategorise, and nothing to reconcile. The
brief's dedup pass, its superseded-key rejection list (`savills-ireland-cork-dsp-ie`,
`crown-relocations-cork-mover-international-ie`, the five general insurers miscategorised as
`healthcare_navigation`, and the rest) and its `index.json` reconciliation all describe rows that
are **not present in this system**. None were actioned, and no rows were created so that they
could be.

## 2. The 19 `vendor_candidates` — triaged, and they do not help

> **Correction.** An earlier revision of this report called the 19 IE/ES candidates a
> "promotion-pipeline gap, not a research gap" and judged it materially cheaper than sourcing.
> **That was wrong.** Triage shows promoting all 19 would add nothing to this corridor's
> shortlist. The original text is replaced rather than annotated, because a recommendation that
> sends someone down the wrong path is worse than no recommendation.

### Zero of them are in a live category

| | |
|---|---|
| candidate categories | `customs_broker`, `pet_relocation`, `vehicle_registration`, `vehicle_shipping` |
| live categories | `legal_admin`, `movers`, `housing_agencies`, `tax_finance`, `schools`, `banks` |
| **overlap** | **0 of 19** |

Promoting every one of them leaves ES→IE at **0 of 6** categories and **0 of 2**
compliance-critical ones. They belong to the pets/vehicles product surface, not to a corridor
vendor shortlist.

### They are not ES→IE research

All 19 carry `run_id = NULL` and sit inside a single **480-row global harvest** spanning 25
countries and 18 categories. The source names are dominated by US-outbound vehicle shipping and
IPATA pet-transport directories — several of the Irish rows come from pages titled *"Schumacher
Cargo — Shipping a Car to Ireland from USA"*, *"ShipNEX — International Car Shipping to Ireland"*
and *"BR Logistics — Ship a car to Ireland"*.

These rows exist for IE and ES because a global scrape happened to cover those countries, **not
because anyone researched the Madrid→Dublin corridor**. Two of the five Irish pet entities are
US-based (Tampa, Chicago) and reach Ireland only as a destination market. For a Spain→Ireland
move — two EU states — a US RoRo car shipper is not a corridor supplier in any useful sense.

### A dedup defect worth fixing regardless

- **IE: 10 rows, 5 distinct entities.** Every Irish candidate is present exactly twice — Air
  Animal Pet Movers, K International Freight, Multi Cargo, Pets in Transit, Pets on Board. Every
  one of those rows has a populated `dedupe_key`, so **the key is not preventing duplicates**.
  That is a pipeline defect, not a data-entry accident, and it will repeat on the next harvest.
- **ES: `Relomar Relocation Services, SL` and `Relopet (Relomar Relocation Services, SL)` are the
  same legal entity** — the second name says so. 9 rows, 8 distinct entities.

Flagged, not merged — per the dedup rules, divergent-key duplicates go to the founder.

### What is good about them

Traceability, unusually: **all 19 carry both a website and a `source_url`**, which is better than
the NO→FR suppliers (30% of those have no `source_url`). Whatever pipeline produced them records
provenance properly. `corridor` is NULL on all 19 and `source_tier` is unset on all 19, so even
after promotion they would be corridor-agnostic — the same defect class as `SIRVA Worldwide`.

## 3. So the corridor is empty, and stays empty

ES→IE has no supplier layer and no candidate pool that can become one. Closing it requires
**actual sourcing against the six live categories** — the dossier-scale work the brief assumed
already existed. There is no cheaper path hiding in `vendor_candidates`.

The one genuinely useful thing the 19 provide is a negative result delivered in minutes rather
than after a promotion run that would have added US car shippers to a Madrid→Dublin shortlist.

## 3. Competitor (RMC) check

Not applicable — the corridor lists no suppliers, so no RMC can be corridor-tagged on it.

`Cartus` and `Crown World Mobility` are absent from the supplier table entirely. See the NO→FR
report §4 for the `SIRVA Worldwide` finding, which is uncountried and therefore corridor-agnostic
— **if ES→IE suppliers are promoted, that row can surface here too.** Resolve it before promoting.

## 4. Corridor context this audit does not cover

The brief supplies real corridor mechanics — DETE employment permit via EPOS before travel, Burgh
Quay IRP within 90 days against a 6–8 week queue, the PPSN→RPN sequence before first payroll to
avoid 40% emergency tax, the proof-of-address bank catch-22, Lifetime Community Rating loading
after nine months, and the two-sided Beckham/SARP tax exposure.

Those are **requirement-layer** facts. They are recorded here only to note that they shape which
categories matter for this corridor — bridge housing is a compliance dependency because PPSN needs
an Irish address first, so `housing_agencies` is arguably critical here even though the shared
category table does not mark it so. The requirement rule-engine was not touched, per the brief.

## 5. Recommended next actions

1. **Do not promote the 19.** They add zero coverage and would put US-outbound car shippers in a
   Madrid→Dublin shortlist.
2. **Fix the candidate dedup.** Every Irish candidate is duplicated despite a populated
   `dedupe_key`; the next harvest will repeat it.
3. **Source ES→IE properly** against the six live categories. This is the real cost, and nothing
   in the data avoids it.
4. Resolve `SIRVA Worldwide` before any promotion into this corridor — it is uncountried, so it
   would surface here too.

Nothing was written to the database or to any seed file.
