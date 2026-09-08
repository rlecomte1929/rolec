# T18 Madrid → Dublin — Claude Code execution prompts

**Generated 2026-08-13** from the T18 campaign + live codebase recon against `rolec@main`.
Five prompts, **sequential — run in this order, one session, one PR each.**

| # | Notion task | What it unblocks | Tier |
|---|---|---|---|
| 1 | T18-01 | Corridor reaches every consumer | 🔴 Red |
| 2 | T18-05 | Nationality reaches `nationality_class` | 🔴 Red |
| 3 | T18-03 | Ireland stops being offered a Blue Card | 🔴 Red |
| 4 | T18-02 | ES→IE requirements exist at all | 🔴 Red |
| 5 | T18-06 | Dublin settle-in content is real | 🔴 Red |

**Why sequential:** 1, 2 and 3 all touch the immigration read path; 4 and 5 are content but their
acceptance tests only pass once 1 lands. Prompts 4 and 5 can be *authored* in parallel — just don't
merge them before 1.

---

## Session preamble — paste once, before prompt 1

```
We are working the T18 Madrid→Dublin findings in the rolec repo. Context you need up front:

A test campaign drove the real prod API (api.relopass.com) through a Madrid→Dublin move for
two personas — a Spanish national (EU free movement) and an Indian national resident in Spain
(third-country, Critical Skills Employment Permit). Report: ReloPass_T18_Madrid-Dublin_Report_2026-08-13.md
at repo root. Raw evidence: results/t18_results_2026-08-13.json and results/t18_evidence_2026-08-13.json.
Re-runnable harness: scripts/madrid_dublin_runner.mjs.

Ground rules for every task in this batch:

1. RECON BEFORE EDIT. Each prompt names the files. Read them before proposing anything.
   Several of these findings already have partial fixes in the repo — find them first.
2. Do NOT create a second source of truth. This codebase already has a documented
   case-table schism (AIQ-1818: relocation_cases is the HR case of record, public.cases
   is the wizard/seed side). Every task here is about making an EXISTING value reach an
   EXISTING consumer.
3. FAIL CLOSED. For anything immigration-related, a null with an explicit "not determined"
   state beats a plausible guess. A wrong permit is the one defect class that harms a customer.
4. One PR per prompt. Do not batch. Stop at the approval gate in each prompt.
5. Content changes are REPRESENTATIVE until SME-verified — keep the existing provenance
   model and make sure scripts/check_compliance_claims.py still passes.

Confirm you've read the report and the two evidence files, then wait for prompt 1.
```

---

# Prompt 1 — T18-01: make the submitted corridor reach its consumers

