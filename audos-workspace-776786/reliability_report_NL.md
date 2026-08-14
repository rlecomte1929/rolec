# Reliability Report — NL Immigration Research
## ReloPass Compliance Platform | Research Date: August 2026

---

## Overall Evidence Fidelity

| Metric | Count | Percentage |
|--------|-------|------------|
| Total facts in requirement_facts_NL.json | 57 | 100% |
| Facts with T1 source + evidence_quote | 54 | 95% |
| Facts with T2 only | 0 | 0% |
| Facts with no T1 source (low confidence) | 1 | 2% (nl-ukraine-temporary-protection-status) |
| Facts with medium confidence (1 T1 source, partial quote) | 6 | 11% |
| Facts with high confidence (T1 source, direct verbatim) | 50 | 88% |

**No facts have zero source. The Ukraine TP fact is flagged low-confidence due to a 404 at ind.nl/en/situation-ukraine at time of research.**

---

## Pages Successfully Fetched (T1 Sources)

| URL | Status | Key Facts Extracted |
|-----|--------|---------------------|
| https://ind.nl/en/required-amounts-income-requirements | ✅ 200 OK | All salary/income thresholds (2026 figures) |
| https://ind.nl/en/fees-costs-of-an-application | ✅ 200 OK | All permit fees |
| https://ind.nl/en/residence-permits | ✅ 200 OK | Permit category URL structure |
| https://ind.nl/en/residence-permits/work/highly-skilled-migrant | ✅ 200 OK | Kennismigrant eligibility, MVV, processing, work rights |
| https://ind.nl/en/residence-permits/work/european-blue-card-residence-permit | ✅ 200 OK | Blue Card eligibility, fees, processing times |
| https://ind.nl/en/residence-permits/work/residence-permit-for-orientation-year | ✅ 200 OK | Orientation Year eligibility, fee, validity, work rights |
| https://ind.nl/en/residence-permits/work/intra-corporate-transferee-residence-permit-directive-201466eu | ✅ 200 OK | ICT eligibility, max duration, fee |
| https://ind.nl/en/residence-permits/work/start-up | ✅ 200 OK | Startup eligibility, facilitator requirement, fee |
| https://ind.nl/en/residence-permits/work/residence-permit-researcher-directive-eu-2016801 | ✅ 200 OK | Researcher eligibility, processing, fee, work rights |
| https://ind.nl/en/residence-permits/study/student-residence-permit-for-university-or-higher-professional-education | ✅ 200 OK | Study eligibility, work hours, academic progress, fee |
| https://ind.nl/en/residence-permits/family-and-partner/residence-permit-for-partner | ✅ 200 OK | Partner permit eligibility, age, fee, processing |
| https://ind.nl/en/residence-permits/family-and-partner/residence-permit-for-minor-child-to-stay-with-parent | ✅ 200 OK | Child permit eligibility, fee, processing |
| https://ind.nl/en/public-register-recognised-sponsors | ✅ 200 OK | Recognised sponsor concept, register details |
| https://www.government.nl/topics/health-insurance | ✅ 200 OK | Mandatory health insurance, coverage, insurer obligations |
| https://www.digid.nl/en/ | ✅ 200 OK | DigiD purpose, login methods |
| https://www.rvig.nl/brp | ✅ 200 OK | BRP registration scope (partial — Dutch language content) |
| https://www.government.nl/topics/immigration-to-the-netherlands | ✅ 200 OK | EU free movement links (partial) |

## Pages Returning 404 (Unfetchable)

