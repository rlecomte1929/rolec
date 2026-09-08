# ES→IE E2E gaps — remediation plan, 2026-08-22

*What the four genuine E2E failures actually are, after reading the handlers, and the exact fix for each. Honest headline up front: three of the four are **content or config, not code bugs** — the endpoints are correct and, in one case, deliberately fail-closed. I did not write throwaway patches for gaps that aren't code, because that would either fabricate legal content or bypass a privacy gate you built on purpose.*

---

## Summary

| Gap | Endpoint | Root cause | Class | Fix owner |
|---|---|---|---|---|
| AREA-3 | `GET /api/employee/geocode/autocomplete` | `GEOAPIFY_API_KEY` unset → returns `{disabled:true}` **by design** (DPA gate) | **Config** | You (set env when DPA signed) |
| DOC-1 | `GET /api/hr/cases/{id}/immigration-requirements` | `immigration_requirements` table has no ES→IE rows; endpoint correctly fails closed | **Content** (+ optional code bridge) | Corridor authoring |
| DOC-3 | `GET .../immigration/available-forms` | `form_templates` has no IE forms | **Content** (real gov PDFs) | Sourcing + admin CRUD |
| DOC-4 | `GET .../immigration/milestones` | `immigration_milestones` empty for the case; nothing seeds it | **Content / flow** | Seed from pathway (draft below) |

The common thread — and it's the same finding as the forward plan's #1 item — is that Ireland's verified content lives in **`requirement_items`** (29 rows, serving, powering the DOC-2 checklist that *passes*) and in the **CSEP pathway YAML** (representative, unverified), but the **immigration subsystem tables** (`immigration_requirements`, `form_templates`, `immigration_milestones`) that DOC-1/3/4 read were never populated for ES→IE. The code reads the right tables; the tables are empty.

---

## AREA-3 — geocode autocomplete → **config, not code**

`backend/app/routers/geocoding.py` returns `{"disabled": true, "suggestions": []}` whenever `GEOAPIFY_API_KEY` is unset, and its docstring states the intent: *"no PII leaves the platform until the DPA is signed and the key is configured."* The endpoint is working exactly as designed; the E2E reads it as a failure because it expects results.

**Fix (yours, ~2 minutes, once the Geoapify DPA is in place):** set `GEOAPIFY_API_KEY` in the Render backend service environment. `is_enabled()` flips automatically; no deploy or code change needed. Until the DPA is signed, leaving it unset is the correct posture — the intake UI degrades to a plain address input. I have deliberately **not** written code here: hardcoding a key or removing the `is_enabled()` guard would defeat a privacy control you put in on purpose (AIQ-1607).

*Optional code nicety (low priority):* the E2E check looks for a `results`/`predictions` key, but the endpoint returns `suggestions` + `disabled`. If you want the runner to score this correctly once keyed, that's a one-line change in `scripts/madrid_dublin_runner.mjs`, not in the product.

## DOC-1 — case immigration-requirements → **content (with an optional code bridge)**

`get_immigration_requirements` calls `immigration_requirement_service.get_requirements(corridor_from, corridor_to, visa_type, employee_type)`, which queries the `immigration_requirements` table. That table has DE/PT/US/UK/FR corridors and **no `*→IE`**, so the endpoint returns its structured `_uncovered_response` (`covered:false`, `requirements:[]`). This is intentional fail-closed behaviour (AIQ-832: never emit a silent default corridor).

Note the shape mismatch that matters here: `immigration_requirements` is a **document checklist** (what papers to file, with apostille / translation / processing metadata and `form_url`), whereas `requirement_items` holds **obligations** (rules like "183-day residence"). They are not the same content, so this is genuinely a "populate the document subsystem for ES→IE" task, not a rename.

**Recommended fix — author the ES→IE immigration document requirements** into `immigration_requirements` (via your corridor pipeline / `relopass-corridor-transfer`), covering the CSEP and D-visa document set: passport, in-date employment permit, signed contract / job offer, qualifications (apostilled/translated where required), proof of funds, police clearance, marriage/birth certs for dependants, etc. — each with a citation to the DETE/ISD page. The CSEP pathway's own `Required documents:` section is a starting inventory, but it is marked *representative, not SME-verified* — it must be verified before it becomes gate-bearing content, per your no-fabrication rule. I won't invent this list and commit it as verified.

**Optional interim code bridge (a product decision, not a blind patch):** make `get_immigration_requirements`, when `immigration_requirements` is empty for a *correctly-resolved* corridor that has `requirement_items` content, return that content in a clearly-labelled "corridor requirements" block (covered=true, sourced from requirement_items) instead of a bare "not covered." This unifies the two representations at read time — the forward plan's core recommendation — and gives HR *something* useful today. Caveat: it surfaces obligations in a view designed for documents, so it's a UX judgement call. **Say the word and I'll write it as a real diff + test on a branch** for you to review; I've held off because it changes a fail-closed immigration endpoint's semantics and deserves your explicit yes.

