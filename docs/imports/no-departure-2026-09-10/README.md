# D-P1 - Norway departure compliance facts (`no-departure-2026-09-10`)

**Package type:** facts (NDJSON)
**Corridor:** NO -> FR | **Nationality:** Norwegian (EEA) | **Phase:** departure
**Persona:** Denis - Norwegian national, SLB employee, Oslo -> Paris repatriation
**fact_key prefix:** `no_dep_`
**Records:** 16 facts

## What this is
Non-obvious Norway-exit compliance requirements an HR generalist would not know to look for when moving a Norwegian EEA national out of Norway to France. Every fact is a **representative candidate** awaiting lawyer verification - it is NOT verified guidance.

## Status flags (per hard constraints)
- `review_status`: `pending` (all records)
- `verification_status`: `representative` (all records)
- No DB writes, no webhook calls - files only.

## Schema (per record)
`fact_key`, `title`, `description`, `non_obvious_flag`, `needs_lawyer_review`, `source_url`, `evidence_quote` (on deep-linked facts), `review_status`, `verification_status`, `corridor` (`NO-FR`), `employee_type` (`EEA_national`).

## Coverage
Tax residence detachment (3-year rule), Folkeregister deregistration, A1 posted-worker certificate, French SIPSI posting declaration, social-security totalization, folketrygden membership + voluntary membership, OTP/AFP pension, exit tax on shares, bank/BankID, trailing skattemelding, Helfo/S1/EHIC, car export across the non-EU customs frontier, removal goods ToR relief, driving licence, barnetrygd/CAF coordination, trailing tax on retained Norwegian property.

## Notes on accuracy
- The generic checklist item "Arbeidstilsynet notification" is an **inbound-to-Norway** posting obligation; for an outbound posting to France the receiving-country obligation is the employer's **SIPSI** declaration. Captured as `no_dep_sipsi_posted_declaration`.
- Norway is EEA but **not** in the EU customs union - this drives the car-export and removal-goods customs facts, which are genuine NO-specific quirks.
- Source URLs are authoritative pages (Skatteetaten, NAV, Helsenorge, Douane, Service-Public, Altinn); exact scope must still be confirmed at lawyer review.
- **Evidence citations (2026-09-11 re-source):** four facts previously pointed at site front doors / language roots that evidenced nothing. Each was re-sourced to a **deep link** to the specific page stating the rule, with a verbatim `evidence_quote` from that page: `no_dep_sipsi_posted_declaration` (service-public R42380), `no_dep_otp_pension` (Altinn OTP), `no_dep_helfo_ehic` (Helsenorge EHIC), `no_dep_car_export_customs` (Douane vehicle-import fiche). fact_keys unchanged.