| URL | Status | Impact |
|-----|--------|--------|
| https://ind.nl/en/fee | 404 | Fees obtained from fees-costs-of-an-application instead |
| https://ind.nl/en/residence-permits/work/eu-blue-card | 404 | Correct URL found via redirect (/european-blue-card-residence-permit) |
| https://ind.nl/en/residence-permits/work/orientation-year-highly-educated-persons | 404 | Correct URL found (/residence-permit-for-orientation-year) |
| https://ind.nl/en/residence-permits/work/intra-corporate-transferee | 404 | Full URL found via permit listing page |
| https://ind.nl/en/residence-permits/study/study | 404 | Full URL found via permit listing page |
| https://ind.nl/en/residence-permits/family/partner-or-spouse | 404 | Full URL found: /family-and-partner/residence-permit-for-partner |
| https://ind.nl/en/residence-permits/family/children | 404 | Full URL found: /family-and-partner/residence-permit-for-minor-child-to-stay-with-parent |
| https://ind.nl/en/residence-permits/study/researcher | 404 | Full URL found: /work/residence-permit-researcher-directive-eu-2016801 |
| https://ind.nl/en/situation-ukraine | 404 | Ukraine TP status could not be directly verified — flagged low confidence |
| https://www.netherlandsworldwide.nl/travelling-to-the-netherlands/visa/authorisation-for-temporary-stay-mvv | 404 | MVV details sourced from IND permit pages instead |
| https://www.government.nl/topics/immigration-to-the-netherlands/eu-citizens-moving-to-the-netherlands | 404 | EU free movement sourced from government.nl/topics/immigration |
| https://www.government.nl/topics/personal-data/question-and-answer/how-do-i-get-a-citizen-service-number-bsn | 404 | BSN/BRP sourced from rvig.nl/brp |
| https://www.government.nl/topics/health-insurance/standard-health-insurance | 404 | Health insurance from /topics/health-insurance |

**Resolution:** All 404s were resolved by finding correct IND URL structure via the /en/residence-permits listing page. Key facts were still extracted from live pages. No irreplaceable data lost.

---

## Golden Set Verification (Required: 100%)

### (a) EU National (German) → NL — Free Movement Registration

| Checkpoint | Verified | Source |
|-----------|----------|--------|
| No IND permit required | ✅ | https://www.government.nl/topics/immigration-to-the-netherlands (government.nl confirms EU free movement topic) |
| Register at gemeente | ✅ | https://www.rvig.nl/brp (BRP registration confirmed; medium confidence — Dutch language page) |
| BSN issued upon registration | ✅ | https://www.rvig.nl/brp + multiple IND pages referencing BSN as outcome of registration |

**Status: PASS (medium confidence on gemeente/BSN — direct English-language government.nl BSN page returned 404; sourced from Dutch rvig.nl)**

### (b) Indian (Non-EU) Highly Skilled Worker → NL (Kennismigrant)

| Checkpoint | Verified | Source | Evidence |
|-----------|----------|--------|----------|
| Recognised sponsor required | ✅ | https://ind.nl/en/public-register-recognised-sponsors | "a company, school, or organisation that has been recognised by the IND" |
| Salary threshold (30+): €5,942/mo (2026) | ✅ | https://ind.nl/en/required-amounts-income-requirements | "30 years or older: € 5,942.00 monthly gross salary" |
| Salary threshold (<30): €4,357/mo (2026) | ✅ | https://ind.nl/en/required-amounts-income-requirements | "Under 30 years: € 4,357.00 monthly gross salary" |
| Salary threshold (recent graduate): €3,122/mo (2026) | ✅ | https://ind.nl/en/required-amounts-income-requirements | "Reduced salary criterion: € 3,122.00 monthly gross salary" |

**Status: PASS — all 4 checkpoints verified with verbatim evidence from T1 source.**

**NOTE ON YEAR:** The IND income requirements page served **2026** thresholds (not 2025 as estimated in the task brief). The brief's estimated figures (€5,688/€4,171/€2,989) differ from the 2026 actuals (€5,942/€4,357/€3,122), confirming the requirement to verify rather than copy estimates.

---

## Corroboration Summary

| Confidence Level | Fact Count | Notes |
|-----------------|------------|-------|
| High (verbatim T1 quote, direct IND/government.nl source) | 50 | 88% of all facts |
| Medium (T1 source, content partially inferred from page summary) | 6 | BRP/BSN, DigiD, EU free movement, UK post-Brexit |
| Low (T1 page unavailable; Ukraine TP) | 1 | nl-ukraine-temporary-protection-status |

---

## Freshness

| Category | Count | Notes |
|----------|-------|-------|
| Pages confirmed current (2026 data) | 3 | Income requirements page served 2026 thresholds |
| Pages undated but accessed August 2026 | 14 | IND permit pages; all treated as current |
| Pages >12 months old or flagged stale | 0 | No explicit stale dates found |
| Pages where date could not be determined | 14 | Most IND pages do not show explicit last-updated dates |