## DOC-3 — available immigration forms → **content (real government PDFs)**

`GET .../immigration/available-forms` reads `form_templates` (admin-managed via `admin_form_templates.py`), which has no IE templates. Forms are **actual fillable government PDFs** (CSEP/GEP application, long-stay 'D' visa application, PPSN application, IRP registration) plus their field maps. These have to be sourced from DETE / ISD / Revenue and loaded through the admin form-template flow. I can't fabricate government forms, and there's no code change that conjures them — this is a sourcing + data-entry task. Lower priority for Andrea than DOC-1/attestation, since the *guidance* (what to file) can be delivered via DOC-1 content before the fillable PDFs exist.

## DOC-4 — immigration milestones → **content/flow (draft below, derived from your verified rows)**

`list_milestones` reads `immigration_milestones WHERE case_id` — empty because nothing seeds a case's timeline. There is a `POST .../milestones` (manual) but no auto-seed from the corridor. Two decisions: (1) the milestone set for the corridor, and (2) whether it auto-seeds when a case's corridor is known or is created on the immigration-file-open step.

Here is a **draft ES→IE (CSEP) milestone timeline**, derived from the CSEP pathway sequence and the timing already verified in your `requirement_items` — i.e. transformed from content you've already sourced, **to be confirmed before seeding**, not invented:

| # | milestone_type | Anchor / lead time | Source basis (already in requirement_items / pathway) |
|---|---|---|---|
| 1 | csep_eligibility_confirmed | move − ~16 wks | CSEP occupation list + salary threshold rows |
| 2 | employment_permit_granted (DETE) | move − ~12 wks | CSEP eligibility row; EPA 2024 |
| 3 | d_visa_lodged (ISD) | after permit, up to 3 mo pre-travel | "entry visa after permit timing" row |
| 4 | d_visa_granted | ~8 wks after lodging | "entry visa after permit timing" row (~8-week decision) |
| 5 | dependant_join_family_visas | parallel with 3–4 | "dependant join family d visa required" (flagged) |
| 6 | travel_to_ireland | move date | pathway sequence |
| 7 | irp_stamp1_registration | within 90 days of arrival | "Stamp 1 / IRP registration"; Immigration Act 2004 s.9 |
| 8 | irp_card_received | ~10 working days after registration | "IRP card — timeline and fee" row |
| 9 | ppsn_application | on/after arrival | "PPSN" row |
| 10 | revenue_job_registration_rpn | immediately on starting work | "Register the job with Revenue" row |
| 11 | spouse_stamp1g_registration | after arrival | "spouse Stamp 1G" row (flagged) |

Every lead time above traces to a row a human already sourced. This is ready to drop into a seeder once you confirm the flow (auto-seed on case corridor assignment is my recommendation) and counsel has attested the underlying rows. **I can turn this into an actual seeder + POST calls once you pick the flow** — that one *is* code I can write safely.

---

## The real go-live gate: counsel attestation

Separate from all four gaps, and more important than any of them: **0 of Ireland's 42 requirement rows is counsel-attested.** The 29 serving rows are all `representative` (visible, awaiting counsel). The **counsel packet is delivered** (`ReloPass_ES-IE_Counsel_Attestation_Packet_2026-08-22.docx`) — 29 rows with official citations, the 4 lawyer-flagged rows leading, an Attest/Amend/Reject box per row. Getting that signed and promoting the rows to `attestation_status='attested'` is what makes ES→IE genuinely *sellable*, and it's the highest-leverage move on the board.

## Recommended order

1. **Send the counsel packet** (done — just forward it). This is the go-live gate and it's ready now.
2. **Set `GEOAPIFY_API_KEY`** once the DPA is signed — 2 minutes, closes AREA-3.
3. **Author + verify ES→IE immigration document requirements** into `immigration_requirements` (closes DOC-1 properly; I can scaffold the draft from the pathway for your verification).
4. **Seed the milestone timeline** above once the flow is chosen — I can write that seeder.
5. **Source the IE form PDFs** (DOC-3) — lowest urgency; DOC-1 content covers the guidance meanwhile.
6. *(Optional)* the DOC-1 read-bridge diff, if you want HR to see corridor content in that view before step 3 lands.

## Why I didn't hand you four patches

You built a platform whose entire value is that it never serves unverified content and never bypasses its own gates. Committing invented immigration document lists, fake form templates, or a key that defeats your DPA control would have violated exactly that. The honest, higher-value output is: the code is correct; here's the content/config each gap needs, a verified-derived milestone draft you can seed, the one code change I'll write on your say-so, and the counsel packet that unblocks the actual sale.

---

*Companion to the audit, forward plan, PR triage, live-check, and E2E report. No code changed, no production writes, no fabricated content.*
