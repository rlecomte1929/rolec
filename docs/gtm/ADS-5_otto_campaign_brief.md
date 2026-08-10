# ReloPass × Otto — campaign brief

**AIQ-1785 (ADS-5).** Draft for Romain to review and send to Audos.
**Do not send until the two gates at the bottom are cleared.**

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
- [ ] **G1: both landing pages confirmed serving prerendered HTML on relopass.com.**
      Until verified on the live domain, every URL in this brief may point at a page a
      crawler reads as blank.
- [ ] Playbook §6 context hints pasted into the section above.
- [ ] Qualified-lead definition approved by Romain.
