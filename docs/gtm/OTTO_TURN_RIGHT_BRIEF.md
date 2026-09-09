# ReloPass × Otto — turn-right brief (deck-translated)

Paste the **Execution prompt** block at the bottom into Audos as-is.
This file is the source of truth after translating the McKinsey “Rewired / full funnel /
churn / QBR” slides into ReloPass constraints.

**Otto does not push GitHub, does not write ReloPass prod, and does not launch ads.**
ReloPass owns ICP, offer, copy, and the qualified-lead definition.

Do not treat McKinsey client numbers (300% SQLs, −40% resignations, 20% churn, 80%
non-human IT chats) as ReloPass targets or as claims we have achieved. Steal the
**method**, not the percentages.

---

## What the deck actually changes in our instructions

| Slide idea | ReloPass translation | Do not |
|---|---|---|
| ~80% say AI made them productive; **6%** report meaningful P&L (≥5% EBIT) | Win = paying cases, expansion cases, employer retained. Hours saved is a vanity metric unless Finance signs an OKR | Report “we used AI” or digest drafts as impact |
| Revenue gains concentrate in **marketing/sales** and **product development**; software eng has the fattest >10% tail | Otto’s job is GTM artifacts + a steering memo. Product quality (served requirements) stays on the deterministic path with a human lawyer gate | Turn ReloPass into an IT helpdesk agent (“CASEE”) |
| Experimenting → piloting → **scaling** | We are still pre-scale. Run **baseline → 4-week pilot → measures-online**, like the SQL chart | Pretend we are in the 44% “already scaling” cohort |
| SQL indexed: baseline 100 → noisy weeks 1–4 → **all measures online** weeks 5–13, ~3× volume, conversion **held** | Hunting list + locked-copy Meta **previews** in weeks 1–4. Outbound on `hot` only after list quality holds. Segment B never counted as SQL | Optimise for click volume; blend A and B |
| Nordic roll-out of the same play | Second corridor / second country only after one paying case and a steering memo | Multi-country ads on a $174 wallet |
| BPO case: 16 use cases, 300% pipeline, **20% churn cut** via prediction + **intervention triggers** | **Three** use cases only: (1) hunt+enrich, (2) early-intervention on live employers, (3) next-case expansion. Triggers, not a 16-agent zoo | Agentify serving/immigration |
| Churn model: 11 inputs → likelihood next quarter + **rank by risk × customer relevance**; early intervention | Map inputs to ReloPass signals below. Output a **ranked intervention list**, not a model we cannot train | Invent 50,000 scored projects |
| Resignations −40% after a stable baseline | Analog = **employer / programme dropout and stalled cases**, not employee resignations. Need a baseline month before claiming a drop. July-style outliers are not the baseline | Copy −40% into ReloPass copy |
| High performers **redesign the workflow**; human-in-the-loop; track impact; leadership owns it | Ads: card-level copy approval. Requirements: serving/LLM isolation. Friday digest proposes; Romain edits ICP | Auto-publish ads or auto-approve facts |
| QBR: 1 input (**adoption**) + 4 outputs (quality, satisfaction/NPS, productivity, financial). Financial = **non-personnel $** with Finance OKRs | ReloPass quarterly read uses the same five columns. Productivity hours must not substitute for financial | Set NPS ambition >75 as a current claim |
| Rewired: **business-led roadmap** first, then talent / OM / tech / data / adoption | This brief *is* the business-led slice (sales + retention). Cursor folder is enablement, not the product | Start with silent IT prevention |
| AI under the workflow: Cursor folder + team room; 3 habits (orientation ≠ facts; route then read; update context) | Otto writes a **context file + provenance**. Numbers come from cited URLs. After the batch, update the steering memo | Invent headcount, corridors, or scores |
| IT: silent prevention, then AI-first support, humans last | ReloPass analog = policy alerts + stalled milestones in the HR digest **before** a sales save-play. Humans own immigration/tax | Imply ReloPass is legal advice |

---

## ReloPass churn inputs (early intervention)

Use these as the ** ReloPass-native** substitutes for the 11 McKinsey inputs.
If a field does not exist in what you can see, leave it null (`source_missing=true`).
Do not train or fake a model.

| McKinsey input | ReloPass signal |
|---|---|
| NPS | Test-drive / survey scores if present; otherwise skip |
| Interview tone | Support-ticket language (if provided in the task pack); otherwise skip |
| Client friction | Stalled milestones, open policy alerts, time-to-complete worsening |
| Tenure | Months since first case / first login |
| Consultant changes | Vendor churn on a case, if evidenced |
| Price model | Access tier if provided; otherwise skip |
| Missing information | Incomplete intake / unanswered qualifying questions |
| Fee:revenue | Skip unless Finance supplies it |
| Tickets | `support_tickets` count if in the pack |
| Claims | `case_outcomes.failure_reason` if in the pack |
| CRM activity | Digest unopened, no HR login, no second case |