```
TASK: T18-01. After a successful employee intake submit for a Madrid→Dublin case, every
corridor-aware consumer still reads corridor_from=null / corridor_to=null. Find out why and
fix it.

=== VERIFIED EVIDENCE (prod, 2026-08-13) ===
Case 07a99b8f-bd18-425b-8416-8daa7bf03414, assignment 22862487-7da6-4891-9f36-a2df0bfb1184.

  PATCH /api/employee/assignments/{aid}/intake-draft  (flat snake_case, real wizard shape) -> 200
  POST  /api/employee/assignments/{aid}/submit                                             -> 200 {"success":true}
  GET   /api/relocation-plans/{id}/view    -> phases:5 tasks:16      <-- WORKS, do not touch
  GET   /api/cases/{id}/requirements       -> missing_fields:["origin_country","destination_country","employment_type"]
  GET   /api/hr/cases/{id}/immigration-requirements
                                           -> {covered:false, coverage_reason:"corridor_not_supported",
                                               corridor:null, corridor_from:null, corridor_to:null}
  GET   /api/employee/cases/{id}/immigration-snapshot -> corridor_from:null, corridor_to:null
  GET   /api/resources/country?assignment_id={aid}    -> profile.destination_country:"" destination_city:""
  GET   /api/employee/assignments/{aid}/marketplace   -> corridor:null
  GET   /api/hr/cases/{id}  -> profile_json.movePlan = {origin:"Oslo, Norway", destination:"Singapore"}

Reproduced on 3 independent cases.

=== CRITICAL: A WRITE PATH ALREADY EXISTS — START THERE ===
Do NOT assume nothing is written. backend/main.py submit_assignment (~line 6368) already does:

    eff_case_for_sync = _effective_relocation_case_id(assignment)
    ...
    db.sync_relocation_case_route_from_wizard_draft(eff_case_for_sync, promote_draft)

and backend/db/cases.py:3106 sync_relocation_case_route_from_wizard_draft() denormalises
relocationBasics onto relocation_cases via wizard_basics_to_route() + touch_relocation_case_route_from_wizard().
This shipped as AIQ-1311 and has a live verifier: scripts/verify_intake_submit_spine.py.

So the most likely shape of this bug is NOT a missing write — it is that the WRITE and the
READS disagree about which record holds the corridor. Establish which before you change anything.

=== PHASE 1 — RECON (no edits) ===
Read, in this order:
  1. backend/main.py:6313-6410     submit_assignment: draft read, promote, sync
  2. backend/db/cases.py:3106      sync_relocation_case_route_from_wizard_draft
     backend/intake_route_fields.py:35   wizard_basics_to_route
     backend/db/cases.py:3055       touch_relocation_case_route_from_wizard
  3. backend/intake_draft_to_case_draft.py   flat snake_case -> camelCase CaseDraftDTO
  4. scripts/verify_intake_submit_spine.py   what AIQ-1311 asserts today
  5. The four consumers and note WHICH table/column each reads corridor from:
       backend/app/routers/cases_read.py                    /api/cases/{id}/requirements
       backend/app/routers/immigration_status.py            immigration-requirements
       backend/app/routers/employee_immigration_snapshot.py immigration-snapshot
       backend/app/services/country_resources.py            build_profile_context (resources/country)

Then run scripts/verify_intake_submit_spine.py and report: does the AIQ-1311 sync still pass?

ANSWER THESE THREE QUESTIONS IN WRITING BEFORE EDITING:
  Q1. After submit, does relocation_cases actually hold home_country/host_country for this case?
      (Query prod. If YES, this is purely a read-side bug.)
  Q2. Which record does each of the four consumers read — relocation_cases, public.cases,
      employee_profiles, or case_assignments.intake_draft?
  Q3. Is _effective_relocation_case_id (backend/main.py:6789) returning the same id the
      consumers look up by? The AIQ-1311 comment says a divergent case-id already caused
      exactly one incident here — "submit read an empty draft and 400'd a fully-filled wizard."

=== PHASE 2 — APPROVAL GATE ===
Post your answers to Q1–Q3 plus a one-paragraph fix proposal naming the single authoritative
source for corridor. STOP. Wait for approval. Do not edit before this.

=== PHASE 3 — IMPLEMENT (after approval) ===
Constraints:
  - Reuse the existing resolver pattern. AIQ-1803 established resolve_case_identities
    (backend/db/cases.py:1962) as the read-side route for employee identity; corridor should
    follow the same shape, not a new one.
  - Type trap, already paid for once in this repo: profiles.id and cases.id are uuid, every
    case_assignments column is text. A join without CAST(... AS TEXT) raises
    "operator does not exist: uuid = text" and, inside a fail-soft except, silently returns nothing.
  - Do NOT fix profile_json.movePlan's Oslo→Singapore default here. AIQ-1818 recorded it as
    vestigial and a backfill there is a DSAR defect. If a consumer reads movePlan, repoint the
    consumer — do not write to movePlan.
  - Leave the relocation-plan generation path alone. It works (phases:5/tasks:16).

=== ACCEPTANCE (all must pass on a fresh prod case) ===
  1. POST submit -> 200 {"success":true}
  2. GET /api/cases/{id}/requirements -> missing_fields excludes origin_country,
     destination_country, employment_type
  3. GET /api/hr/cases/{id}/immigration-requirements -> corridor_from="ES" AND corridor_to="IE"
  4. GET /api/employee/cases/{id}/immigration-snapshot -> corridor_from="ES" AND corridor_to="IE"
  5. GET /api/resources/country?assignment_id={aid} -> profile.destination_country="IE",
     destination_city="Dublin"
  6. GET /api/employee/assignments/{aid}/marketplace -> corridor is non-null
  7. scripts/verify_intake_submit_spine.py still passes
  8. cd backend && pytest tests/ -k "submit or intake or corridor" -q  passes

VERIFY COMMAND: node scripts/madrid_dublin_runner.mjs
  then assert corridor_from/corridor_to are non-null in the emitted t18_results_*.json

Commit on branch fix/t18-01-corridor-propagation. Do not merge.
```

---

# Prompt 2 — T18-05: make nationality reach `nationality_class`

