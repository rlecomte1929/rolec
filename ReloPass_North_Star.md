# ReloPass — North Star

> Canonical summary of the five locked pillars from the Audos vision review.
> Company name is **ReloPass** (Otto's auto-namer kept reverting this to "GlobeIQ" — it's wrong everywhere it appears).

---

## 1. Who — the customer

**HR generalists at SMEs**, personally responsible for an occasional high-stakes international move that's nobody's full-time job.

Sharpest avatar: someone facing their **first or second** relocation — aware enough to be scared, not experienced enough to be calm. Relocation is not their domain and never will be; it's a stressful side-quest on top of their real job.

**Not** the global mobility manager / enterprise specialist. Reasons: the core value ("knows things I don't") doesn't land for an expert who already knows; a dedicated mobility *function* is an enterprise thing, so "mobility manager at an SME" barely exists; and per-move pricing fits a rare-mover, not a pipeline.

## 2. Problem — kills the not-knowing

**It sucks that** an HR generalist gets handed a high-stakes international move that's nobody's full-time job — and the thing that sinks them isn't the work they can see coming, it's the requirement they didn't know to look for, surfacing in week seven when it's already too late to fix.

Personal responsibility is the **amplifier** (it's on *you*). The **blade** is the invisible requirement. The product relieves the not-knowing — it does not remove the accountability — which is exactly why it's neither a staffing agency nor a compliance tracker.

## 3. Solution — Case Command

Case Command, **France → Norway** corridor, **depth over breadth**.

First-mile action: **"surface the unknowns."** HR opens a case (country pair + employee type) → a structured move timeline appears with non-obvious, corridor-specific requirements flagged **inline** (e.g. D-number, the tax card/skattekort needed *before* first pay, police/EEA registration, EEA-but-not-EU quirks).

The bar: at least one flagged requirement they wouldn't have known to look for without a specialist — and it's accurate. The relief is going from **blind to sighted** — week-seven ambush made visible in week one.

## 4. Expansions — what we deliberately do NOT build

**Feature no's (v0):** no Move Roadmaps, no broad corridor coverage, no vendor management, no employee-facing features.

**Strategic no's:**
- **Not a done-for-you agency** — the trap every compliance-adjacent tool falls into. A generalist in pain will ask us to just handle the move; saying yes makes us a low-margin services firm with no moat. The product makes her *competent*; it doesn't take the move off her plate.
- **Not for the specialist / enterprise** — no pipeline dashboards or power-user features.
- **Not a benchmark / community play early** — data effects are sequenced last; they need volume we won't have.
- **No subscription billing in v0** — per-move only.

## 5. Lasting Value — the moat

Three layers that compound, **trust as the throughline**:

1. **Verified corridor knowledge graph** (country-pair × employee-type × current requirements). The real asset is the *maintenance engine* — rules decay constantly, so a copied snapshot rots on day one. Being reliably, verifiably right is the edge.
2. **Case Command as system of record** — once HR's cases, deadlines, and history live here, switching means re-entering everything and re-trusting a new source on high-stakes compliance.
3. **Data effects, last** — at volume, real outcomes sharpen flagging and unlock anonymized benchmarks. A payoff of layers 1–2, not a substitute.

**Two-year competitor test:** to beat ReloPass, a competitor must do three things at once, from behind — match the knowledge *and keep it current*, earn time-based trust they can't buy, and displace an embedded system of record. **Honest caveat:** a well-resourced incumbent *could* fund the maintenance — so the real moat is the full stack aimed at the SME generalist they're structurally built to ignore. Focus is the part money can't shortcut.

---

## Pricing

- **Validation unit (now):** one SME pays for **one relocation case** (per-move). Cleanest proof of willingness-to-pay; matches how they budget relocations.
- **Evolution (later):** hybrid — a light always-on retainer for between-move value (rule-change monitoring, audit-readiness, live case history) **plus** per-move fees. This is what converts a transactional tool into the recurring relationship the moat assumes.

---

## Journey staircase

**Phase 1 · Build & love it** — build Case Command → use it yourself on a real France→Norway scenario. Gate is two-part: **love it AND verifiably correct.** The Norway verification pass is a hard rung, not a nice-to-have — in compliance, one wrong flag to an external user destroys the trust that is the moat.

**Phase 2 · First believers** — one HR generalist (not you) tries it → real feedback → a stranger who found you via an ad tries it → 5 people total → feedback from 5. Loops scoped to the **"surface the unknowns" moment** (minutes to evaluate), not the full relocation (weeks).

**Phase 3 · First dollars** — 1 SME pays for one case → 5 paying → 10 paying. *(Flagged experiment at paying_10: when do repeat/retained accounts become the headline metric, since per-move count can mask episodic demand?)*

**Phase 4 · Repeatable** — 25 → 50 → 100 paying.

**Phase 5 · Scale** — 250 → 500+.

**You are here:** the very start of Phase 1 — Case Command exists as code; the "do I love it AND is it verifiably correct" test is the next rung.

---

## Audos integration boundary

ReloPass's own stack (React/Vite + FastAPI + Supabase/Postgres on Render) is the **system of record and the moat**. Audos is a **top-of-funnel and lifecycle layer**, not a place the core product lives.

**Build-here vs build-there:**

- **Stays on ReloPass (FastAPI / Supabase / Render):** the core product — secrets, custom auth, inbound webhooks, the real Postgres schema and migrations, business logic, server-side Stripe/Meta, CI/CD, and all relocation PII. This is the system of record; do not fragment it.
- **Build on Audos (real leverage):** the landing/marketing page, Meta ads loop, CRM + Boosters for nurture, analytics/funnels, and lightweight prospect-facing or internal coordinator UIs — *as long as authoritative data lives in Supabase.*

**Integration architecture (one-directional contract):**

```
Supabase/Postgres  ←  FastAPI (Render)  ←—HTTPS—→  Audos app (React)
 (system of record)   (secrets, auth,             (marketing site, CRM/
                        webhooks, business          Boosters, ads, light UIs)
                        logic, Stripe/Meta)
```

Audos apps call ReloPass over HTTPS for any authoritative data. ReloPass never depends on Audos. Secrets never enter Audos app code (it's client-side React).

**The load-bearing unknown:** whether an Audos sandbox app can make an outbound `fetch()` to the ReloPass FastAPI origin. If yes → live integration. If egress is blocked → Audos becomes a separate marketing/CRM island with periodic contact-export sync. **Resolve via a 10-line egress probe before architecting anything.**

**Phase discipline (don't let Audos's tools pull you off sequence):**

- Audos's headline levers — Boosters, the ads loop, Autopilot — are **Phase 2–3 growth/lifecycle**, not Phase 1. Driving traffic or automating nurture onto an unverified product spends money and trust (the moat). Build only the **landing page** on Audos for now.
- The milestone-drip Booster (off `relocation_tasks`) is an **employee-facing lifecycle feature → v1, not v0.** Good idea, wrong phase.
- **Autopilot:** keep deliberately **off** until past Phase 1 — nothing should act unsupervised on an unverified product.

**PII / GDPR boundary:** all relocation PII (passport, D-number, case details) stays in Supabase behind FastAPI — never in Audos. If contacts ever sync into the Audos CRM, Audos becomes a **sub-processor of personal data** → add it to `docs/security/PRIV-004_sub-processor_register.md` and confirm its hosting region + DPA *before* any contact flows. Resolve this before touching Boosters.

**Methodology note:** the patterns Otto suggests copying (orchestrator + stateless specialist subagents, trigger-loaded skills, deferred tool loading, a separate verifier that never lets the builder self-certify) are already running in the ReloPass workflow (Notion queue, `relopass-*` skills, the e2e-test / review-validator split). No gap there.
