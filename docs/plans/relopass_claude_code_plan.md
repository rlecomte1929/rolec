# ReloPass — Claude Code Execution Plan
**Generated:** 2026-08-16 · **Repo:** `rolec` · **North star:** ship ES→IE (Andreas) and NO→FR (Denis) end-to-end.

This plan is written to be pasted into Claude Code (or driven by `relopass-dev-queue`). Every item carries **Goal · Plan · Specs · Metrics · Validation · Evals**. Execute in the order given. Stop for a human on any 🔴 Red item before merging.

---

## 0 · Global conventions (apply to every task)

**Stack.** Backend = FastAPI on Render service `rolec-eu` (`srv-d7ku8agjs32c7386fm4g`), API at `https://api.relopass.com`. Frontend = Vite app deployed as the Render Static Site named `Static Site` from `frontend/dist` (see `render.yaml`). DB = Supabase Postgres (pgcrypto enabled).

**Per-task workflow (never skip recon).**
1. `git switch -c fix/aiq-<id>-<slug>`
2. **Recon first** — read the exact files in *Specs* and confirm the current behaviour before editing. Task titles have been wrong before (see AT3 note); trust the code, not the label.
3. Implement following the *existing* pattern the Specs point at. No second code paths.
4. Run the *Validation* commands + `npx tsc --noEmit` (frontend) / `pytest -q` (backend) as applicable.
5. Run the relevant *Evals* (golden-case probes, §0.2) to prove no corridor regression.
6. Open a PR; update the Notion task (Status → Human Review, Final Validation Result → Passed/Partial, Execution Notes = what you did + probe output).
7. **Commit is mandatory** (relopass-dev-queue Phase 7).

**Autonomy tiers.** 🟢 Green = implement + self-close. 🟡 Yellow = implement + self-validate, leave a sample for Romain. 🔴 Red = implement on a branch, **stop before merge** and hand to Romain with the diff + probe evidence.

**Fix-skill routing.** UI → `relopass-fix-ui-bug` · API → `relopass-fix-api-bug` · Isolation/RLS → `relopass-fix-isolation-bug` · Feature/Infra → decompose first (`notion-decomposition`).

**Definition of Done (all items).** Acceptance criteria met + validation command green + no golden-case regression + PR merged + Notion updated + committed.

### 0.1 · Notion IDs (canonical, post-dedup)
The 14-Aug duplicate copies were archived. Use these surviving IDs when updating Notion:
`42→#1848 · 300→#1864 · 301→#1865 · 24→#1890 · 25→#1891 · 26→#1892 · 23→#1889 · 295→#1859 · 137→#1880 · 136→#1879 · 138→#1881 · 134→#1877 · 139→#1882 · 45→#1851 · 104→#1870 · 105→#1871 · 101→#1867 · 102→#1868 · 1746 · 103→#1869 · 106→#1872 · 130→#1883 · 1834 · [T18-D4]→#1888`.

### 0.2 · Golden-case eval harness (run after every corridor-touching change)
Set `T`=a valid HR bearer, `E`=a valid employee bearer, `C`=a Madrid→Dublin case id, `BASE=https://api.relopass.com`.

