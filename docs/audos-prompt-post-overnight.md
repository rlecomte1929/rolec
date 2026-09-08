# Audos — URGENT stop + post-overnight corrections

**Date:** 2026-07-21 · Cowork has completed all DB verification and purged every QA artifact.
Good campaign — 18/18, zero crashes, and the route-guard batch (T15–T18) all passed, which is the first time that boundary has ever been tested.

**§0 is time-critical. Act on it before reading further.**

---

## 0. 🛑 CANCEL #85312 NOW — T13 is a FALSE POSITIVE

**Cancel Cursor job #85312 immediately.** It is about to commit a "fix" for a defect that does not exist, and the change would delete ReloPass's core positioning copy.

### What T13 actually flagged

The instruction I gave you was wrong. It asked for a bare string match on "compliant". The real rule is narrower — from `scripts/check_compliance_claims.py`, verbatim:

> **BANNED** in shipped, customer-facing copy: any claim of EU AI Act **status** — ready, compliant, certified, conformant — and any wording that classifies ReloPass itself as a high-risk AI system.
>
> **ALLOWED, and encouraged:** describing what the controls actually do.

The ban is on **EU AI Act status claims**. Not the word "compliant".

### The exact sentences #85312 would change

Verified against `origin/main`:

| File | Sentence |
|---|---|
| `whyReloPassContent.ts:102` | **"Every relocation case is visible, compliant, on-time."** ← a headline |
| `howItWorksContent.ts:42` | "Track progress to compliant close." |
| `whyReloPassContent.ts:44` | "Generic workflow tools aren't built for relocation complexity: corridors, compliance, multi-vendor coordination, document chains." |
| `whyReloPassContent.ts:65` | "Compliance — *without:* reconstructed after the fact · *with:* logged automatically throughout the case" |
| `platformContent.ts:71` | "Case portfolio, policy adherence, exception flags, compliance status, provider progress." |

**Not one mentions AI.** Every one refers to *relocation* compliance — immigration, policy adherence, audit trail. That is what the product sells. `CLAUDE.md` describes ReloPass as software that *"turns a cross-border corporate relocation into a guided, **compliant** journey."*

### Verified: the banned claim is not present

The only occurrences of "EU AI Act Ready / compliant / certified" anywhere in `frontend/src`, `frontend/public`, `docs/marketing` or `content/` are **code comments recording that those claims were removed** in AIQ-1513. CI passes. There is no defect.

### Actions

1. **Cancel #85312.** Do not let it commit.
2. **Revert #85299** — the Audos EmailGate patch. It applied the same false-positive change to a live surface and should be rolled back to the original wording.
3. **Discard #85304's mirror edits** in `imported-source/rolec-main/`.
4. **Close T13 as "no defect — false positive, instruction error."** No commit, no ticket, no follow-up.

### On your question about which surface visitors hit

It does not change the answer — **neither surface needs fixing**, and the EmailGate one needs un-fixing. Worth knowing for other reasons, but it is not a T13 input.

---

## 1. Your mirror-vs-GitHub finding is the most valuable thing in your report

You caught something important:

> "The repo's code lives in this workspace under `imported-source/rolec-main/`, and I made the wording changes there via the Audos bridge… editing the mirror ≠ pushing to GitHub."

**That is almost certainly why ~10 earlier repo tasks reported success with nothing landing** — Phase 0, Phase 1, the RFQ audit, and several others all reported "complete" while the repo never changed. Good catch, and it is worth turning into a standing rule:

> **A repo task is not complete without a commit SHA on a named branch.** Editing `imported-source/rolec-main/` is a no-op. Any task that cannot produce a SHA must report **BLOCKED**, never "complete".

Please add that to your durable notes. It will prevent the single most repeated failure of the last three days.

---

## 2. The RunF verification is already done — do not re-request it

Cowork ran it before purging:

```
campaign      qa-run003d      ✅
session_id    e7f46c55-8ca4…  ✅ non-null
corridor_id   FR_NO           ✅
```