```
TASK: T18-05. Nationality submitted through the intake wizard never surfaces, so the
EU_EEA vs THIRD_COUNTRY branch cannot fire for any case.

=== VERIFIED EVIDENCE (prod, 2026-08-13) ===
After an intake carrying nationality="ES" and a submit returning success:true:
  GET /api/employee/cases/{id}/intake-nationality -> {"nationality":null,"second_nationality":null}
  GET /api/cases/{id}/requirements                -> nationalityClass:null
  GET /api/hr/cases/{id}                          -> profile_json.primaryApplicant.nationality:null

Consequence: the ES (EU) and IN (third-country) personas returned BYTE-IDENTICAL requirements
payloads. The only differing keys across the entire response were caseId and computedAt.

The engine is NOT the problem. The same public endpoint branches correctly for other
destinations — GET /api/public/corridor-requirements?from=ES&to=X&employee_type=PERMANENT
&purpose=employment&nationality={ES|IN}:
    DE  7 EU_EEA / 7 THIRD_COUNTRY
    NO 11 EU_EEA / 8 THIRD_COUNTRY
    NL  6 EU_EEA / 8 THIRD_COUNTRY
    FR  5 EU_EEA / 9 THIRD_COUNTRY
The value simply never arrives from the case.

=== THE MACHINERY THAT ALREADY EXISTS ===
  backend/app/services/nationality_class.py       EU_EEA / THIRD_COUNTRY / OWN_NATIONAL constants
                                                  at lines 29-30; classify(nationality, dest_country)
                                                  at line 137; is_free_movement_national() at line 156
  backend/app/services/requirements_builder.py:242 filters on applies_to_nationality_classes_json
  backend/app/models.py:98-100                     the applies_to_nationality_classes_json column
  backend/app/schemas.py:173                       "OWN_NATIONAL | EU_EEA | THIRD_COUNTRY | None
                                                    when nationality is unknown"

Note that last comment: null is the DOCUMENTED behaviour when nationality is unknown. So this
is not a broken classifier — the classifier is correctly reporting that it was given nothing.

=== PHASE 1 — RECON (no edits) ===
Trace nationality end to end and report where it is lost:
  1. backend/intake_draft_to_case_draft.py  — the employee_profile block. Does it map
     data["nationality"] into employeeProfile.nationality? (It appears to. Confirm.)
  2. backend/main.py:6012 _draft_to_relocation_profile — does nationality survive into the
     profile dict that db.save_employee_profile() writes?
  3. employee_profiles.nationality — column exists (supabase/migrations/20260518120000_
     immigration_core_tables.sql:58, "ISO 3166-1 alpha-2 (e.g. 'FR')"). Is it ever written?
  4. backend/app/routers/immigration_intake_profile.py — what does intake-nationality READ?
  5. Where is classify() actually called from in the request path for /api/cases/{id}/requirements?

Report the exact hop where the value is dropped. There is one; find it rather than adding a write.

=== PHASE 2 — APPROVAL GATE ===
Post the trace and the single-hop fix. STOP for approval.

=== PHASE 3 — IMPLEMENT (after approval) ===
Constraints:
  - Nationality is personal data. employee_profiles is already inside the DSAR/GDPR surface —
    check backend/app/routers/gdpr.py and immigration_gdpr.py. If you write nationality anywhere
    NEW, a subject-access request will under-report. Strongly prefer the existing
    employee_profiles.nationality column.
  - Do not duplicate the EU/EEA country set. There are already three copies in this repo and a
    comment in immigration_regime.py:84-94 recording that consolidating them onto
    nationality_class.is_free_movement_national was a deliberate fix. Use that function.
  - Switzerland is EU_EEA for this purpose — nationality_class.py:46 records that classifying
    CH as THIRD_COUNTRY "would reproduce the exact bug this module exists to prevent."

=== ACCEPTANCE ===
  1. Submit an intake with nationality="ES" -> GET /api/employee/cases/{id}/intake-nationality
     returns nationality="ES"
  2. GET /api/cases/{id}/requirements -> nationalityClass="EU_EEA"
  3. Same flow with nationality="IN" -> nationalityClass="THIRD_COUNTRY"
  4. On a corridor WITH content (use ES→NO), the two personas now receive DIFFERENT
     requirement lists on the same case shape. This is the real proof.
  5. No nationality written outside a path the existing DSAR resolver already reaches
  6. cd backend && pytest tests/ -k "nationality or intake_nationality or requirements_builder" -q

Commit on branch fix/t18-05-nationality-persistence. Do not merge.
```

---

# Prompt 3 — T18-03: stop offering Ireland an EU Blue Card

