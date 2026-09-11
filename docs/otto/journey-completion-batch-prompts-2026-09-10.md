# Journey-completion batch — paste-able Otto prompts (2026-09-10)

**Why this file exists.** The 34 journey-completion research packages live as cards in the
Notion **AI Work Queue** (`Otto ready` lane, `Claude Cowork`). Otto (Audos) could not ingest
them off the `app.notion.com` board — the board scrape returned no text and none of the 34 ever
appeared on Otto's Jobs board — so the lane sat `Otto ready` with nothing picking it up. This
file removes that dependency: every card's **Execution Prompt is reproduced verbatim below**, so
you can hand the work to Otto directly (paste the whole file, or one persona block at a time)
without waiting on the Notion→Audos bridge.

Each of the four personas is one corridor's full package set (reference-first: Andrea ES→IE is the
gold template; Denis, Adrien, Abraham replicate it). This mirrors
[`journey-completion-brief-2026-09-10.md`](journey-completion-brief-2026-09-10.md) — that brief is
the standing spec (§3 delivery contracts, §4 work packages); this file is just its prompts,
inlined for a copy-paste hand-off.

## How to run this with Otto

1. Paste a persona block (or a single package) into the Audos/Otto chat.
2. Otto researches and delivers **files only** — NDJSON / JSON bundle / CSV **+ a manifest** to
   Google Cloud Storage (per the contract), **candidate-only**. Otto does not touch the repo.
3. Claude Code (a repo-attached session) then runs the gate → loads as candidate → wires the
   serving surface → moves the card to review. Neither side self-approves; a human reviewer/counsel
   promotes candidates to live.

## The standing contract every prompt below assumes (condensed from the brief §3)

- **Three delivery shapes.** **FACTS** → NDJSON + `manifest.json` + `README.md` under
  `docs/imports/<batch-id>/`; gate `python scripts/check_otto_batches.py <batch-id>`; load
  `scripts/import_otto_facts.py`. **RESOURCES** → JSON `ImportBundle` + `README.md`; load
  `scripts/import_resources.py --bundle <path> --mode draft_only` (forces `status=draft`,
  invisible until published). **VENDORS** → 9-column `providers.csv` + `rejects.csv` +
  `manifest.json` + `README.md`; load `scripts/import_supplier_candidates.py <csv>` (lands at
  `platform_vetting_status='pending'`).
- **Nationality + status scoping is make-or-break.** Read `applies_to.nationality` from the fact,
  never infer it from the corridor; a universal obligation is delivered as **two** nationality-scoped
  records, never one with `null`.
- **Official publishers only.** The evidence-URL **domain** decides trust; blogs / law-firms /
  vendor sites are rejected. A vendor's own website is tier-3 → cite the official register/accreditor
  that *lists* the firm.
- **Candidate-only, always.** Facts `review_status='pending'` / `verification_status='representative'`;
  resources `status='draft'`; vendors `platform_vetting_status='pending'`. Never
  `approved` / `verified` / `live` / `published`.
- **Honesty.** No fabricated number, fee, deadline, or citation — absent stays absent. Every
  `fact_text` is backed by a verbatim `evidence_quote` (≥25 chars). `needs_lawyer_review:true` for
  any legal/tax *determination* (treaty tie-breaker, residence-status conclusion), not for a
  published procedural rule. `fact_type` is never `step` — Claude Code owns pathway step graphs.

Card → this file: the Notion `AIQ-nnnn` is noted per package for traceability. The board remains the
system of record; this file is the executable copy.

---

# 1 · Andrea — ES→IE (Madrid→Dublin), Venezuelan third-country (CSEP) — GOLD TEMPLATE

## A-P1 · ES departure requirement facts → `es-departure-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Spain-departure requirement facts for the ES→IE corridor (persona: Andrea, Venezuelan third-country, Madrid→Dublin). RECONCILE-FIRST: a HELD batch es-facts-2026-08-31 (16 facts) already exists and Claude Code will reconcile/load it; your job is to RE-DELIVER only facts that fail the gate, and ADD facts to reach the topics below if missing. Deliver candidate-only NDJSON + manifest + README under docs/imports/es-departure-2026-09-10/.
>
> TOPICS (Spain exit side): baja del padrón (municipal de-registration); Seguridad Social baja / posted-worker A1 if Andrea stays on an ES contract; AEAT tax-exit / non-resident transition (modelo 030, Form 247/210 as applicable).
>
> RECORD (one JSON object per NDJSON line): destination_country='ES' (the country where the obligation applies); entity_topic_key (stable snake_case, groups facts into one requirement); fact_key (globally unique, prefix 'es_ie_dep_', STABLE across re-deliveries); fact_text (the claim in the mover's terms); source_url (OFFICIAL host only); evidence_quote (verbatim sentence(s) from source_url, >=25 chars); fact_type = one of eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence = high|medium|low; applies_to = {nationality:'non-EEA' (NEVER null), status:'professional', pillar: one of RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE, non_obvious:bool, non_obvious_note (when non_obvious), needs_lawyer_review:bool, quote_verbatim_confirmed:false, corridor:'ES->IE'}.
>
> MANIFEST (manifest.json): batch_id='es-departure-2026-09-10' (== folder name), corridor='ES-IE', origin_country_code='ES', destination_country_code='ES', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact (the .ndjson filename), sha256 (of the ndjson bytes), review_status_all='pending', verification_status_all='representative', scope (one paragraph: what this covers, what it excludes).
>
> SCOPING (make-or-break): read applies_to.nationality from the fact, never infer from the corridor; a truly universal obligation is delivered as TWO records (one EEA, one non-EEA). This is an employment relocation → status 'professional'.
> SOURCES (official only; publisher DOMAIN decides trust; blogs/law-firms/vendors are REJECTED): agenciatributaria.es, seg-social.es, *.gob.es, the Madrid ayuntamiento (madrid.es), boe.es.
> HONESTY: no fabricated number/fee/deadline/citation — absent stays absent; every fact_text backed by an evidence_quote; needs_lawyer_review:true for any legal/tax DETERMINATION (treaty tie-breaker, residence-status conclusion), not a published procedural rule. Everything candidate-only — never approved/verified/live.
>
> Deliver FILES only; Claude Code owns all code, loads, and reviews. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.A (A-P1).

- **Validation:** Gate `python scripts/check_otto_batches.py es-departure-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty (nationality+status present on every record); 100% promote (0 Unmapped) on the Claude Code load dry-run; >=6 official-sourced facts across the three topics.
- **Expected output:** `docs/imports/es-departure-2026-09-10/` = `es-departure-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py es-departure-2026-09-10`

## A-P2 · Dublin pre-departure health resources → `ie-predeparture-health-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Pre-departure health resources for Dublin (persona: Andrea + accompanying family). Deliver a candidate-only JSON ImportBundle + README under docs/imports/ie-predeparture-health-2026-09-10/.
>
> GOAL: a pre-departure health checklist/guide covering: recommended/required vaccinations for entry to Ireland; carrying medical records and repeat prescriptions; proof-of-insurance / EHIC-equivalent for the gap before local cover; transferring to an Irish GP; bringing controlled-substance medicines legally.
>
> BUNDLE (JSON, keys): {categories, tags, sources, resources, events}. Each resource object: {country_code:'IE', city_name:'Dublin', category_key:'healthcare', title, resource_type: one of guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL: hse.ie / citizensinformation.ie / gov.ie), source_name, tags:[...], status:'draft'}.
>
> SOURCES (official only): hse.ie, citizensinformation.ie, gov.ie. No blogs/vendors.
> HONESTY: no invented requirement; every claim carries its official source_url; status 'draft' only (Claude Code loads with --mode draft_only → country_resources, invisible until a human publishes).
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.A (A-P2).

