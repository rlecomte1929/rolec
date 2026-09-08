# ReloPass Pilot — Structured Feedback Form

**Date:** 2026-06-04
**Author:** Claude Code (prep-kit generation)
**Notion:** AIQ-257 · P6-1
**Status:** Ready to transcribe into Google Forms / Typeform

---

This is the content for the post-pilot feedback form. Question types are annotated so it can be rebuilt 1:1 in Google Forms or Typeform. The four sections map directly to the topics named in the task brief. Send to **every pilot HR admin** (required for pass criteria); the employee-facing short version is at the end.

**Scale convention:** 1 = strongly disagree / very poor, 5 = strongly agree / excellent.

---

## Intro (form description)

> Thanks for piloting ReloPass. This takes about 8 minutes. Be blunt — the most useful answers are the critical ones. There are no wrong answers, and nothing here is graded. We're trying to find what's broken and what's worth keeping.

**Respondent details**
- Your name *(short text)*
- Company *(short text)*
- Your role in the pilot *(multiple choice: HR admin / Test employee / Both)*

---

## Section 1 — Policy Builder

*Goal: was the wizard intuitive, and did the extracted values look correct?*

1. The Policy Builder wizard was easy to follow. *(scale 1–5)*
2. The values the AI extracted from my policy document looked correct. *(scale 1–5)*
3. Roughly what share of the extracted values did you accept **without editing**? *(multiple choice: <25% / 25–50% / 50–75% / 75–90% / >90%)*
4. Where did you get stuck, confused, or have to redo a step? *(long text)*
5. If you edited an extracted value, what was wrong with it? *(long text — optional)*

---

## Section 2 — HR Review Queue

*Goal: was the confidence scoring helpful, and did you trust the extracted values?*

6. The confidence score on each extracted value was helpful. *(scale 1–5)*
7. I trusted the values the AI marked as **high confidence**. *(scale 1–5)*
8. The low-confidence / "expert review required" flags pointed me to the right things to check. *(scale 1–5)*
9. Did the source citation (the link back to the official source) help you trust a value? *(multiple choice: Yes, used it often / Yes, used it occasionally / Saw it, didn't use it / Didn't notice it)*
10. What would have made the review queue easier to trust or faster to clear? *(long text)*

---

## Section 3 — AI Assistant

*Goal: did the answers feel accurate, and did citations help you trust them?*

11. The AI assistant's answers felt accurate. *(scale 1–5)*
12. The citations under each answer helped me trust the response. *(scale 1–5)*
13. How many questions did you (or your test employees) ask the assistant? *(multiple choice: 0 / 1–4 / 5–10 / >10)*  *(pass criteria needs ≥ 5 per active employee — see runbook)*
14. Did the assistant ever give an answer you believed was **wrong or unsupported**? If yes, paste the question and what it got wrong. *(long text)*
15. Was there a question it **refused or failed** to answer that you expected it to handle? *(long text)*

---

## Section 4 — Overall

16. Overall, how valuable was ReloPass for your relocation policy work? *(scale 1–5)*
17. The **single most frustrating** thing in the pilot was… *(long text — required)*
18. The **single most valuable** thing in the pilot was… *(long text — required)*
19. How likely are you to recommend ReloPass to a peer in another company? *(scale 0–10, NPS)*
20. Anything else we should know? *(long text — optional)*

---

## Employee-facing short version (optional, for test employees)

Send to the 2–5 test employees per company. Keep it to 4 questions:

- E1. The relocation **comparison dashboard** was clear and useful. *(scale 1–5)*
- E2. The **AI assistant** answered my questions accurately. *(scale 1–5)*
- E3. How many questions did you ask the AI assistant? *(multiple choice: 0 / 1–4 / 5–10 / >10)*
- E4. What was confusing, missing, or wrong? *(long text)*

---

## How results feed the pass criteria

- **Q13 / E3** are the evidence for "AI assistant ≥ 5 questions" in the success criteria — capture them per active employee.
- **Q3** (acceptance rate) and **Q2/Q6/Q11** are the headline accuracy + trust metrics for the summary report.
- **Q14, Q17** are the richest source of bug/iteration items — every distinct issue here becomes a candidate AI Work Queue task (need ≥ 3).
- **Q19** (NPS) is the one-number GA-readiness signal.