```
TASK: T18-03. visa_type resolves to "blue_card" for Ireland. Ireland does not participate in
the EU Blue Card Directive. This is served to the employee.

=== SOURCE OF TRUTH ===
European Commission, EU Immigration Portal:
  "The EU Blue Card applies in 25 of the 27 EU Member States. It does not apply in Denmark
   and Ireland."
Ireland's equivalent instrument is the Critical Skills Employment Permit (DETE).

=== VERIFIED EVIDENCE (prod, 2026-08-13, 4 cases, both personas) ===
  GET /api/hr/cases/{id}/immigration-requirements
      -> {covered:false, coverage_reason:"corridor_not_supported", corridor:null,
          corridor_from:null, corridor_to:null, visa_type:"blue_card"}
      Returned even when corridor_to=IE is passed EXPLICITLY, and even when the corridor is
      entirely null — so it is a hardcoded default, not a corridor inference.
  GET /api/employee/cases/{id}/immigration-snapshot
      -> {covered:false, corridor_from:"ES", corridor_to:"IE", visa_type:"blue_card"}
      This one reaches the EMPLOYEE.

=== TWO DISTINCT DEFECTS — FIX BOTH ===

DEFECT A — the regime detector treats Ireland as a Blue Card state.
  backend/app/services/immigration_regime.py, step 5b, lines 334-356
  (the `if` opens at 341, `regime_id="blue_card"` is emitted at line 347):

      if (_is_eu_member_destination(destination_country)
          and not _is_eu_national(nationality)
          and not intra_group_transfer):
          return self._make(regime_id="blue_card", ...)

  Ireland IS an EU member state, so _is_eu_member_destination("IE")
  (immigration_regime.py:110) is True and any third-country national → IE is classified blue_card.

  The fix has an EXACT precedent in the same file. _EU_MEMBER_STATES (line 105) is already
  derived as `_EU_EEA_COUNTRIES - frozenset({...})`, with the comment at lines 102-104
  explaining it holds "EU members, NOT the EEA/EFTA-only countries (Norway, Iceland,
  Liechtenstein, Switzerland). So a non-EEA national → Norway is a national skilled-worker
  permit, not a Blue Card."

  That is the identical reasoning, one directive-membership level down. Apply it to the two
  EU members outside Directive 2021/1883: IE and DK. Encode as a named frozenset with the
  directive cited in a comment — not as an inline `!= "IE"`.

DEFECT B — "blue_card" is a hardcoded parameter default in three places:
  backend/app/routers/employee_immigration_snapshot.py:26   visa_type: str = Query("blue_card")
  backend/app/routers/immigration_intake_consent.py:116     visa_type: str = "blue_card"
  backend/app/services/immigration_snapshot_service.py:47   build_immigration_snapshot(case_id, visa_type="blue_card")

  READ backend/app/routers/immigration_forms.py:68-80 FIRST. Its docstring documents this exact
  bug already being fixed once, in that file, tagged [AIQ-1771]:
      "Both inputs are resolved from the case, never defaulted. The previous signature defaulted
       visa_type='blue_card' and fell back to corridor_to='DE', which produced two distinct wrong
       answers: a FR case queried FR+blue_card, matched nothing, and showed NO forms — the feature
       simply looked absent; a case with no dest_country became a German case and was offered the
       Blue Card — a wrong form presented as correct."
  "Resolved from the case, never defaulted" is the pattern. Apply it to the three sites above
  rather than inventing a new one. Read the AIQ-1771 diff if you can find it.

=== PHASE 1 — RECON (no edits) ===
  1. immigration_regime.py — read detect_regime() in full (~line 257 onward), all six steps
  2. immigration_forms.py:60-100 — the precedent fix
  3. The three default sites above — determine for each whether the caller ever passes a real
     visa_type, or whether the default is always what's used
  4. Grep for other blue_card defaults: grep -rn 'blue_card' backend/ --include=*.py | grep -v tests/
  5. Confirm which corridors currently DEPEND on the blue_card default (IN→DE is seeded as
     blue_card in supabase/migrations/20260608100000_ingest_us_fr_in_de_corridors.sql —
     that one is correct and must not regress)

=== PHASE 2 — APPROVAL GATE ===
Post: the frozenset you propose, the three call sites and what each becomes, and the list of
corridors whose visa_type changes as a result. STOP for approval.

=== PHASE 3 — IMPLEMENT (after approval) ===
  - Prefer null + an explicit "not determined" state over any fallback. A null visa_type that
    the UI renders honestly is correct; a confident wrong permit is not.
  - Ireland's third-country regime should be the Critical Skills Employment Permit, not a
    generic standard_work_permit, if you are adding a regime_id. If that is more than a
    one-line change, return "not determined" and open a follow-up rather than half-modelling it.

=== ACCEPTANCE ===
  1. immigration-requirements for an IE case -> visa_type != "blue_card"
  2. immigration-snapshot for an IE case -> visa_type != "blue_card"
  3. With corridor_from/corridor_to null -> visa_type is null, not a guess
  4. A unit test asserts no Blue Card is ever emitted for destination IE or DK, for any nationality
  5. REGRESSION GUARD: FR, DE, NO and NL keep their current visa_type values. Assert IN→DE is
     still blue_card — that one is correct.
  6. cd backend && pytest tests/ -k "regime or visa_type or immigration_forms" -q

Commit on branch fix/t18-03-ireland-not-blue-card. Do not merge.
```

---

