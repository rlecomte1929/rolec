# ReloPass — Claude-Ready Website Audit Brief

**Version:** April 2026  
**Purpose:** Use this document as a self-contained brief when running a brand or website audit with Claude. Paste it at the top of a new conversation, then attach the page copy (or screenshots) you want audited.

---

## 1. What you are asking Claude to do

Audit the ReloPass website against a defined brand strategy and messaging framework. For each page provided, Claude should:

1. Score the page against the 10-point rubric in Section 4.
2. Flag every issue with the correct severity tier (Section 5).
3. Rewrite every flagged line, applying the 6 voice checks (Section 3).
4. Produce a gap matrix entry for the brand-to-site alignment tracker (Section 6).
5. Recommend a section-order correction if the current page structure misses the required narrative arc (Section 7).

Do not summarise the page. Do not explain what the page is trying to do. Go straight to findings.

---

## 2. Brand context (read before auditing anything)

### Who ReloPass is

ReloPass is the **operating layer for global workforce mobility**. It turns fragmented relocation workflows — email threads, spreadsheets, disconnected vendors — into a structured, policy-driven system of record.

It is **not**:
- A relocation service or agency
- A vendor marketplace
- An HR add-on
- A relocation companion or concierge

It is the **coordination layer** across HR teams, relocating employees, and external providers.

### The brand promise (single source of truth)

> **Every relocation case is visible, compliant, on-time.**

Every piece of copy should ladder up to this. If a sentence cannot be traced back to visibility, compliance, or on-time execution, it is likely filler.

### Primary buyer

HR managers and Global Mobility managers. They want: **control, predictability, visibility**.

Relocating employees are **beneficiaries**, not the primary website audience. They want: clarity, guidance, a structured path. They should appear on the site as a consequence of the system working, not as the hero.

### Tone reference

The brand sits in the same tonal family as Stripe, Linear, Notion, and Datadog. Calm. Precise. Confident. Structured. If a sentence could appear on stripe.com or linear.app without looking out of place, it is close to correct. If it reads like a startup pitch deck, rewrite it.

### Gold-standard copy anchors

Use these as the register target. New copy should feel like it belongs in the same family.

| Slot | Approved copy |
|---|---|
| Hero CTA | "Structure how you run relocation. Start with one case." |
| Why-page hero | "Relocation fails in the handoffs." |
| Section header | "Built for mobility operators." |
| Feature card | "Vendor tasks stay tied to the case, not lost in inboxes." |
| Page `<title>` | "ReloPass — Global mobility infrastructure" |
| Get-started hero | "Three ways in. Book a demo, sign in, or create an account." |
| Footer contact | "Tell us how your relocations run today. We'll show you what changes." |

---

## 3. The 6 voice checks (run all six on every draft)

Every rewrite must pass all six checks before being returned.

**Check 1 — Category framing**  
Does the copy position ReloPass as *infrastructure / operating layer / system of record*? If it reads like a relocation service, agency, or marketplace, rewrite.

**Check 2 — Audience fit**  
HR/mobility managers want control, predictability, visibility. Employees want clarity and structured guidance. The copy must speak to one of these two modes explicitly. Watch second-person "your…" that defaults to the wrong audience. The primary buyer is HR, not the employee.

**Check 3 — Tone**  
Calm, precise, confident, structured. Not inspirational. Not startup-pitched.

**Check 4 — Forbidden registers**  
Flag and rewrite any of the following:

- **Startup hype:** "revolutionary", "game-changing", "disrupt", "supercharge", "unlock", "next-gen"
- **Consulting filler:** "synergies", "best-in-class", "leverage", "end-to-end solutions" (as empty filler)
- **Lifestyle-relocation language:** "journey", "new adventure", "exciting chapter", "pack your bags", travel imagery, passport/suitcase references
- **Generic SaaS filler:** "powerful platform", "seamless experience", "robust", "all-in-one"
- **Defensive qualifiers:** "real", "actual", "true", "genuine", "proper" — these imply you're defending an unspoken objection and weaken every sentence they appear in

**Check 5 — Concreteness**  
Every abstract claim needs a concrete anchor nearby: a workflow, a case, a stakeholder, a corridor, a policy, a compliance step. Abstract claims without anchors are filler.

**Check 6 — Sentence discipline**  
Short, declarative, one idea per sentence. No stacked adjectives. No trailing qualifiers.

---

## 4. The 10-point page scorecard

Score each page 1–5 on every criterion. Use **🔴 red** (1–2), **🟡 amber** (3), **🟢 green** (4–5).

| # | Criterion | What 5 looks like |
|---|---|---|
| 1 | **Category clarity** | The page positions ReloPass as infrastructure/operating layer, not a service or tool |
| 2 | **Audience clarity** | HR/mobility buyer is clearly the hero; employees appear as beneficiaries |
| 3 | **Problem intensity** | The coordination problem is vivid: blind spots, dropped handoffs, compliance exposure |
| 4 | **Differentiation** | The page explains why ReloPass is not a vendor, agency, marketplace, or HR add-on |
| 5 | **Proof** | Product-level evidence: UI, workflow state, case logic, policy execution, audit trail |
| 6 | **Trust** | Seriousness and operational credibility; no lifestyle aesthetics; no hype |
| 7 | **Narrative flow** | Hero → Problem → Guide → Plan → CTA arc is present and ordered correctly |
| 8 | **Visual coherence** | Clean hierarchy, structured grid, product-first visuals, restrained colour |
| 9 | **CTA quality** | One primary CTA and one lower-friction CTA; both visible without scrolling |
| 10 | **Brand fit** | Copy and design feel consistent with Stripe/Linear register; no generic SaaS drift |

