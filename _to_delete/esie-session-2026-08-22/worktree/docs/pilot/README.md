# P6-1 — Internal Pilot Prep Kit

**Notion:** AIQ-257 · [P6-1 · Internal pilot with 2–3 HR customers on real policy documents](https://app.notion.com/p/367887c64d4881209b3eca7ee60f662d)
**Author:** Claude Code (prep-kit generation)
**Date:** 2026-06-04
**Status:** Ready for Romain to execute the pilot

---

This directory holds the runnable artifacts for the Phase-6 internal pilot. It does **not** run the pilot — recruiting customers, signing the agreement, running the onboarding sessions, and collecting live feedback are human steps for Romain.

| File | What it is | Who uses it |
|---|---|---|
| [`P6-1_pilot_brief.md`](P6-1_pilot_brief.md) | The pilot's scope, participants, success criteria, timeline | Romain (internal) + shared summary for participants |
| [`P6-1_data_handling_agreement.md`](P6-1_data_handling_agreement.md) | Agreement each pilot company signs **before** uploading any document | Romain → pilot HR contact (counter-signed) |
| [`P6-1_feedback_form.md`](P6-1_feedback_form.md) | The structured post-pilot feedback form (Google-Form-ready content) | Pilot HR admins + test employees |
| [`P6-1_pilot_runbook.md`](P6-1_pilot_runbook.md) | The 3-week operational checklist: onboarding script, live-usage steps, bug-mirroring process | Romain (operator) |

## ⚠️ Two gates before you load *real customer* data

1. **External pen test.** P5-9 (the security review, AIQ-256) signed off the platform for **internal pilot with _synthetic_ data only**. Loading **real** policy documents from a real customer is still gated by an external pen test (Cure53 recommended — see `docs/security/P5-9_security_review_2026-05-22.md` §3). Decide consciously: run the pilot on synthetic/redacted data first, or commission the pen test before using real documents.
2. **Signed data-handling agreement.** No document is uploaded until the company counter-signs [`P6-1_data_handling_agreement.md`](P6-1_data_handling_agreement.md). This is a hard constraint from the task.

## Definition of done (from the task's Validation Criteria)

- [ ] At least **2 companies** complete the full flow: Policy Builder → document upload → HR review queue → publish → employee comparison dashboard → AI assistant (≥ 5 questions).
- [ ] Structured feedback form completed by **all** pilot HR admins.
- [ ] At least **3 concrete improvement items** identified and added to the AI Work Queue as new tasks.

The post-pilot summary report (issues found, iteration log, 3+ queue items) is authored *after* the pilot runs — a template stub lives at the end of the runbook.
