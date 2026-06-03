# Priya Sharma Demo Script — Employee persona, 15 min, FR→NO corridor

**Task**: AIQ-513 · C1-18 · Priya script
**Persona**: Priya Sharma, Senior Engineer, French citizen relocating from Paris to Oslo with her husband and a 6-year-old
**Audience**: Design partners + YC office hours
**Duration target**: 15 min ± 2
**Source data**: C1-17 fixture corpus (Priya synthetic case)
**Differentiators called out**: bbox citation · escalation handoff · "we don't pretend"
**Date**: 2026-06-03
**Owner**: Romain (review + rehearsal) · GTM (deploy in conversations)

---

## Setup before the call

- Browser: a fresh incognito window. Not yet signed in.
- Email invite open in a second tab (the magic-link email that Pathway sends on case creation).
- Mobile mirror open on a phone or simulator so we can show the responsive behaviour at the right moment (around minute 7).
- Tone: human, warm. Marc's script is a CFO pitch. This one is for the head of HR's heart — what does my employee actually experience.

---

## Time-coded script

### 00:00 — 01:30 · The other side of the story

> **The previous demo showed you Marc, the HR lead. This demo shows you Priya, his employee. She's the senior engineer he's relocating.**
>
> Priya has done this before — she moved from Mumbai to Paris five years ago. She remembers what it was like: a 47-question PDF intake form, three different vendors emailing her at 11 p.m., and her HR team asking her to upload her passport four separate times.
>
> **The number-one reason senior engineers turn down international assignments isn't money. It's the move itself. ReloPass is built for that human, not for the workflow.**
>
> Let me show you what Priya gets.

---

### 01:30 — 03:00 · The first email

[Show the magic-link email in the second tab.]

> Priya gets one email. Subject: "Your relocation to Oslo — let's get started." Body: three sentences and a button.
>
> No login to create. No password to reset. No "click here, then click here." She clicks the button.

[Click. Pathway opens.]

> She lands on a welcome screen with her name. "Hi Priya. I'll help you get the documents your HR team needs."
>
> No marketing copy. No animations. No "let's get to know each other" survey. We start working.

**Talking point**:
> *"This is the moment most relocation tools lose the employee — they ask for 12 things before showing any value. We do the opposite: we show her exactly what we'll ask, why, and how long it'll take."*

[Show the next screen: "Quick question first — what's the purpose of your move?" with three large buttons: "New job", "Existing job, new country", "Returning home"]

> One question. Three buttons. The path forks here.

---

### 03:00 — 05:00 · ✦ DIFFERENTIATOR #1 · "we sequence the asks"

[Click "Existing job, new country." Next screen asks: "Where are you moving from and to?" with dropdowns.]

> Priya selects France → Norway. The next screen confirms: "France to Norway, starting January 6th, 2027. Right?"
>
> She confirms. Now the system knows everything it needs to plan her path: French citizen, EU mobility, Norway destination, January start, 21 days out.

[Show the path screen: a vertical timeline with 6 milestones. The first one — "Register your address" — has a green "next" pill.]

> Here's her path. Six milestones from today to her first day in Oslo. She can see the whole thing. **Importantly: she only has to act on one at a time.**

**Talking point**:
> *"We don't drop 40 tasks on her at once. We sequence them by deadline and dependency. She wakes up tomorrow and there's exactly one thing on her list."*

---

### 05:00 — 08:00 · ✦ DIFFERENTIATOR #2 · BBox citation, from Priya's side — "we don't make her type her own passport number"

[Click "Upload your passport's photo page."]

> First ask: passport. We don't ask her to type her passport number into a form. We ask for the photo page.

[Drop in the fixture passport PDF.]

> She drags a file in. Pathway shows a quick "Reading the document…" state — that takes about 1.5 seconds in the demo, comparable to live.

[Extraction completes. Show the "Is this you?" confirm screen with 4 fields: name, DOB, passport number, expiry.]

> Now she sees what we extracted. "Is this your name? Priya Sharma. Date of birth: 12 April 1989. Passport: P1234567. Expires: 15 March 2030."
>
> If anything's wrong, she taps the field and fixes it. If everything's right, one button: "Yes, that's right."

[Click "Yes."]

> Twenty-three seconds. No typing.

**Talking point** (cue the bbox citation):
> *"And here's something most tools don't do — Priya can also see exactly where we got that information from."*

[Switch to mobile view on the phone simulator. Same screen renders.]

> On mobile, same flow. Same speed. Tap the citation icon next to her name — the OCR bounding box appears overlaid on the document. She can verify we read her name correctly, character by character.

**Why this matters**: *"This isn't a wow feature for Priya. It's a trust feature. The first time she catches us reading something wrong, she tells the system. The next time, she trusts us by default. By document three, she's flying through."*

---

### 08:00 — 10:30 · The intake that doesn't ask three times

[Back to desktop. Show next milestone: "Tell us about your family."]

> Next milestone: family. Priya is moving with her husband Anil and their 6-year-old son Arjun.

[Show the family question with two large buttons: "Just me" and "With family."]

> Two buttons. She picks "With family." The next screen asks: "Who's coming with you?"

[Show the form: spouse / dependants. Add 1 spouse + 1 dependant.]