- **Validation:** Bundle validates against the resource-bundle validator; every resource_type and category_key is in-vocab; all resources status='draft'; each carries an official source_url; the dry-run/validate-only load reports no errors.
- **Expected output:** `docs/imports/ie-predeparture-health-2026-09-10/` = `ie-predeparture-health-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/ie-predeparture-health-2026-09-10/ie-predeparture-health-2026-09-10.bundle.json --validate-only`

## A-P3 · Dublin temp/serviced housing vendors → `es-ie-dublin-temp-housing-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Temporary / serviced-housing vendor directory for Dublin (bridging accommodation before a permanent lease). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/es-ie-dublin-temp-housing-2026-09-10/.
>
> GOAL: 4-6 serviced-apartment / temporary-housing providers serving Dublin for relocating employees.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. Set corridor='ES-IE' (or 'XX-IE' for a Dublin-city provider), service_category='temp_accommodation'.
> PROVENANCE (decisive): source_url must be an OFFICIAL register / accreditor / trade body page that LISTS the firm — the firm's own website is tier-3 and auto-rejected. For Ireland use e.g. Fáilte Ireland registration, the relevant serviced-apartment association, or a CRO company listing; cite the register domain in source_url and source_name.
>
> MANIFEST: batch_id='es-ie-dublin-temp-housing-2026-09-10', corridor, categories:[{service_category:'temp_accommodation', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY: no invented firm/accreditation; a firm you cannot source to an official register goes in rejects.csv with the reason. Candidate-only — providers land at platform_vetting_status='pending' (admin vetting queue); nothing is served until a human approves.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.A (A-P3).

- **Validation:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-temp-housing-2026-09-10/providers.csv` dry-run is clean; >=3 firms pass the provenance gate (tier-1/2 source); every accepted row has an official register source_url; rejects.csv explains each drop.
- **Expected output:** `docs/imports/es-ie-dublin-temp-housing-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-temp-housing-2026-09-10/providers.csv`

## A-P4 · Dublin GP/medical vendors → `es-ie-dublin-medical-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — GP / medical-provider directory for Dublin (clinics accepting new arrivals). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/es-ie-dublin-medical-2026-09-10/.
>
> GOAL: 4-6 GP practices / family clinics in Dublin that register new residents (English-speaking; note any that take private/expat patients without a PPSN).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-IE' (Dublin-city), service_category='medical'.
> PROVENANCE: source_url must be an OFFICIAL register listing the practitioner/practice — the Irish Medical Council register (medicalcouncil.ie) or the ICGP, or the HSE find-a-GP listing. A clinic's own site is insufficient (tier-3, rejected). Put the register URL in source_url + accreditation_body='Medical Council'/accreditation_number where available.
>
> MANIFEST: batch_id='es-ie-dublin-medical-2026-09-10', corridor, categories:[{service_category:'medical', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as A-P3. GDPR — use a company/clinic inbox, never a personal email.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.A (A-P4).

- **Validation:** Import dry-run clean; >=3 practices pass the provenance gate against an official register (Medical Council / HSE); every accepted row cites the register; rejects.csv explains drops.
- **Expected output:** `docs/imports/es-ie-dublin-medical-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-medical-2026-09-10/providers.csv`

## A-P5 · IE driving-licence exchange guide → `ie-driving-licence-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Driving-licence exchange guide for Ireland, scoped to Andrea's licences (Spanish and Venezuelan). NOTE: delivered as a RESOURCE bundle (not requirement facts) because it maps to the transport/settle-in guidance surface, not a gated immigration pillar. Deliver a candidate-only JSON ImportBundle + README under docs/imports/ie-driving-licence-2026-09-10/.
>
> GOAL: a clear guide answering — can an ES licence be exchanged for an Irish one (EU/EEA reciprocity: yes, direct exchange) vs a VE (Venezuelan) licence (is Venezuela on Ireland's recognised-states exchange list? if not, the driver must sit the Irish theory + driving test); the exchange deadline from taking up residence; where to apply (NDLS); documents required.
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'IE', city_name:'Dublin' (or null for national), category_key:'transport', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL), source_name, tags, status:'draft'}. Deliver at least: one resource for the ES→IE (EU exchange) path and one for the VE→IE (recognised-state check / test) path, since the answer differs by licence-issuing country.
>
> SOURCES (official only): ndls.ie, rsa.ie, citizensinformation.ie, gov.ie.
> HONESTY: state the recognised-states position as published; if Venezuela's status is not clearly published, say so in the body and do NOT invent it. status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.A (A-P5, resource-first refinement noted).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; status='draft'; separate resources for the ES (EU exchange) and VE (recognised-state check) paths; every claim cites ndls.ie/rsa.ie/citizensinformation.ie; validate-only load clean.
- **Expected output:** `docs/imports/ie-driving-licence-2026-09-10/` = `ie-driving-licence-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/ie-driving-licence-2026-09-10/ie-driving-licence-2026-09-10.bundle.json --validate-only`

## A-P6 · Dublin language-school vendors → `es-ie-dublin-language-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Language-school vendor directory for Dublin (English tuition for Andrea's accompanying Venezuelan spouse; some employees/partners need English support). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/es-ie-dublin-language-2026-09-10/.
>
> GOAL: 4-6 accredited English-language schools in Dublin offering adult ESOL / general English.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-IE', service_category='language'.
> PROVENANCE: source_url must be the OFFICIAL accreditation register — for Ireland, the ACELS / QQI International Education Mark listing of accredited English-language providers. Put ACELS/QQI in accreditation_body and the listing URL in source_url. A school's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='es-ie-dublin-language-2026-09-10', corridor, categories:[{service_category:'language', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as A-P3.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.A (A-P6). Note (from the brief): language is family-scoped where the mover already speaks the destination language.

- **Validation:** Import dry-run clean; >=3 schools pass the provenance gate against ACELS/QQI; every accepted row cites the accreditation register; rejects.csv explains drops.
- **Expected output:** `docs/imports/es-ie-dublin-language-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-language-2026-09-10/providers.csv`

## A-P7 · Dublin dual-career / spouse-employment vendors → `es-ie-dublin-dual-career-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Dual-career / spouse-employment support vendors for Dublin (career coaching, CV/interview support and job-search help for Andrea's accompanying partner). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/es-ie-dublin-dual-career-2026-09-10/.
>
> GOAL: 4-6 providers offering spouse/partner career transition services in the Dublin market (career coaches, outplacement/relocation career firms, recognised professional coaching bodies' members).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-IE', service_category='spouse'.
> PROVENANCE: prefer providers listed on an OFFICIAL professional register/body (e.g. EMCC/ICF-accredited coach directories, or a CRO company listing) — cite that register in source_url. A provider's own site alone is tier-3 and rejected; put such firms in rejects.csv with the reason.
>
> MANIFEST: batch_id='es-ie-dublin-dual-career-2026-09-10', corridor, categories:[{service_category:'spouse', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as A-P3. (Spouse IMMIGRATION/work-rights facts already exist for this corridor — this card is career-services vendors only.)
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.A (A-P7).

- **Validation:** Import dry-run clean; >=3 providers pass the provenance gate against an official register/body; every accepted row cites its source; rejects.csv explains drops.
- **Expected output:** `docs/imports/es-ie-dublin-dual-career-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-dual-career-2026-09-10/providers.csv`

## A-P9 · Dublin tax-advisor vendors → `es-ie-dublin-tax-advisors-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Tax-advisor vendor directory for Dublin (personal/expat income-tax advisers for Andrea's IE tax registration and ES/IE cross-border position). Top-up of the existing thin tax coverage. Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/es-ie-dublin-tax-advisors-2026-09-10/.
>
> GOAL: 4-6 tax advisers / firms in Dublin handling inbound-expat personal tax (PAYE registration, split-year relief, ES–IE double-taxation).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='ES-IE', service_category='tax_finance'.
> PROVENANCE: source_url must be an OFFICIAL professional register — the Irish Tax Institute (taxinstitute.ie) member directory or Chartered Accountants Ireland; put the body in accreditation_body and the register listing in source_url. Firm's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='es-ie-dublin-tax-advisors-2026-09-10', corridor, categories:[{service_category:'tax_finance', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as A-P3.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.A (A-P9).

- **Validation:** Import dry-run clean; >=3 advisers pass the provenance gate against the Irish Tax Institute / Chartered Accountants Ireland; every accepted row cites the register; rejects.csv explains drops.
- **Expected output:** `docs/imports/es-ie-dublin-tax-advisors-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/es-ie-dublin-tax-advisors-2026-09-10/providers.csv`

## A-P10 · IE→ES/VE return requirement facts → `ie-es-return-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Return/repatriation requirement facts for the reverse corridor IE→ES/VE (persona: Andrea, Venezuelan third-country, ending a Dublin assignment). Deliver candidate-only NDJSON + manifest + README under docs/imports/ie-es-return-2026-09-10/.
>
> TOPICS: HOST-EXIT (Ireland) — close IRP/immigration permission, Revenue tax-residence exit + final return, PPSN retention; HOME RE-ENTRY (Spain) — empadronamiento (re-register address), Seguridad Social re-affiliation, AEAT tax-residence re-establishment; plus the Venezuela consular route if returning to VE rather than ES. This is the back half of the round-trip; keep it a SKELETON (the 6-10 highest-value return facts), not full outbound parity.
>
> RECORD (one JSON per NDJSON line): destination_country = the ISO-2 where each obligation applies ('IE' for host-exit facts, 'ES' for home-re-entry facts); entity_topic_key (stable snake_case); fact_key (globally unique, prefix 'ie_es_ret_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'non-EEA' (NEVER null), status:'professional', pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE, non_obvious, non_obvious_note, needs_lawyer_review, quote_verbatim_confirmed:false, corridor:'IE->ES'}.
>
> MANIFEST: batch_id='ie-es-return-2026-09-10', corridor='IE-ES', origin_country_code='IE', destination_country_code='ES', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only): IE — revenue.ie, irishimmigration.ie, citizensinformation.ie; ES — agenciatributaria.es, seg-social.es, the ayuntamiento (empadronamiento); VE — the relevant consulate/cancillería. needs_lawyer_review:true on any tax tie-breaker / residence determination.
> HONESTY + SCOPING: as A-P1 — nationality never null, universal obligation as two records, no fabrication, candidate-only.
>
> FILES only; Claude Code serves these in the roadmap's Return & repatriation phase (already built). Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.A (A-P10).

- **Validation:** Gate `python scripts/check_otto_batches.py ie-es-return-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote on the dry-run; return fact_keys are distinct from the outbound ES→IE keys; each fact cites an official source.
- **Expected output:** `docs/imports/ie-es-return-2026-09-10/` = `ie-es-return-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py ie-es-return-2026-09-10`

---

# 2 · Denis — NO→FR (Norway→Paris), French / EEA free-mover

## D-P1 · Norway-departure requirement facts → `no-departure-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Norway-departure requirement facts for the NO→FR corridor (persona: Denis, French EEA free-mover, Norway→Paris). COMPLETE-AND-VERIFY: the corridor already has 4 origin facts in facts.yaml + 3 held NO candidates in no-fr-general-curated + no-fr-transition-requirements (only 3/15 quotes verified). Your job: VERIFY the unverified transition quotes against their sources and DELIVER the missing Norway-exit facts. Claude Code will supply the existing 4 fact_keys so there is no duplication. Deliver candidate-only NDJSON + manifest + README under docs/imports/no-departure-2026-09-10/.
>
> TOPICS (Norway exit side): folkeregister move-abroad notification (melding om utflytting); exit from folketrygden + HELFO/EHIC; skattekort / exit-tax (utflyttingsskatt) and NO source-tax on leaving; the A1 / certificate of coverage is issued by URSSAF (France), NOT NAV, for a posted worker; and the non-obvious trap: preserve BankID before de-registration disables it.
>
> RECORD (one JSON per NDJSON line): destination_country='NO' (the country where the obligation applies); entity_topic_key (stable snake_case); fact_key (globally unique, prefix 'no_fr_dep_', STABLE, and NOT one of the 4 existing keys CC will provide); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'EEA' (NEVER null), status:'professional', pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE, non_obvious, non_obvious_note, needs_lawyer_review, quote_verbatim_confirmed:false, corridor:'NO->FR'}.
>
> MANIFEST: batch_id='no-departure-2026-09-10', corridor='NO-FR', origin_country_code='NO', destination_country_code='NO', nationality_class='EU_EEA', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only; blogs/law-firms/vendors REJECTED): skatteetaten.no, nav.no, folkeregisteret.no, altinn.no, helsenorge.no; urssaf.fr (for the A1-issued-by-France point).
> SCOPING + HONESTY: nationality 'EEA' read from the fact, never null; universal obligation as two records; no fabrication; every fact_text backed by an evidence_quote; needs_lawyer_review:true for any tax determination. Candidate-only.
>
> FILES only; Claude Code owns loads/reviews. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Denis P1).

- **Validation:** Gate `python scripts/check_otto_batches.py no-departure-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote on the dry-run; no duplication of the 4 existing NO origin fact_keys; the previously-unverified transition quotes are now quote-confirmed against their sources.
- **Expected output:** `docs/imports/no-departure-2026-09-10/` = `no-departure-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py no-departure-2026-09-10`

## D-P2 · Paris/France pre-departure health resources → `fr-predeparture-health-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Pre-departure health resources for the move to Paris/France (persona: Denis + accompanying family, EEA). Deliver a candidate-only JSON ImportBundle + README under docs/imports/fr-predeparture-health-2026-09-10/.
>
> GOAL: a pre-departure health guide/checklist for an EEA mover to France covering: EHIC / S1 to cover the gap before local affiliation; registering with the French health system (PUMa / Assurance Maladie) and choosing a médecin traitant; carrying medical records and repeat prescriptions; any recommended vaccinations. (For an EEA arrival the story is CPAM/PUMa affiliation + carte vitale, not entry vaccination gates — reflect that.)
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'FR', city_name:'Paris', category_key:'healthcare', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL: ameli.fr / service-public.fr / gouvernement.fr), source_name, tags, status:'draft'}.
>
> SOURCES (official only): ameli.fr, service-public.fr, gouvernement.fr. No blogs/vendors.
> HONESTY: every claim carries its official source_url; status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Denis P2).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; all resources status='draft'; each carries an official source_url; validate-only load clean.
- **Expected output:** `docs/imports/fr-predeparture-health-2026-09-10/` = `fr-predeparture-health-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/fr-predeparture-health-2026-09-10/fr-predeparture-health-2026-09-10.bundle.json --validate-only`