```bash
# ES→IE (Andreas) — requirements engine
node -e "fetch('$BASE/api/public/corridor-requirements?from=ES&to=IE&employee_type=PERMANENT&purpose=employment&nationality=ES').then(r=>r.json()).then(j=>console.log('EU',j.nationality_class,j.requirements.length))"   # expect EU_EEA, >=6
node -e "fetch('$BASE/api/public/corridor-requirements?from=ES&to=IE&employee_type=PERMANENT&purpose=employment&nationality=IN').then(r=>r.json()).then(j=>console.log('3C',j.nationality_class,j.requirements.length))"        # expect THIRD_COUNTRY, >=8
#   ASSERT: no requirement mentions "blue_card" for IE; the EU and third-country lists differ.
# ES→IE — settle-in pack has real content (no placeholders)
node -e "fetch('$BASE/api/resources/country?assignment_id='+process.env.A,{headers:{Authorization:'Bearer '+process.env.T}}).then(r=>r.json()).then(j=>console.log(j.sections.map(s=>s.key)))"
# ES→IE — Dublin housing curated
node -e "fetch('$BASE/api/recommendations/housing?case_id=$C',{headers:{Authorization:'Bearer $E'}}).then(r=>r.json()).then(j=>console.log('housing',Array.isArray(j)?j.length:j))"   # expect >=6
# ES→IE — advisors are IE-capable, no example.com
node -e "fetch('$BASE/api/advisors/match',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer $T'},body:JSON.stringify({origin_country:'ES',destination_country:'IE',purpose:'employment'})}).then(r=>r.json()).then(j=>console.log(JSON.stringify(j.advisors.map(a=>[a.name,a.contact_url]))))"
# NO→FR (Denis) — EEA free-mover, immigration ~ none
node -e "fetch('$BASE/api/public/corridor-requirements?from=NO&to=FR&employee_type=LTA&nationality=NO').then(r=>r.json()).then(j=>console.log('NOFR',j.nationality_class,j.requirements.length))"  # expect 5 EEA rows
```
A change is **regression-free** only if every probe above still returns its expected shape.

---

## PART 0 — Things only Romain does (config/decisions, not code)

### ITEM 300 — `IMMIGRATION_ENCRYPTION_KEY` ✅ DONE (key confirmed set on `rolec-eu`, 2026-08-16)
**This is the full step-by-step you asked for — retained as reference; the key is already set, so only the verification (step 5) remains.** The vault encrypts the passport number with **Postgres pgcrypto** — `pgp_sym_encrypt(value, key)` / `pgp_sym_decrypt(ciphertext, key)` (see `backend/app/services/immigration_service.py` and `ocr_passport_extractor.py`). The "key" is therefore a **passphrase string**, *not* a fixed-length AES/Fernet key — any high-entropy string works. **Status: the key is already set on the `rolec-eu` service (confirmed 2026-08-16), so the vault is live** — encrypt-on-write and decrypt-on-read are active. (Note: some in-code comments still say "unset in production" — those are now stale.) The only remaining action is the **verification** in step 5.

**1 — Create the key (generate a strong passphrase).** On your Mac, run either:
```bash
openssl rand -base64 48
# or
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```
Copy the output. That single line *is* the key.