**Outputs Otto may produce (research, not production scoring):**

1. Churn **likelihood band** for the next quarter: high / medium / low, with the signals used.
2. **Rank** = risk × employer relevance (ICP fit + expansion potential). High-risk + not-ICP is not a save play.
3. One **intervention trigger** per high-risk employer: digest note, next-corridor offer, or human call. Never an automated legal/immigration answer.

---

## QBR columns ReloPass will actually read

Calibrate quarterly. Otto’s memo fills **proposed** numbers with provenance; Romain signs.

1. **Adoption (input)** — % of target HR contacts who started or touched a case; segment size and geography named.
2. **Quality (output)** — stalled-case rate, first-pass requirement issues. Define per initiative.
3. **Satisfaction (output)** — do not invent NPS. If we lack a 10% sample, write `N/A`. Ambition >75 is a later bar, not a badge.
4. **Productivity (output)** — hours saved only if someone measured it. Never the headline.
5. **Financial (output)** — paying cases, expansion cases, employer retained. Non-personnel $ only. Align with a Finance OKR when one exists.

Headline that fails the 80/6 test: “AI improved productivity.” Headline that passes: “Segment A SQLs held conversion; N employers expanded; M at-risk employers got a human intervention.”

---

## Phasing (SQL chart, ReloPass-sized)

- **Baseline:** current `prospect_candidates` + test-drive intros. Index this as 100. Do not invent a 100.
- **Weeks 1–4 (pilot):** hunting list + Meta **PREVIEW_READY** with locked copy. Volume will bounce. Do not launch.
- **Weeks 5+ (measures online):** enrichment bands + outbound on `hot` + digest expansion on live employers. Only if week-1–4 list quality held (citations present, disqualifiers respected, A/B not blended).
- **Quality gate:** “very limited impact on conversion” — Segment A remains the only SQL; Segment B is an account list.

Wallet ~$174 cannot buy a 13-week SQL chart. If spend is still gated by ADS-1, stop at previews and the list.

---

## Three use cases (not sixteen)

1. **Hunt + enrich** — ICP hunting list, public-signal citations, `hot/warm/nurture/not_icp`.
2. **Intervention** — ranked at-risk *employers* (not relocating employees) with one trigger each.
3. **Expand** — next employee / next corridor / Total Rewards packaging for companies that already have a case.

Internal enablement (Cursor folder, context files, Friday digest) is Romain’s lane, not Otto’s product.

---

## Execution prompt (paste into Audos)

