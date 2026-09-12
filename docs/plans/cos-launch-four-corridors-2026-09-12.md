# CoS plan — Demo week, four corridors

Written 2026-09-12. Demo ~15 Sep. Grounded in `origin/main` (`1ea260d4`),
`docs/corridors/README.md`, corridor YAML under `corridors/`, and the Notion
KEEP list after the 2026-09-12 queue cleanup. Do not reverse that cleanup.

This is an execution plan. It does not invent product, routes, tables, or
compliance status.

## 1. North star

Walk Andrea (ES→IE) and Denis (NO→FR) end to end on **already-served, cited
facts**; treat FR→NO as the inbound wedge and IE→ES as authored-not-served
until a filled CVR exists — no new corridors, no paywall, no invented price.

## 2. Four corridors vs launch-ready

**Confirmed IDs:** `IE_ES`, `ES_IE`, `NO_FR`, `FR_NO`.

Evidence, not guesswork:

- Registry has **13** YAML profiles (`corridor_registry.list_corridors()`).
  A profile is not a served corridor (`docs/corridors/README.md`).
- Documented in-repo: IE→ES and FR→NO only (`docs/corridors/README.md` table).
- Live-demo pair: ES→IE (Andrea) + NO→FR (Denis)
  (`docs/otto/andrea-denis-brief-2026-08-21.md`,
  `docs/otto/extraction-and-campaign-master-plan-2026-08-21.md` “Rich, live-demo”).
- FR→NO is the knowledge-layer golden corridor and Norway seed wedge
  (`docs/corridors/fr-no/QBR-knowledge-layer.md`,
  `backend/seeds/requirements/norway.yaml`).
- IE→ES is the only corridor with a sha256-pinned requirement batch, and it
  is **unapplied + unapproved** (`docs/corridors/ie-es/README.md`).
- Otto KEEP maps 1:1 onto this set: 2314 + dest 2061 (ES→IE / Andrea),
  2311 + dest 2067 (NO→FR / Denis), 2313 (IE→ES CVR), 2160 (live-move).
  FR→NO has no extra Otto KEEP card; it is already the inbound seed.

**Rejected as the fourth this week:** `IN_DE` (old Tier-A, 0 non-obvious on
the pathway), `FR_SG` / `US_EC` (Adrien / Abraham YAML only; no KEEP Otto
card), `FR_ES` (structural mirror for IE→ES, not a demo case).

Launch-ready in this repo means all four: YAML profile; **approved**
`requirement_items` (the only rows `requirements_builder` serves); a CVR
with section 6 filled; Otto card only if a research gap remains.

