# Marc Bouchard Demo Script — HR persona, 15 min, FR→NO corridor

**Task**: AIQ-513 · C1-18 · Marc script
**Persona**: Marc Bouchard, Global Mobility Lead, mid-market French tech company relocating an engineer to Oslo
**Audience**: Design partners + YC office hours
**Duration target**: 15 min ± 2
**Source data**: C1-17 fixture corpus (Marc/Priya synthetic case)
**Differentiators called out**: bbox citation · audit replay · rule-citation depth
**Date**: 2026-06-03
**Owner**: Romain (review + rehearsal) · GTM (deploy in conversations)

---

## Setup before the call

- Browser: signed in at `https://relopass.com/hr/dashboard` as `hr_test@relopass.com`
- Company: "Nordic Sails SA" (fixture)
- Active case: "Priya Sharma — FR → NO — Senior Engineer"
- Tabs preloaded: `/hr/cases/priya-sharma` and `/admin/companies` (for the wow-moment cutaway)
- Tone: calm, low-key. We are not a hype deck. The product is the proof.

---

## Time-coded script

### 00:00 — 01:30 · The problem in 90 seconds

> **Marc Bouchard runs global mobility for a 300-person French company. He's about to relocate a senior engineer from Paris to Oslo. The visa, the work permit, the housing, the dependants, the payroll handover — twelve workstreams, four vendors, three lawyers, and one inbox that catches fire every Friday afternoon.**
>
> **The current options look like this:**
>
> Hire a relocation agency. €8,000 per case, opaque pricing, slow.
>
> Hire a fragmented stack — Topia for the workflow, an immigration lawyer in Oslo, BambooHR for the employee record, a Google Sheet for everything else. The HR team becomes the integration layer. Mistakes compound. Nothing audits.
>
> Try to do it in-house with a checklist. Documents go missing. Country rules change. Marc finds out his employee can't start on day one because the work permit application was filed against last quarter's policy.
>
> **ReloPass collapses that into one workspace. Watch.**

[Move to `/hr/dashboard`.]

---

### 01:30 — 03:30 · The HR Dashboard — what Marc opens on a Monday morning

[Show `/hr/dashboard`. Read off the case grid.]

> Marc opens the dashboard. He sees every active case at a glance. Three columns matter:
>
> **Stage** — where each case is in the journey. Visa filing, document collection, contract draft, arrival prep.
>
> **Blockers** — the cases that need him today. Red dot, top of the list.
>
> **Days to start** — countdown to the employee's first day at the destination.

[Hover over Priya Sharma row. Click in.]

> Priya Sharma is moving in 21 days. The blocker chip says "1 contradiction." That's what Marc clicks first.

**Talking point**: "Notice we didn't put a chat bot at the top of the page. We put a list of cases. HR doesn't need to summon information — they need it surfaced."

---

### 03:30 — 06:00 · ✦ DIFFERENTIATOR #1 · BBox citation — "show me where you got that"

