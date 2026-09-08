# ReloPass — North Star v2

> Supersedes North Star v1 (the France→Norway "depth over breadth" lock). Rewritten 2026-08-12 after a full audit of the live platform, the Audos routines, and a 158-company competitive sweep. Company name is **ReloPass** (Otto's auto-namer keeps drifting to "GlobeIQ"/"TrendNest" — wrong everywhere it appears).

---

## The thesis, in one line

**ReloPass is the verifiably-correct relocation brain for the HR generalist — breadth delivered *through* an accuracy engine, not despite it.**

v1 said "pick one corridor, go deep, say no to everything else." That was the right instinct for a standing start and the wrong lock for where you actually are. You've built more than one corridor's worth of platform, and the market proves a single-corridor tool is a demo, not a company. **v2 keeps the discipline but moves it: correctness is now a property of the *pipeline*, not of a *corridor*. Build the verification engine once; every corridor you add inherits its trust — so breadth becomes the moat instead of the liability.**

---

## Two things I'm challenging on the way in

**Challenge to "build too small."** A single France→Norway corridor is not defensible or fundable. The competitive sweep is unambiguous: 158 players, breadth and "AI-native" are table stakes, and the closest analogues (Localyze, Jobbatical, Workia, Permitree, Centuro) already span 11–195 countries. Staying tiny forever loses by default. You are right not to want to be stuck on one destination — the multi-corridor work is the correct ambition.

**Challenge to the current approach.** The risk was never building too small — it's **shipping breadth without operating the engine that makes breadth safe.** Today the platform generates breadth-shaped *activity* — ~15 speculative country research runs, malformed self-certified facts, a parallel code queue inside Audos — while the actual accuracy machinery you already built and shipped (the requirement-fact extractor, the review UI, the eval harness with a France→Norway golden set) **has never been run in production.** The knowledge base is empty; the eval dashboard shows no data; the "healthy" numbers are green because they count silence as success. **Activity is not validated capability.** In a trust market, unvalidated breadth isn't ambition — it's competitor #159 with data you can't stand behind. The correction is not "go slower / go narrower." It's **operate the engine, gate every corridor through it, then open the throttle.**

---

## 1. Who — the customer

**HR generalists at SMEs**, personally responsible for occasional high-stakes international moves that are nobody's full-time job — now often across *more than one* corridor as the company hires internationally.

Sharpest avatar: someone facing their first or second relocation into an unfamiliar country — aware enough to be scared, not experienced enough to be calm. It's a stressful side-quest on top of their real job, and it repeats unpredictably as the business grows.

**Still not** the enterprise global-mobility manager. The competitive sweep *confirms* this is the unclaimed buyer: every tier — direct SaaS, RMCs, immigration software, Big Four, EOR/HCM — is structurally built for enterprise mobility teams, procurement, law firms, or their own payroll customers. **The SME generalist is ignored by all 158.** That gap is the position money can't shortcut, because owning it means abandoning the enterprise base every incumbent is built on.

## 2. Problem — kills the not-knowing

**It sucks that** an HR generalist gets handed a high-stakes move that's nobody's job — and the thing that sinks them isn't the visible work, it's the requirement they didn't know to look for, surfacing in week seven when it's too late to fix.

Personal responsibility is the **amplifier** (it's on *you*). The **blade** is the invisible requirement. That blade is **corridor-agnostic** — it exists for France→Norway, Spain→Ireland, Germany→France, and every pair after. Which is exactly why the product can't be a single hand-built corridor: the thing that relieves the not-knowing has to be an *engine* that surfaces the invisible requirement anywhere — and is provably right when it does.

## 3. Solution — the accuracy engine (Case Command is its first surface)

The product is not "a France→Norway checklist." **The product is the engine: discover authoritative sources → extract structured requirements → independently verify (re-fetch, verbatim-match, recompute source tier) → gate against a corridor gold set → serve inside Case Command with the evidence attached.** Corridors are *content that flows through the engine.*

First-mile action, unchanged: **"surface the unknowns."** HR opens a case (country pair + employee type) → a structured timeline appears with the non-obvious, corridor-specific requirements flagged inline (the Norway D-number, the tax card/skattekort needed *before* first pay, police/EEA registration, EEA-but-not-EU quirks). The bar: at least one flagged requirement they wouldn't have known to look for — **and it's verifiably correct.**

**France→Norway is the first *proven* corridor — the reference rung, not the whole product.** It's the corridor you run through the engine first to prove ≥95% correctness, 100% official-source, full non-obvious coverage. Once that gate is green, the *same engine* opens the next corridor. Depth is how you prove the engine; breadth is what the engine produces.

## 4. What we build vs. deliberately don't (revised from v1's hard "no's")

v1's blanket no's ("no broad corridor coverage, no vendor management, no employee-facing") no longer match the platform or the market. Revised:

- **Breadth — YES, but only through the gate.** Every new corridor's facts stay out of the knowledge base until they pass the eval harness (independent verification + gold-set score). The real "no" is **unvalidated breadth** — never surface a corridor you can't prove.
- **Vendor management — YES, as a *neutral coordination layer*, not as execution.** Integrate the supply (housing: AltoVita/Blueground/Nestpick; movers: Shyft; tax: GTN/Certino; data: Mercer/AIRINC; filing: VisaHQ). **Don't** become a low-margin RMC/DSP that owns the physical move — that trap is still a hard no.
- **Employee-facing — v1, fine now.** The platform has it; keep it lightweight. But the buyer and the moat stay the HR generalist, not the employee.
- **The new disciplines (this is where the approach corrects):** operate the engine before adding surface; never let a builder self-certify (the verifier sets "verified," not the extractor); keep the two systems decoupled (Audos = landing / CRM / source-discovery / prototypes; the ReloPass stack = system of record + engine + all PII); and **hold ads / outreach / Autopilot until accuracy is provable** — driving traffic to unvalidated corridors spends the one thing that is the moat.

## 5. Lasting value — the moat (reframed against 158 competitors)

The moat is **not** "a relocation platform" (158 exist), **not** "AI-native" (a slogan the whole field uses), and **not** breadth (everyone has it). It is the compounding of four layers, trust as the throughline:

1. **The maintained-correctness engine.** Being *verifiably, provably* right — evidence-linked, independently checked, freshness-monitored. Rules decay constantly, so a copied snapshot rots on day one; the asset is the maintenance engine, not the data. This is also the direct answer to the objection you *will* hear from Big-Four-anchored buyers ("expertise + tech beats pure software"): you sell the proof, not the promise.
2. **The SME generalist as system of record.** Once their cases, deadlines, and history live here, switching means re-entering everything and re-trusting a new source on high-stakes compliance — for the buyer no competitor is built to serve.
3. **The neutral coordination layer.** You plug the supply (housing/movers/tax/immigration) into the HR record-of-truth (Workday/HiBob/Personio/Remote via MCP). EORs and RMCs *cannot* be neutral — they're selling you employment or the move. Neutrality is a structural edge, not a feature.
4. **Data effects, last.** At volume, real outcomes sharpen flagging and unlock benchmarks — a payoff of layers 1–3, not a substitute.

**Two-year competitor test (updated):** to beat ReloPass a competitor must do four things at once, from behind — serve the SME generalist they're structurally built to ignore, prove maintained correctness nobody else publishes, be the neutral layer EOR/HCM incumbents can't be, and displace an embedded system of record. The **real** threat is Deel-style **absorption** (an EOR bolting relocation onto the employment relationship — Deel Mobility already ranks #1–2 in G2 Relocation and is open to non-Deel customers). The answer to it is not feature parity; it's the full stack aimed at the unserved buyer, sold on proof, from a neutral position.

---

## Pricing

- **Now:** per-move (one SME pays for one relocation case). Cleanest proof of willingness-to-pay; matches how they budget.
- **Challenge to per-move-only:** the category norm is subscription (ReloTalent from ~€299/mo; WorkFlex with 5,000+ HR users). A per-move-only model **under-monetizes an always-on accuracy engine** whose core value — rule-change monitoring, audit-readiness, live case history across corridors — is delivered *between* moves. Evolve to a **hybrid**: a light always-on retainer for the between-move value **plus** per-move fees. That's what converts a transactional tool into the recurring relationship the moat assumes.

---

## Journey staircase — where you actually are

v1 said "the very start of Phase 1 — Case Command exists as code; the love-it-AND-verifiably-correct test is next." **That's stale.** The engine is *built and shipped* (extractor, extract endpoint, review UI, eval harness, France→Norway golden set — all Done). The rung you're actually on is **operating it**:

- **You are here → Operate & prove.** Run the France→Norway corridor through the shipped engine end-to-end: extract → stage to review → you approve → commit a real eval report so the dashboard goes live and the moat KB is populated with verified facts. Gate: ≥95% correctness, 100% official-source, full non-obvious coverage, on *real* data. This is the "verifiably correct" rung made numeric.
- **Then → Scale corridors through the gate.** Each new corridor is discovered (clean official-URL list), extracted, verified, gold-set-scored — and only *then* trusted. Breadth at whatever pace the engine can certify.
- **Then → First believers → First dollars → Repeatable → Scale**, unchanged in spirit, but now every corridor you show a stranger is one you can *prove*.

---

## Audos integration boundary (unchanged and reinforced)

ReloPass's own stack (React/Vite + FastAPI + Supabase/Postgres on Render) is the **system of record and the moat**. Audos is a **top-of-funnel + lifecycle + source-discovery + prototyping layer** — never where the core product or PII lives. This session's cleanup reinforced it: the parallel code queue was cleared out of Audos, and the immigration routine is being reset to *discovery-only* (clean official-URL lists that feed the production extractor). Authoritative data lives in Supabase behind FastAPI; secrets never enter Audos client code; Autopilot stays off until past the "operate & prove" rung.

---

## Competitive positioning (why we win — one paragraph)

In a field of 158 where breadth and "AI-native" are table stakes, ReloPass wins on the two things almost nobody has: **the SME HR generalist as the buyer** (ignored by every tier) and **provable, maintained correctness as the product** (nobody publishes evidence-linked, independently-verified, freshness-monitored accuracy). We **ride** the rest of the shelf — housing (AltoVita/Blueground), movers (Shyft), tax/data (GTN/Mercer/AIRINC), filing (VisaHQ), and the HR record-of-truth (Workday/HiBob/Personio/Remote) — from a **neutral** position EORs and RMCs structurally can't hold. We **fear** exactly one thing — EOR absorption led by Deel — and we answer it with focus, neutrality, and proof, not feature parity.