# Prompt 4 — T18-02: ingest the ES→IE corridor

```
TASK: T18-02. ES→IE returns zero requirements at every employee type. Ireland is in the
destination catalog and sellable, but the requirements engine has nothing for it.

=== VERIFIED EVIDENCE (prod, 2026-08-13) ===
GET /api/public/corridor-requirements?from=ES&to={dest}&employee_type=PERMANENT&purpose=employment&nationality={nat}

  dest | nat=ES              | nat=IN
  IE   | 0 reqs, class null  | 0 reqs, class null      <-- the gap
  DE   | 7 reqs, EU_EEA      | 7 reqs, THIRD_COUNTRY
  NO   | 11 reqs, EU_EEA     | 8 reqs, THIRD_COUNTRY
  NL   | 6 reqs, EU_EEA      | 8 reqs, THIRD_COUNTRY
  FR   | 5 reqs, EU_EEA      | 9 reqs, THIRD_COUNTRY

Same for LTA and STA. coverage_note: "No generic requirements are configured for destination
IE + PERMANENT in the engine yet."

Meanwhile GET /api/employee/destinations returns Dublin as {"notes":"ReloPass curated"},
approved 2026-05-18, plus Cork/Galway/Limerick/Waterford added 2026-08-12 by the geo-expansion job.

=== EXISTING ASSETS — READ BEFORE WRITING ANYTHING ===
  corridors/ES_IE/corridor.yaml
      Already exists. Header states plainly: "no ES_IE corpus chunks exist yet, so the
      immigration answer engine will fall back to its global retrieval until Tier-1 ES_IE
      sources are ingested — a known gap." Also carries at_risk_window_days: 104, derived from
      the CSEP step graph.
  corridors/ES_IE/pathways/CSEP_2026/v1.yaml
      The step graph. Primary pathway is the Critical Skills Employment Permit; the General
      Employment Permit is an ALTERNATE_PATHWAY inside this file, not a separate corridor.
  supabase/migrations/20261010000000_seed_es_ie_immigration_corpus_docs.sql
      Corpus DOCS already seeded. This task is about immigration_requirements ROWS, which is
      a different table. Check what that migration actually landed before duplicating it.

=== THE INGEST PATTERN TO FOLLOW ===
  Generator:  backend/scripts/ingest_corridor_corpus.py
  Inputs:     corpus/*_corridor.json   (us_fr, in_de, uk_fr, ca_de, br_pt, us_nl)
  Output:     supabase/migrations/20260608100000_ingest_us_fr_in_de_corridors.sql
              (header: "Generated by backend/scripts/ingest_corridor_corpus.py — do not hand-edit")

  Target table: public.immigration_requirements
  Columns: corridor_from, corridor_to, visa_type, employee_type, document_type, document_name,
           is_required, is_conditional, condition_expression, freshness_days, requires_apostille,
           apostille_countries, requires_translation, translation_languages, can_be_prefilled,
           can_be_ocr_extracted, vault_field_mapping, typical_processing_days, book_early_flag,
           book_early_reason, success_tips, common_rejection_reasons, form_url, form_version,
           instructions_url, last_verified_date, source
  Conflict key: (corridor_from, corridor_to, visa_type, employee_type, document_type)

  Nationality branching is carried by immigration_requirements.applies_to_nationality_classes_json
  (backend/app/models.py:98-100), filtered in
  backend/app/services/requirements_builder.py:242. NULL means "applies to all".
  Use ["THIRD_COUNTRY"] and ["EU_EEA"] to split the two branches.

=== THE CONTENT (sourced 2026-08-13; full citations in the T18 report) ===

EU/EEA BRANCH — applies_to_nationality_classes_json = ["EU_EEA"]
The correct first message is that immigration requires NOTHING. Do not invent a permit step.
  - NO employment permit, NO entry visa, NO residence registration, NO residence card.
    Citizens Information: EEA/Swiss citizens "do not need to register with the immigration
    authorities and you do not need a residence card to live here."
  - PPSN — MyWelfare.ie application then a MANDATORY in-person appointment. Requires a signed
    offer of employment and proof of address less than 3 months old. No published processing
    time — do not invent one.
  - Register the job in Revenue myAccount. THE EMPLOYEE does this, not the employer. Miss it and
    from week 5 it is 40% income tax + 8% USC (Revenue, Emergency Tax rules).
  - PRSI Class A, employee 4.2% over €352/week.
  - Healthcare is residency-based, not nationality-based. No medical card on a Google salary
    (limit €184/week single). GP €45–65, unregulated. €100 ED charge without a GP referral.
  - Bank account: photo ID + a SEPARATE proof of address under 6 months. Note the catch-22 —
    an EEA citizen gets no IRP, which is one of the accepted photo IDs, and has no utility bill
    on arrival. Realistic order: PPSN → Revenue document → bank. THIS ORDERING IS THE MOST
    VALUABLE THING IN THIS BRANCH.
  - Spanish driving licence is exchangeable, €65, but the online route needs a Public Services
    Card which needs a PPSN first.

THIRD_COUNTRY BRANCH — applies_to_nationality_classes_json = ["THIRD_COUNTRY"]
  - Critical Skills Employment Permit. SOC 2136 (Programmers and Software Development
    Professionals) is on the Critical Skills Occupations List → €40,904 threshold.
    €68,911 for occupations not on the list. €36,848 for recent graduates. Fee €1,000,
    90% refunded if unsuccessful. No Labour Market Needs Test.
  - THE BINDING CONSTRAINT: the application must be RECEIVED at least 12 weeks before the
    employment start date. This — not the DETE backlog, currently ~9 days — is what sets the
    timeline. Model it as the lead-time driver.
  - Long-stay 'D' visa. India is visa-required. Applies via the Irish Embassy in MADRID
    (residence-based routing), not Delhi. A Spanish residence permit gives NO Irish entry
    right — Ireland is outside Schengen. This misunderstanding is expensive and common.
  - IRP registration within 90 days. First-time registration ONLY at Burgh Quay, Dublin.
    €300. Stamp 1. Book via portal.irishimmigration.ie; account can be created before travelling.
  - Spouse/partner gets Stamp 1G on registration → can work with NO separate permit. This is a
    real CSEP advantage over the General Employment Permit's 12-month wait.
  - Indian driving licence is NOT exchangeable. Full Irish process from the theory test.
  - Everything in the EU branch also applies (PPSN, Revenue, PRSI, healthcare, bank) — with one
    improvement: the IRP card IS an accepted bank photo ID.

TWO STALE FACTS TO AVOID REPRODUCING:
  - The DETE Trusted Partner Initiative is DISCONTINUED. Most third-party 2026 guides still
    advertise it as a fast-track. It is not.
  - CSEP thresholds beyond 2026 are explicitly "TBD following annual review and indexation".
    No 2027+ figures exist. Do not project them.

=== QUALITY BAR ===
Match the Norway entries, not the minimum schema. Norway's skattekort row does not just name
the requirement — it names the consequence and cites the authority: "without one, the employer
must deduct 50 percent tax" (Skatteetaten). Every ES→IE row should do the same. That specificity
is the product.

=== PHASE 1 — RECON, then APPROVAL GATE ===
  1. Read corridors/ES_IE/corridor.yaml and pathways/CSEP_2026/v1.yaml in full
  2. Read one existing corpus JSON (corpus/in_de_corridor.json) to learn the input schema
  3. Check what 20261010000000_seed_es_ie_immigration_corpus_docs.sql already landed
  4. Confirm how requirements_builder resolves applies_to_nationality_classes_json
  5. Propose corpus/es_ie_corridor.json — post the STRUCTURE and the requirement list
     (keys + one-line descriptions), not the full text. STOP for approval.

=== PHASE 3 — IMPLEMENT (after approval) ===
  - Author corpus/es_ie_corridor.json, then GENERATE the migration with
    backend/scripts/ingest_corridor_corpus.py. Do not hand-write the SQL.
  - Mark content REPRESENTATIVE, not SME-verified. Keep the existing disclaimer and provenance
    flags. scripts/check_compliance_claims.py must pass — none of this may become a
    compliance claim.
  - last_verified_date = 2026-08-13. Every row needs a source URL.

=== ACCEPTANCE ===
  1. ES→IE returns ≥6 requirements for nationality=ES and ≥8 for nationality=IN, at
     PERMANENT, LTA and STA
  2. nationality_class is EU_EEA vs THIRD_COUNTRY and THE TWO LISTS DIFFER
  3. EU branch contains NO permit, NO visa, NO residence-registration requirement
  4. THIRD_COUNTRY branch contains CSEP, long-stay D visa, IRP-within-90-days
  5. Both branches contain PPSN, Revenue job registration, PRSI, bank account, housing
  6. Every requirement has a non-empty source
  7. python3 scripts/check_compliance_claims.py passes
  8. No existing corridor's requirement count changes

VERIFY: node -e "fetch('https://api.relopass.com/api/public/corridor-requirements?from=ES&to=IE&employee_type=PERMANENT&purpose=employment&nationality=IN').then(r=>r.json()).then(j=>console.log(j.nationality_class, j.requirements.length))"

Commit on branch feat/t18-02-es-ie-requirements. Do not merge.
```

