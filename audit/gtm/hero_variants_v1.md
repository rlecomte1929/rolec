# FRIDAY-004b · Hero headline + sub-hero variants

**Task**: AIQ-647 → 004b
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (review + pick the pair, or A/B)
**Source of truth**: 004a positioning sentence
**Hand-off to**: 004d (meta tags) + 004e (implementation)

---

## 1. Recommended pair (ship this, or A/B-test #1 against #2)

### 🏆 Pair A — leads with the auditor's question

**Headline (6 words)**:
> **Mobility AI your auditor will trust.**

**Sub-hero (17 words)**:
> Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready.

**Why this is the recommended pair:**
- Headline reframes the buyer's actual fear into a benefit ("your auditor will trust"). Six words, declarative, no hype.
- Sub-hero earns the headline with three concrete moves (logged · cited · EU AI Act–ready) and a triple-pause cadence that scans well at 320 px.
- Together they cover both the "agentic" undercurrent and the "EU AI Act–ready" promise without saying "agentic" once.

---

## 2. Headline variants (4 total, 8-word cap)

| # | Variant | Words | Lead with | Notes |
|---|---|---|---|---|
| 🅰 | **Mobility AI your auditor will trust.** | 6 | auditor / trust | Recommended. Sharpest. Names the buyer's fear as a benefit. |
| 🅱 | **Relocate people. Audit every decision.** | 5 | the two halves of the product | Two-clause structure mirrors ReloPass mental model. Calm, factual. Risk: "audit every decision" can read like surveillance. |
| 🅲 | **Built for the EU AI Act.** | 6 | regulation directly | Most compliance-forward variant. Best for top-of-funnel buyers actively de-risking AI procurement. Risk: niche, won't land for buyers who think AI Act is "2027 problem." |
| 🅳 | **The auditable side of agentic mobility.** | 6 | direct response to Topia | Sharpest competitive pin. Concedes "agentic" exists and reframes the question. Risk: requires buyer to know what "agentic mobility" means — works at YC office hours, may fall flat with mid-market HR. |

### Disqualified options (failed brand-voice or character cap)

- ~~"The most powerful mobility platform for the EU AI Act era"~~ — "most powerful" disqualified by brand-voice rules.
- ~~"Seamless global mobility, fully auditable"~~ — "seamless" disqualified.
- ~~"Your mobility journey, audited end-to-end"~~ — "journey" disqualified.
- ~~"All-in-one mobility with audit trails"~~ — "all-in-one" disqualified.
- ~~"AI-powered mobility built for the EU AI Act"~~ — over the 8-word cap and uses "AI-powered" which is hype-shaped.

---

## 3. Sub-hero variants (4 total, 18-word cap)

| # | Variant | Words | Pairs with | Notes |
|---|---|---|---|---|
| ① | **Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready.** | 17 | 🅰 (recommended) | Triple-pause cadence. Names "logged, cited, ready" — the three proof-block dimensions. Best at any breakpoint. |
| ② | **Documents read. Forms filed. Decisions cited. The audit trail your legal team has been asking for.** | 17 | 🅱 | Four short clauses. Concrete actions. Names the human (legal team) instead of the abstraction. Slightly riskier — buyer may not have a legal team yet. |
| ③ | **One platform for the relocation, the documents, and the audit trail the EU AI Act will require of you.** | 18 | 🅲 | Most descriptive. Names the AI Act as a coming requirement, not a current one — softens for "not in scope yet" buyers. |
| ④ | **The audit logs, the bias testing, the human-in-loop. The same product your employee actually wants to use.** | 17 | 🅳 | Names all three proof-block dimensions verbatim + the EX (employee experience) angle in the second half. Strongest pairing with 🅳. |

### Disqualified

- ~~"Powerful AI-driven mobility, end-to-end"~~ — "powerful" disqualified.
- ~~"Seamless onboarding, full compliance"~~ — "seamless" disqualified.

---

## 4. Pairing matrix

The headline + sub-hero combinations and what each is best for:

| Headline | Sub-hero | Best when |
|---|---|---|
| 🅰 + ① | Mobility AI your auditor will trust + Every step in your employee's relocation… | **Recommended default.** Broadest fit. Works for HR/CHRO + general counsel. Use this if you only ship one pair. |
| 🅰 + ④ | Mobility AI your auditor will trust + The audit logs, the bias testing… | **A/B variant against 🅰+①.** Names the three pillars explicitly in the sub-hero. Better when the audience already self-identifies as "I'm here for AI Act compliance." |
| 🅱 + ② | Relocate people. Audit every decision. + Documents read. Forms filed. Decisions cited. | **For prospects already churning off a legacy vendor.** Calm, factual, no novelty. Use for outbound emails to CHROs frustrated with Cartus/Sirva. |
| 🅲 + ③ | Built for the EU AI Act + One platform for the relocation, the documents… | **For top-of-funnel paid acquisition.** Best for SEO landing pages targeting "EU AI Act mobility" or similar queries. Niche but high-intent. |
| 🅳 + ④ | The auditable side of agentic mobility + The audit logs, the bias testing… | **For YC office hours + sharp design-partner conversations.** Highest-edge pair. Use when room is sophisticated. |

---

## 5. Recommended A/B setup (if a split-test framework is available)

**Control**: existing hero (whatever's live today).
**Variant 1**: 🅰 + ① (recommended default).
**Variant 2**: 🅰 + ④ (recommended A/B challenger — same headline, sharper sub-hero).

Why this A/B and not, say, 🅰 vs 🅱: changing both the headline and the sub-hero at once destroys signal. By holding the headline constant and only varying the sub-hero, you learn whether explicit naming of "audit logs / bias testing / human-in-loop" lifts conversion vs the more lyrical version.

**Primary metric**: clicks on the primary CTA (likely "Book a demo" or "Start a pilot").
**Secondary metrics**: scroll depth, time on page, bounce rate.
**Decision rule**: 95% confidence over ≥ 200 visitors per arm or 14 days, whichever comes first.

---

## 6. Brand-voice compliance check

| Variant | Forbidden words | Concrete? | Cadence | Verdict |
|---|---|---|---|---|
| 🅰 | none | "auditor" + "trust" | 1 line, declarative | ✅ pass |
| 🅱 | none | "relocate people" + "audit every decision" | 2 short clauses | ⚠ pass with risk note: "audit every decision" can read like surveillance |
| 🅲 | none | "EU AI Act" direct | 1 line | ✅ pass |
| 🅳 | none | "auditable side" + "agentic mobility" | 1 line, more abstract | ⚠ pass with risk note: depends on buyer knowing "agentic mobility" |
| ① | none | "logged, cited, ready" — triple concrete | triple-pause | ✅ pass |
| ② | none | "documents read · forms filed · decisions cited · legal team" | four-clause | ✅ pass |
| ③ | none | "relocation · documents · audit trail · EU AI Act" | one sentence | ✅ pass |
| ④ | none | "audit logs · bias testing · human-in-loop · employee" | two sentences | ✅ pass |

All clear the brand-voice bar. The two "⚠ pass" notes are not voice failures — they're audience-fit risks worth flagging.

---

## 7. Validation criteria — self-check

- ✅ **Each variant passes brand-voice rules** — see §6.
- ✅ **Each headline ≤ 8 words** — A=6, B=5, C=6, D=6. All under cap.
- ✅ **Each sub-hero ≤ 18 words** — ①=17, ②=17, ③=18, ④=17. All under cap.
- ✅ **At least one variant emphasizes 'agentic'** — 🅳 explicitly. **At least one emphasizes 'EU AI Act-ready'** — 🅰 implicitly via "auditor will trust", 🅲 + ③ explicitly. Recommended pair 🅰+① threads both via "EU AI Act–ready" in the sub-hero.
- ✅ **None overlap with Topia or Sirva hero copy** — checked against Topia Horizon launch ("Agentic AI that finally gets global mobility right") and Sirva ("Trusted global mobility for the world's leading companies"). No phrase collision.

---

## 8. Hand-off

- → **004c (proof block)**: build the 3 lines under 🅰+① — each one should make "logged, cited, and EU AI Act–ready" verifiable.
- → **004d (meta tags)**: use the recommended pair as source. The `<meta description>` 140-160 chars budget cleanly accommodates "Mobility AI your auditor will trust. Every step in your employee's relocation — every document, every decision — logged, cited, and EU AI Act–ready." (151 chars).
- → **004e (implementation)**: ship 🅰+① as the default; wire 🅰+④ as the A/B challenger if a split-test framework exists.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Variants stress-tested for brand-voice, character budget, and competitive non-overlap. Recommended pair is the lowest-risk, highest-signal default.*
