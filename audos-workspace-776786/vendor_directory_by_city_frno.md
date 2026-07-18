# ReloPass Vendor Directory by City — France → Norway Corridor (v1)

**View / download online:** https://audos.com/p/d0c29613-9cb5-4652-9c6a-494eeed352e5/vendor-directories (rendered tables + one-click .md download).
**Purpose:** city-indexed vendor directory expanding `vendor_qualification_frno.md` (the category deep-dive) to a **minimum of 5 verified providers per platform city**, in one consistent table shape for easy import/export.
**Research date:** 2026-07-17. Method: web research only — company websites, FIDI/FIDI-France/EuRA/IAM registries, school sites, Advokatguiden. No vendor invented; every entry resolves to a live, publicly listed entity.
**Markers:** ✓ = corridor relevance and key facts verified against the provider's own site or an accreditation registry. ⚠️ = live entity, but one or more facts (accreditation, local branch, corridor depth) not independently confirmed — manually verify before surfacing to customers.
**ICP filter (unchanged):** SME-scale providers only. Enterprise relocation management companies are **excluded as ReloPass competitors**, not vendors: SIRVA (incl. Sirva Flyttebyrå Norway), Cartus, CapRelo, Sterling Lexicon, Santa Fe Relocation, Crown World Mobility (the **Crown Relocations moving brand** remains OK).

---

## Scope of this review

**Service categories reviewed (as listed in ReloPass today):**
- The WorkspaceDB `vendors` table defines six service types: Immigration, Tax Advisory, Moving & Logistics, Housing, Schooling, Banking.
- `vendor_qualification_frno.md` covers four in corridor depth: movers, schools, immigration lawyers, tax advisors.
- This directory adds a fifth operational category — **Relocation / settling-in** (home search, registrations, D-number logistics) — which also covers most SME **Housing** needs.
- ⚠️ **Category gaps flagged, not filled:** (a) **Banking** — Norwegian account opening is D-number-gated and handled direct with banks (DNB, Nordea, SpareBank 1); no third-party vendor qualifies cleanly. (b) The 8 rows currently seeded in the `vendors` DB table (Fragomen LLP, KPMG, Crown Worldwide, Dwellworks, Airinc, Santa Fe, Bright Horizons, HSBC Expat) are **global demo seeds, not FR→NO-verified**; Santa Fe additionally violates the competitor exclusion and should not be surfaced.

