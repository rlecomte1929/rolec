# D-P10 - France->Norway return compliance facts (`fr-no-return-2026-09-10`)

**Package type:** facts (NDJSON)
**Corridor:** FR -> NO | **Phase:** return (Denis returning to Norway post-assignment)
**Persona:** Denis - Norwegian national (EEA), Paris -> Oslo repatriation
**fact_key prefix:** `fr_no_ret_`
**Records:** 12 facts

## What this is
Non-obvious compliance requirements for the **return leg** - closing out France and re-establishing Norway. Every fact is a **representative candidate** awaiting lawyer verification, not verified guidance.

## Status flags (per hard constraints)
- `review_status`: `pending` (all records)
- `verification_status`: `representative` (all records)
- `phase`: `return` (all records)
- No DB writes, no webhook calls - files only.

## Schema (per record)
`fact_key`, `title`, `description`, `non_obvious_flag`, `needs_lawyer_review`, `source_url`, `evidence_quote` (on deep-linked facts), `review_status`, `verification_status`, `corridor` (`FR-NO`), `phase` (`return`), `employee_type` (`EEA_national`).

## Coverage
Folkeregister re-registration, Norwegian tax-residence re-establishment, NAV re-affiliation, French declaration de depart to DGFiP, CPAM/Carte Vitale deregistration + S1/A1 closure, pension portability (frozen CNAV/Agirc-Arrco, reactivated OTP/folketrygd), French non-resident bank account, vehicle re-import (engangsavgift + VAT), removal-goods customs relief, Helfo/fastlege re-enrolment, children's school/barnehage + barnetrygd, trailing French property tax.

## Notes on accuracy
- Both countries' residence-break timing must be reconciled to avoid a dual-residence tax gap - flagged for lawyer review.
- Norway's non-EU customs status drives the vehicle re-import and removal-goods facts on the return leg too.
- Source URLs are authoritative pages (Skatteetaten, NAV, Impots.gouv.fr, Ameli, Agirc-Arrco, Toll.no, Helsenorge); exact scope to be confirmed at lawyer review.
- **Evidence citations (2026-09-11 re-source):** three facts previously pointed at site front doors / language roots that evidenced nothing. Each was re-sourced to a **deep link** to the specific page stating the rule, with a verbatim `evidence_quote` from that page: `fr_no_ret_cpam_carte_vitale` (Ameli expatriation), `fr_no_ret_pension_portability` (Agirc-Arrco travailler-à-l'étranger), `fr_no_ret_helfo_fastlege` (Helsenorge right-to-a-doctor). fact_keys unchanged.
