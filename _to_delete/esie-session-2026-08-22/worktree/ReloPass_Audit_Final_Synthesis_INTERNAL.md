# ReloPass Product Audit — Final Synthesis (Internal)

> **Audience:** Internal team, co-founders, advisors with full context. All findings surfaced.
> **Derived cuts:** Pitch-ready (buyer-facing) and Investor-ready cuts available as separate documents.
> **Audit method:** 15-task structured audit. Reference workflow (T1) → SRS read (T2) → product walkthrough (T3) → capability matrix + ERD + state machines (T4) → 8 test scenarios (T5) → legacy walkthrough (T6) → ReloPass post-P0 walkthrough (T7) → delta synthesis (T8) → architectural ceilings (T9-T11) → competitive benchmark (T12) → calibrated verdict (T13) → strengths/weaknesses/missing/risks (T14) → this synthesis (T15).
> **Calibration honesty:** All scoring is synthesized from reference workflows + product observation + audit prompt evidence + competitive public materials. No customer-interview validation — explicit limitation flagged in §11.
> **Date:** 26 April 2026.

---

## Table of Contents

1. Executive Summary
2. Verdict (Decomposed)
3. Strategic Positioning — The Topia-Threat Deliverable
4. Strengths
5. Weaknesses
6. Missing Capabilities (Phased Roadmap)
7. Risks to Product-Market Fit
8. Architectural Verification Spikes (Pre-Launch)
9. Competitive Landscape & Watch List
10. Recommended Actions (Next 90 Days)
11. Methodology, Limitations, Confidence
12. Appendices

---

## 1. Executive Summary

ReloPass is a product audit conducted across 15 structured tasks evaluating product-market fit, architectural readiness, and competitive positioning for the Phase 1 launch.

**The verdict (locked from T12 refinement):**

> *ReloPass is 3–4x better than industry-average mobility ops for SME and mid-market international assignments, and 2–3x better than the closest tech competitors (Localyze Business, Jobbatical) on the policy + budget reconciliation dimensions. It is a complement, not a replacement, for tax-heavy cases (defer to Localyze-Boundless or specialist firms) and for enterprise platforms (Topia post-Horizon). The French mid-market with mixed domestic + international move volume is a sharper opportunity than international-only positioning, contingent on the domestic Case flavor (option b) shipping cleanly.*

**Three operating principles locked through the audit:**

1. **Policy module + Estimate Review are the two product anchors.** Any future scope decision must protect both. Cuts that delay either degrade the verdict materially.
2. **Out-segment for MVP, complement for Phase 2.** SME + mid-market routine + French mid-market are the wedge. Topia-class enterprise is Phase 2 complement positioning, not displacement.
3. **Honest narrow positioning beats vague global claims.** Singapore + 2-3 priority corridors at depth is more defensible than 30+ corridors at half-depth.

**Five architectural verification spikes are conditional dependencies on the verdict.** Total verification effort ~3 weeks. The verdict drops from 3-4x to 2-3x if spikes return mixed results — still a winning verdict, just less aggressive.

1. Destination data depth audit (1-2 wks)
2. `Task.due_date` + date triggers verification (2 hrs verify; 2-3 wks fix)
3. `Case.contract_type` / `move_type` abstraction depth (3-5 days)
4. Family / dual-career signal propagation (half-day verify; 2-4 wks fix)
5. Audit log completeness via Prompts 0/A/B suite (1-2 days)

**Verdict confidence:** Medium-high (70-75%) as a structural claim, conditional on the spikes resolving and on customer-discovery validation. Direction is robust; absolute multiplier decimals are not.

**The single highest-leverage non-engineering investment to make right now:** a 5-10 customer-discovery interview wave with mid-market HR/mobility leads in EU + French markets to validate or refute the M10 mid-market 3 → 4 unlock claim and the policy/budget anchor as the differentiator.

---

## 2. Verdict (Decomposed)

### Per Segment

| Segment | Multiplier | Confidence | Strategic posture |
|---|---|---|---|
| **SME (10-200, EU intra)** | 3-4x vs legacy; 2-3x vs Localyze Starter | High (85%) | Direct pitch; entry tier; PLG motion appropriate |
| **Mid-market routine (200-2000, EU/Asia, no US/tax)** | 3-4x vs legacy; 2-3x vs Localyze Business / Jobbatical | High (85%) | **The core wedge**; primary GTM focus |
| **Mid-market complex (US/heavy-tax)** | 0.7-1x as displacement; complement positioning | Medium | Don't fight; pitch as policy/employee-experience layer alongside Big-4 + immigration firm |
| **French mid-market (domestic + intl mix)** | 3-4x positional vs Anywr | Medium-low (60%) | Sharper opportunity; conditional on option (b); window may close as Anywr stabilizes |
| **Enterprise (2000+, Topia-class)** | Marginal as displacement; complement only | High (90%) | Phase 2 path; integration story (Topia export) becomes real around 2027 |
| **Domestic-only (any segment)** | 2x operational; 3-4x positional with option (b) | Medium | Opportunity is positional, not per-case savings |

### Per Persona

**HR persona:** Largest gains in mid-market routine cases. Audit defensibility 2 → 4 (SME) and 3 → 4 (mid-market). Stakeholder confidence (M10) +1 in mid-market — the decisive PMF unlock. HR-hour reduction 30-40% in SME + mid-market routine; 15-25% in mid-market complex; marginal in enterprise.

**Employee persona:** Universal anxiety reduction via case visibility + Plan view (F12 fully solved). OOP exposure prevention via Estimate Review (-33% to -50% in mid-market family cases). Time-to-launch modestly compressed. Family/dual-career capture at intake (F11 mitigation 62% conditional on Spike 4).

### Per Sensitivity Variable

The verdict is most sensitive to 5 architectural variables. **All 5 must land for the 3-4x verdict to hold at scale.** Detailed in §8.

| Variable | If degraded | Spike # |
|---|---|---|
| Destination data depth | SME/mid-market 3-4x → 2-3x | 1 |
| Task.due_date + date triggers | F8 mitigation 100% → 0%; S7 collapses | 2 |
| contract_type real differentiation | F1 mitigation 82% → 60%; S4 collapses | 3 |
| Family/dual-career signal propagation | F11 mitigation 62% → 30%; S2 family case softens | 4 |
| Audit log completeness | M10 mid-market unlock not realized; multiplier 3-4x → 2-3x | 5 |

---

## 3. Strategic Positioning — The Topia-Threat Deliverable

The explicit, structured strategic recommendation around the Topia threat.

### Context