**2 — Store it in two places:**
- **Your password manager / secrets vault first** (1Password, etc.), labelled `ReloPass IMMIGRATION_ENCRYPTION_KEY (prod)`. This is critical: pgcrypto needs the *same* passphrase forever to decrypt what it encrypted. Lose it and every stored passport becomes permanently unreadable.
- **Render** → service `rolec-eu` → **Environment** tab → **Add Environment Variable** → Key `IMMIGRATION_ENCRYPTION_KEY`, Value = the passphrase. Set it on the **service** tab, **not** an env group (matches this service's convention).

**3 — Redeploy.** Render env changes do **not** hot-reload. Trigger **Manual Deploy → Deploy latest commit** on `rolec-eu` so the running process picks up the var.

**4 — How it's called (for your understanding / verification).** The backend reads it with `os.environ.get("IMMIGRATION_ENCRYPTION_KEY")` in `immigration_service.py`, `ocr_passport_extractor.py`, and `prefill_engine.py`, then passes it straight into `pgp_sym_encrypt`/`pgp_sym_decrypt`. So the moment the var is present + redeployed, uploading a passport encrypts on write and decrypts on read — nothing else to wire.

**5 — Verify (Definition of Done):**
- Upload/OCR a passport on a test case → the stored `imm_employee_profiles.passport_number` column is **ciphertext** (starts with the pgp armor bytes, not the digits).
- The employee-facing intake profile endpoint returns the **decrypted** value.
- Pre-existing rows: run a one-off audit — `SELECT count(*) FROM public.imm_employee_profiles WHERE passport_number IS NOT NULL;` — and confirm none are legacy **plaintext** from before the fail-closed fix. If any exist, encrypt-in-place or purge them (don't leave Art. 9 data in the clear).
- Confirm pgcrypto is enabled: `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (Supabase ships it).

**Metrics:** 0 plaintext passport rows; 100% of new uploads stored as ciphertext; decrypt round-trip works on the employee endpoint.
**Then:** record the decision + date on Notion #1864 and set it to Done. Unblocks **#295** (passport extraction UI).

> **Also in this bucket (Romain actions surfaced by the Human Review pass):**
> - **#1842 — approve the 3 France EEA free-mover rows** at `/admin/countries` (Denis' NO→FR track). Verify: `GET /corridor-requirements?from=NO&to=FR&employee_type=LTA&nationality=NO` → 5 EEA rows.
> - **#45 — Geoapify: PARKED** (Romain, 2026-08-16) — geocode autocomplete stays off; Push-A #139 ships its curated neighbourhood data without live geocoding.
> - **#1832 / #1845 — corridor fact review + "verified" sign-off:** these need your human fact-by-fact judgement; they stay in Human Review by design.

---

## PART 1 — Item 42 · Upgrade AI backbone to Claude Sonnet 5 🟢 (Notion #1848 → Ready for AI)

**Savings verdict:** ✅ Proceed. The task records intro pricing of **$2 / $10 per Mtok through 31 Aug 2026** with near-Opus agentic quality — a ~40% inference-cost cut versus the current backbone. Greenlit, **gated** on the checks below (do not merge if the console price or a regression fails the gate).

- **Goal:** every backend Claude call uses the Sonnet 5 model string; cost drops materially; zero prompt regressions in the relocation-coordinator flow.
- **Plan:**
  1. Confirm the **exact** current model string(s) in backend config and the **exact** Sonnet 5 model ID from the Anthropic console (do not assume `claude-sonnet-5` verbatim — verify the live ID).
  2. Pull last-30-day token volume from the Anthropic console; compute projected $/mo at old vs new pricing. **Gate:** proceed only if net cheaper.
  3. Replace the model string in all backend config/model-router files (grep for the current ID; there should be a single source of truth — if not, centralise it).
  4. **Adaptive thinking is ON by default in Sonnet 5** — for any flow that needs deterministic output, set `thinking: {type: "disabled"}` explicitly.
- **Specs:** model-string config / LLM router in `backend/` (grep the current model ID). Keep a one-line revert ready.
- **Metrics:** projected $/mo saving ≥ 30%; coordinator-flow eval pass rate unchanged; console shows Sonnet 5 usage.
- **Validation:** full E2E suite green; run the relocation-coordinator happy path and diff outputs against a Sonnet-4 baseline for regressions.
- **Evals:** golden-case harness (§0.2) unchanged; a 10-prompt coordinator regression set scored equal-or-better; latency within budget.
- **Rollback:** revert the model string (single commit) if quality or cost regresses.

---

## PART 2 — Item 301 · HR dashboard — decision + UX 🔴 (Notion #1865)

### Judgment call (decided): **CONSOLIDATE into `frontend/` — do NOT deploy `apps/hr-dashboard` as a second site.**
**Why.** `render.yaml` deploys exactly one Static Site (`frontend/dist`). `apps/hr-dashboard` is a richer, never-deployed HR-only app (`features/cases`, `case-detail`, `pdf-viewer`, `bbox-overlay`, `resolution`) that already targets the correct API. Standing it up as a *second* live site would (a) fragment HR across two URLs — the opposite of the coherent, navigable HR experience you want, and (b) risk the `render.yaml` duplicate-service footgun the file explicitly warns about. One app = one nav model, one session, one place for every HR function.

**301a — Port & retire (the consolidation).**
- **Goal:** the richer HR surfaces live inside the deployed `frontend/` app against the correct backend; `apps/hr-dashboard` is deleted.
- **Plan:** recon both apps → identify the surfaces unique to `apps/hr-dashboard` (case-detail, PDF viewer + OCR bbox review, resolution workflow) → port them into `frontend/src/features/case/` reusing frontend's auth/router/session → point them at the correct endpoints → remove `apps/hr-dashboard/**` and its `hr-dashboard-build` CI job → confirm `render.yaml` still defines a single `Static Site`.
- **Specs:** `apps/hr-dashboard/src/{features,pages,routes,lib/api.ts}`, `frontend/src/components/case/`, `frontend/src/features/`, `render.yaml`, `.github/workflows/ci.yml`.
- **Metrics:** 1 deployed HR app (not 2); 0 orphaned CI jobs; every ported surface loads against prod with a real HR login.
- **Validation:** `cd frontend && npx tsc --noEmit && npx vitest`; manual: case-detail + Documents show real rce data against prod.
- **Evals:** HR can open a case, view documents, and see the OCR/resolution surfaces — no dead ends; employee side unaffected.

**301b — HR navigation & UX pass (your actual want).**
- **Goal:** every HR function reachable via a clearly-placed button and a coherent persistent nav; no dead ends.
- **Plan:** run a walkthrough → map the HR IA into a persistent left-nav/top-bar with explicit sections — **Cases · Employees · Documents · Immigration · Vendors/Services · Company/Settings** → put primary actions (New case, Approve, Assign vendor, Upload) as buttons in predictable, consistent positions → add breadcrumbs + working back navigation → fix any screen that dead-ends. Use `design:design-critique` + `design:design-system` + the ReloPass brand voice for copy.
- **Specs:** frontend HR routing/layout shell; button/CTA components; nav component.
- **Metrics:** 100% of HR functions reachable ≤2 clicks from the HR home; 0 dead-end screens in the walkthrough; consistent primary-button placement across screens.
- **Validation:** click-through of the full HR journey (login → case → documents → immigration → vendors → settings) with no orphan states; `tsc` + component tests green.
- **Evals:** a scripted HR walkthrough (Playwright) that visits every nav target and asserts a rendered, actionable screen.

> 301b is a 🔴 UX task — bring the walkthrough + proposed IA back to Romain before large layout changes.

---

## PART 3 — Push B · Front-door P0s (do first, in this order)

### B1 · #1847 [AT3] Fresh employee registration 🔴
- **Goal:** a brand-new employee can register end-to-end; the AT3_FRESH Sentinel gate goes green.
- **Plan:** **open the newest failing AT3_FRESH run artifact and state, verbatim, what fails** before diagnosing (recent Sentinel labels were mislabelled — trust the artifact). Fix the first real failure on the registration path, re-run.
- **Specs:** registration/auth flow (frontend intake + backend auth). Confirm from the artifact which layer breaks.
- **Metrics:** AT3_FRESH passes on a truly fresh account; 0 downstream 500s on first login.
- **Validation:** re-run the AT3_FRESH Sentinel; manual fresh-email signup → dashboard.
- **Evals:** repeat with a second fresh email; confirm employee lands on a usable home, not a dead end.

### B2 · #1890 Wire the Documents "Upload" button 🟡 (UI)
- **Goal:** the header **Upload** button opens a working picker that delegates to the existing `onUpload(file, documentKey)` path — or is removed. No second upload code path.
- **Specs:** `frontend/src/features/platform-v2/documents/DocumentsScreen.tsx` (dead `onClick` ~L946; working `RowUpload` ~L186; `onUpload` prop ~L860), `useDocuments.ts`.
- **Metrics:** clicking Upload yields a file in the list with a non-required status; per-row Upload/Replace still works.
- **Validation:** `npx tsc --noEmit && npm test -- --testPathPattern=DocumentsScreen`.
- **Evals:** upload a doc → appears once (no double path), correct `document_key` sent.

### B3 · #1891 Split Documents "Outstanding" → Missing + In review 🟡 (UI)
- **Goal:** uploading a required doc drops **Missing** and raises **In review** immediately (no approval wait).
- **Specs:** `DocumentsScreen.tsx` (count derivation ~L898-902, chip counts ~L909, stat grid ~L971-990 — the grid is `repeat(4,1fr)`; update the template for a 5th tile). Update `DocumentsScreen` tests.
- **Metrics:** with 2 required docs, uploading both → Missing 0 / In review 2; chip counts + progress bar stay consistent.
- **Validation:** `npx tsc --noEmit && npm test -- --testPathPattern=DocumentsScreen`.
- **Evals:** counts reconcile against the doc list for missing/submitted/approved mixes.

### B4 · #1892 Deep-link the family/dependent roadmap CTA 🟡 (UI)
- **Goal:** clicking "Confirm family / dependent details" opens Dossier & Forms with `?form=<key>` expanded and in view. Don't route back to the intake wizard.
- **Specs:** `frontend/src/pages/employee/EmployeeCaseRoadmapPage.tsx` (L82-86 hint), `frontend/src/features/relocation-plan/task-card/relocationPlanCtaRouter.ts` (L115-126).
- **Metrics:** CTA lands on the expanded family form; existing `?doc=` deep-link behaviour unchanged.
- **Validation:** `npx tsc --noEmit && npm test -- --testPathPattern=relocationTaskCta`.
- **Evals:** both `?form=` and `?doc=` deep-links open the right, expanded target.

### B5 · #1889 Explain what Prepay covers 🔴 (decompose first — blocked on info)
- **Goal:** before any payment, the screen states what Prepay covers, what it saves, and what happens if declined.
- **Plan:** ⚠️ a full-monorepo grep on 2026-08-13 found **zero** matches for prepay/pre-pay/prepaid/top-up/wallet/credits. **First locate the surface** (ask Romain for the tester's screenshot/URL, ref in the task), then decompose: (a) locate → (b) value-prop copy (brand voice) → (c) implement at the point of ask.
- **Metrics:** no employee is asked to prepay against an unexplained benefit.
- **Validation:** manual — the prepay screen shows the explanation pre-payment.
- **Evals:** screenshot diff of the prepay step before/after.
- **Blocker:** get the tester URL/screenshot from Romain before coding.

### B6 · #1859 Surface passport extraction in the UI 🟡 (UI) — unblocked (#300 key is set)
- **Goal:** an upload control on the case screen calls the **existing** extraction pipeline and pre-fills form fields in an **editable review** state; nothing commits until the user confirms.
- **Specs:** frontend only — **reuse** the shipped pipeline (`docs/audos-card-extraction-panel.md`, PR #1772); read via `GET /api/hr/cases/{case_id}/documents`. Do NOT build a Claude Vision path or a Supabase Edge Function.
- **Metrics:** passport upload → editable extracted values; a no-extract doc renders "not yet processed"; nothing persists pre-confirm.
- **Validation:** `cd frontend && npx tsc --noEmit && npx vitest`.
- **Evals:** #300 is set, so end-to-end persistence works — verify the extracted passport persists as **ciphertext** post-confirm (see the Part-0 vault verification).

---

## PART 4 — Push A · Ship the Andreas (ES→IE) journey (in this order)

### A1 · #1880 [T18-05] Nationality never persists 🔴 (API)
- **Goal:** intake nationality persists; the EU-vs-third-country branch fires.
- **Specs:** `backend/intake_draft_to_case_draft.py` (mapping — verify), `backend/main.py` (`submit_assignment`, `_draft_to_relocation_profile`), `backend/app/routers/immigration_intake_profile*`. Break is downstream of the flat-draft→employeeProfile mapping.
- **Metrics:** nationality ES → `EU_EEA`; IN → `THIRD_COUNTRY`; not null.
- **Validation:** `cd backend && pytest tests/ -k "nationality or intake_nationality" -q`; `GET /api/employee/cases/{id}/intake-nationality` = ES.
- **Evals:** §0.2 EU vs third-country probes differ correctly. **Foundational — do first.**

### A2 · #1879 [T18-04] PATCH `/relocationBasics` 500 🟡 (API)
- **Goal:** the corridor-write endpoint returns 200 (persists) or a documented 4xx — never 500.
- **Specs:** `backend/app/routers/cases_write.py` (handler), `cases.py` (duplicate registration?), `scripts/check_router_registrations.py`. GET on the path 405s while PATCH is in OpenAPI — confirm the route is actually wired.
- **Metrics:** valid payload → 200 + persisted; malformed → documented 4xx.
- **Validation:** the task's `curl -X PATCH …/relocationBasics …` returns 200/4xx, not 500; re-read returns persisted values.
- **Evals:** round-trip write→read on a Madrid→Dublin case.

### A3 · #1881 [T18-07] Employee immigration view dead-ends 🟡 (API)
- **Goal:** `GET /api/employee/cases/{id}/immigration` returns 200 with a renderable state (not 404); HR has a working path to create the case.
- **Specs:** `employee_immigration_snapshot.py`, `immigration_status.py` (404 branch), `cases_write.py` (assign handler — implicit create?), `POST /api/hr/immigration/cases` (is it ever called in the normal flow?).
- **Metrics:** assigned+submitted case → 200; no "Contact your HR team" dead end.
- **Validation:** `node -e "fetch('$BASE/api/employee/cases/'+C+'/immigration',{headers:{Authorization:'Bearer '+E}}).then(r=>console.log(r.status))"` → 200.
- **Evals:** full employee immigration surface renders for a fresh assigned case.

### A4 · #1877 [T18-02] ES→IE zero rows in requirements engine 🔴 (Feature/RAG)
- **Goal:** the public corridor endpoint returns ≥6 (EU) / ≥8 (third-country) requirements for ES→IE at PERMANENT/LTA/STA, with correct branching and NO Blue Card.
- **Recon note:** the 14 approved IE rows (from the now-Done landing #1831/#1844) may already satisfy much of this — verify current output first, fill only the gap. Follow the Norway entries as the quality bar.
- **Specs:** `corridors/ES_IE/corridor.yaml`, `corridors/ES_IE/pathways/CSEP_2026/v1.yaml`, `supabase/migrations/` (seed into `public.immi…`).
- **Metrics:** ES→IE ≥6 EU / ≥8 third-country; EU list has no permit-chain noise; lists differ by nationality.
- **Validation:** the task's `node fetch …corridor-requirements?from=ES&to=IE…nationality=IN` → `THIRD_COUNTRY` + length.
- **Evals:** §0.2 ES→IE probes green for ES and IN.

### A5 · #1882 [T18-08] Dublin neighbourhood curation 🟡 (Feature) — geocode autocomplete deferred (#45 Geoapify parked)
- **Goal:** `housing` returns ≥6 named Dublin areas with rent bands + source; `schools` non-empty; geocode autocomplete works.
- **Specs:** `backend/app/routers/geocoding.py` (disabled flag), `predictions.py`/recommendations, `scripts/geocode_datasets.py`, `supabase/migrations/` (Dublin neighborhoods). **#45 Geoapify is parked**, so leave geocode autocomplete disabled and deliver the curated housing/schools/cost-of-living from the seed migration (no live geocoding required).
- **Metrics:** housing ≥6; schools >0. (Live-autocomplete metric deferred with #45.)
- **Validation:** the task's `node fetch …/recommendations/housing?case_id=$C` → ≥6.
- **Evals:** §0.2 Dublin housing probe green. Curation ships now; geocode autocomplete lights up whenever #45 is un-parked.

### A6 · #1870 HR-approved vendor reaches the employee 🔴 (API)
- **Goal:** a vendor HR approves for a destination+category appears in the matching employee Recommendations.
- **Specs:** destination-key resolution between HR curation (`Dublin|Ireland`) and the employee query (`Dublin, IE`/`IE`) — likely a normalisation mismatch.
- **Metrics:** HR-approved Dublin housing vendor shows for the Madrid→Dublin employee.
- **Validation:** manual HR-add → employee-see; a test asserting the join.
- **Evals:** approve→appear round-trip for 2 categories.

### A7 · #1871 ES_IE marketplace empty — allowlist Dublin + seed vendors 🟡 (Infra/DB, Otto-ready)
- **Goal:** Dublin (and Cork) allowlisted; a starter set of review-verified Dublin vendors across core categories; coverage matrix shows a non-zero IE column.
- **Specs:** existing destination-allowlist + vendor-seeding pattern (priority-corridor seeding). Keep vendors review-verified. Coordinate with A4/A5.
- **Metrics:** "Dublin isn't on your allowlist" gone; IE column non-zero; "Find verified vendors in Dublin" returns results.
- **Validation:** HR Vendor Management → Ireland/Dublin populated.
- **Evals:** employee Services page for the Dublin case shows vendors, not an empty state.

### A8 · #1867 ES_IE roadmap — wire CSEP_2026 step-graph 🔴 (Feature)
- **Goal:** the employee roadmap Immigration phase renders corridor-specific CSEP steps (2-yr contract → employer files CSEP with DETE → D visa → IRP/Stamp 1 Burgh Quay → PPSN → Revenue RPN), not the generic template.
- **Specs:** roadmap generator; keep the generic template as fallback. **Do NOT regress** the roadmap paywall (AIQ-1699/1692/1687) or HR↔employee plan sync (AIQ-1606).
- **Metrics:** ES_IE/VE/employment roadmap shows CSEP-named steps; other corridors unchanged.
- **Validation:** generate a roadmap for ES_IE/VE/employment and inspect the Immigration phase.
- **Evals:** a non-ES_IE corridor still renders its own steps (no cross-contamination).

### A9 · #1868 Register IE (route=employment) readiness template 🟡 (API)
- **Goal:** the HR Case Summary "Route / template readiness" no longer warns "No verified readiness template … for IE".
- **Specs:** existing readiness-template registration pattern (FR/DE/NO). Don't weaken the human-review fallback for genuinely unconfigured destinations.
- **Metrics:** ES_IE/employment case summary shows configured readiness; other corridors unchanged.
- **Validation:** open the HR Case Summary for an ES_IE/employment case.
- **Evals:** an unconfigured destination still shows the human-review fallback.

### A10 · #1746 [T18-06] Ireland settle-in pack 🔴 (Feature/Research)
- **Goal:** the IE country pack has real, sourced content (rent bands, ≥6 named Dublin neighbourhoods, cost-of-living with cited source+date) — no placeholder strings.
- **Specs:** `backend/app/routers/resources_activities.py` + country-pack assembly; IE resource seed migration (pattern: `scripts/seed_additional_countries.py`, `seed_resources_oslo.py`). Routing already resolves IE/Dublin.
- **Metrics:** 0 "will appear here"/em-dash placeholders; housing ≥6 named areas; cost_of_living cited.
- **Validation:** `python3 scripts/check_compliance_claims.py` + the task's `/api/resources/country` fetch.
- **Evals:** §0.2 settle-in probe returns populated sections.

### A11 · #1869 Immigration Q&A raw markdown + PII false-positive 🟡 (UI)
- **Goal:** answers render formatted HTML (no literal `##`/`|`); citation URLs intact (no `[REDACTED_PHONE]` on `2003-109`-style ids).
- **Specs:** markdown render in the answer bubble (frontend); narrow the phone-number regex in the PII/masking layer so hyphenated legal identifiers survive.
- **Metrics:** ES_IE/VE answer renders formatted; `emn.ie` source intact in Sources.
- **Validation:** ask an ES_IE/VE immigration question; inspect render + citations.
- **Evals:** a known legal-id string is not redacted; a real phone number still is.

### A12 · #1872 Mover recommendations corridor-filter 🟡 (API)
- **Goal:** Madrid→Dublin no longer surfaces Singapore movers as "best match"; either in-corridor movers or a coverage-gap empty state.
- **Specs:** recommendation query join on vendor service-area vs case destination ("Service Area" already scores; it isn't filtering).
- **Metrics:** 0 SG-only vendors for the Dublin case.
- **Validation:** open Movers recommendations for the Madrid→Dublin case.
- **Evals:** the mover probe shows corridor-appropriate results or an honest empty state.

### A13 · #1883 [T18-09] Advisor matching — IE-capable + no example.com 🟡 (API)
- **Goal:** `POST /api/advisors/match` for IE returns only Ireland-capable advisors (or an empty coverage-gap); no `example.com` contact URLs anywhere.
- **Specs:** `backend/app/routers/advisors.py` (match logic + seed). Separate (a) destination filtering from (b) placeholder seed data.
- **Metrics:** IE match = IE specialisms only; 0 example.com URLs served.
- **Validation:** the task's `POST /api/advisors/match` ES→IE probe.
- **Evals:** §0.2 advisor probe; a test asserts no example.com in any advisor payload.

### A14 · #1834 Add `non_obvious`/`timing` columns + wire serving 🔴 (API)
- **Goal:** surface Andreas' practical-realities block (PPS 40% emergency tax, 3-month payslips, non-Schengen, pets/TRACES) via new columns.
- **Specs:** additive migration; `public_corridor.py` + `requirements_builder.py` + `schemas.py` return `non_obvious`/`timing`.
- **Metrics:** corridor payload includes populated `non_obvious`/`timing` for ES→IE.
- **Validation:** migration applies; corridor endpoint returns the new fields.
- **Evals:** §0.2 ES→IE probe includes the practical-realities items.

### A15 · #1888 [T18-D4] Kill the invented "Oslo → Singapore" move plan 🔴 (Bug, currently Human Review)
- **Goal:** `MovePlan()` serialises `origin=''`/`destination=''`; `_extract_city` never substitutes a place name; the 1,377 stored rows are cleared via a **gated** backfill.
- **Specs:** `backend/schemas.py` (MovePlan defaults), `backend/app/services/hr_policy_resolver.py` (`_extract_city`), `backend/scripts/clear_invented_move_plan.py` (new, gated dry-run first), `backend/tests/test_moveplan_has_no_invented_default.py`. **Do NOT blanket-clear** `profile_json.movePlan` — only the two keys, only when the pair is exactly the invented one and the route columns contradict it.
- **Metrics:** 0 cases show Oslo→Singapore; real move plans preserved.
- **Validation:** the new unit test; dry-run the backfill, review counts, then apply.
- **Evals:** spot-check 5 real cases keep their true move plan; the invented pair is gone.

---

## Appendix — sequencing & parallelism
- **Serial, foundational:** B1 (registration) and A1 (nationality) gate the most downstream value — do them first in their lanes.
- **Parallelisable (independent files):** the UI items (B2–B4, A11) vs the API items (A2/A3/A6/A12/A13) vs data/content (A4/A7/A10) — safe to run as separate Claude Code worktrees (`relopass-conductor-check` will confirm).
- **Dependencies:** #295 (B6) ✅ #300 done · #139 (A5) curation unblocked; geocode autocomplete parked with #45 · A8/A9/A10 read best after A4 lands the corridor data.
- **After each merge:** run §0.2 golden probes. A green board on both ES→IE and NO→FR = Andreas and Denis are served.