## D-P3 · Paris temp/serviced housing vendors → `no-fr-paris-temp-housing-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Temporary / serviced-housing (résidences / apparthotels) vendor directory for Paris. Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/no-fr-paris-temp-housing-2026-09-10/.
>
> GOAL: 4-6 serviced-apartment / résidence providers serving Paris for relocating employees (bridging accommodation before a permanent lease).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. Set corridor='NO-FR' (or 'XX-FR' for a Paris-city provider), service_category='temp_accommodation'.
> PROVENANCE (decisive): source_url must be an OFFICIAL register / accreditor page that LISTS the firm — e.g. a SIRENE/INSEE (annuaire-entreprises.data.gouv.fr) company record, an Atout France / tourism registration, or the résidences-de-tourisme trade body. The firm's own website is tier-3 and auto-rejected; cite the register domain in source_url + source_name.
>
> MANIFEST: batch_id='no-fr-paris-temp-housing-2026-09-10', corridor, categories:[{service_category:'temp_accommodation', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY: a firm not sourceable to an official register goes in rejects.csv with the reason. Candidate-only — land at platform_vetting_status='pending'; nothing served until a human approves.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Denis P3).

- **Validation:** `python scripts/import_supplier_candidates.py docs/imports/no-fr-paris-temp-housing-2026-09-10/providers.csv` dry-run clean; >=3 firms pass the provenance gate (tier-1/2 register); every accepted row has an official source_url; rejects.csv explains each drop.
- **Expected output:** `docs/imports/no-fr-paris-temp-housing-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/no-fr-paris-temp-housing-2026-09-10/providers.csv`

## D-P4 · Paris GP/medical vendors → `no-fr-paris-medical-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — GP / médecin-traitant directory for Paris (practices registering new arrivals; English-speaking noted). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/no-fr-paris-medical-2026-09-10/.
>
> GOAL: 4-6 médecins généralistes / practices in Paris accepting new patients as médecin traitant (flag English-speaking).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-FR', service_category='medical'.
> PROVENANCE: source_url must be an OFFICIAL register listing the practitioner — the Conseil National de l'Ordre des Médecins directory (conseil-national.medecin.fr) or ameli.fr's annuaire santé. Put 'Ordre des Médecins' in accreditation_body + the RPPS/register listing in source_url. A clinic's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='no-fr-paris-medical-2026-09-10', corridor, categories:[{service_category:'medical', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as D-P3. GDPR — use a practice inbox, never a personal email.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Denis P4).

- **Validation:** Import dry-run clean; >=3 practices pass the provenance gate against the Ordre des Médecins / ameli annuaire; every accepted row cites the register; rejects.csv explains drops.
- **Expected output:** `docs/imports/no-fr-paris-medical-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/no-fr-paris-medical-2026-09-10/providers.csv`

## D-P5 · FR driving-licence exchange guide → `fr-driving-licence-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Driving-licence guide for France, scoped to Denis (French national arriving from Norway). Delivered as a RESOURCE bundle (transport guidance, not a gated immigration pillar). Deliver a candidate-only JSON ImportBundle + README under docs/imports/fr-driving-licence-2026-09-10/.
>
> GOAL: a clear guide answering — a French licence is valid as-is; an EEA (Norwegian) licence is valid for driving in France without exchange (exchange required only on expiry, loss, or an offence), and how/where to exchange via ANTS when needed; the timeframe and documents. Cover both cases since the accompanying spouse may hold a non-FR licence.
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'FR', city_name:'Paris' or null, category_key:'transport', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL), source_name, tags, status:'draft'}. Deliver at least one resource for the EEA-licence-in-France position and one for the exchange procedure (ANTS).
>
> SOURCES (official only): service-public.fr, ants.gouv.fr, interieur.gouv.fr.
> HONESTY: state the EEA-licence validity as published; do not invent thresholds. status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Denis P5).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; status='draft'; separate resources for EEA-licence validity and the ANTS exchange procedure; every claim cites service-public.fr/ants.gouv.fr; validate-only load clean.
- **Expected output:** `docs/imports/fr-driving-licence-2026-09-10/` = `fr-driving-licence-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/fr-driving-licence-2026-09-10/fr-driving-licence-2026-09-10.bundle.json --validate-only`

