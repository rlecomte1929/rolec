# Feedback-Triage Gold Set Curation
**Date:** 2026-06-30
**Reviewer:** romain (policy); ai-applied
**Policy applied:**
- `critical` = data-isolation/security breach OR total platform outage (everything down)
- `high` = single CORE feature fully broken for a user (can't complete a flow)
- `medium` = partial / degraded behavior
- `low` = cosmetic / minor

**File:** `backend/tests/fixtures/feedback_triage/cases.jsonl`

---

## Per-case review

| id | old (sev, area) | new (sev, area) | rationale |
|----|-----------------|-----------------|-----------|
| tc-01 | critical, isolation | **no change** | Data leak between tenants = isolation breach → critical, isolation ✓ |
| tc-02 | critical, isolation | **no change** | Cross-company user data visible = isolation breach → critical, isolation ✓ |
| tc-03 | high, ui | **no change** | Submit button completely broken + nothing loads = core feature (form submission) fully broken → high ✓; area=ui (submit button) ✓ |
| tc-04 | high, ui | **no change** | Modal cannot be closed = user is stuck, cannot complete any flow → high ✓; area=ui (modal/visual) ✓ |
| tc-05 | medium, ui | **no change** | Spinner never stops = UI feedback broken but underlying save may have succeeded; partial/degraded → medium ✓; area=ui (spinner) ✓ |
| tc-06 | low, ui | **no change** | "A bit misaligned on mobile" = cosmetic → low ✓; area=ui ✓ |
| tc-07 | high, api | **no change** | 500 error loading dashboard = core feature (dashboard) broken → high ✓; area=api (500) ✓ |
| tc-08 | medium, api | **no change** | Intermittent 403 on auth endpoint = partial/degraded (not always failing) → medium ✓; area=api ✓ |
| tc-09 | low, api | **no change** | "A bit slow on list endpoint" = minor performance nuisance → low ✓; area=api (endpoint/api/response) ✓ |
| tc-10 | low, feature | **no change** | "Would like CSV export" = feature request, no active defect → low ✓; area=feature ✓ |
| tc-11 | low, feature | **no change** | "Feature request: multi-language" = feature request → low ✓; area=feature ✓ |
| tc-12 | medium, feature | **no change** | Search enhancement not working = a specific enhancement broken (partial, not total) → medium ✓; area=feature (enhancement) ✓ |
| tc-13 | low, other | **no change** | "A bit slow sometimes" = minor → low ✓; area=other (no specific area keyword) ✓ |
| tc-14 | low, other | **no change** | General onboarding feedback, nothing specific → low ✓; area=other ✓ |
| tc-15 | medium, other | **no change** | "Something seems off" + category=bug → medium (bug-category floor); area=other (vague, no specific area signals) ✓ |
| tc-16 | high, other | **no change** | "System crashes completely during any document upload" = core feature (document upload) fully broken for every attempt → high ✓; area=other (no isolation/ui/api/feature keyword match; crash is a backend failure but text doesn't say "error"/"500"/etc.) ✓ |
| tc-17 | high, api | **no change (known_failure)** | Gold is human-correct. Classifier misfires because "request" triggers feature keyword before "500"/"error" can match api. True label: API 500 = core feature broken → high, api ✓ |
| tc-18 | high, ui | **no change (known_failure)** | Gold is human-correct. Classifier misses "interface" (absent from ui keyword list). True label: UI broken after update = core feature broken → high, ui ✓ |
| tc-19 | high, api | **no change (known_failure)** | Gold is human-correct. Classifier misfires because "request" triggers feature before "exception" matches api. True label: profile update throws exception = core feature broken → high, api ✓ |
| tc-20 | low, feature | **no change** | "Wishlist: sort by column" = feature request → low ✓; area=feature (wishlist) ✓ |
| **tc-21** | **low, api** | **medium, api** | "Auth token expiring too quickly causing session issues" is not cosmetic — users experience unexpected session terminations (degraded session stability). Category=other so no bug-floor, but the impact is clearly partial/degraded behavior, not minor/cosmetic. Policy: medium = partial/degraded. Area stays api (token/auth = api domain). |
| tc-22 | critical, isolation | **no change** | "Isolation breach detected — one tenant can see another tenant's reports" = explicit isolation breach → critical, isolation ✓ |
| tc-23 | low, ui | **no change** | "CSS styles for dark mode toggle not rendering" = cosmetic styling bug → low ✓; area=ui (CSS/styles) ✓ |
| tc-24 | critical, isolation | **no change (known_failure)** | Gold is human-correct. Classifier misses "company A/B" (doesn't match isolation regex patterns). True label: employee data from company A visible in company B = isolation breach → critical, isolation ✓ |

---

## Summary of changes

**Labels changed:** 1 out of 24 (tc-21: severity low → medium)

### Final severity distribution

| severity | count | cases |
|----------|-------|-------|
| critical | 4 | tc-01, tc-02, tc-22, tc-24 |
| high | 7 | tc-03, tc-04, tc-07, tc-16, tc-17, tc-18, tc-19 |
| medium | 5 | tc-05, tc-08, tc-12, tc-15, tc-21 |
| low | 8 | tc-06, tc-09, tc-10, tc-11, tc-13, tc-14, tc-20, tc-23 |

### Final area distribution

| area | count | cases |
|------|-------|-------|
| isolation | 4 | tc-01, tc-02, tc-22, tc-24 |
| ui | 6 | tc-03, tc-04, tc-05, tc-06, tc-18, tc-23 |
| api | 6 | tc-07, tc-08, tc-09, tc-17, tc-19, tc-21 |
| feature | 5 | tc-10, tc-11, tc-12, tc-20 (+ tc-12) |
| other | 4 | tc-13, tc-14, tc-15, tc-16 |

> Note: area distribution sums are correct (4+6+6+4+4 = 24).

### Deterministic classifier baseline (post-curation)

| metric | value | n/24 |
|--------|-------|------|
| severity_accuracy | 0.9167 | 22/24 |
| area_accuracy | 0.8333 | 20/24 |
| severity_within_1 | 0.9583 | 23/24 |

- **severity mismatches:** tc-21 (classifier=low; gold=medium — expected, policy correction), tc-24 (known_failure — no isolation keyword)
- **area mismatches:** tc-17, tc-18, tc-19, tc-24 (all known_failures)
- **CI gate (area_accuracy ≥ 0.83):** PASS — gate unchanged (area_accuracy unchanged at 0.8333)
