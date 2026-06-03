# Legal disclaimer copy — v0 draft (AIQ-680 / P1-06a)

> **Status: v0 DRAFT — not yet legally reviewed.**
> This copy is an AI-drafted starting point for the five in-product disclaimer
> touchpoints. It must be redlined and signed off by external immigration law
> counsel (tracked as P1-06c) before it ships. Do not treat any wording here as
> final or as legal advice.

## Purpose

ReloPass is an information and coordination tool, **not a law firm**, and gives
no legal or immigration advice. Each touchpoint below tells the user that in
plain language at the moment they could act on AI-generated guidance, so the
platform is not exposed to liability when someone relies on it.

## Constraints applied

- Plain language, not legalese.
- Each inline disclaimer is **≤ 3 sentences** (per P1-06 / P1-06a).
- Low-confidence steps get a **distinct** disclaimer with a "consult a lawyer" CTA.
- Onboarding requires **explicit acknowledgment** before any AI guidance is shown.
- Brand voice checks run: **#5 concreteness** (every disclaimer names a concrete
  anchor — your case, your employer, a form, an accredited lawyer) and **#6
  sentence discipline** (short, declarative, one idea per sentence). No "journey"
  or hype language.

---

## 1. Onboarding acknowledgment

*Placement: a required checkbox the user must tick before the first AI roadmap is
shown. Blocks progression until accepted.*

> ReloPass helps you organise your relocation, but it is not a law firm and does
> not give legal or immigration advice. The steps and forms it prepares are
> information to act on with your employer and, where a case needs it, an
> accredited professional. Tick to confirm you understand before you continue.

**Checkbox label:** "I understand ReloPass gives information, not legal advice."

---

## 2. Roadmap overview banner

*Placement: a persistent, dismissable banner at the top of the roadmap view.*

> This roadmap is generated from your case details to show what your relocation
> usually involves. It is a planning tool, not legal or immigration advice, and
> steps can change as your case progresses. Confirm anything official with your
> employer or an accredited immigration lawyer.

---

## 3. Low-confidence step (inline) — *distinct from the general disclaimer*

*Placement: inline on any step the engine flags as LOW confidence. Replaces, not
adds to, the general roadmap banner for that step.*

> ReloPass is less certain about this step, so treat it as a starting point
> rather than a final answer. The rules here vary by case and change often.
> Consult an accredited immigration lawyer — [find one in Service Providers].

**CTA:** "Consult an accredited immigration lawyer — [find one in Service Providers]"

---

## 4. Form pre-fill confirmation screen

*Placement: the confirmation screen shown before a user submits a form ReloPass
pre-filled.*

> ReloPass filled this form from the details on your case to save you time. Check
> that every field is correct and complete — you are responsible for what you
> submit. ReloPass does not file or certify documents on your behalf.

**Primary action label:** "I've checked these details — continue"

---

## 5. Human-Only step (inline)

*Placement: inline on any step marked Human Only (handled by a person, not by
ReloPass automation).*

> A person handles this step, not ReloPass automation. We flag it because it
> needs a human decision — usually your HR team or an accredited advisor.
> ReloPass tracks the step here but does not complete it for you.

---

## Notes for counsel (P1-06c redline)

1. Confirm "accredited immigration lawyer / professional" is the right term per
   jurisdiction (some corridors use "registered migration agent" or equivalent).
2. Confirm whether the onboarding acknowledgment must be logged with a timestamp
   for evidentiary purposes (likely yes — coordinate with the audit-trail work).
3. Confirm the low-confidence CTA can point users to Service Providers without
   ReloPass implying endorsement of any specific provider.
4. Decide whether a single full "Terms & disclaimer" page should be linked from
   each touchpoint (P1-06 calls for a dedicated full-disclaimer page).