## D-P6 · Paris French-language school vendors → `no-fr-paris-language-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — French-language school vendor directory for Paris (FLE tuition for Denis's accompanying non-French-speaking spouse/family; Denis himself is a French speaker — this is family-scoped). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/no-fr-paris-language-2026-09-10/.
>
> GOAL: 4-6 accredited Français Langue Étrangère (FLE) schools in Paris offering adult general French.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-FR', service_category='language'.
> PROVENANCE: source_url must be the OFFICIAL accreditation register — the Label Qualité français langue étrangère directory (qualitefle.fr) and/or Qualiopi certification. Put the label/body in accreditation_body and the listing URL in source_url. A school's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='no-fr-paris-language-2026-09-10', corridor, categories:[{service_category:'language', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as D-P3.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Denis P6). Note (brief): language is family-scoped where the mover already speaks the destination language.

- **Validation:** Import dry-run clean; >=3 schools pass the provenance gate against the Label Qualité FLE / Qualiopi; every accepted row cites the accreditation register; rejects.csv explains drops.
- **Expected output:** `docs/imports/no-fr-paris-language-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/no-fr-paris-language-2026-09-10/providers.csv`

## D-P7 · Paris dual-career / spouse-employment vendors → `no-fr-paris-dual-career-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Dual-career / spouse-employment support vendors for Paris (career coaching, CV/interview support, job-search help for Denis's accompanying partner). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/no-fr-paris-dual-career-2026-09-10/.
>
> GOAL: 4-6 providers offering spouse/partner career-transition services in the Paris market (career coaches / bilan de compétences providers / relocation career firms).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-FR', service_category='spouse'.
> PROVENANCE: prefer providers listed on an OFFICIAL register/body — a Qualiopi-certified bilan-de-compétences directory, an EMCC France / ICF-accredited coach directory, or a SIRENE company record. Cite the register in source_url. A provider's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='no-fr-paris-dual-career-2026-09-10', corridor, categories:[{service_category:'spouse', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as D-P3. (Spouse work-rights are automatic for an EEA family — this card is career-services vendors only.)
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Denis P7).

- **Validation:** Import dry-run clean; >=3 providers pass the provenance gate against an official register/body (Qualiopi / EMCC / ICF / SIRENE); every accepted row cites its source; rejects.csv explains drops.
- **Expected output:** `docs/imports/no-fr-paris-dual-career-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/no-fr-paris-dual-career-2026-09-10/providers.csv`

## D-P10 · FR→NO return requirement facts → `fr-no-return-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Return/repatriation requirement facts for the reverse corridor FR→NO (persona: Denis, French EEA free-mover, ending a Paris assignment and returning to Norway). Deliver candidate-only NDJSON + manifest + README under docs/imports/fr-no-return-2026-09-10/.
>
> TOPICS: HOST-EXIT (France) — deregister with CPAM/Assurance Maladie, close URSSAF/social affiliation, final impôts / prélèvement à la source and tax-residence exit; HOME RE-ENTRY (Norway) — folkeregister re-registration (melding om innflytting), re-affiliate to folketrygden/HELFO, re-establish NO tax residence and skattekort. Keep it a SKELETON (6-10 highest-value return facts), not full outbound parity.
>
> RECORD (one JSON per NDJSON line): destination_country = the ISO-2 where each obligation applies ('FR' for host-exit, 'NO' for home-re-entry); entity_topic_key; fact_key (globally unique, prefix 'fr_no_ret_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'EEA' (NEVER null), status:'professional', pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE, non_obvious, non_obvious_note, needs_lawyer_review, quote_verbatim_confirmed:false, corridor:'FR->NO'}.
>
> MANIFEST: batch_id='fr-no-return-2026-09-10', corridor='FR-NO', origin_country_code='FR', destination_country_code='NO', nationality_class='EU_EEA', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only): FR — service-public.fr, impots.gouv.fr, ameli.fr, urssaf.fr; NO — skatteetaten.no, nav.no, folkeregisteret.no. needs_lawyer_review:true on any tax tie-breaker.
> SCOPING + HONESTY: as D-P1 — nationality never null, universal obligation as two records, no fabrication, candidate-only.
>
> FILES only; Claude Code serves these in the roadmap's Return & repatriation phase (already built). Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Denis P10).