[On Priya's case detail, click the contradictions tab. Open the active contradiction.]

> Here's what ReloPass found: Priya's passport says she was born **12 April 1989**. Her employment contract says **12 April 1990**.
>
> Marc could resolve this from his desk in 30 seconds — but only because of what we show him next.

[Click the citation icon on the left pane (the passport excerpt).]

> The OCR snippet pops out, with a bounding box drawn over the exact characters on the source document. Marc can see the digit "9" in the passport's MRZ band, and he can see it sitting cleanly on the photo page.
>
> **He's not trusting our AI. He's trusting the source document, and we're just pointing at it.**

[Close. Click the citation on the right pane (the contract).]

> Now look at the contract — and immediately you can see the typo: a "9" that the typist clearly hit instead of "8". The HR vendor in France made the mistake. Not Priya. Not the passport.

**Talking point**:
> *"Every value in this case has a bbox citation back to a source document. If we're wrong, you can see exactly where we got it from and correct us in two clicks. No black box."*

[Click "Keep passport value." Card collapses into a single resolved line.]

> Marc clicked once. The contract gets a correction note. The contradiction is closed. The HR vendor in France gets a flag to fix their template.

---

### 06:00 — 09:00 · ✦ DIFFERENTIATOR #2 · Rule-citation depth — "what does Norwegian law actually say?"

[Navigate to the Immigration tab on Priya's case.]

> Now Marc moves to the work permit. Priya's a Skilled Worker, EU citizen — she goes through Norway's UDI process.

[Show the milestone tracker: 6 steps, 2 done, 4 ahead.]

> ReloPass mapped Priya's path for her: register address, secure D-number, file UDI Skilled Worker application, employment-conditions form, tax card, A1 certificate from France.

[Click into "File UDI Skilled Worker application."]

> Here's where it gets interesting. Every requirement on this step cites the rule that produced it.

[Click the "Show citations" disclosure.]

> The minimum salary threshold isn't a number we typed in. It's pulled from **UDI Circular RS 2025-006 §3.2** — and we link directly to that section.
>
> The required documents list cites **Norway Foreign Nationals Act §23(1)(b)** — and we link there too.
>
> If Norway changes the threshold tomorrow, our rule scraper picks it up. Marc sees a new rule version, with the old version archived, the diff highlighted, and a clear "this affects 3 of your open cases" note.

**Talking point**:
> *"Other tools give you a checklist. We give you a checklist plus the rule that put each item on it. That's the difference between automation and accountability."*

---

### 09:00 — 11:30 · The document flow — Pathway from Priya's side, 90 seconds

[Cutaway: switch to a second tab on the same machine, signed in as `employee_test@relopass.com`.]

> Marc never has to type Priya's address. He doesn't chase her for her passport. He doesn't process her birth certificate himself.
>
> Priya gets a private workspace — we call it Pathway.

[Walk Pathway: welcome screen → corridor question → first ask "upload your passport" → file picker.]

> She sees three things at a time, max. "Hi Priya, I'll help you get the documents your HR team needs. Upload a clear photo or scan of your passport's photo page."

[Drop a fixture passport PDF in. Show the scanning → extracted → confirm screen.]

> ReloPass reads the document, extracts the fields, and shows her: "Is this your name? Priya Sharma." "Date of birth: 12 April 1989." Click yes. Done.
>
> If we get it wrong, she fixes it inline. If we're not sure, we ask. If something's a policy question — say, "can I bring my parents?" — we don't pretend to know. We hand it to Marc with a flag.

[Back to Marc's tab.]

> Marc sees what Priya uploaded. He sees what we extracted. He sees what she confirmed. He never has to chase a document.

**Talking point**:
> *"Most tools dump 30 things on the employee and tell them to come back tomorrow. We sequence the asks, we explain why, and we never ask twice."*

---

### 11:30 — 13:30 · ✦ DIFFERENTIATOR #3 · Audit replay — "show me how we got here"

[Click the "Audit" tab on Priya's case.]

> Marc's company gets audited. The auditor wants to know: who decided the salary on Priya's work-permit form?
>
> Marc opens the audit tab. There's the entry: **salary_eur · 78,000 · sourced from employment_contract.pdf, page 1, bbox (412, 209)–(498, 224) · extracted by gpt-4o on 2026-06-03 at 14:22 · confirmed by Priya at 14:23 · rendered into UDI form 2026-06-05 at 09:11**.

[Click the entry. Audit replay opens — a timeline view.]

> Every step is replayable. Marc can show the auditor the exact OCR result, the prompt that interpreted it, the model version, the cite to the underlying rule. He can prove the entire chain.
>
> **That's not a feature for HR. That's a feature for the legal team, the auditor, and any regulator that walks in.**

**Talking point**:
> *"Compliance isn't a vibe. We give you receipts."*

---

### 13:30 — 14:30 · Rendered output — the form Marc actually files

[Click "Dossier." Open the generated UDI Skilled Worker application PDF preview.]

> Marc opens the Dossier tab. ReloPass renders the UDI application — every field populated from the data we've extracted and Priya has confirmed.

[Scroll the rendered form.]

> Salary, employer reference, address in Oslo, Priya's signature block. Page 4: the supporting-doc index. Page 5: the employment-conditions attachment.
>
> Marc clicks "Send to UDI." It's filed. He didn't open Word.

---

### 14:30 — 15:00 · Close

> **The fragmented stack is €8,000 per case and a week of HR time. ReloPass is €1,800 per case, two hours of HR time, fully auditable, country-aware, and the employee actually likes it.**
>
> Three things to remember:
>
> 1. Every value is cited to its source — bbox or rule.
> 2. Every decision is replayable end to end.
> 3. The employee never feels like they're working two jobs.
>
> Happy to take questions, or to put your own case through.

---

## Three rehearsal notes for the presenter

1. **Don't apologize for the simplicity.** The dashboard is supposed to feel light. Resist the urge to explain why we *don't* have a chat interface on top.
2. **The bbox + rule citation moments are the demo's two punches.** Both must land cleanly — slow down for them, click deliberately, let the audience read the citation text on screen.
3. **The audit-replay moment is for the CFO/legal in the room, not the HR practitioner.** If you can read the room, watch eyes at minute 12.

---

## Differentiation moments — explicit checklist

- ✅ **bbox citation** (06:00–07:00) — passport vs contract dispute resolved on source evidence
- ✅ **rule-citation depth** (07:30–09:00) — UDI Circular RS 2025-006 §3.2 + Foreign Nationals Act §23
- ✅ **audit replay** (11:30–13:30) — full provenance chain on the salary value

---

## Hand-off / what's deferred

This script is the **markdown draft**. Validation criterion #4 ("rehearsed against the live build") is intentionally deferred — it requires the live platform plus a non-customer reviewer (criterion #4 of C1-18 itself). Suggested follow-up:
1. Rehearse once against staging in a Claude Code or in-person session.
2. Time the read-aloud — adjust pauses to hit 15:00 ± 2.
3. Run through `relopass-brand-audit` skill once final phrasing is locked.
4. Note any UI references that drifted (button labels, tab names) and update.

---

*Script generated 2026-06-03 by Claude Cowork via notion-task-executor. Voice tuned to ReloPass brand-voice rules (no hype, concrete, two-sentence cadence in talking points).*