```
TASK: ReloPass turn-right — hunting list + Meta previews + steering memo + intervention rank
OWNER: Otto (Audos). ReloPass owns ICP, offer, copy, qualified-lead definition.
DO NOT: push GitHub; write ReloPass/Supabase prod; launch campaigns; rewrite locked ad copy; install an ad pixel; point ads at audos.com; invent facts, headcount, corridors, NPS, or scores; claim ReloPass hit 300% SQLs, −40% churn, or any EU AI Act status; describe ReloPass as a relocation service, agency, marketplace, or employee “journey”; blend Segment A and B in reporting; treat hours saved as P&L.

NORTH STAR (from the McKinsey 80/6 slide, translated)
Winners get P&L, not productivity theatre. Your artifacts must be usable to create Segment A SQLs, expand a live employer, or trigger a human save. If a deliverable only “uses AI”, it is incomplete.

WHAT YOU BUILD (three use cases only)
1) Hunt + enrich: 40–80 account hunting list.
2) Intervention rank: if (and only if) the task pack includes live-employer signals, a ranked list of employers for early intervention. If the pack has no live cases, output the schema and mark rows N/A — do not invent churn scores.
3) Steering memo: who we hunt / what we promise / what we expand — plus a QBR stub.

You do not close deals, send the HR digest, edit prospect_icp_config.py, or serve requirements.

ICP FILTERS (do not widen)
Size: 50–1,000 first (50–5,000 allowed; no 1,000–10,000 hunt until one paying case).
Sectors: Tech/SaaS, Engineering & R&D, professional services, life sciences, financial services, manufacturing with global footprint. Beachhead: French employers moving staff to Norway when public signals exist.
Regions: Europe (FR, UK, DE, NL, Nordics) first.
Strong signals (need ≥1, with URL + quote ≤25 words): relocation/visa/international-assignment job posts; new international entity; funding with international hiring language; public Head of Global Mobility; multi-country careers pages.
Titles in order: Head of Global Mobility, Global Mobility Manager, International HR Director, Head of People, CPO, People Ops Lead, Head of Total Rewards.
DISQUALIFY: <25 with no international hiring; single-country no expansion; relocation/immigration firms; EOR/PEO (Remote, Deel, Oyster); SIRVA, Cartus, CapRelo, Sterling Lexicon, Santa Fe, Crown World Mobility.

DELIVERABLE 1 — Hunting list
NDJSON + MANIFEST (schema, count, GCS URL). Chat is not the deliverable. Count must match.
Each row: company, domain, HQ country, employee-band, sector, 1–2 cited strong signals, best title (no private email unless public), corridor guess or null, band hot/warm/nurture/not_icp, source_missing true/false.
Never fill a gap. Prefer careers pages, filings, named news. Reject unofficial gossip.

DELIVERABLE 2 — Meta PREVIEW_READY only (do not launch)
Path: delegate_ad_generation → PREVIEW_READY → STOP.
Locked copy only (titles ≤40 / bodies ≤100, already measured).

Segment A → https://relopass.com/mobility-teams/  (trailing slash required)
A1 Relocation fails in the handoffs. | Cases, documents, and providers on one record. Built for HR and mobility teams.
A2 Relocation still runs on spreadsheets | Move every case onto one record. Status, owners, and deadlines in one view.
A3 Know which relocation is late, today | Deadlines, documents, and provider tasks tracked against every case.
A4 Vendor tasks tied to the case | Not lost in inboxes. HR, employees, and providers coordinate on one record.
A5 Every relocation case, one status view | Track cases, documents, and vendor tasks without chasing inboxes.
A6 Start with one relocation case | Structure how you run relocation. See the system before you commit.

Segment B → https://relopass.com/relocation-checklist/  (trailing slash required)
B1 Moving for work? Know what's required | A structured checklist of documents and deadlines for your relocation.
B2 Your relocation, one clear checklist | See required documents, deadlines, and who owns each step. Share it with HR.

utm_source=meta (never chatgpt). Preserve query strings. utm_content=[angle].
No pixel. If a pixel is required to buy, STOP. Ads on relopass.com only.
Segment B hint MUST end: Exclude anyone seeking legal, immigration, or tax advice.
If you cannot buy EU/UK, say so; do not silently drop FR→NO.
Weeks 1–4 of any live test are expected to be noisy. Do not declare a 3× SQL win from previews.

DELIVERABLE 3 — Steering memo + QBR stub + intervention rank
Markdown file with provenance (URL next to every number). Three habits: (1) AI for orientation, not facts — open the source for numbers; (2) route then read; (3) update this memo after the batch so it stays current.

Sections:
A. Who we hunt — 3 signals to BUMP, 2 to DROP, with evidence. Do not edit ReloPass code.
B. What we promise — which locked angle A1–A6/B1–B2 matches pain you found. No new ad copy.
C. What we expand — next employee / corridor / Total Rewards packaging. No gamification.
D. Intervention rank — columns: employer, risk band (H/M/L), relevance (ICP/expansion), signals used, one trigger (digest / next-case offer / human call). Empty pack → schema only.
E. QBR stub — Adoption, Quality, Satisfaction, Productivity, Financial. Use N/A with a reason rather than a fake NPS. Financial = paying/expansion/retained employers, not hours.
F. Phase read — are we in baseline, week-1–4 pilot, or measures-online? What would falsify quality (conversion of Segment A)?

REGISTER — reject at preview, do not fix-and-approve
Banned: revolutionary, game-changing, seamless, powerful, supercharge, unlock, end-to-end, journey, adventure, exciting chapter, robust, best-in-class.
Banned imagery: suitcases, airplanes, passports-on-maps, airport families.
No visa/immigration/tax OUTCOME claims. No EU AI Act Ready/compliant/certified. Never call ReloPass high-risk AI.
You MAY describe controls: human reviews AI recommendations; decisions logged; answers grounded in the customer’s policy and cited; PII masked before model calls.

QUALIFIED LEAD (reporting only)
A: work email on company domain + volume band answered + employer not an agency. 6–20 / 21–50 / 51–200 / 200+ = sales-qualified; 1–5 counted separately.
B: work email + “Who do you work for?” with a real employer. NEVER a sales lead.

DONE WHEN
Manifest count = NDJSON count; every hot/warm row cited or source_missing; Meta PREVIEW_READY or a written block; steering memo has bump/drop/angle + QBR stub + phase; no launch, no pixel, no invented P&L.

STOP AND ASK ROMAIN IF you need to change locked copy, install a pixel, point at audos.com, target RMCs/EOR, launch to spend the credit, or report McKinsey client percentages as ReloPass results.
```