- **Validation:** Gate `python scripts/check_otto_batches.py fr-no-return-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote on the dry-run; return fact_keys distinct from the outbound NO→FR keys; each fact cites an official source.
- **Expected output:** `docs/imports/fr-no-return-2026-09-10/` = `fr-no-return-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py fr-no-return-2026-09-10`

---

# 3 · Adrien — FR→SG (Paris→Singapore), French / third-country work pass

## AD-P1 · France-departure requirement facts → `fr-departure-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — France-departure requirement facts for the FR→SG corridor (persona: Adrien Hardy, French national, Paris→Singapore on an Employment Pass). This corridor has NO origin-side facts yet — net-new. Deliver candidate-only NDJSON + manifest + README under docs/imports/fr-departure-2026-09-10/.
>
> TOPICS (France exit side, for a departing French resident): déclaration de départ / transfer of tax residence to the SIP des non-résidents; prélèvement à la source exit; CPAM/Assurance Maladie de-registration + PUMa cessation; URSSAF; the A1 / certificate of coverage for a posted worker (note: FR–SG has NO EU-style totalization — flag if a bilateral applies, else needs_lawyer_review); CAF cessation.
>
> RECORD (one JSON per NDJSON line): destination_country='FR' (obligations apply in France); entity_topic_key; fact_key (globally unique, prefix 'fr_sg_dep_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality: scope to the audience the fact governs — a departing FRENCH resident's own-national obligation is 'EEA' (NEVER null); status:'professional'; pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE; non_obvious; non_obvious_note; needs_lawyer_review; quote_verbatim_confirmed:false; corridor:'FR->SG'}.
>
> MANIFEST: batch_id='fr-departure-2026-09-10', corridor='FR-SG', origin_country_code='FR', destination_country_code='FR', nationality_class='EU_EEA', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only; blogs/law-firms/vendors REJECTED): service-public.fr, impots.gouv.fr, urssaf.fr, ameli.fr, caf.fr.
> HONESTY: no fabrication; every fact_text backed by an evidence_quote; needs_lawyer_review:true for any tax/treaty determination (esp. FR–SG totalization). Candidate-only.
>
> FILES only; Claude Code owns loads/reviews and will author the FR_SG pathway from these + the existing SG destination facts. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Adrien P1).

- **Validation:** Gate `python scripts/check_otto_batches.py fr-departure-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote on the dry-run; >=6 official-sourced FR-exit facts; the FR–SG totalization position is either sourced or flagged needs_lawyer_review (never invented).
- **Expected output:** `docs/imports/fr-departure-2026-09-10/` = `fr-departure-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py fr-departure-2026-09-10`

## AD-P2 · Singapore pre-departure health resources → `sg-predeparture-health-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Pre-departure health resources for the move to Singapore (persona: Adrien + accompanying family). Deliver a candidate-only JSON ImportBundle + README under docs/imports/sg-predeparture-health-2026-09-10/.
>
> GOAL: a pre-departure health guide/checklist covering: any vaccination / medical-exam requirements for the Employment Pass and Dependant's Pass (SG requires a medical exam incl. HIV/TB screening for some passes); carrying medical records and repeat prescriptions (SG controls certain medicines — HSA import rules); private health insurance for the cover gap (EP holders are not on a public scheme); transferring care to an SG GP/polyclinic.
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'SG', city_name:'Singapore', category_key:'healthcare', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL: moh.gov.sg / ica.gov.sg / mom.gov.sg / hsa.gov.sg), source_name, tags, status:'draft'}.
>
> SOURCES (official only): moh.gov.sg, ica.gov.sg, mom.gov.sg, hsa.gov.sg. No blogs/vendors.
> HONESTY: every claim carries its official source_url; status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Adrien P2).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; all resources status='draft'; each carries an official source_url; validate-only load clean.
- **Expected output:** `docs/imports/sg-predeparture-health-2026-09-10/` = `sg-predeparture-health-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/sg-predeparture-health-2026-09-10/sg-predeparture-health-2026-09-10.bundle.json --validate-only`

## AD-P3 · Singapore temp/serviced housing vendors → `fr-sg-singapore-temp-housing-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Temporary / serviced-housing vendor directory for Singapore (bridging accommodation before a permanent lease). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/fr-sg-singapore-temp-housing-2026-09-10/.
>
> GOAL: 4-6 serviced-apartment / serviced-residence providers in Singapore for relocating employees.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='FR-SG' (or 'XX-SG'), service_category='temp_accommodation'.
> PROVENANCE (decisive): source_url must be an OFFICIAL register that LISTS the firm — a URA (Urban Redevelopment Authority) serviced-apartment listing, or ACRA/BizFile company record (bizfile.gov.sg), or STB registration. The firm's own site is tier-3 and auto-rejected; cite the register domain.
>
> MANIFEST: batch_id='fr-sg-singapore-temp-housing-2026-09-10', corridor, categories:[{service_category:'temp_accommodation', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: firm not sourceable to a register → rejects.csv with reason; land at platform_vetting_status='pending'.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Adrien P3).

- **Validation:** `python scripts/import_supplier_candidates.py docs/imports/fr-sg-singapore-temp-housing-2026-09-10/providers.csv` dry-run clean; >=3 firms pass the provenance gate (URA/ACRA/STB); every accepted row cites an official source; rejects.csv explains drops.
- **Expected output:** `docs/imports/fr-sg-singapore-temp-housing-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/fr-sg-singapore-temp-housing-2026-09-10/providers.csv`

## AD-P4 · Singapore GP/medical vendors → `fr-sg-singapore-medical-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — GP / medical-clinic directory for Singapore (clinics registering new arrivals; expat-friendly noted). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/fr-sg-singapore-medical-2026-09-10/.
>
> GOAL: 4-6 GP clinics / family practices in Singapore accepting new patients.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-SG', service_category='medical'.
> PROVENANCE: source_url must be an OFFICIAL register — the Singapore Medical Council (SMC) register, or the MOH licensed-clinic directory (moh.gov.sg). Put 'SMC'/'MOH' in accreditation_body + the register listing in source_url. A clinic's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='fr-sg-singapore-medical-2026-09-10', corridor, categories:[{service_category:'medical', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as AD-P3. GDPR — practice inbox, never a personal email.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Adrien P4).

- **Validation:** Import dry-run clean; >=3 clinics pass the provenance gate against SMC/MOH; every accepted row cites the register; rejects.csv explains drops.
- **Expected output:** `docs/imports/fr-sg-singapore-medical-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/fr-sg-singapore-medical-2026-09-10/providers.csv`

## AD-P5 · SG driving-licence conversion guide → `sg-driving-licence-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Driving-licence guide for Singapore, scoped to Adrien (French licence holder). Delivered as a RESOURCE bundle (transport guidance, not a gated pillar). Deliver a candidate-only JSON ImportBundle + README under docs/imports/sg-driving-licence-2026-09-10/.
>
> GOAL: a clear guide answering — can Adrien drive in Singapore on a French/international licence and for how long; whether France is on the list of countries whose licence can be converted without the Basic Theory Test (BTT), or whether the BTT is required; the deadline to convert after becoming a resident; where to apply (Traffic Police / one.motoring).
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'SG', city_name:'Singapore' or null, category_key:'transport', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL), source_name, tags, status:'draft'}.
>
> SOURCES (official only): police.gov.sg (Traffic Police), lta.gov.sg, onemotoring.lta.gov.sg.
> HONESTY: state France's BTT-exemption status as published; if unclear, say so and do not invent it. status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Adrien P5).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; status='draft'; the France BTT-exemption position is sourced (or explicitly marked unclear); every claim cites police.gov.sg/lta.gov.sg; validate-only load clean.
- **Expected output:** `docs/imports/sg-driving-licence-2026-09-10/` = `sg-driving-licence-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/sg-driving-licence-2026-09-10/sg-driving-licence-2026-09-10.bundle.json --validate-only`