**This was the best finding of your run.** It proves the survey persists correctly on the happy path, which narrows the P0 from "the survey files to the wrong campaign" to "…only when session context has been lost." So the P0 and P1 are a causal chain: the session-persistence bug is what pushes a tester onto the broken path. **Fix the P1 first.**

---

## 3. The video 404 is an artifact — your report contradicts itself

T12 records `hr.mp4 ✅ employee.mp4 ✅`. The P1 section of the same report says all three 404 on reload. Both cannot be true.

Cowork loaded `start.mp4` directly: Chrome rendered a native video player with controls, which only happens on a real video content-type. The files are genuine MP4s on `main` (982KB / 2.1MB / 3.4MB, correct `ftypisom` headers, no LFS). What you saw is a cancelled in-flight media request logged as a failure. **Drop it from the findings.**

---

## 4. Branch discipline — not `fix/td-qa-services-batch-0719`

That branch carries ~40 duplicate `docs: add stripe-relopass-package…` commits plus unrelated Stripe migrations. It is effectively unreviewable.

Your own reasoning — *"main already caught 2 stray commits"* — argues for a **clean feature branch off `main`**, not for piling onto a messy one. Use `fix/qa-run003-batch` off `main@518bf11c`, or one branch per fix. Commit via the **Git Trees API** as a single atomic commit — never one file per commit, which is what produced the 40 duplicates twice.

---

## 5. DB verification results — for your records

| Test | Result |
|---|---|
| **T7** segment=No | ✅ stored `tester_segment='internal'` |
| **T9** escaping | ✅ stored as literal `<script>alert(1)</script>` text, rendered escaped — correct end to end |
| All rows | ✅ correct `qa-night-*` campaign, real `session_id`, `corridor_id=FR_NO`. **Zero contamination** |

**T8 was actually run** despite being listed "not run" — a `qa-night-08` row exists. But the stored email was `not-an-email@probe.test`, a **valid** address format. The input was never invalid, so validation was never exercised. T8 remains unanswered.

**All artifacts purged** by Cowork: `qa-night-*`, `qa-run003c`, `qa-run003d`. Preserved: 5 `insead-2026` sessions, 9 survey responses, 320 real cases. Nothing needed from you.

---

## 6. What's left — one short session (~30 actions)

Independent edge cases. Provision fresh on each campaign and use the **in-page CTA** — do not navigate away (session loss is the known P1).

| ID | Test | Action | Expected |
|---|---|---|---|
| **T8** | Invalid email | Enter exactly `notanemail` — **no `@`, no domain** | Rejected with a validation message, **or** accepted. Either is a finding — report which |
| **T10** | Double submit | Answer the required segment question, click **Submit twice rapidly** | One response, no duplicate, no error |
| **T11** | Double completion | Click **I've completed my test** twice rapidly | No duplicate session-complete, no error |

Campaigns `qa-t8`, `qa-t10`, `qa-t11`. Report session labels + emails to Cowork for DB verification.

**Rules:** click custom controls by coordinate (ref-clicks silently fail) · decline the analytics banner first · never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · a blocked path is a finding, not something to route around.

---

## 7. Real and worth committing (already filed in the AI Work Queue)

1. **A16 — policy publish.** Your FAIL reproduction stands. Cowork saw it complete after 20–40s with a proper success banner, so the residual defect is **latency**, not a hang — but at 20 seconds a user concludes it failed and re-clicks, which is what caused the original 409. Same fix either way.
2. **Country-picker autocomplete.** Your 3× reproduction and root-cause (completion injected mid-keystroke) is in the ticket verbatim. Genuinely good find.
3. **P1 harness fixture** — staged provisioning (`stage=credentials|case_created|intake_complete|roadmap_ready`). Highest-leverage item on the testing side; it is what makes supplier exposure, the RFQ loop and the full journey testable at all.

These are repo code on the clean branch from §4 — and per §1, none of them is complete without a commit SHA.