| ID | Pair | YAML | Approved items served? | CVR | Otto KEEP | Launch-ready? |
|---|---|---|---|---|---|---|
| `IE_ES` | Ireland → Spain (free movement) | Yes (`corridors/IE_ES/corridor.yaml`, pathway `ES_FREEMOVE_2026`) | **No.** 25 rows in NDJSON + generated migration `20261108000000_ie_es_requirement_items.sql`; all `review_status='pending'`; migration **not applied**. Opening a case returns profile + pathway, zero requirement rows. | Template only: `docs/corridors/ie-es/CVR-TEMPLATE.md` — **NOT STARTED**. No `CVR.md`. | **2313** Blocked human (sit-down). Do not approve without it. | **No** |
| `ES_IE` | Spain → Ireland (Andrea, CSEP / TCN) | Yes (`corridors/ES_IE/corridor.yaml`, pathway `CSEP_2026`). `status` not SME-verified. `origin_facts: []`. | **Partial, destination-keyed.** Ireland catalog rows are already `approved` and serving (AIQ-1845 notes 29 Ireland rows approved as of 2026-08-21, including the AIQ-2027 VE→IE promote). No ES_IE corpus chunks. Counsel doc: 12 Ireland rows are `needs_lawyer_review` **and** already serving. | Named `andrea-es-ie` in docs; **no CVR file in this checkout**. Only the IE→ES template exists under `docs/corridors/`. | **2314** TCN (pending-only). Dest **2061** Andrea. | **No** — demo-walkable on served Ireland facts, not CVR-complete |
| `NO_FR` | Norway → France (Denis, returning EEA) | Yes (`corridors/NO_FR/corridor.yaml`). **`status: authoring`.** Pathway `RETURNING_EEA_CITIZEN_2026`. | **Partial.** `facts.yaml` binds 4 origin + 4 dest refs; dest facts become FR `requirement_items`. France seed is US→FR VLS-TS plus a small EU/EEA establishment set. Counsel: 3 France flagged rows already serving; 2 Denis COUNSEL rows **cannot** be approved until attested. | None in repo. | **2311** gap (audit `facts.yaml` first). Dest **2067** Denis. | **No** — demo-walkable on served FR facts; corridor still authoring |
| `FR_NO` | France → Norway (inbound wedge) | Yes (`corridors/FR_NO/corridor.yaml`, pathway `EEA_FREEDOM_2026`). Thin `facts.yaml` (1 origin + 2 dest). | **Partial / unverified in this checkout.** `norway.yaml` is the wedge seed (skattekort, D-number, police/EEA). New seed writes land `pending`; older NORWAY rows may already be approved (AIQ-1845: 10 NORWAY `verification_status='verified'`, attestation null). Live pending vs approved needs a read-only DB query — QBR stub marks that **N/A**. | None. QBR stub only (`docs/corridors/fr-no/QBR-knowledge-layer.md`). | No dedicated KEEP card. Do not invent one this week. | **No** — walk the wedge; do not claim a completed CVR |

**Demo honesty rule:** show ES→IE and NO→FR (and FR→NO if the Norway catalog
renders) on **approved** rows with citations. For IE→ES, say the 25 facts
exist and stay unserved until CVR + human approve. Do not flip `pending` →
`approved` in the next 72 hours.

## 3. Sequence — next 72 hours

Today is Saturday 12 Sep. Demo ~Monday 15 Sep. Three clocks only.

### Clock 1 — remaining Saturday 12 Sep (human first)

| Who | Do | Do not |
|---|---|---|
| **Human (Romain)** | Review PR #2322 for KEEP Human Review **2302 / 2303 / 2306 / 2309 / 2310 / 2315**. Merge only if the PR is the artifact. | Do not change those statuses except a comment. Do not un-archive the 32 or un-park the 24. |
| **Human** | Book the **2313** IE→ES CVR sit-down (name, time, corridor case). Copy `CVR-TEMPLATE.md` → start `docs/corridors/ie-es/CVR.md` only after the session. | Do not approve the 25 IE→ES rows. Do not apply the IE→ES migration to prod this weekend. |
| **Human** | Comment on **2308** (Concierge): a price, or “no price this week.” | Do not implement a price. |
| **Human** | Comment on **2135** (who pays): name the payer, or confirm paywall stays off for Demo. | Do not turn the paywall on. Parked P0 stays parked. |
| **Engineering** | Execute **2156 / 2157** (invented citations) — Ready for AI. Kill fabricated `source_url`s on served rows before a prospect clicks them. | Do not add a citation to make a row look complete. Empty + honest beats a invented host. |
| **Engineering** | Leave **2307** (upload repro) in Needs Decomposition. | Do not split the card. |

### Clock 2 — Sunday 13 Sep (Otto + one live walk)