April 13, 2026: Topia launched Horizon (agentic AI platform with AI Policy Builder, Cost Modeling & Scenario Planning, Real-Time Compliance Intelligence, Employee-First Experience). Topia + Pearl Global Tech (immigration risk engine, acquired 2022) + Jobbatical EU partnership (April 2024) + Workday/ADP integrations + 159 FTEs + $135M raised + Bow River Capital ownership + customers (Schneider Electric, Dell, Veolia, Equinor, AXA).

**The category bet ReloPass made — "AI-native mobility platform with policy + cost + employee experience" — is now the same bet Topia is making with Horizon.** This is simultaneously the most validating and most threatening competitive event in the audit window.

### Phase 1 (now → 12 months): Out-segment

- Do not pitch enterprise. Period. Topia owns this; Horizon raised the bar.
- Focus exclusively on SME + mid-market routine + French mid-market (with option b).
- **Positioning narrative:** *"ReloPass is the AI-native mobility platform for companies running 5-50 international cases per year. We own policy and budget reconciliation; we partner with your existing tax and immigration providers; we don't try to be a $135M enterprise platform — we try to be the right platform for your scale."*
- **Pricing posture:** SaaS-tier accessible to mid-market budgets, not Topia-class enterprise sticker.

### Phase 2 (12-30 months): Complement

- Build Topia integration (export case data via Topia One open platform, which integrates with Workday/ADP).
- Pitch ReloPass as the *"employee-experience and SME-historical layer"* for enterprises whose mobility teams use Topia operationally.
- **Customer narrative:** *"Your Topia investment stays. Your employees and lower-volume programs use ReloPass. Data flows clean to Topia for compliance/audit/strategic reporting."*
- This is a **second sale, not a competitive sale** — sold to the same enterprise mobility VPs who already chose Topia.

### Phase 3 (30+ months): Niche-attack consideration

- IF Topia downmarket-motion happens (Horizon priced to compete in mid-market), revisit this strategic posture.
- IF customer base graduates beyond Phase 1 segments and Topia complement story doesn't hold, consider niche-attack on a specific dimension Topia is bad at (dual-career couples; permanent transfers; France-specific; mid-market with non-Topia HRIS).
- This phase is reactive, not proactive — driven by signal, not plan.

### What this position requires from ReloPass

1. **Discipline on the segment cut.** No enterprise demos. No 200+ case/year prospects in pipeline beyond complement-pitch. Honesty in sales cycles ("you should look at Topia for that scale").
2. **Phase 2 export readiness in MVP architecture.** Don't paint into a corner where Topia integration requires a rewrite. The Phase-2 complement story is materially harder if data isn't exportable in a Topia-friendly format from day one.
3. **AI-native parity narrative.** Topia + Horizon is the AI-native standard now. ReloPass needs to articulate its own AI capabilities (policy extraction, recommendation scoring, future agentic features) at par or near-par for credibility, even within the smaller segment.
4. **Watch list discipline.** Re-evaluate Topia's downmarket motion every 6 months (per §9).

### What this position protects against

- **Spreading thin to "compete with Topia."** The siren call to add enterprise features (CaseStakeholder full RACI, multi-approver chains, vendor relationship management at depth) drains MVP delivery capacity for features that drive SME/mid-market PMF. Out-segment discipline says *no, we're not building those for MVP because we're not chasing that customer.*
- **Pricing pressure from anchoring on Topia.** If sales conversations include Topia-as-comparison, ReloPass either looks expensive (vs SME baseline) or cheap (vs Topia ARR). Stay anchored to *"vs your current Excel + RMC + ad-hoc setup"* in mid-market sales.
- **Wrong feature roadmap calls.** Topia building feature X next quarter does not mean ReloPass should build X. Topia is building for enterprise. ReloPass is building for the wedge. Different roadmaps.

---

## 4. Strengths

### S1 — Policy management is best-in-class for the wedge segment

**Evidence:** T3 surface depth 5/5 (the only such surface in the audit). 36+ benefit types structured, 6 themes, draft/live versioning, 3-column override pattern (extracted baseline → HR adjustment → effective policy), match-strength scoring, two authoring paths (template + extraction), per-benefit unit/currency/duration/approval-required fields, internal HR notes, level-tiered caps (Entry/Manager/Director/VP/C-suite). T12 dimension scoring: tied with Topia Horizon at 5/5; ahead of Localyze (3/5), Deel (2/5), Jobbatical (2/5).

**Why it matters:** Foundation of F1 mitigation (policy ambiguity → wrong tier risk). Feeds Recommendations + Estimate Review. The single feature that lets ReloPass say "we structure mobility policy as data, not as a Word document HR has somewhere."

**Caveat:** Internal jargon ("Layer-2", "baseline", "evidence rules") leaks into the UI today. Cleanup committed. State the strength as *"once we ship the copy pass."*

### S2 — Case lifecycle with structured task graph (post-due_date fix)

**Evidence:** T3 Plan view depth 4/5. 5 phases, 16 tasks default, dependencies first-class ("Linked steps"), owner per task (You / HR / You & HR), priority flags, status states (blocked / available / in_progress / done). T7: solves F10 (no single source of truth) at 100% mitigation across all 8 scenarios — universal.

**Why it matters:** "The platform is the case file." The single most consequential capability for F10 + F12 mitigation.

**Caveat:** snake_case task IDs leak in UI; due_date missing (P0 fix). State the strength conditional on Phase 1 fixes.

### S3 — Family/dependent capture with dual-career signal at intake

**Evidence:** T3 Wizard step 3 depth 4/5: marital status, spouse with full name + "wants to work" toggle, children with name + DOB + country. F11 (family invisible) mitigation 62% in T7 — captured at intake; service propagation TBC (Spike 4).

**Why it matters:** Most mobility platforms ignore family or capture them as text fields. ReloPass treats them as structured data, and the dual-career flag specifically is unusual — it acknowledges that 30-40% of failed assignments are due to spouse-employment issues.

### S4 — Singapore destination depth as proof-of-concept

**Evidence:** T3 Recommendations + Resources surfaces (depth 4/5 each). 10 movers, 10 schools, 10 neighborhoods, 12+ resource categories, real Singapore vendor names, real schools, real neighborhoods, EP-specific watchouts in case detail, lifestyle scoring (safety, green) for neighborhoods, commute analysis from office, application-deadline awareness.

**Why it matters:** Proves ReloPass *can* do destination depth at the level enterprise customers expect. The pattern needs replication for other corridors but the model is proven.

**Caveat:** State as *"Singapore-corridor depth and the pattern proven; expansion to 2-3 priority corridors in Phase 1.5."*

### S5 — Estimate Review (post-buildout) as the value-prop screen

**Evidence:** Side-Output A specification (color signaling per ECB FX with date stamping, per-service breakdown with multiplier transparency, exception flow integration, personal-cost callout). T8: Estimate Review carries 4 of 8 scenarios (S2, S3, S5, S7) on F12/F14 mitigation. T12 dimension scoring: tied with Topia Horizon at 5/5 once shipped.

