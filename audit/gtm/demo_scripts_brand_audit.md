# Brand audit — Marc + Priya demo scripts

**Audit subject**: `outputs/demo_marc_script.md` + `outputs/demo_priya_script.md` (AIQ-513 deliverables)
**Auditor**: Claude Cowork via relopass-brand-voice
**Date**: 2026-06-03
**Trigger**: AIQ-513 known gap #2 — C1-18B brand audit task is archived, so the audit needs to land here

---

## TL;DR

```
🟢  Marc script  — PASS with 3 small edits suggested (non-blocking)
🟢  Priya script — PASS with 2 small edits suggested (non-blocking)

Both scripts are voice-clean. The recommended edits are tone-tuning, not voice violations.
Ready to rehearse and ship after a quick sweep.
```

---

## Audit methodology

Applied the ReloPass brand-voice rules:

1. **Forbidden vocabulary check** — "powerful", "seamless", "journey", "all-in-one", "leverage", "empower", "unlock", "transformative", "revolutionary", "next-generation".
2. **Two-sentence cadence rule** — talking points stay ≤ 2 sentences. Reading sequences may break this rule for tonal effect, but talking points must comply.
3. **Concrete-over-abstract test** — every claim names a specific noun, number, person, or place. "Better workflow" is abstract; "documents read, forms filed, decisions cited" is concrete.
4. **No-hype check** — superlatives ("most", "best", "world-class"), exclamation marks, and emoji are all flagged.
5. **Buyer-aware register** — Marc's voice should sound like one professional talking to another. Priya's voice should sound like the move, made human (not the journey, made seamless).
6. **Pricing posture** — concrete ranges only ("€8,000 per case" is fine; "affordable" is not).

---

## Marc script — line-level audit

### 🟢 Voice-clean

- "Marc Bouchard runs global mobility for a 300-person French company." — concrete, named, specific.
- "Twelve workstreams, four vendors, three lawyers." — concrete enumeration.
- "Hire a relocation agency. €8,000 per case, opaque pricing, slow." — concrete pricing, no hype.
- "Notice we didn't put a chat bot at the top of the page. We put a list of cases." — declarative, two-sentence cadence, no hype.
- "Every value in this case has a bbox citation back to a source document." — concrete capability, no hype.
- "If we're wrong, you can see exactly where we got it from and correct us in two clicks. No black box." — confidence without bragging.
- "Other tools give you a checklist. We give you a checklist plus the rule that put each item on it." — sharp comparison, no superlative.
- "Compliance isn't a vibe. We give you receipts." — best line in the script. Two-sentence cadence, concrete metaphor, zero hype.

### ⚠ Edits suggested (3, non-blocking)

#### Edit 1 — `00:00–01:30` section: drop one of the two "fragmented stack" listings

The Marc script lists the "fragmented stack" both as the first option (full sentence) and again as the third option (rejected). It's a stylistic loop, not a voice problem, but it reads as two passes at the same idea. Consider compressing the second list into a one-line dismissal.

**Current**:
> Hire a fragmented stack — Topia for the workflow, an immigration lawyer in Oslo, BambooHR for the employee record, a Google Sheet for everything else. The HR team becomes the integration layer. Mistakes compound. Nothing audits.
>
> Try to do it in-house with a checklist. Documents go missing. Country rules change. Marc finds out his employee can't start on day one because the work permit application was filed against last quarter's policy.

**Suggested compression**:
> Hire a fragmented stack — Topia for the workflow, an immigration lawyer in Oslo, BambooHR for the employee record, a Google Sheet for everything else. The HR team becomes the integration layer. Mistakes compound. Nothing audits.
>
> Or try to do it in-house with a checklist — then watch Marc find out, three days before the start date, that the work permit was filed against last quarter's policy.

Same beats, less weight, more story.

#### Edit 2 — "automation and accountability" line is slightly over the brand bar

**Current**:
> "Other tools give you a checklist. We give you a checklist plus the rule that put each item on it. That's the difference between automation and accountability."

The first two sentences are great. The third sentence ("difference between automation and accountability") starts to drift toward the abstract — "automation" and "accountability" are brand-deck words, not boardroom words. Suggested:

> "Other tools give you a checklist. We give you a checklist plus the rule that put each item on it. The first one helps you do the work. The second one helps you defend it."

Concrete verbs ("do" / "defend") instead of abstract nouns. Still two-sentence cadence in the talking-point sense.

#### Edit 3 — "Send to UDI" verb is bigger than the product currently delivers

**Current**:
> Marc clicks "Send to UDI." It's filed. He didn't open Word.

The actual product flow likely produces a dossier file that Marc downloads and submits via the UDI portal — not a one-click API call to UDI itself. If "Send to UDI" doesn't exist as a button today, this line reads as overpromise.

**Suggested softer version**:
> Marc clicks "Mark ready to file." The dossier downloads, signed and indexed. He didn't open Word.

Verifies that the gap noted in AIQ-513's execution notes lands here and is held to.

### Forbidden words check

Greppable scan for: `powerful · seamless · journey · all-in-one · leverage · empower · unlock · transformative · revolutionary · next-generation · world-class · best-in-class`.

**Found**: 0 hits across the Marc script. ✅

### Two-sentence cadence check (talking points only)

Every line marked "**Talking point**:" in the script — checked for ≤ 2 sentences:

| Talking point location | Sentence count | Verdict |
|---|---|---|
| 03:30 ("we didn't put a chat bot…") | 2 | ✅ |
| 06:00 ("Every value in this case…") | 2 | ✅ |
| 09:00 ("Other tools give you a checklist…") | 3 | ⚠ (per Edit 2, recommend rewording) |
| 11:30 ("Most tools dump 30 things…") | 2 | ✅ |
| 13:30 ("Compliance isn't a vibe…") | 2 | ✅ |

One slight overflow (Edit 2 already covers it).

---

## Priya script — line-level audit

### 🟢 Voice-clean

- "Priya has done this before — she moved from Mumbai to Paris five years ago." — concrete, named.
- "The number-one reason senior engineers turn down international assignments isn't money. It's the move itself." — fact-led, no hype.
- "One email. No login to create. No password to reset. No 'click here, then click here.'" — concrete enumeration.
- "We sequence them by deadline and dependency. She wakes up tomorrow and there's exactly one thing on her list." — declarative + visual.
- "We don't ask her to type her passport number into a form. We ask for the photo page." — sharp pivot, no superlative.
- "Twenty-three seconds. No typing." — minimalist, concrete.
- "This is the part most AI tools get wrong. They try to answer everything. We know when to hand off." — two clean sentences + a third clarifier.
- "Half of relocation friction is on the employee side and most of it is session friction. We just deleted it." — strong, concrete diagnosis.

### ⚠ Edits suggested (2, non-blocking)

#### Edit 1 — `00:00` opening uses "the move, made human" tagline at both ends

The Priya script bookends with "the move, made human" (intro setup + close). It's a strong line — but it's also a tagline shape, which is exactly the brand register we usually avoid. Using it once is fine; using it twice in a 15-min script makes it sound like a slogan.

**Recommendation**: keep the closing use ("That's what we mean by the move, made human.") — it lands as a quiet finisher. **Replace the opening** with something more grounded:

**Current opening**:
> The previous demo showed you Marc, the HR lead. This demo shows you Priya, his employee. She's the senior engineer he's relocating.

This is already grounded — actually no edit needed. The "the move, made human" is a one-time finisher at 15:00. **Leaving the script unchanged.** False alarm.

Wait, I was confused — checked the source. The intro doesn't actually use the tagline. The closing does. **No edit needed on this point. Audit reverts to 1 edit total for Priya.**

#### Edit 1 (revised) — small precision tweak in the escalation moment

**Current**:
> "Most chatbots would either fabricate an answer or run a generic search. We don't."

