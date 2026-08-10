# ReloPass × Otto — campaign brief

**AIQ-1785 (ADS-5).** Draft for Romain to review and send to Audos.
**Do not send until the two gates at the bottom are cleared.**

> ## ⚠️ Channel changed: Meta first, ChatGPT second (decided 2026-08-10)
>
> This brief was written for ChatGPT ads. The channel decision has since changed, and
> three things below are now wrong. Fix them before sending.
>
> **Why the change.** The live Audos surface is Meta: both existing campaigns in the Ads
> app are Meta and sit at `PREVIEW_READY`, tonight's workspace agenda is a Meta plan, and
> Otto's launch path is `delegate_ad_generation` → approve previews →
> `launch_previewed_campaign`. ChatGPT Ads exists as a provider in the same app and stays
> as wave two, once Meta gives us a CPC baseline to compare against.
>
> **1 — `utm_source=chatgpt` is now wrong.** Every URL in
> `docs/gtm/ADS-4_destination_urls.md` carries it, and the reconciliation SQL filters on
> it. Change to `utm_source=meta` in both places, or the first campaign's data files
> itself under the wrong channel and the wave-two comparison is lost.
>
> **2 — the budget maths does not support the stated gates.** The wallet shows **$174** of
> ad credit. At the $3–4 CPC below that is ~45–58 clicks *total*, across eight angles —
> roughly six clicks each. That cannot carry a conversion test, and ADS-6's day-3/7/14
> gates should be re-scoped to a single day-7 qualitative read: which phrasings and problem
> framings earned clicks. Segment-level engagement is readable at this volume; cost-per-
> qualified-lead is not. Report it as what it is.
>
> **3 — 🔴 the geography rule and the actual campaign contradict each other, and only
> Romain can settle it.** This brief says *"US and UK only. No EU member state may be
> targeted."* The campaign Otto is primed to run targets **FR→NO HR generalists** — France
> is an EU member state.
>
> The rule's origin is ADS-1 question 4, which asks whether Otto can buy UK inventory *"or
> is it US-only"*. That reads as a **platform-capability** question about ChatGPT ads,
> which launched US-first — not as a ReloPass policy. If that is right, the rule does not
> transfer to Meta, where EU targeting is ordinary and where our actual first corridor
> lives. If instead it was a deliberate data-protection or ad-policy choice, it stands and
> the FR→NO campaign cannot run as planned.
>
> **Do not resolve this by inference.** State which it is, in writing, before spend.



---

## The trade

**ReloPass brings** the ICP, the offer, the copy, and the definition of a qualified lead.
**Otto brings** execution, iteration speed, and budget.

This split is deliberate. Otto's engine is tuned for consumer direct-response on social.
Handed a blank brief, its priors produce ads that convert nobody who can sign a contract.
Everything below is written to be used as-is.

**We are asking for card-level approval rights before anything runs.** Not a veto on
optimisation — approval on creative copy, because register is the whole risk here.

---

## Who we are targeting

**Segment A — the buyer.** HR, People Ops, and mobility leads at companies relocating
employees across borders. They already run relocations; they run them in spreadsheets,
email threads, and vendor portals that do not talk to each other. They can sign.

**Segment B — the signal.** Employees who are relocating. They cannot buy. They are worth
reaching because the one question we ask them — *"Who do you work for?"* — turns
non-buyer traffic into a live target-account list for outbound.

**Budget split: 60% Segment A / 40% Segment B.**
**Bidding: CPC, $3–4.**
**Geography: US and UK only.** No EU member state may be targeted.

---

## The 8 cards

Verbatim. Every title ≤40 characters and every body ≤100, re-measured independently —
counts below are actual, not intended.

### Segment A → `/mobility-teams`

| ID | Title (chars) | Body (chars) |
|---|---|---|
| **A1** | Relocation fails in the handoffs. (33) | Cases, documents, and providers on one record. Built for HR and mobility teams. (79) |
| **A2** | Relocation still runs on spreadsheets (37) | Move every case onto one record. Status, owners, and deadlines in one view. (75) |
| **A3** | Know which relocation is late, today (36) | Deadlines, documents, and provider tasks tracked against every case. (68) |
| **A4** | Vendor tasks tied to the case (29) | Not lost in inboxes. HR, employees, and providers coordinate on one record. (75) |
| **A5** | Every relocation case, one status view (38) | Track cases, documents, and vendor tasks without chasing inboxes. (65) |
| **A6** | Start with one relocation case (30) | Structure how you run relocation. See the system before you commit. (67) |

### Segment B → `/relocation-checklist`

| ID | Title (chars) | Body (chars) |
|---|---|---|
| **B1** | Moving for work? Know what's required (37) | A structured checklist of documents and deadlines for your relocation. (70) |
| **B2** | Your relocation, one clear checklist (36) | See required documents, deadlines, and who owns each step. Share it with HR. (76) |

**A1's title is also the live headline on `/mobility-teams`.** Ad and landing page say the
same thing in the same words — that continuity is the point, not a coincidence to optimise
away.