**Why it matters:** The single screen that turns abstract policy into concrete employee-facing budget guardrails. Produces M10 mid-market 3 → 4 unlock by giving CFO a structured cost-vs-policy reconciliation artifact.

**Caveat:** State as committed-and-shipping, not currently-in-product. Ship before pitching.

### S6 — Architectural readiness for AI-native positioning

**Evidence:** Match-strength scoring on policy extraction (visible in T3); existing audit prompt suite (Prompts 0/A/B from project documents) for tenant isolation testing; recommendations engine with structured scoring; passport OCR wired in wizard step 2; Policy Assistant chat surface visible.

**Why it matters:** Topia Horizon raised the AI-native bar two weeks before this audit. ReloPass has the foundational AI capabilities to credibly claim AI-native positioning at par with the category leader, within the smaller segment.

**Caveat:** Don't claim "AI-native" as a marketing phrase without the agentic policy builder + cost modeling visible features. State as *"AI-powered extraction and scoring throughout"* until you have agentic features to demo.

---

## 5. Weaknesses

Each weakness paired with severity (P0/P1/P2) and recommendation: **fix**, **acknowledge**, or **hide**.

### W1 — Employee Dashboard exposes implementation details (P0, fix)

T3 depth 1/5 — lowest in product. UUIDs, Section A/B language, manual claim form, 9 nav items. **First impression is the worst surface.** Fix in Phase 1: magic-link auto-claim, nav 9 → 3-4, hide UUIDs.

### W2 — Estimate Review is the lightest surface despite being the value-prop screen (P0, fix)

T3 depth 2/5. The screen that should embody MVP value prop currently shows a list of selections + totals — no cap comparison, no delta, no personal-cost callout. Fix per Side-Output A spec (Appendix A). 3-5 wks effort.

### W3 — Internal jargon leaks throughout user-facing copy (P1, fix)

"Layer-2", "baseline", "Section A/B", snake_case task IDs, UUIDs in messages. Cumulatively the difference between "professional B2B SaaS" and "engineer-built tool." 1-2 wks copy pass in Phase 1.5.

### W4 — Stakeholder model is thin (P1, acknowledge)

Only HR / Employee / internal Admin modeled. Hiring manager, HRBP, Mobility Committee, finance approver, payroll home/host, external advisors, vendor users, spouse-as-user — none expressible as first-class actors. CaseStakeholder model in Phase 1.5 (6-8 wks). Acknowledge to mid-market buyers; don't promise multi-stakeholder approval workflows that aren't built.

### W5 — Vendor management is half-modeled (P1, acknowledge)

Vendor entity exists with score, rating, "preferred by company" — but no SLA, no contract, no rate-card, no swap mechanism. F15 (vendor swap) mitigation 0%. Position as *"ReloPass scores and recommends vendors; you continue to work with your existing RMC for actual service delivery; Phase 2 brings RFQ automation."*

### W6 — Domestic move support not yet shipped (P0 if French wedge prioritized, fix)

Architectural Spike 3 is the gating item. Effort 3-4 wks if abstract, 6-8 if hardcoded. Phase 1.5 target. With French mid-market buyers, surface explicitly: *"Domestic moves are committed in Phase 1.5 — we're running an architectural spike now to commit to a date."*

### W7 — Audit log completeness unverified (P0, verify)

M10 mid-market unlock conditional on this. Run Spike 5 (the existing Prompt 0/A/B audit suite) immediately. Output is the verification artifact. If gaps surface, 4-6 wks remediation before MVP. Buyers care about outcome (defensible case file) not implementation detail; surface internal-only.

### W8 — Destination data is Singapore-only depth (P0, narrow positioning)

Singapore is the showcase; depth elsewhere unverified. Spike 1 confirms parity corridors. Ship MVP with explicit narrow positioning per locked option 1. Surface to buyers honestly: *"ReloPass is launching with depth in [Singapore + 2-3 priority corridors] — these are the corridors where we have full vendor coverage, school data, neighborhood profiles, and corridor-specific compliance. Other corridors on roadmap with partner/template-driven coverage."*

### W9 — No SSO / MFA / enterprise auth (P1, fix)

Self-signup with role dropdown, no SSO. P1 for mid-market routine procurement. SSO (SAML/OIDC) in Phase 1.5. ~3-4 wks engineering. Acceptable as roadmap commitment to mid-market buyers.

### W10 — RFQ flow currently terminates in localStorage (P0 for buyer perception, hide+fix)

The screen explicitly states "sending requests from here is not available yet." Hide entirely from MVP. Reframe funnel ending: cut the funnel at "package selection"; reposition value prop as "ReloPass shows employees their available providers within policy; HR uses existing RFP process." RFQ Phase 2 build-out.

---

## 6. Missing Capabilities (Phased Roadmap)

### Phase 1 (concurrent with P0 fixes) — ~12-17 weeks engineering, parallelizable to ~6-9 wall-clock weeks with 2-3 engineers

| # | Capability | Effort | Blocks |
|---|---|---|---|
| **M1** | `Task.due_date` + date-based triggers | 2-3 wks | F8 (forgotten repat); Command Center KPIs; risk classification |
| **M2** | `ExceptionRequest` entity + workflow | 3-4 wks | Estimate Review completion; F6 mitigation; M10 mid-market unlock |
| **M3** | Audit log gap remediation (after Spike 5) | 0 verified or 4-6 wks fix | M10 mid-market unlock; F9 mitigation |
| **M4** | FX rate snapshot persistence (ECB integration) | 1-2 wks | Estimate Review reliability; multi-currency cases |
| **M5** | Case `paused` status + pause/resume UI | 1 wk | Edge-case realism |
| **M6** | Hide RFQ screen + reframe funnel ending | 0.5 wk | MVP UX coherence |
| **M7** | Employee Dashboard P0 redesign | 1-2 wks | First-impression UX |
| **M8** | Command Center simplification (3 KPIs admin-configurable) | 1-2 wks | KPI honesty |
| **M9** | Estimate Review buildout per Side-Output A spec | 3-5 wks | The killer screen |
| **M10** | Dev tooling strip from production UI | 0.5 wk | Production hygiene |

### Phase 1.5 (mid-market wedge consolidation) — ~25-35 weeks, parallelizable to ~15-20 wall-clock weeks

