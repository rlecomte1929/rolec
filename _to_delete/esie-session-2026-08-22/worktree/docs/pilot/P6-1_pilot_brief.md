# [P6-1] Internal Pilot Brief

**Date:** 2026-06-04
**Author:** Claude Code (prep-kit generation)
**Status:** Draft — awaiting Romain's participant selection + go/no-go
**Notion:** AIQ-257

---

## Why this pilot

The pilot is the moment of truth: real HR administrators, real policy documents, real questions. Everything the platform was built for gets tested end-to-end before GA. The goal is **not** to prove the product works — it's to surface where it breaks, where users hesitate, and where the extracted data is wrong, so the final iteration is driven by evidence rather than assumption.

## Scope & guardrails

- **Environment:** Staging (`staging.relopass.com` / staging API) — **never production.**
- **Data:** Real policy documents with all **employee PII removed** before upload. (If a company cannot redact, use a synthetic/representative policy instead — see the data gate below.)
- **Data gate:** No document is uploaded until the company has counter-signed the [data-handling agreement](P6-1_data_handling_agreement.md).
- **Security gate:** Per P5-9 (AIQ-256), the platform is cleared for an internal pilot **on synthetic/redacted data**. Using a customer's *real, un-redacted* documents requires the external pen test (Cure53, see `docs/security/P5-9_security_review_2026-05-22.md` §3) to complete first. **Default recommendation: run round 1 on redacted/synthetic data.**
- **Onboarding:** Each pilot HR admin gets a **30-minute guided session** (script in the [runbook](P6-1_pilot_runbook.md)).
- **Bug logging:** Every issue is logged as a **GitHub Issue** and mirrored to the **AI Work Queue** in Notion.

## Participants

Recruit **2–3 companies**. For each, capture:

| Field | Company A | Company B | Company C (optional) |
|---|---|---|---|
| Company name | | | |
| HR admin contact (name, email) | | | |
| Test employees (2–5, names/emails) | | | |
| Origin → destination corridor(s) | | | |
| Policy document provided (title, redacted?) | | | |
| Data-handling agreement signed (date) | | | |
| Tier structure (single / multi-tier) | | | |

**Selection criteria** (pick companies that maximise signal):
- At least one with a **multi-tier** policy (Manager vs Executive) to exercise tier isolation.
- At least one **international corridor** that ReloPass already supports (so the comparison dashboard and AI assistant have real data to draw on).
- An HR contact who will actually engage for the full 3 weeks, not a one-time login.

## Success criteria

The pilot **passes** when all three hold (these mirror the Notion Validation Criteria):

1. **Full flow completed by ≥ 2 companies:** Policy Builder → document upload → HR review queue → publish → employee comparison dashboard → AI assistant with **≥ 5 questions asked**.
2. **Feedback captured:** the [structured feedback form](P6-1_feedback_form.md) is completed by **every** pilot HR admin (and ideally each test employee).
3. **Iteration backlog produced:** at least **3 concrete improvement items** are filed as new AI Work Queue tasks.

Secondary signals worth recording (not pass/fail):
- Extraction accuracy: % of AI-extracted policy values the HR admin accepted without edit.
- Trust: did HR admins trust the confidence scores and citations? (form Q2/Q3)
- Time-to-publish: wall-clock from upload to published policy.
- AI assistant faithfulness: any answer the HR admin flagged as wrong or unsupported.

## Timeline (3 weeks)

| Week | Focus | Key outputs |
|---|---|---|
| **1 — Onboarding** | Agreement signed · 30-min guided session · HR uploads (redacted) policy · AI extracts values for HR validation | Signed agreements; each company onboarded; first extraction reviewed |
| **2 — Live usage** | HR validates + publishes policy · 2–5 test employees use the comparison dashboard · 2–5 test employees ask the AI assistant ≥ 5 questions each | Published policies; employee usage logged; assistant transcripts captured |
| **3 — Feedback** | Feedback form sent to all participants · bug review & triage · iteration items registered in the Work Queue | Completed feedback forms; triaged bug list; ≥ 3 new queue tasks; [pilot summary report](P6-1_pilot_runbook.md#post-pilot-summary-report-template) |

## Roles

- **Pilot operator (Romain):** recruits companies, runs onboarding sessions, triages bugs, files queue items, authors the summary report.
- **Pilot HR admin (customer):** uploads policy, validates extracted values, publishes, completes the feedback form.
- **Test employees (customer):** use the comparison dashboard and AI assistant, optionally complete the feedback form.

## Out of scope for this pilot

- Production data or production environment.
- Real, un-redacted customer PII (gated by the pen test above).
- Paid/contractual commitments — this is an evaluation pilot, not a sale.
- New feature development during the pilot window (fixes only; enhancements become queue items).