---

## Destination URLs

One per angle, in `docs/gtm/ADS-4_destination_urls.md`. Every URL carries
`utm_content=[angle]`, which is how we tell which angles to concentrate spend on at
Gate 2. **Please preserve query strings through any redirect** — UTMs stripped in transit
means no attribution at all, and it fails silently.

---

## Context hints

> ⚠️ **HOLE — not written here on purpose.**
> Both hints are drafted verbatim in **playbook §6**, which is not in the repo and I could
> not locate it in the workspace. Paste them in before sending; I have not invented them,
> because a context hint is what the model actually reads to decide who sees the ad, and
> a plausible-sounding guess would be worse than an obvious gap.
>
> One requirement is known and must survive whatever the final wording is: **Segment B's
> hint ends with an explicit exclusion — _"Exclude anyone seeking legal, immigration, or
> tax advice"_.** That is our policy-risk mitigation, stated where the model reads it. It
> is not optional and not a stylistic choice.

---

## Register — what must not appear

**Banned words:** revolutionary, game-changing, seamless, powerful, supercharge, unlock,
end-to-end, journey, adventure, exciting chapter, robust, best-in-class.

**Banned imagery:** suitcases, airplanes, passports on maps, families at airports.

That imagery is relocation-*service* visual language, and it positions ReloPass as a
vendor rather than infrastructure. Use interface fragments, case records, status views,
structured type.

**No claim about a visa, immigration, or tax outcome, in any card, ever.** ReloPass
coordinates the work; it does not determine what an authority decides. The landing pages
carry the disclaimer verbatim: *"ReloPass is coordination software. It does not provide
legal, immigration, or tax advice."*

**No EU AI Act status claim of any kind.** Not "Ready". Not compliant, certified or
conformant with it. And never describe ReloPass, or our AI, as a high-risk system.

This one is not a matter of register, it is legal exposure. Our own assessment
(`docs/compliance/AIQ-1487_eu_ai_act_assessment.md`) found the system **limited-risk, not
high-risk**, and concluded there is no readiness or certification scheme to hold in the
first place — so the claim would be false as well as premature, and it says plainly that a
premature compliance claim is itself a liability. We shipped exactly this badge on the
website once and had to remove it.

**What you may say instead** — these are verifiable product facts, and they are stronger
copy than a badge: a human reviews every AI recommendation · each decision is logged
alongside the AI output that informed it · answers are grounded in the customer's own
policy and cited · personal data is masked before any model call. Describe the controls,
claim no status.

If a generated variant introduces any of this wording, reject it at preview — do not edit
it into shape and approve it. CI enforces the same rule over this file
(`scripts/check_compliance_claims.py`).

---

## What counts as a qualified lead

**Proposed — needs Romain's sign-off, and written agreement with Audos before spend.**

**Segment A — qualified when all three hold:**
1. A work email on a company domain (not gmail/outlook/etc.).
2. The volume dropdown answered — any band. It is the qualifying question; unanswered
   means unscored.
3. The domain is a plausible employer of relocating staff, not an agency reselling us.

Bands `6–20`, `21–50`, `51–200` and `200+` are **sales-qualified**. `1–5` is a real user
but not a near-term contract; count it separately rather than discarding it.

**Segment B — qualified when both hold:**
1. A work email on a company domain.
2. "Who do you work for?" answered with a real employer name.

A segment B lead is **never** counted as a sales lead. Its value is the *account*, not the
person. Reporting must keep the two segments apart — blending them would make a cheap
segment B click look like pipeline, and that is the fastest way to misread this test.

---

## Reporting we need

- Raw click and conversion export, not just dashboard aggregates.
- Angle-level breakdown (A1–A6, B1–B2) — otherwise Gate 2 is guesswork.
- Spend and CPC per angle per segment.

We will reconcile against our own analytics weekly. Not distrust — platform attribution on
ChatGPT ads is undocumented (windows, view-through, incrementality are unpublished), so
two independent counts are the only way to know what actually happened.

---

## ⛔ Gates before this is sent

- [ ] **ADS-1 answered in writing** — revenue share, account ownership, credit amount and
      window, buyable geographies, and the domain question. Items 1, 4 and 5 are hard
      gates.
- [x] **G1: both landing pages confirmed serving prerendered HTML on relopass.com.**
      **Measured 2026-08-10, and it FAILED on first measurement** — the slash-less URLs
      served a 1,677-byte empty shell to every crawler. Fixed in
      `docs/gtm/ADS-4_destination_urls.md`; the destination URLs now carry a trailing
      slash, which is load-bearing. Re-run before every launch:
      `bash scripts/check_ad_landing_prerender.sh`.
- [ ] **Channel corrections applied** — `utm_source=meta`, ADS-6 re-scoped to a day-7
      qualitative read, and the geography contradiction settled in writing. See the
      box at the top.
- [ ] Playbook §6 context hints pasted into the section above.
- [ ] Qualified-lead definition approved by Romain.