---

# Prompt 5 — T18-06: give Ireland a real settle-in pack

```
TASK: T18-06. The Ireland country resource pack is 12 placeholder sections, and its one
populated section is factually wrong for both nationalities.

=== VERIFIED EVIDENCE (prod, 2026-08-13) ===
GET /api/resources/country for an IE/Dublin case returns 12 sections. The profile block is
CORRECT (destination_country:"IE", destination_city:"Dublin") and recommendedTags are sensible
(registration, schooling, healthcare, bank_account, neighborhood) — so ROUTING WORKS. Only the
content is missing:

  housing        -> "Rental market information will appear here."   neighborhoods: []
  schools        -> school_types ["Public","International","Private"]
  healthcare     -> "Healthcare system and registration."  emergency: "112"
  cost_of_living -> Average rent "—", Transport pass "—", Groceries "—"
  community      -> groups: []      culture_leisure -> events: []
  welcome        -> "Punctuality is valued", "Formal communication initially"
  events: []     recommended: []

AND THE ONE POPULATED SECTION IS WRONG:
  admin_essentials -> "Residence registration — Within 7-14 days"
    EU/EEA citizens: Ireland requires NO residence registration at all.
    Non-EEA: IRP within 90 DAYS, at Burgh Quay, €300, Stamp 1.
  Wrong for both branches.

=== WHERE THIS LIVES ===
  backend/app/services/country_resources.py
    line 8        RESOURCE_SECTIONS — the 12 section keys
    line 24       the section titles map
    line 76       build_profile_context(draft)
    line 114      get_personalization_hints(profile)
    line 153      get_default_section_content(country_code, city, section_key)  <-- THE FUNCTION
                  Docstring: "Return default section content when DB has none. Curated per country."
                  Exactly three countries are curated:
                    line 158-159  # Norway-specific content    if c == "NO":
                    line 261-262  # Singapore-specific content if c == "SG":
                    line 365      if c == "US":
                    line 466      # Generic defaults           <-- IE falls through to here
                  The generic block is what Ireland currently receives:
                    470  "cultural_tips": ["Punctuality is valued", ...]
                    473  "admin_essentials": {...}   <-- the wrong 7-14 days
                    483  "overview": "Rental market information will appear here."

    USE THE NORWAY BLOCK (158-260) AS THE TEMPLATE. It is the strongest of the three: real
    timelines AND real links, e.g.
      {"title": "Residence registration (Folkeregisteret)", "timeline": "Within 7 days",
       "link": "https://www.skatteetaten.no/en/person/national-registry/"}
    Note it also proves the shape supports a per-country link — the generic block passes
    link: None for every topic, which is half of why Ireland's pack is useless.

  Seed pattern for reference: scripts/seed_additional_countries.py,
  scripts/seed_resources_oslo.py, scripts/generate_country_resources_seed.py

=== PHASE 1 — RECON, then APPROVAL GATE ===
  1. Read country_resources.py:153-500 in full. NO / SG / US are the three curated blocks;
     Norway is the template.
  2. Decide: does IE become a fourth `if c == "IE":` block, or does this move to seeded data?
     The function's own docstring says "when DB has none" — so a DB-seeded path may already
     exist and take precedence. Check that before adding a fourth hardcoded block. Either way,
     do NOT refactor the mechanism and add content in the same PR.
  3. IMPORTANT — is admin_essentials nationality-aware at all? It cannot be correct for
     Ireland otherwise, because the right answer differs completely by nationality. If the
     signature has no nationality parameter, say so and propose the smallest change that
     threads it through (this depends on T18-05 landing).
  STOP for approval before writing content.

=== CONTENT (sourced 2026-08-13; full citations in the T18 report) ===

admin_essentials — MUST branch by nationality:
  EU/EEA:  no registration step at all. Sequence is PPSN → Revenue job registration → bank.
  Non-EEA: IRP within 90 days, Burgh Quay only, €300, Stamp 1.
  Both:    PPSN (in-person appointment, signed offer + proof of address <3 months),
           Revenue myAccount job registration (employee's responsibility; week 5 = 40% + 8% USC).

housing — Daft.ie Rental Report Q1 2026:
  Dublin 1-bed €2,012 (+8.0% YoY), 2-bed €2,609 (+7.6%), 3-bed €3,304 (+9.1%)
  Sub-regions, 2-bed: South City €2,850 · City Centre €2,651 · South County €2,605 ·
                      North City €2,444 · North County €2,407 · West Dublin €2,332
  ⚠ The report gives Dublin 2-bed as BOTH €2,536 (county table) and €2,609 (apartment-size
    table) on different geographic bases. Never present a single figure without stating which.
  ⚠ The report publishes NO per-neighbourhood breakdown. Map named areas to their SUB-REGION
    band and label it as such. Do not invent per-postcode numbers.
  Neighbourhoods for a Grand Canal Dock commute: Grand Canal Dock/South Docklands (walkable,
  newest stock), Ringsend/Irishtown, Sandymount, Portobello/Rathmines, Ranelagh (own Luas
  Green Line stop), Stoneybatter/Smithfield, Drumcondra/Phibsborough (Luas Green Line),
  Blackrock/Dún Laoghaire.
  ⚠ DART station details were NOT verified in the T18 research — either verify them or omit.

  RENT RULES — Rent Pressure Zones were ABOLISHED 1 March 2026 (RTB), replaced by national
  rent control: one increase per year, 2% or CPI whichever is lower; apartments where
  construction began after 10 June 2025 follow CPI with no 2% cap; 6-year tenancy cycles with
  rent resettable to market at cycle end. Any RPZ-based content is five months stale.

transport — TFI Leap Card: 90-minute fare €2.00 (bus, Luas, DART/Commuter Zone 1);
  Express/Nitelink €2.40 and excluded; daily cap €6.00, weekly cap €24.00 across all operators.
  Roughly €100/month ceiling — which is the argument for the cheaper outer neighbourhoods.

healthcare — entitlement is RESIDENCY-based, not nationality-based. "Ordinarily resident" =
  living here a year or intending to. No medical card on a Google salary (limit €184/week
  single, €266.50 couple). No national GP registration system — you find a practice yourself
  and some are closed to new patients. GP €45–65, unregulated. €100 ED charge WITHOUT a GP
  referral, none with one. Public in-patient charges abolished 17 April 2023.

emergency — 112 works, but 999 is the number people in Ireland actually use. Show both.

cost_of_living — populate from the rent and transport figures above. Do not leave em-dashes.

=== CONSTRAINTS ===
  - Every factual claim carries a source URL and a verified date. Mark REPRESENTATIVE.
  - scripts/check_compliance_claims.py must pass.
  - Do NOT ship anything you cannot source. The T18 report has an explicit exception register
    of items that could not be confirmed (PPSN processing time, D-visa time from Spain, named
    newcomer-friendly banks, mobile providers, split-year tax treatment). Omit those or mark
    them as unconfirmed — do not fill them in.

=== ACCEPTANCE ===
  1. No section contains "will appear here", "Practical guidance for your relocation", or an
     em-dash placeholder value
  2. housing.neighborhoods has ≥6 named Dublin areas, each with its sub-region rent band and source
  3. cost_of_living carries real figures with cited source + date
  4. admin_essentials shows NO residence-registration step for an EEA national, and
     IRP-within-90-days for a third-country national
  5. Every factual claim has a source URL
  6. python3 scripts/check_compliance_claims.py passes
  7. The NO / SG / US blocks are byte-unchanged
  8. Every admin_essentials topic has a real `link`, not None (Norway's block is the bar)

VERIFY: node -e "fetch('https://api.relopass.com/api/resources/country?assignment_id='+A,{headers:{Authorization:'Bearer '+T}}).then(r=>r.json()).then(j=>console.log(JSON.stringify(j.sections,null,1)))"

Commit on branch feat/t18-06-ireland-resource-pack. Do not merge.
```