---

## 5. Severity tiers (tag every finding before rewriting)

Always sort findings in severity order: 🔴 first, then 🟠, then 🟡. Never sort by page order.

**🔴 SITE-WIDE** — Appears in metadata, nav labels, page titles, footer, or brand name treatment. Search engines and link previews use this. Fix first.

**🟠 PAGE-LEVEL** — Appears once per page in a high-visibility slot: hero headline, section header, primary CTA. High priority.

**🟡 SENTENCE-LEVEL** — Body copy, secondary microcopy, list items. Fix once higher-severity issues are resolved.

---

## 6. Brand-to-site gap matrix

For each page audited, produce a row for each of the following dimensions.

| Dimension | Blueprint says | Site currently says | Gap | Recommended fix | Priority |
|---|---|---|---|---|---|
| Category | | | | | |
| Audience | | | | | |
| Problem | | | | | |
| Promise | | | | | |
| Differentiation | | | | | |
| Tone | | | | | |
| Visual system | | | | | |
| CTA | | | | | |
| Trust | | | | | |
| Proof | | | | | |

Fill in "Blueprint says" using the brand context in Section 2. Fill in "Site currently says" from the copy provided. Derive the gap. The recommended fix should be a single sentence describing the correction, not a rewrite.

---

## 7. Required narrative arc per page type

Use the arc below as the reference structure. If the current page deviates, flag the section that is missing or out of order, and state what should replace it.

### Homepage arc
1. **Hero** — Category statement + buyer value + two CTAs
2. **Problem stakes** — The coordination failure: email, spreadsheets, fragmented vendors, compliance exposure
3. **System overview** — ReloPass as the operating layer: cases, timelines, documents, providers, status
4. **How it works** — Four-step operational sequence (create, apply policy, coordinate, monitor)
5. **Product proof** — Annotated UI showing workflow state, case view, provider coordination
6. **Differentiation** — Not an agency, not a marketplace, not an HR add-on
7. **Trust** — Operational logic, auditability, policy execution, corridor intelligence
8. **Final CTA** — Talk to us about your relocation operations

### Platform page arc
1. Platform overview statement
2. Module-by-module breakdown (cases, timelines, documents, providers, policy controls, reporting)
3. Annotated product screenshots per module
4. "What HR sees / what the employee sees" comparison
5. CTA

### Why ReloPass arc
1. The market problem (coordination, not just complexity)
2. Why current tools fail (email, spreadsheets, fragmented vendors)
3. Category framing (operating layer, not another vendor)
4. Contrast blocks (without / with ReloPass)
5. CTA

### How it works arc
1. Overview statement (3–4 steps maximum)
2. Step-by-step with inputs, system actions, outputs
3. Supporting UI per step
4. CTA

### Get started arc
1. Buyer-focused headline
2. Form with minimal fields
3. Trust microcopy (30-minute walkthrough, no commitment)
4. What the demo covers
5. Lower-friction CTA (see platform)

---

## 8. Copy substitution table

Use this as a quick-reference swap guide when rewriting flagged copy.

| Forbidden | Replacement direction |
|---|---|
| "Your relocation journey" | "Your relocation operations" or remove entirely |
| "Seamless relocation" | "Structured relocation execution" |
| "All-in-one platform" | "One system for cases, documents, providers, and timelines" |
| "Simplify the journey" | "Reduce coordination overhead" or "Replace manual tracking with structured workflows" |
| "Support every move" | "Track every case from policy to completion" |
| "Powerful platform" | Describe the specific capability instead |
| "Robust solution" | Describe the specific outcome instead |
| "Real relocations" / "actual workflows" | Remove the qualifier; state the claim directly |
| "Game-changing" | Remove; replace with a concrete operational claim |
| "Exciting new chapter" | Remove; this is employee lifestyle copy, not buyer copy |

---

## 9. Expected output format

For each page audited, Claude should return:

```
PAGE: [page name]
SCORECARD: [10 scores in red/amber/green format]
OVERALL SCORE: [X/50]

FINDINGS (sorted 🔴 → 🟠 → 🟡):

[Severity] [Check #] [Location in page]
Current: "[exact quote]"
Issue: [one-sentence diagnosis]
Rewrite: "[replacement copy]"

GAP MATRIX:
[filled table for this page]

NARRATIVE ARC ASSESSMENT:
[missing or out-of-order sections, with correction]
```

Do not write a summary paragraph before findings. Do not add caveats. Go straight to the structured output.

---

## 10. Known first-priority issues (pre-audit intelligence)

These are the most likely issues based on prior analysis. Confirm or refute each when auditing.

1. **Page `<title>` reads "ReloPass — Your Relocation Journey"** — category error (lifestyle/employee framing); correct to "ReloPass — Global mobility infrastructure" 🔴 SITE-WIDE
2. **Homepage hero may be split between HR buyer and employee** — employee-journey framing dilutes infrastructure positioning 🟠 PAGE-LEVEL
3. **"Your Relocation Journey" appears to be a site-wide or homepage headline** — forbidden register (Check 4) 🟠 PAGE-LEVEL
4. **Coordination problem is likely understated** — "Cases, documents, providers, and status in one place" describes features; it doesn't make the problem vivid 🟠 PAGE-LEVEL
5. **Product screenshots may function as decoration rather than proof** — each screenshot must show a workflow state, not just a UI surface 🟡 SENTENCE-LEVEL
6. **Page roles may overlap** — "Platform", "Why ReloPass", and "How it works" must each do a distinct job; flag any repeated content across pages 🟠 PAGE-LEVEL

---

*End of audit brief. Attach page copy or screenshots below this line to begin the audit.*