## AD-P7 · Singapore dual-career / spouse-employment vendors → `fr-sg-singapore-dual-career-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Dual-career / spouse-employment support vendors for Singapore (career coaching, CV/interview support, job-search help for Adrien's accompanying partner). NOTE: a Dependant's Pass holder needs a Letter of Consent or their own work pass to work in SG — reflect that context, but this card is CAREER-SERVICES VENDORS only (the immigration/work-eligibility facts belong in the facts batches). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/fr-sg-singapore-dual-career-2026-09-10/.
>
> GOAL: 4-6 providers offering spouse/partner career-transition services in Singapore (career coaches / outplacement / relocation career firms).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-SG', service_category='spouse'.
> PROVENANCE: prefer providers listed on an OFFICIAL register/body (an ACRA/BizFile company record, or an ICF-accredited coach directory). Cite the register in source_url. A provider's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='fr-sg-singapore-dual-career-2026-09-10', corridor, categories:[{service_category:'spouse', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as AD-P3.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Adrien P7).

- **Validation:** Import dry-run clean; >=3 providers pass the provenance gate against ACRA/ICF; every accepted row cites its source; rejects.csv explains drops.
- **Expected output:** `docs/imports/fr-sg-singapore-dual-career-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/fr-sg-singapore-dual-career-2026-09-10/providers.csv`

## AD-TAX · Singapore tax (IRAS) requirement facts → `fr-sg-tax-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Singapore tax requirement facts for the FR→SG corridor (persona: Adrien, French, Employment Pass). FILLS THE DOCUMENTED HOLE: the corridor has only 1 tax fact today (the IRAS mega-menu was unscrapeable). Deliver candidate-only NDJSON + manifest + README under docs/imports/fr-sg-tax-2026-09-10/.
>
> TOPICS (SG tax, for an EP-holder foreigner): tax residence (the 183-day rule); employment-income tax rates and the resident vs non-resident distinction; the Notice of Assessment / filing obligation and deadline; no CPF contributions for EP holders; the FR–SG double-taxation treaty position (source it or flag needs_lawyer_review); tax clearance (Form IR21) on leaving.
>
> RECORD (one JSON per NDJSON line): destination_country='SG'; entity_topic_key; fact_key (globally unique, prefix 'fr_sg_tax_', STABLE); fact_text; source_url (OFFICIAL: iras.gov.sg); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'non-EEA' (a French national is a third-country foreigner from Singapore's perspective; follow the existing fr-sg-facts batch precedent; NEVER null); status:'professional'; pillar='EMPLOYMENT' (tax maps to EMPLOYMENT in the loader); non_obvious; non_obvious_note; needs_lawyer_review; quote_verbatim_confirmed:false; corridor:'FR->SG'}.
>
> MANIFEST: batch_id='fr-sg-tax-2026-09-10', corridor='FR-SG', origin_country_code='FR', destination_country_code='SG', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only): iras.gov.sg (and mom.gov.sg for the CPF/EP point).
> HONESTY + candidate-only: no fabricated rate/threshold; every claim sourced to IRAS; treaty determination flagged needs_lawyer_review.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Adrien — the TAX hole).

- **Validation:** Gate `python scripts/check_otto_batches.py fr-sg-tax-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote; >=6 IRAS-sourced tax facts; the FR–SG treaty position sourced or flagged, never invented.
- **Expected output:** `docs/imports/fr-sg-tax-2026-09-10/` = `fr-sg-tax-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py fr-sg-tax-2026-09-10`

## AD-P10 · SG→FR return requirement facts → `sg-fr-return-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Return/repatriation requirement facts for the reverse corridor SG→FR (persona: Adrien, French, ending a Singapore assignment and returning to France). Deliver candidate-only NDJSON + manifest + README under docs/imports/sg-fr-return-2026-09-10/. SKELETON (6-10 highest-value return facts).
>
> TOPICS: HOST-EXIT (Singapore) — IRAS tax clearance (Form IR21) before the last day, cancel the Employment Pass (employer files), close CPF/none, MOM notification; HOME RE-ENTRY (France) — re-establish FR tax residence + PAS, re-affiliate to CPAM/PUMa, re-register with URSSAF/employer.
>
> RECORD (one JSON per NDJSON line): destination_country = the ISO-2 where each obligation applies ('SG' for host-exit, 'FR' for home-re-entry); entity_topic_key; fact_key (globally unique, prefix 'sg_fr_ret_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality: scope per audience — SG-exit obligations governing a work-pass holder = 'non-EEA'; FR-re-entry obligations governing a returning French national = 'EEA' (NEVER null); status:'professional'; pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE; non_obvious; non_obvious_note; needs_lawyer_review; quote_verbatim_confirmed:false; corridor:'SG->FR'}.
>
> MANIFEST: batch_id='sg-fr-return-2026-09-10', corridor='SG-FR', origin_country_code='SG', destination_country_code='FR', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope (note the batch is mixed-audience: SG-exit non-EEA + FR-reentry EEA).
>
> SOURCES (official only): SG — iras.gov.sg, mom.gov.sg; FR — service-public.fr, impots.gouv.fr, ameli.fr, urssaf.fr.
> SCOPING + HONESTY: nationality per fact never null; no fabrication; candidate-only.
>
> FILES only; Claude Code serves these in the roadmap's Return & repatriation phase (already built). Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Adrien P10).

- **Validation:** Gate `python scripts/check_otto_batches.py sg-fr-return-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote; return fact_keys distinct from outbound; each fact cites an official source; SG-exit facts nationality non-EEA and FR-reentry facts EEA.
- **Expected output:** `docs/imports/sg-fr-return-2026-09-10/` = `sg-fr-return-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py sg-fr-return-2026-09-10`

---

# 4 · Abraham — US→EC (Seattle→Quito), US / third-country residence visa

## AB-P1 · US-departure requirement facts → `us-departure-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — US-departure requirement facts for the US→EC corridor (persona: Abraham Romo, US national, Seattle→Quito on a professional residence visa). This corridor has NO origin-side facts yet — net-new. Deliver candidate-only NDJSON + manifest + README under docs/imports/us-departure-2026-09-10/.
>
> TOPICS (US exit side, for a departing US citizen): US citizens remain subject to federal income tax filing while abroad (Form 1040), the Foreign Earned Income Exclusion (Form 2555) and FBAR (FinCEN 114) obligations; Washington State has NO state income tax (so no state exit filing — state this as a fact); there is NO US–Ecuador totalization (social-security) agreement — deliver this as an explicit fact (both countries may levy social contributions); maintaining a US mailing address / SSN; State Dept / STEP enrolment.
>
> RECORD (one JSON per NDJSON line): destination_country='US' (obligations apply in the US); entity_topic_key; fact_key (globally unique, prefix 'us_ec_dep_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'non-EEA' (the EEA/non-EEA vocab is EU-centric; a US citizen is non-EEA / third-country in the corridor framing — follow the existing us-ec-facts batch precedent; NEVER null); status:'professional'; pillar ∈ EMPLOYMENT|SOCIAL_SECURITY|IDENTITY|RESIDENCE; non_obvious; non_obvious_note; needs_lawyer_review; quote_verbatim_confirmed:false; corridor:'US->EC'}.
>
> MANIFEST: batch_id='us-departure-2026-09-10', corridor='US-EC', origin_country_code='US', destination_country_code='US', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only; blogs/law-firms/vendors REJECTED): irs.gov, fincen.gov, ssa.gov, travel.state.gov, dor.wa.gov (Washington).
> HONESTY: no fabrication; every fact_text backed by an evidence_quote; the no-totalization-treaty fact must be sourced to ssa.gov's totalization-agreements list (its ABSENCE from that list is the evidence); needs_lawyer_review:true for any tax determination. Candidate-only.
>
> FILES only; Claude Code owns loads/reviews and will author the US_EC pathway from these + the EC destination facts. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Abraham P1).