| Who | Do | Do not |
|---|---|---|
| **Otto** | **2311** NO→FR: gap table vs `corridors/NO_FR/facts.yaml` + `RETURNING_EEA_CITIZEN_2026`. Research only missing topics. Candidates `pending`. | Do not re-research the corridor. Do not mark approved. Do not treat Denis as TCN. |
| **Otto** | **2314** ES→IE TCN: four pending items (permit does not transfer; IRP as check-not-asserted; SS tail only with a cited host; PPS/Revenue). Hosts: DETE / ISD / Revenue. | Do not mirror IE→ES free-movement facts onto ES→IE. Do not approve. |
| **Otto** | Dest KEEP: **2061** Andrea, **2067** Denis, **2160** live-move validation. Candidate / pending only. | Do not promote to approved. Do not open parked Otto cards. |
| **Human** | One logged-in walk of Andrea ES→IE and Denis NO→FR on prod (or a provisioned test-drive with `?corridor=ES_IE` / `NO_FR`). Write what broke in a comment on 2160. | Do not “fix” an empty pillar by inventing a fact. Do not demo IE→ES as served. |
| **Engineering** | If #2322 is approved, merge. Then stop. | No new feature PRs. No `supabase db push`. No router-only-in-`app/main.py`. |

### Clock 3 — Monday 14 Sep → Demo (~15 Sep)

| Who | Do | Do not |
|---|---|---|
| **Human** | Demo script: Andrea (permit / IRP / emergency tax) + Denis (EEA return / DPAE / PAS) + optional FR→NO skattekort / D-number. Cite the official URL on screen. | Do not claim EU AI Act status, “compliant,” “certified,” or high-risk AI. Describe controls only (human review, citations, PII mask). |
| **Human** | If 2313 happened: commit filled `docs/corridors/ie-es/CVR.md` (section 6 Yes/No). Still do not bulk-approve the 25 until counsel closes the two treaty rows. | Do not serve unreviewed IE→ES facts to make the fourth corridor “look done.” |
| **Engineering** | Hotfix only what the Sunday walk broke (citation 404, wrong nationality class, empty screen). | No Concierge, no paywall, no new corridor YAML, no Next.js (AIQ-2040 rejected). |

**Done-for-Demo (minimum):** two named people can finish a case on ES→IE and
NO→FR without a dead end or a invented citation; FR→NO wedge items that are
already approved still render; IE→ES is explained as pending. Anything else
is after Demo.

## 4. Explicit NON-goals

- **Parked Otto / parked P0–P3** from the 2026-09-12 cleanup (24 parked). Do
  not unpark for Demo week.
- **Social research** and any new destination playbook outside the four IDs.
- **EU AI Act status claims** in Demo copy, titles, PDFs, or badges. CI
  (`scripts/check_compliance_claims.py`) fails a prohibited claim. Describe
  what the controls do; claim no status.
- **Reversing the cleanup:** 32 archived, 1 rejected (AIQ-2040 Next.js).
- **2308 price implementation.** Comment only.
- **2135 paywall on** until a named payer exists.
- **Splitting 2307.**
- **New public tables, `cvr_records`, waitlist, `/admin/cvr/*`.** CVRs are
  markdown under `docs/corridors/`.
- **Applying the IE→ES load or flipping `review_status`.** Pending-not-served
  is the system working.
- **Corridors 5–13** (`IN_DE`, `FR_SG`, `US_EC`, `FR_ES`, stubs). Profiles
  may stay; they are not Demo scope.
- **`supabase db push`** against prod.

## 5. Decision log needed from Romain

Comment on the existing cards. Do not change KEEP statuses except those
comments.

| Card | Question | If unanswered by Demo |
|---|---|---|
| **2308** Concierge — Needs Human Clarification | What is the price, or is Concierge off-script this week? | Concierge stays unspoken. No number in the product. |
| **2135** who pays — Parked P0 | Who is the payer (employee / employer / ReloPass)? | Paywall stays **OFF**. Do not collect a card. |
| **2313** IE→ES CVR — Blocked human | When is the sit-down, and who is the mover? | IE→ES stays unserved. Demo uses the other three walks plus an honest “authored, not approved” line. |

After Demo, the same three answers still gate Concierge, checkout, and
whether the 25 IE→ES rows may ever be approved.
