# Finland (FI) — non-obvious third-country-national relocation facts

**Corridor:** any → FI (hub: Helsinki) · **Perspective:** non-EEA professional relocated by employer
**Date:** 2026-08-31 · **Facts:** 14 (all browser-grounded, verbatim official quotes confirmed)
**Load status:** candidates only — `review_status='pending'`; do NOT serve as approved.

## Scope discipline
Finland is EEA. Every fact here is **third-country-national specific** — residence permits
(TTOL / specialist / EU Blue Card), the D visa, employer certification, the foreign
"key employee" flat source tax (requires no Finnish tax residence in the prior 5 years),
Kela coverage being gated on holding a residence permit, non-EU/EEA driving-licence exchange,
and the family-tie income requirement. No EU free-movement facts were written. The universal
"183-day / 6-month tax residence" rule was deliberately **excluded** as a standalone fact
because it applies equally to EU citizens; it survives only inside the key-employee fact
("...even if you reside in Finland for over 6 months"), which is third-country specific.

## Sources (official government / statutory only) — all opened in-browser, quotes verbatim
| Authority | Page | URL |
|---|---|---|
| Finnish Immigration Service (Migri) | Residence permit for an employed person (TTOL) | https://migri.fi/en/residence-permit-for-an-employed-person |
| Migri | Specialist residence permit | https://migri.fi/en/specialist |
| Migri | EU Blue Card | https://migri.fi/en/eu-blue-card |
| Migri | D visa | https://migri.fi/en/d-visa |
| Migri | Income requirement for family members | https://migri.fi/en/income-requirement-for-family-members-of-a-person-who-has-been-granted-a-residence-permit-in-finland |
| Tax Administration (Vero) | Key employees from other countries | https://www.vero.fi/en/individuals/tax-cards-and-tax-returns/arriving_in_finland/work_in_finland/specific-instructions-for-different-occupations/key_employees_from_other_countrie/ |
| Kela (social insurance) | Moving to Finland | https://www.kela.fi/moving-to-finland |
| Traficom (transport) | Driving in Finland with a foreign driving licence | https://traficom.fi/en/transport/drivers-and-vehicles/driving-licenses/driving-finland-foreign-driving-licence |

Also read for grounding/context (not cited in a fact line): vero.fi "Arriving in Finland" and
"Work in Finland" (6-month rule, tax card needs a personal ID, 1–3 business-day tax card),
dvv.fi "Municipality of residence" and "Registration of a foreigner" (personal identity code
vs municipality of residence; in-person visit within 1 month).

## Browser-confirmed verbatim?
**Yes — every one of the 14 evidence_quote strings is an exact substring copied from the live
official page opened in the browser** (`quote_verbatim_confirmed: true`). Max quote length 176
chars (< 200). NDJSON validated: 14/14 lines parse, all required fields + applies_to keys present.

## Facts by pillar
IMMIGRATION 8 · TAX 2 · EMPLOYMENT 1 · HEALTHCARE 1 · HOUSING 1 (driving) · FAMILY 1
Fact types: eligibility 7 · process 3 · cost 2 · obligation 1 · deadline 1

## Topics covered
- TTOL: first permit must be filed **from abroad**; permit is **locked to a field of employment**;
  fees 750€ online vs 950€ paper.
- **Labour market test** (employer must show no available FI/EU/EEA labour).
- **Employer certification → D visa** (up to 100 days) for immediate travel after the decision.
- **Specialist / EU Blue Card**: salary floor **EUR 3,937/month (2026)**; **2-week fast track**;
  specialists may work **90 days without a permit**; Blue Card **not bound to one employer**.
- **Foreign key-employee flat source tax**: **25% from 2026** (was 32% to 2025); conditions —
  ≥ **EUR 5,800/month** cash salary, special expertise, **no FI tax residence in prior 5 years**,
  apply within **90 days**, max **84 months**.
- **Kela** coverage not automatic — residence permit must be granted first; depends on
  permanent residence or work.
- **Driving**: non-EU/EEA licence valid only **2 years** (Convention state) / **1 year** (other
  recognised state) after moving, then must be exchanged (medical certificate required).
- **Family**: net-income requirement scaled by household size/region (Helsinki 1 adult 1,210€ +
  610€/child); benefits do not count.

## Unverifiable / excluded categories (no fact written)
- **Rate value the task suggested (32% key-employee tax) is outdated** — the official Vero page
  states it dropped to **25% on 1 Jan 2026**. Used the current official figure, not the prompt's.
- **DVV personal identity code / municipality of residence** as a standalone fact — the core
  obligation applies to EU citizens too, so it fails the third-country-only rule. The nuance
  (a municipality of residence, unlike a bare personal ID, needs an intended stay > 1 year) sits
  behind a JS-expanded FAQ on dvv.fi that did not render as static text; left unwritten rather
  than paraphrased.
- **Certified-employer eligibility criteria** — Migri's standalone certified-employer page
  (/en/certified-employer) 404s/redirects to the frontpage; the certification→D-visa link is
  grounded from the TTOL and D-visa pages instead.
- **Standalone 183-day/6-month tax residence** — excluded as not third-country specific (see Scope).
- No fees, salary numbers, dates, or citations were invented; any figure not on the opened page
  was omitted.