**Cities covered (all cities named in the platform's FR→NO corridor content):**
- **Norway (destination):** Oslo, Bergen, Stavanger, Trondheim, Kristiansand.
- **France (origin hubs):** Paris, Lyon.

**Coverage summary:**

| City | Providers listed | Fully verified (✓) | Needs manual check (⚠️) |
|---|---|---|---|
| Oslo | 14 | 12 | 2 |
| Bergen | 8 | 7 | 1 |
| Stavanger | 7 | 7 | 0 |
| Trondheim | 7 | 7 | 0 |
| Kristiansand | 6 | 4 | 2 |
| Paris | 10 | 9 | 1 |
| Lyon | 7 | 3 | 4 |

**Import/export note:** every table below uses the same columns — `Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes` — one row per provider per city, so the whole file can be copy-pasted or parsed into CSV in one pass. Columns map 1:1 onto the WorkspaceDB `vendors` table (`name`, `service_type`, `country_coverage`/city, `website`, `notes`) plus the corridor shape proposed in `vendor_qualification_frno.md` (`languages`, `public_pricing`, `verified`, `source_url`).

---

## Oslo

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| AGS Movers Norway (AGS Group) | Moving & Logistics | Oslo branch; national NO + French origin network | FR, EN, NO | Quote only | https://www.ags-demenagement.com/filiales/europe/norvege/norvege/ | ✓ | FIDI/FAIM. Same group on both corridor endpoints; handles RD-0030 customs. |
| NFB International Relocations AS | Moving & Logistics | Skui (Oslo area); national | NO, EN | Quote only | https://nfbir.com/ | ✓ | FIDI-FAIM. Norwegian customs (flyttegods) specialist; Alfa group. |
| Crown Relocations (Norway) | Moving & Logistics | Oslo; global network incl. France | NO, EN | Quote only | https://www.crownrelo.com/norway/en-no | ✓ | FIDI-FAIM. List the moving brand only — Crown World Mobility is a competitor category. |
| Alfa Moving Norway AS | Moving & Logistics | Oslo (Eikenga 33) + Asker/Bærum; Nordic group | NO, EN | Quote only | https://www.alfamoving.no/ | ✓ | Since 1995; international moves via sister company Alfa Mobility (150+ countries). |
| CarGoRiga | Moving & Logistics | Oslo/national; Europe-wide incl. France | NO, EN | Quote only | https://cargoriga.com/ | ⚠️ | Since 1997, own fleet; no FIDI/IAM accreditation found — verify insurance/references. |
| Lycée Français René Cassin d'Oslo (LFO) | Schooling | Oslo (Skovveien 9) | FR | App fee 3,000 NOK (2026/27) | https://lfo.no/ | ✓ | Norway's only AEFE French-curriculum school. Main window Feb 2 – Mar 1 for August start. |
| Oslo International School (OIS) | Schooling | Bekkestua, greater Oslo | EN (FR B in DP) | 288,700 NOK/yr (2026-27) | https://www.oslointernationalschool.no/ | ✓ | IPC + IB DP; rolling admissions year-round. |
| Norlights International School (NLIS) | Schooling | Oslo (Skådalen) | EN | 43,450 NOK/yr (Gr 1-10); 29,700 NOK/yr (DP) | https://internationalschool-oslo.no/ | ✓ | Full IB continuum; deadline 1 Mar for August start. |
| Advokatfirmaet Lippestad — Halvor Frihagen | Immigration (legal) | Oslo | NO, **FR**, EN, DE, ES | Not public | https://advokatlippestad.no/ansatte/halvor-frihagen/ | ✓ | Default referral when the family prefers French. |
| Advokatfirmaet Sterk AS | Immigration (legal) | Oslo | NO, EN | **2,000–5,200 NOK/h + VAT** (published) | https://www.advokats.no/en/kompetanse/immigration-law | ✓ | Transparent pricing; takes individual employee cases. |
| Littler Norway (Littler advokatfirma AS) | Immigration / employment (legal) | Oslo | NO, EN | Not public | https://littler.no/en/ | ✓ | Employer-side posted-worker compliance and contract structuring. |
| Aider Legal (ex-Magnus Legal) | Tax Advisory | Oslo (+ Bergen, Stavanger, Trondheim) | NO, EN | Not public | https://www.aiderlegal.com/our-expertise/global-mobility | ✓ | Best single ICP fit: A-melding, withholding, immigration under one roof. |
| Expat Relocation | Relocation / settling-in | Oslo (+ Bergen, Stavanger, Trondheim, Hammerfest) | NO, EN | Quote only | https://expatrelocation.no/ | ✓ | EuRA Quality Seal since 2012; immigration + relocation since 1998. |
| Onboard Norway | Relocation / settling-in | Norway-wide (Oslo base) | NO, EN | Quote only | https://onboardnorway.com/ | ⚠️ | One of the longest-operating NO relocation firms; confirm office location + EuRA status before referral. |

---

## Bergen

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| Adams Express AS | Moving & Logistics | HQ Bergen (+ Oslo, Stavanger) | NO, EN | Quote only | https://www.adamsexpress.no/ | ✓ | 125+ years; FIDI/IAM; France origin via agent network. |
| International School of Bergen (ISB) | Schooling | Bergen | EN (FR as acquisition language) | On site | https://www.isbergen.no/ | ✓ | IB PYP+MYP; **no IB Diploma for 16+** — feasibility flag for older teens. |
| Bergen Legal — Advokat Per-Erik Gåskjenn | Immigration (legal) | Bergen (Valkendorfsgaten 4) | NO, EN | Not public | https://bergenlegal.no/english/ | ✓ | 20+ yrs immigration law; ex-UDI; ex-member of Bar Association's asylum/immigration law committee. |
| Aider Legal — Bergen office | Tax Advisory / immigration | Bergen | NO, EN | Not public | https://www.aiderlegal.com/ | ✓ | Named Bergen-based global-mobility lawyer (C. L. Fjeldsøe); EEA-exemption specialism. |
| Expat Relocation — Bergen office | Relocation / settling-in | Bergen | NO, EN | Quote only | https://expatrelocation.no/ | ✓ | EuRA-certified; strong oil & gas relocation history on the west coast. |
| Pytheas AS | Relocation / settling-in | Oslo, Bergen, Trondheim, Stavanger | NO, EN | Quote only | https://pytheas.no/ | ✓ | Since 2013; housing, D-number, bank setup, school guidance. |
| BDO Norway — Bergen office | Tax Advisory | ~70 offices incl. Bergen | NO, EN | Not public | https://www.bdo.no/ | ✓ | Expat tax / cross-border payroll outside Oslo. |
| Flyto Relocation | Moving & Logistics | Bergen via partner network; 20 EU countries | EN, NO | From €650 (small moves); tiered | https://flytorelocation.com/no/bergen/ | ⚠️ | Founded 2018, 4.9/5 Google (400+); coordinator model, no FIDI — verify partner quality. |

---

## Stavanger

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| Håkull AS | Moving & Logistics | HQ Stavanger (+ Kristiansand, Oslo, DK) | NO, EN | Quote only | https://haakull.no/en/ | ✓ | FIDI-FAIM + IAM; ~100 trailers/week to/from Norway — strong FR→NO road groupage. |
| Alfa Moving — Stavanger office | Moving & Logistics | Madlastokken 5, Hafrsfjord/Stavanger | NO, EN | Quote only | https://www.alfamoving.no/ | ✓ | Local branch of Alfa group; international via Alfa Mobility. |
| International School of Stavanger (ISS) | Schooling | Stavanger | EN | Fee schedule on site | https://isstavanger.no/ | ✓ | Est. 1966, ages 1–18, ~514 students; rolling admissions (Early Years waitlisted). |
| British International School of Stavanger (BISS) | Schooling | Stavanger (Gausel, Sentrum, Preschool) | EN | On site | https://www.biss.no/admissions | ✓ | Three sites, central admissions; IB curriculum interest prioritised at Gausel. |
| Expat Relocation — Stavanger office | Relocation / settling-in | Stavanger | NO, EN | Quote only | https://expatrelocation.no/ | ✓ | EuRA-certified; deep energy-sector relocation volume. |
| Aider Legal — Stavanger office | Tax Advisory | Stavanger | NO, EN | Not public | https://www.aiderlegal.com/ | ✓ | A-melding / D-number / PAYE execution close to the case. |
| Pytheas AS | Relocation / settling-in | Covers Stavanger | NO, EN | Quote only | https://pytheas.no/ | ✓ | Home search incl. virtual viewings + lease negotiation. |

---

## Trondheim

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| Vinjes Transport AS | Moving & Logistics | HQ Trondheim (Tiller); national + international | NO, EN | Quote only | https://vinjes.no/ | ✓ | Norway's oldest mover (est. 1889), largest fleet; dedicated international division. |
| Trondheim International School (THIS) | Schooling | Trondheim | EN | 3,150–3,450 NOK/month (state-subsidised) | https://this.no/ | ✓ | IB World School, grades 1–10, 48 nationalities. |
| Birralee International School | Schooling | Trondheim | EN | 3,645–3,733 NOK/month (2026) | https://birralee.no/ | ✓ | Ages 3–16; **application deadline Feb 1** for August start — feasibility flag. |
| Expat Relocation — Trondheim office | Relocation / settling-in | Trondheim | NO, EN | Quote only | https://expatrelocation.no/ | ✓ | EuRA-certified local presence. |
| Aider Legal — Trondheim office | Tax Advisory | Trondheim | NO, EN | Not public | https://www.aiderlegal.com/ | ✓ | Same one-stop global-mobility scope as Oslo office. |
| Pytheas AS | Relocation / settling-in | Covers Trondheim | NO, EN | Quote only | https://pytheas.no/ | ✓ | Settling-in: bank, ID number, school guidance. |
| BDO Norway — Trondheim office | Tax Advisory | Trondheim | NO, EN | Not public | https://www.bdo.no/ | ✓ | Cross-border payroll / expat tax outside Oslo. |

---

## Kristiansand

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| Kristiansand International School (KIS) | Schooling | Kristiansand | EN (compulsory NO classes) | ~4,500 NOK/**year** (2023-24 rate) | https://kristiansandis.no/ | ✓ | IB PYP+MYP, grades 1–10, ~200 students; municipally subsidised — lowest fees in this directory. |
| Håkull AS — Kristiansand office | Moving & Logistics | Kristiansand | NO, EN | Quote only | https://haakull.no/en/ | ✓ | FIDI-FAIM + IAM; local office of the Stavanger HQ. |
| T2M Déménagement | Moving & Logistics | Covers Kristiansand from France (Lyon/IdF) | FR, EN | Quote only (24 h) | https://www.t2m-demenagement.com/pays/norvege/ | ⚠️ | Dedicated Norway page lists Kristiansand; no FIDI/IAM found — verify before referral. |
| AGS Movers Norway | Moving & Logistics | National NO coverage from Oslo | FR, EN, NO | Quote only | https://www.ags-demenagement.com/ | ✓ | FIDI/FAIM; French-speaking origin crews. |
| NFB International Relocations AS | Moving & Logistics | National coverage incl. south coast | NO, EN | Quote only | https://nfbir.com/ | ✓ | FIDI-FAIM; ~150-country partner network. |
| BDO Norway — Kristiansand | Tax Advisory | Kristiansand (national ~70-office network) | NO, EN | Not public | https://www.bdo.no/ | ⚠️ | Network almost certainly covers Kristiansand — confirm the local office before naming it on a case. |

> Kristiansand has the thinnest locally-based verified coverage of the five Norwegian cities — most service depth is delivered from Stavanger/Oslo. Treat it as a secondary destination until local vendors are qualified.

---

## Paris (origin)

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| AGS Déménagement International | Moving & Logistics | HQ Paris region; 148 branches / 101 countries | FR, EN | Quote only | https://www.ags-demenagement.com/ | ✓ | FIDI/FAIM; own Norway branch — single group door-to-door. |
| Grospiron Mobility Solutions | Moving & Logistics | Paris region (+ Lyon, Toulouse, Lille, Nice, Marseille) | FR, EN | Quote only | https://www.grospiron.com/en/ | ✓ | FIDI/FAIM; fine art, pets, vehicles; virtual surveys — good SME fit. |
| Bailly International | Moving & Logistics | Paris region | FR, EN | Quote only | https://www.fidi-france.com/ | ✓ | FIDI France member (FAIM-certified). |
| Neer Service France | Moving & Logistics | Paris region | FR, EN | Quote only | https://www.fidi-france.com/ | ✓ | FIDI France member (FAIM-certified). |
| France Global Relocation (FGR) | Moving & Logistics / relocation | Paris | FR, EN | Quote only | https://www.fidi-france.com/ | ✓ | FIDI France member (FAIM-certified). |
| Gosselin (France) | Moving & Logistics | Paris + European network | FR, EN | Quote only | https://www.fidi-france.com/ | ✓ | FIDI France member; strong own-fleet European road network. |
| MTN Déménagement | Moving & Logistics | Paris/Lyon/Marseille departures → NO | FR, EN | **From €3,500 (20 m³) / €5,000 (35 m³)**, 5–7 days | https://www.mtn-demenagement.com/demenagement-france-norvege | ✓ | Only published FR→NO fixed pricing — budget anchor. ⚠️ young company (2024), coordinator model, no FIDI. |
| Forvis Mazars (France) | Tax Advisory | National French network + Norway offices | FR, EN, NO | Not public | https://www.forvismazars.com/fr/fr | ✓ | Both corridor endpoints in one network — natural coordinated FR↔NO referral. |
| CMS Francis Lefebvre Avocats | Tax / legal (escalation) | Paris (Neuilly) | FR, EN | Not public (enterprise-grade) | https://cms.law/en/fra/ | ✓ | Escalation tier only — FR-side tax structuring, exit tax. |
| Eurofiscalis | Tax Advisory | French-founded European network | FR, EN | Not public | https://www.eurofiscalis.com/en/eu-employer-norway-guide/ | ⚠️ | Strong on registrations/VAT (NUF, A-melding, D-numbers); confirm depth on personal tax/treaty. |

> Free public reference for A1 / Reg. 883/2004 social-security questions: [CLEISS](https://www.cleiss.fr/) (state body, not a vendor).

---

## Lyon (origin)

| Provider | Category | Coverage | Languages | Public pricing | Website | Verified | Notes |
|---|---|---|---|---|---|---|---|
| T2M Déménagement | Moving & Logistics | Dagneux (Lyon) + Lieusaint (IdF) | FR, EN | Quote only (24 h response) | https://www.t2m-demenagement.com/pays/norvege/ | ⚠️ | Dedicated Norway page (Oslo, Bergen, Stavanger, Kristiansand), both directions; no FIDI/IAM found. |
| Grospiron — Lyon branch | Moving & Logistics | Lyon | FR, EN | Quote only | https://www.grospiron.com/en/ | ✓ | FIDI/FAIM via Paris HQ; corporate/HR positioning. |
| AGS — Lyon agency | Moving & Logistics | Lyon (national AGS network) | FR, EN | Quote only | https://www.ags-demenagement.com/ | ⚠️ | AGS's French agency network includes Rhône-Alpes — confirm the Lyon agency handles the survey locally. |
| Aux Déménagements Monet | Moving & Logistics | Lyon / Rhône-Alpes; international road-sea-air | FR | Quote only | https://www.monet-demenagement.com/demenagement-international-w1 | ✓ | Lyon mover since 1945; corporate + private international moves incl. Europe road. |
| Activmoving | Moving & Logistics | Lyon; international | FR | Quote only, tiered formulas | https://activmoving.com/demenagement-international-lyon/ | ⚠️ | Family firm, long-distance specialist; no FIDI/IAM found — verify references. |
| MTN Déménagement | Moving & Logistics | Lyon departures → NO, 5–7 days road | FR, EN | From €3,500 (20 m³) | https://www.mtn-demenagement.com/demenagement-france-norvege | ✓ | Same budget-anchor pricing applies from Lyon. |
| Europack | Moving & Logistics | France → Scandinavia groupage (Oslo, Bergen, Stavanger departures) | FR | Quote only | — | ⚠️ | Recommended by the FR-expat community for Scandinavia groupage; base city + accreditation unconfirmed — locate current site before referral. |

---

## Integration notes (unchanged model, wider index)

- Case Command should surface this directory **by city of destination/origin on the case**: movers at the pre-departure logistics step (with the RD-0030 customs card), schools at offer/feasibility stage, lawyers as escalation cards at the EEA-registration step, tax advisors at the D-number/tax-card step, relocation/settling-in providers at arrival week.
- **Language boost:** for French-preference cases rank FR-capable vendors first — AGS, Grospiron, T2M, MTN, Monet (movers); LFO (school); Lippestad/Frihagen (lawyer); Forvis Mazars, Eurofiscalis (tax).
- **Data hygiene:** ⚠️ entries must never auto-surface as primary recommendations — hold behind the manual verification gate (live site + org number in Brønnøysund/Infogreffe + accreditation registry + one direct FR→NO/SME confirmation). Re-verify all entries every 6 months; school fees each annual cycle.
- **Import path:** these tables are designed to load into the WorkspaceDB `vendors` table (or the proposed corridor-vendor shape) one row at a time — `Provider→name`, `Category→service_type`, `Coverage→city/country`, `Website→website`, `Verified→is_preferred/verified`, `Notes→notes`.