| # | Capability | Effort | Blocks |
|---|---|---|---|
| **M11** | `Case.move_type` + `contract_type` propagation (Spike 3 → implement) | 3-4 wks (clean) or 6-8 (hardcoded) | F1 mitigation for permanent transfers; option (b) for domestic |
| **M12** | `CaseStakeholder` model (minimum viable RACI) | 6-8 wks | F6 mitigation; mid-market multi-actor cases |
| **M13** | 2-3 additional destinations at Singapore depth | 6-9 wks content + 6-8 wks tooling (parallel) | Verdict scoring depends on this |
| **M14** | Granular task dependencies (parallel-task support) | 2 wks | Time-to-launch compression |
| **M15** | Bulk case creation (admin import) | 2 wks | Mid-market scaling (30+ cases/year) |
| **M16** | Copy / jargon cleanup pass | 1-2 wks | Trust improvement |
| **M17** | SSO (SAML/OIDC) | 3-4 wks | Mid-market procurement |
| **M18** | Family / dual-career signal propagation (Spike 4 → implement) | 2-4 wks | F11 mitigation 62% → 90%+ |

### Phase 2 (complement positioning + scaling) — ~55-75 weeks, ~6-9 wall-clock months with 3-4 person team

| # | Capability | Effort | Justification |
|---|---|---|---|
| **M19** | Corridor-scoped policies | 4-6 wks | Multi-corridor mid-market |
| **M20** | Vendor relationship management (SLA, contract, swap) | 4-6 wks | Approaches Topia parity |
| **M21** | Conditional policy rules (if-then) | 4-6 wks | Tier × family-size × corridor variations |
| **M22** | Hierarchical benefits | 3-4 wks | Bundled package representation |
| **M23** | External system ingest layer (webhooks, integration connectors) | 6-8 wks | Phase 2 complement core |
| **M24** | RFQ flow build-out | 8-12 wks | Vendor outreach automation |
| **M25** | Tax provider integration interface | 6-8 wks | Mid-market complex cases |
| **M26** | Spouse-as-user (limited scope) | 6-8 wks | F11 full mitigation |
| **M27** | **Topia One export integration** | 4-6 wks | **The complement-positioning core** |
| **M28** | Webhook / event ingest infrastructure | 6-8 wks | Real-time accuracy |

### Phase 3+ (post-PMF expansion)

Side-letter generation, government portal integrations, multi-language UI, white-label/per-tenant branding, mobile native apps, multi-region deployment + data residency. Each is a customer-demand-driven build, not a roadmap commitment.

---

## 7. Risks to Product-Market Fit

| # | Risk | Probability | Severity | Mitigation |
|---|---|---|---|---|
| **R1** | Topia downmarket motion | Low-medium | High | Watch list every 6 months. Build Topia One export (M27) early as insurance. Accelerate Phase 2 complement positioning if signal appears. |
| **R2** | Architectural spikes return bad news | Medium | High (if 2+ fail) | Run all 5 spikes in parallel in next 3 weeks. Single readiness report before MVP launch commit. Verdict degrades to 2-3x but still wins. |
| **R3** | Destination data scaling cost overwhelms engineering | Medium-high | Medium | Locked option 1 narrow. Build destination admin tooling before adding 4th corridor. Consider part-time mobility-domain hire/contractor for content curation. |
| **R4** | AI extraction reliability fails publicly | Low-medium | High if it happens | Publish extraction match-strength data. Build "uncertain extraction → require HR review" UX. Default to template-start for SME without strong policy doc. |
| **R5** | Tenant isolation bug surfaces in production | Low | Existential | Run Prompts 0/A/B as part of Spike 5. Make isolation tests part of CI/CD before MVP. **Non-negotiable.** |
| **R6** | Deel Mobility ships deeper than expected | Medium | Medium-high | Watch list. Customer interviews with mid-market HR running Personio/BambooHR/HiBob to confirm best-of-breed appetite. Hold pricing tight. |
| **R7** | Localyze-Boundless integration produces stronger product than expected | Medium | Medium | Watch H2 2026 integration churn opportunity (be ready to engage Localyze customers re-evaluating their stack). |
| **R8** | Anywr stabilizes / French wedge window closes | Medium | Medium (specific to FR) | Spike 3 ASAP. If clean, commit option (b) delivery date in 4-6 weeks. Begin French market customer-discovery in parallel. |
| **R9** | No customer interviews validate any of this | High | Medium | **Run 5-10 customer-discovery interview wave in parallel with Phase 1 engineering.** Highest-leverage non-engineering investment. |
| **R10** | Spreading budget on enterprise temptation | Medium | Medium-high | **Sales discipline.** Out-segment commitment. When 2000+ prospect calls: complement story for Phase 2; Topia recommendation for now. Hard for sales muscle, easier as written policy. |

### R5 is the only existential risk. R9 is the only universal one.

R5 (tenant isolation) is the non-negotiable verification. The audit prompts (Prompts 0/A/B from project documents) exist precisely for this — run them before MVP launch.

R9 (no customer validation) is the only risk affecting every other claim in this document. Schedule the discovery wave now.

---

## 8. Architectural Verification Spikes (Pre-Launch)

The verdict is conditional on these 5 architectural realities. Recommend a brief verification spike on each before committing to MVP launch. **Total verification effort ~3 weeks.**

### Spike 1: Destination Data Depth (C7)

**Question:** What is the current depth of destination data beyond Singapore? Specifically: do Berlin, Madrid, Boston, Tokyo, Lyon (or whatever target corridors are committed) have ≥80% parity with Singapore on (a) vendor coverage [movers, schools, neighborhoods], (b) corridor watchouts, (c) cost data, (d) curated resources?

**Method:** Internal team scan — content audit per destination. Score each 0-5 against Singapore as the reference 5. Identify the 2-3 destinations closest to Singapore depth and prioritize MVP launch around those corridors.

**Effort:** 3-5 days of content audit per destination; 1-2 weeks total.

**Decision criterion:** If only Singapore is at depth, ship MVP with Singapore + 2 priority corridors and explicit "other corridors on roadmap" positioning per locked option 1 narrow.

### Spike 2: `Task.due_date` + Date Triggers (C3)

**Question:** Is `Task.due_date` present in the schema? Are case-level date triggers (e.g., `case.target_end_date - 90 days`) wired to the cron/scheduler infrastructure? Do they fire idempotently?

**Method:** Code review (1-2 hrs by senior engineer) + test-environment seed + verify alert fires.

**Effort:** 2 hrs verification; 2-3 wks to implement if absent.

**Decision criterion:** **P0** — F8 (forgotten repat) mitigation is the highest-cost legacy failure mode. Without due_date + triggers, the verdict on S7 collapses and M10 mid-market unlock is bounded.

### Spike 3: `Case.contract_type` Real Differentiation (C5)

**Question:** Does `Case.contract_type = permanent_transfer` (or `local_hire`, `domestic` for option b) actually drive different downstream behavior in plan generation, policy benefit application, services catalog filtering, and resources? Or is it a label only?