- **Validation:** Gate `python scripts/check_otto_batches.py us-departure-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote; >=6 official-sourced US-exit facts; the no-US-EC-totalization fact is sourced to ssa.gov (absence from the agreements list) and the WA no-state-income-tax fact to dor.wa.gov.
- **Expected output:** `docs/imports/us-departure-2026-09-10/` = `us-departure-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py us-departure-2026-09-10`

## AB-P2 · Ecuador pre-departure health resources → `ec-predeparture-health-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Pre-departure health resources for the move to Quito, Ecuador (persona: Abraham + accompanying family). Deliver a candidate-only JSON ImportBundle + README under docs/imports/ec-predeparture-health-2026-09-10/.
>
> GOAL: a pre-departure health guide/checklist covering: recommended vaccinations (Hep A/typhoid; yellow-fever for Amazon-region travel; the CDC destination page for Ecuador); altitude acclimatisation (Quito sits at ~2,850 m); carrying medical records and repeat prescriptions; private/international health insurance for the cover gap before IESS affiliation; finding care in Quito.
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'EC', city_name:'Quito', category_key:'healthcare', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL: cdc.gov travel-health / salud.gob.ec (MSP) / cancilleria.gob.ec), source_name, tags, status:'draft'}.
>
> SOURCES (official only): cdc.gov (US govt travel health — authoritative for vaccinations), salud.gob.ec (MSP), cancilleria.gob.ec. No blogs/vendors.
> HONESTY: every claim carries its official source_url; do not overstate a vaccination as mandatory unless the source says so; status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Abraham P2).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; all resources status='draft'; each carries an official source_url; the yellow-fever guidance is scoped to Amazon-region travel (not blanket); validate-only load clean.
- **Expected output:** `docs/imports/ec-predeparture-health-2026-09-10/` = `ec-predeparture-health-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/ec-predeparture-health-2026-09-10/ec-predeparture-health-2026-09-10.bundle.json --validate-only`

