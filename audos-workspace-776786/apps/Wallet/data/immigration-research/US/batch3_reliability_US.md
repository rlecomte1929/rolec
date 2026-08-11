# Batch 3 Reliability Report — US Immigration Research
**Date:** 2026-08-11  
**Facts produced:** US-B3-001 through US-B3-011 (11 facts)  
**Researcher:** Claude (claude-sonnet-4-6), automated research pass

---

## 1. Gaps Closed vs. Remaining

| Gap | Target Fact(s) | Status | Confidence |
|-----|---------------|--------|------------|
| USCIS filing fees (G-1055 May 2026) | US-B3-001 to US-B3-005 | Closed (indirect) | MED–HIGH |
| J-2 EAD eligibility verbatim quote | US-B3-006 | Closed | HIGH |
| E-1/E-2 treaty country list (top 20) | US-B3-007 | Closed (indirect) | MED |
| Visa Bulletin Aug 2026 — EB priority dates | US-B3-008 to US-B3-010 | Closed | HIGH |
| El Salvador TPS watch (Sept 9, 2026 expiry) | US-B3-011 | Partial — active uncertainty | MED |

### Still Open / Needs Follow-Up
- **El Salvador TPS (US-B3-011):** No DHS Federal Register notice confirming extension or termination beyond September 9, 2026 found as of August 11, 2026. Statutory deadline missed (July 11, 2026). Recommend weekly monitoring of federalregister.gov for a new notice.
- **I-129 small-employer fee discrepancy (US-B3-001):** Sources conflict on whether the small-employer I-129 base fee is $390 or $460. The $780/$390 split is most consistent with 8 CFR 106.2 structure; $460 may be a legacy or pre-inflation-adjustment figure. Recommend direct G-1055 PDF verification when uscis.gov access improves.
- **I-539 fee discrepancy (US-B3-005):** Two source clusters: $370 online / $420 paper (majority), vs. $420 online / $470 paper (minority). Used majority figure. Verify via USCIS fee calculator.
- **E-1/E-2 Nigeria status (US-B3-007):** Some sources classify Nigeria as E-2 eligible, others as non-treaty. Classified as non-treaty pending direct T1 verification from travel.state.gov treaty list page.

---

## 2. Confidence Breakdown

| Confidence | Count | Facts |
|-----------|-------|-------|
| HIGH | 7 | US-B3-002, US-B3-003, US-B3-004, US-B3-006, US-B3-008, US-B3-009, US-B3-010 |
| MED | 4 | US-B3-001, US-B3-005, US-B3-007, US-B3-011 |
| LOW | 0 | — |

### Reason for MED Ratings
- **US-B3-001 (I-129):** Direct T1 page fetch blocked (HTTP 403); fee amounts sourced from multiple search-indexed secondary sources referencing G-1055 edition 05/29/26. Minor internal discrepancy in small-employer base fee ($390 vs. $460).
- **US-B3-005 (I-539):** Two conflicting source clusters on online vs. paper fee tiers. Majority sources support $370/$420; used majority figure.
- **US-B3-007 (E-1/E-2 treaty list):** Direct T1 fetch of travel.state.gov/treaty blocked (HTTP 403). Country list sourced from secondary site that explicitly cites State Dept as source and states "last verified April 2026." Nigeria classification uncertain.
- **US-B3-011 (El Salvador TPS):** Statutory decision deadline (July 11, 2026) reportedly missed but no official DHS Federal Register confirmation of what happens next has been published. Fact captures the uncertainty faithfully.

---

## 3. Source Access Issues

All five target T1 domains (uscis.gov, travel.state.gov, dhs.gov, ecfr.gov, federalregister.gov) returned HTTP 403 Forbidden for direct WebFetch. One govinfo.gov URL (Federal Register HTML) was accessible and returned verbatim content for the El Salvador TPS notice.

Research strategy used: WebSearch to locate cached/indexed content, then WebFetch of secondary law-firm and practitioner sites for verbatim quotes, cross-corroborated against 2+ independent sources for each fact.

---

## 4. Policy Updates Found

### El Salvador TPS — Active Monitoring Required
**Status as of August 11, 2026:**  
- Current designation valid through September 9, 2026 (per 90 FR 5953, Jan. 17, 2025).
- Statutory deadline for DHS to announce extension or termination: July 11, 2026.
- **DHS reportedly missed the July 11 deadline** — no Federal Register notice found as of August 11, 2026.
- Immigration practitioners (WHK Law Firm, writing in August 2026) report the missed deadline and suggest an automatic six-month extension (to ~March 2027) is likely, citing precedent from Lebanon TPS. However, **no official DHS confirmation has been published**.
- The Immigration Policy Tracking Project (immpolicytracking.org) has a live entry titled "DHS terminates TPS for El Salvador" which references the 2018 Trump-era attempted termination (blocked by courts). As of this research, there is no 2026 termination notice in the Federal Register.
- **Recommendation:** Check federalregister.gov weekly for a new El Salvador TPS Federal Register notice. If no notice appears by September 9, 2026, the legal status of Salvadoran TPS holders becomes uncertain and requires immediate escalation.

### EB-2 India — FY2026 Quota Exhausted
The August 2026 Visa Bulletin marks EB-2 India as "Unavailable" for the remainder of FY 2026 (fiscal year ends September 30, 2026). This is a notable development for Indian-national professionals on the EB-2 pathway. EB-1 India is also at risk of becoming unavailable before fiscal year end.

---

## 5. J-2 EAD Fix (US-B2-027 Upgrade)

Fact US-B2-027 (previously LOW confidence) has been superseded by US-B3-006 (HIGH confidence).

The upgrade is based on:
1. Verbatim regulatory text from 8 CFR 274a.12(c)(5) obtained from law.cornell.edu (eCFR mirror of official text): "An alien spouse or minor child of an exchange visitor (J-2) pursuant to § 214.2(j) of this chapter"
2. USCIS Policy Manual verbatim quote (Volume 2, Part D, Chapter 6): "J-2 nonimmigrants may be eligible for employment authorization; however, they may not use their income to support the J-1 nonimmigrant. To apply for employment authorization as a J-2 nonimmigrant, the dependent family member must file an Application for Employment Authorization (Form I-765). USCIS may authorize the employment for the length of the J-1 exchange visitor's stay or 4 years, whichever is shorter."

---

## 6. Visa Bulletin Key Findings (August 2026)

| Category | Country | Final Action Date |
|----------|---------|------------------|
| EB-1 | India | October 15, 2022 |
| EB-1 | China | July 1, 2023 |
| EB-1 | Philippines | Current |
| EB-2 | India | Unavailable |
| EB-2 | China | September 1, 2021 |
| EB-2 | Philippines | Current |
| EB-3 (Prof./Skilled) | India | January 1, 2014 |
| EB-3 (Prof./Skilled) | China | January 1, 2022 |
| EB-3 (Prof./Skilled) | Philippines | August 1, 2023 |
| EB-3 (Other Workers) | India | January 1, 2014 |
| EB-3 (Other Workers) | China | May 1, 2019 |
| EB-3 (Other Workers) | Philippines | December 1, 2021 |

USCIS is using the **Final Action Dates Chart** (not Dates for Filing) for employment-based adjustment of status in August 2026.
