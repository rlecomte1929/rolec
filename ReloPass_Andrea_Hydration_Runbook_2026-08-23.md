# ReloPass — Andrea case hydration runbook (ready to fire)

**Date:** 2026-08-23 · **Case:** `6ecadafe-0fdb-43c5-b8dc-0284e323cf51` (ES→IE, Madrid→Dublin, `roadmap_paid` — real paying customer)
**Prepared by:** Claude (Cowork) · **Blocking decision for Romain:** confirm her nationality (see §4).
**Status:** everything below is staged and verified against prod; **nothing has been written.** One value (nationality) needs your confirm, then it's a 2-minute run.

---

## 1. Root cause (verified in prod, not inferred)

Her case looks hollow because **her wizard draft is empty**, and the roadmap/serving both read from that draft:

- `wizard_cases.draft_json` for `6ecadafe…` is literally: `{"relocationBasics": {}, "employeeProfile": {}, "familyMembers": {}, "assignmentContext": {}}`
- The corridor overlay (`roadmap_corridor_overlay.corridor_overlay`, applied at **read time** in `cases_read.merge_corridor_overlay_v2` and `roadmap_builder.derive_roadmap`) reads:
  - `draft.relocationBasics.originCountry / destCountry` → `_resolve_pathway()`. Both empty → **returns None → no CSEP overlay → she sees the 16 generic scaffold milestones.**
  - `employeeProfile.nationality` → `nationality_class.classify(nat, dest)`. Empty → no clean THIRD_COUNTRY resolution.
- The corridor requirements she's *served* (`requirement_items`, 65 IE rows, 53 `THIRD_COUNTRY` / 6 `EU_EEA`) are scoped by nationality class. With nationality null her case cannot select the right scope.

So the fix is **not** a heavy regen and **not** more code — the code (CSEP overlay #1867/#2016, hydration #2002/#2003) is live. It's: **populate her draft.** The overlay renders on her next plan view.

Her child tables today: 16 generic milestones, **0** services / recommendation_slates / RFQs / vendor_shortlist / dependents / requirement_evaluations. `employee_id` null, `status`/`stage` null, profile still the null-filled family-of-four seed.

---

## 2. What she should be (target state)

- **Nationality:** Venezuelan → ISO `VE` → class `THIRD_COUNTRY` (**confirm — see §4**). Third country because VE is not EU/EEA/CH.
- **Corridor:** ES → IE (Madrid → Dublin). Pathway `corridors/ES_IE/pathways/CSEP_2026/v1.yaml` (13-step: Critical Skills Permit → long-stay D visa → IRP/Stamp 1 at Burgh Quay → PPSN → Revenue RPN).
- **Family:** family of 4 = spouse + 2 children → `maritalStatus: "partner_kids"`, spouse `wantsToWork: true` (from the existing seed).
- **Office:** Grand Canal Dock, Dublin (for the neighbourhood advisor / commute ranking, once run).

---

## 3. The hydration — two options (pick one; both need your nationality confirm)

### Option A — intended API path (safe; writes all stores + respects consent/field_source) — RECOMMENDED
Fill the draft, then the read-time overlay does the rest. Endpoints verified present in `main`:

1. **Set the corridor basics into the draft** — `PATCH /api/cases/6ecadafe-0fdb-43c5-b8dc-0284e323cf51/relocationBasics`
   ```json
   { "originCountry": "ES", "destCountry": "IE", "originCity": "Madrid", "destCity": "Dublin" }
   ```
2. **Set nationality + family** (HR path, no employee login needed) — `PATCH /api/hr/cases/6ecadafe…/profile/hr-fields`
   ```json
   { "nationality": "VE", "family_size": 4, "marital_status": "partner_kids", "field_source": "hr_provided" }
   ```
   (or the employee path `PUT /api/employee/cases/{id}/profile` once consent exists; HR path is faster for the demo.)
3. **View her plan** — `GET /api/cases/6ecadafe…/roadmap` (or open her case in-product). The CSEP overlay now resolves and renders. Confirm the 13 immigration steps replace the generic scaffold.
4. **Populate recommendations / vendors / RFQs** — hit the recommendation + curated-vendor surfaces for her case (the 29 curated Dublin vendors are already selected=true for her company). If a slate doesn't auto-compute on view, trigger the recommendation build for the case.

### Option B — direct draft write (fastest, demo-only; I can run this on your OK)
One `UPDATE` to `wizard_cases.draft_json` merging in the basics + nationality + family. This lights up the **roadmap + served requirements** immediately (they read the draft at render). It does **not** write the PII profile store or trigger the recommendation engine, so services/RFQs still need Option-A step 4. Exact statement staged (not run):
```sql
UPDATE public.wizard_cases
SET draft_json = jsonb_set(jsonb_set(jsonb_set(
      draft_json::jsonb,
      '{relocationBasics}', '{"originCountry":"ES","destCountry":"IE","originCity":"Madrid","destCity":"Dublin"}'::jsonb, true),
      '{employeeProfile}', '{"nationality":"VE"}'::jsonb, true),
      '{familyMembers}', '{"maritalStatus":"partner_kids","spouseWantsToWork":true,"childCount":2}'::jsonb, true)::text,
    updated_at = now()
WHERE id = '6ecadafe-0fdb-43c5-b8dc-0284e323cf51';
```

---

## 4. The one decision that's yours (blocking)

**Confirm Andrea's nationality.** The Aug-22 experience audit records her as **Venezuelan** (third-country), which is why the 9 `ve-ie-entry-family` facts were promoted for her. Nationality determines *which requirements she is legally served* (third-country visa/permit track vs EU/EEA free-mover), so it must be confirmed, not assumed.

- If **Venezuelan** → use `VE` above (THIRD_COUNTRY). ✅ default.
- If she actually holds an **EU/EEA** passport → she needs *none* of the CSEP/visa steps; tell me and I'll swap the payload (and she'd be served the 6 `EU_EEA` rows instead).

---

## 5. After hydration — verify (don't trust the write)

- `GET …/roadmap` shows the CSEP 13-step immigration route, not `task_profile_core` etc.
- Served requirements for her case return the `THIRD_COUNTRY` set (incl. the emergency-tax week-5 trap, IRP 90-day, CSEP 50:50) and **not** the EU/EEA-only rows.
- A recommendation slate + the 29 curated Dublin vendors appear on her profile; she can launch an RFQ.
- Re-check: `updated_at` on the case moves off 2026-08-16; `case_dependents` = 2.

## 6. Caveats
- Multiple case representations exist (`wizard_cases.draft_json`, `imm_employee_profiles`, `relocation_cases.profile_json`). Option A keeps them consistent; Option B populates only the draft (enough for roadmap + requirements, not recs). Prefer A for a real customer.
- This is a prod write on a real paying customer — hence the explicit nationality gate and the "verify after" step.
- Independent of the null-scope + review/attestation gate work (the 36-row worksheet) — that still applies to the corridor catalog; this is about *her case* pointing at it.

---

### Ready to fire
Say **"hydrate Andrea as VE / THIRD_COUNTRY"** (or give the correct nationality) and pick **A** (full, via API) or **B** (fast draft write, I run the SQL). I'll execute, then run §5 verification and report exactly what her case shows.