**Method:** Architectural code review: trace `contract_type` from Case creation through plan generation through policy application through services. Identify hardcoded "international LTA" assumptions. Document each subsystem touchpoint.

**Effort:** 3-5 days. **Critical: this spike must run before option (b) commits to a delivery date.** If `move_type` and `contract_type` are well-abstracted, option (b) is 3-4 wks. If hardcoded, it's 6-8.

**Decision criterion:** Result drives Phase 1.5 sequencing and Anywr-positioning timeline.

### Spike 4: Family / Dual-Career Signal Propagation

**Question:** When wizard step 3 captures `spouse.wants_to_work = true`, does that flag propagate to (a) destination resource surfacing (job-search support, language lessons), (b) services questionnaire (asking about spouse-employment preferences), (c) policy application (spouse-support benefit visibility)? Or is the flag stored and never read?

**Method:** Trace the flag from wizard → DB → all downstream consumers. 2-3 hours of code reading.

**Effort:** Half-day verification; 2-4 weeks to implement propagation if absent.

**Decision criterion:** F11 (family invisible) mitigation currently scored at 62% conditional on this. If flag is stored-but-not-read, downgrade S2 verdict to 2.5-3x and surface as MVP-must-fix.

### Spike 5: Audit Log Completeness (C8)

**Question:** What actions are currently captured in the audit log? Specifically: policy publish, policy version, case create, case status change, package submit, exception request (when built), HR approve/reject, document upload, message sent. Are denied actions logged?

**Method:** **Run the existing Prompt 0/A/B audit suite from the project documents.** This is exactly what the prompts are designed for. Output: structured discovery report + ingestion report + behavior report covering tenant isolation, audit log coverage, RBAC, prompt-injection resistance.

**Effort:** 1-2 days to run; if gaps surface, 4-6 weeks to remediate.

**Decision criterion:** Foundation of M10 mid-market unlock. The mid-market 3 → 4 jump on stakeholder confidence requires this to be solid. Don't ship MVP without verifying.

### Spike Summary

| # | Spike | Verify | Fix if absent | Priority |
|---|---|---|---|---|
| 1 | Destination data depth | 1-2 wks | 3-4 wks/dest + 6-8 wks tooling | Pre-launch |
| 2 | Task.due_date + triggers | 2 hrs | 2-3 wks | **P0 Phase 1** |
| 3 | contract_type / move_type abstraction | 3-5 days | 0 or 4 wks delta | **Pre-Phase 1.5** |
| 4 | Dual-career signal propagation | Half-day | 2-4 wks | P1 Phase 1.5 |
| 5 | Audit log completeness (run Prompts 0/A/B) | 1-2 days | 4-6 wks | **P0 Phase 1** |

---

## 9. Competitive Landscape & Watch List

### The Five Players

**Localyze** (the mirror image — now tilted). Berlin HQ. Acquired by Boundless Immigration October 1, 2025. Pivoted heavily toward immigration via Boundless. 200+ pathways across Europe. AI-driven legal-strategy recommendations. 3 software tiers (Starter/Business/Enterprise) + service tiers (Basic/Premium). Customers include Delivery Hero, Personio, Flix, Babbel, Roland Berger.

> **ReloPass posture:** Out-position via policy/budget anchor. The Boundless tilt makes the products less competitive than they were 6 months ago. Watch H2 2026 integration churn for re-evaluating Localyze customers.

**Deel** (the convergent threat). Launched Deel Mobility at Big Deel 2026 (March 2026). 100+ countries (Mobility specifically). 40,000 customers across all Deel products. Mobility integrated into Deel HRIS. EOR-sponsored visas. In-house immigration team.

> **ReloPass posture:** Out-segment. Target mid-market on Personio/BambooHR/HiBob/Workday HRIS who don't want their mobility data living in a competitor's payroll product. ReloPass is best-of-breed mobility specialist; Deel is feature-of-an-EOR.

**Jobbatical** (the corridor overlap). Estonia HQ. Immigration-first across 30-34+ countries. 15,000+ relocations completed. AI-powered eligibility checks, automated form pre-fill, real-time risk tracking, WhatsApp alerts. Topia partnership April 2024. Customers include Personio.