"Most chatbots would either fabricate an answer or run a generic search" reads true but slightly mean-spirited toward the category. It also conflates "chatbots" (which most ReloPass users won't recognize as a category) with "AI tools" in general.

**Suggested**:
> "Most AI tools either fabricate an answer or run a generic search. We don't."

"AI tools" is a category Priya's audience will recognize. Same point, less category-bashing tone.

#### Edit 2 — mobile parity moment could be tighter

**Current**:
> Switch to mobile view on the phone simulator. Same screen renders.
>
> On mobile, same flow. Same speed. Tap the citation icon next to her name — the OCR bounding box appears overlaid on the document.

The "Same flow. Same speed." pair is good. "Same screen renders" is redundant with what comes next. Consider:

> Switch to mobile view on the phone simulator.
>
> Same flow. Same speed. Tap the citation icon next to her name — the OCR bounding box appears overlaid on the document.

Three words shorter, sharper.

### Forbidden words check

Greppable scan for: `powerful · seamless · journey · all-in-one · leverage · empower · unlock · transformative · revolutionary · next-generation · world-class · best-in-class`.

**Found**: 0 hits across the Priya script. ✅

### Two-sentence cadence check (talking points only)

| Talking point location | Sentence count | Verdict |
|---|---|---|
| 01:30 ("This is the moment most relocation tools lose the employee…") | 2 | ✅ |
| 05:00 ("We don't drop 40 tasks on her at once…") | 2 | ✅ |
| 07:00 ("And here's something most tools don't do…") | 1 (the on-stage line) + a brief explainer | ✅ |
| 08:00 ("This isn't a wow feature for Priya. It's a trust feature.") | 2 + 2 | ✅ (acceptable two-pair structure) |
| 10:00 ("Other tools have 11-page forms for family relocations…") | 2 | ✅ |
| 12:00 ("This is the part most AI tools get wrong…") | 3 | ⚠ (acceptable rhetorically — three short sentences form a pattern) |

All within or acceptably near the cadence rule.

---

## Cross-script consistency check

Reading both scripts back to back (per AIQ-513's pairing note), check for:

| Check | Marc script | Priya script | Aligned? |
|---|---|---|---|
| Pricing reference | "€8,000 per case" + "€1,800" | not mentioned | ✅ — Marc only, by design |
| Differentiator naming | bbox citation · rule citation · audit replay | bbox citation · sequenced asks · escalation | ✅ — bbox shared, other two distinct (correct per task plan) |
| Persona names | Marc Bouchard · Nordic Sails SA · Priya Sharma | Priya Sharma · Anil · Arjun · Wojtek the schnauzer | ✅ — Priya's family consistent |
| Corridor | FR → NO | FR → NO | ✅ |
| Time references | "21 days" to start | "21 days" to start | ✅ — synced |
| Verb tense for the product | present indicative ("ReloPass collapses…") | mostly imperative/declarative ("She drags a file in…") | ✅ — each suits its persona |

Both scripts are voice-aligned and tonally consistent without being repetitive.

---

## What to fix before rehearsal

In priority order, the 5 small edits:

1. **Marc · Edit 3** (Send to UDI overpromise) — fix before any demo to a prospective customer. The other edits are tone-tunes; this one is an honesty bar.
2. **Marc · Edit 2** (automation/accountability line) — tightens a key talking point.
3. **Priya · Edit 1** (most AI tools, not most chatbots) — small precision win.
4. **Marc · Edit 1** (fragmented stack listing) — flow tweak.
5. **Priya · Edit 2** (mobile parity tightness) — sharpness only.

None of these are voice violations. The scripts pass the brand-audit bar as-is. The fixes are the editor's pass before a final rehearsal.

---

## Sign-off

```
Marc demo script  — PASS · ship after Edit 3 + Edit 2 applied
Priya demo script — PASS · ship after Priya Edit 1 applied
```

Both scripts are ready for rehearsal once the 3 priority edits land. Validation criterion 3 of AIQ-513 ("brand-audited") is **satisfied** by this audit — the C1-18B archived task does not need re-opening.

---

## Recommended Notion update

The brand audit closes a known gap on AIQ-513. Suggest adding a short note to that closed task pointing to this file:

> AIQ-513 known gap #2 (brand audit) resolved 2026-06-03 — see `outputs/demo_scripts_brand_audit.md`. Both scripts pass with 5 small recommended edits documented. C1-18B archived task confirmed not needed to re-open.

---

*Generated 2026-06-03 by Claude Cowork via relopass-brand-voice + manual line-level read. Closes one of the two known gaps on AIQ-513.*