---

## After all five

```
Re-run the full campaign and diff against the 2026-08-13 baseline:

  node scripts/madrid_dublin_runner.mjs

Baseline to beat: 22 pass / 32 fail, 41% overall, RED.
Target after these five: Documents ≥75%, Journey 100%, Neighbourhood ≥60%, overall ≥70% AMBER.

Then re-check the remaining T18 tasks — several may resolve as a side effect:
  T18-04 (relocationBasics 500)  · T18-07 (employee immigration 404)
  T18-08 (Dublin housing/schools, geocode disabled) · T18-09 (advisors)
  T18-11 (silent-accept writes)
T18-10 (relocation agent role) is blocked on a product decision — leave it.
```

---

## Notes on what I deliberately did NOT put in these prompts

- **No fix for `profile_json.movePlan` Oslo→Singapore.** AIQ-1818 investigated it, recorded it as
  vestigial, and found the obvious backfill would be a DSAR defect (writing `profile_json.userId`
  into `relocation_cases.employee_id` would make an HR user's subject-access request return the
  cases they opened *about other people*). Prompt 1 says repoint the consumer instead.
- **No "the relocation plan is empty" task.** My first report called that a P0. It was my own
  payload-shape error — with the correct flat snake_case wizard draft the plan generates 5 phases
  and 16 tasks. AIQ-1004's fix is intact. That correction is why prompt 1 targets the read side.
- **No refactor of the three duplicated EU/EEA country sets.** There's a comment in
  `immigration_regime.py:84-94` recording that consolidation as already done deliberately; prompt 2
  says use `nationality_class.is_free_movement_national` rather than adding a fourth copy.