> Priya adds Anil and Arjun. We ask for two documents: her marriage certificate and Arjun's birth certificate. Same upload → OCR → confirm cycle.

[Show the two documents uploaded, extracted, confirmed.]

> **Now — this is the part that surprises every HR team I demo this to.** We've already got Priya's husband's name (from the marriage cert), her son's date of birth (from the birth cert), and we've already confirmed Priya's own data on the passport upload.
>
> When she gets to the Norwegian family-permit application, **we don't ask her any of these again**. She sees a pre-populated form, she scans it, she confirms.

**Talking point**:
> *"Other tools have 11-page forms for family relocations. We have a recognise-and-confirm flow. Same data, one-tenth the typing."*

---

### 10:30 — 12:30 · ✦ DIFFERENTIATOR #3 · "We don't pretend — escalation to HR done right"

[Show a screen where Priya types a question into a help box: "Can I bring my dog?"]

> Priya has a dog. Wojtek the schnauzer. She asks: "Can I bring my dog?"

[Show the response.]

> Most chatbots would either fabricate an answer or run a generic search. We don't. The reply is:
>
> **"Pet import to Norway has specific rules. I can't give you policy advice on this — I've flagged it for your HR contact Marc, who'll route it to the right person. You'll get an email when there's an answer. Typically: within one business day."**
>
> The question goes into Marc's queue with the case context attached. Priya sees a status: "With HR — typical response: within one business day."

**Talking point**:
> *"This is the part most AI tools get wrong. They try to answer everything. We know when to hand off — and the human on the other side has full context the moment they open the question."*

---

### 12:30 — 14:00 · The save-and-resume reality

> Priya's not going to do all this in one sitting. She has a job. She has Arjun's homework. Watch what happens when she closes the tab and comes back tomorrow.

[Close the browser tab. Re-open. Click the magic link again from the email.]

> Same magic link, same email. Pathway resumes exactly where she left off. "Welcome back, Priya. Picking up where you left off."
>
> No password. No re-upload. No "are you sure you want to lose your progress?" warning. She continues.

[Show the resumed screen.]

> Half of relocation friction is on the employee side and most of it is **session friction**. We just deleted it.

---

### 14:00 — 15:00 · The first-day moment

> Fast-forward 21 days. Priya lands in Oslo with Anil and Arjun. Wojtek is in cargo.
>
> She opens Pathway one more time. A new screen: **"Welcome to Oslo. Here's what to do this week."**
>
> Three items: register at the police station (D-number — booked for her on Wednesday), sign the apartment lease (the link is in her inbox), pick up the Norwegian tax card (instructions inline).
>
> She's not lost. She's not chasing four emails from four vendors. She has a list of three things. That's what we mean by **the move, made human**.

---

## Three rehearsal notes for the presenter

1. **The first 60 seconds set the tone.** Marc's demo opens on a problem. Priya's opens on a person. Don't rush. Let "she remembers what it was like" land.
2. **The escalation moment (10:30) is the most subtle of the three differentiators.** Slow down. Read the system response in full. Then say nothing for two beats. Let the audience absorb that we *refused* to answer.
3. **Don't oversell the mobile parity.** Show it briefly, say "same speed, same flow," move on. Anyone who's built mobile knows what it costs; the brevity itself is the proof.

---

## Differentiation moments — explicit checklist

- ✅ **bbox citation from Priya's side** (07:00–08:00) — same feature as Marc's demo, framed as a trust mechanic for the employee
- ✅ **sequenced asks** (05:00 + 08:00–10:30) — recognition + reuse, the "we don't ask twice" mechanic
- ✅ **escalation with full context** (10:30–12:30) — the "we don't pretend" moment, the AI's most adult feature

---

## Hand-off / what's deferred

This script is the **markdown draft**. Validation criteria #1 ("15 ± 2 min when read aloud") and #4 ("rehearsed against the live build") are intentionally deferred — both require a stopwatch + the running platform. Suggested follow-up:
1. Read aloud in front of a non-customer reviewer (criterion #4 of C1-18 itself).
2. Time the read — current word count is tuned for ~15 min at a calm conversational pace; verify against a clock.
3. Run `relopass-brand-audit` skill once final phrasing is locked.
4. Validate against the live build: confirm UI labels/buttons match what's actually in production (tabs, button copy, OCR confirm wording from `pathway_strings_v1.json`).
5. Note any UI references that drifted and update.

---

## Pairing notes (vs Marc script)

These scripts are designed to be **complementary, not redundant**. If both are watched back-to-back:

- Marc opens on **the buyer's pain** (€8,000 per case, compliance receipts).
- Priya opens on **the employee's experience** (the 47-question PDF, the four vendors at 11 p.m.).
- Marc closes on **the dossier filing** — the moment value is delivered to HR.
- Priya closes on **the arrival** — the moment value is delivered to the human.
- The bbox citation appears in both, framed differently each time (audit-grade proof vs trust mechanic).

Use Marc for HR/CHRO conversations and YC office hours. Use Priya for design-partner conversations where the room has a head of EX (employee experience) or a CPO who cares about adoption.

---

*Script generated 2026-06-03 by Claude Cowork via notion-task-executor. Voice tuned to ReloPass brand-voice rules — concrete, two-sentence cadence, no hype.*
