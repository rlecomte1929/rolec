# `/test-drive` — page copy + survey

**For:** ReloPass corridor stress-test campaign · companion to `beta-test-campaign-spec.md`
**Voice:** ReloPass brand voice (infrastructure register; calm, precise, structured). Avoids "journey" per brand rules.
**Status:** Draft v1 · 2026-07-04 — ready to drop into a `testDriveContent.ts` file (mirrors the `GetStartedPage` pattern).

Copy uses tokens `{origin}`, `{destination}`, `{corridor}` so one page serves all five corridors. Tier-B corridors also render the early-coverage note (§ "Corridor label").

---

## 1. Hero

**Eyebrow:** `Beta test · {corridor}`

**Headline:** Run one relocation, end to end.

**Subhead:** You'll act as both the HR manager and the relocating employee on a single corridor — from case setup to the employee's roadmap. About 20 minutes, on sample data.

**Primary CTA (button):** Start the test

---

## 2. What we're testing

**Header:** What we're testing

**Body:** ReloPass is the coordination layer across HR, employees, and providers. This test checks one thing: does a case stay visible, compliant, and on-time from the first HR action to the employee's roadmap? Run it, and tell us where it holds and where it breaks.

---

## 3. How it works

**Header:** How it works

1. **Enter your first name.** We generate your HR and employee test accounts from it.
2. **Run the HR side.** Configure the case and hand it to the employee.
3. **Run the employee side.** Complete intake and reach the roadmap.
4. **Flag anything, anytime.** The feedback button stays with you the whole way.
5. **Mark it complete.** Answer five short questions and you're done.

---

## 4. About the data

**Header:** About the data

**Body:** Every account and case here is synthetic. Nothing you enter is personal data, and nothing connects to a live relocation. Use the sample details provided — there's nothing to protect, and nothing to clean up afterward.

---

## 5. Before you start (videos)

**Header:** Before you start

Three short clips. Watch them or skip them — the flow is self-explanatory either way.

- **Overview — 60 sec.** What ReloPass coordinates, and why relocation fails in the handoffs.
- **The HR side — 90 sec.** Configure a case and hand it off.
- **The employee side — 90 sec.** From intake to roadmap.

> _Production note:_ record as Looms; keep each under the stated length. Caption text above is the on-page label per clip.

---

## 6. Corridor label

**Standard (all corridors):**
> **Your corridor:** {origin} → {destination}

**Tier-B addendum (`GB_US`, `NL_SG`, `ES_AE` only):**
> This corridor is in early coverage. Expect gaps in the guidance — flagging them is exactly what we're testing.

---

## 7. Feedback reminder (persistent, near the widget)

**Header:** See something off?

**Body:** The feedback button sits bottom-right the whole time. Good or bad, one sentence is enough — attach a screenshot if it helps. Everything routes straight to Romain.

---

## 8. Start block

**Field label:** First name
**Placeholder:** e.g. Alex
**Helper:** We'll generate your HR and employee test accounts from this.

**Button:** Start the test

**Legal micro-line (under button):** Sample data only. No personal data is stored from this test.

---

## 9. In-flow completion CTA

**Button (persistent, appears once both sides are reachable):** I've completed my test

---

## 10. Completion page (survey intro)

**Header:** A few quick questions, then you're done.

**Body:** You've run both sides of a case. Tell us how it went — most of these are one tap. If you already left detailed feedback along the way, keep the written ones short.

---

# Survey

**Design note (not shown to tester):** Seven questions, but only three ask for typing and all of those are optional — the rest are a single tap. The three highest-value asks (testimonial, pilot interest, intro) sit at the **end**, where goodwill is highest. Every response is stamped with `corridor_id`, `tester_segment`, and `campaign`. The identity + contact fields are the **only** place real personal data is captured, and each carries its own consent.

**About you (lead-in):**
- Your name
- Your email — _for follow-up only._
- Company & role — _optional; helps me understand whose feedback this is._
- Sector / industry — _optional; e.g. energy, finance, tech._ (Company/role + sector are the tester-quality + beachhead signal for the results — see spec §3.)

**Q1 — Overall** _(one tap)_
> Overall, how did running this case feel?

Scale 1–5 (`1 = rough` → `5 = smooth`).

**Q2 — Friction** _(optional text)_
> Where did you get stuck, confused, or slowed down?

Helper: _Be specific — a step, a screen, a moment._

**Q3 — Problem fit** _(one tap + one line)_
> Does ReloPass address a problem you recognize?

Options: `Yes, clearly` · `Somewhat` · `Not really`
Follow-up (one line): _Why?_

**Q4 — One change** _(optional text)_
> If you could change one thing, what would it be?

---

_The next three are the ones that make this campaign worth running. Kept last, on purpose._

**Q5 — In your words (testimonial)**
> In one sentence, how would you describe ReloPass to someone in your field?

- Free text (one line).
- ☐ _You can quote me — with my name and company._

Helper: _If it landed, a sentence in your words is worth more than any pitch of mine._

**Q6 — Pilot interest (primary)**
> Would you or your company want to run a real pilot?

Options: `Yes — let's talk` · `Maybe, tell me more` · `Not now`
Optional note: _Anything that would make it a yes?_

Helper: _No pressure — even a "maybe" tells me who to keep close._

**Q7 — Intro**
> Who else runs or oversees relocations that I should speak with?

Fields (all optional, but prominent):
- Name
- Company / role
- How to reach them (email or LinkedIn)
- ☐ _You can mention I referred them._

Helper: _A pilot starts with one conversation. An intro to the right person is the most useful thing you can leave me with._

> **On submit:** Q7 creates a `prospect_candidates` row tagged `referred_by = {tester name/email}` + `corridor_id`; Q6 `Yes`/`Maybe` flags the tester's own row as a warm pilot lead; Q5-with-consent is stored as a quotable testimonial. All three feed the Admin dashboard (spec §6).

---

## Thank-you state

**Header:** Thanks — that's genuinely useful.

**Body:** I'll act on what you flagged. If you offered a pilot or an intro, expect a personal note from me shortly.

---

### Brand-voice notes
- Leaned on gold-standard patterns: _"Relocation fails in the handoffs"_ (§2), _"Structure how you run relocation. Start with one case."_ (hero register), _"Coordinate relocation across HR, employees, and providers."_ (§2 category line).
- **Avoided "journey"** throughout (brand-forbidden) — used _case_, _flow_, _both sides_, _roadmap_ instead. If you want to align the test-drive with in-product language that does say "journey," that's a deliberate override to make, not an oversight.
- Kept sentences short and declarative; every abstract claim anchored to a concrete step (case, handoff, intake, roadmap, corridor).
