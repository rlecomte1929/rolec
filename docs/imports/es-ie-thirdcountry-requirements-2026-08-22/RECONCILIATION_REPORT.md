# ES→IE third-country batch — topic_key reconciliation report (CT-3)

**Batch:** `es-ie-thirdcountry-requirements-2026-08-22` — 38 facts / 6 entities, `status='new'`
in `otto_staging` on prod (`nsvefcvpvwwwhuqyuqmp`).
**Date:** 2026-08-22 · **Mode:** READ-ONLY (SELECT only; nothing applied, nothing promoted).
**Purpose:** decision aid for the promotion gate. Romain decides the mapping.

---

## 0. Read this first — the reconciliation key is NOT `topic_key`

The task frames this as a `topic_key` reconciliation. `topic_key` is **not** what promotion
dedupes on, so reconciling it alone would not prevent a single duplicate.

`backend/imports/otto/executor.py::promote()` writes `public.requirement_items` through
`crud.create_requirement_item`, which upserts on the natural key
**`(country_code, purpose, title)`**, with the row id derived as uuid5 over that key. And in
`backend/imports/otto/mappings.py::resolve()`, **`title = entity.title` verbatim**.

Three consequences that drive every recommendation below:

1. **`promote()` never reads `requirement_entities` / `requirement_facts` at all.** It reads
   `otto_staging` and writes `requirement_items`. Those two structured tables are a *parallel*
   store, not an upstream of serving. A "MERGE-INTO `<live_key>`" instruction aimed at
   `requirement_entities` would therefore change nothing about what a reader sees.
2. **The collision that matters is the title string.** I checked all six staged titles against
   live `IRELAND`/`employment` titles: **0 collide.** So promoting as-staged creates **6 brand-new
   served rows** alongside the 42 IRELAND rows already there — content-duplicating several of
   them while colliding with none. `dup_existing_live=0` from CT-1 is confirmed as a vocabulary
   artifact, exactly as suspected.
3. **All six will resolve — none will be refused.** Every fact carries
   `applies_to.nationality='non-EEA'` (→ `THIRD_COUNTRY`) and `applies_to.status='professional'`
   (→ `purpose='employment'`), consistently within each topic. There is no `Unmapped` safety net
   here; promotion would go through.

**Pillar is forced, and it is wrong for three topics.** `mappings.py` reads the pillar off the
schema — `domain_area='immigration'` ⇒ `RESIDENCE`, always — and ignores `applies_to.pillar`.
Four staged topics carry *conflicting* pillars across their own facts, and the batch's own
intent is overridden:

| staged topic | pillar(s) in `applies_to` | promoted pillar | live convention for this concept |
|---|---|---|---|
| `taxation` | `TAX` (2), `RESIDENCE` (1) | RESIDENCE | **EMPLOYMENT** (live tax-residence rows) |
| `revenue_rpn_emergency_tax` | `EMPLOYMENT` (2), `RESIDENCE` (5) | RESIDENCE | **EMPLOYMENT** (live RPN/emergency-tax rows) |
| `ppsn` | `EMPLOYMENT` (1), `RESIDENCE` (4) | RESIDENCE | RESIDENCE (live PPS rows) — consistent |
| `health_entitlements` | `HEALTHCARE` (2), `RESIDENCE` (1) | RESIDENCE | RESIDENCE (live health rows) — consistent |
| `immigration_work_authorization` | `RESIDENCE` (9) | RESIDENCE | RESIDENCE — consistent |
| `isd_irp_registration` | `RESIDENCE` (11) | RESIDENCE | RESIDENCE — consistent |