## AB-P3 · Quito temp/serviced housing vendors → `us-ec-quito-temp-housing-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Temporary / serviced-housing vendor directory for Quito (bridging accommodation before a permanent lease). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/us-ec-quito-temp-housing-2026-09-10/.
>
> GOAL: 4-6 serviced-apartment / aparta-suite providers in Quito for relocating employees.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='US-EC' (or 'XX-EC'), service_category='temp_accommodation'.
> PROVENANCE (decisive, browser-grounded where needed): source_url must be an OFFICIAL register that LISTS the firm — the Ministerio de Turismo catastro turístico (turismo.gob.ec) registration, or the SRI RUC company record. The firm's own site is tier-3 and auto-rejected; cite the register.
>
> MANIFEST: batch_id='us-ec-quito-temp-housing-2026-09-10', corridor, categories:[{service_category:'temp_accommodation', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: firm not sourceable to a register → rejects.csv with reason; land at platform_vetting_status='pending'.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Abraham P3).

- **Validation:** Import dry-run clean; >=3 firms pass the provenance gate (Min. Turismo catastro / SRI RUC); every accepted row cites an official source; rejects.csv explains drops.
- **Expected output:** `docs/imports/us-ec-quito-temp-housing-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-temp-housing-2026-09-10/providers.csv`

## AB-P4 · Quito GP/medical vendors → `us-ec-quito-medical-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — GP / medical-provider directory for Quito (clinics/hospitals registering new arrivals; English-speaking noted). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/us-ec-quito-medical-2026-09-10/.
>
> GOAL: 4-6 clinics / private hospitals / general practitioners in Quito accepting new patients (flag English-speaking / expat-oriented).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-EC', service_category='medical'.
> PROVENANCE (browser-grounded where needed): source_url must be an OFFICIAL register — the ACESS (Agencia de Aseguramiento de la Calidad de los Servicios de Salud) licensed-facility listing or the MSP (salud.gob.ec) directory. Put ACESS/MSP in accreditation_body + the register listing in source_url. A clinic's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='us-ec-quito-medical-2026-09-10', corridor, categories:[{service_category:'medical', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as AB-P3. GDPR/data-min — facility inbox, never a personal email.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Abraham P4).

- **Validation:** Import dry-run clean; >=3 facilities pass the provenance gate against ACESS/MSP; every accepted row cites the register; rejects.csv explains drops.
- **Expected output:** `docs/imports/us-ec-quito-medical-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-medical-2026-09-10/providers.csv`

## AB-P5 · EC driving-licence exchange guide → `ec-driving-licence-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Driving-licence guide for Ecuador, scoped to Abraham (US licence holder). Delivered as a RESOURCE bundle (transport guidance, not a gated pillar). Deliver a candidate-only JSON ImportBundle + README under docs/imports/ec-driving-licence-2026-09-10/.
>
> GOAL: a clear guide answering — how long Abraham can drive in Ecuador on a US licence (and/or an International Driving Permit); whether/when a US licence can be exchanged for an Ecuadorian one or a local test is required; the process and where to apply (ANT — Agencia Nacional de Tránsito); documents required.
>
> BUNDLE (JSON): {categories, tags, sources, resources, events}. Each resource: {country_code:'EC', city_name:'Quito' or null, category_key:'transport', title, resource_type ∈ guide|checklist_item|official_link|tip, summary, body, source_url (OFFICIAL: ant.gob.ec), source_name, tags, status:'draft'}.
>
> SOURCES (official only): ant.gob.ec, cancilleria.gob.ec.
> HONESTY: state the exchange/validity rules as published; if unclear, say so and do not invent it. status 'draft' only.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.B + §4.R (Abraham P5).

- **Validation:** Bundle validates; resource_type/category_key in-vocab; status='draft'; the US-licence validity/exchange rule is sourced to ant.gob.ec (or marked unclear); validate-only load clean.
- **Expected output:** `docs/imports/ec-driving-licence-2026-09-10/` = `ec-driving-licence-2026-09-10.bundle.json` + `README.md`.
- **Test command:** `python scripts/import_resources.py --bundle docs/imports/ec-driving-licence-2026-09-10/ec-driving-licence-2026-09-10.bundle.json --validate-only`

## AB-P6 · Quito Spanish-language school vendors → `us-ec-quito-language-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Spanish-language school vendor directory for Quito (Spanish tuition for Abraham + family; a US national moving to a Spanish-speaking country — language is a core need here, not just family-scoped). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/us-ec-quito-language-2026-09-10/.
>
> GOAL: 4-6 Spanish-language schools in Quito offering adult general Spanish (Quito is a well-known Spanish-immersion destination).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-EC', service_category='language'.
> PROVENANCE (browser-grounded where needed): source_url must be an OFFICIAL register — the SETEC (Secretaría Técnica de Formación Profesional) accredited-provider listing, or an SRI RUC company record, or (for schools accredited to teach Spanish as a foreign language) the relevant Instituto Cervantes accreditation if present. A school's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='us-ec-quito-language-2026-09-10', corridor, categories:[{service_category:'language', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as AB-P3.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Abraham P6).

- **Validation:** Import dry-run clean; >=3 schools pass the provenance gate (SETEC / SRI RUC / Instituto Cervantes); every accepted row cites its source; rejects.csv explains drops.
- **Expected output:** `docs/imports/us-ec-quito-language-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-language-2026-09-10/providers.csv`

## AB-P7 · Quito dual-career / spouse-employment vendors → `us-ec-quito-dual-career-2026-09-10` — P2

**Execution Prompt**

> OTTO RESEARCH — Dual-career / spouse-employment support vendors for Quito (career coaching, CV/interview support, job-search help for Abraham's accompanying partner). Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/us-ec-quito-dual-career-2026-09-10/.
>
> GOAL: 4-6 providers offering spouse/partner career-transition services in Quito (career coaches / outplacement / relocation career firms).
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. corridor='XX-EC', service_category='spouse'.
> PROVENANCE (browser-grounded where needed): prefer providers listed on an OFFICIAL register/body — an SRI RUC company record, or an ICF-accredited coach directory. Cite the register in source_url. A provider's own site alone is tier-3 and rejected.
>
> MANIFEST: batch_id='us-ec-quito-dual-career-2026-09-10', corridor, categories:[{service_category:'spouse', register, denominator, accepted, rejected, confidence, notes}], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected.
> HONESTY + candidate-only: as AB-P3. (Dependant work-rights under the residence visa belong in the facts batches — this card is career-services vendors only.)
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Abraham P7).

- **Validation:** Import dry-run clean; >=3 providers pass the provenance gate (SRI RUC / ICF); every accepted row cites its source; rejects.csv explains drops.
- **Expected output:** `docs/imports/us-ec-quito-dual-career-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-dual-career-2026-09-10/providers.csv`

## AB-CORE · Quito core-provider re-source (banks/schools/legal/tax, browser-grounded) → `us-ec-quito-core-providers-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Core-provider directory for Quito, browser-grounded. FILLS THE BLOCKED GAP: Ecuador currently has 0 providers for banks/schools/legal/tax because the official registers are JS/iframe/login-gated. Source these via the browser (render the register, read the listing) and cite the official regulator. Deliver a candidate-only 9-column CSV + rejects + manifest + README under docs/imports/us-ec-quito-core-providers-2026-09-10/.
>
> GOAL: 3-5 each of: banks onboarding foreign residents, international/IB schools, immigration lawyers, and tax/accounting advisers — all in Quito.
>
> CSV — fixed 9-column header, exact order: corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry. One file, one row per firm; corridor='US-EC' (or 'XX-EC'); service_category is one of banks | schools | legal_admin | tax_finance per row.
> PROVENANCE (decisive, browser-grounded): source_url must be an OFFICIAL regulator listing rendered in-browser — banks: Superintendencia de Bancos (superbancos.gob.ec); schools: Ministerio de Educación (educacion.gob.ec) or the IB world-school finder for international schools; legal: the Foro de Abogados via the Consejo de la Judicatura (funcionjudicial.gob.ec); tax: the relevant Colegio de Contadores. A firm's own site alone is tier-3 and rejected; note in the README which registers were JS-gated and how you rendered them.
>
> MANIFEST: batch_id='us-ec-quito-core-providers-2026-09-10', corridor, categories:[{service_category, register, denominator, accepted, rejected, confidence, notes} for each of banks/schools/legal_admin/tax_finance], files:{'providers.csv':{records, sha256}}, total_accepted, total_rejected, least_certain_category.
> HONESTY + candidate-only: a firm not sourceable to a rendered official register → rejects.csv with the reason; land at platform_vetting_status='pending'; nothing served until a human approves.
>
> FILES only. Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.C + §4.R (Abraham — blocked providers).

- **Validation:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-core-providers-2026-09-10/providers.csv` dry-run clean; each of the 4 categories has >=3 firms passing the provenance gate against a rendered official register; rejects.csv explains drops; README notes which registers were JS-gated.
- **Expected output:** `docs/imports/us-ec-quito-core-providers-2026-09-10/` = `providers.csv` + `rejects.csv` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/import_supplier_candidates.py docs/imports/us-ec-quito-core-providers-2026-09-10/providers.csv`

## AB-P10 · EC→US return requirement facts → `ec-us-return-2026-09-10` — P1

**Execution Prompt**

> OTTO RESEARCH — Return/repatriation requirement facts for the reverse corridor EC→US (persona: Abraham, US national, ending a Quito assignment and returning to the US). Deliver candidate-only NDJSON + manifest + README under docs/imports/ec-us-return-2026-09-10/. SKELETON (6-10 highest-value return facts).
>
> TOPICS: HOST-EXIT (Ecuador) — SRI tax-residence exit / final RUC filing, IESS de-registration, cancel/close the residence visa & cédula obligations, any exit certificate; HOME RE-ENTRY (US) — re-establish US state residency (Washington), resume normal IRS filing (end of FEIE), re-enrol in US health coverage, reactivate SSN-linked benefits.
>
> RECORD (one JSON per NDJSON line): destination_country = the ISO-2 where each obligation applies ('EC' for host-exit, 'US' for home-re-entry); entity_topic_key; fact_key (globally unique, prefix 'ec_us_ret_', STABLE); fact_text; source_url (OFFICIAL host); evidence_quote (verbatim, >=25 chars); fact_type ∈ eligibility|document|deadline|fee|where_to_apply|other — NEVER 'step'; confidence ∈ high|medium|low; applies_to = {nationality:'non-EEA' (US citizen; NEVER null); status:'professional'; pillar ∈ RESIDENCE|IDENTITY|EMPLOYMENT|HOUSING|SOCIAL_SECURITY|HEALTHCARE; non_obvious; non_obvious_note; needs_lawyer_review; quote_verbatim_confirmed:false; corridor:'EC->US'}.
>
> MANIFEST: batch_id='ec-us-return-2026-09-10', corridor='EC-US', origin_country_code='EC', destination_country_code='US', nationality_class='THIRD_COUNTRY', target_table='public.requirement_items', record_count, non_obvious_count, needs_lawyer_review_count, artifact, sha256, review_status_all='pending', verification_status_all='representative', scope.
>
> SOURCES (official only): EC — sri.gob.ec, iess.gob.ec, cancilleria.gob.ec; US — irs.gov, ssa.gov, dor.wa.gov. needs_lawyer_review:true on any tax determination.
> SCOPING + HONESTY: nationality never null; no fabrication; candidate-only.
>
> FILES only; Claude Code serves these in the roadmap's Return & repatriation phase (already built). Full contract: docs/otto/journey-completion-brief-2026-09-10.md §3.A + §4.R (Abraham P10).

- **Validation:** Gate `python scripts/check_otto_batches.py ec-us-return-2026-09-10` passes; sha256 + counts reconcile; unscoped-topics empty; 100% promote; return fact_keys distinct from the outbound US→EC keys; each fact cites an official source.
- **Expected output:** `docs/imports/ec-us-return-2026-09-10/` = `ec-us-return-2026-09-10.ndjson` + `manifest.json` + `README.md`.
- **Test command:** `python scripts/check_otto_batches.py ec-us-return-2026-09-10`

---

## Corridor-authoring cards (Claude Code, not Otto)

Two cards stay `Blocked` on the board and are **not** in the paste set — they are Claude Code work,
authored from the facts above once loaded:

- **AD-WIRE** (AIQ-2255) — Author `corridors/FR_SG/` pathway graph + `facts.yaml`. Unblocks when
  `fr-departure-2026-09-10` (AD-P1) + `fr-sg-tax-2026-09-10` (AD-TAX) load to pending.
- **AB-WIRE** (AIQ-2265) — Author `corridors/US_EC/` pathway graph + `facts.yaml`. Unblocks when
  `us-departure-2026-09-10` (AB-P1) loads to pending.

## Batch summary

| Persona | Corridor | Packages | of which P1 (facts spine) |
|---|---|---|---|
| Andrea | ES→IE | 9 (A-P1..P7, P9, P10) | A-P1 (ES departure), A-P10 (IE→ES/VE return) |
| Denis | NO→FR | 8 (D-P1..P7, P10) | D-P1 (NO departure), D-P10 (FR→NO return) |
| Adrien | FR→SG | 8 (AD-P1..P7 less P6/P9, + TAX, P10) | AD-P1 (FR departure), AD-TAX (SG tax), AD-P10 (SG→FR return) |
| Abraham | US→EC | 9 (AB-P1..P7, CORE, P10) | AB-P1 (US departure), AB-CORE (blocked providers), AB-P10 (EC→US return) |

**34 Otto research packages.** Deliver files-only, candidate-only; Claude Code gates → loads →
wires; a human reviewer/counsel promotes to live.
