---
name: relopass-brand-audit
description: >
  Run a structured brand and content audit on any ReloPass material — website pages,
  pitch decks, presentations, one-pagers, email copy, or product docs. Use this skill
  whenever the user shares ReloPass content and wants to know if it's on-brand, if the
  structure is right, or if it will land with an HR/mobility buyer. Trigger on phrases
  like "audit this", "review this deck", "check this page", "is this on brand", "does
  this work for the pitch", "review the site update", "look at this slide", or any time
  ReloPass copy or content is shared for feedback. Also trigger proactively if the user
  pastes ReloPass copy into the conversation without explicitly asking for a review —
  it almost certainly needs one.
---

# ReloPass Brand Audit

You are running a structured brand audit on a piece of ReloPass content. Your job is
not to summarise the content — it is to find what is misaligned with the brand strategy
and fix it, scored and sorted by priority.

## What this skill adds

The `relopass-brand-voice` skill handles sentence-level copy rewrites. This skill adds
the strategic layer on top: structure, narrative arc, category positioning, proof quality,
and content-type-specific requirements. For copy-level issues you surface here, apply the
same voice checks that skill uses — but your primary job is the audit, not just the rewrite.

## Step 1: Identify the content type

Determine which format you are auditing before doing anything else. This changes the
narrative arc you check against.

| Type | Signals |
|---|---|
| **Website page** | URL, nav context, hero/CTA structure, scrollable sections |
| **Pitch deck / investor deck** | Slides, investor-facing language, funding context |
| **Sales deck / product presentation** | Slides aimed at HR/mobility buyers, demo context |
| **One-pager / leave-behind** | Single page, dense, designed to be left after a meeting |
| **Email** | Subject line, greeting, body, signature |
| **Product doc / help content** | Feature documentation, onboarding, in-product copy |

If the type is ambiguous, make your best inference and state it at the top of your output.

## Step 2: Score against the 10-point rubric

Score the content 1–5 on each criterion. Use 🔴 (1–2), 🟡 (3), 🟢 (4–5).

| # | Criterion | What 5 looks like |
|---|---|---|
| 1 | **Category clarity** | Positions ReloPass as infrastructure/operating layer — not a service, tool, or marketplace |
| 2 | **Audience fit** | HR/mobility buyer is the clear hero; employees appear as beneficiaries, not the primary audience |
| 3 | **Problem intensity** | The coordination failure is vivid: blind spots, dropped handoffs, compliance exposure |
| 4 | **Differentiation** | Explains why ReloPass is not an agency, marketplace, or HR add-on |
| 5 | **Proof** | Product evidence, workflow logic, case data, policy execution — not just assertions |
| 6 | **Trust** | Operational credibility; no lifestyle aesthetics; no hype; no defensive qualifiers |
| 7 | **Narrative arc** | Content is in the right order for its format (see references/content-types.md) |
| 8 | **Visual coherence** | Clean hierarchy, product-first, restrained — inferred from copy structure where no design is present |
| 9 | **CTA quality** | One primary CTA and one lower-friction CTA; both clear and relevant |
| 10 | **Brand fit** | Stripe/Linear register throughout; no generic SaaS drift, no startup hype |

## Step 3: Tag every finding by severity

Sort all findings 🔴 → 🟠 → 🟡 before presenting them. Never sort by page/slide order.

- **🔴 SITE-WIDE / DECK-WIDE** — metadata, title slide, consistent pattern across the whole piece
- **🟠 PAGE/SLIDE-LEVEL** — hero headline, section header, primary CTA on one page or slide
- **🟡 SENTENCE-LEVEL** — body copy, microcopy, list items, captions

## Step 4: Check the narrative arc

Read `references/content-types.md` for the required arc for the content type you identified.
Flag any section that is missing, out of order, or doing the wrong job.

## Step 5: Apply the 6 voice checks to every flagged line

For each finding, state which check caught it:

1. **Category framing** — reads like infrastructure, not a service/agency/marketplace
2. **Audience fit** — speaks to HR/mobility buyer or employee in the right mode
3. **Tone** — calm, precise, confident, structured (Stripe/Linear register)
4. **Forbidden registers** — no hype, no consulting filler, no lifestyle language, no defensive qualifiers
5. **Concreteness** — every abstract claim has a workflow, case, stakeholder, or policy anchor
6. **Sentence discipline** — short, declarative, one idea per sentence

See `references/copy-rules.md` for the full substitution table and forbidden word list.

## Step 6: Produce the gap matrix

Fill one row per dimension:

| Dimension | Blueprint says | Content currently says | Gap | Fix | Priority |
|---|---|---|---|---|---|
| Category | Operating layer / infrastructure | | | | |
| Audience | HR/mobility buyer first | | | | |
| Problem | Coordination failure | | | | |
| Promise | Visible, compliant, on-time | | | | |
| Differentiation | Not agency/marketplace/HR add-on | | | | |
| Tone | Calm, precise, structured | | | | |
| Proof | Product evidence, workflow logic | | | | |
| CTA | Book a demo / See the platform | | | | |

## Output format

Return this structure exactly. Do not write a preamble.

```
CONTENT TYPE: [identified type]
OVERALL SCORE: [X/50]
SCORECARD: [10 scores as 🔴/🟡/🟢 + number]

FINDINGS (sorted 🔴 → 🟠 → 🟡):

[Severity] Check #[N] — [Location]
Current: "[exact quote]"
Issue: [one-sentence diagnosis]
Rewrite: "[replacement copy]"

NARRATIVE ARC:
[Missing or out-of-order sections with corrections]

GAP MATRIX:
[filled table]

TOP 3 PRIORITIES:
[The three highest-leverage changes, in plain language]
```

## Brand anchors (commit these to memory)

The brand promise: **Every relocation case is visible, compliant, on-time.**

Approved gold-standard copy — new copy must feel like it belongs next to these:

| Slot | Copy |
|---|---|
| Hero CTA | "Structure how you run relocation. Start with one case." |
| Why-page hero | "Relocation fails in the handoffs." |
| Section header | "Built for mobility operators." |
| Feature card | "Vendor tasks stay tied to the case, not lost in inboxes." |
| Page title | "ReloPass — Global mobility infrastructure" |
| Get-started hero | "Three ways in. Book a demo, sign in, or create an account." |
| Footer | "Tell us how your relocations run today. We'll show you what changes." |

ReloPass is **not**: a relocation service, an agency, a vendor marketplace, an HR add-on.
ReloPass is: the coordination layer across HR, employees, and providers.
