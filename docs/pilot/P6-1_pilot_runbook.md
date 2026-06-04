# [P6-1] Pilot Runbook

**Date:** 2026-06-04
**Author:** Claude Code (prep-kit generation)
**Status:** Operational checklist — for the pilot operator (Romain)
**Notion:** AIQ-257

---

This is the step-by-step operating guide for running the 3-week pilot. Work it top to bottom per company. Boxes are meant to be checked off in a copy per participant.

## Pre-flight (before week 1)

- [ ] Confirm staging is healthy: `GET /health` on the staging API returns OK; staging frontend loads.
- [ ] Decide the **data posture**: redacted/synthetic (default, no pen test needed) **or** real customer data (requires P5-9 §3 pen test complete). Record the decision.
- [ ] Finalise participant list in the [pilot brief](P6-1_pilot_brief.md#participants) table (2–3 companies).
- [ ] Send the [data-handling agreement](P6-1_data_handling_agreement.md) to each HR contact; get it counter-signed.
- [ ] Build the [feedback form](P6-1_feedback_form.md) in Google Forms / Typeform; have the share links ready.
- [ ] Create a GitHub Issues label `pilot-p6-1` for bug tracking.

---

## Week 1 — Onboarding (per company)

- [ ] Agreement counter-signed and on file. **Do not proceed past this line without it.**
- [ ] Schedule + run the **30-minute guided session** (script below).
- [ ] HR admin uploads their **redacted** policy document via Policy Builder.
- [ ] AI extraction completes; HR admin sees extracted values for validation.
- [ ] Capture the first-impression: did extraction look right? (informal — the formal version is the week-3 form.)

### 30-minute onboarding session script

1. **(2 min) Frame it.** "This is a pre-launch pilot. We want you to break it and tell us what's annoying. Nothing you do here affects real employees — it's a staging sandbox."
2. **(3 min) Consent & data.** Confirm the agreement is signed; confirm the uploaded policy has employee PII removed.
3. **(8 min) Policy Builder walkthrough.** Screen-share. Upload the policy together. Let the AI extract. Narrate what the confidence scores mean.
4. **(7 min) HR review queue.** Walk through validating extracted values. Show high vs low confidence and the source citation. Let them accept/edit a few values themselves.
5. **(5 min) Publish + employee view.** Publish the policy. Switch to a test-employee account; show the comparison dashboard and the AI assistant. Ask one sample question together.
6. **(3 min) Their homework for week 2.** Validate + publish their policy; have 2–5 test employees use the dashboard and ask the assistant **≥ 5 questions each**. Tell them how to report bugs (email you, or you'll log them).
7. **(2 min) Close.** Confirm the week-3 feedback form is coming. Thank them.

---

## Week 2 — Live usage (per company)

- [ ] HR admin completes value validation and **publishes** the policy.
- [ ] 2–5 test employees use the **comparison dashboard**.
- [ ] 2–5 test employees ask the **AI assistant ≥ 5 questions each** — track counts (this is a pass criterion).
- [ ] Operator monitors: skim assistant transcripts / traces (P5-8 observability) for wrong or unsupported answers; note any for the bug log.
- [ ] Log every issue as a GitHub Issue with label `pilot-p6-1` and mirror to the AI Work Queue (process below).

### Full-flow completion checklist (the pass gate — needs ≥ 2 companies)

For each company, confirm the **entire** chain happened:

- [ ] Policy Builder used
- [ ] Document uploaded
- [ ] HR review queue worked through
- [ ] Policy published
- [ ] Employee comparison dashboard used
- [ ] AI assistant asked ≥ 5 questions

### Bug → queue mirroring process

1. File a **GitHub Issue**: title `[pilot-p6-1] <short symptom>`, label `pilot-p6-1`, body = steps to reproduce + which company + severity.
2. Mirror to the **AI Work Queue** (Notion, collection `75d7ed78-91f4-46b6-b805-12e43abbecce`): create a task, set Priority by severity, link the GitHub Issue in Context Links, set Status `Ready for AI` (or `Needs Decomposition` if large).
3. Tag the originating pilot in the task body (`Source: P6-1 pilot, Company X`).

---

## Week 3 — Feedback & iteration

- [ ] Send the [feedback form](P6-1_feedback_form.md) to **all** HR admins (required) + test employees (optional).
- [ ] Chase non-responders — the form completed by **every** HR admin is a pass criterion.
- [ ] Review + triage all `pilot-p6-1` GitHub Issues.
- [ ] Register at least **3 concrete improvement items** as new AI Work Queue tasks (drawn from form Q14/Q17 and the bug log).
- [ ] Write the [pilot summary report](#post-pilot-summary-report-template).
- [ ] Update Notion AIQ-257 → `Human Review` with the report linked, then hand to yourself for sign-off.

---

## Post-pilot summary report template

> Save as `docs/pilot/P6-1_pilot_summary_<date>.md` once the pilot completes.

```markdown
# [P6-1] Pilot Summary Report

**Date:** <YYYY-MM-DD>
**Companies:** <A, B[, C]>
**Data posture:** <redacted-synthetic | real (pen test ref)>

## Outcome vs success criteria
- Full flow completed by: <N> companies (need ≥ 2) — <PASS/FAIL>
- Feedback form completed by all HR admins: <yes/no> — <PASS/FAIL>
- ≥ 3 improvement items filed: <N> — <PASS/FAIL>

## Headline metrics
- Extraction acceptance rate (form Q3): <range>
- Confidence-score helpfulness (Q6): <avg/5>
- AI assistant accuracy (Q11): <avg/5>
- NPS (Q19): <score>
- Wrong/unsupported assistant answers reported: <count>

## Issues found
| # | Symptom | Type (bug / UX / data quality) | Severity | GitHub Issue | Queue task |
|---|---|---|---|---|---|
| 1 | | | | | |

## Iteration log (fixed during the pilot)
| # | What was fixed | Commit / PR |
|---|---|---|
| 1 | | |

## Improvement items registered (≥ 3, new queue tasks)
| # | Title | Priority | AI Work Queue ID |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

## Verdict
<GA-ready / iterate-then-GA / not-ready> — <one-paragraph rationale>
```