> **ReloPass posture:** Out-execute. Better policy module. Better Estimate Review (employee-facing cost-vs-policy reconciliation, vs Jobbatical's immigration-fee orientation). Better French market depth if option (b) lands.

**Anywr** (the French gatekeeper). French international group, founded 2012, 900-1000 employees, 14-16 countries. Originally Cooptalis. Services-led: recruitment, consulting, immigration, relocation, mobility policies, EOR. **Uses third-party SaaS RelocationOnline as tech platform.** Went through *sauvegarde accélérée* (financial restructuring); Laurent Perriault new CEO.

> **ReloPass posture:** Pure tech depth + UX wins vs RelocationOnline (generic SaaS). Self-serve mid-market beats consultant-led pricing. Modern policy management (codification) vs Anywr's policy consulting. French market entry via option (b) unifies domestic + international workflow Anywr currently bundles.

**Topia** (the enterprise reference). San Mateo HQ, founded 2010, 159 employees, $135M raised. Acquired by Bow River Capital June 2025. **Launched Horizon agentic AI platform April 13, 2026.** AI Policy Builder, Cost Modeling & Scenario Planning, Real-Time Compliance Intelligence, Employee-First Experience. Built into MCP environments. Pearl Global Tech immigration risk engine acquired 2022. Workday/ADP integrations. Enterprise customers: Schneider Electric, Dell, Veolia, Equinor, AXA.

> **ReloPass posture:** Cannot displace. Out-segment for MVP. Complement for Phase 2 (Topia One export integration). The Horizon launch validates ReloPass's category bet; the strategic posture is detailed in §3.

### Dimension-by-Dimension Comparison

(R = ReloPass post-P0; L = Localyze post-Boundless; D = Deel Mobility; J = Jobbatical; A = Anywr; T = Topia + Horizon)

| Dimension | R | L | D | J | A | T |
|---|---|---|---|---|---|---|
| Case management depth | 4 | 4 | 3 | 4 | 3 | 5 |
| **Policy management** | **5** | 3 | 2 | 2 | 3 (consulting) | **5** |
| Stakeholder model | 2 | 3 | 3 | 3 | 4 (consultants) | 5 |
| Destination coverage | 1-2 | 4 | 5 | 3 | 4 | 5 |
| Exception handling | 0 (P0 build) | 2 | 2 | 2 | 4 (mediated) | 5 |
| Audit trail | 3-4 | 4 | 4 | 4 | 3 | 5 |
| Vendor management | 2 | 3 | 4 | 2 | 5 | 5 |
| Integrations (HRIS) | 0 | 4 | 5 | 4 | 3 | 5 |
| Immigration depth | 0 | 5 | 4 | 5 | 4 | 4 |
| Tax / compensation | 1 | 2 | 4 | 1 | 4 | 5 |
| Employee UX | 4 | 4 | 3 | 4 | 3 | 4 |
| **Estimate Review** | **5** | 3 | 3 | 2 | 3 | **5** |
| Domestic move support | 4 (Phase 1.5) | 1 | 2 | 1 | 5 | 3 |
| Segment focus | SME + Mid | Mid + Ent | Mid + Ent | Mid | Mid + Ent (FR) | Ent only |

ReloPass's 5/5 dimensions: Policy + Estimate Review. Same as Topia Horizon. Nobody else matches. **This is the differentiator inside the SME/mid-market wedge.**

### Where ReloPass Wins (Buyer Map)

| Buyer profile | Primary alternative | Why ReloPass wins |
|---|---|---|
| EU SME (50-200), 2-10 cases/yr, no policy doc | Excel + lawyer; Localyze Starter | Templates + AI-extracted policy + structured case file. M10 2→3. |
| EU mid-market routine (200-2000), 10-50 cases/yr, no US-heavy mix | Localyze Business; Jobbatical; legacy RMC + Excel | Best-in-class policy + Estimate Review. Out-positioned vs Localyze (immigration tilt) and Jobbatical (immigration-first). M10 3→4. **The wedge.** |
| Mid-market with French domestic + intl mix | Anywr (services-led) | Unified domestic + intl workflow at SaaS pricing vs Anywr's consultant-led pricing. **Anywr-displacement opportunity.** |
| Mid-market on Personio/BambooHR/Workday HRIS | Deel Mobility; Localyze | Best-of-breed mobility specialist that doesn't drag the customer into a payroll/EOR migration. |
| Mid-market with US/heavy-tax volume | Localyze-Boundless; Topia | **Bounded.** Sell as complement to existing tax/immigration setup. |
| Enterprise (2000+) | Topia; Anywr (FR); Localyze Enterprise | **Cannot win MVP.** Phase 2 complement only. |

### Watch List (re-evaluate every 6 months)

| Signal | Threat / opportunity | Watch source |
|---|---|---|
| Topia downmarket motion | M10 ceiling for ReloPass mid-market shifts | Topia.com pricing pages; Bow River Capital comms |
| Localyze-Boundless integration friction | Customer churn opportunity for ReloPass H2 2026 | G2 reviews, customer LinkedIn signals |
| Deel Mobility maturity | Integration depth, mobility-specific UX | Big Deel 2027 announcements, customer reviews |
| Anywr stability | Continued restructuring or consolidation creates more openings | French press, Anywr communications |
| AI-extraction reliability standards | Public benchmarks emerging | Industry pubs, Topia Horizon docs |

---

## 10. Recommended Actions (Next 90 Days)

### Weeks 1-3: Verification

1. **Run all 5 architectural spikes in parallel.** Output: single architectural-readiness report. Total ~3 weeks.
2. **Run Prompts 0/A/B audit suite** as part of Spike 5. This is non-negotiable for tenant isolation correctness (R5).
3. **Schedule 5-10 customer-discovery interviews** with mid-market HR/mobility leads in EU + French markets. Validate or refute the M10 mid-market 3 → 4 unlock. Output: validated/refuted verdict claim by week 6.

### Weeks 4-12: Phase 1 Execution

Sequenced per §6 Phase 1 list. Highest-leverage items first:

1. **M1 (Task.due_date + triggers):** P0 — unlocks F8 mitigation, Command Center KPIs.
2. **M2 (ExceptionRequest):** P0 — required for Estimate Review completion.
3. **M9 (Estimate Review buildout per Side-Output A):** P0 — the killer screen.
4. **M7 (Employee Dashboard redesign):** P0 — first-impression UX.
5. **M3 (Audit log gap remediation):** P0 — M10 mid-market unlock foundation.
6. **M4 (FX rate snapshot persistence):** P0 — Estimate Review reliability.
7. **M6, M8, M10:** Quick wins (RFQ hide, Command Center simplify, dev tooling strip).
8. **M5 (paused state):** Edge case realism.

### Weeks 4-12 (parallel): Strategic Foundation

1. **Lock the segment cut.** Written policy: no enterprise demos, no 200+ case/year prospects beyond complement-pitch. Out-segment discipline.
2. **Begin destination data audit.** Identify 2-3 priority corridors beyond Singapore for Phase 1.5 expansion.
3. **Begin French market customer-discovery** in parallel with Spike 3 (option b feasibility).
4. **Draft pricing.** Based on Phase 1 feature set + segment positioning. Hold tight against Deel bundle pressure.
5. **Document the Topia complement story** for Phase 2 — even though it's not built, the narrative needs to be ready for sales conversations that will inevitably touch enterprise.

### Decision Points

- **End of week 3:** Architectural readiness report complete. Decision: launch MVP, fix-and-launch, or restructure.
- **End of week 6:** Customer discovery wave complete. Decision: verdict claim validated, refined, or replaced.
- **End of week 12:** Phase 1 features shipped (or close). Decision: open Phase 1.5 or extend Phase 1.

---

## 11. Methodology, Limitations, Confidence

### Method

15 sequential tasks with stop-and-greenlight reviews after each. Reference workflow synthesized from NBIM Mobility Overview interview deck + general mobility-ops literature. ReloPass product observation via 29 screenshots covering all major surfaces. Architecture inferred from screenshots + SRS + audit prompts (no codebase access). Competitive landscape via web search across 5 chosen competitors with Apr 2026 evidence. Verdict calibrated against 8 representative scenarios across SME / mid-market / enterprise × LTA / STA / permanent-transfer / repat / domestic.

### Limitations

| Limitation | Impact |
|---|---|
| **No codebase access** | Architecture is inferred (capability matrix tagged with confidence levels 🟢🟡🟠🔴). Effort estimates ±50%. |
| **No customer interviews** | Verdict is structurally robust but field-untested. R9 mitigation: schedule discovery wave. |
| **No live competitor product evaluation** | Competitor scoring is from public materials, not hands-on demos. |
| **Synthesized scoring throughout** | Every multiplier, every M10 score, every F-code mitigation percentage is calibrated, not measured. Direction is robust; absolute decimals are not. |
| **Topia Horizon launched 2 weeks ago** | Capability claims are not field-tested. Even at 70% of marketed capability, the competitive shape doesn't change. |
| **Pricing comparison impossible** | None of the 5 competitors publish prices. Real competitive pricing positioning needs sales-cycle data ReloPass will gather. |
| **Domestic verdict (S8) and French wedge** | Lowest scoring confidence. Conditional on option (b) shipping clean AND Anywr window staying open. |
| **Enterprise verdict (S6)** | Honest but uncomfortable. Topia + RMC + KPMG already deliver M10=4. ReloPass cannot displace. |

### Confidence Summary

| Component of verdict | Confidence | Why |
|---|---|---|
| 3-4x vs legacy in SME | High (85%) | Legacy baseline well-characterized; gain mechanisms concrete |
| 3-4x vs legacy in mid-market routine | High (85%) | Validated across 3 scenarios |
| 4x specifically in family cases (S2) | Medium-high (75%) | Conditional on F11 propagation (Spike 4) |
| 2-3x vs Localyze Business / Jobbatical | Medium (65%) | Inferred from competitor materials |
| Complement-not-replace for tax-heavy + enterprise | High (90%) | Topia Horizon makes near-certain for enterprise |
| French mid-market sharper opportunity | Medium-low (60%) | Multiple compounding contingencies |
| F8 (repat) mitigation | Conditional on Spike 2 | Single-point failure on C3 |
| Verdict survives competitive pressure 12 months | Medium (60%) | Topia/Deel/Localyze-Boundless trajectories unknown |

**Overall verdict confidence: Medium-high (70-75%) as a structural claim.**

---

## 12. Appendices

### Appendix A — Estimate Review Specification (Side-Output A, complete)

#### A.1 Purpose

The single screen where the MVP value proposition becomes visible to the employee and audit-defensible for HR. Three jobs:

1. **Make policy concrete.** Translate abstract caps into "what you actually get."
2. **Surface the gap.** Where the employee's selections exceed policy, show the personal cost in plain numbers.
3. **Provide an action path.** Either reduce to fit policy, request an exception, or accept the personal cost.

Anti-goal: this is *not* a final invoice. It is an *indicative* package summary built from estimates. The page must be honest about that.

#### A.2 Layout (top to bottom)

```
┌──────────────────────────────────────────────────────────────────┐
│  CASE HEADER                                                       │
│  Paul Doe · Lyon → Singapore · Move 1 Aug 2026 · 36 mo · 1 spouse │
│  + 1 child ·  Policy: Mobility baseline (Standard) v1 · USD/EUR   │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TOTAL PACKAGE                                                     │
│                                                                    │
│   Estimated package cost (36 mo)        €164,213                  │
│   Your policy budget                    €145,000                  │
│   ─────────────────────────────────────────────                   │
│   Above policy by                       €19,213    [⚠ over]       │
│                                                                    │
│   What this means: if you proceed with these selections, you      │
│   would pay €19,213 from your own pocket over the assignment.     │
│                                                                    │
│   [ Edit selections ]  [ Request exception ]  [ Proceed anyway ]  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  PER-SERVICE BREAKDOWN                                            │
│                                                                    │
│  ✓  Movers — Santa Fe Relocation                                   │
│     One-time          €11,187      Cap: €15,000 (one-time)         │
│     Status:           Within policy. Fully covered.                │
│                                                                    │
│  ⚠  Schools — Canadian International School                        │
│     €30,636/year × 3 yr = €91,908   Cap: €15,000/child/yr × 3 yr   │
│                                       = €45,000 (1 child)          │
│     Status:           Above policy by €46,908 over 3 years.        │
│     Personal cost:    €15,636/year (~€1,303/month).                │
│     [ Why? ] (links to policy line)                                │
│                                                                    │
│  ✓  Housing — Novena (rented apartment)                           │
│     €2,042/mo × 36 mo = €73,531    Cap: €2,500/mo × 36 = €90,000  │
│     Status:           Within policy. Fully covered.                │
│                                                                    │
│  ⓘ  Schooling support (policy benefit)                            │
│     Policy includes: Up to €15,000/child/yr education support      │
│     Status:           Applied above. No selection required.        │
│                                                                    │
│  ⓘ  Tax equalization (policy benefit)                             │
│     Policy includes: Yes                                           │
│     Status:           HR will arrange. No selection required.      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  IF YOU PROCEED                                                    │
│                                                                    │
│  Covered by your employer:        €145,000  (within policy)       │
│  Your personal cost:              €19,213   (above policy)        │
│  Total package:                   €164,213                         │
│                                                                    │
│  Currency note: estimates shown in EUR. Source data in EUR/SGD/    │
│  USD; converted at indicative rates from 24 Apr 2026. Final        │
│  quotes from vendors may differ.                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### A.3 Color Signaling Rules

| Color | Status | Trigger | Where it appears |
|---|---|---|---|
| 🟢 Green | Well within policy | actual ≤ 80% of cap | Service line item, total summary if all green |
| 🟡 Yellow | Approaching limit | 80% < actual ≤ 100% of cap | Line item; total if any yellow |
| 🔴 Red | Above policy | actual > 100% of cap | Line item; total if any red |
| ⚪ Grey | No cap defined | policy has no rule for this benefit | Line item only — never roll into total |
| ⚫ Outline | Excluded by policy | benefit explicitly `excluded: true` | Line item with "not covered" framing |

**Total package indicator** uses worst color across line items (one red turns the total red). Color is reinforced with text and an icon — never color alone (WCAG).

**80% threshold** is configurable per tenant (Path A: ReloPass admin sets per-customer thresholds).

**Notifications & warnings:**

| Trigger | Notification |
|---|---|
| Any service goes red | In-screen banner: "1 service exceeds policy. Personal cost: €X." |
| Total > 100% | Top-of-screen banner + email to employee + audit_log entry |
| Total > 100% AND employee proceeds | Required: ExceptionRequest must be filed before "Proceed" enables |
| Service goes red after recommendation refresh | Push notification + message |
| FX rate older than 24h | Footer warning: "Exchange rates last refreshed [date]. Refresh available." |

#### A.4 FX Rate Sourcing

**Primary source:** European Central Bank (ECB) Euro foreign exchange reference rates.
- API: ECB stats portal (XML feed available)
- Refresh cadence: ECB publishes daily ~16:00 CET on TARGET working days
- Coverage: EUR base, ~31 currencies (USD, GBP, JPY, CHF, SGD, NOK, SEK, AUD, CAD, etc.)

**Implementation:**
1. ReloPass fetches ECB feed daily at 16:30 CET, stores as `FXRate(currency_code, rate_to_eur, source='ECB', source_date, fetched_at)`.
2. Every estimate computation references the latest `FXRate` row at compute time, stamps `source_date` on the LineItem.
3. Display: "Estimates shown in EUR. Exchange rates from ECB, [DD Mon YYYY]." Footer link to ECB source page for transparency.

**Edge cases:**
- Currency not in ECB list: show in source currency only with badge "Estimate not converted — currency outside ECB reference list."
- Weekend / holiday: use latest published rate, footer notes "Last published [date]."
- Source date older than 7 days: hard warning, escalate to admin.

#### A.5 Calculations

```
LineItem {
  service_category: enum (movers, housing, schools, banking, ...)
  vendor_name: str
  unit_cost: Money
  unit: enum (one_time, per_month, per_year, per_dependent)
  multiplier: int  # derived from case context
  total_cost = unit_cost * multiplier
  
  cap: Money | null
  cap_unit: enum | null
  cap_total = cap * multiplier_for_cap
  
  delta = total_cost - cap_total
  status = within_policy | over_policy | no_cap_defined | not_covered_by_policy
  personal_cost = max(0, delta)
}

Multiplier rules:
- movers: 1 (one-time)
- housing: case.duration_months
- schools: case.duration_years × case.family.children_count
- language training (per-person): case.family.size_eligible
- tax equalization: not a cost, a benefit — show as "Included" / "Not included"

Totals:
total_package = sum(line_items.total_cost)
total_covered = sum(line_items.total_cost where status == within_policy)
                + sum(line_items.cap_total where status == over_policy)
total_personal = total_package - total_covered
```

#### A.6 Edge Cases

| Edge case | UX response |
|---|---|
| **No policy published yet** | Banner: "HR is finalizing your policy. The figures below are estimates only and don't yet reflect your coverage." Hide comparison columns; show package estimate only. |
| **Partial policy coverage** | Per-service status differs. Services with no defined cap show "No cap defined in policy" (not zero). Distinguish from "Excluded by policy" (employee pays full). |
| **Currency mismatch** | Source currency in tooltip. Page always one currency consistently. FX rate + date in footer. |
| **Multiplier ambiguity** (e.g., schooling cap "per child per year", 2 kids, 3-year duration) | Show the math: "€15,000 × 1 child × 3 years = €45,000 cap." Never just the final number. |
| **One-time vs recurring confusion** | Always show "x36 months" or "/year × 3" inline. |
| **Policy expressed as % of salary** | Compute against `case.salary_band` midpoint. Footnote: "Estimated based on midpoint of your salary band; final value confirmed in your assignment letter." |
| **Selection above policy + "Proceed anyway"** | Generate `ExceptionRequest` record routed to HR. Don't let through silently. |
| **Selection above policy + "Request exception"** | Form: reason, justification, proposed coverage % from employer. Routed to HR with case context. |
| **HR view of same screen** | Same layout, action buttons become: [Approve as-is] [Approve with exception] [Request changes]. Plus note field. |
| **Tax-equalized assignments** | Row: "Tax equalization — handled by HR" with explainer. |
| **Annualized comparison toggle** | "Show annual / total" toggle for long assignments. |
| **Selections with "Limited availability" / "Waitlist"** | Carry forward as: "⚠ Limited availability — confirm with vendor before booking." |

#### A.7 Microcopy Principles

- Always show the math. "€15,000 × 1 child × 3 years = €45,000" not just "€45,000 cap."
- State the assumption. "Based on your salary band midpoint." "At indicative FX from 24 Apr 2026."
- Never use "approved" before HR has approved. Use "covered," "within policy," "estimated."
- Personal cost is named, not implied. "Your out-of-pocket cost" — directly.
- No green checkmarks for "within policy" services where vendor hasn't quoted yet. Use "Estimated within policy."

#### A.8 Permissions & Audit

- Employee sees their own estimate. Edits trigger draft state.
- HR (same tenant) sees the same estimate plus: total cost roll-up across employee's package, history of edits, exception requests pending.
- HR cannot edit selections but can attach notes and approve/request changes.
- Every state change writes to `audit_log` with actor, timestamp, before/after values.

#### A.9 Effort Estimate

3-5 weeks of focused work for a single full-stack engineer + designer. Most of the work is in calculation logic and edge cases, not the UI.

### Appendix B — Scenario Reference

The 8 representative test scenarios used for T6/T7/T8 evaluation:

| # | Scenario | Segment | Assignment | Corridor | Family | Stresses |
|---|---|---|---|---|---|---|
| **S1** | "The simple LTA" | SME | Long-term | EU intra (Lyon→Berlin) | Single | Floor case |
| **S2** | "The family case" | Mid-market | Long-term | EU intra (Paris→Madrid) | Spouse + 2 kids | F11, F16, schools |
| **S3** | "The US transfer" | Mid-market | Long-term | TGA (Frankfurt→Boston) | Spouse, no kids | F4, F17, US visa |
| **S4** | "Permanent transfer" | Mid-market | Permanent | EU intra (Madrid→Amsterdam) | Single | F1, F8, no-repat |
| **S5** | "The short-term project" | SME | Short-term | Long-haul (Berlin→Singapore) | Single | Speed, scope-down |
| **S6** | "The enterprise displacement" | Enterprise | Long-term | Long-haul (Paris→Tokyo) | Spouse + teen | All gaps; vendor swap |
| **S7** | "The forgotten repat" | (continues S2) | Repat | Madrid→Paris | Same family | F8, lifecycle gap |
| **S8** | "Domestic Paris→Lyon" | French mid-market | Domestic | FR intra (Paris→Lyon) | Spouse + 1 child | Anywr lens, requires option b |

### Appendix C — F-Code Reference

The 17 friction codes used in the audit, sourced from T1 reference workflow synthesis:

| Code | Friction |
|---|---|
| F1 | Policy ambiguity / wrong tier risk |
| F2 | Document chase loops |
| F3 | Vendor communications gaps |
| F4 | Tax planning late |
| F5 | Side-letter errors |
| F6 | Exceptions ad-hoc |
| F7 | COLA misses |
| F8 | Repat forgotten |
| F9 | Audit defensibility |
| F10 | No single source of truth |
| F11 | Family invisible to systems |
| F12 | Employee no view |
| F13 | Institutional knowledge loss |
| F14 | Stale cost projections |
| F15 | Vendor swap difficulty |
| F16 | Translation / apostille |
| F17 | Immigration fragmentation |

### Appendix D — 10-Metric Scoring Rubric

Used in T6/T7/T8 to evaluate each scenario:

1. Time-to-launch (clock weeks)
2. HR active hours (cumulative)
3. Employee active hours (cumulative on logistical tasks)
4. Errors / redo events
5. Audit defensibility (1-5)
6. Cost variance % (actual vs estimated)
7. HR cognitive load (1-5)
8. Employee anxiety (1-5)
9. Out-of-policy spend exposure (€)
10. Internal stakeholder confidence M10 (1-5; CFO/CHRO/CEO trust)

---

**End of Internal Synthesis.**

*Total: 12 sections + 4 appendices. Confidence calibrated. Audience-coding for derived cuts in §11.*