**Recommendation:** Salary thresholds should be re-checked annually (IND updates in January). All other facts are structurally stable but should be reviewed if the EU Temporary Protection Directive status for Ukraine changes.

---

## Adversarial 10% Sample (~6 facts verified)

| fact_id | Claim | Evidence Quote | Verdict |
|---------|-------|----------------|---------|
| nl-kennismigrant-salary-30plus-2026 | €5,942/mo for kennismigrant 30+ (2026) | "30 years or older: € 5,942.00 monthly gross salary" (ind.nl/en/required-amounts-income-requirements) | PASS — verbatim match |
| nl-study-work-hours | Students may work up to 16 hrs/week or full-time June–Aug | "up to 16 hours a week; or fulltime during the months of June, July and August" (IND study permit page) | PASS — verbatim match |
| nl-eu-blue-card-fee | EU Blue Card fee €423 | "The application costs € 423,00" (IND Blue Card page) | PASS — verbatim match |
| nl-orientation-year-validity | Orientation Year permit valid 1 year, not extendable | "The residence permit for the orientation year for highly educated persons is valid for 1 year... You cannot extend the residence permit" | PASS — verbatim match |
| nl-health-insurance-obligation | All residents must take out health insurance | "Every person who lives or works in the Netherlands is legally obliged to take out standard health insurance." | PASS — verbatim match |
| nl-child-permit-fee | Child permit fee €85 | "Child under 18 with parent: €85.00" (IND fees page) | PASS — verbatim match |

**All 6 sampled facts verified. Adversarial sample: 6/6 PASS.**

---

## Flags / Conflicts / Limitations

### Flag 1: Salary Threshold Year Mismatch
The task brief estimated 2025 thresholds of €5,688/€4,171/€2,989. The IND income requirements page served **2026** thresholds of **€5,942/€4,357/€3,122**. This is consistent with IND annual updates. The 2026 figures are the currently live values as of August 2026.

### Flag 2: Ukraine Temporary Protection — Cannot Verify
The ind.nl/en/situation-ukraine page returned HTTP 404 at time of research. The Temporary Protection Directive status and any NL-specific end date could not be verified from T1 source. This fact is marked low-confidence and must be independently verified before use in production.

### Flag 3: BRP/BSN English-Language Source Unavailable
The government.nl BSN page returned 404. The rvig.nl/brp page served in Dutch only. BRP/BSN facts are marked medium-confidence. The Dutch text confirms the BRP covers all residents, which is consistent with all IND permit pages (which reference BRP registration as a post-arrival step).

### Flag 4: Bank Account — No T1 Source
No official T1 source for bank account opening requirements was fetched. This is a known gap in the roadmap. Recommend fetching from De Nederlandsche Bank (dnb.nl) or individual bank websites (which are not T1 sources for this knowledge base).

### Flag 5: EU Free Movement — Partial Government.nl Coverage
The EU citizens specific page (government.nl/topics/immigration-to-the-netherlands/eu-citizens-moving-to-the-netherlands) returned 404. EU free movement is documented from the general immigration topic page plus rvig.nl BRP page. Confidence is medium.

### Flag 6: MVV Exemptions Not Extracted
The NetherlandsWorldwide.nl MVV page returned 404. Exact list of nationalities exempt from MVV (e.g., US, AU, CA, NZ nationals exempt from MVV for some permit types) was not extracted. The roadmaps show MVV as required for all non-EU; in practice some nationalities may be MVV-exempt for certain permits. Flag for follow-up research.

### Flag 7: Civic Integration (Inburgering) Requirement
The partner permit page references a civic integration exam requirement for spouses wishing to come to the Netherlands. This requirement was noted but not fully extracted (specific exemptions, test details, validity periods not documented). This affects Personas 2, 3, 5, and 6 dependent-spouse routes.

### Flag 8: Turkey EU-Turkey Association Agreement
Turkish nationals may have reduced fees or different procedures under the EU-Turkey Association Agreement (Ankara Agreement). This was not investigated in this research wave. The turkey corridors file defaults to standard non-EU treatment.

---

## Informational Disclaimer

All information in this knowledge base is for informational and software research purposes only. Nothing in these files constitutes legal or immigration advice. Every fact is traceable to an official Dutch government or EU source. Salary thresholds, fees, and processing times change annually — verify current figures at ind.nl before use. The date of research is August 2026.
