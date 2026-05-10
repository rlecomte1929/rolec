# Brand Messaging — Source of Truth

This document codifies the voice, positioning, and copy rules for everything user-facing in ReloPass: marketing pages, in-product UI, error messages, emails, onboarding, and CTAs. It is the reference any contributor should apply before merging copy changes.

If a piece of copy doesn't pass the checks below, rewrite it.

---

## Promise

> **Every relocation case is visible, compliant, on-time.**

Every headline, label, error, and CTA should ladder up to that promise. Visibility, compliance, on-time delivery — these are the three things HR/mobility operators are buying.

---

## Position

### What ReloPass is

- **Operating layer / infrastructure** for mobility coordination
- **Workflow-first system** that keeps cases on track
- Built for **HR and mobility operators** — not employees, not vendors
- A **source of truth** for case status, documents, and provider work

### What ReloPass is NOT

- A relocation service (we don't move people)
- A vendor marketplace (we don't sell relocation services)
- A generic project management tool
- A lifestyle or travel brand

### Reference brands for tone

We sound like Stripe, Linear, Notion, Datadog. Not like a relocation service, not like a startup pitch deck.

| Reference | What we borrow |
|-----------|----------------|
| Stripe | Calm precision. Infrastructure framing. Concrete claims. |
| Linear | Short, declarative sentences. Operator-first. |
| Notion | Workflow language ("workspace", "case", "process"). |
| Datadog | Visibility framing. Built-for-operators positioning. |

---

## The 6 Voice Checks

Apply all 6 to every piece of copy before merging.

### 1. Category framing

**Does it position ReloPass as infrastructure / an operating layer?**

- Pass: "Run relocation as one process" (`landingContent.ts`)
- Pass: "Built for mobility operators" (`landingContent.ts`)
- Fail: "Relocation platform" (too generic — sounds like any SaaS)
- Fail: "Mobility marketplace" (wrong category — we're not a marketplace)

### 2. Audience fit

**Does it speak to HR/mobility operators about control, visibility, predictability?**

- Pass: "See your cases and next actions" (`accessContent.ts`)
- Pass: "Cases, documents, providers, and status in one place" (`landingContent.ts`)
- Fail: "Make your relocation amazing" (talks to the employee, not HR)
- Fail: "Join the relocation revolution" (audience-vague + hype)

### 3. Tone

**Would this sound natural on stripe.com or linear.app?**

- Pass: "Schedule a demo" (`BookDemoModal.tsx`)
- Pass: "Try this on one case." (`whyReloPassContent.ts`)
- Fail: "Let's chat about your relocation dreams!"
- Fail: "Unlock relocation mastery"

### 4. Forbidden registers

**Are any of these registers present? If yes, rewrite.**

| Register | Banned terms (non-exhaustive) |
|----------|-------------------------------|
| Startup hype | revolutionary, game-changing, disrupt, supercharge, unlock, next-gen, cutting-edge, world-class |
| Consulting jargon | synergies, best-in-class, leverage, end-to-end solutions, holistic approach |
| Lifestyle/relocation cliché | journey, adventure, exciting chapter, new beginning, pack your bags, explore |
| Generic SaaS filler | powerful platform, seamless experience, robust solution |
| Defensive qualifiers | real, actual, true, genuine (e.g. "real coordination" implies defending against fakeness) |

### 5. Concreteness

**Does every abstract claim have a workflow anchor (case, document, provider, policy, status, follow-up)?**

- Pass: "Vendor tasks stay tied to the case, not lost in inboxes." (`landingContent.ts`)
- Pass: "Hard to see what moved, what is blocked, and who owns the next step." (`landingContent.ts`)
- Fail: "Powerful coordination" (no anchor)
- Fail: "Amazing visibility" (abstract — visibility into *what*?)

### 6. Sentence discipline

**Is each sentence short, declarative, one idea per sentence?**

- Pass: "Three ways in." (4 words, declarative — `landingContent.ts`)
- Pass: "Each move is one trackable case." (`landingContent.ts`)
- Fail: "To leverage our powerful coordination infrastructure and unlock your relocation visibility, get started today!" (multi-clause, hype-laden, vague)

Aim for ≤15 words per sentence. One idea per sentence. End on the noun, not a preposition.

---

## Pre-merge checklist

Copy this checklist into the PR description for any change touching user-facing strings:

```
- [ ] Positioning: ReloPass framed as infrastructure / operating layer
- [ ] Audience: speaks to HR/mobility operators (control, visibility, predictability)
- [ ] Tone: would read naturally on stripe.com / linear.app
- [ ] Forbidden registers: no startup hype, consulting jargon, lifestyle cliché, generic SaaS filler, or defensive qualifiers
- [ ] Concreteness: every abstract claim has a workflow anchor
- [ ] Sentence discipline: short, declarative, one idea per sentence
```

If any check fails, rewrite before merging. There is no "ship now, fix copy later" — copy debt compounds and is rarely paid back.

---

## Where copy lives in the repo

| Surface | File | Notes |
|---------|------|-------|
| Landing page | [frontend/src/pages/landing/landingContent.ts](../frontend/src/pages/landing/landingContent.ts) | Hero, problem cards, solution blocks, trust, final CTA |
| Platform page | [frontend/src/pages/public/platformContent.ts](../frontend/src/pages/public/platformContent.ts) | Hero, product definition, inside-product blocks, CTA |
| Why page | [frontend/src/pages/public/whyReloPassContent.ts](../frontend/src/pages/public/whyReloPassContent.ts) | Reality, thesis, differentiation, outcomes, peak CTA, final CTA |
| Trust page | [frontend/src/pages/public/trustContent.ts](../frontend/src/pages/public/trustContent.ts) | Process, boundaries |
| Access page | [frontend/src/pages/public/accessContent.ts](../frontend/src/pages/public/accessContent.ts) | Three paths: demo, sign in, create account |
| Demo modal | [frontend/src/components/marketing/BookDemoModal.tsx](../frontend/src/components/marketing/BookDemoModal.tsx) | Title, subtitle, fields, errors, success state |
| Demo emails | [supabase/functions/submit-demo-request/index.ts](../supabase/functions/submit-demo-request/index.ts) | Notification + auto-reply copy |
| In-product UI | `frontend/src/features/`, `frontend/src/pages/` | Currently inconsistent — see audit task |

Marketing copy is centralized in `*Content.ts` files so it can be updated without layout work. Keep this pattern. New marketing surfaces should follow the same `<surface>Content.ts` convention.

---

## Reference: gold-standard copy in the codebase

These are the highest-quality strings shipped today. Use them as anchors when rewriting.

| Copy | Why it works |
|------|--------------|
| "Run relocation as one process" | Verb "run" puts the operator in control. "One process" frames the value. |
| "Relocation fails in the handoffs" | Specific failure mode the buyer recognizes immediately. |
| "Cases, documents, providers, and status in one place" | Four concrete anchors. No abstraction. |
| "Vendor tasks stay tied to the case, not lost in inboxes." | Negative concrete anchor ("not lost in inboxes") makes the positive land. |
| "Built for mobility operators." | Period. Declarative. Audience-explicit. |
| "Guided process, human decisions" | Sets the contract: automation + human judgment. |
| "You can start with one case." | Lowers activation energy. Specific commitment ask. |

When in doubt, model new copy on these.

---

## What this document does NOT cover

- **Visual design** — colors, typography, spacing live in `tailwind.config.js` and the marketing token system (`--marketing-*`).
- **Component patterns** — see `frontend/src/components/marketing/` for the shared component library.
- **Demo-booking-specific UX** — see the `Documents/Claude/Projects/ReloPass/BRAND_GUIDELINES_FOR_DEMO_BOOKING.md` reference for the full demo-form spec (field labels, error messages, accessibility).
- **In-product copy** — currently inconsistent with marketing voice. An audit pass is on the roadmap (see `Documents/Claude/Projects/ReloPass/LANDING_PAGE_AUDIT_REPORT.md` Phase 2.3).

---

## Maintenance

When you ship a copy change that establishes a new pattern (e.g. a new headline shape, a new error-message format), add it as a row in either "gold-standard copy" or as a new pass example under the relevant voice check. This document only stays useful if it tracks the codebase.
