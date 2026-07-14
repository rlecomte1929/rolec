# EU AI Act — ReloPass AI Feature Assessment (DRAFT)

**Task:** AIQ-1487 · **Date:** 2026-07-13 · **Status:** DRAFT — legal review required before any external use
**Prepared by:** Claude Code (relopass-dev-queue). Not legal advice.

> **Publishing gate (hard):** Nothing in this document — badge, statement, or notice — may go
> live on relopass.com or into a sales asset until a qualified reviewer signs off. A false or
> premature compliance claim is itself a legal liability. See the task's Risk & Rollback note.

---

## Headline determination (differs from the task's premise)

The task assumed ReloPass's AI features "likely qualify as high-risk." **Grounded analysis says the
opposite: they are limited-risk, not high-risk.** This is the stronger and more honest position —
and it is *cheaper* to comply with, not more expensive.

**Why not high-risk.** The EU AI Act's high-risk employment category (Annex III §4) covers AI used
for **recruitment/selection, promotion/termination decisions, task allocation, performance
evaluation, and workplace monitoring** — i.e. AI that *decides things about a person's employment*.
ReloPass's AI does none of these. The relocation is decided by the employer **before** ReloPass is
involved; our AI then supports the *logistics* of that already-made decision. It never selects,
scores, ranks, promotes, or terminates anyone.

**Belt-and-suspenders (Article 6(3)).** Even if a feature were argued into an Annex III area, the
6(3) filter exempts systems performing a narrow procedural or preparatory task that does **not
materially influence** an employment decision. We do **not** lean primarily on 6(3) — the
Commission's draft guidelines require it to be read narrowly, and the "material influence" catch is
real. The primary argument is simpler: **the features are not in Annex III scope to begin with.**

**What still applies (limited-risk / Article 50 transparency):** users must be told when they are
interacting with an AI system, and AI-generated content should be marked. Both are cheap and we
largely do this already.

**Deadline context.** High-risk obligations were slated for **2 August 2026**; the proposed Digital
Omnibus may make this conditional on harmonised standards and push parts to **Dec 2027 / Aug 2028**.
Limited-risk transparency obligations are not the pressing item they were framed as — but they are
worth closing now as a trust signal.

---

## 1. Risk register

| # | AI Feature | What it does | In Annex III (high-risk employment)? | Classification | Risk level | Mitigation | Human oversight mechanism |
|---|---|---|---|---|---|---|---|
| 1 | **Policy Q&A / Policy Assistant** (RAG over company policy docs) | Answers an HR/employee question about *their own* relocation policy from published policy text | No — informational retrieval, no employment decision | Limited-risk (Art. 50 transparency) | Low | PII masked before any LLM call (`pii_masker`); answers cite source policy text; grounded-RAG refuses when unsupported | Employee/HR reads the cited source; answer is advisory, never binding; HR can override |
| 2 | **Cost estimation** (relocation cost bands) | Produces indicative €-range estimates for relocation services | No — cost figure, not an employment decision about a person | Limited-risk | Low | Estimates labelled indicative, not quotes; based on published/representative data | HR/employee reviews before committing spend; figures are non-binding |
| 3 | **Assignment / supplier recommendations** (movers, banks, housing…) | Ranks/suggests service *vendors* for a case | No — recommends third-party services, not a decision about the employee's employment | Limited-risk | Low–moderate | Recommendations are suggestions; user chooses freely; no auto-commitment | Employee/HR selects the vendor; nothing is auto-actioned |
| 4 | **Roadmap / requirements generation** | Generates a checklist of relocation steps for a corridor | No — procedural checklist from rules/regulations | Limited-risk (arguably out of scope entirely) | Low | Deterministic rules where possible; representative content flagged "indicative — confirm with authority" | Employee/HR follows or overrides; steps are informational |

**No ReloPass AI feature makes or materially influences a hiring, promotion, termination, task-
allocation, performance, or monitoring decision.** None is high-risk under Annex III §4.

---

## 2. Transparency notice template (≤200 words) — for HR to share with employees

> **How ReloPass uses AI in your relocation**
>
> ReloPass uses artificial intelligence to help you through your move. Specifically, AI helps
> answer your questions about your company's relocation policy, produce indicative cost estimates,
> and suggest service providers (such as movers, banks, or housing partners).
>
> These features are there to **inform and assist you** — they do not make decisions about your
> employment, and they do not decide anything on their own. A person is always in the loop: you
> and your HR team review AI-generated suggestions and make the actual choices. You can ask a human
> at any point.
>
> AI answers are drawn from your company's own policy documents and published information, and cite
> their source where possible. They may occasionally be incomplete or out of date, so please
> confirm anything important with your HR contact or the relevant authority before acting on it.
>
> We do not send your personal details to AI providers in the clear — identifying information is
> removed before any text is processed.
>
> If you have questions about how AI is used in your relocation, contact your HR representative.

*(Word count ≈ 175.)*

---

## 3. Compliance statement (≤100 words) — DRAFT, do NOT publish without legal sign-off

> **ReloPass and the EU AI Act.** ReloPass's AI features assist with relocation logistics —
> answering policy questions, estimating costs, and suggesting service providers. They do not make
> employment decisions and are not "high-risk AI systems" under the EU AI Act. They fall under the
> Act's limited-risk transparency rules: we tell you when you're interacting with AI, keep a human
> in every decision, and remove personal details before AI processes any text. We keep an internal
> record of how each AI feature works and review it as the rules and our product evolve.

*(Word count ≈ 90. No "EU AI Act Ready" badge — that phrasing overclaims; the above is a factual,
defensible description instead.)*

---

## Recommendation on the "trust badge"

**Do not ship an "EU AI Act Ready" / "Compliant" badge.** For a limited-risk system there is no
certification to be "ready" for, and the phrasing implies a formal status we don't hold — the exact
false-claim risk the task flagged. Instead: (a) publish the factual compliance statement (§3) after
legal review, and (b) surface the transparency notice (§2) in-product where AI is used. That is a
real trust signal without the liability.

## Reviewer actions
1. Confirm the not-high-risk determination with counsel (Annex III §4 scope + Art. 6(3) fallback).
2. Approve/edit §2 and §3 copy.
3. Decide placement: §2 in-product near AI features; §3 on a trust/security page (not a badge).

## Sources
- Crowell — *AI and Human Resources in the EU: a 2026 Legal Overview*
- EU AI Act, Article 6 (Classification rules) — artificialintelligenceact.eu/article/6
- European Commission draft guidelines on high-risk AI systems (Annex III scope; Art. 6(3) narrow interpretation), June 2026