Live serving already files Irish tax under `EMPLOYMENT` (e.g. *"Irish tax residence turns on 183
days…"*, *"The employer's RPN drives Income Tax, USC and PRSI deductions"*). Promoting the two
tax topics at `RESIDENCE` puts the same subject matter in two different pillars.

---

## 1. Decision table

Fact-level overlap is by real-world concept. **N** = no live equivalent found in either store.

| staged_topic | candidate live entity(ies) + keys — in `requirement_facts` (RF) AND `requirement_items` (RI) | recommendation | rationale | fact-level overlaps |
|---|---|---|---|---|
| `ES-IE:thirdcountry:immigration_work_authorization`<br>(9 facts) | **RF:** `csep` (15f), `csep_eligibility`, `csep_salary_threshold`, `csep-salary-threshold`, `csep_application_fee`, `csep-application-fee`, `csep-occupation-list`, `csep-to-stamp4`, `csep_residency_pathway`<br>**RI:** *Critical Skills Employment Permit — eligibility*; *Critical Skills Permit – application fee* (`verified`); *– occupation list*; *– salary threshold*; *Immigration permission – CSEP to Stamp 4*; *Ireland — csep no labour market needs test thresholds*; *Ireland — entry visa after permit timing*; *Work Permission Requirement for Non-EEA Workers* | **MERGE-INTO `csep`** (RF) / fold into the existing CSEP item family (RI) | Heaviest pre-existing coverage of any topic — 9 live RF entities and 8 live RI rows already describe CSEP. A 7th CSEP naming family would make the duplication materially worse. 5 of 9 facts restate live content; the 4 genuinely new ones are the value. | **DUP:** `csep_processing_fee_and_refund` ↔ *Critical Skills Permit – application fee* (**RI is `verification_status='verified'` — do not overwrite**); `csep_remuneration_thresholds` ↔ *– salary threshold* / `csep-salary-threshold`; `csep_stamp4_after_permit_no_support_letter` ↔ *Immigration permission – CSEP to Stamp 4* / `csep-to-stamp4`; `csep_no_labour_market_needs_test` ↔ *Ireland — csep no labour market needs test thresholds* / `gep-lmnt`; `entry_visa_follows_permit_if_visa_required` ↔ *Ireland — entry visa after permit timing*.<br>**PARTIAL:** `employment_permit_is_not_residence_permission` ↔ *Work Permission Requirement…* + `stamp1-irp-registration`.<br>**N:** `csep_nine_month_employer_lock`, `employer_50_percent_eea_workforce_rule`, `permit_application_12_week_lead_time` |
| `ES-IE:thirdcountry:isd_irp_registration`<br>(11 facts) | **RF:** `irp_registration` (11f, 10 approved), `stamp1-irp-registration` (1f)<br>**RI:** *Immigration permission – Stamp 1 / IRP registration*; *IRP / ISD Immigration Registration (non-EEA nationals)*; *IRP card — first-time registration timeline and fee* (`corpus_grounded`) | **MERGE-INTO `irp_registration`** (RF) / fold into *IRP / ISD Immigration Registration (non-EEA nationals)* (RI) | The non-EEA IRP item is already the right audience and is still `pending`, so merging costs no approved work. Largest new-detail yield in the batch (7 of 11 new). **⚠ Contains a factual conflict — see §1a.** | **DUP:** `irp_registration_fee_300` ↔ *IRP card — first-time registration timeline and fee*; `registration_appointment_biometrics_and_irp_card` ↔ `irp_registration` facts.<br>**CONFLICT:** `isd_registration_required_over_90_days` + `landing_stamp_90_day_registration_deadline` ↔ *IRP / ISD…* `timing`.<br>**N:** `booked_appointment_within_90_days_preserves_lawful_presence`, `burgh_quay_nationwide_registration_office`, `cannot_hold_residence_permits_in_two_eu_states`, `irp_absence_limit_90_days_rolling_year`, `leaving_state_before_registration_needs_new_entry_visa`, `registration_cannot_be_booked_before_arrival`, `employment_permit_registration_valid_12_months` |
| `ES-IE:thirdcountry:ppsn`<br>(5 facts) | **RF:** *(none — no PPSN entity exists)*<br>**RI:** *PPS Number — Application and Uses (non-EEA nationals)* (pending); *(EU/EEA nationals)* (pending); *PPSN (Personal Public Service Number) — application and emergency tax* (approved) | **MERGE-INTO *PPS Number — Application and Uses (non-EEA nationals)*** (RI). KEEP-AS-NEW in RF only if that store is being maintained. | Split-brain topic: **absent from `requirement_entities` entirely but served by three RI rows.** Proof that RF is not the serving upstream. Merge target is the non-EEA row — matching this batch's audience exactly. | **DUP (concept):** all 5 ↔ *PPS Number — Application and Uses (non-EEA)*; `no_ppsn_route_is_dsp_not_revenue` also ↔ *PPSN … and emergency tax*.<br>**N (detail):** `ppsn_mygovid_basic_account_prerequisite`, `ppsn_not_issued_at_appointment_posted_later`, `ppsn_requires_valid_reason_job_qualifies`, `ppsn_in_person_appointment_mandatory` |
| `ES-IE:thirdcountry:revenue_rpn_emergency_tax`<br>(7 facts) | **RF:** *(none)*<br>**RI:** *Register the job with Revenue through myAccount to avoid emergency tax* (approved, EMPLOYMENT); *The employer's RPN drives Income Tax, USC and PRSI deductions* (approved, EMPLOYMENT); *PPSN … and emergency tax* (approved) | **MERGE-INTO the EMPLOYMENT emergency-tax pair** (RI) — **and correct the pillar to EMPLOYMENT** | Two live approved rows already state the trigger and the RPN mechanism. What is new is the **rate mechanics** (40%, four-week band, week-5 cliff, 8% USC) — the part an employee actually feels. Promoting as-is duplicates the framing and buries the new detail under the wrong pillar. | **DUP:** `first_job_in_state_must_be_registered_by_employee` ↔ *Register the job with Revenue…*; `rpn_follows_first_job_registration` ↔ *The employer's RPN drives…*.<br>**N:** `emergency_tax_trigger_is_missing_rpn`, `emergency_tax_no_ppsn_all_pay_at_40_percent`, `emergency_tax_first_four_weeks_single_rate_band`, `emergency_tax_week_5_full_40_percent`, `emergency_usc_flat_8_percent` |
| `ES-IE:thirdcountry:taxation`<br>(3 facts) | **RF:** *(none)*<br>**RI:** *Irish tax residence turns on 183 days in a year, or 280 across two* (approved, EMPLOYMENT); *Split-year treatment can be requested for the year of arrival* (approved); *Irish Income Tax — Rates and Bands (non-EEA nationals)* (pending) | **KEEP-AS-NEW**, sibling to the live tax rows — **pillar EMPLOYMENT, not RESIDENCE** | Genuinely complementary, not duplicative. Live serves the **residence** test (183/280 days); this batch adds the **ordinary-residence + domicile** axes and what they do to worldwide-income exposure. Together they complete the triad; separately each is misleading. | **PARTIAL:** `irish_tax_status_has_three_independent_tests` ↔ *Irish tax residence turns on 183 days…* (this fact names the 183-day test as only one of three).<br>**N:** `non_resident_but_ordinarily_resident_and_domiciled`, `resident_and_domiciled_means_worldwide_income` |
| `ES-IE:thirdcountry:health_entitlements`<br>(3 facts) | **RF:** *(none)*<br>**RI:** *Public Health Entitlement — Ordinary Residence (non-EEA nationals)* (pending); *(EU/EEA nationals)* (pending) | **MERGE-INTO *Public Health Entitlement — Ordinary Residence (non-EEA nationals)*** (RI) | Same concept, same audience, same statutory test. The live row already carries the one-year ordinary-residence timing; this batch adds the **documentary** side (what HSE asks for, and that HSE may verify permission with ISD). | **DUP:** `health_entitlement_rests_on_ordinary_residence` ↔ *Public Health Entitlement — Ordinary Residence (non-EEA)*.<br>**N:** `health_ordinary_residence_accommodation_evidence`, `health_non_eea_immigration_permission_verified` ⚠ (`needs_review`: quote captured but never re-verified) |

### 1a. Factual conflict — resolve before promoting `isd_irp_registration`

Live served row *IRP / ISD Immigration Registration (non-EEA nationals)* carries
`timing = "within 90 days of ISD granting permission"`.

Two staged facts say the 90 days runs from a different event — the **landing stamp at the port
of entry / arrival in the State** (`landing_stamp_90_day_registration_deadline`,
`isd_registration_required_over_90_days`), sourced to `irishimmigration.ie`.

These are not the same clock and they can differ by weeks. One of the two is wrong. This is the
one item in the batch that is a **correctness** question rather than a naming question, and it
should be settled on the source page before either row is served. Note the live row is `pending`,
so nothing wrong is being served *today* from it.

### 1b. Correction to the task's worked example

The brief gives `isd_irp_registration → irp_registration / stamp1-irp-registration /
registration_process`. **`registration_process` is not an immigration topic** — live it is
*"Vehicle Registration Process & Deadline (Ireland)"*, part of the vehicle-import set, and it
holds **0 facts**. It should not be a merge candidate. The first two are correct.

---

## 2. Section A — pre-existing live naming duplicates, independent of this batch

These exist in live `IRELAND` data now and are worth cleaning whatever is decided about CT-1.

### A1. `requirement_entities` — underscore/hyphen and synonym pairs

| # | duplicate pair | facts / status | note |
|---|---|---|---|
| 1 | `csep_application_fee` ↔ `csep-application-fee` | 1 (rejected) ↔ 1 (pending) | Underscore vs hyphen, same concept. `csep_application_fee`'s **title is generic** — *"Employment Permit — application fees"* — on a CSEP-specific key. |
| 2 | `csep_salary_threshold` ↔ `csep-salary-threshold` | 1 (rejected) ↔ 1 (pending) | Underscore vs hyphen. One rejected, one pending — the same claim reviewed twice to opposite outcomes. |
| 3 | `gep_labour_market_test` ↔ `gep-lmnt` | 1 (pending) ↔ 1 (approved) | Synonym (spelled-out vs initialism). |
| 4 | `csep_residency_pathway` ↔ `csep-to-stamp4` | 1 (pending) ↔ 1 (pending) | Same CSEP→Stamp 4 pathway under two names. |
| 5 | `irp_registration` ↔ `stamp1-irp-registration` | 11 (10 appr.) ↔ 1 (pending) | The 11-fact entity is the real one; the singleton is a stub. |
| 6 | `csep` ↔ `csep_eligibility` ↔ `csep-occupation-list` ↔ `csep_salary_threshold`(+hyphen twin) | 15 / 1 / 1 / 1 | `csep` (15 facts) already covers eligibility, occupation list and salary; the singletons are attribute-shards of it. **Three naming conventions coexist**: bare `csep`, `csep_snake`, `csep-kebab`. |
| 7 | `gep` ↔ `gep-application-fee` ↔ `gep-salary-threshold` ↔ `gep-lmnt`/`gep_labour_market_test` | 14 / 1 / 1 / 1+1 | Same shard pattern as CSEP. |

### A2. `requirement_entities` — 8 empty vehicle entities whose facts are misfiled

`customs_duty`, `import_vat`, `lhd_rhd_legality`, `registration_process`, `registration_tax`,
`roadworthiness_inspection`, `transfer_of_residence_exemption`, `type_approval` — **all 0 facts.**

Their content is sitting under the generic entity `immigration` (*"IE immigration"*, 8 approved
facts), which holds `vrt-omsp-nox`, `ncts-inspection`, `tor-6mo-12mo`, `vat-23pct`,
`eu-coc-or-nsai`, `lhd-permitted-impractical`, `third-country-duty` — i.e. **seven vehicle-import
facts filed under a topic called "immigration"**, while eight purpose-built entities for exactly
those facts sit empty. This is a bigger misfiling than anything CT-1 introduces.

### A3. `requirement_items` — served-layer duplicates

- **Three IRP rows:** *Immigration permission – Stamp 1 / IRP registration* (approved) ·
  *IRP / ISD Immigration Registration (non-EEA nationals)* (pending) ·
  *IRP card — first-time registration timeline and fee* (approved, `corpus_grounded`).
- **Three PPSN rows:** the EU/EEA + non-EEA pair, **plus** *PPSN (Personal Public Service Number)
  — application and emergency tax* (approved), which straddles both audiences and also overlaps
  the emergency-tax rows.
- **Two naming families for CSEP:** *"Critical Skills Permit – …"* (en-dash, title-case) vs
  *"Ireland — csep …"* (em-dash, lowercased key fragment, e.g. *"Ireland — csep no labour market
  needs test thresholds"*). The second family reads like a machine-generated key, not a title —
  and since **title is the upsert key**, these families can never converge on one row.
- **Deliberate, NOT duplicates:** the EU/EEA ↔ non-EEA paired rows (PPS Number, PRSI, USC, Public
  Health, Irish Income Tax). That is the nationality split working as designed — leave them.

---

## 3. Section B — recommended canonical `topic_key` convention for IE

### Recommendation: **bare, snake_case, concept-scoped — NOT corridor-scoped.**

```
irp_registration            ✅   ES-IE:thirdcountry:isd_irp_registration      ❌
csep                        ✅   ES-IE:thirdcountry:immigration_work_auth…    ❌
ppsn                        ✅
revenue_emergency_tax       ✅
tax_residence               ✅
health_entitlement          ✅
```

**Why bare wins here — three reasons, in order of weight:**

1. **A destination requirement is not corridor-specific.** IRP registration is identical for a
   third-country professional arriving from Madrid, Mumbai or São Paulo. Corridor-scoping the key
   forces one entity per origin country and multiplies the same facts N times — the fan-out is
   the number of origins you ever support.
2. **Audience is already modelled elsewhere, correctly.** What actually varies is nationality
   class and status, and those live in `applies_to.nationality` / `.status` →
   `applies_to_nationality_classes_json` / `purpose`. Live serving already does this properly with
   its `(EU/EEA nationals)` ↔ `(non-EEA nationals)` pairs. Encoding `thirdcountry` in the
   *topic_key* duplicates that dimension in a second, uncoordinated place.
3. **It matches the existing majority.** Live IE is already predominantly bare snake_case
   (`irp_registration`, `csep`, `gep`, `join_family`, `long_term_residence`, `eu_treaty_rights`).
   Corridor-scoping would add a **fourth** convention to a table that already has three.

**Where the corridor belongs instead:** as data on the fact — `applies_to.corridor` (the batch
already carries `"ES->IE"` on all 38 rows) — never in the key.

### Migration implication

**The honest headline: for the served reader, this convention change is close to a no-op today,
because `topic_key` is not in `requirement_items` at all.** It is a hygiene fix to the
`requirement_entities`/`requirement_facts` store plus a discipline for future batches.

1. **Nothing to migrate in serving.** `requirement_items` has no `topic_key` column. Renaming
   entity keys cannot change a served row, break a citation, or move a case's requirements.
2. **Re-key CT-1 before promotion, not after.** Rewriting `entity_topic_key` in
   `otto_staging` is cheap while `status='new'`. **But note the dedupe_key is
   `dest|entity_topic_key|fact_key`** — re-keying changes all 38 dedupe keys, so a re-stage of
   the same file afterwards would insert 38 *new* rows rather than dedupe. Re-key by UPDATE in
   place, or re-stage from the file **once**, never both.
3. **Merging entity pairs in A1 requires re-pointing `requirement_facts.entity_id`**, then
   deleting the emptied entity — order matters (`entity_id` is `NOT NULL`). Facts carry their own
   `status`; a merge must not resurrect a `rejected` fact as `pending`, and pairs #1 and #2 each
   have one of each.
4. **The `verified` and `corpus_grounded` rows are the tripwire.** *Critical Skills Permit –
   application fee* is `verification_status='verified'`; *IRP card — first-time registration
   timeline and fee* is `corpus_grounded`. `crud.create_requirement_item` **rewrites**
   description, severity, owner and citations on the natural key. Any merge or promotion that
   lands on those titles overwrites reviewed work. `promote()` has a guard for this — do not
   route around it.
5. **Deciding the pillar is a prerequisite, not a follow-up.** Because `mappings.py` hardcodes
   `RESIDENCE` from `domain_area='immigration'`, promoting the tax topics at their correct
   `EMPLOYMENT` pillar is not reachable through `--promote` as the code stands. That is a code
   change (or a post-promotion correction), and it should be settled before promotion rather
   than left to be cleaned up in the served table.

---

## 4. Summary of recommendations

| staged topic | recommendation | new facts | duplicated | needs decision first |
|---|---|---|---|---|
| `immigration_work_authorization` | MERGE-INTO `csep` | 3 | 5 (+1 partial) | Don't overwrite the `verified` fee row |
| `isd_irp_registration` | MERGE-INTO `irp_registration` | 7 | 2 | **90-day clock conflict (§1a)** |
| `ppsn` | MERGE-INTO *PPS Number — … (non-EEA)* | 4 | 1 (concept: all 5) | — |
| `revenue_rpn_emergency_tax` | MERGE-INTO EMPLOYMENT emergency-tax pair | 5 | 2 | **Pillar → EMPLOYMENT** |
| `taxation` | KEEP-AS-NEW (sibling to live tax rows) | 2 | 1 partial | **Pillar → EMPLOYMENT** |
| `health_entitlements` | MERGE-INTO *Public Health Entitlement — … (non-EEA)* | 2 | 1 | 1 fact `needs_review` (unverified quote) |

**Totals: 23 of 38 facts are genuinely new; 11 duplicate live content; 3 partial; 1 conflicts.**

No topic is a clean KEEP-AS-NEW at entity level except `taxation`, and none should be promoted
as six standalone rows — which is exactly what `--promote` would do today, since 0 of 6 titles
collide with anything live.

---

*Read-only report. No INSERT/UPDATE/DELETE was issued; no promotion run; no code or migration
changed. Sources: `otto_staging.immigration_entities` / `immigration_fact_candidates`,
`public.requirement_entities` / `requirement_facts` / `requirement_items` on
`nsvefcvpvwwwhuqyuqmp`, and `backend/imports/otto/{executor,mappings,parsers}.py` at
`feat/enrich-curated-batches-non-obvious`.*
